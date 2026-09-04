"""Export mart tables to Parquet for the static dashboard.

The dashboard queries these files in the browser with DuckDB-WASM, so the deployed
site needs no server. Files are written with stable ordering so a rebuild from the
same inputs produces the same data.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from liftpipe.config import DASHBOARD_DATA_DIR

EXPORTS: dict[str, str] = {
    "dim_exercise": "exercise_title",
    "fct_workouts": "started_at, workout_id",
    "mart_weekly_muscle_volume": "week_start, muscle_group",
    "mart_exercise_e1rm": "exercise_title, workout_date",
    "mart_pr_history": "achieved_on, exercise_title, pr_type",
    "mart_body_trends": "metric, measured_on",
    "mart_training_consistency": "week_start",
}


def export_marts(warehouse_path: Path, out_dir: Path = DASHBOARD_DATA_DIR) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    # Not read-only: an in-process dbt run may still hold a read-write handle.
    with duckdb.connect(str(warehouse_path)) as con:
        for table, order_by in EXPORTS.items():
            target = out_dir / f"{table}.parquet"
            con.execute(
                f"COPY (SELECT * FROM marts.{table} ORDER BY {order_by}) "
                f"TO '{target}' (FORMAT parquet, COMPRESSION zstd)"
            )
            counts[table] = con.execute(f"SELECT count(*) FROM marts.{table}").fetchone()[0]  # type: ignore[index]
        first, last = con.execute(
            "SELECT min(workout_date), max(workout_date) FROM marts.fct_workouts"
        ).fetchone()  # type: ignore[misc]
    meta = {
        "tables": counts,
        "first_workout": str(first),
        "last_workout": str(last),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return counts


def main() -> None:
    from liftpipe.config import get_settings

    settings = get_settings()
    for table, rows in export_marts(settings.warehouse_path).items():
        print(f"{table:<28} {rows:>6} rows")


if __name__ == "__main__":
    main()
