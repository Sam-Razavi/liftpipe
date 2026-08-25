-- One row per training session across both sources. A Hevy workout and the Apple
-- Watch strength workout recorded alongside it (start within 30 minutes) are the same
-- session: the Hevy row is kept and enriched with the watch's energy estimate.
with hevy as (
    select
        w.*,
        s.working_sets,
        s.total_reps,
        s.volume_kg,
        s.exercises
    from {{ ref('stg_hevy__workouts') }} as w
    left join (
        select
            workout_id,
            count(*) filter (where is_working_set)::integer as working_sets,
            sum(reps) filter (where is_working_set)::integer as total_reps,
            coalesce(sum(volume_kg), 0) as volume_kg,
            count(distinct exercise_title)::integer as exercises
        from {{ ref('int_sets_enriched') }}
        group by workout_id
    ) as s using (workout_id)
),

apple as (
    select * from {{ ref('stg_apple_health__workouts') }}
),

candidates as (
    select
        hevy.workout_id as hevy_workout_id,
        apple.workout_id as apple_workout_id,
        apple.energy_kcal,
        abs(date_diff('second', hevy.started_at, apple.started_at)) as gap_seconds
    from hevy
    inner join apple
        on apple.is_strength
        and apple.started_at between hevy.started_at - interval 30 minute
        and hevy.started_at + interval 30 minute
),

matches as (
    -- Closest pairing wins, and each Apple workout is used at most once.
    select * from (
        select *
        from candidates
        qualify row_number() over (partition by hevy_workout_id order by gap_seconds) = 1
    )
    qualify row_number() over (partition by apple_workout_id order by gap_seconds) = 1
)

select
    hevy.workout_id,
    'hevy' as source,
    'strength' as workout_type,
    hevy.workout_title,
    hevy.started_at,
    hevy.ended_at,
    hevy.workout_date,
    hevy.duration_min,
    hevy.working_sets,
    hevy.total_reps,
    hevy.volume_kg,
    hevy.exercises,
    matches.energy_kcal,
    cast(null as double) as distance_km,
    matches.apple_workout_id is not null as has_watch_data
from hevy
left join matches on hevy.workout_id = matches.hevy_workout_id

union all

select
    apple.workout_id,
    'apple_health' as source,
    case when apple.is_strength then 'strength' else 'cardio' end as workout_type,
    apple.activity as workout_title,
    apple.started_at,
    apple.ended_at,
    apple.workout_date,
    round(apple.duration_min)::integer as duration_min,
    cast(null as integer) as working_sets,
    cast(null as integer) as total_reps,
    cast(null as double) as volume_kg,
    cast(null as integer) as exercises,
    apple.energy_kcal,
    apple.distance_km,
    true as has_watch_data
from apple
where apple.workout_id not in (select apple_workout_id from matches)
