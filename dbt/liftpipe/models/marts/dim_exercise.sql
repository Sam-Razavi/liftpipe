select
    md5(lower(exercise_title)) as exercise_id,
    exercise_title,
    primary_muscle_group,
    secondary_muscle_group,
    equipment,
    is_mapped,
    min(workout_date) as first_performed_on,
    max(workout_date) as last_performed_on,
    count(*) filter (where is_working_set)::integer as working_sets,
    count(distinct workout_id)::integer as sessions
from {{ ref('int_sets_enriched') }}
group by all
