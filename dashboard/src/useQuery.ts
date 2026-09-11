import { useEffect, useState } from "react";
import { query } from "./db";

export type QueryState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; rows: T[] };

export function useQuery<T>(sql: string | null): QueryState<T> {
  const [state, setState] = useState<QueryState<T>>({ status: "loading" });
  useEffect(() => {
    if (sql === null) return;
    let cancelled = false;
    setState({ status: "loading" });
    query<T>(sql)
      .then((rows) => !cancelled && setState({ status: "ready", rows }))
      .catch((err: unknown) => !cancelled && setState({ status: "error", error: String(err) }));
    return () => {
      cancelled = true;
    };
  }, [sql]);
  return state;
}
