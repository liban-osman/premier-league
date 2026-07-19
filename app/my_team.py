import pandas as pd
import requests
import streamlit as st
from db import get_conn
from ui import STATUS_COLORS, badge_url, photo_url, position_badge

st.title("My Team")
st.caption(
    "Enter your FPL team ID (from your Points page URL: "
    "fantasy.premierleague.com/entry/**12345**/event/1) to see your squad against "
    "today's signals -- weak links, suggested swaps, and who to captain."
)

VERDICT = {
    "transfer_in": "🟢 Transfer in",
    "hold": "🔵 Hold",
    "monitor": "🟡 Monitor",
    "drop": "🔴 Drop",
}


# Short TTL: unlike the daily snapshot marts, gameweek state and an individual
# manager's picks can change within a day (transfers, chip use).
@st.cache_data(ttl=900)
def load_current_gw() -> tuple[int, bool]:
    events = requests.get(
        "https://fantasy.premierleague.com/api/bootstrap-static/", timeout=15
    ).json()["events"]
    current = next((e for e in events if e["is_current"]), None)
    if current is None:
        current = max((e for e in events if e["finished"]), key=lambda e: e["id"])
    # "current" pointing at an already-finished gameweek with no next one
    # queued yet is exactly the between-seasons gap this project has hit
    # elsewhere (decision log #36) -- surfaced to the user, not hidden.
    is_offseason = current["finished"] and not any(e["is_next"] for e in events)
    return current["id"], is_offseason


@st.cache_data(ttl=300)
def load_squad(team_id: int, gw: int):
    entry = requests.get(f"https://fantasy.premierleague.com/api/entry/{team_id}/", timeout=15)
    entry.raise_for_status()
    picks = requests.get(
        f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/", timeout=15
    )
    picks.raise_for_status()
    return entry.json(), picks.json()


@st.cache_data(ttl=3600)
def load_signals():
    conn = get_conn()
    df = conn.execute(
        """
        select d.*, p.player_code, t.team_code
        from gold.mart_transfer_decision d
        left join silver.stg_fpl_players p
            on d.load_date = p.load_date and d.player_id = p.player_id
        left join silver.stg_fpl_teams t
            on d.load_date = t.load_date and d.team_id = t.team_id
        where d.load_date = (select max(load_date) from gold.mart_transfer_decision)
        """
    ).df()
    conn.close()
    df["photo"] = df["player_code"].map(photo_url)
    df["badge"] = df["team_code"].map(badge_url)
    df["verdict"] = df["recommendation"].map(VERDICT)
    return df


def suggest_replacement(signals: pd.DataFrame, squad_ids: list, weak: pd.Series, bank_m: float):
    budget = weak["price_m"] + bank_m
    candidates = signals[
        (~signals["player_id"].isin(squad_ids))
        & (signals["position_short_name"] == weak["position_short_name"])
        & (signals["price_m"] <= budget)
        & (signals["availability_risk"] != "high_risk")
    ].sort_values("transfer_score", ascending=False)
    return candidates.iloc[0] if not candidates.empty else None


gw, is_offseason = load_current_gw()
team_id = st.number_input("FPL Team ID", min_value=1, step=1, value=None, placeholder="e.g. 123456")
load_clicked = st.button("Load my team", type="primary")

if not load_clicked or not team_id:
    st.stop()

try:
    entry, picks = load_squad(int(team_id), gw)
except requests.HTTPError:
    st.error(
        f"Couldn't find team ID {int(team_id)} for gameweek {gw}. Double-check the ID "
        "from your FPL Points page URL."
    )
    st.stop()
except requests.RequestException:
    st.error("Couldn't reach the FPL API right now -- try again in a moment.")
    st.stop()

if is_offseason:
    st.info(
        f"Showing your final Gameweek {gw} squad -- the new season hasn't kicked off yet, "
        "so this is last season's team until gameweek 1 lands."
    )

signals = load_signals()
squad_ids = [p["element"] for p in picks["picks"]]
squad = pd.DataFrame(picks["picks"]).merge(
    signals, left_on="element", right_on="player_id", how="left"
)
squad["role"] = squad.apply(
    lambda r: "©️ Captain" if r["is_captain"] else ("Ⓥ Vice" if r["is_vice_captain"] else ""), axis=1
)
squad["squad_slot"] = squad["position"].apply(lambda p: "Starting XI" if p <= 11 else "Bench")

bank_m = picks["entry_history"]["bank"] / 10
value_m = picks["entry_history"]["value"] / 10

