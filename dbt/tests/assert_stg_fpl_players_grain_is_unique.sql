-- Singular test: fails (returns rows) if the UNNEST in stg_fpl_players ever
-- produces more than one row for the same (load_date, player_id).
select
    load_date,
    player_id,
    count(*) as row_count
from {{ ref('stg_fpl_players') }}
group by load_date, player_id
having count(*) > 1
