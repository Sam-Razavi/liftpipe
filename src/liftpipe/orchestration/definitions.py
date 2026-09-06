"""Dagster entry point: ``dagster dev -m liftpipe.orchestration.definitions``."""

from __future__ import annotations

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    Definitions,
    ScheduleDefinition,
    define_asset_job,
    in_process_executor,
)
from dagster_dbt import DbtCliResource

from liftpipe.orchestration.assets import apple_health, dashboard_parquet, hevy_sets
from liftpipe.orchestration.dbt import dbt_project, liftpipe_dbt_assets
from liftpipe.orchestration.sensors import new_export_sensor

refresh_all = define_asset_job(
    "refresh_all",
    selection=AssetSelection.all(),
    description="Ingest every export, build and test all dbt models, export the marts.",
)

nightly = ScheduleDefinition(
    job=refresh_all,
    cron_schedule="0 4 * * *",
    execution_timezone="Europe/Stockholm",
    default_status=DefaultScheduleStatus.STOPPED,
)

defs = Definitions(
    assets=[hevy_sets, apple_health, liftpipe_dbt_assets, dashboard_parquet],
    jobs=[refresh_all],
    schedules=[nightly],
    sensors=[new_export_sensor],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
    # One DuckDB file accepts a single writer, so steps run sequentially in one process.
    executor=in_process_executor,
)
