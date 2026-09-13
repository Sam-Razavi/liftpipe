import { fmtDate, fmtNum } from "../format";
import { RECENT_PRS } from "../queries";
import { useQuery } from "../useQuery";
import { Card, Loadable } from "./Card";

type Row = {
  achieved_on: string;
  exercise_title: string;
  pr_type: "e1rm" | "heaviest_weight" | "most_reps";
  value: number;
  previous_value: number;
  improvement: number;
};

const LABELS: Record<Row["pr_type"], string> = {
  e1rm: "e1RM",
  heaviest_weight: "Heaviest set",
  most_reps: "Most reps",
};

const unit = (t: Row["pr_type"]) => (t === "most_reps" ? " reps" : " kg");

export function PrTable() {
  const state = useQuery<Row>(RECENT_PRS);
  return (
    <Card className="span-5" title="Recent personal records" subtitle="Days on which an exercise beat its previous best.">
      <Loadable state={state}>
        {(rows) => (
          <div className="table-wrap" style={{ maxHeight: 420 }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Exercise</th>
                  <th>Record</th>
                  <th className="num">Value</th>
                  <th className="num">Gain</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.achieved_on}-${r.exercise_title}-${r.pr_type}`}>
                    <td>{fmtDate(r.achieved_on)}</td>
                    <td className="wrap">{r.exercise_title}</td>
                    <td>{LABELS[r.pr_type]}</td>
                    <td className="num">{fmtNum(r.value)}{unit(r.pr_type)}</td>
                    <td className="num" style={{ color: "var(--good)" }}>+{fmtNum(r.improvement)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loadable>
    </Card>
  );
}
