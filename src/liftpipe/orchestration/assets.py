"""Ingestion and export assets.

Asset keys for raw tables (``raw/hevy_sets`` and so on) match the dbt source names, so
dagster-dbt wires them upstream of the staging models automatically.
"""

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSpec,
    MaterializeResult,
    MetadataValue,
    asset,
    multi_asset,
)
from dagster_dbt import get_asset_key_for_model

from liftpipe.config import get_settings
from liftpipe.export import EXPORTS, export_marts
from liftpipe.ingest.pipeline import ingest_apple_health, ingest_hevy
from liftpipe.ingest.raw_store import LoadResult, connect
from liftpipe.orchestration.dbt import liftpipe_dbt_assets


def _summary(results: list[LoadResult]) -> dict[str, MetadataValue]:
    table = "| file | rows | new | skipped |\n|---|---|---|---|\n" + "\n".join(
        f"| {r.file} | {r.rows_in_file} | {r.new_rows} | {r.skipped} |" for r in results
    )
    return {
        "files": MetadataValue.int(len(results)),
        "new_rows": MetadataValue.int(sum(r.new_rows for r in results)),
        "loads": MetadataValue.md(table),
    }


@asset(
    key=AssetKey(["raw", "hevy_sets"]),
    group_name="ingestion",
    kinds={"python", "polars", "duckdb"},
    description="Hevy CSV exports, validated (Pydantic, Pandera) and upserted by set_id.",
)
def hevy_sets(context: AssetExecutionContext) -> MaterializeResult:
    settings = get_settings()
    with connect(settings.warehouse_path) as con:
        results = ingest_hevy(settings, con)
        total = con.execute("SELECT count(*) FROM raw.hevy_sets").fetchone()[0]  # type: ignore[index]
    context.log.info("raw.hevy_sets now holds %d rows", total)
    return MaterializeResult(metadata={**_summary(results), "total_rows": MetadataValue.int(total)})


@multi_asset(
    specs=[
        AssetSpec(
            AssetKey(["raw", "health_records"]),
            group_name="ingestion",
            kinds={"python", "lxml", "duckdb"},
            description="Body-measurement records streamed from Apple Health export.xml.",
        ),
        AssetSpec(
            AssetKey(["raw", "health_workouts"]),
            group_name="ingestion",
            kinds={"python", "lxml", "duckdb"},
            description="Workouts streamed from Apple Health export.xml.",
        ),
    ],
)
def apple_health(context: AssetExecutionContext):
    settings = get_settings()
    with connect(settings.warehouse_path) as con:
        results = ingest_apple_health(settings, con)
    for table in ("health_records", "health_workouts"):
        own = [r for r in results if r.table == table]
        yield MaterializeResult(asset_key=AssetKey(["raw", table]), metadata=_summary(own))


@asset(
    group_name="serving",
    kinds={"parquet"},
    deps=[get_asset_key_for_model([liftpipe_dbt_assets], model) for model in EXPORTS],
    description="Mart tables exported as Parquet for the static DuckDB-WASM dashboard.",
)
def dashboard_parquet(context: AssetExecutionContext) -> MaterializeResult:
    counts = export_marts(get_settings().warehouse_path)
    context.log.info("exported %d tables", len(counts))
    return MaterializeResult(
        metadata={table: MetadataValue.int(rows) for table, rows in counts.items()}
    )
