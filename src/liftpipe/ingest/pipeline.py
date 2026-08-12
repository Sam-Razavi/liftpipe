"""Ingestion entry points shared by the CLI, Dagster assets and tests."""

from __future__ import annotations

import logging

import duckdb

from liftpipe.config import Settings
from liftpipe.ingest.hevy_csv import HevyCsvSource
from liftpipe.ingest.raw_store import LoadResult, already_ingested, file_sha256, persist
from liftpipe.quality.schemas import hevy_sets_schema

log = logging.getLogger(__name__)


def ingest_hevy(settings: Settings, con: duckdb.DuckDBPyConnection) -> list[LoadResult]:
    results: list[LoadResult] = []
    for path in settings.hevy_files():
        sha = file_sha256(path)
        if already_ingested(con, sha, "hevy_sets"):
            log.info("skipping %s: already ingested", path.name)
            results.append(LoadResult("hevy_sets", path.name, 0, 0, skipped=True))
            continue
        frame = hevy_sets_schema.validate(HevyCsvSource(path).read())
        result = persist(con, "hevy_sets", frame, path, settings.raw_dir, sha)
        log.info("loaded %s: %d rows, %d new", path.name, result.rows_in_file, result.new_rows)
        results.append(result)
    return results
