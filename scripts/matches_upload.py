import boto3
from pathlib import Path
from datetime import date
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Read configuration from environment
BUCKET = os.getenv("BUCKET")
SEASON = os.getenv("SEASON", "2025")
LOAD_DATE = os.getenv("LOAD_DATE", date.today().isoformat())
MATCHES_FOLDER = os.getenv("MATCHES_FOLDER")

s3 = boto3.client("s3")
local_folder = Path(MATCHES_FOLDER)

s3_prefix = f"whoscored/matches/season={SEASON}/load_date={LOAD_DATE}/"

# Upload all JSON files in folder
for file_path in local_folder.glob("*.json"):
    s3_key = f"{s3_prefix}{file_path.name}"
    s3.upload_file(str(file_path), BUCKET, s3_key)
    print(f"Uploaded {file_path.name} → s3://{BUCKET}/{s3_key}")
