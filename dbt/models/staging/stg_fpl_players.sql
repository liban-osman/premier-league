-- Grain: one row per (load_date, player_id). Each raw.fpl_bootstrap row is one
-- whole-API snapshot with `elements` as a nested array of every player at that
-- moment -- unnesting it here is what turns "current state" into a time series.
with source as (
    select
        load_date,
        season,
        e
    from {{ source('raw', 'fpl_bootstrap') }}, unnest(elements) as t(e)
)

select
    load_date,
    season,
    try_cast(e ->> 'id' as integer) as player_id,
    e ->> 'first_name' as first_name,
    e ->> 'second_name' as second_name,
    e ->> 'web_name' as web_name,
    -- global asset id (stable across seasons, unlike player_id which resets):
    -- resources.premierleague.com player photos are keyed on it
    try_cast(e ->> 'code' as integer) as player_code,
    try_cast(e ->> 'team' as integer) as team_id,
    try_cast(e ->> 'element_type' as integer) as position_id,

    -- now_cost is FPL's price in tenths of a million (62 == GBP 6.2m)
    try_cast(e ->> 'now_cost' as integer) as now_cost,
    try_cast(e ->> 'cost_change_event' as integer) as cost_change_event,
    try_cast(e ->> 'cost_change_start' as integer) as cost_change_start,
    try_cast(e ->> 'selected_by_percent' as double) as selected_by_percent,
    try_cast(e ->> 'transfers_in_event' as integer) as transfers_in_event,
    try_cast(e ->> 'transfers_out_event' as integer) as transfers_out_event,
    try_cast(e ->> 'transfers_in' as bigint) as transfers_in_total,
    try_cast(e ->> 'transfers_out' as bigint) as transfers_out_total,

    try_cast(e ->> 'form' as double) as form,
    try_cast(e ->> 'points_per_game' as double) as points_per_game,
    try_cast(e ->> 'total_points' as integer) as total_points,
    try_cast(e ->> 'event_points' as integer) as event_points,
    try_cast(e ->> 'ep_next' as double) as expected_points_next,
    try_cast(e ->> 'ep_this' as double) as expected_points_this,
    try_cast(e ->> 'value_form' as double) as value_form,
    try_cast(e ->> 'value_season' as double) as value_season,

    try_cast(e ->> 'minutes' as integer) as minutes,
    try_cast(e ->> 'starts' as integer) as starts,
    try_cast(e ->> 'goals_scored' as integer) as goals_scored,
    try_cast(e ->> 'assists' as integer) as assists,
    try_cast(e ->> 'clean_sheets' as integer) as clean_sheets,
    try_cast(e ->> 'goals_conceded' as integer) as goals_conceded,
    try_cast(e ->> 'saves' as integer) as saves,
    try_cast(e ->> 'bonus' as integer) as bonus,
    try_cast(e ->> 'bps' as integer) as bps,

    try_cast(e ->> 'influence' as double) as influence,
    try_cast(e ->> 'creativity' as double) as creativity,
    try_cast(e ->> 'threat' as double) as threat,
    try_cast(e ->> 'ict_index' as double) as ict_index,
    try_cast(e ->> 'expected_goals' as double) as expected_goals,
    try_cast(e ->> 'expected_assists' as double) as expected_assists,
    try_cast(e ->> 'expected_goal_involvements' as double) as expected_goal_involvements,
    try_cast(e ->> 'expected_goals_conceded' as double) as expected_goals_conceded,

    try_cast(e ->> 'yellow_cards' as integer) as yellow_cards,
    try_cast(e ->> 'red_cards' as integer) as red_cards,

    -- status: a=available, d=doubtful, i=injured, s=suspended, u=unavailable, n=not in squad
    e ->> 'status' as status,
    try_cast(e ->> 'chance_of_playing_next_round' as integer) as chance_of_playing_next_round,
    try_cast(e ->> 'chance_of_playing_this_round' as integer) as chance_of_playing_this_round,
    nullif(e ->> 'news', '') as news,
    try_cast(e ->> 'news_added' as timestamp) as news_added,

    try_cast(e ->> 'can_transact' as boolean) as can_transact,
    try_cast(e ->> 'can_select' as boolean) as can_select,
    try_cast(e ->> 'removed' as boolean) as removed
from source
