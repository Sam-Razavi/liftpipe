# data/

| Folder | Contents | In git? |
| --- | --- | --- |
| `real/` | Your own Hevy CSV and Apple Health `export.zip` | Never |
| `synthetic/` | Output of `make synthetic` | No (regenerated) |
| `raw/` | Parquet batches written by ingestion | No |
| `warehouse/` | DuckDB database file | No |

To run on your own data, place Hevy CSV exports in `data/real/hevy/` and Apple Health `export.zip` files in `data/real/apple_health/`, then run `make real`. Several exports may sit side by side; overlapping history is de-duplicated on load.
