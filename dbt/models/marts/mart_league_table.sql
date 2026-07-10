-- Grain: one row per (load_date, team_id). The league table is derived from
-- finished fixture results, NOT from the bootstrap teams block: FPL zeroes
-- team W/D/L/points in preseason snapshots, so results are the durable source
-- of truth. Tiebreaks follow the PL's first three rules (points, goal
-- difference, goals scored) with team name as a deterministic final tiebreak;
-- head-to-head (rule 4+) is not modelled.
with fixtures as (
    select * from {{ ref('stg_fpl_fixtures') }}
    where finished = true
),

-- One row per team per fixture, from that team's perspective.
team_results as (
    select
        load_date,
        season,
        home_team_id as team_id,
        home_score as goals_for,
        away_score as goals_against
    from fixtures

    union all

    select
        load_date,
        season,
        away_team_id as team_id,
        away_score as goals_for,
        home_score as goals_against
    from fixtures
),

aggregated as (
    select
        load_date,
        season,
        team_id,
        count(*) as played,
        cast(sum(case when goals_for > goals_against then 1 else 0 end) as integer) as won,
        cast(sum(case when goals_for = goals_against then 1 else 0 end) as integer) as drawn,
        cast(sum(case when goals_for < goals_against then 1 else 0 end) as integer) as lost,
        cast(sum(goals_for) as integer) as goals_for,
        cast(sum(goals_against) as integer) as goals_against,
        cast(sum(goals_for) - sum(goals_against) as integer) as goal_difference,
        cast(
            sum(
                case
                    when goals_for > goals_against then 3
                    when goals_for = goals_against then 1
                    else 0
                end
            ) as integer
        ) as points
    from team_results
    group by load_date, season, team_id
)

select
    a.load_date,
    a.season,
    row_number() over (
        partition by a.load_date
        order by a.points desc, a.goal_difference desc, a.goals_for desc, t.team_name
    ) as position,
    a.team_id,
    t.team_name,
    t.team_short_name,
    a.played,
    a.won,
    a.drawn,
    a.lost,
    a.goals_for,
    a.goals_against,
    a.goal_difference,
    a.points
from aggregated a
left join {{ ref('stg_fpl_teams') }} t
    on a.load_date = t.load_date and a.team_id = t.team_id
order by a.load_date, position
