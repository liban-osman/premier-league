-- Collapses status + chance_of_playing_next_round + news into one risk flag,
-- since deciding whether to hold/drop a player means reading all three
-- together rather than checking status alone.
with players as (
    select * from {{ ref('stg_fpl_players') }}
    where removed = false
)

select
    load_date,
    player_id,
    web_name,
    team_id,
    position_id,
    status,
    chance_of_playing_next_round,
    chance_of_playing_this_round,
    news,
    news_added,
    case
        when status = 'a' and chance_of_playing_next_round is null then 'available'
        when chance_of_playing_next_round >= 75 then 'likely'
        when chance_of_playing_next_round >= 25 then 'doubtful'
        when status in ('i', 's', 'u')
            or chance_of_playing_next_round < 25 then 'high_risk'
        else 'unknown'
    end as availability_risk
from players
