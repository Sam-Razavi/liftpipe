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
    def hevy_dir(self) -> Path:
        return self.input_dir / "hevy"

    @property
    def apple_health_dir(self) -> Path:
        return self.input_dir / "apple_health"

    def hevy_files(self) -> list[Path]:
        """All Hevy CSV exports, oldest first (exports are full-history snapshots)."""
        return sorted(self.hevy_dir.glob("*.csv"))

    def apple_health_files(self) -> list[Path]:
        """All Apple Health exports (``.zip`` or bare ``.xml``), oldest first."""
        files = [*self.apple_health_dir.glob("*.zip"), *self.apple_health_dir.glob("*.xml")]
        return sorted(files)


def get_settings() -> Settings:
    source = os.environ.get("LIFTPIPE_SOURCE", "synthetic")
    if source not in ("synthetic", "real"):
        raise ValueError(f"LIFTPIPE_SOURCE must be 'synthetic' or 'real', got {source!r}")
    return Settings(source=source)  # type: ignore[arg-type]
