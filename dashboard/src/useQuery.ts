import { useEffect, useState, useSyncExternalStore } from "react";
import { getSource, getVersion, query, subscribe } from "./db";

export type QueryState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; rows: T[] };

export const useDatasetVersion = () => useSyncExternalStore(subscribe, getVersion);
export const useDatasetSource = () => useSyncExternalStore(subscribe, getSource);

export function useQuery<T>(sql: string | null): QueryState<T> {
  const version = useDatasetVersion();
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
  }, [sql, version]);
  return state;
}
