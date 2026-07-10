import streamlit as st
from db import get_conn

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
            position, team_name, played, won, drawn, lost,
            goals_for, goals_against, goal_difference, points, load_date
        from gold.mart_league_table
        where load_date = (select max(load_date) from gold.mart_league_table)
        order by position
        """
    ).df()
    conn.close()
    return df


df = load_table()
st.caption(f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d}")

st.dataframe(
    df.drop(columns=["load_date"]),
    hide_index=True,
    column_config={
        "position": st.column_config.NumberColumn("#"),
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
    },
)
