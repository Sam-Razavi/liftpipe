import { useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { fmtDate, fmtMonth, fmtNum } from "../format";
import { bodyTrend } from "../queries";
import { useQuery } from "../useQuery";
import { useThemeColors } from "../useThemeColors";
import { Card, DataTable, Loadable } from "./Card";
import { ChartTooltip } from "./ChartTooltip";

type Row = { day: string; value: number | null; rolling_7d_avg: number | null };

const METRICS = [
  { key: "body_mass_kg", label: "Weight", unit: "kg" },
  { key: "body_fat_pct", label: "Body fat", unit: "%" },
  { key: "lean_body_mass_kg", label: "Lean mass", unit: "kg" },
  { key: "resting_hr_bpm", label: "Resting HR", unit: "bpm" },
] as const;

export function BodyTrend() {
  const c = useThemeColors();
  const [metric, setMetric] = useState<(typeof METRICS)[number]>(METRICS[0]);
  const state = useQuery<Row>(bodyTrend(metric.key));

  return (
    <Card
      className="span-5"
      title="Body measurements"
      subtitle="Apple Health readings with a 7-day rolling average."
      controls={
        <div className="seg" role="group" aria-label="Metric">
          {METRICS.map((m) => (
            <button key={m.key} type="button" aria-pressed={m.key === metric.key} onClick={() => setMetric(m)}>
              {m.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="legend" aria-hidden="true">
        <span><i className="swatch" style={{ background: c["series-2"] }} />7-day average</span>
        <span><i className="swatch dot" style={{ background: c["text-muted"] }} />Daily reading</span>
      </div>
      <Loadable state={state} height={260}>
        {(rows) => (
          <>
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={rows} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={c.grid} />
                <XAxis dataKey="day" tickFormatter={fmtMonth} minTickGap={40} tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis width={40} domain={["auto", "auto"]} tickFormatter={(v: number) => fmtNum(v, 0)} tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ stroke: c["text-muted"], strokeDasharray: "3 3" }}
                  content={(p) => {
                    const row = (p.payload?.[0] as unknown as { payload?: Row } | undefined)?.payload;
                    return (
                      <ChartTooltip
                        {...p}
                        title={fmtDate(String(p.label ?? ""))}
                        rows={() =>
                          row
                            ? [
                                { label: "Reading", value: row.value === null ? "none" : `${fmtNum(row.value)} ${metric.unit}`, color: c["text-muted"] },
                                { label: "7-day avg", value: `${fmtNum(row.rolling_7d_avg)} ${metric.unit}`, color: c["series-2"] },
                              ]
                            : []
                        }
                      />
                    );
                  }}
                />
                <Scatter dataKey="value" fill={c["text-muted"]} fillOpacity={0.45} shape="circle" isAnimationActive={false} />
                <Line type="monotone" dataKey="rolling_7d_avg" stroke={c["series-2"]} strokeWidth={2} dot={false} connectNulls activeDot={{ r: 4, stroke: c["surface-1"], strokeWidth: 2 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <DataTable
              rows={rows.filter((r) => r.value !== null).reverse()}
              columns={[
                { key: "day", label: "Date" },
                { key: "value", label: `Reading (${metric.unit})`, numeric: true, format: (v) => fmtNum(v as number) },
                { key: "rolling_7d_avg", label: "7-day avg", numeric: true, format: (v) => fmtNum(v as number, 2) },
              ]}
            />
          </>
        )}
      </Loadable>
    </Card>
  );
}
