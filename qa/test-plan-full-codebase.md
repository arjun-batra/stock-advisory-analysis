# SAA Full-Codebase Test Plan (Claude Code Execution)

**Repo:** `arjun-batra/stock-advisory-analysis`
**Executor:** Claude Code
**Authority:** Requirements v4 (source of truth), UI-handoff v3 (rendering authority), Solution Design v15
(superseded — see 2026-07-12 staleness correction below)

> **2026-07-12 staleness correction (multi-agent-template adoption pass, qa):** This plan's authority
> line originally pointed at "Solution Design v15." The current source-of-truth docs are
> `docs/design.md` (tech-lead's as-built solution design, condensed and code-verified from
> `requirements_docs/SD.md`, now at v20) and `docs/requirements.md` (pm's FR1–FR31/NFR1–NFR5
> requirements doc, ported from `requirements_docs/stock-advisory-agent-requirements.md` v5). Where this
> plan's body text below still says "SD v15" in an individual test's pass-criteria (P1-3, P2-3, P2-6,
> P3-1 through P3-4, P3-8, P6-4), read that as "the historical v15 snapshot cited when this plan was
> written" and cross-check against the current `docs/design.md` when re-running those tests — those
> per-test references were not individually rewritten in this pass (only the items below explicitly
> flagged as factually wrong were corrected: the Authority line, P6-2, P1-6, and the Phase 6 section).
**Session state file:** `.qa-session-state.md` — Claude Code must create this at Phase 0, check off every test ID as it completes, and resume from it after any interruption with a single "continue."

---

## 0. Ground Rules (non-negotiable)

1. **No real alerts.** Every dispatch or pipeline run must set `alerts_enabled=false`. If a test requires exercising ntfy publish, use a throwaway topic (`saa-qa-<random>`), never the production topic.
2. **No production data mutation.** Supabase access is read-only except for clearly-marked test rows tagged with `ticker like 'QA_%'`, which must be deleted in Phase 7 teardown. Use `execute_sql` for reads; never `apply_migration` in this plan (no schema changes are in scope).
3. **Passcode hygiene.** Extract the dashboard gate value from page source at runtime. Never write it to `.qa-session-state.md`, commit messages, logs, or GitHub issues.
4. **Playwright in isolated/headless mode** for all browser tests: `claude mcp add playwright -s user -- npx @playwright/mcp@latest --isolated --headless`.
5. **Doc-vs-reality gaps are logged, not fixed.** Any mismatch found between code behavior and Requirements v4 / UI-handoff v3 / SD v15 goes into a gap register (title, plain description, type, recommended resolution). Do not change code or docs; Arjun rules first.
6. **Every phase ends with a summary block** written to `.qa-session-state.md`: tests run, pass/fail/blocked counts, gap register additions.

---

## Phase 0 — Environment & Preconditions

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P0-1 | Clone repo, create venv, `pip install -r requirements.txt` | bash | Clean install, no dependency conflicts |
| P0-2 | Confirm required env vars are documented in `config.py` and all referenced vars resolve or have safe defaults | grep + import `config` | `python -c "import scripts.config"` succeeds with test env; missing-var behavior is explicit (fail-fast or documented default), never silent |
| P0-3 | Verify no secrets in repo | grep for key patterns (API keys, `sb_`, ntfy topic, passcode) across all files + git history of current branch | Zero hits outside env-var references |
| P0-4 | Create `.qa-session-state.md` with full test checklist | file write | File exists, all test IDs listed unchecked |

---

