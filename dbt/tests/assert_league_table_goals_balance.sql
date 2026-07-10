-- Singular test: in any snapshot, every goal scored by one team is conceded
-- by another, so league-wide goals_for must equal goals_against. Catches
-- double-counting or dropped sides in the home/away unpivot.
select
    load_date,
    sum(goals_for) as total_for,
    sum(goals_against) as total_against
from {{ ref('mart_league_table') }}
group by load_date
having sum(goals_for) != sum(goals_against)
