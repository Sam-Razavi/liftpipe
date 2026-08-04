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


def test_prefers_zip_export(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from liftpipe.config import Settings

    settings = Settings(source="real", data_dir=tmp_path)
    settings.input_dir.mkdir(parents=True)
    assert settings.apple_health_export.name == "export.xml"
    (settings.input_dir / "export.zip").touch()
    assert settings.apple_health_export.name == "export.zip"
