import streamlit as st
import pandas as pd
from mplsoccer import Pitch
import matplotlib.pyplot as plt
from snowflake_conn import get_conn  # your existing helper

st.title("Passes Visualization")

# streamlit run c:/Users/liban/Documents/premier-league/app/streamlit_app.py


# Pull events data for a specific game_id
game_id = 1821049

conn = get_conn()
query = f"""
SELECT *
FROM gold.fact_pass_events
WHERE game_id = {game_id}
"""
df_events = pd.read_sql(query, conn)
conn.close()

st.write(f"Showing passes for game_id {game_id}")

# Plotting function
def passes_plot(df_passes):
    #df_passes = df_passes[df_passes["TYPE"] == "Pass"]
    pitch = Pitch(pitch_type='opta', pitch_color='#22312b', line_color='#c7d5cc')
    fig, ax = pitch.draw(figsize=(16, 11), constrained_layout=False, tight_layout=True)
    fig.set_facecolor('#22312b')

    df_suc = df_passes[df_passes["OUTCOME_TYPE"] == "Successful"]
    pitch.lines(df_suc["X"], df_suc.Y, df_suc.END_X, df_suc.END_Y,
                lw=5, transparent=True, comet=True, color='#ad993c', ax=ax)

    df_unsuc = df_passes[df_passes["OUTCOME_TYPE"] == "Unsuccessful"]
    pitch.lines(df_unsuc.X, df_unsuc.Y, df_unsuc.END_X, df_unsuc.END_Y,
                lw=5, transparent=True, comet=True, color='#ba4f45', ax=ax)

    ax.legend(facecolor='#22312b', edgecolor='None', fontsize=12, loc='upper left', handlelength=4)
    st.pyplot(fig)

passes_plot(df_events)
