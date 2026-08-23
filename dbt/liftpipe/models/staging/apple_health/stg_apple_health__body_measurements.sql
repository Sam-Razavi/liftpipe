-- Long format, one row per measurement, with consistent units:
-- mass in kg, percentages on a 0-100 scale, lengths in cm.
with source as (
    select * from {{ source('raw', 'health_records') }}
),

renamed as (
    select
        record_id,
        case record_type
            when 'HKQuantityTypeIdentifierBodyMass' then 'body_mass_kg'
            when 'HKQuantityTypeIdentifierLeanBodyMass' then 'lean_body_mass_kg'
            when 'HKQuantityTypeIdentifierBodyFatPercentage' then 'body_fat_pct'
            when 'HKQuantityTypeIdentifierBodyMassIndex' then 'bmi'
            when 'HKQuantityTypeIdentifierHeight' then 'height_cm'
            when 'HKQuantityTypeIdentifierWaistCircumference' then 'waist_cm'
            when 'HKQuantityTypeIdentifierRestingHeartRate' then 'resting_hr_bpm'
        end as metric,
        case
            when unit = 'lb' then value * 0.45359237
            when unit = 'g' then value / 1000
            -- Health stores percentages as fractions with unit '%'.
            when unit = '%' and value <= 1 then value * 100
            when unit = 'm' then value * 100
            when unit = 'in' then value * 2.54
            when unit = 'ft' then value * 30.48
            else value
        end as value,
        unit as source_unit,
        start_date as measured_at,
        cast(start_date as date) as measured_on,
        source_name,
        _loaded_at
    from source
)

select * from renamed
where metric is not null
