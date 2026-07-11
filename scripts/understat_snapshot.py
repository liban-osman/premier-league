import json
import os
import re
import sys
import time
from datetime import date

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("BUCKET")
LOAD_DATE = os.getenv("LOAD_DATE") or date.today().isoformat()

UNDERSTAT_BASE = "https://understat.com"
LEAGUE = "EPL"
# Understat has no documented API; this is the JSON endpoint the site's own
# league page JS calls (see docs/decision_log.md #25). Identify ourselves and
# send the headers a browser XHR would.
HEADERS = {
    "User-Agent": "fpl-data-platform (personal portfolio project)",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{UNDERSTAT_BASE}/league/{LEAGUE}",
}


def parse_season_start_year(league_page_html: str) -> str:
    """Current season start year from the league page title ('2025/2026' -> '2025').

    Derived from the page rather than guessed from today's date, same rule as
    fpl_snapshot.py: raise loudly rather than label a partition wrong.
    """
    match = re.search(r"for the (\d{4})/\d{4} season", league_page_html)
    if match is None:
        raise ValueError("could not find a season in the Understat league page title")
    return match.group(1)


def split_league_payload(payload: dict) -> dict[str, list]:
    """Split one getLeagueData response into three top-level-array files.

    Top-level arrays land in DuckDB as one row per entity; the teams
    dict-of-team-ids would instead become an ever-widening struct across
    seasons (see docs/decision_log.md #27), so it flattens to its values.
    Raises KeyError if the payload shape changed -- fail loudly.
    """
    return {
        "players.json": payload["players"],
        "matches.json": payload["dates"],
        "teams.json": list(payload["teams"].values()),
    }


def fetch_league_data(season: str) -> dict:
    url = f"{UNDERSTAT_BASE}/getLeagueData/{LEAGUE}/{season}"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def derive_current_season() -> str:
    response = requests.get(f"{UNDERSTAT_BASE}/league/{LEAGUE}", headers=HEADERS, timeout=30)
    response.raise_for_status()
    return parse_season_start_year(response.text)


def upload_snapshot(data, filename: str, season: str) -> str:
    s3_key = f"understat/season={season}/load_date={LOAD_DATE}/{filename}"
    boto3.client("s3").put_object(Bucket=BUCKET, Key=s3_key, Body=json.dumps(data).encode("utf-8"))
    return s3_key


def main():
    # Explicit season args (backfill) win; otherwise refresh the current season.
    seasons = sys.argv[1:] or [derive_current_season()]
    for i, season in enumerate(seasons):
        if i > 0:
            time.sleep(3)  # be polite: at most one request every few seconds
        payload = fetch_league_data(season)
        for filename, rows in split_league_payload(payload).items():
            s3_key = upload_snapshot(rows, filename, season)
            print(f"Uploaded {filename} ({len(rows)} rows) -> s3://{BUCKET}/{s3_key}")


if __name__ == "__main__":
    main()
