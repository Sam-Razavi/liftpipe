"""Exercise catalogue and a push/pull/legs programme used by the generator.

Exercise titles match Hevy's built-in library so the synthetic CSV looks like a real
export. Starting loads and weekly gains describe an intermediate lifter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["weighted", "bodyweight", "duration", "cardio"]


@dataclass(frozen=True)
class Exercise:
    title: str
    kind: Kind
    start_kg: float = 0.0
    weekly_gain_kg: float = 0.0
    increment_kg: float = 2.5
    rep_range: tuple[int, int] = (8, 12)
    working_sets: int = 3
    warmups: int = 0


CATALOGUE: dict[str, Exercise] = {
    e.title: e
    for e in [
        Exercise("Bench Press (Barbell)", "weighted", 70, 0.9, 2.5, (5, 8), 3, 2),
        Exercise("Incline Bench Press (Dumbbell)", "weighted", 24, 0.25, 2.0, (8, 12), 3, 1),
        Exercise("Overhead Press (Barbell)", "weighted", 42.5, 0.4, 2.5, (5, 8), 3, 1),
        Exercise("Lateral Raise (Dumbbell)", "weighted", 10, 0.06, 2.0, (12, 15), 3),
        Exercise("Triceps Pushdown", "weighted", 25, 0.15, 2.5, (10, 15), 3),
        Exercise("Squat (Barbell)", "weighted", 95, 1.2, 2.5, (5, 8), 3, 2),
        Exercise("Romanian Deadlift (Barbell)", "weighted", 80, 0.8, 2.5, (8, 10), 3, 1),
        Exercise("Leg Press (Machine)", "weighted", 160, 1.5, 5.0, (10, 15), 3),
        Exercise("Lying Leg Curl (Machine)", "weighted", 40, 0.2, 2.5, (10, 15), 3),
        Exercise("Seated Calf Raise", "weighted", 50, 0.3, 5.0, (12, 20), 3),
        Exercise("Deadlift (Barbell)", "weighted", 130, 1.3, 2.5, (3, 5), 2, 2),
        Exercise("Pull Up", "bodyweight", rep_range=(6, 12), working_sets=3),
        Exercise("Lat Pulldown (Cable)", "weighted", 60, 0.4, 2.5, (8, 12), 3),
        Exercise("Bent Over Row (Barbell)", "weighted", 65, 0.6, 2.5, (6, 10), 3, 1),
        Exercise("Face Pull", "weighted", 20, 0.1, 2.5, (12, 20), 3),
        Exercise("Bicep Curl (Dumbbell)", "weighted", 12, 0.08, 2.0, (10, 12), 3),
        Exercise("Hammer Curl (Dumbbell)", "weighted", 14, 0.08, 2.0, (10, 12), 2),
        Exercise("Plank", "duration", working_sets=2),
        Exercise("Treadmill", "cardio", working_sets=1),
    ]
}

# Each session: workout title -> ordered exercises. The last two titles in a session
# are performed as a superset.
PROGRAMME: dict[str, list[str]] = {
    "Push": [
        "Bench Press (Barbell)",
        "Overhead Press (Barbell)",
        "Incline Bench Press (Dumbbell)",
        "Lateral Raise (Dumbbell)",
        "Triceps Pushdown",
    ],
    "Pull": [
        "Deadlift (Barbell)",
        "Pull Up",
        "Bent Over Row (Barbell)",
        "Lat Pulldown (Cable)",
        "Face Pull",
        "Bicep Curl (Dumbbell)",
        "Hammer Curl (Dumbbell)",
    ],
    "Legs": [
        "Squat (Barbell)",
        "Romanian Deadlift (Barbell)",
        "Leg Press (Machine)",
        "Lying Leg Curl (Machine)",
        "Seated Calf Raise",
        "Plank",
    ],
}

ROTATION = ["Push", "Pull", "Legs"]
