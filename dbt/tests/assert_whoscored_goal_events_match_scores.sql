-- The same WhoScored payload records every goal twice: as a Goal event in the
-- event stream and inside the ftScore string. A complete, correctly parsed
-- export must agree with itself -- a mismatch means a future upload landed
-- with truncated event arrays or the score parse broke. (Own goals are typed
-- 'Goal' too, so the two counts are directly comparable.)
select
    goal_events,
    score_goals
from (
    select count(*) as goal_events
    from {{ ref('stg_whoscored_events') }}
    where event_type = 'Goal'
),
(
    select sum(home_goals + away_goals) as score_goals
    from {{ ref('stg_whoscored_matches') }}
)
where goal_events != score_goals
