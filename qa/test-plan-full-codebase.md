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
| P1-2 | Dead code scan | `vulture` or manual grep for unreferenced functions/branches | Findings logged. (2026-07-12 correction: the `notify.py` `kind="reminder"` path previously listed here as an expected dead branch has been fully removed from the code, not left unreachable — `docs/design/components.md` §4.6 confirms "the `reminder` kind is retired." There is no `kind=="reminder"` branch anywhere in `notify.py` to find; do not search for it.) |
| P1-3 | `textutil.py` unit tests | Write pytest cases for every public function: empty string, unicode (NSE company names), very long input, whitespace-only | All pass; behavior matches SD v15 §refactor notes |
| P1-4 | `state.py` verdict-transition logic | Pytest: table-driven test of every verdict pair (Buy→Sell, Buy→Hold, Hold→Buy, Sell→Buy, Sell→Hold, Hold→Sell, and all three no-change cases) | **Locked rule (issue #11):** ANY change → alert flag true, immediately, no cooldown. No change → no alert. Any cooldown logic surviving in code = FAIL + gap register |
| P1-5 | `prefilter.py` gate logic | Pytest with synthetic price/volume inputs at boundaries | Boundary behavior matches Requirements v4 thresholds exactly (off-by-one at thresholds is the target) |
| P1-6 | `config.py` env-var overrides | Set `GEMINI_TIMEOUT_MS`, `NSE_GEMINI_MODEL` etc. to non-default values, assert propagation | Overrides take effect; defaults correct when unset; production model default is `gemini-3.5-flash` (corrected 2026-07-12 — was mis-stated as `gemini-3-flash`; verified against `scripts/config.py` and `docs/requirements.md` §10) |
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
| P2-5 | `notify.py` isolated path (**TC-2.6, currently unverified**) | Direct invocation against throwaway ntfy topic | HTTP 200/204 verified in code path; message format matches Requirements v4 alert spec. (2026-07-12 correction: the `kind="reminder"` path this cell used to ask executors to confirm "never invoked" has been fully removed from `notify.py`, not just left unreachable — there is nothing to invoke or confirm; drop that check.) |
| P2-6 | **FR7/FR8 change/no-change pair on NSE tickers** (currently skipped) | Two consecutive mocked runs on an NSE ticker: run 1 forces verdict change, run 2 forces identical verdict | Run 1 → alert emitted (to throwaway topic); run 2 → silence. `.NS` ticker handling correct throughout |
| P2-7 | `publish_prices.py` output contract | Run with mocks, diff output schema against current `pages/prices.json` | Schema identical; all three markets represented; no client-side yfinance dependency introduced |
| P2-8 | `run_discovery.py` | Dry run | No reference to `candidate_universe` anywhere (table permanently retired — load-bearing decision #7). Any reference = FAIL |

---

## Phase 3 — Database Verification (Supabase, read-only)

Project `ikghqdtlbwifwnooytmm`. One logical query per `execute_sql` call. Quote `call_log."timestamp"` always.

| ID | Test | Method | Pass criteria |
|---|---|---|---|
| P3-1 | Schema matches SD v15 | List tables/columns, diff against SD §schema | Exact match; `candidate_universe` absent. (2026-07-16 correction: the shadow tracks were retired — see the "Retired: shadow-pilot tracks" note in `docs/design.md` — so `call_log_shadow`/`call_log_shadow_nse` are no longer expected. `sql/drop_shadow_tables_migration.sql` drops both tables; as of this test-plan update it had not yet been applied to the live project, so confirm current state rather than assuming either presence or absence.) |
| P3-2 | RLS coverage | Join `pg_policies` × `pg_tables` on schemaname+tablename | Every public table has expected policy per SD v15 |
| P3-3 | Cron inventory | `select jobid, jobname, schedule, command, active from cron.job order by jobid` | Jobs match SD v15 schedule table; no orphaned/disabled-but-expected jobs |
| P3-4 | Live function source vs SD | `pg_get_functiondef` for each dispatch function | Source matches SD v15 description; ET-gate uses buffered boundary |
| P3-5 | `data_snapshot.market` in live rows | `select data_snapshot->>'market', count(*) from call_log group by 1` (recent window) | Post-fix rows populated; pre-fix nulls expected and dated. BLOCKED if #31 fix not deployed |
| P3-6 | Dispatch health, last 5 trading days | Response-count-per-time-slot pattern (not `net._http_response` joins — queue doesn't retain) | Expected dispatch count per slot; gaps logged with timestamps |
| P3-7 | ~~Shadow isolation~~ — RETIRED (2026-07-16) | N/A | The shadow tracks (`scripts/shadow.py`, `scripts/run_shadow.py`, `scripts/run_shadow_nse.py`) were deleted per the "Retired: shadow-pilot tracks" note in `docs/design.md`; there is no shadow write path left to isolate. Do not re-run. |
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
| P4-5 | `detail.html` per-ticker view | Load detail for the same three tickers | Fields per UI-handoff v3. (2026-07-12 correction: the "check for residual reminder handling" instruction previously here referred to `notify.py`'s `kind="reminder"` path, which has been fully removed from the codebase — `docs/design/components.md` §4.6. There is no known residual reminder handling to look for; if this test surfaces any reminder-related UI text, that would be a NEW finding, not the previously-expected one.) |
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

## Phase 6 — Shadow Pipeline — RETIRED (2026-07-16)

The US/TSX and NSE shadow wallet pilots (FR24–FR31/NFR5, FR32–FR39/NFR6) were retired and their code
(`scripts/shadow.py`, `scripts/run_shadow.py`, `scripts/run_shadow_nse.py`, `scripts/wallet_sim.py`,
`scripts/eval_shadow.py`, both shadow SQL migrations, both workflow steps) deleted — see
the "Retired: shadow-pilot tracks" note in `docs/design.md` for the removal plan and `docs/requirements.md`'s
changelog for the retirement changelog entries. This phase (formerly P6-1..P6-5, covering the `SHADOW_ENABLED`/`SHADOW_NSE_ENABLED` kill
switches, prompt/model isolation, scope, concurrency safety, and the FR31 evaluation-harness gap) no
longer applies to any live code path and must not be re-run. Kept here, struck from the active plan,
for traceability only.

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

- `data_snapshot.market` nulls in pre-fix rows (P3-5) — expected historical artifact

> **2026-07-12 correction (REV-013):** This section previously also listed `notify.py`'s dead
> `kind="reminder"` path and "possible residual reminder handling in `detail.html`" (P1-2, P2-5, P4-5) as
> expected/don't-fix findings. Reviewer confirmed by reading current `scripts/notify.py` in full that this
> code path has been **fully removed**, not merely left unreachable (`docs/design/components.md` §4.6: "the
> `reminder` kind is retired"). Both entries have been removed from this list so a future executor doesn't
> go looking for a dead branch that no longer exists; the corresponding P1-2/P2-5/P4-5 cells above were
> updated to match.

## Blocking Dependencies

- **Issue #31** blocks P2-2, P3-5, P4-4 until the populate-from-`watchlist.market` fix lands. Mark BLOCKED, not FAIL.
