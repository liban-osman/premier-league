-- Defensive outlook: how likely a team is to keep a clean sheet soon,
-- blending their clean-sheet record so far this season with how easy their
-- next run of fixtures is. Built specifically for goalkeeper/defender
-- transfer decisions, which mart_transfer_decision's own signals barely
-- speak to -- its "underlying threat" signal is an attacking metric
-- (npxG+xA) that sits neutral for keepers and only rewards defenders for
-- their own attacking returns, never their defensive record.
with team_clean_sheets as (
    -- clean_sheets is a per-player FPL stat that only accrues to a player
    -- who was on the pitch for a clean match -- an ever-present player's own
    -- count tracks the team's true clean sheet count closely, so the max
    -- across a team's players is a robust proxy without a separate calc.
    select
        load_date,
        team_id,
        max(clean_sheets) as team_clean_sheets
    from {{ ref('stg_fpl_players') }}
    where removed = false
    group by load_date, team_id
),

league as (
    select load_date, team_id, team_name, played
    from {{ ref('mart_league_table') }}
),

-- Same rolling next-5 fixture signal as mart_transfer_decision's own next5
-- CTE (mart_team_fixture_difficulty already computes the raw run; only the
-- percent_rank direction needs repeating here).
next5 as (
    select
        load_date,
        team_id,
        avg_difficulty_next_5,
        percent_rank() over (
            partition by load_date
            order by avg_difficulty_next_5 desc
        ) as fixture_pctl
    from {{ ref('mart_team_fixture_difficulty') }}
    where upcoming_fixture_number = 1
),

-- Clean-sheet rate and its percentile computed only among teams with at
-- least one match played this season -- a played=0 team (new season, before
-- kickoff) has no clean-sheet record to rank on, and coalesces to neutral
-- downstream, the same treatment mart_transfer_decision gives an excluded
-- player rather than let a missing value rank artificially well.
rated as (
    select
        l.load_date,
        l.team_id,
        round(c.team_clean_sheets / l.played, 2) as clean_sheet_rate,
        percent_rank() over (
            partition by l.load_date
            order by c.team_clean_sheets / l.played
        ) as clean_sheet_pctl
    from league l
    inner join team_clean_sheets c on l.load_date = c.load_date and l.team_id = c.team_id
    where l.played > 0
),

joined as (
    select
        l.load_date,
        l.team_id,
        l.team_name,
        l.played,
        c.team_clean_sheets,
        r.clean_sheet_rate,
        r.clean_sheet_pctl,
        n.avg_difficulty_next_5,
        n.fixture_pctl
    from league l
    left join team_clean_sheets c on l.load_date = c.load_date and l.team_id = c.team_id
    left join rated r on l.load_date = r.load_date and l.team_id = r.team_id
    left join next5 n on l.load_date = n.load_date and l.team_id = n.team_id
)

-- Clean-sheet record so far weighs more than one upcoming run of fixtures
-- (a settled defensive record is a stronger prior than 5 games of fixture
-- difficulty): 60% clean_sheet_pctl, 40% fixture_pctl. A missing signal
-- coalesces to 0.5, same convention as mart_transfer_decision.
select
    load_date,
    team_id,
    team_name,
    played,
    team_clean_sheets,
    clean_sheet_rate,
    clean_sheet_pctl,
    avg_difficulty_next_5,
    round(fixture_pctl, 2) as fixture_pctl,
    round(
        100 * (
            0.60 * coalesce(clean_sheet_pctl, 0.5)
            + 0.40 * coalesce(fixture_pctl, 0.5)
        ),
        1
    ) as defensive_outlook_score
from joined
order by load_date, defensive_outlook_score desc
