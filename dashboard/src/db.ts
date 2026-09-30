// DuckDB-WASM in the browser, reading mart Parquet files exported by the pipeline.
// The demo loads the bundled synthetic marts; an upload replaces them with the marts
// the API built from the visitor's own Hevy CSV.
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

export type DatasetSource = "demo" | "upload";

const BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
  eh: { mainModule: ehWasm, mainWorker: ehWorker },
};

type Engine = { db: duckdb.AsyncDuckDB; conn: duckdb.AsyncDuckDBConnection };
let engine: Promise<Engine> | null = null;

// A tiny store so components re-query when the dataset is swapped.
let version = 0;
let source: DatasetSource = "demo";
const listeners = new Set<() => void>();
export const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};
export const getVersion = () => version;
export const getSource = () => source;

async function registerAndView(
  { db, conn }: Engine,
  files: Record<(typeof TABLES)[number], Uint8Array>,
) {
  for (const table of TABLES) {
    await db.registerFileBuffer(`${table}.parquet`, files[table]);
    await conn.query(`CREATE OR REPLACE VIEW ${table} AS SELECT * FROM read_parquet('${table}.parquet')`);
  }
}

async function fetchDemoFiles() {
  // The demo files are small (under 100 kB in total), so fetch them whole rather than
  // relying on HTTP range requests.
  const entries = await Promise.all(
    TABLES.map(async (table) => {
      const response = await fetch(`${import.meta.env.BASE_URL}data/${table}.parquet`);
      if (!response.ok) throw new Error(`Could not load ${table}.parquet (${response.status})`);
      return [table, new Uint8Array(await response.arrayBuffer())] as const;
    }),
  );
  return Object.fromEntries(entries) as Record<(typeof TABLES)[number], Uint8Array>;
}

async function init(): Promise<Engine> {
  const bundle = await duckdb.selectBundle(BUNDLES);
  const worker = new Worker(bundle.mainWorker!);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  const conn = await db.connect();
  const instance = { db, conn };
  await registerAndView(instance, await fetchDemoFiles());
  return instance;
}

export function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
  engine ??= init();
  return engine.then((e) => e.conn);
}

function publish(next: DatasetSource) {
  source = next;
  version += 1;
  listeners.forEach((fn) => fn());
}

/** Replace the marts with Parquet files built from an upload. */
export async function loadUploadedDataset(files: Record<string, Uint8Array>): Promise<void> {
  const missing = TABLES.filter((t) => !files[`${t}.parquet`]);
  if (missing.length) throw new Error(`The response is missing ${missing.join(", ")}`);
  engine ??= init();
  const instance = await engine;
  await registerAndView(
    instance,
    Object.fromEntries(TABLES.map((t) => [t, files[`${t}.parquet`]])) as Record<
      (typeof TABLES)[number],
      Uint8Array
    >,
  );
  publish("upload");
}

export async function restoreDemoDataset(): Promise<void> {
  engine ??= init();
  await registerAndView(await engine, await fetchDemoFiles());
  publish("demo");
}

/** Run SQL and return plain objects. Cast dates to text and counts to INTEGER in SQL. */
export async function query<T>(sql: string): Promise<T[]> {
  const conn = await getConnection();
  const result = await conn.query(sql);
  return result.toArray().map((row) => row.toJSON() as T);
}
