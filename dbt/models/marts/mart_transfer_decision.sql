-- The decision layer: one row per (load_date, player_id) with a 0-100
-- transfer_score and a recommendation bucket. Each signal is converted to a
-- percent_rank within (load_date, position) so "good" always means "relative
-- to the players you could actually swap them for", then combined with
-- explicit weights. Availability is a hard gate, not a weighted input: an
-- injured player is not 15% less attractive, they're undroppable-in.
--
-- Weights (a deliberate, tunable design choice, not a fitted model):
--   35% value (points per GBP m), 30% form, 20% fixture ease (next 5),
--   15% transfer momentum (net transfers this gameweek).
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
        n.fixture_pctl
    from value v
    left join momentum m on v.load_date = m.load_date and v.player_id = m.player_id
    left join availability a on v.load_date = a.load_date and v.player_id = a.player_id
    left join next5 n on v.load_date = n.load_date and v.team_id = n.team_id
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
                0.35 * coalesce(value_pctl, 0.5)
                + 0.30 * coalesce(form_pctl, 0.5)
                + 0.20 * coalesce(fixture_pctl, 0.5)
                + 0.15 * coalesce(momentum_pctl, 0.5)
            ),
            1
        ) as transfer_score
    from scored
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
    round(value_pctl, 2) as value_pctl,
    round(form_pctl, 2) as form_pctl,
    round(fixture_pctl, 2) as fixture_pctl,
    round(momentum_pctl, 2) as momentum_pctl,
    transfer_score,
    case
        when availability_risk = 'high_risk' then 'drop'
        when availability_risk = 'doubtful' and transfer_score >= 40 then 'monitor'
        when transfer_score >= 75 then 'transfer_in'
        when transfer_score >= 40 then 'hold'
        else 'monitor'
    end as recommendation
from weighted
order by load_date, transfer_score desc
