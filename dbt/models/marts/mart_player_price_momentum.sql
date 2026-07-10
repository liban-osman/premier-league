-- The FPL API only ever exposes cost_change_since_season_start -- it can't
-- tell you what happened between any two arbitrary dates. Comparing each
-- snapshot to our own previous one is the actual point of snapshotting: it
-- builds the day-to-day price/ownership trend the API throws away.
with players as (
    select * from {{ ref('stg_fpl_players') }}
),

with_prev as (
    select
        *,
        lag(now_cost) over (partition by player_id order by load_date) as prev_now_cost,
        lag(selected_by_percent) over (partition by player_id order by load_date)
            as prev_selected_by_percent
    from players
)

select
    load_date,
    player_id,
    web_name,
    team_id,
    position_id,
    now_cost,
    prev_now_cost,
    now_cost - prev_now_cost as price_change_since_prev_snapshot,
    selected_by_percent,
    prev_selected_by_percent,
    round(selected_by_percent - prev_selected_by_percent, 2) as ownership_change_since_prev_snapshot,
    transfers_in_event,
    transfers_out_event,
    transfers_in_event - transfers_out_event as net_transfers_event,
    case
        when prev_now_cost is null then 'no_prior_snapshot'
        when now_cost > prev_now_cost then 'rising'
        when now_cost < prev_now_cost then 'falling'
        else 'stable'
    end as price_trend
from with_prev
order by player_id, load_date
