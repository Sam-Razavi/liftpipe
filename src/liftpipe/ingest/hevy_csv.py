"""Hevy CSV export reader.

Natural keys, because the export carries no IDs:

* ``workout_id`` = hash of the workout's start time. A person cannot start two workouts
  in the same minute, and unlike the title it survives renaming a workout in the app.
* ``set_id`` = hash of ``workout_id``, the exercise's position in the workout and the
  set index. Position rather than exercise title keeps keys unique when the same
  exercise appears twice in one workout.

Exports are full-history snapshots, so loading an older and a newer export yields the
same keys for the overlapping history.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
from pydantic import TypeAdapter, ValidationError

from liftpipe.ingest.base import stable_hash
from liftpipe.models import HevySet

KG_PER_LB = 0.45359237
KM_PER_MILE = 1.609344

REQUIRED_COLUMNS = {
    "title",
    "start_time",
    "end_time",
    "exercise_title",
    "set_index",
    "set_type",
    "reps",
}

RAW_SCHEMA: dict[str, pl.DataType] = {
    "set_id": pl.String(),
    "workout_id": pl.String(),
    "workout_title": pl.String(),
    "start_time": pl.Datetime("us"),
    "end_time": pl.Datetime("us"),
    "description": pl.String(),
    "exercise_index": pl.Int32(),
    "exercise_title": pl.String(),
    "superset_id": pl.Int32(),
    "exercise_notes": pl.String(),
    "set_index": pl.Int32(),
    "set_type": pl.String(),
    "weight_kg": pl.Float64(),
    "reps": pl.Int32(),
    "distance_km": pl.Float64(),
    "duration_seconds": pl.Int32(),
    "rpe": pl.Float64(),
    "_source_file": pl.String(),
}

_rows = TypeAdapter(list[HevySet])


class HevyFormatError(ValueError):
    """The file does not look like a Hevy export."""


def _normalise_units(df: pl.DataFrame) -> pl.DataFrame:
    """Accounts set to imperial export ``weight_lbs``/``distance_miles``."""
    if "weight_lbs" in df.columns:
        df = df.with_columns(
            (pl.col("weight_lbs").replace("", None).cast(pl.Float64) * KG_PER_LB)
            .round(2)
            .alias("weight_kg")
        ).drop("weight_lbs")
    if "distance_miles" in df.columns:
        df = df.with_columns(
            (pl.col("distance_miles").replace("", None).cast(pl.Float64) * KM_PER_MILE)
            .round(3)
            .alias("distance_km")
        ).drop("distance_miles")
    for optional in ("weight_kg", "distance_km", "duration_seconds", "rpe", "superset_id"):
        if optional not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias(optional))
    return df


def read_hevy_csv(path: Path) -> pl.DataFrame:
    """Read, validate and key one Hevy CSV export."""
    df = pl.read_csv(path, infer_schema=False)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HevyFormatError(f"{path.name}: missing columns {sorted(missing)}")
    df = _normalise_units(df).rename({"title": "workout_title"})

    try:
        validated = _rows.validate_python(df.to_dicts())
    except ValidationError as exc:
        first = exc.errors()[0]
        row = first["loc"][0] if first["loc"] else "?"
        raise HevyFormatError(
            f"{path.name}: row {row} failed validation ({first['msg']}); "
            f"{exc.error_count()} error(s) in total"
        ) from exc

    model_schema = {name: RAW_SCHEMA[name] for name in HevySet.model_fields}
    frame = pl.DataFrame([r.model_dump() for r in validated], schema=model_schema)
    if frame.is_empty():
        return pl.DataFrame(schema=RAW_SCHEMA)

    frame = (
        frame.with_columns(
            pl.col("start_time")
            .map_elements(lambda t: stable_hash("hevy", t.isoformat()), return_dtype=pl.String)
            .alias("workout_id"),
            pl.lit(path.name).alias("_source_file"),
        )
        .with_columns(
            # A new exercise block starts whenever the title changes within a workout.
            (pl.col("exercise_title") != pl.col("exercise_title").shift(1))
            .over("workout_id")
            .fill_null(True)
            .alias("_new_block")
        )
        .with_columns(
            (pl.col("_new_block").cast(pl.Int32).cum_sum().over("workout_id") - 1).alias(
                "exercise_index"
            )
        )
        .with_columns(
            pl.struct("workout_id", "exercise_index", "set_index")
            .map_elements(
                lambda r: stable_hash(r["workout_id"], r["exercise_index"], r["set_index"]),
                return_dtype=pl.String,
            )
            .alias("set_id")
        )
    )
    return frame.select([pl.col(c).cast(t) for c, t in RAW_SCHEMA.items()])


@dataclass(frozen=True)
class HevyCsvSource:
    """``WorkoutSource`` backed by one Hevy CSV export."""

    path: Path
    name: str = "hevy_csv"

    def read(self) -> pl.DataFrame:
        return read_hevy_csv(self.path)
