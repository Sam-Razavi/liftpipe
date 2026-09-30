# Upload API for Railway (or any container host). Build from the repository root.
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Dependencies first, so source changes do not invalidate this layer.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-group orchestration --no-install-project

COPY src ./src
COPY dbt ./dbt
RUN uv sync --locked --no-dev --no-group orchestration

# Run as an unprivileged user; uploads live only in a per-request temporary folder.
RUN useradd --create-home --uid 10001 liftpipe && chown -R liftpipe /app
USER liftpipe

ENV LIFTPIPE_MAX_UPLOAD_MB=10 LIFTPIPE_RATE_LIMIT_PER_HOUR=10 LIFTPIPE_TRUST_PROXY=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/healthz', timeout=3)"

# Railway supplies $PORT. One worker: DuckDB and dbt are CPU-bound, so scale with replicas.
CMD ["sh", "-c", "exec uvicorn liftpipe.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
