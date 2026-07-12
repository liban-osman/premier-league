import altair as alt
import pandas as pd
import streamlit as st
from db import get_conn
from ui import photo_url, series_hues

st.title("FPL Transfer Decisions")
st.caption(
    "Daily FPL snapshots → MotherDuck → dbt. transfer_score is a weighted percentile "
    "within position: 30% value (points per £m), 25% form, 20% underlying threat "
    "(Understat npxG+xA per 90), 15% fixture ease (next 5), 10% transfer momentum. "
    "Availability is a hard gate, not a weighted input."
)

# Status markers ship as icon + label together, never color alone.
VERDICT = {
    "transfer_in": "🟢 Transfer in",
    "hold": "🔵 Hold",
    "monitor": "🟡 Monitor",
    "drop": "🔴 Drop",
}


# Cached for an hour: the mart only changes once a day when the snapshot lands.
# player_code (the photo asset id) joins in from staging rather than widening
# the mart -- it's a display attribute, not a decision signal.
@st.cache_data(ttl=3600)
def load_latest_snapshot():
    conn = get_conn()
    df = conn.execute(
        """
        select d.*, p.player_code
        from gold.mart_transfer_decision d
        left join silver.stg_fpl_players p
            on d.load_date = p.load_date and d.player_id = p.player_id
        where d.load_date = (select max(load_date) from gold.mart_transfer_decision)
        order by d.transfer_score desc
        """
    ).df()
    conn.close()
    df["photo"] = df["player_code"].map(photo_url)
    df["verdict"] = df["recommendation"].map(VERDICT)
    return df


df = load_latest_snapshot()
st.caption(f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d} — {len(df)} players scored")

st.subheader("Top pick by position")
tiles = st.columns(4)
for tile, pos in zip(tiles, ["GKP", "DEF", "MID", "FWD"]):
    pool = df[df["position_short_name"] == pos]
    if pool.empty:
        continue
    pick = pool.iloc[0]  # df is already sorted by transfer_score desc
    with tile.container(border=True):
        face, facts = st.columns([1, 2], vertical_alignment="center")
        face.image(pick["photo"], width=56)
        facts.markdown(f"**{pick['web_name']}**")
        facts.caption(
            f"{pick['team_name']}  \nscore {pick['transfer_score']:.0f} · £{pick['price_m']}m"
        )

st.subheader("All players")
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
    photo_col, facts_col, chart_col = st.columns([1, 2, 3], vertical_alignment="center")
    photo_col.image(photo_url(player["player_code"], size="250x250"), width=150)
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
