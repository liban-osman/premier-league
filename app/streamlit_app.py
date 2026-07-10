import streamlit as st
from db import get_conn

st.set_page_config(page_title="FPL Transfer Decisions", layout="wide")

st.title("FPL Transfer Decisions")
st.caption(
    "Daily FPL snapshots → MotherDuck → dbt. transfer_score is a weighted percentile "
    "within position: 35% value (points per £m), 30% form, 20% fixture ease (next 5), "
    "15% transfer momentum. Availability is a hard gate, not a weighted input."
)


# Cached for an hour: the mart only changes once a day when the snapshot lands.
@st.cache_data(ttl=3600)
def load_latest_snapshot():
    conn = get_conn()
    df = conn.execute(
        """
        select * from gold.mart_transfer_decision
        where load_date = (select max(load_date) from gold.mart_transfer_decision)
        order by transfer_score desc
        """
    ).df()
    conn.close()
    return df


df = load_latest_snapshot()
st.caption(f"Snapshot: {df['load_date'].iloc[0]:%Y-%m-%d} — {len(df)} players")

left, right = st.columns(2)
positions = left.multiselect("Position", df["position_short_name"].dropna().unique().tolist())
recommendations = right.multiselect("Recommendation", df["recommendation"].unique().tolist())

filtered = df
if positions:
    filtered = filtered[filtered["position_short_name"].isin(positions)]
if recommendations:
    filtered = filtered[filtered["recommendation"].isin(recommendations)]

st.dataframe(
    filtered.drop(columns=["load_date", "team_id", "position_id"]),
    hide_index=True,
)
