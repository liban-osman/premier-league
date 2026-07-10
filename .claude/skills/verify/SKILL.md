---
name: verify
description: Build, run, and drive this project's surfaces (dbt marts in MotherDuck, Streamlit app) to verify changes end-to-end before committing.
---

# Verify — FPL data platform

`uv` is NOT on PATH on this machine; everything runs from the project venv:
`.venv\Scripts\<tool>.exe`. Env vars come from `.env` (never print values):

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s]' } |
  ForEach-Object { $kv = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($kv[0].Trim(), $kv[1].Trim()) }
```

## dbt (models + tests, against MotherDuck)

```powershell
.venv\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt            # everything
.venv\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt --select <model>  # one model + its tests
```

Inspect results by querying `md:fpl_data_platform` with `.venv\Scripts\python.exe`
+ duckdb (schemas: `raw`, `silver`, `gold`). Set `PYTHONIOENCODING=utf-8` —
player names contain non-cp1252 characters and crash prints otherwise.

## Streamlit app

Server: `.venv\Scripts\streamlit.exe run app/streamlit_app.py --server.headless true --server.port 8765`
(health check: `GET /_stcore/health` → `ok`).

Drive the script (real widgets, real MotherDuck query) with Streamlit's AppTest;
`sys.path.insert(0, "<repo>/app")` first because the app does `from db import ...`:

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app/streamlit_app.py", default_timeout=120).run()
assert not at.exception
at.multiselect[0].select("GKP").run()   # drive filters like a user
```

Gotcha: `load_dotenv()` in `app/db.py` resolves `.env` upward from the *file's*
location, so clearing env vars isn't enough to simulate a missing token —
shadow it with an empty `app/.env` (gitignored) and delete it after.

## Lint

```powershell
.venv\Scripts\ruff.exe check app/ scripts/
.venv\Scripts\ruff.exe format --check app/ scripts/
```

## Live pipeline

After pushing pipeline-touching changes: `gh workflow run "FPL Snapshot" --ref main`,
then `gh run watch <id> --exit-status`. Green means S3 land + MotherDuck load +
full dbt build passed in production.
