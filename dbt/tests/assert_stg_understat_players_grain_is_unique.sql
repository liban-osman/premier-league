-- One row per (season, player): the latest-load_date-per-season filter is
-- what enforces this -- if it broke, every weekly refresh would duplicate
-- the season's players.
select
    season,
    player_ud_id,
    count(*) as n
from {{ ref('stg_understat_players') }}
group by season, player_ud_id
having count(*) > 1
