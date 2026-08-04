"""Project paths and runtime settings.

Everything is derived from the repository root so the pipeline runs the same way
locally, in CI and inside Dagster. The data source (synthetic or real) is chosen
with the ``LIFTPIPE_SOURCE`` environment variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Source = Literal["synthetic", "real"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DBT_PROJECT_DIR = REPO_ROOT / "dbt" / "liftpipe"
DASHBOARD_DATA_DIR = REPO_ROOT / "dashboard" / "public" / "data"


@dataclass(frozen=True)
class Settings:
    source: Source
    data_dir: Path = DATA_DIR

    @property
    def input_dir(self) -> Path:
        return self.data_dir / self.source

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw" / self.source

    @property
    def warehouse_path(self) -> Path:
        return self.data_dir / "warehouse" / f"liftpipe_{self.source}.duckdb"

    @property
    def hevy_csv(self) -> Path:
        return self.input_dir / "workouts.csv"

    @property
    def apple_health_export(self) -> Path:
        """Apple Health export; ``export.zip`` is preferred over a bare ``export.xml``."""
        zipped = self.input_dir / "export.zip"
        return zipped if zipped.exists() else self.input_dir / "export.xml"


def get_settings() -> Settings:
    source = os.environ.get("LIFTPIPE_SOURCE", "synthetic")
    if source not in ("synthetic", "real"):
        raise ValueError(f"LIFTPIPE_SOURCE must be 'synthetic' or 'real', got {source!r}")
    return Settings(source=source)  # type: ignore[arg-type]
