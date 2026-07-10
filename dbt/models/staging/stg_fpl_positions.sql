-- Grain: one row per position_id. Position definitions (GKP/DEF/MID/FWD) are
-- genuinely static reference data, so this collapses to the latest snapshot
-- rather than historizing like players/teams.
with source as (
    select
        load_date,
        et
    from {{ source('raw', 'fpl_bootstrap') }}, unnest(element_types) as x(et)
),

latest as (
    select
        et,
        row_number() over (
            partition by try_cast(et ->> 'id' as integer)
            order by load_date desc
        ) as rn
    from source
)

select
    try_cast(et ->> 'id' as integer) as position_id,
    et ->> 'singular_name' as position_name,
    et ->> 'singular_name_short' as position_short_name,
    try_cast(et ->> 'squad_min_play' as integer) as squad_min_play,
    try_cast(et ->> 'squad_max_play' as integer) as squad_max_play,
    try_cast(et ->> 'element_count' as integer) as element_count
from latest
where rn = 1
