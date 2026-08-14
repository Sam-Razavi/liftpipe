"""Synthetic Apple Health export (``export.xml`` inside ``export.zip``).

The writer streams elements to disk so large files (hundreds of MB) can be produced to
exercise the streaming parser. Structure mirrors a real export: an internal DTD, a
``Me`` element, ``Record`` elements (body measurements plus high-volume noise such as
step counts and heart rate), ``Workout`` elements with ``WorkoutStatistics`` children
and ``ActivitySummary`` rows.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import IO
from xml.sax.saxutils import quoteattr
from zoneinfo import ZoneInfo

import numpy as np
from faker import Faker

from liftpipe.synthetic.hevy import Session

APPLE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"
LOCAL_TZ = ZoneInfo("Europe/Stockholm")
ZIP_MEMBER = "apple_health_export/export.xml"

_DTD = """<!DOCTYPE HealthData [
<!ELEMENT HealthData (ExportDate,Me,(Record|Correlation|Workout|ActivitySummary)*)>
<!ATTLIST HealthData locale CDATA #REQUIRED>
<!ELEMENT ExportDate EMPTY>
<!ATTLIST ExportDate value CDATA #REQUIRED>
<!ELEMENT Record ((MetadataEntry|HeartRateVariabilityMetadataList)*)>
<!ATTLIST Record
  type          CDATA #REQUIRED
  unit          CDATA #IMPLIED
  value         CDATA #IMPLIED
  sourceName    CDATA #REQUIRED
  sourceVersion CDATA #IMPLIED
  device        CDATA #IMPLIED
  creationDate  CDATA #IMPLIED
  startDate     CDATA #REQUIRED
  endDate       CDATA #REQUIRED
>
<!ELEMENT Workout ((MetadataEntry|WorkoutEvent|WorkoutRoute|WorkoutStatistics)*)>
<!ATTLIST Workout
  workoutActivityType   CDATA #REQUIRED
  duration              CDATA #IMPLIED
  durationUnit          CDATA #IMPLIED
  sourceName            CDATA #REQUIRED
  sourceVersion         CDATA #IMPLIED
  creationDate          CDATA #IMPLIED
  startDate             CDATA #REQUIRED
  endDate               CDATA #REQUIRED
>
]>
"""

STRENGTH = "HKWorkoutActivityTypeTraditionalStrengthTraining"
RUNNING = "HKWorkoutActivityTypeRunning"


def _t(value: datetime) -> str:
    """Format a naive local time the way Health does: local wall clock plus UTC offset."""
    return value.replace(tzinfo=LOCAL_TZ).strftime(APPLE_TIME_FORMAT)


def _el(tag: str, attrs: dict[str, object], children: list[str] | None = None) -> str:
    rendered = " ".join(f"{k}={quoteattr(str(v))}" for k, v in attrs.items())
    if not children:
        return f" <{tag} {rendered}/>\n"
    inner = "".join(f"  {c}\n" for c in children)
    return f" <{tag} {rendered}>\n{inner} </{tag}>\n"


# Trends are defined over a fixed horizon, not the export length, so a later export
# reproduces earlier history exactly (as a real re-export would).
HORIZON_DAYS = 548


class _Body:
    """Slow recomposition: weight drifts down slightly while body fat falls."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng

    def weight(self, day: int) -> float:
        trend = 84.0 - 3.5 * day / HORIZON_DAYS + 0.8 * np.sin(day / 58)
        return round(float(trend + self.rng.normal(0, 0.45)), 1)

    def body_fat(self, day: int) -> float:
        trend = 0.195 - 0.04 * day / HORIZON_DAYS
        return round(float(trend + self.rng.normal(0, 0.006)), 3)


