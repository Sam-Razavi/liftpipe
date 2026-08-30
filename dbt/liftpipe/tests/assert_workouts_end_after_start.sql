select workout_id, started_at, ended_at
from {{ ref('fct_workouts') }}
where ended_at < started_at
