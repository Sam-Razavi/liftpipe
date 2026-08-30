{{ config(severity='warn') }}
-- Warn when more than 10% of working sets belong to exercises missing from the muscle
-- map; add them to seeds/exercise_muscle_map.csv.
select
    count(*) filter (where not d.is_mapped) as unmapped_sets,
    count(*) as total_sets
from {{ ref('fct_sets') }} as f
inner join {{ ref('dim_exercise') }} as d using (exercise_id)
where f.is_working_set
having count(*) filter (where not d.is_mapped) > 0.10 * count(*)
