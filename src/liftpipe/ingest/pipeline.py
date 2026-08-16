"""Ingestion entry points shared by the CLI, Dagster assets and tests."""

from __future__ import annotations

import logging

import duckdb

from liftpipe.config import Settings
from liftpipe.ingest.apple_health import parse_apple_health
from liftpipe.ingest.hevy_csv import HevyCsvSource
from liftpipe.ingest.raw_store import LoadResult, already_ingested, file_sha256, persist
from liftpipe.quality.schemas import (
    health_records_schema,
    health_workouts_schema,
    hevy_sets_schema,
)

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


def ingest_apple_health(settings: Settings, con: duckdb.DuckDBPyConnection) -> list[LoadResult]:
    results: list[LoadResult] = []
    for path in settings.apple_health_files():
        sha = file_sha256(path)
        tables = ("health_records", "health_workouts")
        if all(already_ingested(con, sha, t) for t in tables):
            log.info("skipping %s: already ingested", path.name)
            results += [LoadResult(t, path.name, 0, 0, skipped=True) for t in tables]
            continue
        frames = parse_apple_health(path)
        records = health_records_schema.validate(frames.records)
        workouts = health_workouts_schema.validate(frames.workouts)
        for table, frame in (("health_records", records), ("health_workouts", workouts)):
            result = persist(con, table, frame, path, settings.raw_dir, sha)
            log.info(
                "loaded %s into %s: %d rows, %d new",
                path.name,
                table,
                result.rows_in_file,
                result.new_rows,
            )
            results.append(result)
    return results


def ingest_all(settings: Settings, con: duckdb.DuckDBPyConnection) -> list[LoadResult]:
    return ingest_hevy(settings, con) + ingest_apple_health(settings, con)
