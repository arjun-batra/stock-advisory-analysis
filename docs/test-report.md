# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-6 — Admin portal tunables editor (FR30) — 2026-07-29

**Scope:** `sql/admin_portal_tunables.sql`, `tunables_cache.json`, `admin-portal/app/(app)/tunables/page.tsx`
(+ small edits to `admin-portal/components/AuthGuard.tsx`, `admin-portal/lib/validation.ts`),
`scripts/config.py`'s two-tier tunables fallback chain, `scripts/run_hourly.py`/`run_discovery.py`/
`publish_prices.py` (heartbeat + write-back wiring), `.github/workflows/hourly-watchlist.yml`/
`publish-prices.yml` (concurrency rename, job-scoped permissions, commit step), `tests/conftest.py`.
Branch: `claude/admin-portal-evaluation-txaehj`, commit `b2934c1`. Design: `docs/design/admin-portal-
tunables.md`, `docs/design/tunables-fallback.md`, `docs/design/tunables-workflow-writeback.md` (all
§16.4). Acceptance criteria: `docs/design/increment-plan.md` lines 189-282 (16 ACs). Dev's handoff:
`docs/handoff.md`.

**Session constraint, same as INC-5:** no live Supabase network access (org egress denies
`ikghqdtlbwifwnooytmm.supabase.co`) and no Supabase MCP / GitHub Actions dispatch tool bound to this
session. Every AC requiring a live migration apply, live RLS/CRUD, or a real workflow dispatch could
**not** be independently reproduced this run — reported as **deferred**, not as verified. See the
per-AC table below.

### Independent verification of dev's two flagged claims

