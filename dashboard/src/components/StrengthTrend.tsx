import { useEffect, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { fmtDate, fmtMonth, fmtNum, fmtSigned, titleCase } from "../format";
import { EXERCISES, exerciseTrend } from "../queries";
import { useQuery } from "../useQuery";
import { useThemeColors } from "../useThemeColors";
import { Card, DataTable, Loadable } from "./Card";
import { ChartTooltip } from "./ChartTooltip";

type ExerciseRow = { exercise_title: string; sessions: number };
type TrendRow = {
  day: string;
  best_e1rm_kg: number;
  rolling_28d_best_e1rm_kg: number;
  top_set_kg: number;
  pct_change_28d: number | null;
  overload_trend: string;
};

const PREFERRED = ["Bench Press (Barbell)", "Squat (Barbell)", "Deadlift (Barbell)"];

export function StrengthTrend() {
  const c = useThemeColors();
  const exercises = useQuery<ExerciseRow>(EXERCISES);
  const [exercise, setExercise] = useState<string | null>(null);

  useEffect(() => {
    if (exercise === null && exercises.status === "ready" && exercises.rows.length) {
      const names = exercises.rows.map((r) => r.exercise_title);
      setExercise(PREFERRED.find((p) => names.includes(p)) ?? names[0]);
    }
  }, [exercises, exercise]);

  const trend = useQuery<TrendRow>(exercise ? exerciseTrend(exercise) : null);
  const latest = trend.status === "ready" ? trend.rows[trend.rows.length - 1] : undefined;

  return (
    <Card
      className="span-7"
      title="Estimated one-rep max"
      subtitle="Epley formula on working sets of 1–12 reps. The line is the best of the last 28 days."
      controls={
        exercises.status === "ready" && (
          <select aria-label="Exercise" value={exercise ?? ""} onChange={(e) => setExercise(e.target.value)}>
            {exercises.rows.map((r) => (
              <option key={r.exercise_title} value={r.exercise_title}>{r.exercise_title}</option>
            ))}
          </select>
        )
      }
    >
      {latest && (
        <p className="sub" style={{ marginBottom: 6 }}>
          Rolling best {fmtNum(latest.rolling_28d_best_e1rm_kg)} kg,{" "}
          {fmtSigned(latest.pct_change_28d)} % vs four weeks earlier{" "}
          <span className={`trend ${latest.overload_trend}`}>{titleCase(latest.overload_trend)}</span>
        </p>
      )}
      <div className="legend" aria-hidden="true">
        <span><i className="swatch" style={{ background: c["series-1"] }} />28-day best e1RM</span>
        <span><i className="swatch dot" style={{ background: c["series-1-soft"] }} />Session best e1RM</span>
      </div>
      <Loadable state={trend} height={280}>
        {(rows) => (
          <>
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={rows} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={c.grid} />
                <XAxis dataKey="day" tickFormatter={fmtMonth} minTickGap={40} tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis width={58} domain={["dataMin - 5", "dataMax + 5"]} tickFormatter={(v: number) => fmtNum(v, 0)} tick={{ fill: c["text-muted"], fontSize: 12 }} axisLine={false} tickLine={false} unit=" kg" />
                <Tooltip
                  cursor={{ stroke: c["text-muted"], strokeDasharray: "3 3" }}
                  content={(p) => {
                    const row = (p.payload?.[0] as unknown as { payload?: TrendRow } | undefined)?.payload;
                    return (
                      <ChartTooltip
                        {...p}
                        title={fmtDate(String(p.label ?? ""))}
                        rows={() =>
                          row
                            ? [
                                { label: "Session e1RM", value: `${fmtNum(row.best_e1rm_kg)} kg`, color: c["series-1-soft"] },
                                { label: "28-day best", value: `${fmtNum(row.rolling_28d_best_e1rm_kg)} kg`, color: c["series-1"] },
                                { label: "Top set", value: `${fmtNum(row.top_set_kg)} kg` },
                              ]
                            : []
                        }
                      />
                    );
                  }}
                />
                <Scatter dataKey="best_e1rm_kg" fill={c["series-1-soft"]} shape="circle" isAnimationActive={false} />
                <Line type="stepAfter" dataKey="rolling_28d_best_e1rm_kg" stroke={c["series-1"]} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: c["surface-1"], strokeWidth: 2 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <DataTable
              rows={[...rows].reverse()}
              columns={[
                { key: "day", label: "Date" },
                { key: "best_e1rm_kg", label: "e1RM (kg)", numeric: true, format: (v) => fmtNum(Number(v)) },
                { key: "rolling_28d_best_e1rm_kg", label: "28-day best (kg)", numeric: true, format: (v) => fmtNum(Number(v)) },
                { key: "top_set_kg", label: "Top set (kg)", numeric: true, format: (v) => fmtNum(Number(v)) },
                { key: "overload_trend", label: "Trend", format: (v) => titleCase(String(v)) },
              ]}
            />
          </>
        )}
      </Loadable>
    </Card>
  );
}
