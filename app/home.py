import pandas as pd
import streamlit as st
from db import get_conn
from ui import badge_url, hero, photo_url

hero(
    "FPL Data Platform",
    "Know who to buy, who to sell and who to captain. Daily price and form tracking "
    "plus an xG model show who's really rising before the rest of your league notices.",
    kicker="Transfer picks · Live points · xG insights",
)
st.subheader("Today's highlights")


@st.cache_data(ttl=3600)
def load_top_pick():
    conn = get_conn()
    row = (
        conn.execute(
            """
            select d.web_name, d.team_name, d.transfer_score, d.price_m,
                   p.player_code, t.team_code
            from gold.mart_transfer_decision d
            left join silver.stg_fpl_players p
                on d.load_date = p.load_date and d.player_id = p.player_id
            left join silver.stg_fpl_teams t
                on d.load_date = t.load_date and d.team_id = t.team_id
            where d.load_date = (select max(load_date) from gold.mart_transfer_decision)
            order by d.transfer_score desc
            limit 1
            """
        )
        .df()
        .iloc[0]
    )
    conn.close()
    return row


@st.cache_data(ttl=3600)
def load_xg_story():
    conn = get_conn()
    row = (
        conn.execute(
            """
            select player_name, team_name, goals, xg, (goals - xg) as delta, season
            from silver.stg_understat_players
            where season = (
                select max(season) from silver.stg_understat_players where minutes >= 900
            )
              and minutes >= 900
            order by abs(goals - xg) desc
            limit 1
            """
        )
        .df()
        .iloc[0]
    )
    conn.close()
    return row


@st.cache_data(ttl=3600)
def load_best_defence():
    conn = get_conn()
    row = (
        conn.execute(
            """
            select d.team_name, d.defensive_outlook_score, d.played, t.team_code
            from gold.mart_team_defensive_outlook d
            left join silver.stg_fpl_teams t
                on d.load_date = t.load_date and d.team_id = t.team_id
            where d.load_date = (select max(load_date) from gold.mart_team_defensive_outlook)
            order by d.defensive_outlook_score desc
            limit 1
            """
        )
        .df()
        .iloc[0]
    )
    conn.close()
    return row


@st.cache_data(ttl=3600)
def load_league_leader():
    conn = get_conn()
    row = (
        conn.execute(
            """
            select team_name, points, played, team_code, season
            from gold.mart_league_table
            where load_date = (select max(load_date) from gold.mart_league_table)
              and position = 1
            """
        )
        .df()
        .iloc[0]
    )
    conn.close()
    return row


top_pick = load_top_pick()
xg_story = load_xg_story()
best_defence = load_best_defence()
leader = load_league_leader()

c1, c2, c3, c4 = st.columns(4)

with c1.container(border=True, key="highlight-0"):
    if pd.notna(top_pick["player_code"]):
        st.image(photo_url(top_pick["player_code"]), width=96)
    st.markdown('<div class="kicker">Top transfer pick</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="big-stat">{top_pick["web_name"]}</div>', unsafe_allow_html=True)
    st.caption(
        f"{top_pick['team_name']} · score {top_pick['transfer_score']:.0f}/100 · "
        f"£{top_pick['price_m']}m"
    )
    st.page_link("transfer_decisions.py", label="Transfer Decisions", icon="🔁")

with c2.container(border=True, key="highlight-1"):
    delta = xg_story["delta"]
    verb = "outscoring" if delta >= 0 else "underperforming"
    xg_season = int(xg_story["season"])
    st.markdown('<div class="kicker">xG story</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="big-stat">{xg_story["player_name"]}</div>', unsafe_allow_html=True)
    st.caption(
        f"{xg_story['team_name']} · {verb} their chances — {int(xg_story['goals'])} goals "
        f"from {xg_story['xg']:.1f} xG ({delta:+.1f}) · {xg_season}/{str(xg_season + 1)[2:]}"
    )
    st.page_link("xg_analytics.py", label="xG Analytics", icon="📈")

with c3.container(border=True, key="highlight-2"):
    if pd.notna(best_defence["team_code"]):
        st.image(badge_url(best_defence["team_code"]), width=64)
    st.markdown('<div class="kicker">Best clean-sheet bet</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="big-stat">{best_defence["team_name"]}</div>', unsafe_allow_html=True)
    # A full 38-game record means this is last season's final tally, not a
    # live in-progress one -- same reasoning as league_table.py's own check.
    record_note = " (final, last season)" if best_defence["played"] >= 38 else ""
    st.caption(f"Defensive outlook {best_defence['defensive_outlook_score']:.0f}/100{record_note}")
    st.page_link("transfer_decisions.py", label="Clean Sheet Picks", icon="🔁")

with c4.container(border=True, key="highlight-3"):
    if pd.notna(leader["team_code"]):
        st.image(badge_url(leader["team_code"]), width=64)
    st.markdown('<div class="kicker">League leader</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="big-stat">{leader["team_name"]}</div>', unsafe_allow_html=True)
    if leader["played"] >= 38:
        season = int(leader["season"])
        detail = f"{leader['points']} pts, final {season}/{str(season + 1)[2:]} table"
    else:
        detail = f"{leader['points']} pts from {leader['played']} played"
    st.caption(detail)
    st.page_link("league_table.py", label="League Table", icon="🏆")

st.subheader("Explore")
NAV = [
    (
        "transfer_decisions.py",
        "Transfer Decisions",
        "🔁",
        "Movers, budget picks, differentials, clean sheets, captaincy.",
    ),
    ("my_team.py", "My Team", "🧑‍💼", "Your squad against today's signals — weak links and swaps."),
    ("live.py", "Live", "🔴", "This gameweek's live scores — goals, bonus, points as they land."),
    ("leaderboard.py", "Leaderboard", "📋", "Your private mini-league standings."),
    (
        "league_table.py",
        "League Table",
        "🏆",
        "Standings, form guide, qualification/relegation zones.",
    ),
    ("player_stats.py", "Player Stats", "📊", "Top scorers/assists, goals vs xG."),
    ("xg_analytics.py", "xG Analytics", "📈", "Team and player xG models, over/underperformance."),
]
for row_start in range(0, len(NAV), 4):
    cols = st.columns(4)
    for col, (page, label, icon, blurb) in zip(cols, NAV[row_start : row_start + 4]):
        with col.container(border=True, key=f"nav-{page[:-3]}"):
            st.page_link(page, label=label, icon=icon)
            st.caption(blurb)
