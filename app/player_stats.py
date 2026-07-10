import altair as alt
import pandas as pd
import streamlit as st
from db import get_conn

st.title("Player Stats — season so far")

# Hues from the validated reference palette (dataviz skill): blue for the
# primary sequential context, aqua for the second, each with a dark-surface
# step. Muted ink for reference lines.
LIGHT, DARK = ("#2a78d6", "#1baf7a"), ("#3987e5", "#199e70")
MUTED_INK = "#898781"


def series_hues() -> tuple[str, str]:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except AttributeError:
        return LIGHT


# Reads silver directly: these are pure projections of the cleaned staging
# layer (no business logic), which is what the marts are reserved for.
@st.cache_data(ttl=3600)
def load_players():
    conn = get_conn()
    df = conn.execute(
        """
        select
            p.load_date, p.web_name, t.team_name, pos.position_short_name,
            p.goals_scored, p.assists, p.expected_goals, p.expected_assists,
            p.minutes, p.total_points, p.clean_sheets
        from silver.stg_fpl_players p
        left join silver.stg_fpl_teams t
            on p.load_date = t.load_date and p.team_id = t.team_id
        left join silver.stg_fpl_positions pos on p.position_id = pos.position_id
        where p.load_date = (select max(load_date) from silver.stg_fpl_players)
        """
    ).df()
    conn.close()
    return df


def leaderboard(df: pd.DataFrame, value_col: str, label: str, hue: str) -> alt.Chart:
    top = df.nlargest(10, value_col)
    base = alt.Chart(top).encode(
        y=alt.Y("web_name:N", sort="-x", title=None),
        x=alt.X(f"{value_col}:Q", axis=None),
        tooltip=[
            alt.Tooltip("web_name", title="Player"),
            alt.Tooltip("team_name", title="Team"),
            alt.Tooltip(value_col, title=label),
        ],
    )
    bars = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=hue)
    labels = base.mark_text(align="left", dx=4).encode(text=f"{value_col}:Q")
    return (bars + labels).properties(height=300)


df = load_players()
blue, aqua = series_hues()

st.caption(f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d} — 2025/26 season totals from FPL")

left, right = st.columns(2)
left.subheader("Top scorers")
left.altair_chart(leaderboard(df, "goals_scored", "Goals", blue), width="stretch")
right.subheader("Top assists")
right.altair_chart(leaderboard(df, "assists", "Assists", aqua), width="stretch")

st.subheader("Goals vs expected goals (xG)")
min_minutes = st.slider("Minimum minutes played", 0, int(df["minutes"].max()), 900, step=90)
shooters = df[(df["minutes"] >= min_minutes) & (df["expected_goals"] > 0)].copy()
shooters["xg_delta"] = shooters["goals_scored"] - shooters["expected_goals"]

axis_max = float(max(shooters["expected_goals"].max(), shooters["goals_scored"].max())) + 1
diagonal = (
    alt.Chart(pd.DataFrame({"v": [0, axis_max]}))
    .mark_line(strokeDash=[4, 4], color=MUTED_INK)
    .encode(x="v:Q", y="v:Q")
)
points = (
    alt.Chart(shooters)
    .mark_circle(size=70, color=blue, opacity=0.7)
    .encode(
        x=alt.X("expected_goals:Q", title="Expected goals (xG)"),
        y=alt.Y("goals_scored:Q", title="Goals"),
        tooltip=[
            alt.Tooltip("web_name", title="Player"),
            alt.Tooltip("team_name", title="Team"),
            alt.Tooltip("goals_scored", title="Goals"),
            alt.Tooltip("expected_goals", title="xG"),
        ],
    )
)
# Selective direct labels: only the five biggest over/under-performers.
outliers = shooters.reindex(shooters["xg_delta"].abs().nlargest(5).index)
labels = (
    alt.Chart(outliers)
    .mark_text(align="left", dx=7, dy=-5)
    .encode(x="expected_goals:Q", y="goals_scored:Q", text="web_name:N")
)
st.altair_chart((diagonal + points + labels).properties(height=420), width="stretch")
st.caption(
    "Above the dashed line: scoring more than chance quality suggests. "
    "Below: underperforming their chances."
)

with st.expander("Full table"):
    st.dataframe(df.drop(columns=["load_date"]), hide_index=True)
