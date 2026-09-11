import type { ReactNode } from "react";

type Entry = { name?: unknown; value?: unknown; color?: string; payload?: unknown };

export function ChartTooltip({
  active,
  payload,
  title,
  rows,
}: {
  active?: boolean;
  payload?: Entry[];
  title: ReactNode;
  rows: (payload: Entry[]) => { label: string; value: string; color?: string }[];
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <div className="t">{title}</div>
      {rows(payload).map((r) => (
        <div key={r.label} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {r.color && <span className="swatch dot" style={{ background: r.color }} />}
          <span>{r.label}</span>
          <strong style={{ marginLeft: "auto" }}>{r.value}</strong>
        </div>
      ))}
    </div>
  );
}
