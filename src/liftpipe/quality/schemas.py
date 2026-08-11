"""Pandera schemas for raw frames.

Pydantic validates each row; these schemas check properties of the whole frame
(key uniqueness, allowed categories, plausible ranges) before it is persisted.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

SET_TYPES = ["normal", "warmup", "failure", "dropset"]

hevy_sets_schema = pa.DataFrameSchema(
    {
        "set_id": pa.Column(str, unique=True, nullable=False),
        "workout_id": pa.Column(str, nullable=False),
        "workout_title": pa.Column(str, nullable=False),
        "start_time": pa.Column(pl.Datetime("us"), nullable=False),
        "end_time": pa.Column(pl.Datetime("us"), nullable=False),
        "exercise_index": pa.Column(pl.Int32, pa.Check.ge(0)),
        "exercise_title": pa.Column(str, nullable=False),
        "set_index": pa.Column(pl.Int32, pa.Check.ge(0)),
        "set_type": pa.Column(str, pa.Check.isin(SET_TYPES)),
        "weight_kg": pa.Column(float, pa.Check.in_range(0, 1000), nullable=True),
        "reps": pa.Column(pl.Int32, pa.Check.in_range(0, 1000), nullable=True),
        "distance_km": pa.Column(float, pa.Check.ge(0), nullable=True),
        "duration_seconds": pa.Column(pl.Int32, pa.Check.ge(0), nullable=True),
        "rpe": pa.Column(float, pa.Check.in_range(1, 10), nullable=True),
    },
    checks=[
        pa.Check(
            lambda data: data.lazyframe.select(pl.col("end_time") >= pl.col("start_time")),
            error="workout ends before it starts",
        ),
    ],
    strict=False,
    name="raw.hevy_sets",
)

health_records_schema = pa.DataFrameSchema(
    {
        "record_id": pa.Column(str, unique=True, nullable=False),
        "record_type": pa.Column(str, nullable=False),
        "source_name": pa.Column(str, nullable=False),
        "value": pa.Column(float, nullable=False),
        "start_date": pa.Column(pl.Datetime("us"), nullable=False),
        "end_date": pa.Column(pl.Datetime("us"), nullable=False),
    },
    strict=False,
    name="raw.health_records",
)

health_workouts_schema = pa.DataFrameSchema(
    {
        "workout_id": pa.Column(str, unique=True, nullable=False),
        "activity_type": pa.Column(str, pa.Check.str_startswith("HKWorkoutActivityType")),
        "duration_min": pa.Column(float, pa.Check.in_range(0, 24 * 60), nullable=True),
        "total_energy_kcal": pa.Column(float, pa.Check.ge(0), nullable=True),
        "total_distance_km": pa.Column(float, pa.Check.ge(0), nullable=True),
        "start_date": pa.Column(pl.Datetime("us"), nullable=False),
        "end_date": pa.Column(pl.Datetime("us"), nullable=False),
    },
    strict=False,
    name="raw.health_workouts",
)
