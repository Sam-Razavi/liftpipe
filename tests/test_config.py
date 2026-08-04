import pytest

from liftpipe.config import get_settings


def test_defaults_to_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIFTPIPE_SOURCE", raising=False)
    settings = get_settings()
    assert settings.source == "synthetic"
    assert settings.warehouse_path.name == "liftpipe_synthetic.duckdb"


def test_rejects_unknown_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFTPIPE_SOURCE", "prod")
    with pytest.raises(ValueError):
        get_settings()


def test_discovers_export_files(tmp_path) -> None:
    from liftpipe.config import Settings

    settings = Settings(source="real", data_dir=tmp_path)
    settings.hevy_dir.mkdir(parents=True)
    settings.apple_health_dir.mkdir(parents=True)
    (settings.hevy_dir / "workouts_2026-02-01.csv").touch()
    (settings.hevy_dir / "workouts_2026-01-01.csv").touch()
    (settings.apple_health_dir / "export.zip").touch()
    (settings.apple_health_dir / "notes.txt").touch()

    assert [p.name for p in settings.hevy_files()] == [
        "workouts_2026-01-01.csv",
        "workouts_2026-02-01.csv",
    ]
    assert [p.name for p in settings.apple_health_files()] == ["export.zip"]
