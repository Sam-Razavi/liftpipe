-- An estimated 1RM can never be lower than a weight actually lifted for reps.
select set_id, weight_kg, reps, estimated_1rm_kg
from {{ ref('fct_sets') }}
where estimated_1rm_kg < weight_kg