## Phase 1 — Static Analysis & Module-Level (no network, no DB)

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P1-1 | Syntax + import check on all 12 modules in `scripts/` | `python -m py_compile scripts/*.py`, then import each with mocked env | All compile and import |
| P1-2 | Dead code scan | `vulture` or manual grep for unreferenced functions/branches | Findings logged. **Expected known finding:** `notify.py` dead `kind="reminder"` path (issue #11 aftermath) — confirm it's still unreachable, log to gap register, do NOT remove |
| P1-3 | `textutil.py` unit tests | Write pytest cases for every public function: empty string, unicode (NSE company names), very long input, whitespace-only | All pass; behavior matches SD v15 §refactor notes |
| P1-4 | `state.py` verdict-transition logic | Pytest: table-driven test of every verdict pair (Buy→Sell, Buy→Hold, Hold→Buy, Sell→Buy, Sell→Hold, Hold→Sell, and all three no-change cases) | **Locked rule (issue #11):** ANY change → alert flag true, immediately, no cooldown. No change → no alert. Any cooldown logic surviving in code = FAIL + gap register |
| P1-5 | `prefilter.py` gate logic | Pytest with synthetic price/volume inputs at boundaries | Boundary behavior matches Requirements v4 thresholds exactly (off-by-one at thresholds is the target) |
| P1-6 | `config.py` env-var overrides | Set `GEMINI_TIMEOUT_MS`, `NSE_GEMINI_MODEL` etc. to non-default values, assert propagation | Overrides take effect; defaults correct when unset; production model default is `gemini-3.5-flash` (corrected 2026-07-12 — was mis-stated as `gemini-3-flash`; verified against `scripts/config.py` and `docs/requirements.md` §11) |
| P1-7 | Time-boundary checks | Grep all time comparisons in `run_hourly.py`, `prefilter.py`, sql/ for exact-equality upper bounds (`<= time '16:00'` pattern) | All market-close boundaries carry the +5 min jitter buffer. Any exact-equality upper bound = FAIL (pg_cron jitter, known failure class) |
| P1-8 | Naming collision regression | Confirm the collision fixed in PR #28 has not reappeared; no two modules export same-named functions with different behavior | Clean |

---

## Phase 2 — Pipeline Integration (mocked externals, dry-run)

Mock Gemini and yfinance with fixtures. `alerts_enabled=false` everywhere.

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P2-1 | `ingest.py` end-to-end with yfinance mocked for one ticker per market (US, TSX, NSE) | Run with fixtures | `data_snapshot` payload structurally complete for all three markets |
| P2-2 | **Issue #31 verification:** `data_snapshot.market` populated | Inspect generated snapshot for each market | `market` field present and equals `watchlist.market` value. If code fix hasn't landed yet, mark BLOCKED (not FAIL) and note dependency on issue #31 |
| P2-3 | `ai_judge.py` with mocked Gemini responses | Feed: valid JSON verdict, malformed JSON, empty response, timeout simulation | Valid → parsed verdict; malformed/empty → logged failure, no crash, no phantom verdict written; timeout → retry behavior matches SD v15 (no compounding retry waste) |
| P2-4 | `run_hourly.py` full dry run, single ticker, alerts off | Execute with mocks | Completes; gate-decision audit lines present in log for every gate; no silent skips |
| P2-5 | `notify.py` isolated path (**TC-2.6, currently unverified**) | Direct invocation against throwaway ntfy topic | HTTP 200/204 verified in code path; message format matches Requirements v4 alert spec; `kind="reminder"` path confirmed never invoked |
| P2-6 | **FR7/FR8 change/no-change pair on NSE tickers** (currently skipped) | Two consecutive mocked runs on an NSE ticker: run 1 forces verdict change, run 2 forces identical verdict | Run 1 → alert emitted (to throwaway topic); run 2 → silence. `.NS` ticker handling correct throughout |
| P2-7 | `publish_prices.py` output contract | Run with mocks, diff output schema against current `pages/prices.json` | Schema identical; all three markets represented; no client-side yfinance dependency introduced |
| P2-8 | `run_discovery.py` | Dry run | No reference to `candidate_universe` anywhere (table permanently retired — load-bearing decision #7). Any reference = FAIL |

---

## Phase 3 — Database Verification (Supabase, read-only)

Project `ikghqdtlbwifwnooytmm`. One logical query per `execute_sql` call. Quote `call_log."timestamp"` always.

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P3-1 | Schema matches SD v15 | List tables/columns, diff against SD §schema | Exact match; `candidate_universe` absent; `call_log_shadow` present |
| P3-2 | RLS coverage | Join `pg_policies` × `pg_tables` on schemaname+tablename | Every public table has expected policy per SD v15 |
| P3-3 | Cron inventory | `select jobid, jobname, schedule, command, active from cron.job order by jobid` | Jobs match SD v15 schedule table; no orphaned/disabled-but-expected jobs |
| P3-4 | Live function source vs SD | `pg_get_functiondef` for each dispatch function | Source matches SD v15 description; ET-gate uses buffered boundary |
| P3-5 | `data_snapshot.market` in live rows | `select data_snapshot->>'market', count(*) from call_log group by 1` (recent window) | Post-fix rows populated; pre-fix nulls expected and dated. BLOCKED if #31 fix not deployed |
| P3-6 | Dispatch health, last 5 trading days | Response-count-per-time-slot pattern (not `net._http_response` joins — queue doesn't retain) | Expected dispatch count per slot; gaps logged with timestamps |
| P3-7 | Shadow isolation | Confirm `run_shadow.py`/`shadow.py` write only to `call_log_shadow`, never `call_log` | Code inspection + row provenance check. Cross-contamination = FAIL |
| P3-8 | **ET-gate / monitor-window live verification** (pending since June 25) | Query gate-decision audit trail across one full recent trading session per market | Gates opened/closed at correct buffered ET times; no missed windows |

---

## Phase 4 — Dashboard & Detail Pages (Playwright, headless)

Live GitHub Pages + live Supabase where applicable. UI-handoff v3 wins over SD on rendering.

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P4-1 | Password gate | Load dashboard, wrong passcode, then correct (extracted at runtime) | Wrong → blocked; correct → content. Passcode never logged |
| P4-2 | **TC-2.7: live browser ↔ live Supabase wiring** (currently skipped) | Load dashboard, verify rendered verdicts match a direct `call_log` query for same tickers | 1:1 match on verdict, timestamp recency, ticker set |
| P4-3 | Live prices from `prices.json` | Network tab via Playwright: confirm prices fetched from `prices.json`, zero direct Yahoo calls from browser | No CORS errors; no Yahoo endpoints in request log (all three markets are CORS-blocked — any direct call = FAIL) |
| P4-4 | Market badge + currency logic (§4.7) | Verify badge/currency for one US, one TSX, one NSE ticker | Reads `data_snapshot.market`, renders per UI-handoff v3. BLOCKED if P2-2/P3-5 blocked |
| P4-5 | `detail.html` per-ticker view | Load detail for the same three tickers | Fields per UI-handoff v3; **check for residual reminder handling** — log to gap register if present, don't remove |
| P4-6 | Empty/error states | Ticker with no data; simulate `prices.json` fetch failure | Graceful per UI-handoff v3; no raw JS errors in console |
| P4-7 | Console hygiene | Collect console errors across all page loads | Zero uncaught errors |

---

## Phase 5 — Workflows & Scheduling (GitHub Actions)

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P5-1 | Workflow file lint | Parse `.github/workflows/*` | Valid YAML; triggers are `workflow_dispatch` (pg_cron drives scheduling — native cron for market runs = gap register entry) |
| P5-2 | Secrets referenced vs configured | List secret names referenced in workflows; verify each exists in repo settings (names only, never values) | All resolve |
| P5-3 | Test dispatch, alerts off | `workflow_dispatch` with `alerts_enabled=false`, single ticker | Run succeeds end-to-end; logs show gate decisions, HTTP verifications (204), no alert sent |
| P5-4 | Failure-path logging | Review most recent failed run (if any) in Actions history | Failure cause identifiable from logs alone — no silent failure |

---

## Phase 6 — Shadow Pipeline

> **2026-07-12 staleness correction:** This phase now maps to `docs/requirements.md` §10
> (FR24–FR31, NFR5 — the Experimental Tracks / shadow wallet pilot section), superseding the ad hoc
> shadow assumptions this phase was originally written against. See `docs/design.md` §13 for the
> as-built shadow pilot design.

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P6-1 | `SHADOW_ENABLED` kill switch (FR30, NFR5) | Run shadow entry point with flag false, then true (mocked Gemini) | False → zero shadow activity, zero `call_log_shadow` writes; true → normal path. Note the documented accepted risk: the switch defaults **fail-OPEN** (unset/empty stays enabled; only the literal string `false` disables it, per FR30) |
| P6-2 | Single-variable isolation (FR24, FR25) | Confirm the shadow prompt is built by appending the position-awareness addendum to `ai_judge.BATCH_SYSTEM_PROMPT` — i.e. `SHADOW_SYSTEM_PROMPT` in `scripts/shadow.py` (inline Python; there is **no** `shadow_pilot_prompt.md` file — that file does not exist in the repo) — and that the shadow call uses the **same** model try-order as production (`GEMINI_MODEL`/`GEMINI_MODEL_BACKUP`, default `gemini-3.5-flash`/`gemini-3.1-flash-lite`, via `ai_judge._models_to_try`) | Prompt = production's `BATCH_SYSTEM_PROMPT` verbatim + position-awareness addendum (differs only in the appended section); model identical to production's watchlist model pair. Model divergence = FAIL |
| P6-3 | Scope (FR24) | Shadow runs only against US/Canada batch | No NSE tickers in shadow path |
| P6-4 | Concurrency safety (FR29) | Verify shadow and production runs share no mutable state (tables, files, rate limits that would starve production) | True concurrent execution safe per SD v15 |
| P6-5 | Evaluation query readiness (FR31 — OPEN GAP) | Run the verdict-balance comparison query (counts per verdict per track) against `call_log` vs `call_log_shadow` | **BLOCKED on FR31, not a pass.** No committed, reproducible evaluation harness exists anywhere in the repo — the SQL migration's own comments reference a "wallet-sim recursive-CTE walk / harness" that lives only in the ad hoc Supabase SQL editor, not as versioned SQL/scripts (verified across `sql/`). Do not mark this test PASS by hand-running an ad hoc query; per `docs/requirements.md` FR31 the pilot cannot be assessed and must not graduate until dev commits a versioned, reproducible harness. Re-run this test once FR31 lands |

---

## Phase 7 — Teardown & Report

1. Delete any `QA_%` test rows from Supabase.
2. Confirm throwaway ntfy topic abandoned; no production topic messages sent (query topic if verifiable, otherwise assert from logs).
3. Final report appended to `.qa-session-state.md`:
   - Pass/fail/blocked table for all test IDs
   - **Gap register** (title, description, type, recommended resolution) + plain-English translation
   - Explicit list of tests BLOCKED on issue #31, with re-run instructions post-fix
4. Open one GitHub issue titled `QA: full-codebase test run <date>` containing the report (no passcodes, no secrets, no topic names).

---

## Known Expected Findings (log, don't fix)

- `notify.py` dead `kind="reminder"` path (P1-2, P2-5)
- Possible residual reminder handling in `detail.html` (P4-5)
- `data_snapshot.market` nulls in pre-fix rows (P3-5) — expected historical artifact

## Blocking Dependencies

- **Issue #31** blocks P2-2, P3-5, P4-4 until the populate-from-`watchlist.market` fix lands. Mark BLOCKED, not FAIL.
