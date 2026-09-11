// SQL against the exported marts. Dates are returned as ISO text, counts as INTEGER.

export const sqlString = (value: string) => `'${value.replaceAll("'", "''")}'`;

export const LAST_DAY = `(SELECT max(workout_date) FROM fct_workouts)`;

export const KPIS = `
  WITH last AS (SELECT ${LAST_DAY} AS d)
  SELECT
    (SELECT count(*)::INTEGER FROM fct_workouts, last
       WHERE workout_date > last.d - INTERVAL 28 DAY) AS sessions_28d,
    (SELECT count(*)::INTEGER FROM fct_workouts, last
       WHERE workout_date > last.d - INTERVAL 56 DAY
         AND workout_date <= last.d - INTERVAL 28 DAY) AS sessions_prev_28d,
    (SELECT streak_weeks FROM mart_training_consistency ORDER BY week_start DESC LIMIT 1)
      AS current_streak,
    (SELECT max(streak_weeks) FROM mart_training_consistency) AS longest_streak,
    (SELECT count(*)::INTEGER FROM mart_pr_history, last
       WHERE NOT is_first_record AND achieved_on > last.d - INTERVAL 28 DAY) AS prs_28d,
    (SELECT rolling_7d_avg FROM mart_body_trends
       WHERE metric = 'body_mass_kg' ORDER BY measured_on DESC LIMIT 1) AS weight_avg,
    (SELECT rolling_avg_change_28d FROM mart_body_trends
       WHERE metric = 'body_mass_kg' ORDER BY measured_on DESC LIMIT 1) AS weight_change_28d,
    (SELECT round(sum(volume_kg) / 1000, 1) FROM fct_workouts, last
       WHERE workout_date > last.d - INTERVAL 28 DAY) AS tonnes_28d
`;

export const META = `
  SELECT strftime(min(workout_date), '%Y-%m-%d') AS first_day,
         strftime(max(workout_date), '%Y-%m-%d') AS last_day
  FROM fct_workouts
`;

export const MUSCLE_SETS_8W = `
  SELECT muscle_group,
         round(sum(fractional_sets) / 8, 1) AS weekly_sets,
         round(sum(working_sets) / 8, 1) AS weekly_direct_sets
  FROM mart_weekly_muscle_volume
  WHERE week_start > (SELECT max(week_start) FROM mart_weekly_muscle_volume) - INTERVAL 56 DAY
  GROUP BY muscle_group
  ORDER BY weekly_sets DESC
`;

export const muscleWeekly = (muscle: string) => `
  WITH weeks AS (SELECT week_start FROM mart_training_consistency)
  SELECT strftime(weeks.week_start, '%Y-%m-%d') AS week_start,
         coalesce(v.fractional_sets, 0) AS sets,
         coalesce(v.volume_kg, 0) AS volume_kg
  FROM weeks
  LEFT JOIN mart_weekly_muscle_volume v
    ON v.week_start = weeks.week_start AND v.muscle_group = ${sqlString(muscle)}
  ORDER BY weeks.week_start
`;

export const EXERCISES = `
  SELECT e.exercise_title, count(*)::INTEGER AS sessions
  FROM mart_exercise_e1rm e
  GROUP BY e.exercise_title
  HAVING count(*) >= 8
  ORDER BY sessions DESC
`;

export const exerciseTrend = (exercise: string) => `
  SELECT strftime(workout_date, '%Y-%m-%d') AS day,
         best_e1rm_kg, rolling_28d_best_e1rm_kg, top_set_kg, pct_change_28d, overload_trend
  FROM mart_exercise_e1rm
  WHERE exercise_title = ${sqlString(exercise)}
  ORDER BY workout_date
`;

export const RECENT_PRS = `
  SELECT strftime(achieved_on, '%Y-%m-%d') AS achieved_on, exercise_title, pr_type,
         value, previous_value, improvement
  FROM mart_pr_history
  WHERE NOT is_first_record
  ORDER BY achieved_on DESC, exercise_title, pr_type
  LIMIT 10
`;

export const bodyTrend = (metric: string) => `
  SELECT strftime(measured_on, '%Y-%m-%d') AS day, value, rolling_7d_avg
  FROM mart_body_trends
  WHERE metric = ${sqlString(metric)}
  ORDER BY measured_on
`;

export const DAILY_TRAINING = `
  WITH last AS (SELECT ${LAST_DAY} AS d),
  days AS (
    SELECT unnest(generate_series(
      date_trunc('week', (SELECT d FROM last) - INTERVAL 364 DAY),
      (SELECT d FROM last),
      INTERVAL 1 DAY))::DATE AS day
  )
  SELECT strftime(days.day, '%Y-%m-%d') AS day,
         coalesce(sum(w.duration_min), 0)::INTEGER AS minutes,
         count(w.workout_id)::INTEGER AS sessions,
         coalesce(string_agg(w.workout_title, ', ' ORDER BY w.started_at), '') AS titles
  FROM days
  LEFT JOIN fct_workouts w ON w.workout_date = days.day
  GROUP BY days.day
  ORDER BY days.day
`;
