-- Grain: one row per WhoScored player id. Each match payload ships a
-- playerIdNameDictionary of everyone in either squad; flattening and deduping
-- across all matches yields the WhoScored side of the player mapping.
with entries as (
    select
        ent.key as player_ws_id_str,
        ent.value ->> '$' as player_name,
        regexp_extract(filename, '(\d+)\.json$', 1) as match_id
    from {{ source('raw', 'whoscored_events') }},
        unnest(map_entries(playeridnamedictionary)) as t(ent)
)

select
    try_cast(player_ws_id_str as integer) as player_ws_id,
    -- a few players have spelling variants across matches; take the most common
    mode(player_name) as player_name,
    count(distinct match_id) as n_squad_appearances
from entries
group by 1
