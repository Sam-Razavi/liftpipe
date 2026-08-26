-- Daily best estimated 1RM per exercise, a 28-day rolling best, and the change versus
-- the rolling best four weeks earlier: the progressive-overload signal.
with daily as (
    select
        exercise_id,
        exercise_title,
        workout_date,
        max(estimated_1rm_kg) as best_e1rm_kg,
        max(weight_kg) as top_set_kg,
        count(*)::integer as working_sets,
        round(sum(volume_kg), 1) as volume_kg
    from {{ ref('fct_sets') }}
    where is_working_set and estimated_1rm_kg is not null
    group by exercise_id, exercise_title, workout_date
),

rolling as (
    select
        *,
        max(best_e1rm_kg) over (
            partition by exercise_id
            order by workout_date
            range between interval 27 days preceding and current row
        ) as rolling_28d_best_e1rm_kg
    from daily
),

compared as (
    select
        cur.*,
        prev.rolling_28d_best_e1rm_kg as rolling_best_28d_ago_kg
    from rolling as cur
    asof left join rolling as prev
        on cur.exercise_id = prev.exercise_id
        and cast(cur.workout_date - interval 28 day as date) >= prev.workout_date
)

select
    *,
    round(
        100 * (rolling_28d_best_e1rm_kg - rolling_best_28d_ago_kg) / rolling_best_28d_ago_kg, 2
    ) as pct_change_28d,
    case
        when rolling_best_28d_ago_kg is null then 'insufficient_history'
        when rolling_28d_best_e1rm_kg >= rolling_best_28d_ago_kg * 1.025 then 'progressing'
        when rolling_28d_best_e1rm_kg <= rolling_best_28d_ago_kg * 0.975 then 'regressing'
        else 'plateau'
    end as overload_trend
from compared
