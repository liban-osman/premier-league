-- Cross-source reconciliation: WhoScored and Understat are independent
-- providers measuring the same objective reality (goals in finished
-- Premier League matches). For any season both sources cover, their season
-- goal totals must agree exactly -- a mismatch means one side landed
-- incomplete data. Seasons only one source covers are skipped by the join.
with whoscored as (
    select season_start_year as season, sum(home_goals + away_goals) as goals
    from {{ ref('stg_whoscored_matches') }}
    group by 1
),

understat as (
    select season, sum(home_goals + away_goals) as goals
    from {{ ref('stg_understat_matches') }}
    where is_result
    group by 1
)

select
    season,
    w.goals as whoscored_goals,
    u.goals as understat_goals
from whoscored w
inner join understat u using (season)
where w.goals != u.goals
