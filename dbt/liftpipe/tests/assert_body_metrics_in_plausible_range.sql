-- Body readings outside human ranges usually mean a unit mix-up (lb vs kg, fraction vs %).
select metric, measured_on, value
from {{ ref('int_body_daily') }}
where (metric = 'body_mass_kg' and value not between 30 and 250)
   or (metric = 'body_fat_pct' and value not between 2 and 60)
   or (metric = 'lean_body_mass_kg' and value not between 20 and 150)
   or (metric = 'resting_hr_bpm' and value not between 25 and 120)
