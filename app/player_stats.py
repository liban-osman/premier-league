import altair as alt
import pandas as pd
import streamlit as st
from db import get_conn
from ui import MUTED_INK, badge_url, photo_url, series_hues, text_halo, text_ink

st.title("Player Stats — season so far")


# Reads silver directly: these are pure projections of the cleaned staging
# layer (no business logic), which is what the marts are reserved for.
@st.cache_data(ttl=3600)
def load_players():
    conn = get_conn()
    df = conn.execute(
        """
        select
            p.load_date, p.web_name, p.player_code, t.team_name, t.team_code,
            pos.position_short_name, p.season,
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
    df["photo"] = df["player_code"].map(photo_url)
    # The badge rides alongside the photo everywhere a photo appears: the PL's
    # official headshot CDN can lag a real transfer by months (kit stays the
    # old club's), but the badge is keyed on the club itself so it's never stale.
    df["badge"] = df["team_code"].map(badge_url)
    return df


def leaderboard(container, df: pd.DataFrame, value_col: str, label: str) -> None:
    top = df.nlargest(10, value_col)[["photo", "badge", "web_name", "team_name", value_col]]
    container.dataframe(
        top,
        hide_index=True,
        column_config={
            "photo": st.column_config.ImageColumn("", width="small"),
            "badge": st.column_config.ImageColumn("", width="small"),
            "web_name": "Player",
            "team_name": "Team",
            value_col: st.column_config.ProgressColumn(
                label, format="%d", min_value=0, max_value=max(int(top[value_col].max()), 1)
            ),
        },
    )


def halo_labels(points: pd.DataFrame, dy: int, halo: str, ink: str) -> list[alt.Chart]:
    """A label pair per point: a surface-colored stroke underneath, ink on top."""
    enc = {"x": "expected_goals:Q", "y": "goals_scored:Q", "text": "web_name:N"}
    under = (
        alt.Chart(points)
        .mark_text(align="left", dx=8, dy=dy, stroke=halo, strokeWidth=4)
        .encode(**enc)
    )
    over = alt.Chart(points).mark_text(align="left", dx=8, dy=dy, color=ink).encode(**enc)
    return [under, over]


df = load_players()
blue, aqua = series_hues()

season = int(df["season"].iloc[0])
st.caption(
    f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d} — "
    f"{season}/{str(season + 1)[2:]} season totals from FPL"
)

left, right = st.columns(2)
left.subheader("Top scorers")
leaderboard(left, df, "goals_scored", "Goals")
right.subheader("Top assists")
leaderboard(right, df, "assists", "Assists")

st.subheader("Goals vs expected goals (xG)")
controls = st.columns([1.4, 2, 2.6], vertical_alignment="bottom")
positions = controls[0].pills("Position", ["DEF", "MID", "FWD"], selection_mode="multi")
min_minutes = controls[1].slider(
    "Minimum minutes played", 0, int(df["minutes"].max()), 900, step=90
)

shooters = df[(df["minutes"] >= min_minutes) & (df["expected_goals"] > 0)].copy()
if positions:
    shooters = shooters[shooters["position_short_name"].isin(positions)]
shooters["xg_delta"] = (shooters["goals_scored"] - shooters["expected_goals"]).round(2)

# Labels are opt-in and haloed instead of stamped on the five busiest points --
# the old fixed labels collided into an unreadable clump around the diagonal.
default_labels = shooters.reindex(shooters["xg_delta"].abs().nlargest(5).index)["web_name"].tolist()
labelled_names = controls[2].multiselect(
    "Label players",
    sorted(df.loc[df["expected_goals"] > 0, "web_name"].unique().tolist()),
    default=default_labels,
)
labelled = shooters[shooters["web_name"].isin(labelled_names)]

axis_max = float(max(shooters["expected_goals"].max(), shooters["goals_scored"].max())) + 1
diagonal = (
    alt.Chart(pd.DataFrame({"v": [0, axis_max]}))
    .mark_line(strokeDash=[4, 4], color=MUTED_INK)
    .encode(x="v:Q", y="v:Q")
)
pick = alt.selection_point(name="point_sel", fields=["web_name"], on="click", empty=False)
points = (
    alt.Chart(shooters)
    .mark_circle(size=70, color=blue, opacity=0.6)
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
    .add_params(pick)
)
highlight = (
    alt.Chart(labelled)
    .mark_circle(size=130, color=aqua, opacity=0.95)
    .encode(x="expected_goals:Q", y="goals_scored:Q")
)
# Over-performers sit above the diagonal, so their labels go up and away from
# it; under-performers get labels pushed down. Halo + ink keeps both readable.
halo, ink = text_halo(), text_ink()
chart = alt.layer(
    diagonal,
    points,
    highlight,
    *halo_labels(labelled[labelled["xg_delta"] >= 0], dy=-10, halo=halo, ink=ink),
    *halo_labels(labelled[labelled["xg_delta"] < 0], dy=14, halo=halo, ink=ink),
).properties(height=460)
event = st.altair_chart(chart, width="stretch", on_select="rerun", key="xg_scatter")
st.caption(
    "Above the dashed line: scoring more than chance quality suggests. Below: "
    "underperforming their chances. Click any point for the player's card; add "
    "names to *Label players* to pin more labels."
)

picked = event.selection.point_sel if event.selection else []
if picked:
    hits = df[df["web_name"] == picked[0]["web_name"]]
    if not hits.empty:
        p = hits.iloc[0]
        with st.container(border=True):
            img_col, badge_col, info_col = st.columns([1, 0.4, 5], vertical_alignment="center")
            img_col.image(photo_url(p["player_code"], size="250x250"), width=110)
            if pd.notna(p["badge"]):
                badge_col.image(p["badge"], width=32)
            info_col.markdown(
                f"**{p['web_name']}** — {p['team_name']} · {p['position_short_name']} · "
                f"{int(p['minutes'])} minutes"
            )
            m = info_col.columns(5)
            m[0].metric("Goals", int(p["goals_scored"]))
            m[1].metric("xG", f"{p['expected_goals']:.1f}")
            m[2].metric("Assists", int(p["assists"]))
            m[3].metric("xA", f"{p['expected_assists']:.1f}")
            m[4].metric("FPL points", int(p["total_points"]))

with st.expander("Full table"):
    st.dataframe(
        df[
            [
                "photo",
                "badge",
                "web_name",
                "team_name",
                "position_short_name",
                "minutes",
                "goals_scored",
                "expected_goals",
                "assists",
                "expected_assists",
                "clean_sheets",
                "total_points",
            ]
        ].sort_values("total_points", ascending=False),
        hide_index=True,
        column_config={
            "photo": st.column_config.ImageColumn("", width="small"),
            "badge": st.column_config.ImageColumn("", width="small"),
            "web_name": "Player",
            "team_name": "Team",
            "position_short_name": "Pos",
            "minutes": "Mins",
            "goals_scored": "Goals",
            "expected_goals": st.column_config.NumberColumn("xG", format="%.1f"),
            "assists": "Assists",
            "expected_assists": st.column_config.NumberColumn("xA", format="%.1f"),
            "clean_sheets": "CS",
            "total_points": "Pts",
        },
    )
