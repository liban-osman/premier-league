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

## Deferred (not blocking Phase 1)

- **FPL ↔ WhoScored join key.** No natural shared player/team identifier between the two
  sources. Will likely need an explicit mapping table. Deferred to Phase 4 schema design.
- **dbt adoption.** Explicitly not adopted now (see #2). Worth revisiting only if the plain-SQL
  layering starts to strain under duplication or testing needs.
