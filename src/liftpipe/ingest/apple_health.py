"""Streaming reader for Apple Health ``export.xml`` (bare or inside ``export.zip``).

Exports routinely reach several gigabytes because every heart-rate and step sample is a
``<Record>``. The reader uses ``lxml.etree.iterparse`` and clears each element (and its
already-processed siblings) as soon as it has been read, so memory stays flat regardless
of file size. Only body-measurement records and workouts are kept.

Timestamps are written as local wall-clock time with a UTC offset
(``2025-02-03 07:31:02 +0100``). They are stored as naive local timestamps, matching
Hevy, with the offset kept in its own column.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO

import polars as pl
from lxml import etree

from liftpipe.ingest.base import stable_hash
from liftpipe.models import HealthRecord, HealthWorkout

BODY_RECORD_TYPES = frozenset(
    {
        "HKQuantityTypeIdentifierBodyMass",
        "HKQuantityTypeIdentifierBodyFatPercentage",
        "HKQuantityTypeIdentifierLeanBodyMass",
        "HKQuantityTypeIdentifierBodyMassIndex",
        "HKQuantityTypeIdentifierHeight",
        "HKQuantityTypeIdentifierWaistCircumference",
        "HKQuantityTypeIdentifierRestingHeartRate",
    }
)

RECORDS_SCHEMA: dict[str, pl.DataType] = {
    "record_id": pl.String(),
    "record_type": pl.String(),
    "source_name": pl.String(),
    "unit": pl.String(),
    "value": pl.Float64(),
    "start_date": pl.Datetime("us"),
    "end_date": pl.Datetime("us"),
    "creation_date": pl.Datetime("us"),
    "utc_offset": pl.String(),
    "_source_file": pl.String(),
}

WORKOUTS_SCHEMA: dict[str, pl.DataType] = {
    "workout_id": pl.String(),
    "activity_type": pl.String(),
    "source_name": pl.String(),
    "duration_min": pl.Float64(),
    "total_energy_kcal": pl.Float64(),
    "total_distance_km": pl.Float64(),
    "start_date": pl.Datetime("us"),
    "end_date": pl.Datetime("us"),
    "utc_offset": pl.String(),
    "_source_file": pl.String(),
}

_TO_KM = {"km": 1.0, "m": 0.001, "mi": 1.609344}
_TO_KCAL = {"kcal": 1.0, "Cal": 1.0, "kJ": 0.239006}
_TO_MIN = {"min": 1.0, "s": 1 / 60, "hr": 60.0}


class AppleHealthFormatError(ValueError):
    """The file is not a readable Apple Health export."""


@dataclass(frozen=True)
class AppleHealthFrames:
    records: pl.DataFrame
    workouts: pl.DataFrame


def _local_time(value: str) -> tuple[datetime, str]:
    """``'2025-02-03 07:31:02 +0100'`` -> (naive local datetime, ``'+0100'``)."""
    try:
        return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S"), value[20:].strip()
    except ValueError as exc:
        raise AppleHealthFormatError(f"unrecognised Health timestamp: {value!r}") from exc


@contextmanager
def _open_export(path: Path) -> Iterator[IO[bytes]]:
    if path.suffix.lower() != ".zip":
        with path.open("rb") as fh:
            yield fh
        return
    with zipfile.ZipFile(path) as zf:
        # The main file is export.xml; export_cda.xml holds clinical records we ignore.
        candidates = [
            info
            for info in zf.infolist()
            if info.filename.lower().endswith(".xml")
            and "cda" not in info.filename.lower()
            and "/workout-routes/" not in info.filename.lower()
        ]
        if not candidates:
            raise AppleHealthFormatError(f"{path.name}: no export.xml inside the archive")
        main = max(candidates, key=lambda info: info.file_size)
        with zf.open(main) as fh:
            yield fh


def _scaled(value: str | None, unit: str | None, table: dict[str, float]) -> float | None:
    if value is None:
        return None
    return float(value) * table.get(unit or "", 1.0)


def _workout_totals(elem: etree._Element) -> tuple[float | None, float | None]:
    """Energy and distance: legacy attributes, or ``WorkoutStatistics`` (iOS 16+)."""
    energy = _scaled(elem.get("totalEnergyBurned"), elem.get("totalEnergyBurnedUnit"), _TO_KCAL)
    distance = _scaled(elem.get("totalDistance"), elem.get("totalDistanceUnit"), _TO_KM)
    for stat in elem.iterchildren("WorkoutStatistics"):
        kind = stat.get("type", "")
        if energy is None and kind.endswith("ActiveEnergyBurned"):
            energy = _scaled(stat.get("sum"), stat.get("unit"), _TO_KCAL)
        elif distance is None and "Distance" in kind:
            distance = _scaled(stat.get("sum"), stat.get("unit"), _TO_KM)
    return energy, distance


def iter_elements(fh: IO[bytes]) -> Iterator[etree._Element]:
    """Yield ``Record`` and ``Workout`` elements, freeing memory behind the cursor."""
    context = etree.iterparse(
        fh,
        events=("end",),
        tag=("Record", "Workout"),
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=True,
    )
    for _, elem in context:
        yield elem
        elem.clear(keep_tail=True)
        # Drop siblings already processed (including ones the tag filter skipped).
        parent = elem.getparent()
        if parent is not None:
            while elem.getprevious() is not None:
                del parent[0]
    del context


def parse_apple_health(path: Path) -> AppleHealthFrames:
    records: list[dict[str, object]] = []
    workouts: list[dict[str, object]] = []
    source_file = path.name
    try:
        with _open_export(path) as fh:
            for elem in iter_elements(fh):
                if elem.tag == "Record":
                    record_type = elem.get("type")
                    if record_type not in BODY_RECORD_TYPES:
                        continue
                    start, offset = _local_time(elem.get("startDate", ""))
                    end, _ = _local_time(elem.get("endDate", ""))
                    created = elem.get("creationDate")
                    record = HealthRecord(
                        record_type=record_type,
                        source_name=elem.get("sourceName", ""),
                        unit=elem.get("unit"),
                        value=elem.get("value"),  # type: ignore[arg-type]
                        start_date=start,
                        end_date=end,
                        creation_date=_local_time(created)[0] if created else None,
                    )
                    records.append(
                        {
                            "record_id": stable_hash(
                                record.record_type,
                                record.source_name,
                                record.start_date.isoformat(),
                                record.end_date.isoformat(),
                                record.value,
                                record.unit,
                            ),
                            **record.model_dump(),
                            "utc_offset": offset,
                            "_source_file": source_file,
                        }
                    )
                else:
                    start, offset = _local_time(elem.get("startDate", ""))
                    end, _ = _local_time(elem.get("endDate", ""))
                    energy, distance = _workout_totals(elem)
                    workout = HealthWorkout(
                        activity_type=elem.get("workoutActivityType", ""),
                        source_name=elem.get("sourceName", ""),
                        duration_min=_scaled(
                            elem.get("duration"), elem.get("durationUnit"), _TO_MIN
                        ),
                        total_energy_kcal=energy,
                        total_distance_km=distance,
                        start_date=start,
                        end_date=end,
                    )
                    workouts.append(
                        {
                            "workout_id": stable_hash(
                                workout.activity_type,
                                workout.source_name,
                                workout.start_date.isoformat(),
                                workout.end_date.isoformat(),
                            ),
                            **workout.model_dump(),
                            "utc_offset": offset,
                            "_source_file": source_file,
                        }
                    )
    except etree.XMLSyntaxError as exc:
        raise AppleHealthFormatError(f"{path.name}: malformed XML ({exc})") from exc
    except zipfile.BadZipFile as exc:
        raise AppleHealthFormatError(f"{path.name}: not a valid zip archive") from exc

    # A record can legitimately be written twice in one export (sync retries).
    return AppleHealthFrames(
        records=pl.DataFrame(records, schema=RECORDS_SCHEMA)
        .unique("record_id", keep="last")
        .sort("start_date", "record_id"),
        workouts=pl.DataFrame(workouts, schema=WORKOUTS_SCHEMA)
        .unique("workout_id", keep="last")
        .sort("start_date", "workout_id"),
    )
