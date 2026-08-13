import csv
from pathlib import Path

import polars as pl
import pytest

from liftpipe.ingest.hevy_csv import HevyFormatError, read_hevy_csv
from liftpipe.synthetic.hevy import HEVY_COLUMNS_KG, HEVY_COLUMNS_LBS

ROWS = [
    # title, start, end, description, exercise, superset, notes, idx, type, w, reps, km, s, rpe
    [
        "Push",
        "12 Aug 2024, 18:03",
        "12 Aug 2024, 19:10",
        "",
        "Bench Press (Barbell)",
        "",
        "",
        "0",
        "warmup",
        "40",
        "8",
        "",
        "",
        "",
    ],
    [
        "Push",
        "12 Aug 2024, 18:03",
        "12 Aug 2024, 19:10",
        "",
        "Bench Press (Barbell)",
        "",
        "",
        "1",
        "normal",
        "80",
        "5",
        "",
        "",
        "8.5",
    ],
    [
        "Push",
        "12 Aug 2024, 18:03",
        "12 Aug 2024, 19:10",
        "",
        "Lateral Raise (Dumbbell)",
        "0",
        "",
        "0",
        "normal",
        "10",
        "12",
        "",
        "",
        "",
    ],
    # The same exercise again later in the workout restarts set_index at 0.
    [
        "Push",
        "12 Aug 2024, 18:03",
        "12 Aug 2024, 19:10",
        "",
        "Bench Press (Barbell)",
        "",
        "",
        "0",
        "dropset",
        "60",
        "10",
        "",
        "",
        "",
    ],
    [
        "Legs",
        "14 Aug 2024, 07:30",
        "14 Aug 2024, 08:20",
        "",
        "Treadmill",
        "",
        "",
        "0",
        "normal",
        "",
        "",
        "3.2",
        "1200",
        "",
    ],
]


def _write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_parses_types_and_times(tmp_path: Path) -> None:
    df = read_hevy_csv(_write(tmp_path / "w.csv", HEVY_COLUMNS_KG, ROWS))
    assert df.height == 5
    first = df.row(1, named=True)
    assert first["start_time"].isoformat() == "2024-08-12T18:03:00"
    assert first["weight_kg"] == 80.0
    assert first["reps"] == 5
    assert first["rpe"] == 8.5
    assert df["superset_id"].to_list()[2] == 0
    cardio = df.filter(pl.col("exercise_title") == "Treadmill").row(0, named=True)
    assert cardio["weight_kg"] is None
    assert cardio["distance_km"] == 3.2


def test_keys_are_unique_and_stable(tmp_path: Path) -> None:
    a = read_hevy_csv(_write(tmp_path / "a.csv", HEVY_COLUMNS_KG, ROWS))
    b = read_hevy_csv(_write(tmp_path / "b.csv", HEVY_COLUMNS_KG, ROWS))
    assert a["set_id"].n_unique() == a.height
    assert a["set_id"].to_list() == b["set_id"].to_list()
    assert a["workout_id"].n_unique() == 2
    # Repeated exercise gets its own block, so its set 0 does not collide with the first.
    assert a["exercise_index"].to_list() == [0, 0, 1, 2, 0]


def test_renaming_a_workout_keeps_its_id(tmp_path: Path) -> None:
    renamed = [["Push day", *r[1:]] if r[0] == "Push" else r for r in ROWS]
    a = read_hevy_csv(_write(tmp_path / "a.csv", HEVY_COLUMNS_KG, ROWS))
    b = read_hevy_csv(_write(tmp_path / "b.csv", HEVY_COLUMNS_KG, renamed))
    assert a["workout_id"].to_list() == b["workout_id"].to_list()


def test_converts_imperial_units(tmp_path: Path) -> None:
    rows = [[*r[:9], "176.4" if r[9] == "80" else r[9], *r[10:]] for r in ROWS]
    rows[4][11] = "2"  # miles
    df = read_hevy_csv(_write(tmp_path / "lbs.csv", HEVY_COLUMNS_LBS, rows))
    assert df.row(1, named=True)["weight_kg"] == pytest.approx(80.01, abs=0.01)
    assert df.row(4, named=True)["distance_km"] == pytest.approx(3.219, abs=0.001)


def test_accepts_iso_timestamps(tmp_path: Path) -> None:
    rows = [[r[0], "2024-08-12 18:03:00", "2024-08-12 19:10:00", *r[3:]] for r in ROWS[:1]]
    df = read_hevy_csv(_write(tmp_path / "iso.csv", HEVY_COLUMNS_KG, rows))
    assert df["start_time"][0].isoformat() == "2024-08-12T18:03:00"


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        (8, "superset", "set_type"),
        (10, "-3", "reps"),
        (1, "yesterday", "timestamp"),
    ],
)
def test_rejects_invalid_rows(tmp_path: Path, column: int, value: str, message: str) -> None:
    rows = [list(r) for r in ROWS]
    rows[2][column] = value
    with pytest.raises(HevyFormatError, match="row 2"):
        read_hevy_csv(_write(tmp_path / "bad.csv", HEVY_COLUMNS_KG, rows))


def test_rejects_non_hevy_file(tmp_path: Path) -> None:
    path = tmp_path / "strong.csv"
    path.write_text("Date,Workout Name,Exercise Name\n2024-01-01,A,B\n")
    with pytest.raises(HevyFormatError, match="missing columns"):
        read_hevy_csv(path)


def test_empty_export(tmp_path: Path) -> None:
    df = read_hevy_csv(_write(tmp_path / "empty.csv", HEVY_COLUMNS_KG, []))
    assert df.is_empty()
    assert "set_id" in df.columns
