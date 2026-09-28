"""Build dashboard marts from one Hevy CSV in a throwaway DuckDB file.

This reuses the batch pipeline unchanged: the same reader, validation, raw store, dbt
project and exporter. Only the wiring differs. Apple Health tables are created empty so
every model still builds, and the body-measurement charts simply show no data.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

import polars as pl

from liftpipe.config import DBT_PROJECT_DIR
from liftpipe.export import export_marts
from liftpipe.ingest.apple_health import RECORDS_SCHEMA, WORKOUTS_SCHEMA
from liftpipe.ingest.hevy_csv import HevyFormatError, read_hevy_csv
from liftpipe.ingest.raw_store import connect, create_table, persist
from liftpipe.quality.schemas import hevy_sets_schema

DBT_TIMEOUT_SECONDS = 120

# `dbt` as a subprocess keeps each request's warehouse path in its own environment, so
# concurrent builds cannot see each other's DuckDB file.
_DBT_LAUNCHER = "from dbt.cli.main import cli; cli()"


PARSE_CACHE = Path(tempfile.gettempdir()) / "liftpipe-dbt-parse-cache"
_parse_lock = threading.Lock()


class DashboardBuildError(RuntimeError):
    """The uploaded data parsed but failed a dbt model or data-quality test."""


WAREHOUSE_NAME = "warehouse.duckdb"


def _dbt_env() -> dict[str, str]:
    # A constant, relative warehouse path keeps the rendered dbt profile identical for
    # every request (dbt discards its parse cache when the profile changes). Each build
    # runs with its own work folder as the working directory, so the file stays private.
    return {
        **os.environ,
        "LIFTPIPE_WAREHOUSE": WAREHOUSE_NAME,
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
    }


def prepare_parse_cache() -> None:
    """Parse the dbt project once; requests start from this cache instead of re-parsing.

    dbt's partial-parse file lives in the target folder. Each request gets its own target
    folder (so builds never share state) seeded with a copy of this file, which saves
    around five seconds per upload.
    """
    with _parse_lock:
        if (PARSE_CACHE / "partial_parse.msgpack").exists():
            return
        PARSE_CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                "-c",
                _DBT_LAUNCHER,
                "parse",
                "--project-dir",
                str(DBT_PROJECT_DIR),
                "--profiles-dir",
                str(DBT_PROJECT_DIR),
                "--target-path",
                str(PARSE_CACHE),
                "--log-path",
                str(PARSE_CACHE / "logs"),
                "--quiet",
            ],
            env=_dbt_env(),
            cwd=PARSE_CACHE,
            check=True,
            capture_output=True,
            timeout=DBT_TIMEOUT_SECONDS,
        )


def _run_dbt(workdir: Path) -> None:
    prepare_parse_cache()
    target = workdir / "target"
    target.mkdir(exist_ok=True)
    shutil.copy(PARSE_CACHE / "partial_parse.msgpack", target / "partial_parse.msgpack")
    command = [
        sys.executable,
        "-c",
        _DBT_LAUNCHER,
        "build",
        "--exclude",
        "resource_type:unit_test",
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
        "--target-path",
        str(target),
        "--log-path",
        str(workdir / "logs"),
        "--no-use-colors",
    ]
    try:
        result = subprocess.run(
            command,
            env=_dbt_env(),
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=DBT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DashboardBuildError("building the dashboard took too long") from exc
    if result.returncode != 0:
        failures = [
            line.split("[", 1)[0].strip() or line.strip()
            for line in result.stdout.splitlines()
            if " FAIL " in line or " ERROR " in line
        ]
        detail = "; ".join(dict.fromkeys(failures))[:300]
        raise DashboardBuildError(
            f"data quality checks failed: {detail}" if detail else "dbt failed"
        )


def build_dashboard_files(csv_bytes: bytes, workdir: Path) -> Path:
    """Run the pipeline for one upload and return the folder holding the mart Parquet."""
    upload = workdir / "hevy" / "workouts.csv"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(csv_bytes)

    try:
        frame = hevy_sets_schema.validate(read_hevy_csv(upload))
    except pl.exceptions.PolarsError as exc:
        raise HevyFormatError("could not read the file as a CSV") from exc
    except UnicodeDecodeError as exc:
        raise HevyFormatError("the file is not UTF-8 text") from exc
    if frame.is_empty():
        raise HevyFormatError("the export contains no workouts")

    warehouse = workdir / WAREHOUSE_NAME
    with connect(warehouse) as con:
        persist(con, "hevy_sets", frame, upload, workdir / "raw")
        create_table(con, "health_records", pl.Schema(RECORDS_SCHEMA))
        create_table(con, "health_workouts", pl.Schema(WORKOUTS_SCHEMA))

    _run_dbt(workdir)
    out_dir = workdir / "marts"
    export_marts(warehouse, out_dir)
    return out_dir


def build_dashboard_zip(csv_bytes: bytes) -> bytes:
    """Return a zip of the mart Parquet files and ``meta.json``. Nothing is kept on disk."""
    with tempfile.TemporaryDirectory(prefix="liftpipe-") as tmp:
        out_dir = build_dashboard_files(csv_bytes, Path(tmp))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
            for path in sorted(out_dir.iterdir()):
                zf.write(path, path.name)
        return buffer.getvalue()
