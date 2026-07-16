import altair as alt
import pandas as pd
import streamlit as st
from db import get_conn
from ui import badge_url, photo_url, position_badge, series_hues

st.title("FPL Transfer Decisions")

# Status markers ship as icon + label together, never color alone.
VERDICT = {
    "transfer_in": "🟢 Transfer in",
    "hold": "🔵 Hold",
    "monitor": "🟡 Monitor",
    "drop": "🔴 Drop",
}


# Cached for an hour: the mart only changes once a day when the snapshot lands.
# player_code (the photo asset id) and team_code (the badge asset id) join in
# from staging rather than widening the mart -- display attributes, not
# decision signals.
@st.cache_data(ttl=3600)
def load_latest_snapshot():
    conn = get_conn()
    df = conn.execute(
        """
        select d.*, p.player_code, t.team_code
        from gold.mart_transfer_decision d
        left join silver.stg_fpl_players p
            on d.load_date = p.load_date and d.player_id = p.player_id
        left join silver.stg_fpl_teams t
            on d.load_date = t.load_date and d.team_id = t.team_id
        where d.load_date = (select max(load_date) from gold.mart_transfer_decision)
        order by d.transfer_score desc
        """
    ).df()
    conn.close()
    df["photo"] = df["player_code"].map(photo_url)
    # The badge rides alongside the photo everywhere a photo appears: the PL's
    # official headshot CDN can lag a real transfer by months (kit stays the
    # old club's), but the badge is keyed on the club itself so it's never stale.
    df["badge"] = df["team_code"].map(badge_url)
    df["verdict"] = df["recommendation"].map(VERDICT)
    df["prev_verdict"] = df["prev_recommendation"].map(VERDICT)
    return df


@st.cache_data(ttl=3600)
def load_defensive_outlook():
    conn = get_conn()
    out = conn.execute(
        """
        select d.*, t.team_code
        from gold.mart_team_defensive_outlook d
        left join silver.stg_fpl_teams t
            on d.load_date = t.load_date and d.team_id = t.team_id
        where d.load_date = (select max(load_date) from gold.mart_team_defensive_outlook)
        order by d.defensive_outlook_score desc
        """
    ).df()
    conn.close()
    out["badge"] = out["team_code"].map(badge_url)
    return out


@st.cache_data(ttl=3600)
def load_next_fixtures():
    conn = get_conn()
    out = conn.execute(
        """
        select team_id, opponent_name, is_home, difficulty
        from gold.mart_team_fixture_difficulty
        where load_date = (select max(load_date) from gold.mart_team_fixture_difficulty)
          and upcoming_fixture_number = 1
        """
    ).df()
    conn.close()
    return out


def player_mini_card(container, row: pd.Series, detail: str, section: str) -> None:
    """photo + badge + name + position + one caption line -- the shared unit
    for movers, budget picks, differentials, clean sheet picks, captaincy,
    and top-pick tiles. Left border is status-colored (keyed off `recommendation`,
    present on every row this is called with); name carries a position badge.
    `section` scopes the container key so the same player appearing in two
    sections (e.g. a budget pick that's also its position's top pick) doesn't
    collide -- Streamlit keys must be unique across the whole page render."""
    key = f"status-{row['recommendation']}-{section}-{row['player_id']}"
    with container.container(border=True, key=key):
        face, badge_col, facts = st.columns([1, 0.4, 1.6], vertical_alignment="center")
        face.image(row["photo"], width=56)
        if pd.notna(row["badge"]):
            badge_col.image(row["badge"], width=24)
        facts.markdown(
            f"**{row['web_name']}**{position_badge(row.get('position_short_name'))}",
            unsafe_allow_html=True,
        )
        facts.caption(detail)


def mover_detail(row: pd.Series) -> str:
    return (
        f"{row['team_name']}  \n"
        f"{row['prev_verdict']} → {row['verdict']}  \n"
        f"score {row['prev_transfer_score']:.0f} → {row['transfer_score']:.0f} · "
        f"owned {row['selected_by_percent']:.1f}%"
    )


df = load_latest_snapshot()
st.caption(f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d} — {len(df)} players scored")

st.subheader("📢 Movers since last snapshot")
all_movers = df[df["recommendation_trend"].isin(["upgraded", "downgraded"])]

