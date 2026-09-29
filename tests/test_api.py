import io
import zipfile
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from liftpipe.api.app import ApiSettings, SlidingWindowLimiter, create_app
from liftpipe.export import EXPORTS


@pytest.fixture(scope="module")
def hevy_csv(synthetic_data_dir: Path) -> bytes:
    return sorted((synthetic_data_dir / "synthetic" / "hevy").glob("*.csv"))[-1].read_bytes()


def _client(**overrides) -> TestClient:
    settings = ApiSettings(**{"rate_limit_per_hour": 100, **overrides})
    return TestClient(create_app(settings))


def _upload(client: TestClient, content: bytes, name: str = "workouts.csv"):
    return client.post("/v1/dashboards", files={"file": (name, content, "text/csv")})


def test_healthz() -> None:
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_upload_returns_every_mart(hevy_csv: bytes) -> None:
    with _client() as client:
        response = _upload(client, hevy_csv)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = set(zf.namelist())
        assert names == {f"{table}.parquet" for table in EXPORTS} | {"meta.json"}
        rows = {t: pl.read_parquet(io.BytesIO(zf.read(f"{t}.parquet"))).height for t in EXPORTS}
    assert rows["fct_workouts"] > 0
    assert rows["mart_exercise_e1rm"] > 0
    assert rows["mart_weekly_muscle_volume"] > 0
    assert rows["mart_body_trends"] == 0  # a Hevy-only upload has no Apple Health data


def test_uploads_are_independent(hevy_csv: bytes) -> None:
    """A second, smaller upload must not see rows from the first."""
    lines = hevy_csv.decode().splitlines()
    small = "\n".join(lines[:1] + lines[1:60]).encode()
    with _client() as client:
        full = _upload(client, hevy_csv).content
        part = _upload(client, small).content

    def workouts(blob: bytes) -> int:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            return pl.read_parquet(io.BytesIO(zf.read("fct_workouts.parquet"))).height

    assert 0 < workouts(part) < workouts(full)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"Date,Workout Name,Exercise Name\n2024-01-01,A,B\n", "missing columns"),
        (b"\xff\xfe\x00 not text \x00\x01", "Hevy export"),
    ],
)
def test_rejects_non_hevy_files(content: bytes, message: str) -> None:
    with _client() as client:
        response = _upload(client, content)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_rejects_header_only_export() -> None:
    from liftpipe.synthetic.hevy import HEVY_COLUMNS_KG

    header = ",".join(f'"{c}"' for c in HEVY_COLUMNS_KG) + "\n"
    with _client() as client:
        response = _upload(client, header.encode())
    assert response.status_code == 400
    assert "no workouts" in response.json()["detail"]


def test_rejects_oversized_upload() -> None:
    with _client(max_upload_bytes=1024) as client:
        response = _upload(client, b"x" * 2048)
    assert response.status_code == 413
    assert "limit" in response.json()["detail"]


def test_rate_limit_applies_per_client() -> None:
    with _client(rate_limit_per_hour=2) as client:
        codes = [_upload(client, b"").status_code for _ in range(3)]
    assert codes == [400, 400, 429]  # the third request never reaches the parser


def test_sliding_window_expires() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=10)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)  # other clients are unaffected
    assert limiter.allow("a", now=11)  # the first hit has aged out


def test_cors_allows_only_configured_origins() -> None:
    with _client(cors_origins=("https://liftpipe.vercel.app",)) as client:
        ok = client.options(
            "/v1/dashboards",
            headers={
                "Origin": "https://liftpipe.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )
        other = client.options(
            "/v1/dashboards",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
    assert ok.headers.get("access-control-allow-origin") == "https://liftpipe.vercel.app"
    assert "access-control-allow-origin" not in other.headers
