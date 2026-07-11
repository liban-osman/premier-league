-- Grain: one row per (season, player). Understat serves full-season aggregates
-- that only grow as the season progresses, so unlike the FPL staging models
-- this reads ONLY the latest load_date per season -- refresh semantics, not a
-- snapshot time series (decision log #26).
with latest as (
    select season, max(load_date) as load_date
    from {{ source('raw', 'understat_players') }}
    group by season
),

source as (
    select p.*
    from {{ source('raw', 'understat_players') }} p
    inner join latest using (season, load_date)
)

select
    cast(season as integer) as season,
    try_cast(id as integer) as player_ud_id,
    -- Understat HTML-escapes apostrophes (Jake O&#039;Brien); the only entity
    -- observed in the data. Decoded here so names render and match cleanly.
    replace(player_name, '&#039;', '''') as player_name,
    -- comma-separated when a player moved clubs mid-season; kept verbatim
    team_title as team_name,
    position,
    try_cast(games as integer) as games,
    try_cast("time" as integer) as minutes,
    try_cast(goals as integer) as goals,
    try_cast(npg as integer) as non_penalty_goals,
    try_cast(assists as integer) as assists,
    try_cast(shots as integer) as shots,
    try_cast(key_passes as integer) as key_passes,
    try_cast(xg as double) as xg,
    try_cast(npxg as double) as npxg,
    try_cast(xa as double) as xa,
    try_cast(xgchain as double) as xg_chain,
    try_cast(xgbuildup as double) as xg_buildup,
    try_cast(yellow_cards as integer) as yellow_cards,
    try_cast(red_cards as integer) as red_cards,
    load_date
from source