if all_movers.empty:
    # Real state as of writing: the live pipeline only started 2026-07-10 and
    # it's deep preseason, so transfer_score hasn't moved day-over-day yet.
    # The section stays visible with an honest explanation rather than
    # hiding -- a hidden feature reads as unbuilt, not quiet.
    st.info(
        "No transfer_score verdicts have changed since the previous snapshot yet. "
        "This fills in once the season's fixtures, form, and prices start moving "
        "week to week."
    )
else:
    ownership_threshold = st.slider(
        "Minimum ownership to count as a high-owned player (%)",
        0.0,
        float(df["selected_by_percent"].max()),
        5.0,
        step=0.5,
    )
    high_owned_movers = all_movers[all_movers["selected_by_percent"] >= ownership_threshold]
    downgraded = high_owned_movers[
        high_owned_movers["recommendation_trend"] == "downgraded"
    ].sort_values("selected_by_percent", ascending=False)
    upgraded = high_owned_movers[
        high_owned_movers["recommendation_trend"] == "upgraded"
    ].sort_values("selected_by_percent", ascending=False)

    col_sell, col_buy = st.columns(2)
    col_sell.markdown("**🔴 Consider selling**")
    if downgraded.empty:
        col_sell.caption("No high-ownership players downgraded since the last snapshot.")
    else:
        for _, row in downgraded.head(5).iterrows():
            player_mini_card(col_sell, row, detail=mover_detail(row), section="movers-sell")

    col_buy.markdown("**🟢 Rising — consider buying**")
    if upgraded.empty:
        col_buy.caption("No high-ownership players upgraded since the last snapshot.")
    else:
        for _, row in upgraded.head(5).iterrows():
            player_mini_card(col_buy, row, detail=mover_detail(row), section="movers-buy")

st.divider()

st.subheader("💰 Budget picks")
st.caption("Best value under your price cap, split by position so all four show at once.")
price_min, price_max = float(df["price_m"].min()), float(df["price_m"].max())
budget_cutoff = st.slider(
    "Max price to count as a budget pick (£m)",
    price_min,
    price_max,
    min(6.0, price_max),
    step=0.5,
)
budget_pool = df[df["price_m"] <= budget_cutoff]

budget_cols = st.columns(4)
for col, pos in zip(budget_cols, ["GKP", "DEF", "MID", "FWD"]):
    col.markdown(f"**{pos}**")
    # transfer_score, not points_per_million: the score already bakes in the
    # availability hard gate, so an injured cheap player can't wrongly surface
    # as a "pick" the way a raw value sort could.
    pos_picks = (
        budget_pool[budget_pool["position_short_name"] == pos]
        .sort_values("transfer_score", ascending=False)
        .head(3)
    )
    if pos_picks.empty:
        col.caption(f"None at £{budget_cutoff:.1f}m or under.")
    else:
        for _, row in pos_picks.iterrows():
            player_mini_card(
                col,
                row,
                detail=(
                    f"{row['team_name']}  \n"
                    f"score {row['transfer_score']:.0f} · £{row['price_m']}m · "
                    f"{row['points_per_million']:.1f} pts/£m"
                ),
                section="budget",
            )

st.divider()

st.subheader("🎯 Differentials")
st.caption(
    "High transfer_score, low ownership -- picks for climbing rank rather than "
    "tracking the template."
)
diff_max_owned = st.slider(
    "Max ownership to count as a differential (%)",
    0.0,
    float(df["selected_by_percent"].max()),
    5.0,
    step=0.5,
)
differentials = (
    df[df["selected_by_percent"] <= diff_max_owned]
    .sort_values("transfer_score", ascending=False)
    .head(5)
)

if differentials.empty:
    st.caption(f"No players at {diff_max_owned:.1f}% ownership or under match this filter.")
else:
    diff_tiles = st.columns(len(differentials))
    for tile, (_, row) in zip(diff_tiles, differentials.iterrows()):
        player_mini_card(
            tile,
            row,
            detail=(
                f"{row['team_name']}  \n"
                f"score {row['transfer_score']:.0f} · owned {row['selected_by_percent']:.1f}%"
            ),
            section="differentials",
        )

st.divider()

