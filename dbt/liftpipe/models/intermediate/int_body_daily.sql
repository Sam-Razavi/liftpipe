-- One value per metric per day. When several readings exist (a scale and a manual
-- entry, or two weigh-ins) the latest reading of the day wins; ties go to the source
-- name alphabetically so the result is deterministic.
select
    metric,
    measured_on,
    value,
    source_name,
    measured_at,
    count(*) over (partition by metric, measured_on) as readings_that_day
from {{ ref('stg_apple_health__body_measurements') }}
qualify row_number() over (
    partition by metric, measured_on
    order by measured_at desc, source_name
) = 1
