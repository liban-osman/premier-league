-- The decision layer: one row per (load_date, player_id) with a 0-100
-- transfer_score and a recommendation bucket, plus each player's own
-- previous snapshot for both so a page can surface who just changed
-- (recommendation_trend), not just today's ranking. Each signal is
-- converted to a percent_rank within (load_date, position) so "good"
-- always means "relative to the players you could actually swap them
-- for", then combined with explicit weights. Availability is a hard
-- gate, not a weighted input: an injured player is not 15% less
-- attractive, they're undroppable-in.
--
-- Weights (a deliberate, tunable design choice, not a fitted model):
--   30% value (points per GBP m), 25% form, 20% underlying threat
--   (Understat npxG+xA per 90 -- an independent xG model, robust to
--   finishing luck), 15% fixture ease (next 5), 10% transfer momentum.
with value as (
    select * from {{ ref('mart_player_value') }}
),

momentum as (
    select * from {{ ref('mart_player_price_momentum') }}
),

availability as (
    select * from {{ ref('mart_player_availability_risk') }}
),

-- Team-grain fixture signal: the rolling next-5 FDR run starting at each
-- team's next unplayed fixture, ranked across the 20 teams (hardest run = 0,
-- easiest = 1). Null when a team has no unplayed fixtures (season over).
next5 as (
    select
        load_date,
        team_id,
        avg_difficulty_next_5,
        percent_rank() over (
            partition by load_date
            order by avg_difficulty_next_5 desc
        ) as fixture_pctl
    from {{ ref('mart_team_fixture_difficulty') }}
    where upcoming_fixture_number = 1
),

-- Underlying threat: Understat's npxG + xA per 90, season-matched to each
-- snapshot and joined through the map's stable player_code (player_id resets
-- every season; the code doesn't, so historical snapshots keep joining
-- correctly after a rollover). Scoped to outfield players with >=450
-- Understat minutes: keepers all sit at ~0 npxG+xA (percent_rank would rank
-- them all bottom instead of neutral), and tiny-minute per-90 rates are
-- noise. Everyone excluded coalesces to the neutral 0.5 downstream.
underlying as (
    select
        p.load_date,
        p.player_id,
        round((u.npxg + u.xa) / (u.minutes / 90.0), 2) as npxg_xa_per90,
        percent_rank() over (
            partition by p.load_date, p.position_id
            order by (u.npxg + u.xa) / (u.minutes / 90.0)
        ) as underlying_pctl
    from {{ ref('stg_fpl_players') }} p
    inner join {{ ref('stg_fpl_positions') }} pos on p.position_id = pos.position_id
    inner join {{ ref('player_id_map_understat') }} m on p.player_code = m.fpl_player_code
    inner join {{ ref('stg_understat_players') }} u
        on m.player_ud_id = u.player_ud_id
        and u.season = try_cast(p.season as integer)
    where pos.position_short_name != 'GKP' and u.minutes >= 450
),

-- Base population is mart_player_value (removed = false); the other player
-- marts are supersets or same-filtered, so these joins can't drop rows.
joined as (
    select
        v.load_date,
        v.player_id,
        v.web_name,
        v.team_id,
        t.team_name,
        v.position_id,
        p.position_short_name,
        v.now_cost,
        v.total_points,
        v.points_per_million,
        v.form,
        m.price_trend,
        m.net_transfers_event,
        m.selected_by_percent,
        a.availability_risk,
        a.news,
        n.avg_difficulty_next_5,
        n.fixture_pctl,
        u.npxg_xa_per90,
        u.underlying_pctl
    from value v
    left join momentum m on v.load_date = m.load_date and v.player_id = m.player_id
    left join availability a on v.load_date = a.load_date and v.player_id = a.player_id
    left join next5 n on v.load_date = n.load_date and v.team_id = n.team_id
    left join underlying u on v.load_date = u.load_date and v.player_id = u.player_id
    left join {{ ref('stg_fpl_teams') }} t
        on v.load_date = t.load_date and v.team_id = t.team_id
    left join {{ ref('stg_fpl_positions') }} p on v.position_id = p.position_id
),

scored as (
    select
        *,
        percent_rank() over (
            partition by load_date, position_id
            order by points_per_million
        ) as value_pctl,
        percent_rank() over (
            partition by load_date, position_id
            order by form
        ) as form_pctl,
        percent_rank() over (
            partition by load_date, position_id
            order by net_transfers_event
        ) as momentum_pctl
    from joined
),

-- A missing signal coalesces to 0.5 (neutral): it should neither boost nor
-- sink the player, and the score stays on the same 0-100 scale for everyone.
weighted as (
    select
        *,
        round(
            100 * (
                0.30 * coalesce(value_pctl, 0.5)
                + 0.25 * coalesce(form_pctl, 0.5)
                + 0.20 * coalesce(underlying_pctl, 0.5)
                + 0.15 * coalesce(fixture_pctl, 0.5)
                + 0.10 * coalesce(momentum_pctl, 0.5)
            ),
            1
        ) as transfer_score
    from scored
),

-- recommendation, hoisted out of the terminal select into its own CTE so
-- lag() below has a named column to look back over.
recommended as (
    select
        *,
        case
            when availability_risk = 'high_risk' then 'drop'
            when availability_risk = 'doubtful' and transfer_score >= 40 then 'monitor'
            when transfer_score >= 75 then 'transfer_in'
            when transfer_score >= 40 then 'hold'
            else 'monitor'
        end as recommendation
    from weighted
),

-- Ordinal mapped from the bucket name itself (not a second copy of the
-- threshold conditions above), so "upgraded"/"downgraded" is a real order
-- comparison without risking the two definitions drifting apart if the
-- thresholds above ever change.
ranked as (
    select
        *,
        case recommendation
            when 'drop' then 0
            when 'monitor' then 1
            when 'hold' then 2
            when 'transfer_in' then 3
        end as recommendation_rank
    from recommended
),

-- Same lag()-over-player_id idiom as mart_player_price_momentum /
-- mart_player_form_trend, applied to this mart's own derived score and
-- recommendation instead of a raw staged column.
with_prev as (
    select
        *,
        lag(transfer_score) over (
            partition by player_id order by load_date
        ) as prev_transfer_score,
        lag(recommendation) over (
            partition by player_id order by load_date
        ) as prev_recommendation,
        lag(recommendation_rank) over (
            partition by player_id order by load_date
        ) as prev_recommendation_rank
    from ranked
)

select
    load_date,
    player_id,
    web_name,
    team_id,
    team_name,
    position_id,
    position_short_name,
    round(now_cost / 10.0, 1) as price_m,
    total_points,
    points_per_million,
    form,
    avg_difficulty_next_5,
    price_trend,
    net_transfers_event,
    selected_by_percent,
    availability_risk,
    news,
    npxg_xa_per90,
    round(value_pctl, 2) as value_pctl,
    round(form_pctl, 2) as form_pctl,
    round(underlying_pctl, 2) as underlying_pctl,
    round(fixture_pctl, 2) as fixture_pctl,
    round(momentum_pctl, 2) as momentum_pctl,
    transfer_score,
    recommendation,
    prev_transfer_score,
    round(transfer_score - prev_transfer_score, 1) as score_change_since_prev_snapshot,
    prev_recommendation,
    case
        when prev_recommendation is null then 'no_prior_snapshot'
        when recommendation_rank = prev_recommendation_rank then 'unchanged'
        when recommendation_rank > prev_recommendation_rank then 'upgraded'
        else 'downgraded'
    end as recommendation_trend
from with_prev
order by load_date, transfer_score desc