st.subheader("🧤 Clean sheet picks")
st.caption(
    "Best goalkeeper/defender holds by defensive outlook -- clean-sheet rate this "
    "season blended with upcoming fixture ease. transfer_score's own signals barely "
    "speak to defense: its underlying-threat component is an attacking metric that "
    "sits neutral for keepers."
)
defensive = load_defensive_outlook()
if defensive["fixture_pctl"].isna().all():
    st.caption(
        "Fixture ease isn't available yet (next season's fixture list hasn't been "
        "published) -- rankings are on clean-sheet record alone for now."
    )

for _, team_row in defensive.head(4).iterrows():
    team_pool = df[df["team_id"] == team_row["team_id"]]
    top_gkp = team_pool[team_pool["position_short_name"] == "GKP"].sort_values(
        "transfer_score", ascending=False
    )
    top_def = team_pool[team_pool["position_short_name"] == "DEF"].sort_values(
        "transfer_score", ascending=False
    )
    with st.container(border=True):
        badge_col, name_col = st.columns([0.3, 4], vertical_alignment="center")
        if pd.notna(team_row["badge"]):
            badge_col.image(team_row["badge"], width=28)
        name_col.markdown(
            f"**{team_row['team_name']}** — defensive outlook "
            f"{team_row['defensive_outlook_score']:.0f}/100"
        )
        pick_cols = st.columns(2)
        if not top_gkp.empty:
            gkp = top_gkp.iloc[0]
            player_mini_card(
                pick_cols[0],
                gkp,
                detail=f"🧤 Keeper · score {gkp['transfer_score']:.0f} · £{gkp['price_m']}m",
                section="cleansheet-gkp",
            )
        if not top_def.empty:
            defender = top_def.iloc[0]
            player_mini_card(
                pick_cols[1],
                defender,
                detail=(
                    f"🛡️ Defender · score {defender['transfer_score']:.0f} · £{defender['price_m']}m"
                ),
                section="cleansheet-def",
            )

st.divider()

st.subheader("👑 Captain this gameweek")
st.caption(
    "Top transfer_score players, with their next fixture alongside -- a great score "
    "against a tough fixture is a different call than a great score against a soft one."
)
next_fixtures = load_next_fixtures()
captain_pool = df.merge(next_fixtures, on="team_id", how="left").sort_values(
    "transfer_score", ascending=False
)
if next_fixtures.empty:
    st.caption(
        "Fixture ease isn't available yet (next season's fixture list hasn't been "
        "published) -- ranked on transfer_score alone for now."
    )

captain_tiles = st.columns(5)
for tile, (_, row) in zip(captain_tiles, captain_pool.head(5).iterrows()):
    if pd.notna(row["opponent_name"]):
        venue = "h" if row["is_home"] else "a"
        fixture_detail = f"vs {row['opponent_name']} ({venue}) · FDR {int(row['difficulty'])}"
    else:
        fixture_detail = "fixture TBD"
    player_mini_card(
        tile,
        row,
        detail=f"{row['team_name']}  \nscore {row['transfer_score']:.0f} · {fixture_detail}",
        section="captain",
    )

st.divider()

st.subheader("Top pick by position")
tiles = st.columns(4)
for tile, pos in zip(tiles, ["GKP", "DEF", "MID", "FWD"]):
    pool = df[df["position_short_name"] == pos]
    if pool.empty:
        continue
    pick = pool.iloc[0]  # df is already sorted by transfer_score desc
    player_mini_card(
        tile,
        pick,
        detail=f"{pick['team_name']}  \nscore {pick['transfer_score']:.0f} · £{pick['price_m']}m",
        section="toppick",
    )

