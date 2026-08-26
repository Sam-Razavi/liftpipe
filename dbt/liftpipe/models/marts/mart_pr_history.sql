-- Every personal record: a day on which an exercise beat its previous best.
--   e1rm            best estimated 1RM (loaded sets of 1-12 reps)
--   heaviest_weight heaviest working-set load
--   most_reps       most reps in one working set of an unloaded (bodyweight) exercise
with metrics as (
    select exercise_id, exercise_title, workout_date, 'e1rm' as pr_type,
           max(estimated_1rm_kg) as value
    from {{ ref('fct_sets') }}
    where is_working_set
    group by all
    union all
    select exercise_id, exercise_title, workout_date, 'heaviest_weight',
           max(weight_kg)
    from {{ ref('fct_sets') }}
    where is_working_set
    group by all
    union all
    select exercise_id, exercise_title, workout_date, 'most_reps',
           max(reps)
    from {{ ref('fct_sets') }}
    where is_working_set and weight_kg is null and reps is not null
    group by all
),

with_previous as (
    select
        *,
        max(value) over (
            partition by exercise_id, pr_type
            order by workout_date
            rows between unbounded preceding and 1 preceding
        ) as previous_best
    from metrics
    where value is not null
)

select
    md5(exercise_id || '|' || pr_type || '|' || workout_date) as pr_id,
    exercise_id,
    exercise_title,
    pr_type,
    workout_date as achieved_on,
    value,
    previous_best as previous_value,
    round(value - previous_best, 2) as improvement,
    previous_best is null as is_first_record,
    row_number() over (partition by exercise_id, pr_type order by workout_date)::integer as pr_number
from with_previous
where previous_best is null or value > previous_best
