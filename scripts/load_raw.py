import os
import sys

import duckdb
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("BUCKET")
LOCAL_STAGING_DB = "_staging.duckdb"

# One raw table per source, each a glob over every snapshot landed in S3 --
# read_json_auto infers schema across all matching files.
SOURCES = {
    "fpl_bootstrap": "fpl/season=*/load_date=*/bootstrap_static.json",
    "fpl_fixtures": "fpl/season=*/load_date=*/fixtures.json",
    "whoscored_events": "whoscored/events/season=*/load_date=*/*.json",
    "whoscored_matches": "whoscored/matches/season=*/load_date=*/*.json",
}


def stage_locally(source: str) -> None:
    # Real event JSON has deeply nested, dynamically-keyed fields (WhoScored
    # qualifiers keyed by numeric qualifier-type IDs that vary event to
    # event). Letting read_json_auto fully struct-ify that -- and then
    # union_by_name reconcile it across ~30 files -- OOM'd at 25GB locally,
    # not just on MotherDuck's compute. That's the wrong shape for raw
    # landing anyway: cap inference depth so stable top-level fields (id,
    # minute, teamId, x, y, type, ...) stay typed, and genuinely dynamic
    # nested content collapses into an opaque JSON blob instead of exploding
    # into hundreds of reconciled struct fields. Parsing deliberately in
    # silver, once the shape is actually known, is the right place for that.
    s3_glob = SOURCES[source]
    conn = duckdb.connect(LOCAL_STAGING_DB)
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute(f"""
        CREATE OR REPLACE SECRET s3_secret (
            TYPE s3,
            KEY_ID '{os.environ["AWS_ACCESS_KEY_ID"]}',
            SECRET '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            REGION '{os.getenv("AWS_DEFAULT_REGION", "us-east-1")}'
        )
    """)
    conn.execute(
        "CREATE OR REPLACE TABLE staged AS "
        "SELECT * FROM read_json_auto("
        f"'s3://{BUCKET}/{s3_glob}', filename = true, union_by_name = true, "
        "maximum_depth = 2)"
    )
    conn.close()


def push_to_motherduck(source: str) -> str:
    # ATTACH 'md:' AS <alias> isn't supported in MotherDuck's workspace mode,
    # so connect directly to the target database instead, and attach the
    # local staging file (a completely ordinary DuckDB file, no MotherDuck
    # involved) as the source to pull the already-parsed data from.
    table = f"raw.{source}"
    conn = duckdb.connect("md:")
    conn.execute("CREATE DATABASE IF NOT EXISTS fpl_data_platform")
    conn.execute("USE fpl_data_platform")
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute(f"ATTACH '{LOCAL_STAGING_DB}' AS local_staging")
    conn.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM local_staging.staged")
    conn.execute("DETACH local_staging")
    conn.close()
    return table


def load_raw_table(source: str) -> str:
    stage_locally(source)
    table = push_to_motherduck(source)
    os.remove(LOCAL_STAGING_DB)
    return table


if __name__ == "__main__":
    loaded_table = load_raw_table(sys.argv[1])
    print(f"Loaded {loaded_table}")
