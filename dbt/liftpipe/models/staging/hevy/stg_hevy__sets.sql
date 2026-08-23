with source as (
    select * from {{ source('raw', 'hevy_sets') }}
)

select
    set_id,
    workout_id,
    start_time as workout_started_at,
    cast(start_time as date) as workout_date,
    exercise_index,
    trim(exercise_title) as exercise_title,
    set_index,
    set_type,
    set_type = 'warmup' as is_warmup,
    nullif(weight_kg, 0) as weight_kg,
    reps,
    distance_km,
    duration_seconds,
    rpe,
    superset_id,
    _loaded_at
from source
