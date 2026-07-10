import json
import os
from datetime import date

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("BUCKET")
SEASON = os.getenv("SEASON") or "2025"
LOAD_DATE = os.getenv("LOAD_DATE") or date.today().isoformat()

FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"

s3 = boto3.client("s3")


def fetch(url: str):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def upload_snapshot(data, filename: str) -> str:
    s3_key = f"fpl/season={SEASON}/load_date={LOAD_DATE}/{filename}"
    s3.put_object(Bucket=BUCKET, Key=s3_key, Body=json.dumps(data).encode("utf-8"))
    return s3_key


def main():
    bootstrap = fetch(FPL_BOOTSTRAP_URL)
    bootstrap_key = upload_snapshot(bootstrap, "bootstrap_static.json")
    print(
        f"Uploaded bootstrap_static.json ({len(bootstrap.get('elements', []))} players) "
        f"-> s3://{BUCKET}/{bootstrap_key}"
    )

    fixtures = fetch(FPL_FIXTURES_URL)
    fixtures_key = upload_snapshot(fixtures, "fixtures.json")
    print(f"Uploaded fixtures.json ({len(fixtures)} fixtures) -> s3://{BUCKET}/{fixtures_key}")


if __name__ == "__main__":
    main()
