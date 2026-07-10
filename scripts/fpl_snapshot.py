import json
import os
from datetime import date

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("BUCKET")
LOAD_DATE = os.getenv("LOAD_DATE") or date.today().isoformat()

FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"


def fetch(url: str):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def derive_season(bootstrap: dict) -> str:
    """Season start year from the first gameweek deadline ('2025' == 2025/26).

    Read from the payload rather than hardcoded so the S3 partition label
    rolls over automatically on whatever day FPL flips the API to the new
    season. Raises if the events block is missing or empty -- a loudly failed
    run beats silently mislabelling a partition.
    """
    deadline = bootstrap["events"][0]["deadline_time"]  # e.g. 2025-08-15T17:30:00Z
    return deadline[:4]


def upload_snapshot(data, filename: str, season: str) -> str:
    s3_key = f"fpl/season={season}/load_date={LOAD_DATE}/{filename}"
    boto3.client("s3").put_object(Bucket=BUCKET, Key=s3_key, Body=json.dumps(data).encode("utf-8"))
    return s3_key


def main():
    bootstrap = fetch(FPL_BOOTSTRAP_URL)
    # An explicit SEASON env var wins (manual backfills); otherwise label the
    # partition with the season the API itself says it's serving.
    season = os.getenv("SEASON") or derive_season(bootstrap)

    bootstrap_key = upload_snapshot(bootstrap, "bootstrap_static.json", season)
    print(
        f"Uploaded bootstrap_static.json ({len(bootstrap.get('elements', []))} players) "
        f"-> s3://{BUCKET}/{bootstrap_key}"
    )

    fixtures = fetch(FPL_FIXTURES_URL)
    fixtures_key = upload_snapshot(fixtures, "fixtures.json", season)
    print(f"Uploaded fixtures.json ({len(fixtures)} fixtures) -> s3://{BUCKET}/{fixtures_key}")


if __name__ == "__main__":
    main()
