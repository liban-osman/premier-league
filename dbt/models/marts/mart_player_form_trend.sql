-- form is FPL's own rolling average, but it's still only a current-state
-- number -- this tracks how it and total_points move snapshot to snapshot.
with players as (
    select * from {{ ref('stg_fpl_players') }}
),

with_prev as (
    select
        *,
        lag(form) over (partition by player_id order by load_date) as prev_form,
        lag(total_points) over (partition by player_id order by load_date) as prev_total_points
    from players
)

select
    load_date,
    player_id,
    web_name,
    team_id,
    position_id,
    form,
    prev_form,
    round(form - prev_form, 2) as form_change_since_prev_snapshot,
    total_points,
    total_points - prev_total_points as points_gained_since_prev_snapshot,
    event_points
from with_prev
order by player_id, load_date
