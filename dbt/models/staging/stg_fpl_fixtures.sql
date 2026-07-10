-- Grain: one row per (load_date, fixture_id). fixtures.json is a flat JSON
-- array (unlike bootstrap-static's nested object), so read_json_auto already
-- gives one row per fixture -- no UNNEST needed here.
-- `stats` (per-match goals/assists/bps breakdown) is dropped: that's the same
-- match-event grain WhoScored already covers in raw.whoscored_events, and
-- reconciling the two is the still-deferred FPL<->WhoScored join key problem.
select
    load_date,
    season,
    try_cast(id as integer) as fixture_id,
    try_cast(code as bigint) as fixture_code,
    try_cast(event as integer) as gameweek,
    try_cast(team_h as integer) as home_team_id,
    try_cast(team_a as integer) as away_team_id,
    try_cast(team_h_score as integer) as home_score,
    try_cast(team_a_score as integer) as away_score,
    try_cast(team_h_difficulty as integer) as home_difficulty,
    try_cast(team_a_difficulty as integer) as away_difficulty,
    try_cast(kickoff_time as timestamp) as kickoff_time,
    try_cast(started as boolean) as started,
    try_cast(finished as boolean) as finished,
    try_cast(minutes as integer) as minutes_played
from {{ source('raw', 'fpl_fixtures') }}
