import type { ReactNode } from "react";
import type { QueryState } from "../useQuery";

type Props = {
  title: string;
  subtitle?: string;
  controls?: ReactNode;
  className?: string;
  children: ReactNode;
};

export function Card({ title, subtitle, controls, className = "", children }: Props) {
  return (
    <section className={`card ${className}`} aria-label={title}>
      <div className="card-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="sub">{subtitle}</p>}
        </div>
        {controls && <div className="controls">{controls}</div>}
      </div>
      {children}
    </section>
  );
}

/** Loading and error states shared by every card. */
export function Loadable<T>({
  state,
  height = 260,
  children,
}: {
  state: QueryState<T>;
  height?: number;
  children: (rows: T[]) => ReactNode;
}) {
  if (state.status === "loading")
    return <div className="state" style={{ minHeight: height }}>Loading…</div>;
  if (state.status === "error")
    return <div className="state" role="alert" style={{ minHeight: height }}>Query failed: {state.error}</div>;
  if (state.rows.length === 0)
    return <div className="state" style={{ minHeight: height }}>No data yet.</div>;
  return <>{children(state.rows)}</>;
}

export type Column<T> = {
  key: keyof T;
  label: string;
  numeric?: boolean;
  format?: (value: T[keyof T], row: T) => string;
};

/** The table view behind each chart, for screen readers and exact values. */
export function DataTable<T>({ rows, columns, label = "Show data" }: { rows: T[]; columns: Column<T>[]; label?: string }) {
  return (
    <details className="data">
      <summary>{label}</summary>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={String(c.key)} className={c.numeric ? "num" : undefined}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={String(c.key)} className={c.numeric ? "num" : undefined}>
                    {c.format ? c.format(row[c.key], row) : String(row[c.key] ?? "–")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
