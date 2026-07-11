-- Grain: one row per confidently matched player -- the explicit join key
-- between FPL and WhoScored, which share no natural identifier.
--
-- Matching is a ladder of *deterministic, exact* rules over unicode- and
-- case-normalized names. No fuzzy matching, deliberately: a wrong mapping
-- silently corrupts every downstream join, while an unmatched player is
-- visible and countable. Each rule only sees players the rules above left
-- unmatched, and any name that would match more than one candidate is
-- dropped rather than guessed.
--
-- Unmatched players are expected, not a defect: the WhoScored export is the
-- 2024/25 season while FPL snapshots are 2025/26, so relegated clubs'
-- players and mid-season departures legitimately have no FPL counterpart
-- (~63% of WhoScored players map on current data).
with ws as (
    select
        player_ws_id,
        lower(strip_accents(player_name)) as ws_name
    from {{ ref('stg_whoscored_players') }}
),

fpl as (
    select
        player_id as fpl_player_id,
        lower(strip_accents(first_name || ' ' || second_name)) as full_name,
        -- FPL names are official long-form, hiding the common surname at
        -- either end: 'Bruno Miguel Borges Fernandes' goes by the LAST
        -- surname token, 'David Raya Martin' by the FIRST -- a rule for each
        lower(strip_accents(
            split_part(first_name, ' ', 1) || ' ' || split_part(second_name, ' ', -1)
        )) as short_name,
        lower(strip_accents(
            split_part(first_name, ' ', 1) || ' ' || split_part(second_name, ' ', 1)
        )) as first_tokens,
        lower(strip_accents(web_name)) as web_name
    from {{ ref('stg_fpl_players') }}
    where load_date = (select max(load_date) from {{ ref('stg_fpl_players') }})
      and not removed
),

rule_full_name as (
    select
        ws.player_ws_id,
        fpl.fpl_player_id,
        'full_name' as match_rule
    from ws
    inner join fpl on ws.ws_name = fpl.full_name
),

rule_short_name as (
    select player_ws_id, fpl_player_id, 'short_name' as match_rule
    from (
        select
            ws.player_ws_id,
            fpl.fpl_player_id,
            count(*) over (partition by ws.player_ws_id) as n_per_ws,
            count(*) over (partition by fpl.fpl_player_id) as n_per_fpl
        from ws
        inner join fpl on ws.ws_name = fpl.short_name
        where ws.player_ws_id not in (select player_ws_id from rule_full_name)
          and fpl.fpl_player_id not in (select fpl_player_id from rule_full_name)
    )
    where n_per_ws = 1 and n_per_fpl = 1
),

matched_so_far as (
    select player_ws_id, fpl_player_id from rule_full_name
    union all
    select player_ws_id, fpl_player_id from rule_short_name
),

rule_first_tokens as (
    select player_ws_id, fpl_player_id, 'first_tokens' as match_rule
    from (
        select
            ws.player_ws_id,
            fpl.fpl_player_id,
            count(*) over (partition by ws.player_ws_id) as n_per_ws,
            count(*) over (partition by fpl.fpl_player_id) as n_per_fpl
        from ws
        inner join fpl on ws.ws_name = fpl.first_tokens
        where ws.player_ws_id not in (select player_ws_id from matched_so_far)
          and fpl.fpl_player_id not in (select fpl_player_id from matched_so_far)
    )
    where n_per_ws = 1 and n_per_fpl = 1
),

matched_so_far_2 as (
    select player_ws_id, fpl_player_id from matched_so_far
    union all
    select player_ws_id, fpl_player_id from rule_first_tokens
),

rule_web_name as (
    select player_ws_id, fpl_player_id, 'web_name' as match_rule
    from (
        select
            ws.player_ws_id,
            fpl.fpl_player_id,
            count(*) over (partition by ws.player_ws_id) as n_per_ws,
            count(*) over (partition by fpl.fpl_player_id) as n_per_fpl
        from ws
        inner join fpl on ws.ws_name = fpl.web_name
        where ws.player_ws_id not in (select player_ws_id from matched_so_far_2)
          and fpl.fpl_player_id not in (select fpl_player_id from matched_so_far_2)
    )
    where n_per_ws = 1 and n_per_fpl = 1
)

select player_ws_id, fpl_player_id, match_rule from rule_full_name
union all
select player_ws_id, fpl_player_id, match_rule from rule_short_name
union all
select player_ws_id, fpl_player_id, match_rule from rule_first_tokens
union all
select player_ws_id, fpl_player_id, match_rule from rule_web_name
