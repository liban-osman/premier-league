-- Grain: one row per (season, team, match_date) -- each team's per-match
-- analytics history, unnested from the nested array on the raw team row.
-- Latest load_date per season only (refresh semantics -- decision log #26).
--
-- PPDA arrives as {att, def} (opponent passes vs own defensive actions in
-- the pressing zone); the metric itself is the ratio, computed here.
with latest as (
    select season, max(load_date) as load_date
    from {{ source('raw', 'understat_teams') }}
    group by season
),

source as (
    select
        t.season,
        t.load_date,
        try_cast(t.id as integer) as team_ud_id,
        t.title as team_name,
        unnest(t.history) as h
    from {{ source('raw', 'understat_teams') }} t
    inner join latest using (season, load_date)
)

select
    cast(season as integer) as season,
    team_ud_id,
    team_name,
    cast(try_cast(h ->> 'date' as timestamp) as date) as match_date,
    h ->> 'h_a' as h_a,
    try_cast(h ->> 'scored' as integer) as goals_scored,
    try_cast(h ->> 'missed' as integer) as goals_conceded,
    h ->> 'result' as result,
    try_cast(h ->> 'pts' as integer) as points,
    try_cast(h ->> 'xG' as double) as xg,
    try_cast(h ->> 'xGA' as double) as xga,
    try_cast(h ->> 'npxG' as double) as npxg,
    try_cast(h ->> 'npxGA' as double) as npxga,
    try_cast(h ->> 'npxGD' as double) as npxgd,
    try_cast(h ->> 'xpts' as double) as expected_points,
    try_cast(h -> 'ppda' ->> 'att' as double)
        / nullif(try_cast(h -> 'ppda' ->> 'def' as double), 0) as ppda,
    try_cast(h -> 'ppda_allowed' ->> 'att' as double)
        / nullif(try_cast(h -> 'ppda_allowed' ->> 'def' as double), 0) as ppda_allowed,
    try_cast(h ->> 'deep' as integer) as deep_completions,
    try_cast(h ->> 'deep_allowed' as integer) as deep_completions_allowed,
    load_date
from source
