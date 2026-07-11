import altair as alt
import pandas as pd
import streamlit as st
from db import get_conn

st.title("xG Analytics")
st.caption(
    "Team and player expected-goals analytics. xG model: [Understat](https://understat.com) — "
    "season aggregates refreshed weekly."
)

# Hues from the validated reference palette (dataviz skill), matching the
# player stats page: blue primary, aqua secondary, muted ink for reference lines.
LIGHT, DARK = ("#2a78d6", "#1baf7a"), ("#3987e5", "#199e70")
MUTED_INK = "#898781"


def series_hues() -> tuple[str, str]:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except AttributeError:
        return LIGHT


# Reads silver directly: season-level sums/averages of the cleaned staging
# layer, no business logic -- the same pure-projection policy as player stats.
@st.cache_data(ttl=3600)
def load_seasons() -> list[int]:
    conn = get_conn()
    seasons = [
        row[0]
        for row in conn.execute(
            "select distinct season from silver.stg_understat_team_matches order by season desc"
        ).fetchall()
    ]
    conn.close()
    return seasons


@st.cache_data(ttl=3600)
def load_team_table(season: int) -> pd.DataFrame:
    conn = get_conn()
    df = conn.execute(
        """
        select
            team_name,
            count(*) as played,
            cast(sum(points) as integer) as points,
            round(sum(expected_points), 1) as expected_points,
            round(sum(points) - sum(expected_points), 1) as points_minus_xpts,
            round(sum(xg), 1) as xg,
            round(sum(xga), 1) as xga,
            round(sum(npxgd), 1) as npxgd,
            round(avg(ppda), 1) as ppda
        from silver.stg_understat_team_matches
        where season = ?
        group by team_name
        order by points desc, npxgd desc
        """,
        [season],
    ).df()
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_players(season: int) -> pd.DataFrame:
    conn = get_conn()
    df = conn.execute(
        """
        select
            player_name, team_name, position, games, minutes,
            goals, xg, non_penalty_goals, npxg, assists, xa, shots, key_passes
        from silver.stg_understat_players
        where season = ?
        """,
        [season],
    ).df()
    conn.close()
    return df


seasons = load_seasons()
season = st.selectbox("Season", seasons, format_func=lambda s: f"{s}/{str(s + 1)[2:]}")
teams = load_team_table(season)
players = load_players(season)
blue, aqua = series_hues()

st.subheader("Team xG table")
st.caption(
    "xPTS is the points total the xG model expects from each match's chances; "
    "Pts − xPTS above zero means results ran hotter than performances."
)
st.dataframe(
    teams,
    hide_index=True,
    column_config={
        "team_name": "Team",
        "played": "P",
        "points": "Pts",
        "expected_points": st.column_config.NumberColumn("xPTS", format="%.1f"),
        "points_minus_xpts": st.column_config.NumberColumn("Pts − xPTS", format="%+.1f"),
        "xg": st.column_config.NumberColumn("xG", format="%.1f"),
        "xga": st.column_config.NumberColumn("xGA", format="%.1f"),
        "npxgd": st.column_config.NumberColumn("npxGD", format="%+.1f"),
        "ppda": st.column_config.NumberColumn(
            "PPDA", format="%.1f", help="Opponent passes per defensive action — lower = more press"
        ),
    },
)

st.subheader("Points vs expected points")
axis_min = float(min(teams["points"].min(), teams["expected_points"].min())) - 4
axis_max = float(max(teams["points"].max(), teams["expected_points"].max())) + 4
diagonal = (
    alt.Chart(pd.DataFrame({"v": [axis_min, axis_max]}))
    .mark_line(strokeDash=[4, 4], color=MUTED_INK)
    .encode(x="v:Q", y="v:Q")
)
points_chart = (
    alt.Chart(teams)
    .mark_circle(size=90, color=blue, opacity=0.8)
    .encode(
        x=alt.X(
            "expected_points:Q",
            title="Expected points (xPTS)",
            scale=alt.Scale(domain=[axis_min, axis_max]),
        ),
        y=alt.Y("points:Q", title="Points", scale=alt.Scale(domain=[axis_min, axis_max])),
        tooltip=[
            alt.Tooltip("team_name", title="Team"),
            alt.Tooltip("points", title="Pts"),
            alt.Tooltip("expected_points", title="xPTS"),
            alt.Tooltip("points_minus_xpts", title="Pts − xPTS"),
        ],
    )
)
# Selective direct labels: only the five biggest over/under-achievers.
outliers = teams.reindex(teams["points_minus_xpts"].abs().nlargest(5).index)
team_labels = (
    alt.Chart(outliers)
    .mark_text(align="left", dx=8, dy=-5)
    .encode(x="expected_points:Q", y="points:Q", text="team_name:N")
)
st.altair_chart((diagonal + points_chart + team_labels).properties(height=420), width="stretch")
st.caption("Above the dashed line: winning more points than chance quality earns.")

st.subheader("Finishing: goals minus xG")
min_minutes = st.slider("Minimum minutes played", 0, int(players["minutes"].max()), 900, step=90)
finishers = players[players["minutes"] >= min_minutes].copy()
finishers["finishing_delta"] = (finishers["goals"] - finishers["xg"]).round(1)
extremes = pd.concat(
    [finishers.nlargest(8, "finishing_delta"), finishers.nsmallest(8, "finishing_delta")]
).sort_values("finishing_delta", ascending=False)

base = alt.Chart(extremes).encode(
    y=alt.Y("player_name:N", sort=None, title=None),
    x=alt.X("finishing_delta:Q", title="Goals − xG"),
    tooltip=[
        alt.Tooltip("player_name", title="Player"),
        alt.Tooltip("team_name", title="Team"),
        alt.Tooltip("goals", title="Goals"),
        alt.Tooltip("xg", title="xG", format=".1f"),
    ],
)
bars = base.mark_bar(cornerRadius=4).encode(
    color=alt.condition(alt.datum.finishing_delta >= 0, alt.value(blue), alt.value(aqua)),
)
over_labels = (
    base.mark_text(align="left", dx=4)
    .encode(text=alt.Text("finishing_delta:Q", format="+.1f"))
    .transform_filter(alt.datum.finishing_delta >= 0)
)
under_labels = (
    base.mark_text(align="right", dx=-4)
    .encode(text=alt.Text("finishing_delta:Q", format="+.1f"))
    .transform_filter(alt.datum.finishing_delta < 0)
)
st.altair_chart((bars + over_labels + under_labels).properties(height=440), width="stretch")
st.caption("Clinical finishers up top; the biggest chance-wasters at the bottom.")

with st.expander("Full player table"):
    st.dataframe(finishers.drop(columns=["finishing_delta"]), hide_index=True)
