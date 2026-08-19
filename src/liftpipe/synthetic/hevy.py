"""Synthetic training history written in Hevy's CSV export format.

Hevy exports one row per set with 14 columns. Times use the ``"12 Aug 2024, 18:03"``
format and loads are in kilograms (``weight_kg``) or pounds (``weight_lbs``) depending
on the account's unit setting. Every export is a full-history snapshot.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from faker import Faker

from liftpipe.synthetic.programme import CATALOGUE, PROGRAMME, ROTATION, Exercise

HEVY_TIME_FORMAT = "%d %b %Y, %H:%M"
KG_PER_LB = 0.45359237

HEVY_COLUMNS_KG = [
    "title",
    "start_time",
    "end_time",
    "description",
    "exercise_title",
    "superset_id",
    "exercise_notes",
    "set_index",
    "set_type",
    "weight_kg",
    "reps",
    "distance_km",
    "duration_seconds",
    "rpe",
]
HEVY_COLUMNS_LBS = [
    {"weight_kg": "weight_lbs", "distance_km": "distance_miles"}.get(c, c) for c in HEVY_COLUMNS_KG
]


@dataclass
class SetRow:
    exercise_title: str
    set_index: int
    set_type: str
    weight_kg: float | None = None
    reps: int | None = None
    distance_km: float | None = None
    duration_seconds: int | None = None
    rpe: float | None = None
    superset_id: int | None = None
    exercise_notes: str = ""


@dataclass
class Session:
    title: str
    start: datetime
    end: datetime
    description: str = ""
    sets: list[SetRow] = field(default_factory=list)


def _round_to(value: float, step: float) -> float:
    return round(round(value / step) * step, 2)


class _Lifter:
    """Tracks training age, fatigue and missed weeks to produce plausible loads."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng
        self.detraining = 0.0  # fraction of strength lost after a break

    def working_weight(self, ex: Exercise, week: int, deload: bool) -> float:
        # Diminishing returns: fast early gains, slower later.
        trend = ex.start_kg + ex.weekly_gain_kg * 14 * math.log1p(week / 14)
        weight = trend * (1 - self.detraining) * (0.85 if deload else 1.0)
        weight *= 1 + self.rng.normal(0, 0.015)
        return max(_round_to(weight, ex.increment_kg), ex.increment_kg)


def _reps_for(rng: np.random.Generator, ex: Exercise, set_no: int) -> int:
    lo, hi = ex.rep_range
    # Fatigue across sets: later sets tend towards the bottom of the range.
    centre = hi - (hi - lo) * (0.3 + 0.25 * set_no)
    return int(np.clip(round(rng.normal(centre, 1.0)), max(lo - 2, 1), hi + 2))