st.subheader(entry.get("name", "Your team"))
m1, m2, m3, m4 = st.columns(4)
m1.metric("Overall rank", f"{entry['summary_overall_rank']:,}")
m2.metric("Total points", entry["summary_overall_points"])
m3.metric("Squad value", f"£{value_m:.1f}m")
m4.metric("In the bank", f"£{bank_m:.1f}m")

unresolved = squad["player_id"].isna().sum()
if unresolved:
    st.caption(
        f"{unresolved} squad player(s) aren't in today's snapshot (likely no longer in "
        "the top flight) and are excluded from the signals below."
    )


# Same row-tint pattern as league_table.py's zone_tint: a translucent wash so
# it stays legible on both themes, icon + label (the verdict column itself)
# carries the same info, so the tint is never the only encoding.
def verdict_tint(row: pd.Series) -> list[str]:
    color = STATUS_COLORS.get(row["recommendation"])
    style = f"background-color: {color}26" if color else ""
    return [style] * len(row)


squad_display_cols = [
    "photo",
    "badge",
    "web_name",
    "team_name",
    "position_short_name",
    "role",
    "squad_slot",
    "price_m",
    "transfer_score",
    "verdict",
]
st.dataframe(
    # recommendation rides along (hidden via column_order below) so
    # verdict_tint can read it -- it isn't itself a display column.
    squad[[*squad_display_cols, "recommendation"]].style.apply(verdict_tint, axis=1),
    hide_index=True,
    column_order=squad_display_cols,
    column_config={
        "photo": st.column_config.ImageColumn("", width="small"),
        "badge": st.column_config.ImageColumn("", width="small"),
        "web_name": "Player",
        "team_name": "Team",
        "position_short_name": "Pos",
        "role": "Role",
        "squad_slot": "Slot",
        "price_m": st.column_config.NumberColumn("Price", format="£%.1fm"),
        "transfer_score": st.column_config.ProgressColumn(
            "Score", format="%.0f", min_value=0, max_value=100
        ),
        "verdict": "Verdict",
    },
)

st.divider()
st.subheader("👑 Captain suggestion")
starters = squad[(squad["squad_slot"] == "Starting XI") & squad["player_id"].notna()]
fit_starters = starters[starters["availability_risk"] != "high_risk"]
if fit_starters.empty:
    st.caption("No fit starters with a signal to suggest a captain from.")
else:
    best = fit_starters.sort_values("transfer_score", ascending=False).iloc[0]
    current_captain = starters[starters["is_captain"]]
    if not current_captain.empty and current_captain.iloc[0]["player_id"] == best["player_id"]:
        st.success(f"**{best['web_name']}** is already your captain, and the top score in your XI.")
    elif not current_captain.empty:
        st.warning(
            f"Your captain is **{current_captain.iloc[0]['web_name']}** "
            f"(score {current_captain.iloc[0]['transfer_score']:.0f}), but **{best['web_name']}** "
            f"(score {best['transfer_score']:.0f}) is your highest-scoring fit starter."
        )
    else:
        st.info(
            f"Highest-scoring fit starter: **{best['web_name']}** "
            f"(score {best['transfer_score']:.0f})."
        )

st.divider()
st.subheader("🔁 Weak links")
st.caption(
    "Squad players flagged drop or monitor today, each with the best same-position "
    "replacement your actual budget (their price + your bank) covers."
)
weak = squad[squad["recommendation"].isin(["drop", "monitor"]) & squad["player_id"].notna()]
if weak.empty:
    st.caption("No one in your squad is flagged drop/monitor today.")
else:
    for _, player in weak.iterrows():
        replacement = suggest_replacement(signals, squad_ids, player, bank_m)
        key = f"status-{player['recommendation']}-weaklink-{player['player_id']}"
        with st.container(border=True, key=key):
            out_col, arrow_col, in_col = st.columns([2, 0.4, 2], vertical_alignment="center")
            with out_col:
                pos = position_badge(player.get("position_short_name"))
                st.markdown(
                    f"**{player['web_name']}**{pos} — {player['verdict']}",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{player['team_name']} · score {player['transfer_score']:.0f} · "
                    f"£{player['price_m']}m"
                )
            arrow_col.markdown("→")
            with in_col:
                if replacement is not None:
                    pos = position_badge(replacement.get("position_short_name"))
                    st.markdown(f"**{replacement['web_name']}**{pos}", unsafe_allow_html=True)
                    st.caption(
                        f"{replacement['team_name']} · score {replacement['transfer_score']:.0f} · "
                        f"£{replacement['price_m']}m"
                    )
                else:
                    st.caption("No affordable same-position replacement found today.")
