-- The same getLeagueData payload reports goals twice: per match (dates block)
-- and inside each team's history (teams block). The two land as separate S3
-- files and raw tables, so this catches a partial landing or a broken parse
-- on either path -- per season, total match goals must equal total goals
-- scored across all team histories.
with match_goals as (
    select season, sum(home_goals + away_goals) as goals
    from {{ ref('stg_understat_matches') }}
    where is_result
    group by season
),

team_goals as (
    select season, sum(goals_scored) as goals
    from {{ ref('stg_understat_team_matches') }}
    group by season
)

select
    season,
    m.goals as match_goals,
    t.goals as team_goals
from match_goals m
inner join team_goals t using (season)
where m.goals != t.goals
