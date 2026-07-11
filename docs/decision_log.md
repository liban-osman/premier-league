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

## Phase 4 + consumption: decision layer and league pages (2026-07-10)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 16 | Decider output shape (resolves open decision #1) | **Weighted percentile score** (0–100) + recommendation buckets, availability as a **hard gate** | Each signal becomes a `percent_rank` within (load_date, position) so a weighted sum is meaningful — raw units (points per £m vs transfer counts) can't be added. Weights (35% value / 30% form / 20% fixtures / 15% momentum) are explicit and tunable, unlike a fitted model. Injury is a rule, not a 15% penalty: high_risk forces drop, doubtful caps at monitor. Missing signals coalesce to a neutral 0.5, so offseason snapshots still score sensibly. |
| 17 | League table source | **Derived from finished fixture results**, not the bootstrap `teams` block | FPL zeroes team W/D/L/points in preseason snapshots, so the bootstrap fields are not durable. Fixture scores are. Guarded by a goals-balance singular test (league-wide goals_for = goals_against per snapshot); derived standings cross-check against the `league_position` remnants FPL leaves behind. Tiebreaks: points, GD, GF (head-to-head not modelled). |
| 18 | WhoScored on the public app | **Heavy aggregates only** — never raw events or per-match detail | The data is not-for-redistribution; a public Streamlit URL is redistribution just as much as a public repo. Season-level derived metrics (rates, composites, rankings) are the ceiling. The old pass-map page (per-match event rendering) was removed accordingly. |
| 19 | When a page may read `silver` directly | **Allowed for pure projections** (player stats page); marts reserved for business logic | A mart that is a `select *` pass-through of staging adds a copy to maintain, not value. The league table and transfer score encode real logic and get marts; leaderboards that only select/join/sort do not. |
| 20 | League pages build order | **FPL-derived pages first**, before WhoScored staging or Understat ingestion | Everything needed (goals, assists, xG, fixtures) already lands daily from the FPL API — shippable immediately with zero new ingestion. WhoScored pages depend on the licensing ceiling (#18); Understat is its own design-first integration. |

## Phase 4, second half: WhoScored staging + player mapping (2026-07-11)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 21 | WhoScored staging source | **All three staging models read `raw.whoscored_events`**; the `whoscored_matches` calendar export stays unstaged | Probing the raw tables showed the "events" export is one whole match-centre payload per match: match facts (teams, ftScore, date) on its top level, the event array, and a `playerIdNameDictionary` all in one place. The calendar export carries nothing extra we need — staging it would be a copy, not value (same reasoning as #19). |
| 22 | WhoScored season labelling | **Derive `season_start_year` from each match's own date**, not the S3 partition label | The export sits under `season=2025` in S3 but its matches run 2024-08 → 2025-05 — it is the **2024/25** season, and the hand-set label doesn't follow the FPL convention (start year). The match date is ground truth the payload carries itself; same "derive, don't hardcode" fix as the FPL SEASON bug. |
| 23 | FPL ↔ WhoScored join key (resolves the deferred item) | **`player_id_map` dbt model: a ladder of deterministic, exact name-match rules** — no fuzzy matching, ambiguous candidates dropped | Rules: (1) normalized full name, 392; (2) FPL first+last name token, +22 — catches official long names like "Bruno Miguel Borges Fernandes"; (3) FPL web_name, +19. Total 433 of 685 (~63%), 1:1 enforced by `unique` tests on both id columns. Fuzzy matching is excluded on purpose: a false positive silently corrupts every downstream join, while an unmatched player is visible and countable. The unmatched ~37% is largely *correct* — the WhoScored export (2024/25) and FPL snapshots (2025/26) are different seasons, so relegated clubs' players and departures have no counterpart. |
| 24 | Event grain honesty | **`stg_whoscored_events` is one row per exported event element** — no uniqueness test at this grain | The export itself contains duplicated event ids (27 pairs in 579k; neither `id` nor `(match_id, eventId)` is clean). Claiming a key the source can't honor would mean either a red test or silent deduping; instead the grain is documented as-is and integrity is guarded by a stronger invariant: goal events in the stream must equal goals parsed from ftScore (they do, 1,115 = 1,115 — `assert_whoscored_goal_events_match_scores`). |

## Deferred (still open)

- **Understat integration.** Third source with a real API (xG depth for the league pages and
  the decision layer). S3 prefix reserved; needs its own decision-log entry + architecture
  update before code, per the design-first rule.
- **FPL ↔ WhoScored *team* mapping.** #23 resolves players; team ids stay unmapped until a
  mart actually needs to join at team grain (name-based mapping is trivial by comparison).
