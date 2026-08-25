{{
    config(
        materialized='incremental',
        unique_key='set_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

-- Incremental on the raw load timestamp: a re-export only reprocesses rows that were
-- inserted or replaced by that load. Muscle groups live on dim_exercise, so editing the
-- seed never requires a full refresh of this table.
select
    set_id,
    workout_id,
    md5(lower(exercise_title)) as exercise_id,
    exercise_title,
    workout_started_at,
    workout_date,
    week_start,
    exercise_index,
    set_index,
    set_type,
    is_working_set,
    weight_kg,
    reps,
    distance_km,
    duration_seconds,
    rpe,
    superset_id,
    volume_kg,
    estimated_1rm_kg,
    _loaded_at
from {{ ref('int_sets_enriched') }}
{% if is_incremental() %}
where _loaded_at > (select coalesce(max(_loaded_at), '1900-01-01'::timestamp) from {{ this }})
{% endif %}
