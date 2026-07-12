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

## Understat integration (2026-07-11)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 25 | Understat access path | **`GET /getLeagueData/{league}/{season}` with plain `requests`** — no scraper library | Understat has no documented API. The well-known community libraries parse JSON blobs embedded in the page HTML — and probing showed **that format is gone in 2026**: pages are now thin shells and the data loads client-side from `getLeagueData`, found by reading the site's own `league.min.js`. Calling the endpoint directly is simpler, matches what the site itself does, and adds zero dependencies (the libraries would be broken anyway, and adding deps is blocked on regenerating `uv.lock`). One ~530KB GET returns a season's players, matches, and team histories. |
| 26 | Ingestion pattern | **Backfill + weekly refresh** (`@weekly` GitHub Actions, own workflow), *not* the daily snapshot pattern | The FPL pipeline snapshots daily because the FPL API throws history away. Understat serves any season back to 2014/15 on demand — copying the snapshot pattern would build a time series that already exists at the source. Staging therefore reads **only the latest `load_date` per season** (refresh semantics); re-runs are idempotent overwrites, not new time-series points. A separate workflow isolates scrape failures from the live daily FPL pipeline. Loaded now: **2024** (overlaps the WhoScored export → cross-source reconciliation) and **2025** (aligns with FPL snapshots). Current season is derived from the league page title, not hardcoded (same rule as #22 / the FPL SEASON fix); explicit season args override for backfill. |
| 27 | Landing shape | **Split the payload into three top-level JSON arrays** (`players.json`, `matches.json`, `teams.json` — the teams dict-of-ids becomes a list of its values, content untouched) | `read_json_auto` types dynamically-keyed dicts as ever-widening structs (the WhoScored qualifiers lesson), while top-level arrays land cleanly as one row per entity — it's why `fpl_fixtures` needs no unnesting. Mirrors the existing two-file FPL landing pattern. |
| 28 | FPL ↔ Understat join key | **`player_id_map_understat`** — the same deterministic exact-match rule ladder as #23 | Same reasoning as #23 (no fuzzy matching, ambiguous candidates dropped, 1:1 enforced by tests). Verification surfaced unmatched high-minute players and two systematic causes, both fixed: Understat HTML-escapes apostrophes (decoded in staging), and FPL's long official names hide the common surname at *either* end ('Bruno Miguel Borges **Fernandes**' vs 'David **Raya** Martin') — a fourth `first_tokens` rule catches the latter, added to **both** maps. Final: Understat 558 mapped (**489 of 537 = 91%** of 2025/26 players, same season as FPL); WhoScored 433 → 471. The remaining unmatched are transliterations ('Djordje Petrovic' vs 'Đorđe Petrović') and nicknames ('Matty' Cash) — a manual-override seed is the future fix, never fuzzy matching. |

## App visual overhaul (2026-07-11)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 29 | Badges + player photos | **Hotlink the official Premier League asset CDN**, keyed on FPL's global asset codes (`team_code` / `player_code`, now staged in silver) | The bootstrap payload already carries the asset ids; the CDN URLs are the same ones the FPL site itself serves, so nothing is stored or redistributed from this repo. The codes are global and stable across seasons (unlike `team_id`/`player_id`, which reset), so they're also the best future cross-season keys. `not_null` tests guard that every snapshot carries them. |
| 30 | Where display attributes live | **`team_code`/`form_last_5` go into `mart_league_table`; player photos join from staging in the app query** | The league mart already joins `stg_fpl_teams`, and a form guide is derived logic that belongs in gold, not in a page. The player photo id, by contrast, would have to thread through two marts (`mart_player_value` → `mart_transfer_decision`) purely for display — the app-side join to silver is a pure projection, which decision #19 explicitly allows. |
| 31 | Chart label collisions (the "can't read the names" fix) | **Haloed, direction-aware, user-controlled labels** — never more static labels | Labels get a surface-colored stroke underneath ink text; over-performers label upward and under-performers downward, away from the diagonal where the cloud is densest; the labelled set is a multiselect the reader controls (defaulting to the top-5 outliers). Clicking any point opens a full player card instead of cramming more text onto the plot. |

## Mapping overrides (2026-07-11)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 32 | Residual unmatched players (resolves the deferred item from #28) | **`seed_player_map_overrides_understat`** — a hand-verified dbt seed of 27 pairs, keyed on the stable `player_code`, winning over the ladder in `player_id_map_understat` | Every pair was confirmed by team + position + minutes before entering the seed (Petrović and Alisson match to the minute); the note column records why the ladder missed each one (transliterations like Đorđe/Djordje and Ødegaard — Ø isn't a strippable accent — nicknames like Matty/Matthew, name-order flips like Mitoma Kaoru). Keying on `player_code` rather than `player_id` means the seed survives season rollovers. Coverage: 489 → **516 of 537 (96%)** of 2025/26 players, and **every player with 900+ minutes is now mapped**. Still never fuzzy matching — the seed is the designed escape hatch for exactly this residue. WhoScored gets no seed: its unmatched rest is cross-season, not misspelling. |

## Understat xG in the decision layer (2026-07-12)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 33 | Fifth transfer_score signal (resolves the deferred item) | **Underlying threat = Understat npxG+xA per 90**, percentile within (load_date, position); weights rebalanced to **30% value / 25% form / 20% underlying / 15% fixtures / 10% momentum** (user-confirmed) | An *independent* xG model adds what FPL's own xG can't: a finishing-luck-robust read on chance quality — underperformers are buy-low candidates, overperformers regression bait. The mart joins through the map's stable `player_code` + season match, so historical snapshots keep joining correctly after a season rollover (`player_id` resets; the code doesn't). Scoped to outfielders with ≥450 Understat minutes: keepers all sit at ~0 npxG+xA (percent_rank would rank them all bottom instead of neutral) and tiny-minute per-90 rates are noise; everyone excluded coalesces to the neutral 0.5. At the August flip the signal degrades gracefully to neutral until Understat 2026/27 accumulates via the weekly cron. |

## Transfer decisions page redesign: actionable highlights (2026-07-12)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 34 | Transfer decisions page shape | **Lead with actionable highlights** — high-ownership "movers" (recommendation change since last snapshot, split consider-selling / consider-buying) and price-capped "budget picks" — before the top-pick tiles; the full sortable table and methodology caption move into a collapsed expander | A page that opens on a sortable table of every player's score answers "how is transfer_score computed," not "what should I actually do today." The two highlight sections answer the second question directly, the way someone managing an existing squad actually uses the page. Mirrors `player_stats.py`'s existing "full table in an expander" precedent. |
| 35 | Day-over-day recommendation change | **`prev_transfer_score` / `prev_recommendation` / `recommendation_trend` added directly to `mart_transfer_decision`**, via the same `lag() over (partition by player_id order by load_date)` idiom as `mart_player_price_momentum` / `mart_player_form_trend` (#16) — not a separate mart | The comparison is business logic about the same signal the mart already owns (#19's dividing line). Unlike the two precedent marts, `recommendation` is itself computed inside this model, not a raw staged column — it has to be hoisted into its own CTE (and given an ordinal `recommendation_rank`, mapped from the bucket name rather than duplicating the threshold conditions) one step before the lag, which the precedents never needed. `prev_recommendation` stays untested for nullness — legitimately null on a player's first-ever snapshot, and `dbt build` runs in the live daily pipeline, so a bad `not_null` test would go red on every new player. `recommendation_trend` is always computed and gets both `not_null` and `accepted_values`, since the new UI feature filters on it directly. Budget picks needed zero dbt changes — a price/score filter over columns the mart already exposed. |
| 36 | Empty-state honesty for movers | **Always render the movers section; empty subsets get an explanatory caption, not a hidden section** | As of this snapshot history (4 days, 2026-07-09 through 2026-07-12, deep preseason — the live pipeline only went green 2026-07-10) `transfer_score` hasn't moved day-over-day at all: zero movers is the correct, expected answer right now, not a bug. Hiding the section when empty would make a real feature look unbuilt to anyone viewing the live site during a quiet week; an honest caption both proves the feature works and explains why the page is quiet, the same instinct as #26 / #33. |

## Deferred (still open)

- **FPL ↔ WhoScored *team* mapping.** #23 resolves players; team ids stay unmapped until a
  mart actually needs to join at team grain (name-based mapping is trivial by comparison).
- **`player_id` resets across a season rollover**, and `mart_transfer_decision`'s new
  `lag() partition by player_id` (#35) inherits the same characteristic `mart_player_price_momentum`
  / `mart_player_form_trend` already have unaddressed: at a season boundary a reused `player_id`
  could produce a spurious `prev_recommendation` where `'no_prior_snapshot'` would be correct.
  Not fixed here; `player_code` (stable across seasons, per #29) is the eventual fix if it matters.
