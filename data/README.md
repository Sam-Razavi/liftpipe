# data/

| Folder | Contents | In git? |
| --- | --- | --- |
| `real/` | Your own Hevy CSV and Apple Health `export.zip` | Never |
| `synthetic/` | Output of `make synthetic` | No (regenerated) |
| `raw/` | Parquet batches written by ingestion | No |
| `warehouse/` | DuckDB database file | No |

To run on your own data, place `workouts.csv` (Hevy export) and `export.zip` (Apple Health export) in `data/real/` and run `make real`.
