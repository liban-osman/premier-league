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


def fetch_bootstrap() -> dict:
    response = requests.get(FPL_BOOTSTRAP_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def upload_snapshot(data: dict) -> str:
    s3_key = f"fpl/season={SEASON}/load_date={LOAD_DATE}/bootstrap_static.json"
    boto3.client("s3").put_object(
        Bucket=BUCKET, Key=s3_key, Body=json.dumps(data).encode("utf-8")
    )
    return s3_key


def main():
    data = fetch_bootstrap()
    s3_key = upload_snapshot(data)
    print(f"Uploaded bootstrap_static.json ({len(data.get('elements', []))} players) -> s3://{BUCKET}/{s3_key}")


if __name__ == "__main__":
    main()
