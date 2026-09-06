"""Trigger a refresh when a new export file lands in the input folder."""

import hashlib

from dagster import (
    DefaultSensorStatus,
    RunRequest,
    SensorEvaluationContext,
    SkipReason,
    sensor,
)

from liftpipe.config import get_settings


@sensor(
    job_name="refresh_all",
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.STOPPED,
    description="Runs refresh_all when export files are added or changed.",
)
def new_export_sensor(context: SensorEvaluationContext):
    settings = get_settings()
    files = settings.hevy_files() + settings.apple_health_files()
    fingerprint = hashlib.sha256(
        "\n".join(f"{p.name}:{p.stat().st_size}:{p.stat().st_mtime_ns}" for p in files).encode()
    ).hexdigest()
    if not files:
        return SkipReason(f"no exports in {settings.input_dir}")
    if fingerprint == context.cursor:
        return SkipReason("no new or changed exports")
    context.update_cursor(fingerprint)
    return RunRequest(run_key=fingerprint)