with st.expander("Full player table & methodology"):
    st.caption(
        "Daily FPL snapshots → MotherDuck → dbt. transfer_score is a weighted percentile "
        "within position: 30% value (points per £m), 25% form, 20% underlying threat "
        "(Understat npxG+xA per 90), 15% fixture ease (next 5), 10% transfer momentum. "
        "Availability is a hard gate, not a weighted input."
    )

    f_pos, f_verdict, f_search = st.columns([1.6, 2.2, 1.6], vertical_alignment="bottom")
    positions = f_pos.pills("Position", ["GKP", "DEF", "MID", "FWD"], selection_mode="multi")
    verdicts = f_verdict.pills("Recommendation", list(VERDICT.values()), selection_mode="multi")
    search = f_search.text_input("Find a player", placeholder="e.g. Haaland")

    filtered = df
    if positions:
        filtered = filtered[filtered["position_short_name"].isin(positions)]
    if verdicts:
        filtered = filtered[filtered["verdict"].isin(verdicts)]
    if search:
        filtered = filtered[
            filtered["web_name"].str.contains(search, case=False)
            | filtered["team_name"].str.contains(search, case=False, na=False)
        ]

    table = st.dataframe(
        filtered[
            [
                "photo",
                "badge",
                "web_name",
                "team_name",
                "position_short_name",
                "price_m",
                "total_points",
                "points_per_million",
                "form",
                "avg_difficulty_next_5",
                "selected_by_percent",
                "transfer_score",
                "verdict",
                "news",
            ]
        ],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "photo": st.column_config.ImageColumn("", width="small"),
            "badge": st.column_config.ImageColumn("", width="small"),
            "web_name": "Player",
            "team_name": "Team",
            "position_short_name": "Pos",
            "price_m": st.column_config.NumberColumn("Price", format="£%.1fm"),
            "total_points": "Pts",
            "points_per_million": st.column_config.NumberColumn("Pts/£m", format="%.1f"),
            "form": st.column_config.NumberColumn("Form", format="%.1f"),
            "avg_difficulty_next_5": st.column_config.NumberColumn(
                "FDR next 5",
                format="%.1f",
                help="Average FPL difficulty rating of the next five fixtures — lower is easier",
            ),
            "selected_by_percent": st.column_config.NumberColumn("Owned", format="%.1f%%"),
            "transfer_score": st.column_config.ProgressColumn(
                "Score", format="%.0f", min_value=0, max_value=100
            ),
            "verdict": "Verdict",
            "news": "News",
        },
    )
    st.caption("Click a row to see why the score is what it is.")

    if table.selection.rows:
        player = filtered.iloc[table.selection.rows[0]]
        st.divider()
        photo_col, badge_col, facts_col, chart_col = st.columns(
            [1, 0.4, 1.6, 3], vertical_alignment="center"
        )
        photo_col.image(photo_url(player["player_code"], size="250x250"), width=150)
        if pd.notna(player["badge"]):
            badge_col.image(player["badge"], width=36)
        facts_col.markdown(f"### {player['web_name']}")
        facts_col.markdown(
            f"{player['team_name']} · {player['position_short_name']} · £{player['price_m']}m"
        )
        facts_col.markdown(
            f"**{player['verdict']}** — transfer score {player['transfer_score']:.0f}/100"
        )
        facts_col.caption(
            f"{int(player['total_points'])} pts · {player['points_per_million']:.1f} pts/£m · "
            f"form {player['form']:.1f} · owned by {player['selected_by_percent']:.1f}%"
        )
        if pd.notna(player["news"]) and player["news"]:
            facts_col.warning(player["news"])

        # The five weighted signals behind the score, each a percentile within
        # position. A missing signal shows at 0.5 -- the same neutral the mart uses.
        signals = pd.DataFrame(
            {
                "signal": [
                    "Value (30%)",
                    "Form (25%)",
                    "Underlying xG (20%)",
                    "Fixtures (15%)",
                    "Momentum (10%)",
                ],
                "pctl": [
                    player["value_pctl"],
                    player["form_pctl"],
                    player["underlying_pctl"],
                    player["fixture_pctl"],
                    player["momentum_pctl"],
                ],
            }
        )
        signals["pctl"] = signals["pctl"].fillna(0.5)
        blue, _ = series_hues()
        breakdown = (
            alt.Chart(signals)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=blue)
            .encode(
                x=alt.X(
                    "pctl:Q",
                    title="Percentile within position",
                    scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format="%"),
                ),
                y=alt.Y("signal:N", sort=None, title=None),
                tooltip=[
                    alt.Tooltip("signal", title="Signal"),
                    alt.Tooltip("pctl", title="Percentile", format=".0%"),
                ],
            )
            .properties(height=180)
        )
        chart_col.altair_chart(breakdown, width="stretch")
