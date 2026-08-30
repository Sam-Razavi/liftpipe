-- Weekly training frequency on a gap-free calendar of ISO weeks, with the current
-- streak of consecutive weeks containing at least one strength session.
with workouts as (
    select date_trunc('week', workout_date)::date as week_start, *
    from {{ ref('fct_workouts') }}
),

spine as (
    select unnest(generate_series(min(week_start), max(week_start), interval 7 day))::date
        as week_start
    from workouts
),

weekly as (
    select
        spine.week_start,
        count(w.workout_id) filter (where w.workout_type = 'strength')::integer
            as strength_sessions,
        count(w.workout_id) filter (where w.workout_type = 'cardio')::integer as cardio_sessions,
        count(distinct w.workout_date)::integer as active_days,
        coalesce(sum(w.duration_min), 0)::integer as training_minutes
    from spine
    left join workouts as w using (week_start)
    group by spine.week_start
),

flagged as (
    select
        *,
        strength_sessions > 0 as is_active_week,
        -- Each inactive week starts a new group (gaps and islands).
        sum(case when strength_sessions = 0 then 1 else 0 end)
            over (order by week_start rows unbounded preceding) as streak_group
    from weekly
)

select
    week_start,
    strength_sessions,
    cardio_sessions,
    active_days,
    training_minutes,
    is_active_week,
    case
        when is_active_week
            then sum(case when is_active_week then 1 else 0 end) over (
                partition by streak_group order by week_start rows unbounded preceding
            )
        else 0
    end::integer as streak_weeks,
    round(
        avg(strength_sessions + cardio_sessions)
            over (order by week_start rows between 3 preceding and current row),
        2
    ) as rolling_4w_avg_sessions
from flagged
