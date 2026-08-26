-- Weekly working sets and volume per muscle group. fractional_sets also credits the
-- secondary muscle with half a set (a bench press counts 1 for chest, 0.5 for triceps),
-- a common way to estimate weekly training stimulus.
with sets as (
    select
        f.week_start,
        f.workout_id,
        f.reps,
        f.volume_kg,
        d.primary_muscle_group,
        d.secondary_muscle_group
    from {{ ref('fct_sets') }} as f
    inner join {{ ref('dim_exercise') }} as d using (exercise_id)
    where f.is_working_set
      and d.primary_muscle_group <> 'cardio'
),

contributions as (
    select week_start, workout_id, primary_muscle_group as muscle_group,
           1.0 as set_credit, reps, volume_kg
    from sets
    union all
    select week_start, workout_id, secondary_muscle_group,
           0.5, null, null
    from sets
    where secondary_muscle_group is not null
)

select
    week_start,
    muscle_group,
    count(*) filter (where set_credit = 1.0)::integer as working_sets,
    sum(set_credit)::double as fractional_sets,
    coalesce(sum(reps), 0)::integer as reps,
    round(coalesce(sum(volume_kg), 0), 1) as volume_kg,
    count(distinct workout_id)::integer as sessions
from contributions
group by week_start, muscle_group
