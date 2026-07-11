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
        away_score as goals_against,
        kickoff_time
    from fixtures

    union all

    select
        load_date,
        season,
        away_team_id as team_id,
        away_score as goals_for,
        home_score as goals_against,
        kickoff_time
    from fixtures
),

-- Form guide: each team's last five results as a 'W D L' string, oldest to
-- newest, so the rightmost letter is the most recent match.
form as (
    select
        load_date,
        team_id,
        string_agg(
            case
                when goals_for > goals_against then 'W'
                when goals_for = goals_against then 'D'
                else 'L'
            end,
            ' '
            order by kickoff_time
        ) as form_last_5
    from (
        select
            *,
            row_number() over (
                partition by load_date, team_id order by kickoff_time desc
            ) as recency
        from team_results
    )
    where recency <= 5
    group by load_date, team_id
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
    t.team_code,
    a.played,
    a.won,
    a.drawn,
    a.lost,
    a.goals_for,
    a.goals_against,
    a.goal_difference,
    a.points,
    f.form_last_5
from aggregated a
left join {{ ref('stg_fpl_teams') }} t
    on a.load_date = t.load_date and a.team_id = t.team_id
left join form f
    on a.load_date = f.load_date and a.team_id = f.team_id
order by a.load_date, position
