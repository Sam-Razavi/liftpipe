"""The contract every workout source implements.

Hevy's CSV export is the only connector today. Hevy also has a Pro-only REST API
(v0.0.1, unstable); it can be added later as another ``WorkoutSource`` returning the
same frame schema, without touching storage, dbt or the dashboard.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import polars as pl


class WorkoutSource(Protocol):
    """Yields set-level rows in the ``raw.hevy_sets`` schema."""

    name: str

    def read(self) -> pl.DataFrame:
        """Return validated rows with a stable ``set_id`` natural key."""
        ...


def stable_hash(*parts: object) -> str:
    """Deterministic 16-byte hex key; ``None`` and ``""`` hash identically."""
    joined = "\x1f".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode()).hexdigest()[:32]
