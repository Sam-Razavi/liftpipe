"""``python -m liftpipe.ingest``: load every export for the configured source."""

from __future__ import annotations

import logging

from liftpipe.config import get_settings
from liftpipe.ingest.pipeline import ingest_all
from liftpipe.ingest.raw_store import connect


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    with connect(settings.warehouse_path) as con:
        for r in ingest_all(settings, con):
            status = "skipped" if r.skipped else f"{r.rows_in_file} rows, {r.new_rows} new"
            print(f"{r.table:<16} {r.file:<28} {status}")


if __name__ == "__main__":
    main()
