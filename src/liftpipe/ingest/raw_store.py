"""Persist validated frames as Parquet and load them into DuckDB idempotently.

* Every input file becomes one Parquet batch under ``data/raw/<source>/<table>/``.
* ``raw._ingest_log`` records each file's SHA-256; an unchanged file is skipped.
* Raw tables have a primary key on the natural key and are loaded with
  ``INSERT OR REPLACE``. Files are processed oldest first, so for overlapping exports the
  newest version of a row wins, and re-loading the same data never creates duplicates.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import polars as pl

PRIMARY_KEYS = {
    "hevy_sets": "set_id",
    "health_records": "record_id",
    "health_workouts": "workout_id",
}

_DUCKDB_TYPES: dict[type[pl.DataType], str] = {
    pl.String: "VARCHAR",
    pl.Datetime: "TIMESTAMP",
    pl.Int32: "INTEGER",
    pl.Int64: "BIGINT",
    pl.Float64: "DOUBLE",
    pl.Boolean: "BOOLEAN",
}


@dataclass(frozen=True)
class LoadResult:
    table: str
    file: str
    rows_in_file: int
    new_rows: int
    skipped: bool = False


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(warehouse_path: Path) -> duckdb.DuckDBPyConnection:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw._ingest_log (
            sha256 VARCHAR NOT NULL,
            target_table VARCHAR NOT NULL,
            file_name VARCHAR NOT NULL,
            rows_in_file INTEGER NOT NULL,
            new_rows INTEGER NOT NULL,
            ingested_at TIMESTAMP NOT NULL,
            PRIMARY KEY (sha256, target_table)
        )
        """
    )
    return con


def already_ingested(con: duckdb.DuckDBPyConnection, sha256: str, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM raw._ingest_log WHERE sha256 = ? AND target_table = ?", [sha256, table]
    ).fetchone()
    return row is not None


def create_table(con: duckdb.DuckDBPyConnection, table: str, schema: pl.Schema) -> None:
    """Create ``raw.<table>`` from a Polars schema if it does not exist."""
    columns = [f'"{name}" {_DUCKDB_TYPES[type(dtype)]}' for name, dtype in schema.items()]
    columns.append('"_loaded_at" TIMESTAMP NOT NULL')
    key = PRIMARY_KEYS[table]
    con.execute(
        f"CREATE TABLE IF NOT EXISTS raw.{table} ({', '.join(columns)}, PRIMARY KEY ({key}))"
    )


def persist(
    con: duckdb.DuckDBPyConnection,
    table: str,
    frame: pl.DataFrame,
    source_file: Path,
    raw_dir: Path,
    sha256: str | None = None,
) -> LoadResult:
    """Write ``frame`` to a Parquet batch and upsert it into ``raw.<table>``."""
    sha256 = sha256 or file_sha256(source_file)
    batch = raw_dir / table / f"{source_file.stem}.parquet"
    batch.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(batch)

    create_table(con, table, frame.schema)
    now = datetime.now(UTC).replace(tzinfo=None)
    before = con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]  # type: ignore[index]
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(
            f"INSERT OR REPLACE INTO raw.{table} BY NAME "
            "SELECT *, ?::TIMESTAMP AS _loaded_at FROM read_parquet(?)",
            [now, str(batch)],
        )
        after = con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]  # type: ignore[index]
        con.execute(
            "INSERT OR REPLACE INTO raw._ingest_log VALUES (?, ?, ?, ?, ?, ?)",
            [sha256, table, source_file.name, frame.height, after - before, now],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return LoadResult(table, source_file.name, frame.height, after - before)
