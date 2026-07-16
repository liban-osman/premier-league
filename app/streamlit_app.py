import streamlit as st
from ui import inject_theme_css

st.set_page_config(page_title="FPL Data Platform", page_icon="⚽", layout="wide")
inject_theme_css()

pg = st.navigation(
    [
        st.Page("home.py", title="Home", icon="⚽", default=True),
        st.Page("transfer_decisions.py", title="Transfer Decisions", icon="🔁"),
        st.Page("my_team.py", title="My Team", icon="🧑‍💼"),
        st.Page("live.py", title="Live", icon="🔴"),
        st.Page("leaderboard.py", title="Leaderboard", icon="📋"),
        st.Page("league_table.py", title="League Table", icon="🏆"),
        st.Page("player_stats.py", title="Player Stats", icon="📊"),
        st.Page("xg_analytics.py", title="xG Analytics", icon="📈"),
    ]
)
pg.run()
