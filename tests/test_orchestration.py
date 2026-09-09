import pytest
from dagster import AssetKey, SkipReason, build_sensor_context

from liftpipe.config import Settings
from liftpipe.orchestration import sensors
from liftpipe.orchestration.definitions import defs


def test_definitions_load() -> None:
    defs.validate_loadable(defs)


def test_lineage_runs_from_raw_to_dashboard() -> None:
    graph = defs.resolve_asset_graph()
    staging = AssetKey(["staging", "stg_hevy__sets"])
    assert AssetKey(["raw", "hevy_sets"]) in graph.get(staging).parent_keys
    upstream = graph.get(AssetKey("dashboard_parquet")).parent_keys
    assert AssetKey(["marts", "mart_exercise_e1rm"]) in upstream


def test_sensor_fires_once_per_new_export(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sensors, "get_settings", lambda: settings)
    first = sensors.new_export_sensor(build_sensor_context())
    assert not isinstance(first, SkipReason)
    again = sensors.new_export_sensor(build_sensor_context(cursor=first.run_key))
    assert isinstance(again, SkipReason)
