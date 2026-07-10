-- Unpivots each fixture into one row per team (so "Arsenal's fixtures" is a
-- plain filter, not a CASE on home/away), then ranks each team's still-unplayed
-- fixtures by kickoff and rolls up the average FDR over their next 5 -- the
-- actual "good run of fixtures coming up" signal for the decision layer.
with fixtures as (
    select * from {{ ref('stg_fpl_fixtures') }}
),

team_fixtures as (
    select
        load_date, season, fixture_id, gameweek, kickoff_time, finished,
        home_team_id as team_id, away_team_id as opponent_team_id,
        true as is_home, home_difficulty as difficulty
    from fixtures

    union all

    select
        load_date, season, fixture_id, gameweek, kickoff_time, finished,
        away_team_id as team_id, home_team_id as opponent_team_id,
        false as is_home, away_difficulty as difficulty
    from fixtures
),

upcoming_ranked as (
    select
        load_date, team_id, fixture_id,
        row_number() over (partition by load_date, team_id order by kickoff_time) as upcoming_fixture_number
    from team_fixtures
    where finished = false
),

with_run_avg as (
    select
        load_date, team_id, fixture_id, upcoming_fixture_number,
        avg(difficulty_for_run) over (
            partition by load_date, team_id
            order by upcoming_fixture_number
            rows between current row and 4 following
        ) as avg_difficulty_next_5
    from (
        select ur.*, tf.difficulty as difficulty_for_run
        from upcoming_ranked ur
        join team_fixtures tf
            on ur.load_date = tf.load_date
            and ur.team_id = tf.team_id
            and ur.fixture_id = tf.fixture_id
    )
)

select
    tf.load_date,
    tf.season,
    tf.fixture_id,
    tf.gameweek,
    tf.team_id,
    t.team_name,
    tf.opponent_team_id,
    ot.team_name as opponent_name,
    tf.is_home,
    tf.difficulty,
    tf.kickoff_time,
    tf.finished,
    wra.upcoming_fixture_number,
    round(wra.avg_difficulty_next_5, 2) as avg_difficulty_next_5
from team_fixtures tf
left join with_run_avg wra
    on tf.load_date = wra.load_date
    and tf.team_id = wra.team_id
    and tf.fixture_id = wra.fixture_id
left join {{ ref('stg_fpl_teams') }} t
    on tf.load_date = t.load_date and tf.team_id = t.team_id
left join {{ ref('stg_fpl_teams') }} ot
    on tf.load_date = ot.load_date and tf.opponent_team_id = ot.team_id
order by tf.load_date, tf.team_id, tf.kickoff_time
