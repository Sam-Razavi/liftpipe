import shutil

from liftpipe.config import Settings
from liftpipe.ingest.pipeline import ingest_hevy
from liftpipe.ingest.raw_store import connect


def _count(con, table: str) -> int:
    return con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]


def test_overlapping_exports_do_not_duplicate(settings: Settings) -> None:
    con = connect(settings.warehouse_path)
    older, newer = ingest_hevy(settings, con)
    assert older.new_rows == older.rows_in_file
    assert 0 < newer.new_rows < newer.rows_in_file  # only the four extra weeks are new
    assert _count(con, "hevy_sets") == newer.rows_in_file


def test_rerun_is_a_no_op(settings: Settings) -> None:
    con = connect(settings.warehouse_path)
    ingest_hevy(settings, con)
    total = _count(con, "hevy_sets")
    again = ingest_hevy(settings, con)
    assert all(r.skipped for r in again)
    assert _count(con, "hevy_sets") == total


def test_same_content_under_new_name_is_skipped(settings: Settings, tmp_path) -> None:
    con = connect(settings.warehouse_path)
    ingest_hevy(settings, con)
    local = tmp_path / "hevy"
    shutil.copytree(settings.hevy_dir, local)
    newest = sorted(local.glob("*.csv"))[-1]
    shutil.copy(newest, local / "zz_renamed_copy.csv")
    settings.hevy_dir.unlink()
    settings.hevy_dir.symlink_to(local)
    results = ingest_hevy(settings, con)
    assert [r.skipped for r in results] == [True, True, True]


def test_newest_export_wins_for_edited_rows(settings: Settings, tmp_path) -> None:
    con = connect(settings.warehouse_path)
    local = tmp_path / "hevy"
    shutil.copytree(settings.hevy_dir, local)
    _older, newer = sorted(local.glob("*.csv"))
    # Simulate editing an old set's reps in the app before the second export.
    lines = newer.read_text().splitlines()
    target = next(i for i, line in enumerate(lines) if '"normal","' in line and i > 500)
    fields = lines[target].split('","')
    fields[10] = "99"
    lines[target] = '","'.join(fields)
    newer.write_text("\n".join(lines) + "\n")
    settings.hevy_dir.unlink()
    settings.hevy_dir.symlink_to(local)

    ingest_hevy(settings, con)
    assert con.execute("SELECT count(*) FROM raw.hevy_sets WHERE reps = 99").fetchone()[0] == 1
