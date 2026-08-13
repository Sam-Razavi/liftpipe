from pathlib import Path

import pytest

from liftpipe.config import Settings
from liftpipe.synthetic.__main__ import generate


@pytest.fixture(scope="session")
def synthetic_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two overlapping snapshots per source, 16 weeks of history."""
    data_dir = tmp_path_factory.mktemp("data")
    generate(data_dir, seed=3, weeks=16, noise_per_day=4)
    return data_dir


@pytest.fixture
def settings(synthetic_data_dir: Path, tmp_path: Path) -> Settings:
    """Settings reading the shared synthetic exports but writing to a fresh warehouse."""
    target = tmp_path / "data"
    (target / "synthetic").mkdir(parents=True)
    for sub in ("hevy", "apple_health"):
        (target / "synthetic" / sub).symlink_to(synthetic_data_dir / "synthetic" / sub)
    return Settings(source="synthetic", data_dir=target)
