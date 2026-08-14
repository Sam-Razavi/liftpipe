import csv
import zipfile
from datetime import date

import pytest
from lxml import etree

from liftpipe.synthetic.__main__ import generate
from liftpipe.synthetic.apple_health import ZIP_MEMBER
from liftpipe.synthetic.hevy import (
    HEVY_COLUMNS_KG,
    HEVY_COLUMNS_LBS,
    generate_sessions,
    write_hevy_csv,
)

START, END = date(2026, 1, 5), date(2026, 3, 29)


@pytest.fixture(scope="module")
def sessions():
    return generate_sessions(7, START, END)


def test_sessions_are_deterministic(sessions) -> None:
    again = generate_sessions(7, START, END)
    assert [(s.title, s.start, len(s.sets)) for s in again] == [
        (s.title, s.start, len(s.sets)) for s in sessions
    ]


def test_sessions_are_plausible(sessions) -> None:
    weeks = (END - START).days / 7
    assert 2 * weeks <= len(sessions) <= 5 * weeks
    for s in sessions:
        assert START <= s.start.date() <= END
        assert s.end > s.start
        set_types = {r.set_type for r in s.sets}
        assert set_types <= {"normal", "warmup", "failure", "dropset"}


def test_hevy_csv_header_and_format(tmp_path, sessions) -> None:
    path = tmp_path / "workouts.csv"
    n = write_hevy_csv(sessions, path)
    with path.open() as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == HEVY_COLUMNS_KG
    assert len(rows) == n + 1
    # "29 Mar 2026, 18:03": newest workout first
    assert rows[1][1].endswith(":" + rows[1][1][-2:])
    assert "Mar 2026" in rows[1][1]


def test_hevy_csv_in_pounds(tmp_path, sessions) -> None:
    path = tmp_path / "workouts.csv"
    write_hevy_csv(sessions, path, units="lbs")
    with path.open() as fh:
        assert next(csv.reader(fh)) == HEVY_COLUMNS_LBS


def test_snapshot_cut_off(tmp_path, sessions) -> None:
    path = tmp_path / "workouts.csv"
    write_hevy_csv(sessions, path, until=date(2026, 2, 1))
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    assert all("Mar 2026" not in r["start_time"] for r in rows)


def test_generate_writes_overlapping_snapshots(tmp_path) -> None:
    paths = generate(tmp_path, seed=1, weeks=10, noise_per_day=2)
    names = sorted(p.name for p in paths)
    assert names == [
        "export_2026-07-03.zip",
        "export_2026-07-31.zip",
        "workouts_2026-07-03.csv",
        "workouts_2026-07-31.csv",
    ]
    older, newer = sorted(tmp_path.glob("synthetic/hevy/*.csv"))
    older_lines = set(older.read_text().splitlines())
    newer_lines = set(newer.read_text().splitlines())
    assert older_lines < newer_lines  # the later export contains the earlier one


def test_apple_export_is_well_formed(tmp_path) -> None:
    generate(tmp_path, seed=1, weeks=4, noise_per_day=2)
    export = sorted(tmp_path.glob("synthetic/apple_health/*.zip"))[-1]
    with zipfile.ZipFile(export) as zf, zf.open(ZIP_MEMBER) as fh:
        root = etree.parse(fh).getroot()
    assert root.tag == "HealthData"
    types = {r.get("type") for r in root.iter("Record")}
    assert "HKQuantityTypeIdentifierBodyMass" in types
    assert "HKQuantityTypeIdentifierBodyFatPercentage" in types
    assert root.find("Workout") is not None
    # Summer and winter dates carry their own UTC offsets.
    assert all(r.get("startDate")[-5:] in {"+0100", "+0200"} for r in root.iter("Record"))


def test_apple_snapshots_share_history(tmp_path) -> None:
    generate(tmp_path, seed=1, weeks=8, noise_per_day=1)
    older, newer = sorted(tmp_path.glob("synthetic/apple_health/*.zip"))

    def elements(path):
        with zipfile.ZipFile(path) as zf, zf.open(ZIP_MEMBER) as fh:
            root = etree.parse(fh).getroot()
        return {etree.tostring(e, with_tail=False) for e in root if e.tag in ("Record", "Workout")}

    assert elements(older) <= elements(newer)
