-- Grain: one row per match (380 for the 2024/25 season). WhoScored's "events"
-- export is one whole match-centre payload per match, so match-level facts
-- come off its top level; the separate "matches" calendar export carries
-- nothing extra we need and stays unstaged.
with source as (
    select * from {{ source('raw', 'whoscored_events') }}
)

select
    -- the numeric part of the landed file name is WhoScored's match id
    try_cast(regexp_extract(filename, '(\d+)\.json$', 1) as integer) as match_id,
    cast(startdate as date) as match_date,

    -- The S3 season= label was set by hand at upload time and doesn't follow
    -- the FPL convention (season start year: this export sits under
    -- season=2025 but is the 2024/25 season). Derive the season each match
    -- actually belongs to from its own date instead -- seasons run Aug-May,
    -- so July onwards belongs to the season starting that year.
    case
        when month(cast(startdate as date)) >= 7 then year(cast(startdate as date))
        else year(cast(startdate as date)) - 1
    end as season_start_year,

    try_cast(home.teamid ->> '$' as integer) as home_team_ws_id,
    home."name" ->> '$' as home_team_name,
    try_cast(away.teamid ->> '$' as integer) as away_team_ws_id,
    away."name" ->> '$' as away_team_name,

    -- ftScore arrives as '2 : 0'; the cast tolerates the padding
    try_cast(split_part(ftscore, ':', 1) as integer) as home_goals,
    try_cast(split_part(ftscore, ':', 2) as integer) as away_goals,

    attendance,
    venuename as venue_name,
    load_date
from source
