import duckdb
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    # MOTHERDUCK_TOKEN is picked up automatically from the environment.
    return duckdb.connect("md:fpl_data_platform")