def _records(
    rng: np.random.Generator, watch: str, start: date, end: date, noise_per_day: int
) -> Iterator[str]:
    scale, phone = "Withings", "Health"
    n_days = (end - start).days + 1
    body = _Body(rng)
    first = datetime.combine(start, datetime.min.time())
    yield _el(
        "Record",
        {
            "type": "HKQuantityTypeIdentifierHeight",
            "sourceName": phone,
            "unit": "cm",
            "creationDate": _t(first),
            "startDate": _t(first),
            "endDate": _t(first),
            "value": 181,
        },
    )
    for day in range(n_days):
        midnight = first + timedelta(days=day)
        if rng.random() < 0.65:
            at = midnight + timedelta(hours=6, minutes=int(rng.integers(30, 150)))
            weight = body.weight(day)
            base = {"sourceName": scale, "creationDate": _t(at), "startDate": _t(at)}
            base["endDate"] = _t(at)
            yield _el(
                "Record",
                {"type": "HKQuantityTypeIdentifierBodyMass", **base, "unit": "kg", "value": weight},
            )
            if rng.random() < 0.05:  # the same weigh-in also typed in by hand
                yield _el(
                    "Record",
                    {
                        "type": "HKQuantityTypeIdentifierBodyMass",
                        **base,
                        "sourceName": phone,
                        "unit": "kg",
                        "value": round(weight + float(rng.normal(0, 0.2)), 1),
                    },
                )
            if rng.random() < 0.8:
                fat = body.body_fat(day)
                yield _el(
                    "Record",
                    {
                        "type": "HKQuantityTypeIdentifierBodyFatPercentage",
                        **base,
                        "unit": "%",
                        "value": fat,
                    },
                )
                yield _el(
                    "Record",
                    {
                        "type": "HKQuantityTypeIdentifierLeanBodyMass",
                        **base,
                        "unit": "kg",
                        "value": round(weight * (1 - fat), 1),
                    },
                )
                yield _el(
                    "Record",
                    {
                        "type": "HKQuantityTypeIdentifierBodyMassIndex",
                        **base,
                        "unit": "count",
                        "value": round(weight / 1.81**2, 1),
                    },
                )
        rest = midnight + timedelta(hours=23, minutes=50)
        yield _el(
            "Record",
            {
                "type": "HKQuantityTypeIdentifierRestingHeartRate",
                "sourceName": watch,
                "unit": "count/min",
                "creationDate": _t(rest),
                "startDate": _t(midnight),
                "endDate": _t(rest),
                "value": int(rng.normal(58 - 4 * day / HORIZON_DAYS, 2.5)),
            },
        )
        for i in range(noise_per_day):
            at = midnight + timedelta(minutes=int(i * 1440 / max(noise_per_day, 1)))
            yield _el(
                "Record",
                {
                    "type": "HKQuantityTypeIdentifierStepCount",
                    "sourceName": watch,
                    "unit": "count",
                    "creationDate": _t(at + timedelta(minutes=10)),
                    "startDate": _t(at),
                    "endDate": _t(at + timedelta(minutes=10)),
                    "value": int(rng.integers(0, 1400)),
                },
                [f'<MetadataEntry key="HKMetadataKeySyncVersion" value="{i % 3}"/>'],
            )


def _workout(
    activity: str,
    start: datetime,
    end: datetime,
    source: str,
    kcal: float,
    distance_km: float | None = None,
) -> str:
    minutes = (end - start).total_seconds() / 60
    stats = [
        f'<WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" '
        f'startDate="{_t(start)}" endDate="{_t(end)}" sum="{kcal:.1f}" unit="kcal"/>'
    ]
    if distance_km is not None:
        stats.append(
            f'<WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning" '
            f'startDate="{_t(start)}" endDate="{_t(end)}" sum="{distance_km:.2f}" unit="km"/>'
        )
    return _el(
        "Workout",
        {
            "workoutActivityType": activity,
            "duration": f"{minutes:.2f}",
            "durationUnit": "min",
            "sourceName": source,
            "creationDate": _t(end),
            "startDate": _t(start),
            "endDate": _t(end),
        },
        ['<MetadataEntry key="HKIndoorWorkout" value="1"/>', *stats],
    )


def _workouts(
    seed: int, watch: str, sessions: list[Session], start: date, end: date
) -> Iterator[str]:
    # Independent streams so a longer export does not shift earlier random draws.
    rng = np.random.default_rng(seed + 2)
    for s in sessions:
        if rng.random() < 0.85:  # the watch is not always worn
            minutes = (s.end - s.start).total_seconds() / 60
            yield _workout(STRENGTH, s.start, s.end, watch, minutes * rng.uniform(5, 7.5))
    rng = np.random.default_rng(seed + 3)
    day = start
    while day <= end:
        if rng.random() < 0.8:
            run_start = datetime.combine(day, datetime.min.time()) + timedelta(hours=10)
            km = float(rng.uniform(4, 10))
            run_end = run_start + timedelta(minutes=km * rng.uniform(5.2, 6.2))
            yield _workout(RUNNING, run_start, run_end, watch, km * 65, km)
        day += timedelta(days=int(rng.integers(5, 10)))


def write_apple_health_xml(
    fh: IO[str],
    sessions: list[Session],
    seed: int,
    start: date,
    end: date,
    noise_per_day: int = 24,
) -> None:
    rng = np.random.default_rng(seed + 1)
    fake = Faker("sv_SE")
    fake.seed_instance(seed)
    watch = f"{fake.first_name()}\u2019s Apple Watch"
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    fh.write(_DTD)
    fh.write('<HealthData locale="en_SE">\n')
    exported = datetime.combine(end, datetime.min.time()) + timedelta(hours=21)
    fh.write(f' <ExportDate value="{_t(exported)}"/>\n')
    fh.write(
        ' <Me HKCharacteristicTypeIdentifierDateOfBirth="1996-04-11" '
        'HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexMale" '
        'HKCharacteristicTypeIdentifierBloodType="HKBloodTypeNotSet"/>\n'
    )
    for record in _records(rng, watch, start, end, noise_per_day):
        fh.write(record)
    in_range = [s for s in sessions if s.start.date() <= end]
    for workout in _workouts(seed, watch, in_range, start, end):
        fh.write(workout)
    fh.write("</HealthData>\n")


def write_apple_health_zip(
    path: Path,
    sessions: list[Session],
    seed: int,
    start: date,
    end: date,
    noise_per_day: int = 24,
) -> None:
    """Write ``export.zip`` with the same member layout as the iPhone Health app."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf,
        zf.open(ZIP_MEMBER, "w") as raw,
        io.TextIOWrapper(raw, encoding="utf-8") as fh,
    ):
        write_apple_health_xml(fh, sessions, seed, start, end, noise_per_day)
