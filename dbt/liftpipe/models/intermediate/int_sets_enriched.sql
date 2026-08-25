-- Sets with muscle groups, working-set flags, volume and estimated 1RM.
with sets as (
    select * from {{ ref('stg_hevy__sets') }}
),

muscles as (
    select * from {{ ref('exercise_muscle_map') }}
)

select
    sets.set_id,
    sets.workout_id,
    sets.workout_started_at,
    sets.workout_date,
    date_trunc('week', sets.workout_date)::date as week_start,
    sets.exercise_index,
    sets.exercise_title,
    coalesce(muscles.primary_muscle_group, 'other') as primary_muscle_group,
    muscles.secondary_muscle_group,
    coalesce(muscles.equipment, 'unknown') as equipment,
    muscles.exercise_title is not null as is_mapped,
    sets.set_index,
    sets.set_type,
    not sets.is_warmup as is_working_set,
    sets.weight_kg,
    sets.reps,
    sets.distance_km,
    sets.duration_seconds,
    sets.rpe,
    sets.superset_id,
    -- Volume load (kg x reps) counts working sets only.
    case when not sets.is_warmup then sets.weight_kg * sets.reps end as volume_kg,
    case when not sets.is_warmup then {{ epley_1rm('sets.weight_kg', 'sets.reps') }} end
        as estimated_1rm_kg,
    sets._loaded_at
from sets
left join muscles
    on lower(sets.exercise_title) = lower(muscles.exercise_title)
