"""Pydantic models that every ingested row must satisfy.

Validation happens at the edge, before anything is written to Parquet, so malformed
exports fail loudly with the offending row instead of surfacing later as odd numbers
in a mart.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SetType = Literal["normal", "warmup", "failure", "dropset"]

HEVY_TIME_FORMATS = (
    "%d %b %Y, %H:%M",  # current export: "12 Aug 2024, 18:03"
    "%Y-%m-%d %H:%M:%S",  # older exports and API-style timestamps
    "%Y-%m-%dT%H:%M:%S",
)


def parse_hevy_time(value: str) -> datetime:
    for fmt in HEVY_TIME_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognised Hevy timestamp: {value!r}")


class HevySet(BaseModel):
    """One set from a Hevy export, normalised to kilograms and kilometres."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    workout_title: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    description: str | None = None
    exercise_title: str = Field(min_length=1)
    superset_id: int | None = None
    exercise_notes: str | None = None
    set_index: int = Field(ge=0)
    set_type: SetType
    weight_kg: float | None = Field(default=None, ge=0, le=1000)
    reps: int | None = Field(default=None, ge=0, le=1000)
    distance_km: float | None = Field(default=None, ge=0, le=1000)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    rpe: float | None = Field(default=None, ge=1, le=10)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _parse_time(cls, value: object) -> object:
        return parse_hevy_time(value) if isinstance(value, str) else value

    @field_validator(
        "description",
        "exercise_notes",
        "superset_id",
        "weight_kg",
        "reps",
        "distance_km",
        "duration_seconds",
        "rpe",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _end_after_start(self) -> HevySet:
        if self.end_time < self.start_time:
            raise ValueError("end_time is before start_time")
        return self


class HealthRecord(BaseModel):
    """A quantity sample from Apple Health (``<Record>``)."""

    model_config = ConfigDict(frozen=True)

    record_type: str
    source_name: str
    unit: str | None
    value: float
    start_date: datetime
    end_date: datetime
    creation_date: datetime | None = None


class HealthWorkout(BaseModel):
    """A workout from Apple Health (``<Workout>``)."""

    model_config = ConfigDict(frozen=True)

    activity_type: str
    source_name: str
    duration_min: float | None = Field(default=None, ge=0)
    total_energy_kcal: float | None = Field(default=None, ge=0)
    total_distance_km: float | None = Field(default=None, ge=0)
    start_date: datetime
    end_date: datetime
