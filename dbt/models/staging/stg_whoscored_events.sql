-- Grain: one row per exported event element (~580k per season). Not one row
-- per event id: the export itself carries a handful of duplicated ids
-- (27 pairs in 579k), so no uniqueness is claimed at this grain.
--
-- The deeply nested qualifiers stay as an opaque JSON blob -- raw landing
-- capped inference depth for exactly this reason (see scripts/load_raw.py);
-- parse specific qualifiers downstream once a mart actually needs them.
with source as (
    select
        try_cast(regexp_extract(filename, '(\d+)\.json$', 1) as integer) as match_id,
        load_date,
        unnest(events) as e
    from {{ source('raw', 'whoscored_events') }}
)

select
    match_id,
    try_cast(e ->> 'id' as bigint) as event_ws_id,
    try_cast(e ->> 'minute' as integer) as minute,
    try_cast(e ->> 'second' as integer) as second,
    try_cast(e ->> 'teamId' as integer) as team_ws_id,
    -- null for the ~1% of events not attributable to a player (kickoff etc.)
    try_cast(e ->> 'playerId' as integer) as player_ws_id,
    e -> 'type' ->> 'displayName' as event_type,
    (e -> 'outcomeType' ->> 'displayName') = 'Successful' as is_successful,
    try_cast(e ->> 'isTouch' as boolean) as is_touch,
    try_cast(e ->> 'x' as double) as x,
    try_cast(e ->> 'y' as double) as y,
    e -> 'qualifiers' as qualifiers,
    load_date
from source
