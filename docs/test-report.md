# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-11 — Live-verification pass (Decision #36) — 2026-07-30

**Not a qa-executed run.** Subagents have no Supabase/GitHub credentials this session; the orchestrator
executed these live checks directly and handed the raw results to qa to record per doc-hygiene/attribution
rules. Raw evidence blocks are in `docs/handoff.md` ("Evidence record: INC-11 live-verification pass",
appended after the INC-12 entry) — **run by: orchestrator**, not qa, not dev. This entry only flips the
per-AC status table `docs/design/increment-plan.md`'s INC-11 section calls for.

| Item | Status | Evidence |
|---|---|---|
| Live DB Postgres major version | **CONFIRMED: 17.6.1** | Resolves the residual PG14+ assumption carried forward as an open INC-11 prerequisite in `docs/archive/test-report-archive.md`'s BUG-008 fix-cycle-1 entry and `docs/handoff.md`'s "BUG-008 fix (fix cycle 1 of 3)" section — no longer an assumption. `create or replace trigger` (PG14+) is safely below the live floor. |
| INC-3 AC3 (resume-baseline / no-false-alarm under a real pause/resume cycle) | **PASS — 2026-07-30** | `kill_switch_state.paused` false→true at `19:12:47.594Z`; `dispatch_github_workflow('hourly-watchlist.yml','{}')` returned `null` and created no workflow run (scheduled dispatches run at :00/:30; last real run `19:00:01Z`, none at `19:12`); resumed `19:12:57.378Z`. `kill_switch_audit` gained exactly two new rows, one per toggle — also independently reconfirms **AC4** (previously passed 2026-07-29 against a different pause/resume cycle). **Caveat:** actor was `postgres` — this exercised the service-role path, not the portal's `is_admin()` path (see INC-7 row below). |
| INC-4 AC6 (live Gemini smoke test) | **PASS — 2026-07-30** | 90 `call_log` rows in the trailing 3h to `19:01:42Z`, every row `parse_status='ok'`, `model_used='gemini-2.5-flash'`, `fallback_from=null` — 90 consecutive successful live Gemini calls, stronger than a one-off smoke test. |
| INC-7 Step 0 (confirm `sql/kill_switch_portal_grant.sql` is live) | **PASS — 2026-07-30** | `admin_read_kill_switch` policy live on `kill_switch_state` (SELECT/`authenticated`/`is_admin()`); `set_kill_switch(boolean,text)` live, containing the `is_admin()` check. |
| INC-7 AC2/AC3 (portal RPC round-trip + live dispatch-suppression, via an authenticated admin **portal** session) | **STILL OPEN — not done.** | Needs a real authenticated admin browser session; none available to any subagent or the orchestrator this session. Not to be inferred from INC-3 AC3's service-role proof above — that's a materially different auth path (see caveat). |
| INC-10 SQL objects applied live | **PASS — 2026-07-30 (supplementary, not one of INC-11's three named items, folded in the same pass)** | `inc10_tunables_validate_trigger`, `inc10_holdings_currency_derivation`, `inc10_alerts_enabled_description_fix` all confirmed live: both triggers present and enabled, `tunables_0_validate_update` sorts before `tunables_stamp_update` (correct fire order). **DEEP-005 proven closed live:** `update tunables set value='yes' where key='ALERTS_ENABLED'` rejected inside a rolled-back transaction with `tunables.value for key ALERTS_ENABLED must be exactly "true" or "false" (case-insensitive), got yes`; live value still `true`, description corrected. |

**Net effect on `docs/requirements.md` traceability:** FR24–FR26 and FR33 can now be considered delivered
(not merely "deferred, pending live execution") per increment-plan.md's INC-11 AC3. FR31/FR32 (admin
portal kill-switch UI) remain delivered-pending-live-verification for the **portal's own** authenticated
path specifically (INC-7 AC2/AC3) — pm should carry this distinction into Phase-4 closure, not collapse it
into "done" on the strength of INC-3 AC3's service-role proof.

---

## INC-12 — kill-switch in-flight boundary checks + mid-run-abort classification (FR24, FR35; closes DEEP-007) — 2026-07-30

