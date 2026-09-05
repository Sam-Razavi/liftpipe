"""Ingest -> dbt build -> export on a small synthetic dataset."""

import json
import os
from pathlib import Path

import duckdb
import polars as pl
import pytest
from dbt.cli.main import dbtRunner

from liftpipe.config import DBT_PROJECT_DIR, Settings
from liftpipe.export import EXPORTS, export_marts
from liftpipe.ingest.pipeline import ingest_all
from liftpipe.ingest.raw_store import connect


def _dbt_build(warehouse: Path, target: Path) -> None:
    os.environ["LIFTPIPE_WAREHOUSE"] = str(warehouse)
    result = dbtRunner().invoke(
        [
            "build",
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR),
            "--target-path",
            str(target),
            "--quiet",
        ]
    )
    assert result.success, result.exception


@pytest.fixture
def built(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("LIFTPIPE_WAREHOUSE", str(settings.warehouse_path))
    with connect(settings.warehouse_path) as con:
        ingest_all(settings, con)
    _dbt_build(settings.warehouse_path, tmp_path / "target")
    return settings


def test_marts_reconcile_with_raw(built: Settings) -> None:
    with duckdb.connect(str(built.warehouse_path)) as con:
        raw_sets = con.sql("SELECT count(*) FROM raw.hevy_sets").fetchone()[0]
        fct_sets = con.sql("SELECT count(*) FROM marts.fct_sets").fetchone()[0]
        raw_workouts = con.sql("SELECT count(DISTINCT workout_id) FROM raw.hevy_sets").fetchone()[0]
        hevy_workouts = con.sql(
            "SELECT count(*) FROM marts.fct_workouts WHERE source = 'hevy'"
        ).fetchone()[0]
        weekly_sets = con.sql(
            "SELECT sum(working_sets) FROM marts.mart_weekly_muscle_volume"
        ).fetchone()[0]
        working_non_cardio = con.sql(
            """
            SELECT count(*) FROM marts.fct_sets f JOIN marts.dim_exercise d USING (exercise_id)
            WHERE f.is_working_set AND d.primary_muscle_group <> 'cardio'
            """
        ).fetchone()[0]
    assert fct_sets == raw_sets
    assert hevy_workouts == raw_workouts
    assert weekly_sets == working_non_cardio


def test_incremental_rebuild_is_stable(built: Settings, tmp_path: Path) -> None:
    query = "SELECT count(*), sum(volume_kg) FROM marts.fct_sets"
    with duckdb.connect(str(built.warehouse_path)) as con:
        before = con.sql(query).fetchone()
    _dbt_build(built.warehouse_path, tmp_path / "target2")
    with duckdb.connect(str(built.warehouse_path)) as con:
        assert con.sql(query).fetchone() == before


def test_export_writes_every_mart(built: Settings, tmp_path: Path) -> None:
    out = tmp_path / "public-data"
    counts = export_marts(built.warehouse_path, out)
    assert set(counts) == set(EXPORTS)
    for table, rows in counts.items():
        assert rows > 0
        assert pl.read_parquet(out / f"{table}.parquet").height == rows
    meta = json.loads((out / "meta.json").read_text())
    assert meta["tables"] == counts
