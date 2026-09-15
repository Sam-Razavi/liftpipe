import { useState } from "react";
import { fmtDate, fmtShort } from "../format";
import { DAILY_TRAINING } from "../queries";
import { useQuery } from "../useQuery";
import { useThemeColors } from "../useThemeColors";
import { Card, Loadable } from "./Card";

type Day = { day: string; minutes: number; sessions: number; titles: string };

const CELL = 12;
const GAP = 3;
const DAYS = ["Mon", "", "Wed", "", "Fri", "", "Sun"];
const STEPS = [1, 30, 60, 90]; // minute thresholds for the sequential ramp

export function Consistency() {
  const c = useThemeColors();
  const state = useQuery<Day>(DAILY_TRAINING);
  const [hover, setHover] = useState<Day | null>(null);
  const ramp = [c["surface-2"], c["seq-2"], c["seq-3"], c["seq-4"], c["seq-5"]];
  const colour = (m: number) => ramp[STEPS.filter((s) => m >= s).length];

  return (
    <Card title="Training calendar" subtitle="Minutes trained per day over the last year, strength and cardio combined.">
      <Loadable state={state} height={140}>
        {(days) => {
          const weeks = Math.ceil(days.length / 7);
          const width = 30 + weeks * (CELL + GAP);
          const height = 18 + 7 * (CELL + GAP);
          const trained = days.filter((d) => d.sessions > 0).length;
          return (
            <>
              <p className="sub" aria-live="polite" style={{ minHeight: "1.5em" }}>
                {hover
                  ? `${fmtDate(hover.day)}: ${hover.sessions ? `${hover.titles} (${hover.minutes} min)` : "rest day"}`
                  : `${trained} training days in the last ${weeks} weeks. Hover or focus a day for details.`}
              </p>
              <div className="heatmap">
                <svg width={width} height={height} role="img" aria-label={`Training calendar: ${trained} training days`}>
                  {DAYS.map((label, i) => (
                    <text key={i} x={0} y={18 + i * (CELL + GAP) + CELL - 2} fontSize={10} fill={c["text-muted"]}>{label}</text>
                  ))}
                  {days.map((d, i) => {
                    const week = Math.floor(i / 7);
                    const dow = i % 7;
                    const isMonthStart = d.day.endsWith("-01") || (dow === 0 && Number(d.day.slice(8)) <= 7);
                    return (
                      <g key={d.day}>
                        {dow === 0 && isMonthStart && (
                          <text x={30 + week * (CELL + GAP)} y={10} fontSize={10} fill={c["text-muted"]}>
                            {fmtShort(d.day).split(" ")[1]}
                          </text>
                        )}
                        <rect
                          x={30 + week * (CELL + GAP)}
                          y={18 + dow * (CELL + GAP)}
                          width={CELL}
                          height={CELL}
                          rx={3}
                          fill={colour(d.minutes)}
                          stroke={hover?.day === d.day ? c["text-secondary"] : "none"}
                          strokeWidth={1.5}
                          tabIndex={d.sessions ? 0 : -1}
                          onMouseEnter={() => setHover(d)}
                          onMouseLeave={() => setHover(null)}
                          onFocus={() => setHover(d)}
                          onBlur={() => setHover(null)}
                        >
                          <title>{`${d.day}: ${d.sessions ? `${d.titles}, ${d.minutes} min` : "rest"}`}</title>
                        </rect>
                      </g>
                    );
                  })}
                </svg>
              </div>
              <div className="heat-legend" aria-hidden="true">
                Rest
                {ramp.map((col) => <i key={col} style={{ background: col }} />)}
                90+ min
              </div>
            </>
          );
        }}
      </Loadable>
    </Card>
  );
}