**Scope.** dev handoff at commit `530c687`. Read `docs/design/increment-plan.md`'s `### INC-12`,
`docs/design/operational-controls.md` §13.6 (all five subsections), `docs/requirements.md` FR24/FR35 +
Decisions #37/#38, and `docs/handoff.md`'s INC-12 entry. No test files existed for any of this
increment's behavior before this pass (dev verified everything with a scratch harness that no longer
exists, per the increment's own "no test files" scope). New file: `tests/test_kill_switch_boundary.py`
(22 tests). No production code touched; `sql/kill_switch_abort_log.sql` was **not** applied live (per
instruction) — re-verified re-runnable against a local scratch Postgres, not the live project.

### The load-bearing property — made permanent

`KillSwitchAbort` subclasses `BaseException`, not `Exception`, specifically so it survives the
pre-existing `except Exception` guard in `_process_group`'s Phase-3 loop without being miscounted into
`outcomes["error"]` — exactly what FR35 forbids. Two permanent tests now guard this independently of
`run_hourly.py`'s internals (`test_kill_switch_abort_subclasses_base_exception_not_exception`,
`test_kill_switch_abort_is_not_caught_by_a_bare_except_exception`) plus one end-to-end trace against the
real orchestrator code confirming no `ERROR MSFT`/`KillSwitchAbort` text appears in a real aborted run's
output (`test_kill_switch_abort_propagates_through_process_group_uncounted_in_error`). All three pass;
reverting the base class to plain `Exception` locally makes the first two fail immediately (spot-checked).

### AC-by-AC (increment-plan.md's `### INC-12`)

1. **PASS** — `is_paused()` returns the mocked flag in both states.
2. **PASS** — call-site counts made permanent via regex against the real source files (not a one-off
   grep): exactly 2 in `run_hourly.py`, 2 in `run_discovery.py`, 2 in `state.py`, 1 in
   `publish_prices.py`; `class KillSwitchAbort(BaseException):` appears exactly once.
3. **PASS** — checkpoint 1 (`run_hourly.main()`, `run_discovery.main()`) and checkpoint 4
   (`publish_prices.main()`) call none of the six named functions when paused; `publish_prices.main()`
   additionally confirmed to leave the output file untouched (checkpoint 4 is placed *after* Yahoo
   fetches, only before the write — per design, not a defect).
4. **PASS** — checkpoint 2 abort (both `run_hourly.py` and `run_discovery.py`): `judge_batch` never
   called, `write_heartbeat` never called, one `kill_switch_abort_log` row with `checkpoint="ai_call"`,
   correct `workflow`, `real_rows_this_cycle=0`.
5. **PASS** — checkpoint 3 mid-run abort: the aborted ticker's `verdict_state` and `call_log` are left
   byte-identical to before the cycle touched them; exactly one abort row, `checkpoint="push"`,
   `real_rows_this_cycle` equal to the real-outcome count already produced this cycle (1); no heartbeat
   row.
6. **PASS** — resume: a subsequent run with the kill switch off pushes the pending ticker and advances
   its `verdict_state`, with zero additional code, confirming FR35's resume claim.
7. **PASS** — see "load-bearing property" above; same run proves the propagation.
8. Live-SQL half — **not re-applied live this pass** (explicit instruction); re-verified re-runnable
   against a local scratch Postgres (RLS+FORCE both `true`, `anon` denied SELECT/INSERT). Live
   `check_pipeline_health()` non-alerting proof against a real dispatched run remains release/live-
   verification territory, per the increment plan's own text (not a merge blocker).
9. **PASS** — full suite green, `git status --porcelain` shows only the new test file.

### Edge probes beyond the ACs

- **Pause observed strictly between checkpoint 2 and checkpoint 3** — covered
  (`test_pause_flips_between_checkpoint2_and_checkpoint3`): checkpoint 2 passes, the very next
  checkpoint-3 read catches it. No new call_log/verdict_state writes; one `checkpoint="push"` row.
