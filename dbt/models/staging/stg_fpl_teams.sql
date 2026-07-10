-- Grain: one row per (load_date, team_id). Kept historized like players --
-- form/points/position move week to week once the season is underway, even
-- though they're static at 0 in preseason snapshots.
with source as (
    select
        load_date,
        season,
        t
    from {{ source('raw', 'fpl_bootstrap') }}, unnest(teams) as x(t)
)

select
    load_date,
    season,
    try_cast(t ->> 'id' as integer) as team_id,
    t ->> 'name' as team_name,
    t ->> 'short_name' as team_short_name,

    try_cast(t ->> 'strength' as integer) as strength,
    try_cast(t ->> 'strength_overall_home' as integer) as strength_overall_home,
    try_cast(t ->> 'strength_overall_away' as integer) as strength_overall_away,
    try_cast(t ->> 'strength_attack_home' as integer) as strength_attack_home,
    try_cast(t ->> 'strength_attack_away' as integer) as strength_attack_away,
    try_cast(t ->> 'strength_defence_home' as integer) as strength_defence_home,
    try_cast(t ->> 'strength_defence_away' as integer) as strength_defence_away,

    try_cast(t ->> 'played' as integer) as played,
    try_cast(t ->> 'win' as integer) as win,
    try_cast(t ->> 'draw' as integer) as draw,
    try_cast(t ->> 'loss' as integer) as loss,
    try_cast(t ->> 'points' as integer) as points,
    try_cast(t ->> 'position' as integer) as league_position,
    try_cast(t ->> 'form' as double) as form,
    try_cast(t ->> 'unavailable' as boolean) as unavailable
from source
