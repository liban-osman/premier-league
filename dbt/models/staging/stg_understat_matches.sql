-- Grain: one row per (season, match). Latest load_date per season only
-- (refresh semantics -- decision log #26). is_result = false rows are
-- fixtures not yet played; their goals/xG stay null via try_cast.
with latest as (
    select season, max(load_date) as load_date
    from {{ source('raw', 'understat_matches') }}
    group by season
),

source as (
    select m.*
    from {{ source('raw', 'understat_matches') }} m
    inner join latest using (season, load_date)
)

select
    cast(season as integer) as season,
    try_cast(id as integer) as match_ud_id,
    "datetime" as match_datetime,
    isresult as is_result,
    try_cast(h.id ->> '$' as integer) as home_team_ud_id,
    h.title ->> '$' as home_team_name,
    try_cast(a.id ->> '$' as integer) as away_team_ud_id,
    a.title ->> '$' as away_team_name,
    try_cast(goals.h ->> '$' as integer) as home_goals,
    try_cast(goals.a ->> '$' as integer) as away_goals,
    try_cast(xg.h ->> '$' as double) as home_xg,
    try_cast(xg.a ->> '$' as double) as away_xg,
    load_date
from source
