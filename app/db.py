import os

import duckdb
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    # Locally MOTHERDUCK_TOKEN comes from .env; Streamlit Community Cloud has
    # no .env and exposes secrets only via st.secrets, so bridge it into the
    # environment where the duckdb md: extension looks for it.
    if "MOTHERDUCK_TOKEN" not in os.environ:
        import streamlit as st

        os.environ["MOTHERDUCK_TOKEN"] = st.secrets["MOTHERDUCK_TOKEN"]
    return duckdb.connect("md:fpl_data_platform")
