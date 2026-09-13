import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtMonth, fmtNum, fmtShort, titleCase } from "../format";
import { MUSCLE_SETS_8W, muscleWeekly } from "../queries";
import { useQuery } from "../useQuery";
import { useThemeColors } from "../useThemeColors";
import { Card, DataTable, Loadable } from "./Card";
import { ChartTooltip } from "./ChartTooltip";

type MuscleRow = { muscle_group: string; weekly_sets: number; weekly_direct_sets: number };
type WeekRow = { week_start: string; sets: number; volume_kg: number };

export function MuscleVolume() {
  const c = useThemeColors();
  const muscles = useQuery<MuscleRow>(MUSCLE_SETS_8W);
  const [selected, setSelected] = useState("chest");
  const weekly = useQuery<WeekRow>(muscleWeekly(selected));

  return (
    <Card
      className="span-7"
      title="Weekly sets per muscle group"
      subtitle="Average over the last 8 weeks. Secondary muscles count half a set. Select a bar to see its history."
    >
      <Loadable state={muscles} height={300}>
        {(rows) => (
          <>
            <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 26)}>
              <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }} barCategoryGap={4}>
                <CartesianGrid horizontal={false} stroke={c.grid} />
                <XAxis type="number" tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="muscle_group"
                  width={92}
                  interval={0}
                  tickFormatter={titleCase}
                  tick={{ fill: c["text-secondary"], fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: c["surface-2"] }}
                  content={(p) => (
                    <ChartTooltip
                      {...p}
                      title={titleCase(String(p.label ?? ""))}
                      rows={(payload) => {
                        const row = payload[0] as unknown as { payload: MuscleRow };
                        return [
                          { label: "Sets per week", value: fmtNum(row.payload.weekly_sets) },
                          { label: "Direct sets", value: fmtNum(row.payload.weekly_direct_sets) },
                        ];
                      }}
                    />
                  )}
                />
                <Bar
                  dataKey="weekly_sets"
                  radius={[0, 4, 4, 0]}
                  isAnimationActive={false}
                  onClick={(d: { muscle_group?: string }) => d.muscle_group && setSelected(d.muscle_group)}
                  style={{ cursor: "pointer" }}
                >
                  {rows.map((r) => (
                    <Cell
                      key={r.muscle_group}
                      fill={r.muscle_group === selected ? c["series-1"] : c["series-1-soft"]}
                      stroke={c["surface-1"]}
                      strokeWidth={1}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <label style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Muscle group{" "}
              <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                {rows.map((r) => (
                  <option key={r.muscle_group} value={r.muscle_group}>{titleCase(r.muscle_group)}</option>
                ))}
              </select>
            </label>
          </>
        )}
      </Loadable>
      <Loadable state={weekly} height={160}>
        {(rows) => (
          <>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={rows} margin={{ left: 0, right: 8, top: 12, bottom: 0 }} barCategoryGap={1}>
                <CartesianGrid vertical={false} stroke={c.grid} />
                <XAxis dataKey="week_start" tickFormatter={fmtMonth} minTickGap={40} tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis width={36} tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: c["surface-2"] }}
                  content={(p) => (
                    <ChartTooltip
                      {...p}
                      title={`Week of ${fmtShort(String(p.label ?? ""))}`}
                      rows={(payload) => [{ label: `${titleCase(selected)} sets`, value: fmtNum(Number(payload[0].value)) }]}
                    />
                  )}
                />
                <Bar dataKey="sets" fill={c["series-1"]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
            <DataTable
              rows={rows}
              label={`Show weekly data for ${titleCase(selected)}`}
              columns={[
                { key: "week_start", label: "Week" },
                { key: "sets", label: "Sets", numeric: true, format: (v) => fmtNum(Number(v)) },
                { key: "volume_kg", label: "Volume (kg)", numeric: true, format: (v) => fmtNum(Number(v), 0) },
              ]}
            />
          </>
        )}
      </Loadable>
    </Card>
  );
}
