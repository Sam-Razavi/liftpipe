// DuckDB-WASM in the browser, reading mart Parquet files exported by the pipeline.
import * as duckdb from "@duckdb/duckdb-wasm";
import ehWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url";
import mvpWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url";
import ehWasm from "@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url";
import mvpWasm from "@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url";

export const TABLES = [
  "dim_exercise",
  "fct_workouts",
  "mart_weekly_muscle_volume",
  "mart_exercise_e1rm",
  "mart_pr_history",
  "mart_body_trends",
  "mart_training_consistency",
] as const;

const BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
  eh: { mainModule: ehWasm, mainWorker: ehWorker },
};

let connection: Promise<duckdb.AsyncDuckDBConnection> | null = null;

async function init(): Promise<duckdb.AsyncDuckDBConnection> {
  const bundle = await duckdb.selectBundle(BUNDLES);
  const worker = new Worker(bundle.mainWorker!);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);

  // The files are small (under 100 kB in total), so fetch them whole rather than
  // relying on HTTP range requests.
  await Promise.all(
    TABLES.map(async (table) => {
      const response = await fetch(`${import.meta.env.BASE_URL}data/${table}.parquet`);
      if (!response.ok) throw new Error(`Could not load ${table}.parquet (${response.status})`);
      await db.registerFileBuffer(`${table}.parquet`, new Uint8Array(await response.arrayBuffer()));
    }),
  );
  const conn = await db.connect();
  for (const table of TABLES) {
    await conn.query(`CREATE VIEW ${table} AS SELECT * FROM read_parquet('${table}.parquet')`);
  }
  return conn;
}

export function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
  connection ??= init();
  return connection;
}

/** Run SQL and return plain objects. Cast dates to text and counts to INTEGER in SQL. */
export async function query<T>(sql: string): Promise<T[]> {
  const conn = await getConnection();
  const result = await conn.query(sql);
  return result.toArray().map((row) => row.toJSON() as T);
}