- **Checkpoint-3 abort on the first ticker of a cycle** — `real_rows_this_cycle=0` on a **push**
  checkpoint, distinct from checkpoint 2's own zero-row sub-case (§13.6.3). Confirmed with its own test;
  both are legitimate, both correctly non-alerting.
- **`is_paused()` itself failing (Supabase unreachable)** — behavior differs materially by checkpoint,
  and neither path silently proceeds as if unpaused:
  - **Checkpoint 1**: outside any try/except in `main()`. A real exception from `is_paused()` propagates
    fully uncaught, crashing the run before any Yahoo fetch/AI call/push. Fail-**closed** with respect to
    the irreversible action (nothing downstream ever runs), but as a loud, alerting crash — correctly
    **not** classified as a deliberate pause (no `kill_switch_abort_log` row), so NFR2 alerting is not
    suppressed. This is the FR24-correct posture: never silently proceed as unpaused when the pause state
    can't be determined.
  - **Checkpoint 3**: sits inside `process_ticker`/`process_candidate`, which `_process_group`'s Phase-3
    loop already wraps in `except Exception`. A real (non-`KillSwitchAbort`) exception from `is_paused()`
    there **is** caught by that pre-existing guard, counted as an ordinary `outcomes["error"]`, and does
    **not** crash the whole run or block other tickers — a materially different, gentler fail mode than
    checkpoint 1's hard crash, but still correctly alerting (`run_heartbeat.status="partial"`) and still
    never misclassified as a pause. Confirmed with a dedicated test for each checkpoint.
  - Net answer to "fail open or closed": **closed**, in both cases — the guarded irreversible action never
    executes on a failed pause-check — but the *blast radius* differs (whole-run crash at checkpoint 1 vs.
    a normal per-ticker error at checkpoint 3), which is worth tech-lead/pm awareness even though neither
    is a bug against FR24's actual text.
- **Two aborts in one run** — proven impossible by construction: `main()`'s `try/except` wraps the entire
  `for s in run_sessions` loop, not each group individually, so the first `KillSwitchAbort` to propagate
  ends the function immediately. Verified with both US/TSX and NSE open simultaneously: the second group's
  `_process_group` is never entered, `judge_batch` is called zero times, exactly one abort row is written.

### `real_rows_this_cycle` excludes `outcomes["skip"]` — design question, already routed to tech-lead

Confirmed the implemented behavior matches the design's literal code sample (§13.6.2): a skip (which does
write its own `call_log` row via `state.log_skip`) is **not** counted into `real_rows_this_cycle`, only
`cold-start`/`quiet`/`change-alert`/`push-failed`/`no-read` are. Not filed as a bug — dev implemented
exactly what the design specifies, and the brief that commissioned this pass says this is already routed
to tech-lead as an open design question. Flagging qa's own read for the record: FR35's prose ("has already
written at least one real (non-skip) `call_log` row") reads as if a skip-with-a-row should count toward
"real," while the design's code sample explicitly excludes it — a genuine textual tension between FR35 and
§13.6.2, not a code defect either way `real_rows_this_cycle` is purely informational (§13.6.5's own
comment: "NOT a gating condition"), so nothing behavioral hinges on the resolution.

### Regression

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **275 passed, 0 failed** (baseline 253 + 22
  new in `tests/test_kill_switch_boundary.py`).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed**
  (unchanged — this increment touched no TypeScript).
- Shippability: `python3 -c "import run_hourly, run_discovery, publish_prices, state"` → all import
  cleanly; `issubclass(state.KillSwitchAbort, BaseException) is True` and
  `issubclass(state.KillSwitchAbort, Exception) is False` reconfirmed directly against the real module
  (not just through a test fixture).
- `git status --porcelain` → only `tests/test_kill_switch_boundary.py` added; no production code, no SQL
  applied.

### Verdict — INC-12

**PASS.** All 9 literal ACs independently verified with permanent, committed tests (not accepted on dev's
scratch-harness account). The one property flagged as most load-bearing — `BaseException` propagation
uncounted in `outcomes["error"]` — now has dedicated, implementation-independent coverage. No bugs filed.
No production code touched.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass. Full detail:
`docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