1. **"168 passed, 3 failed, all three intended, not regressions."** Independently re-ran the pre-existing
   suite before adding anything: reproduced **exactly** the same 168/3 split, same three test IDs
   (`test_nse_model_pair_inherits_watchlist_pair_by_default`,
   `test_discovery_min_market_cap_override_propagates`,
   `test_heartbeat_is_ok_when_every_ticker_processes_cleanly`). Read all three failures against the new
   design contract, not the claim:
   - The two `test_config.py` failures set `GEMINI_MODEL`/`DISCOVERY_MIN_MARKET_CAP` via env var and
     asserted propagation. Both keys are curated tunables as of Decision #27 — `scripts/config.py:194,
     313` sources them only from `_tunable()` (table → cache), never `os.environ`; confirmed by reading
     the code, not inferring it. **Genuine, intended contract change — updated, not a regression.**
   - `test_heartbeat_is_ok_when_every_ticker_processes_cleanly` asserted `status == "ok"` for a clean
     ticker run. `tests/conftest.py`'s new `SKIP_TUNABLES_FETCH=true` default makes every curated key
     resolve from tier 2 for the whole suite, so `config.TUNABLES_DEGRADED` is `True` throughout, and
     `run_hourly.py:161`'s `status = "partial" if (degraded or config.TUNABLES_DEGRADED) else "ok"`
     correctly reports `"partial"`. **Genuine, intended (AC14/REV-045) — the test conflated two
     independent conditions (ticker cleanliness vs. tunables degradation) that INC-6 correctly split.**
   - **Verdict: all 3 are confirmed-intended contract changes, not regressions.** Fixed in `tests/`
     (below), not in production code. Full suite is now 201 passed, 0 failed: 171 baseline (168 passed +
     3 failed, all 3 now fixed forward rather than carried as red) + 30 new tests (28 in
     `test_tunables.py`, 1 in `test_config.py`, 1 in `test_run_orchestration.py`).
2. **The stale-permissions-premise account.** `git log --oneline -- .github/workflows/hourly-
   watchlist.yml` shows exactly the sequence dev described: commit `920876f` ("release+pm+dev+qa: fix
   Pass 11 audit findings", dated 2026-07-28 04:53 UTC) added a **top-level** `permissions: {contents:
   read}` block, predating INC-6's build commit `b2934c1` (2026-07-29 04:07 UTC) by nearly a day.
   `docs/design/tunables-fallback.md`'s premise ("hourly-watchlist.yml has no permissions: block at all
   today") was accurate when drafted (2026-07-27/28) but stale by the time INC-6 built. **Account
   confirmed accurate via `git log -p`, independently, not taken on trust.** The resulting file was also
   independently confirmed to satisfy AC16's literal text: exactly one `permissions:` block in the file,
   indented under `jobs.watchlist` (`grep -n permissions:` → line 45 only, inside the job body, no
   top-level occurrence) — `tests/test_tunables.py::test_ac16_permissions_block_is_job_scoped_not_top_level`
   locks this in permanently.

### What was added / changed in `tests/`

- **New `tests/test_tunables.py`** (28 tests) — the two-tier fallback chain end to end. Two techniques,
  both established by the design itself (`tunables-fallback.md` REV-041's "single patchable seam" note):
  (a) most tests monkeypatch `config._TUNABLES`/`_TUNABLES_CACHE`/`_CACHE_PATH` directly and call
  `_tunable()`/`write_tunables_cache_if_fetched()` — no reload needed; (b) tests needing a real tier-1
  fetch to run (AC5/AC10/AC13 propagation) patch `supabase.create_client` before `reload_config()`
  reloads `config.py`. Covers AC2 (byte-for-byte seed diff, independent of dev's own diff), AC5 (import-time-
  only pickup, empty-string-is-a-value edge case), AC8 (static: only `run_hourly.py` calls the writer),
  AC9 (direct-unit + a real subprocess `import config` reproduction in an isolated tmp-copy of `scripts/`
  — never touches the real repo `tunables_cache.json`), AC10 (both AND-gate directions, mocked table
  fetch), AC12 (validate-before-write, never-shrinks, tier-1 cast-failure fails loud), AC13 (timeout
  default/override, timeout actually reaches `ClientOptions`, zero network calls under
  `SKIP_TUNABLES_FETCH` via a `socket.socket.connect` trap), AC14 (degraded → heartbeat at
  `run_discovery.py`/`publish_prices.py`, both the degraded and not-degraded halves), and AC11/AC15/AC16
  as durable structural checks over the current workflow YAML content (not a git-diff-against-a-commit,
  which would break on the next increment's commits — the one-time diff-vs-baseline for *this* increment
  was confirmed directly via `git diff`, see above/below, not encoded as a standing test).
- **New `tests/admin_portal/tunables_static.test.ts`** (13 tests) — closes the gap dev flagged in Known
  Limitations ("no admin-portal-side test yet exercises the new `/tunables` page"). Static/source-level,
  same convention as `static_source_checks.test.ts`: `tunables` table RLS-enabled, CHECK registry is
  exactly the 10 keys, `admin_write_tunables` policy is `select, update` only (not `for all`), zero
  insert/delete policy, `updated_at`/`updated_by` server-stamped by trigger; portal page's `.update()`
  call sends exactly `{ value }` (never `id`/`key`/`updated_at`/`updated_by`), no `.insert()`/`.delete()`
  against `tunables`, reads via `.from("tunables").select("*")`; `AuthGuard` nav includes `/tunables`;
  `validateTunableValue` happy path / whitespace edge case / empty invalid-input case.
- **Updated `tests/test_config.py`** — `test_nse_model_pair_inherits_watchlist_pair_by_default` rewritten
  to test only the inheritance mechanism itself (unaffected by INC-6), since it can no longer prove
  inheritance by setting `GEMINI_MODEL` via env var; added
  `test_gemini_model_env_var_no_longer_has_any_effect` to explicitly cover that half of the new contract.
  `test_discovery_min_market_cap_override_propagates` renamed to
  `test_discovery_min_market_cap_resolves_from_cache_not_env_var` and rewritten the same way.
- **Updated `tests/test_run_orchestration.py`** — `test_heartbeat_is_ok_when_every_ticker_processes_cleanly`
  now neutralizes `config.TUNABLES_DEGRADED = False` so it isolates the ticker-cleanliness half of the
  "ok" rule it was originally written for; added
  `test_heartbeat_is_partial_when_tunables_are_degraded` as the sibling assertion for the degraded half
  (AC14, `run_hourly.py`).
- No production code touched by qa, per `CLAUDE.md`.

### Suite results

- **Python:** `python3 -m pytest -q --tb=short` → **201 passed, 0 failed** (was 168 passed/3 failed on
  dev's handoff; the 3 failures are fixed here as described above, and 30 new tests added: 28 in
  `test_tunables.py` + 2 net-new in `test_config.py`/`test_run_orchestration.py`).
- **Admin-portal JS/TS:** `node --experimental-strip-types --test tests/admin_portal/*.test.ts` →
  **39 passed, 0 failed** (26 pre-existing + 13 new in `tunables_static.test.ts`).
- **Lint:** `npx eslint .` (admin-portal) → clean, zero errors/warnings.

### Shippability check (real entry point)

`npm run build` (real `next build`, not dev mode) with disposable `qa-test-marker-...` env values:
succeeded, `/tunables` appears in the route table alongside `/`, `/login`, `/watchlist`, `/holdings`,
statically prerendered. `next start -p 3312` + `curl`:
- `GET /tunables` (no session) → 200, renders `AuthGuard`'s "Checking session…" shell — same pattern as
  INC-5's `/watchlist`/`/holdings` (client-side redirect after hydration; RLS is the real server-side
  gate regardless of what the shell renders pre-hydration).
- `GET /` → 200.
No server errors in the `next start` log. `.next/` build artifact cleaned up afterward.

### Acceptance criteria — per-AC verdict

| AC | Verdict | Evidence |
|---|---|---|
| 1. `tunables` seeded w/ 10 FR30 keys, `ALERTS_ENABLED="true"` | **PASS (static+live-seed-diff); RLS/CRUD live-behavior DEFERRED** | SQL migration shape/CHECK/seed values confirmed by direct read + `tunables_static.test.ts`. Live RLS rejection and live CHECK-constraint violation need the migration applied to the real project (not done — same as INC-5's `sql/admin_portal_rls.sql` pattern; orchestrator applies post-handoff). |
| 2. `tunables_cache.json` byte-for-byte matches SQL seed | **PASS — independently re-verified** | `test_ac2_cache_seed_matches_sql_seed_byte_for_byte` diffs the two files directly (own transcription, not reused from dev's diff); `ALERTS_ENABLED: "true"` confirmed in both. |
| 3. Anon/no-session write rejected; admin insert/delete rejected; bad `key` fails CHECK | **PASS (static shape); live curl DEFERRED** | Policy text confirmed `for select, update to authenticated`, not `for all`; zero insert/delete policy exists (RLS-enabled + zero policy = denied by construction). No live Supabase to fire the actual `curl`/insert/delete attempts. |
| 4. Update stamps `updated_at`/`updated_by` server-side, visible on next read | **PASS (static trigger shape + portal never sends those fields); live round-trip DEFERRED** | Trigger body confirmed (`new.updated_at := now()`, `new.updated_by := coalesce(auth.jwt()->>'email', session_user)`); portal's `.update()` call confirmed to send only `{ value }` (`tunables_static.test.ts`). No live write to round-trip through `select *`. |
| 5. `_tunable()`-derived values pick up an edit on next process start only | **PASS — independently re-verified** | `test_ac5_table_edit_propagates_on_next_process_start` + `test_ac5_resolved_value_does_not_change_mid_process` (mocked tier-1 fetch, real `importlib.reload`). |
| 6. Cache write-back, unchanged case: zero commits | **DEFERRED** | Needs a live `hourly-watchlist.yml` dispatch against an unmodified live table. |
| 7. Cache write-back, changed case: exactly one `github-actions[bot]` commit | **DEFERRED** | Needs a live dispatch + a portal edit against the applied migration. |
| 8. Read-only workflows never write | **PASS — independently re-verified** | `test_ac8_run_discovery_and_publish_prices_never_call_write_tunables_cache` / `test_ac8_run_hourly_calls_write_tunables_cache_exactly_once` (static source checks, own greps, not reused from dev's). |
| 9. Double-failure fails loud, non-zero exit | **PASS — independently re-verified** | `test_ac9_direct_double_miss_raises_systemexit_naming_the_key` (unit) + `test_ac9_entry_point_import_exits_nonzero_on_double_miss` (real `import config` subprocess in an isolated tmp copy of `scripts/`, no real cache file touched) + `test_ac9_corrupted_cache_file_is_treated_as_a_miss`. |
| 10. `ALERTS_ENABLED` AND-gate direction (both halves) | **PASS — independently re-verified, both directions** | `test_ac10_table_false_suppresses_a_scheduled_default_true_run`, `test_ac10_manual_dry_run_input_suppresses_even_when_table_true`, `test_ac10_both_true_is_the_only_combination_that_alerts` (mocked tier-1 fetch — dev had only unit-proved the formula and left this AC's live half deferred; qa closed it using the seam the design built specifically for this). |
| 11. Workflow diff scope (`daily-discovery.yml` untouched; `publish-prices.yml` one line; `hourly-watchlist.yml` limited to 3 changes) | **PASS — independently re-verified via `git diff` this session, plus durable structural tests** | `git diff 1f48e45 b2934c1 -- .github/workflows/*.yml` confirmed the exact scope by hand; `test_ac11_*` tests lock in the durable structural properties (no `tunables` references in `daily-discovery.yml`/`publish-prices.yml`) so future commits don't silently regress this. |
| 12. (REV-036) Write-back validates, never shrinks | **PASS — independently re-verified** | `test_ac12_write_back_never_shrinks_and_rejects_bad_casts`, `test_ac12_write_back_is_a_noop_when_this_runs_fetch_entirely_failed`, `test_ac12_tier1_cast_failure_fails_loud_never_reaches_cache_write`. |
| 13. (REV-041) Timeout tunable + offline seam | **PASS — independently re-verified** | `test_ac13_timeout_tunable_default_and_override`, `test_ac13_timeout_is_actually_passed_into_client_options` (asserts the real `ClientOptions.postgrest_client_timeout` value, not just the env var), `test_ac13_skip_tunables_fetch_makes_zero_network_calls` (a `socket.socket.connect` trap — proves zero calls, not just "no exception seen"). |
| 14. (REV-045) `TUNABLES_DEGRADED` reaches heartbeat at all 3 entry points | **PASS — all 3 entry points, including BUG-003 fix** | `run_hourly.py`: `test_heartbeat_is_partial_when_tunables_are_degraded` (test_run_orchestration.py). `publish_prices.py`: `test_ac14_publish_prices_heartbeat_is_partial_when_degraded_even_with_zero_skips` / `..._is_ok_when_not_degraded...`. `run_discovery.py`: PASS for the normal candidate-processing path (`test_ac14_run_discovery_heartbeat_is_partial_when_degraded_even_with_a_clean_candidate_run`); the zero-candidates/no-screen-errors early-return branch (`run_discovery.py:59`) originally hardcoded `"ok"` and never consulted `config.TUNABLES_DEGRADED` — found via `test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded`, filed as **BUG-003** and since **FIXED** by dev (commit `799cd35`): the branch now ORs in `config.TUNABLES_DEGRADED` (`if screens_errored or config.TUNABLES_DEGRADED:`), and the same test now asserts `"partial"`. See Gaps/Open Bugs sections below for full history. |
| 15. (REV-040a) Shared concurrency group prevents the race | **PASS (structural); live race/serialization DEFERRED** | `test_ac15_hourly_and_publish_prices_share_the_repo_commit_concurrency_group` confirms both files use `group: repo-commit`, neither still says the old per-file group name. Live two-dispatch race/serialization proof needs GitHub Actions dispatch access. |
| 16. (REV-040b) Push retry fires; permissions job-scoped | **PASS (structural); live retry-firing DEFERRED** | `test_ac16_permissions_block_is_job_scoped_not_top_level` (confirms zero top-level `permissions:`, job-scoped `contents: write` present — this is the stale-premise-independent-verification test) + `test_ac16_commit_step_has_a_bounded_retry_loop_with_error_annotation` (retry loop, `::error::` message present). Live lost-race/retry-firing proof needs a real workflow run. |

### Gaps / bugs found this session

**BUG-003 — AC14 (REV-045): `run_discovery.py`'s zero-candidates early-return branch doesn't consult
`config.TUNABLES_DEGRADED`.**
- **Increment:** INC-6. **FR/NFR:** FR30 / REV-045 (design: `docs/design/tunables-fallback.md` lines
  280-288, increment-plan.md AC14).
- **Repro:** `tests/test_tunables.py::test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded`
  — mock `prefilter.find_candidates` to return zero candidates with zero screen errors, set
  `config.TUNABLES_DEGRADED = True`, run `run_discovery.main()`.
- **Expected (per AC14's literal text, "all three entry points"):** `run_heartbeat.status == "partial"`.
- **Actual:** `run_heartbeat.status == "ok"` — `run_discovery.py:64` (`state.write_heartbeat(sb,
  heartbeat_key, "ok")`) is a hardcoded literal in the early-return branch, never OR'd with
  `config.TUNABLES_DEGRADED` the way the later computed `status =` line (`run_discovery.py:115`) is.
- **Note:** dev already surfaced this exact gap in `docs/handoff.md`'s Known Limitations, reading the
  brief's "the existing status-computation line" (singular) narrowly to exclude this branch, and
  explicitly asked tech-lead/qa to confirm scope. This is a genuine open design-scope question, not
  clearly a coding mistake — routing to dev/tech-lead to decide (fix the branch to include
  `config.TUNABLES_DEGRADED`, or amend AC14's text to carve out the zero-candidates case) rather than
  qa deciding unilaterally by editing production code.
- **Status:** FIXED (dev). `run_discovery.py:59`'s early-return branch now ORs in
  `config.TUNABLES_DEGRADED` (`if screens_errored or config.TUNABLES_DEGRADED:`), mirroring the later
  computed `status =` line. `test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded`
  updated to assert `"partial"` (was pinning the gap). Full suite re-run clean, no regressions.

**No other functional bugs found.** All other code-level checks this session (fallback-chain behavior,
write-back validation, workflow YAML structure, portal RLS/UI shape) match their design/requirement text
exactly.

### Verdict

**PASS. BUG-003 found this session and FIXED by dev (commit `799cd35`); no bugs remain open.** Python:
201/201 passed (0 regressions from a 168/3 baseline — the 3 were confirmed intended and are now fixed
forward in `tests/`, not carried as red). Admin-portal JS/TS: 39/39 passed (13 new). Shippability: real
`next build` + `next start` serves `/tunables` and every other route correctly. 12 of 16 ACs independently
re-verified this session (AC2, AC5, AC8, AC9, AC10, AC11, AC12, AC13, AC14, AC15 structural, AC16
structural); AC1/AC3/AC4/AC6/AC7's live-project halves and AC15/AC16's live-dispatch halves remain
deferred pending live Supabase/GitHub Actions access (same constraint as INC-5). Both of dev's flagged
claims (the 3-failure characterization, the stale-permissions-premise account) were independently
confirmed accurate via direct re-execution and `git log -p`, not taken on trust. No production code
modified by qa.

---

## Open bugs

**BUG-003** — `run_discovery.py`'s zero-candidates/zero-screen-errors early-return branch doesn't OR in
`config.TUNABLES_DEGRADED` before writing the heartbeat status (AC14, FR30/REV-045). See INC-6 section
above for full repro. **FIXED** — dev OR'd in `config.TUNABLES_DEGRADED` at the early-return branch
(`run_discovery.py:59`); the locking test now asserts `"partial"`.
