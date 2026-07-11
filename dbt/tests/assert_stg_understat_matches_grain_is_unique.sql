-- One row per (season, match) -- same latest-load_date guard as the players
-- grain test.
select
    season,
    match_ud_id,
    count(*) as n
from {{ ref('stg_understat_matches') }}
group by season, match_ud_id
having count(*) > 1
