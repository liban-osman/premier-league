-- Points per GBP million, recomputed from our own data each snapshot rather
-- than trusting FPL's own value_season field, and ranked within position so
-- "good value" means relative to the players you'd actually swap them for.
with players as (
    select * from {{ ref('stg_fpl_players') }}
    where removed = false
),

valued as (
    select
        load_date,
        player_id,
        web_name,
        team_id,
        position_id,
        now_cost,
        total_points,
        round(total_points / nullif(now_cost / 10.0, 0), 2) as points_per_million,
        form,
        points_per_game,
        minutes
    from players
)

select
    *,
    rank() over (
        partition by load_date, position_id
        order by points_per_million desc
    ) as value_rank_in_position
from valued
