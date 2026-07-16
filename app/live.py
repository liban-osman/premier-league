import pandas as pd
import requests
import streamlit as st
from db import get_conn
from ui import POSITION_COLORS, badge_url, photo_url

st.title("Live")
st.caption(
    "Live gameweek scores straight from FPL's live API -- goals, assists, bonus, and "
    "total points as they're provisionally awarded."
)


# Short TTL: live scores change constantly mid-gameweek, unlike the daily snapshot marts.
@st.cache_data(ttl=120)
def load_gw_context() -> tuple[dict, bool]:
    events = requests.get(
        "https://fantasy.premierleague.com/api/bootstrap-static/", timeout=15
    ).json()["events"]
    current = next((e for e in events if e["is_current"]), None)
    if current is None:
        current = max((e for e in events if e["finished"]), key=lambda e: e["id"])
    # Same off-season detection as My Team (decision log #42): FPL leaves the
    # last event of a finished season flagged is_current with no is_next
    # queued, rather than clearing it, right up until the new season's
    # fixtures are published.
    is_offseason = current["finished"] and not any(e["is_next"] for e in events)
    return current, is_offseason


@st.cache_data(ttl=120)
def load_live_stats(gw: int) -> pd.DataFrame:
    data = requests.get(
        f"https://fantasy.premierleague.com/api/event/{gw}/live/", timeout=15
    ).json()
    rows = [{"player_id": el["id"], **el["stats"]} for el in data["elements"]]
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600)
def load_player_meta() -> pd.DataFrame:
    conn = get_conn()
    df = conn.execute(
        """
        select p.player_id, p.web_name, p.player_code, t.team_name, t.team_code,
               pos.position_short_name
        from silver.stg_fpl_players p
        left join silver.stg_fpl_teams t
            on p.load_date = t.load_date and p.team_id = t.team_id
        left join silver.stg_fpl_positions pos on p.position_id = pos.position_id
        where p.load_date = (select max(load_date) from silver.stg_fpl_players)
        """
    ).df()
    conn.close()
    df["photo"] = df["player_code"].map(photo_url)
    df["badge"] = df["team_code"].map(badge_url)
    return df


gw, is_offseason = load_gw_context()

if is_offseason:
    st.info(
        f"Showing the final live stats from Gameweek {gw['id']} -- the new season "
        "hasn't kicked off yet."
    )
elif gw["finished"]:
    st.info(f"Gameweek {gw['id']} is finished -- showing its final live stats.")
else:
    st.success(f"Gameweek {gw['id']} is live.")

live = load_live_stats(gw["id"])
meta = load_player_meta()
merged = live.merge(meta, on="player_id", how="left")
played = merged[merged["minutes"] > 0]

if gw.get("average_entry_score") or gw.get("highest_score"):
    m1, m2 = st.columns(2)
    if gw.get("average_entry_score"):
        m1.metric("Average score", gw["average_entry_score"])
    if gw.get("highest_score"):
        m2.metric("Highest score", gw["highest_score"])

st.subheader("Top performers")
if played.empty:
    st.caption(f"No minutes played yet for Gameweek {gw['id']}.")
else:
    top = played.sort_values("total_points", ascending=False).head(15)

    # Same translucent row-wash technique as league_table.py's zone_tint --
    # the Pos column text is the real encoding, this just makes position
    # scannable at a glance across a 15-row table.
    def position_tint(row: pd.Series) -> list[str]:
        color = POSITION_COLORS.get(row["position_short_name"])
        style = f"background-color: {color}1f" if color else ""
        return [style] * len(row)

    st.dataframe(
        top[
            [
                "photo",
                "badge",
                "web_name",
                "team_name",
                "position_short_name",
                "minutes",
                "goals_scored",
                "assists",
                "clean_sheets",
                "bonus",
                "total_points",
            ]
        ].style.apply(position_tint, axis=1),
        hide_index=True,
        column_config={
            "photo": st.column_config.ImageColumn("", width="small"),
            "badge": st.column_config.ImageColumn("", width="small"),
            "web_name": "Player",
            "team_name": "Team",
            "position_short_name": "Pos",
            "minutes": "Mins",
            "goals_scored": "Goals",
            "assists": "Assists",
            "clean_sheets": "CS",
            "bonus": "Bonus",
            "total_points": st.column_config.ProgressColumn(
                "Pts", format="%d", min_value=0, max_value=int(top["total_points"].max())
            ),
        },
    )
