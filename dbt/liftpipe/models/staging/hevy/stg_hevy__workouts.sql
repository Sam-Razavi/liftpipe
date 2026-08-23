-- Hevy repeats workout attributes on every set row; collapse to one row per workout.
select
    workout_id,
    any_value(workout_title) as workout_title,
    min(start_time) as started_at,
    max(end_time) as ended_at,
    cast(min(start_time) as date) as workout_date,
    date_diff('minute', min(start_time), max(end_time))::integer as duration_min,
    nullif(any_value(description), '') as description,
    max(_loaded_at) as _loaded_at
from {{ source('raw', 'hevy_sets') }}
group by workout_id
