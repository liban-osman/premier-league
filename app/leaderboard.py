import pandas as pd
import requests
import streamlit as st

st.title("Leaderboard")
st.caption(
    "Enter your FPL team ID (from your Points page URL: "
    "fantasy.premierleague.com/entry/**12345**/event/1) to see your mini-league standings."
)


@st.cache_data(ttl=900)
def load_entry(team_id: int) -> dict:
    r = requests.get(f"https://fantasy.premierleague.com/api/entry/{team_id}/", timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def load_standings(league_id: int) -> dict:
    r = requests.get(
        f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/",
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


team_id = st.number_input("FPL Team ID", min_value=1, step=1, value=None, placeholder="e.g. 123456")
load_clicked = st.button("Load my leagues", type="primary")

if not load_clicked or not team_id:
    st.stop()

try:
    entry = load_entry(int(team_id))
except requests.HTTPError:
    st.error(
        f"Couldn't find team ID {int(team_id)}. Double-check the ID from your FPL Points page URL."
    )
    st.stop()
except requests.RequestException:
    st.error("Couldn't reach the FPL API right now -- try again in a moment.")
    st.stop()

# league_type "x" = a private classic league someone actually created (invite
# code); "s" = an FPL system league everyone's auto-joined (Overall, country,
# club-support, "Gameweek 1") -- real, but too large and not what "mini-league"
# means to a manager, so they're excluded rather than swamping the picker.
private_leagues = [ld for ld in entry["leagues"]["classic"] if ld["league_type"] == "x"]

if not private_leagues:
    st.info(
        "No private mini-leagues found for this team -- only the automatic FPL system "
        "leagues (Overall, country, etc.), which aren't shown here since they're too "
        "large to be a meaningful table."
    )
    st.stop()

league_names = {ld["id"]: ld["name"] for ld in private_leagues}
selected_id = st.selectbox("Mini-league", list(league_names), format_func=lambda i: league_names[i])

try:
    standings = load_standings(selected_id)
except requests.RequestException:
    st.error("Couldn't reach the FPL API right now -- try again in a moment.")
    st.stop()

results = pd.DataFrame(standings["standings"]["results"])
if results.empty:
    st.caption("No standings available for this league yet.")
else:
    results["you"] = results["entry"] == int(team_id)

    # A 50-row table hides your own position by default -- same translucent
    # row-wash technique as league_table.py's zone_tint, but here the "you"
    # checkbox column is the icon+label pairing rather than a separate column.
    def you_tint(row: pd.Series) -> list[str]:
        style = "background-color: #9085e926" if row["you"] else ""
        return [style] * len(row)

    st.dataframe(
        results[["rank", "entry_name", "player_name", "total", "you"]].style.apply(
            you_tint, axis=1
        ),
        hide_index=True,
        column_config={
            "rank": "#",
            "entry_name": "Team",
            "player_name": "Manager",
            "total": "Points",
            "you": st.column_config.CheckboxColumn("You", disabled=True),
        },
    )
    if standings["standings"]["has_next"]:
        st.caption(f"Showing the top {len(results)} — this league has more entries.")
