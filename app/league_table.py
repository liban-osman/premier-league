import pandas as pd
import streamlit as st
from db import get_conn
from ui import badge_url

st.title("League Table")
st.caption(
    "Derived from fixture results in gold.mart_league_table, not FPL's own team "
    "records — FPL zeroes those in preseason snapshots. Tiebreaks: points, goal "
    "difference, goals scored."
)


@st.cache_data(ttl=3600)
def load_table():
    conn = get_conn()
    df = conn.execute(
        """
        select
            position, team_code, team_name, played, won, drawn, lost,
            goals_for, goals_against, goal_difference, points, form_last_5, load_date, season
        from gold.mart_league_table
        where load_date = (select max(load_date) from gold.mart_league_table)
        order by position
        """
    ).df()
    conn.close()
    df.insert(1, "badge", df["team_code"].map(badge_url))
    return df


df = load_table()
st.caption(f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d}")

# A 20-team PL season is always 38 games; every team hitting that means the
# table is a completed season's final standings, not a live in-progress one
# -- true regardless of what the "season" label says, since the FPL API
# itself doesn't roll that label over until the next season's fixtures exist.
if df["played"].min() >= 38:
    season = int(df["season"].iloc[0])
    st.info(
        f"Showing the final standings from the {season}/{str(season + 1)[2:]} season — "
        "the new season's fixtures haven't been played yet."
    )

leader = df.iloc[0]
attack = df.loc[df["goals_for"].idxmax()]
defence = df.loc[df["goals_against"].idxmin()]
cards = st.columns(3)
for col, (label, team, detail) in zip(
    cards,
    [
        ("Leader", leader, f"{int(leader['points'])} pts from {int(leader['played'])} games"),
        ("Best attack", attack, f"{int(attack['goals_for'])} goals scored"),
        ("Best defence", defence, f"{int(defence['goals_against'])} goals conceded"),
    ],
):
    with col.container(border=True):
        img, txt = st.columns([1, 4], vertical_alignment="center")
        img.image(team["badge"], width=44)
        txt.markdown(f"**{team['team_name']}**")
        txt.caption(f"{label} · {detail}")


# Row tints for the qualification/relegation zones; low alpha keeps them
# legible on both themes. The legend caption below carries the same info as
# icon + label, so the tint is never the only encoding.
def zone_tint(row: pd.Series) -> list[str]:
    if row["position"] <= 4:
        style = "background-color: rgba(42, 120, 214, 0.14)"
    elif row["position"] == 5:
        style = "background-color: rgba(27, 175, 122, 0.14)"
    elif row["position"] >= 18:
        style = "background-color: rgba(214, 69, 69, 0.14)"
    else:
        style = ""
    return [style] * len(row)


display = df.drop(columns=["load_date", "team_code"])
st.dataframe(
    display.style.apply(zone_tint, axis=1),
    hide_index=True,
    column_config={
        "position": st.column_config.NumberColumn("#"),
        "badge": st.column_config.ImageColumn(""),
        "team_name": "Team",
        "played": "P",
        "won": "W",
        "drawn": "D",
        "lost": "L",
        "goals_for": "GF",
        "goals_against": "GA",
        "goal_difference": "GD",
        "points": st.column_config.ProgressColumn(
            "Pts", format="%d", min_value=0, max_value=int(df["points"].max())
        ),
        "form_last_5": st.column_config.TextColumn(
            "Form", help="Last five results, most recent on the right"
        ),
    },
)
st.caption("🔵 Champions League (top 4) · 🟢 Europa League (5th) · 🔴 Relegation (bottom 3)")
