import pandas as pd
import streamlit as st
from db import get_conn
from ui import badge_url, photo_url

st.title("⚽ FPL Data Platform")
st.markdown(
    "The official FPL API only ever shows *today's* prices, form, and ownership -- it "
    "throws history away. This platform snapshots it daily and adds an independent xG "
    "model (Understat) on top, to answer the question the API can't: who's actually "
    "rising, worth transferring in, or worth dropping. Start with a highlight below, or "
    "jump straight to a page."
)

st.divider()
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
            where season = (select max(season) from silver.stg_understat_players)
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
        st.image(photo_url(top_pick["player_code"]), width=64)
    st.markdown(f"**🔁 {top_pick['web_name']}**")
    st.caption(
        f"{top_pick['team_name']} · score {top_pick['transfer_score']:.0f}/100 · "
        f"£{top_pick['price_m']}m — today's top transfer pick"
    )
    st.page_link("transfer_decisions.py", label="Transfer Decisions", icon="🔁")

with c2.container(border=True, key="highlight-1"):
    delta = xg_story["delta"]
    verb = "outscoring" if delta >= 0 else "underperforming"
    xg_season = int(xg_story["season"])
    st.markdown(f"**⚡ {xg_story['player_name']}**")
    st.caption(
        f"{xg_story['team_name']} · {verb} their chances — {int(xg_story['goals'])} goals "
        f"from {xg_story['xg']:.1f} xG ({delta:+.1f}) · {xg_season}/{str(xg_season + 1)[2:]}"
    )
    st.page_link("xg_analytics.py", label="xG Analytics", icon="📈")

with c3.container(border=True, key="highlight-2"):
    if pd.notna(best_defence["team_code"]):
        st.image(badge_url(best_defence["team_code"]), width=40)
    st.markdown(f"**🧤 {best_defence['team_name']}**")
    # A full 38-game record means this is last season's final tally, not a
    # live in-progress one -- same reasoning as league_table.py's own check.
    record_note = " (final, last season)" if best_defence["played"] >= 38 else ""
    st.caption(
        f"Defensive outlook {best_defence['defensive_outlook_score']:.0f}/100 — "
        f"best clean-sheet bet{record_note}"
    )
    st.page_link("transfer_decisions.py", label="Clean Sheet Picks", icon="🔁")

with c4.container(border=True, key="highlight-3"):
    if pd.notna(leader["team_code"]):
        st.image(badge_url(leader["team_code"]), width=40)
    st.markdown(f"**🏆 {leader['team_name']}**")
    if leader["played"] >= 38:
        season = int(leader["season"])
        detail = f"{leader['points']} pts, final {season}/{str(season + 1)[2:]} table"
    else:
        detail = f"{leader['points']} pts from {leader['played']} played"
    st.caption(f"{detail} — league leader")
    st.page_link("league_table.py", label="League Table", icon="🏆")

st.divider()
st.subheader("Where to go")
nav_cols = st.columns(7)
with nav_cols[0]:
    st.page_link("transfer_decisions.py", label="Transfer Decisions", icon="🔁")
    st.caption("Movers, budget picks, differentials, clean sheet picks, captaincy.")
with nav_cols[1]:
    st.page_link("my_team.py", label="My Team", icon="🧑‍💼")
    st.caption("Your actual squad against today's signals — weak links and swaps.")
with nav_cols[2]:
    st.page_link("live.py", label="Live", icon="🔴")
    st.caption("This gameweek's live scores — goals, bonus, and points as they land.")
with nav_cols[3]:
    st.page_link("leaderboard.py", label="Leaderboard", icon="📋")
    st.caption("Your private mini-league standings.")
with nav_cols[4]:
    st.page_link("league_table.py", label="League Table", icon="🏆")
    st.caption("Standings, form guide, qualification/relegation zones.")
with nav_cols[5]:
    st.page_link("player_stats.py", label="Player Stats", icon="📊")
    st.caption("Top scorers/assists, goals vs xG.")
with nav_cols[6]:
    st.page_link("xg_analytics.py", label="xG Analytics", icon="📈")
    st.caption("Team and player xG models, over/underperformance.")