def _exercise_sets(
    rng: np.random.Generator,
    lifter: _Lifter,
    ex: Exercise,
    week: int,
    deload: bool,
    superset_id: int | None,
) -> list[SetRow]:
    rows: list[SetRow] = []
    if ex.kind == "cardio":
        minutes = float(rng.uniform(15, 30))
        speed = float(rng.uniform(9.0, 11.5))
        rows.append(
            SetRow(
                ex.title,
                0,
                "normal",
                distance_km=round(speed * minutes / 60, 2),
                duration_seconds=int(minutes * 60),
            )
        )
        return rows
    if ex.kind == "duration":
        for i in range(ex.working_sets):
            secs = int(np.clip(rng.normal(60 + week * 0.6, 10), 30, 180))
            rows.append(SetRow(ex.title, i, "normal", duration_seconds=secs))
        return rows

    weight = lifter.working_weight(ex, week, deload) if ex.kind == "weighted" else None
    idx = 0
    if weight is not None:
        for fraction in (0.5, 0.7)[: ex.warmups]:
            rows.append(
                SetRow(
                    ex.title,
                    idx,
                    "warmup",
                    weight_kg=_round_to(weight * fraction, ex.increment_kg),
                    reps=int(rng.integers(5, 9)),
                )
            )
            idx += 1
    for set_no in range(ex.working_sets):
        reps = _reps_for(rng, ex, set_no)
        if ex.kind == "bodyweight":
            reps = int(np.clip(reps + week // 12, 3, 20))
        set_type = "normal"
        last = set_no == ex.working_sets - 1
        if last and not deload and rng.random() < 0.12:
            set_type = "failure"
        rpe = None
        if rng.random() < 0.6:
            base = 7.0 if deload else 8.0 + 0.5 * set_no
            rpe = float(np.clip(round(rng.normal(base, 0.6) * 2) / 2, 6.0, 10.0))
        rows.append(SetRow(ex.title, idx, set_type, weight_kg=weight, reps=reps, rpe=rpe))
        idx += 1
        if last and weight is not None and ex.rep_range[0] >= 10 and rng.random() < 0.15:
            rows.append(
                SetRow(
                    ex.title,
                    idx,
                    "dropset",
                    weight_kg=_round_to(weight * 0.7, ex.increment_kg),
                    reps=_reps_for(rng, ex, 0),
                )
            )
            idx += 1
    for row in rows:
        row.superset_id = superset_id
    return rows


def generate_sessions(seed: int, start: date, end: date) -> list[Session]:
    """Generate a full training history between ``start`` and ``end`` (inclusive)."""
    rng = np.random.default_rng(seed)
    fake = Faker("sv_SE")
    fake.seed_instance(seed)
    lifter = _Lifter(rng)
    sessions: list[Session] = []
    rotation_pos = 0
    n_weeks = (end - start).days // 7 + 1

    for week in range(n_weeks):
        week_start = start + timedelta(weeks=week)
        if rng.random() < 0.08:  # holiday, illness or a busy week
            lifter.detraining = min(lifter.detraining + 0.04, 0.12)
            continue
        lifter.detraining = max(lifter.detraining - 0.02, 0.0)
        deload = week > 0 and week % 7 == 6
        n_sessions = int(rng.choice([2, 3, 4, 5], p=[0.08, 0.32, 0.42, 0.18]))
        days = sorted(rng.choice(7, size=n_sessions, replace=False).tolist())
        for day in days:
            session_date = week_start + timedelta(days=day)
            if session_date > end:
                break
            title = ROTATION[rotation_pos % len(ROTATION)]
            rotation_pos += 1
            weekend = session_date.weekday() >= 5
            hour = int(rng.integers(9, 14) if weekend else rng.choice([7, 17, 18, 19]))
            started = datetime.combine(session_date, datetime.min.time()).replace(
                hour=hour, minute=int(rng.integers(0, 60))
            )
            exercises = PROGRAMME[title]
            rows: list[SetRow] = []
            for i, name in enumerate(exercises):
                superset = 0 if i >= len(exercises) - 2 and title != "Legs" else None
                rows += _exercise_sets(rng, lifter, CATALOGUE[name], week, deload, superset)
            if title == "Legs" and rng.random() < 0.4:
                rows += _exercise_sets(rng, lifter, CATALOGUE["Treadmill"], week, deload, None)
            if rows and rng.random() < 0.1:
                rows[0].exercise_notes = fake.sentence(nb_words=6)
            duration = timedelta(minutes=int(len(rows) * rng.uniform(2.3, 3.2)))
            description = (
                "Deload week"
                if deload
                else (fake.sentence(nb_words=4) if rng.random() < 0.1 else "")
            )
            sessions.append(Session(title, started, started + duration, description, rows))
    return sessions


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def write_hevy_csv(
    sessions: list[Session],
    path: Path,
    until: date | None = None,
    units: str = "kg",
) -> int:
    """Write sessions as a Hevy CSV export. Returns the number of set rows written."""
    columns = HEVY_COLUMNS_KG if units == "kg" else HEVY_COLUMNS_LBS
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(columns)
        # Hevy lists the most recent workout first.
        for s in sorted(sessions, key=lambda s: s.start, reverse=True):
            if until is not None and s.start.date() > until:
                continue
            for r in s.sets:
                weight = r.weight_kg
                distance = r.distance_km
                if units == "lbs":
                    weight = None if weight is None else round(weight / KG_PER_LB, 1)
                    distance = None if distance is None else round(distance / 1.609344, 2)
                writer.writerow(
                    [
                        s.title,
                        s.start.strftime(HEVY_TIME_FORMAT),
                        s.end.strftime(HEVY_TIME_FORMAT),
                        s.description,
                        r.exercise_title,
                        _fmt(r.superset_id),
                        r.exercise_notes,
                        r.set_index,
                        r.set_type,
                        _fmt(weight),
                        _fmt(r.reps),
                        _fmt(distance),
                        _fmt(r.duration_seconds),
                        _fmt(r.rpe),
                    ]
                )
                n += 1
    return n
