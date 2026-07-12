-- Singular test: fails (returns rows) if any join in mart_team_defensive_outlook
-- fans out and produces more than one row per (load_date, team_id).
select
    load_date,
    team_id,
    count(*) as row_count
from {{ ref('mart_team_defensive_outlook') }}
group by load_date, team_id
having count(*) > 1
