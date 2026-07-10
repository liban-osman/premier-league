# Architecture

FPL Data Platform — snapshots two sources on a schedule, lands them in DuckDB/MotherDuck through a
raw → silver → gold layering (via dbt), and serves a decision layer + visualizations off the top.

> Revised from the original Snowflake-based design in [decision_log.md](decision_log.md) — cost
> (Snowflake trial credits expire) and needing an actually-deployed, actually-free site drove the
> swap to DuckDB/MotherDuck + dbt + Streamlit Community Cloud.

```mermaid
flowchart LR
    subgraph Sources
        FPL["FPL Official API<br/>current-state only<br/>bootstrap-static + fixtures"]
        WS["WhoScored export<br/>proprietary, manual, not-for-redistribution"]
        US["Understat API<br/>planned -- xG depth"]
    end

    subgraph Ingestion["Ingestion"]
        FPL_TASK["fpl_snapshot_pipeline<br/>GitHub Actions, @daily"]
        WS_TASK["events_pipeline<br/>Airflow, local Docker, manual trigger"]
    end

    subgraph Landing["S3 -- raw JSON, partitioned"]
        S3_FPL["fpl/season=.../load_date=.../"]
        S3_WS["whoscored/events & matches/season=.../load_date=.../"]
        S3_US["understat/ -- prefix reserved"]
    end

    subgraph Warehouse["MotherDuck (DuckDB), via dbt"]
        direction TB
        RAW["raw -- loaded via DuckDB's native S3/httpfs read"] --> SILVER["silver -- dbt staging models"] --> GOLD["gold -- dbt marts<br/>incl. mart_transfer_decision"]
    end

    Consumption["Streamlit Community Cloud<br/>transfer decisions · league table · player stats"]

    FPL --> FPL_TASK --> S3_FPL --> RAW
    WS --> WS_TASK --> S3_WS --> RAW
    US -.-> S3_US -.-> RAW
    GOLD --> Consumption
```

## Stage notes

**Sources.** Unchanged from the original design: FPL is a public, current-state-only API;
WhoScored is a proprietary per-match event export, manual today, never committed to the repo.

**Ingestion.** Two separate schedulers, not one, because the two sources have genuinely
different automation stories:

- `fpl_snapshot_pipeline` — runs on **GitHub Actions cron**, `@daily` at 06:00 UTC
  (`.github/workflows/fpl_snapshot.yml`): fetch FPL `bootstrap-static` **and `fixtures`** →
  land both in S3 → load MotherDuck `raw` (`fpl_bootstrap`, `fpl_fixtures`) → `dbt build`.
  GitHub Actions instead of Airflow here because there's no free way to keep an Airflow
  scheduler running unattended 24/7 for a personal project, and Actions is free for a public
  repo. `BUCKET`, `AWS_*`, and `MOTHERDUCK_TOKEN` live as **GitHub repo secrets** (configured,
  live, and green as of 2026-07-10).
- `events_pipeline` — stays on **Airflow, local Docker, LocalExecutor**, manually triggered.
  This DAG already exists (`airflow_dag/pipeline_dag.py`) and is kept specifically as a
  demonstrated artifact of Airflow fluency, even though it isn't the thing actually running the
  live site. Its `load_raw` task now calls the same `scripts/load_raw.py` helper the GitHub
  Actions workflow uses, for the WhoScored sources.

**Landing (S3).** Unchanged — raw JSON, partitioned by season and load date.

**Warehouse + transform (MotherDuck via dbt).** Replaces Snowflake + plain SQL scripts.
- `raw` — loaded via DuckDB's native `read_json_auto('s3://...')` / httpfs support, no separate
  `COPY INTO` step needed the way Snowflake required.
- `silver` = dbt **staging** models (views) — cleaned, typed: `stg_fpl_players` / `teams` /
  `positions` (unnested from bootstrap) and `stg_fpl_fixtures`. WhoScored staging is still
  pending (raw sources are declared in `sources.yml` only).
- `gold` = dbt **marts** models (tables):
  - five signal marts — form trend, price momentum, team fixture difficulty (rolling next-5
    FDR), value (points per £m ranked in position), availability risk;
  - `mart_transfer_decision` — the decision layer: each signal becomes a `percent_rank`
    within (load_date, position), weighted 35/30/20/15 into a 0–100 `transfer_score`,
    with availability as a hard gate (high-risk → drop) rather than a weighted input;
  - `mart_league_table` — standings derived from finished fixture results (FPL zeroes the
    bootstrap team records in preseason snapshots), guarded by a goals-balance invariant test.
- dbt vocabulary maps directly onto the raw/silver/gold naming used everywhere else in this
  project; see the comment in `dbt/dbt_project.yml`.
- dbt runs from its **own isolated venv** inside the Airflow image (`/home/airflow/dbt-venv`),
  not Airflow's own Python environment — dbt-core's dependencies genuinely conflict with
  Airflow's pinned constraints (hit this for real: `isodate` version conflict), so they can't
  share a site-packages directory.

**Consumption.** Streamlit, deployed on **Streamlit Community Cloud** (free, public-repo tier)
instead of local-only `streamlit run` — the actual fix for "usable by someone who isn't me."
Connects to the same MotherDuck database the pipeline writes to, via `MOTHERDUCK_TOKEN`
(bridged from `st.secrets` into the environment on Cloud; from `.env` locally). Auto-redeploys
on every push to `main`. Three pages behind `st.navigation`:

- **Transfer decisions** — the headline view over `mart_transfer_decision`, filterable by
  position and recommendation.
- **League table** — reads `mart_league_table`.
- **Player stats** — top scorers/assists leaderboards and a goals-vs-xG scatter; reads
  `silver` directly, deliberately: these are pure projections with no business logic, and a
  pass-through mart would add a copy, not value.

**WhoScored on the public app: heavy aggregates only.** The data is not-for-redistribution and
a public app is redistribution — so raw events or per-match detail never render there (the old
pass-map page was removed for this reason, among others). Season-level derived metrics are the
permitted ceiling.

## Known open items

- **FPL ↔ WhoScored join key.** Still unresolved, still deferred — no natural shared
  player/team identifier between the two sources; will likely need an explicit mapping table.
- **WhoScored staging models don't exist yet.** `whoscored_events` / `whoscored_matches` are
  declared as raw sources in `sources.yml` but nothing in `silver` reads them — the second
  half of Phase 4.
- **Understat is reserved, not wired.** The `understat/` S3 prefix exists; no script, DAG, or
  dbt source touches it yet. Integrating it is its own design-first step (decision log entry +
  diagram update before code).
- **`SEASON` is pinned to `"2025"`** in the workflow and `.env`. When FPL rolls the API to
  2026/27 (typically late July), snapshots would mislabel into the old partition — needs a
  bump or a derived value before then.
- **Unused app dependencies.** `mplsoccer` / `matplotlib` remain in `pyproject.toml` after the
  pass-map page was removed; dropping them requires regenerating `uv.lock`, and `uv` isn't
  installed on the dev machine. Cleanup deferred, deliberately, to avoid breaking the
  workflow's `uv sync --locked`.
