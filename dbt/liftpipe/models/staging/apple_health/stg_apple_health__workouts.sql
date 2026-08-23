select
    workout_id,
    activity_type,
    -- HKWorkoutActivityTypeTraditionalStrengthTraining -> traditional_strength_training
    lower(regexp_replace(replace(activity_type, 'HKWorkoutActivityType', ''), '([a-z])([A-Z])', '\1_\2', 'g'))
        as activity,
    activity_type in (
        'HKWorkoutActivityTypeTraditionalStrengthTraining',
        'HKWorkoutActivityTypeFunctionalStrengthTraining'
    ) as is_strength,
    source_name,
    start_date as started_at,
    end_date as ended_at,
    cast(start_date as date) as workout_date,
    duration_min,
    total_energy_kcal as energy_kcal,
    total_distance_km as distance_km,
    _loaded_at
from {{ source('raw', 'health_workouts') }}
