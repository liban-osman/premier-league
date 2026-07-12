-- Grain: one row per confidently matched player -- the explicit FPL <->
-- Understat join key. Same deterministic exact-match rule ladder as
-- player_id_map (see that model for the full reasoning: no fuzzy matching,
-- ambiguous candidates dropped, unmatched players are visible rather than
-- guessed). Understat 2025 and the FPL snapshots cover the SAME season, so
-- the match rate should run well above the WhoScored map's 63%.
with ud as (
    select
        player_ud_id,
        lower(strip_accents(mode(player_name))) as ud_name
    from {{ ref('stg_understat_players') }}
    group by player_ud_id
),

fpl as (
    select
        player_id as fpl_player_id,
        player_code,
        lower(strip_accents(first_name || ' ' || second_name)) as full_name,
        -- long official names hide the common surname at either end:
        -- 'Bruno Miguel Borges Fernandes' goes by the LAST surname token,
        -- 'David Raya Martin' by the FIRST -- one rule for each
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
        ud.player_ud_id,
        fpl.fpl_player_id,
        'full_name' as match_rule
    from ud
    inner join fpl on ud.ud_name = fpl.full_name
),

rule_short_name as (
    select player_ud_id, fpl_player_id, 'short_name' as match_rule
    from (
        select
            ud.player_ud_id,
            fpl.fpl_player_id,
            count(*) over (partition by ud.player_ud_id) as n_per_ud,
            count(*) over (partition by fpl.fpl_player_id) as n_per_fpl
        from ud
        inner join fpl on ud.ud_name = fpl.short_name
        where ud.player_ud_id not in (select player_ud_id from rule_full_name)
          and fpl.fpl_player_id not in (select fpl_player_id from rule_full_name)
    )
    where n_per_ud = 1 and n_per_fpl = 1
),

matched_so_far as (
    select player_ud_id, fpl_player_id from rule_full_name
    union all
    select player_ud_id, fpl_player_id from rule_short_name
),

rule_first_tokens as (
    select player_ud_id, fpl_player_id, 'first_tokens' as match_rule
    from (
        select
            ud.player_ud_id,
            fpl.fpl_player_id,
            count(*) over (partition by ud.player_ud_id) as n_per_ud,
            count(*) over (partition by fpl.fpl_player_id) as n_per_fpl
        from ud
        inner join fpl on ud.ud_name = fpl.first_tokens
        where ud.player_ud_id not in (select player_ud_id from matched_so_far)
          and fpl.fpl_player_id not in (select fpl_player_id from matched_so_far)
    )
    where n_per_ud = 1 and n_per_fpl = 1
),

matched_so_far_2 as (
    select player_ud_id, fpl_player_id from matched_so_far
    union all
    select player_ud_id, fpl_player_id from rule_first_tokens
),

rule_web_name as (
    select player_ud_id, fpl_player_id, 'web_name' as match_rule
    from (
        select
            ud.player_ud_id,
            fpl.fpl_player_id,
            count(*) over (partition by ud.player_ud_id) as n_per_ud,
            count(*) over (partition by fpl.fpl_player_id) as n_per_fpl
        from ud
        inner join fpl on ud.ud_name = fpl.web_name
        where ud.player_ud_id not in (select player_ud_id from matched_so_far_2)
          and fpl.fpl_player_id not in (select fpl_player_id from matched_so_far_2)
    )
    where n_per_ud = 1 and n_per_fpl = 1
),

ladder as (
    select player_ud_id, fpl_player_id, match_rule from rule_full_name
    union all
    select player_ud_id, fpl_player_id, match_rule from rule_short_name
    union all
    select player_ud_id, fpl_player_id, match_rule from rule_first_tokens
    union all
    select player_ud_id, fpl_player_id, match_rule from rule_web_name
),

-- Hand-verified pairs the ladder can't reach (transliterations, nicknames,
-- name-order flips -- see the seed's note column). Keyed on the stable
-- player_code so the seed survives season rollovers; resolved to the
-- current season's player_id here.
overrides as (
    select
        o.player_ud_id,
        fpl.fpl_player_id,
        'manual' as match_rule
    from {{ ref('seed_player_map_overrides_understat') }} o
    inner join fpl on o.fpl_player_code = fpl.player_code
)

-- Overrides win: a ladder row that conflicts with an override on either id
-- is dropped, so the unique (1:1) tests keep holding by construction.
select player_ud_id, fpl_player_id, match_rule from overrides
union all
select player_ud_id, fpl_player_id, match_rule
from ladder
where player_ud_id not in (select player_ud_id from overrides)
  and fpl_player_id not in (select fpl_player_id from overrides)
