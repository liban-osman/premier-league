import streamlit as st

st.set_page_config(page_title="FPL Data Platform", page_icon="⚽", layout="wide")

pg = st.navigation(
    [
        st.Page("home.py", title="Home", icon="⚽", default=True),
        st.Page("transfer_decisions.py", title="Transfer Decisions", icon="🔁"),
        st.Page("my_team.py", title="My Team", icon="🧑‍💼"),
        st.Page("live.py", title="Live", icon="🔴"),
        st.Page("league_table.py", title="League Table", icon="🏆"),
        st.Page("player_stats.py", title="Player Stats", icon="📊"),
        st.Page("xg_analytics.py", title="xG Analytics", icon="📈"),
    ]
)
pg.run()
