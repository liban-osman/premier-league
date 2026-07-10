-- Singular test: fails (returns rows) if any join in mart_transfer_decision
-- fans out and produces more than one row per (load_date, player_id).
select
    load_date,
    player_id,
    count(*) as row_count
from {{ ref('mart_transfer_decision') }}
group by load_date, player_id
having count(*) > 1
