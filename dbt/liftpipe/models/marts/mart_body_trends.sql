-- Daily series per body metric on a continuous calendar, with a 7-day rolling average
-- (smooths day-to-day water and glycogen swings) and its change over 28 days.
with daily as (
    select metric, measured_on, value
    from {{ ref('int_body_daily') }}
    where metric in ('body_mass_kg', 'body_fat_pct', 'lean_body_mass_kg', 'resting_hr_bpm')
),

spine as (
    select
        metric,
        unnest(generate_series(min(measured_on), max(measured_on), interval 1 day))::date
            as measured_on
    from daily
    group by metric
),

series as (
    select
        spine.metric,
        spine.measured_on,
        daily.value,
        avg(daily.value) over w7 as rolling_7d_avg,
        count(daily.value) over w7 as readings_7d_raw
    from spine
    left join daily using (metric, measured_on)
    window w7 as (
        partition by spine.metric
        order by spine.measured_on
        rows between 6 preceding and current row
    )
)

select
    metric,
    measured_on,
    round(value, 2) as value,
    round(rolling_7d_avg, 2) as rolling_7d_avg,
    readings_7d_raw::integer as readings_7d,
    -- The spine is gap-free, so 28 rows back is exactly 28 days back.
    round(
        rolling_7d_avg - lag(rolling_7d_avg, 28) over (partition by metric order by measured_on),
        2
    ) as rolling_avg_change_28d
from series
