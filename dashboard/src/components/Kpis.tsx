import { fmtNum, fmtSigned } from "../format";
import { KPIS } from "../queries";
import { useQuery } from "../useQuery";

type Row = {
  sessions_28d: number;
  sessions_prev_28d: number;
  current_streak: number;
  longest_streak: number;
  prs_28d: number;
  weight_avg: number | null;
  weight_change_28d: number | null;
  tonnes_28d: number | null;
};

function Tile({ label, value, unit, delta }: { label: string; value: string; unit?: string; delta?: string }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {delta && <div className="delta">{delta}</div>}
    </div>
  );
}

export function Kpis() {
  const state = useQuery<Row>(KPIS);
  if (state.status === "error") return null;
  if (state.status !== "ready") return <div className="kpis" aria-busy="true" style={{ minHeight: 98 }} />;
  const k = state.rows[0];
  return (
    <div className="kpis">
      <Tile
        label="Sessions, last 4 weeks"
        value={String(k.sessions_28d)}
        delta={`${fmtSigned(k.sessions_28d - k.sessions_prev_28d, 0)} vs previous 4 weeks`}
      />
      <Tile label="Volume, last 4 weeks" value={fmtNum(k.tonnes_28d)} unit="t" delta="Working sets, kg × reps" />
      <Tile label="Current streak" value={String(k.current_streak)} unit="weeks" delta={`Longest: ${k.longest_streak} weeks`} />
      <Tile label="PRs, last 4 weeks" value={String(k.prs_28d)} delta="e1RM, load or reps" />
      {k.weight_avg === null ? (
        <Tile label="Body weight, 7-day avg" value="–" delta="Needs Apple Health data" />
      ) : (
        <Tile
          label="Body weight, 7-day avg"
          value={fmtNum(k.weight_avg)}
          unit="kg"
          delta={`${fmtSigned(k.weight_change_28d)} kg over 28 days`}
        />
      )}
    </div>
  );
}
