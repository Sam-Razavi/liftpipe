"""Command-line entry point: ``python -m liftpipe.synthetic``.

Writes two overlapping snapshots per source, mimicking a user who exported once and
then again four weeks later. Loading both must yield the same tables as loading only
the newer one, which is how idempotency is exercised in tests and CI.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from liftpipe.config import Settings
from liftpipe.synthetic.apple_health import write_apple_health_zip
from liftpipe.synthetic.hevy import generate_sessions, write_hevy_csv

DEFAULT_END = date(2026, 7, 31)


def generate(
    out_dir: Path,
    seed: int = 42,
    weeks: int = 78,
    end: date = DEFAULT_END,
    noise_per_day: int = 24,
) -> list[Path]:
    settings = Settings(source="synthetic", data_dir=out_dir)
    start = end - timedelta(weeks=weeks) + timedelta(days=1)
    earlier = end - timedelta(weeks=4)
    sessions = generate_sessions(seed, start, end)
    written: list[Path] = []
    for snapshot in (earlier, end):
        hevy = settings.hevy_dir / f"workouts_{snapshot.isoformat()}.csv"
        write_hevy_csv(sessions, hevy, until=snapshot)
        apple = settings.apple_health_dir / f"export_{snapshot.isoformat()}.zip"
        write_apple_health_zip(apple, sessions, seed, start, snapshot, noise_per_day)
        written += [hevy, apple]
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Hevy and Apple Health exports")
    parser.add_argument("--out", type=Path, default=Path("data"), help="data directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weeks", type=int, default=78, help="length of training history")
    parser.add_argument(
        "--noise-per-day",
        type=int,
        default=24,
        help="irrelevant Health records per day; raise to produce a very large export.xml",
    )
    args = parser.parse_args()
    for path in generate(args.out, args.seed, args.weeks, noise_per_day=args.noise_per_day):
        print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
