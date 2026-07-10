# Decision Log

Short log of choices made and why. Updated as decisions get made, not rewritten after the
fact — if a decision changes later, add a new entry rather than editing the old one.

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Warehouse | **Snowflake** (not DuckDB/Postgres) | Already implemented and working in the existing DAG; no reason to migrate for a portfolio piece. |
| 2 | Transform tooling | **Plain SQL scripts** via Airflow `SnowflakeOperator` (not dbt) | Matches the existing `sql/01_raw` → `02_silver` → `03_gold` structure already in place. dbt is a possible stated future-work item, not adopted now. |
| 3 | Orchestration | **Airflow** (not GitHub Actions/cron, not Dagster) | Already implemented (`airflow_dag/pipeline_dag.py`). |
| 4 | Orchestration host | **Local via Docker** | Matches the locked-in "reproducible in Docker" decision and CLAUDE.md's local-first default. Cloud-managed Airflow (MWAA/Astronomer) stays a visible phase-2 option, not adopted now. |
| 5 | FPL data landing | **S3-first**, mirroring the WhoScored scripts (`fpl/season=.../load_date=.../`), then `COPY INTO` to Snowflake raw | One consistent landing pattern across both sources instead of two different ingestion shapes. |
| 6 | FPL snapshot cadence | **Daily** (`@daily`) | Prices, ownership %, and form move daily — this is the core time-series signal the whole project exists to capture. Matches the existing DAG's schedule. |
| 7 | DAG topology | **Two DAGs**: `fpl_snapshot_pipeline` (daily) and `events_pipeline` (weekly / manual trigger) | Airflow DAGs run on one schedule each. A daily-automated source and a source gated on a manual export step can't share a schedule without one blocking the other. |
| 8 | Event data source (resolves CLAUDE.md's `[TO CONFIRM]`) | **WhoScored**, manual per-match JSON export, uploaded via `events_upload.py` / `matches_upload.py` | Confirmed by reading the existing upload scripts (S3 prefix is literally `whoscored/...`). Not-for-redistribution — raw files stay gitignored; only code/schema/synthetic samples are tracked. |

## Revision: cost + "must actually be a deployed, usable site" (post-Phase-2)

Challenged the original stack once Phase 2 was built: Snowflake's free trial credits expire,
and nothing was actually deployed anywhere — `streamlit run` only ever worked on one machine.
These entries supersede rather than edit the originals above, per this log's own rule.

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 9 | Warehouse (supersedes #1) | **DuckDB / MotherDuck** (not Snowflake) | Snowflake trial credits expire, then it's a card on file for a repo that earns nothing. This project's data volume never needed a distributed cloud warehouse. $0 forever, and currently a stronger resume signal than Snowflake, not a weaker one. |
| 10 | Transform tooling (supersedes #2) | **dbt-core + dbt-duckdb** (not plain SQL scripts) | `sql/01_raw`→`03_gold` were still 0 bytes when this changed — nothing real to migrate. dbt-core itself is free (only dbt Cloud costs money), and dbt is one of the most in-demand keywords in current data engineering hiring. Free and higher-signal, no actual tradeoff. |
| 11 | Live FPL orchestration | **GitHub Actions cron**, `@daily` | No free way to keep a local-Docker Airflow scheduler running unattended for a personal project. Actions is free for a public repo and is its own recognizable CI/CD keyword. Not yet built — Phase 3/5. |
| 12 | Airflow's role (supersedes #3/#4 in spirit, not in fact) | **Kept as a demonstrated artifact**, not the live scheduler | The Phase 2 Airflow+Docker work (`events_pipeline` DAG) stays in the repo, fully working, as proof of Airflow fluency — it just isn't what runs the live site day to day. Gets the Airflow keyword honestly without paying to host it. |
| 13 | dbt execution environment | **Isolated venv inside the Airflow image**, not Airflow's own Python environment | Real conflict, not hypothetical: dbt-core's dependency tree collides with Airflow's pinned constraints (`isodate`) even against Airflow's own constraints file — confirmed via a failed `docker build` before this fix. |
| 14 | Streamlit hosting | **Streamlit Community Cloud** (not local-only `streamlit run`) | Free for a public repo; turns this into a link instead of code a hiring manager would have to clone and run. |
| 15 | MotherDuck vs. DuckDB-file-in-S3 | **MotherDuck free tier** | Airflow and Streamlit Cloud run in separate environments and both need the same data. MotherDuck gives a real hosted DuckDB reachable from both over the network — no custom file-sync code to write or maintain. |

## Deferred (still open)

- **FPL ↔ WhoScored join key.** No natural shared player/team identifier between the two
  sources. Will likely need an explicit mapping table. Deferred to Phase 4 schema design.
