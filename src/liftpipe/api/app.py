"""FastAPI app: ``POST /v1/dashboards`` turns a Hevy CSV into the dashboard's mart Parquet.

Uploads are processed in a temporary folder that is deleted before the response is sent.
File contents are never logged. Limits are deliberately small because the service is a
free public demo: 10 MB per file, a per-IP hourly quota and a cap on concurrent builds.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from liftpipe.api.service import DashboardBuildError, build_dashboard_zip, prepare_parse_cache
from liftpipe.ingest.hevy_csv import HevyFormatError


@dataclass(frozen=True)
class ApiSettings:
    max_upload_bytes: int = 10 * 1024 * 1024
    rate_limit_per_hour: int = 10
    max_concurrent_builds: int = 1
    queue_timeout_seconds: float = 30.0
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:4173")
    trust_proxy: bool = False

    @classmethod
    def from_env(cls) -> ApiSettings:
        env = os.environ
        origins = env.get("LIFTPIPE_CORS_ORIGINS")
        return cls(
            max_upload_bytes=int(float(env.get("LIFTPIPE_MAX_UPLOAD_MB", "10")) * 1024 * 1024),
            rate_limit_per_hour=int(env.get("LIFTPIPE_RATE_LIMIT_PER_HOUR", "10")),
            max_concurrent_builds=int(env.get("LIFTPIPE_MAX_CONCURRENT_BUILDS", "1")),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip())
            if origins
            else cls.cors_origins,
            trust_proxy=env.get("LIFTPIPE_TRUST_PROXY") == "1",
        )


@dataclass
class SlidingWindowLimiter:
    """Per-client request quota over a rolling hour. In memory, so per process."""

    limit: int
    window_seconds: float = 3600.0
    _hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def allow(self, client: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[client]
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def _client_id(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Behind Railway's proxy the last entry is the address the proxy itself saw.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    limiter = SlidingWindowLimiter(settings.rate_limit_per_hour)
    slots = asyncio.Semaphore(settings.max_concurrent_builds)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await run_in_threadpool(prepare_parse_cache)  # parse the dbt project once, up front
        yield

    app = FastAPI(
        title="liftpipe upload API",
        version="0.1.0",
        description="Upload a Hevy CSV export; receive the dashboard's mart Parquet files.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/dashboards",
        response_class=Response,
        responses={
            200: {"content": {"application/zip": {}}, "description": "Mart Parquet and meta.json"},
            400: {"description": "Not a valid Hevy export"},
            413: {"description": "File too large"},
            422: {"description": "The data failed a quality check"},
            429: {"description": "Rate limit exceeded"},
            503: {"description": "Busy, try again shortly"},
        },
    )
    async def create_dashboard(request: Request, file: Annotated[UploadFile, File()]) -> Response:
        if not limiter.allow(_client_id(request, settings.trust_proxy)):
            raise HTTPException(429, "Rate limit reached; try again later.")

        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > settings.max_upload_bytes + 4096:
            raise HTTPException(413, _too_large(settings))
        content = await file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(413, _too_large(settings))
        if not content.strip():
            raise HTTPException(400, "The file is empty.")

        try:
            await asyncio.wait_for(slots.acquire(), settings.queue_timeout_seconds)
        except TimeoutError:
            raise HTTPException(503, "The server is busy; try again in a minute.") from None
        try:
            archive = await run_in_threadpool(build_dashboard_zip, content)
        except HevyFormatError as exc:
            raise HTTPException(400, f"This does not look like a Hevy export: {exc}") from exc
        except DashboardBuildError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            slots.release()

        return Response(
            archive,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="liftpipe-dashboard.zip"',
                "Cache-Control": "no-store",
            },
        )

    return app


def _too_large(settings: ApiSettings) -> str:
    return f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."


app = create_app()
