# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-8 — Degraded-run visibility + delivery-confirmed alerting (NFR2, FR15, FR34; DEEP-001+DEEP-002) — 2026-07-30

**Scope.** `scripts/state.py`, `scripts/notify.py`, `scripts/run_hourly.py`, `scripts/run_discovery.py`,
`pages/dashboard.html` (`git diff --name-only 087f5dd..feaf58b` confirms exactly these five files + `docs/
handoff.md`). Read against `docs/design/increment-plan.md`'s INC-8 section (8 ACs),
`docs/design/components.md` §4.6/§4.8, `docs/design/data-and-flow.md` §6, `docs/requirements.md`
NFR2/FR15/FR34 + Decisions #31/#32, and `docs/review-log.md` DEEP-001/DEEP-002 — not from dev's summary.

### 1. Baseline reconciliation (dev claimed 207, `test-report.md`'s last full-system entry recorded 204)

**Both were correct at their own point in time — not a contradiction.** Stashed dev's INC-8 diff and ran the
suite against the immediate pre-INC-8 commit (`087f5dd`): **207 passed, 0 failed**, confirming dev's stated
baseline exactly. The archived Phase-4 entry's "204" was recorded at commit `34e94d9`, three commits before
`eb859b5` ("fix: add `ingest.get_price_only()`...", REV-043) added exactly 3 new tests to
`tests/test_ingest.py`. 204 + 3 = 207 — the true, reconciled pre-INC-8 baseline is **207 passed, 0 failed**;
the "204" figure was already stale by the time INC-8 started, for reasons unrelated to INC-8.

### 2. Verifying dev's claim on the 8 failures (not accepted on account)

Ran the suite against dev's INC-8 commit (`feaf58b`) independently: reproduced the exact same **199 passed,
8 failed**, all in `tests/test_notify.py`/`tests/test_state.py`, as dev reported. Read every failing
assertion against the actual new contract in `scripts/notify.py`/`scripts/state.py` (behavior, not diff) and
against `docs/design/components.md` §4.6's specified return contract before touching anything. Per-failure
classification:

| Test | Classification | Why |
|---|---|---|
| `test_notify.py::test_ntfy_notifier_swallows_network_errors_without_crashing` | **Old-contract assertion — fixed** | Asserted the retired `"[notify error]"` log substring; AC4 explicitly requires the new, distinct `[notify] ERROR push failed for {ticker}: ...` line (confirmed present via behavior, not read from the diff). Not a defect — the new line is correct and required. |
| `test_state.py::test_any_verdict_change_fires_immediate_alert` (6 parametrized cases) | **Old-contract assertion — fixed** | `FakeNotifier.push()` had no `return` (implicit `None`). Under the *old* contract the return value was never read; under FR34, `None` means "dry run," so `alerted` is correctly written `False` per the new contract, and the test's `assert ... is True` is checking behavior FR34 deliberately changed. This is DEEP-002's own finding, almost verbatim. |
| `test_state.py::test_discovery_buy_pushes` | **Old-contract assertion — fixed** | Same root cause as above, discovery side. |

**No real defect found among the 8.** Verified this conclusion against production behavior directly (not
just re-reading dev's own diagnosis): drove `state.process_ticker`/`process_candidate` with a
`FakeNotifier` configured to actually return `True`/`False`/`None` per FR34's three-valued contract and
confirmed `alerted`/`current_verdict`/outcome all match `components.md` §4.6 exactly (see §4 below) — the
production code is correct; only the shared test fixture encoded the old contract.

**Fix applied (`tests/`, qa's own file, not production code):** `FakeNotifier` (`tests/test_state.py`) now
takes `returns=True` (default — an ordinary successful send, matching what these pre-existing tests actually
intend) or `queue=[...]` (a scripted per-call sequence, used by the new AC5 retry test). `tests/
test_notify.py`'s two assertions updated to the new log line and now additionally assert the `bool`/`None`
return values themselves (the old test never checked `push()`'s return value at all).

**Separately found and fixed (not one of the 8, a latent gap, no bug filed — production code is correct):**
`test_ntfy_notifier_posts_to_correct_topic_url_mocked`'s mocked response object had a bare `status_code`
with no `raise_for_status()` method. Once `NtfyNotifier.push()` started calling `raise_for_status()` inside
its `try`, this "success" test's mock actually made `push()` return `False` via the caught `AttributeError`
— silently, since the test never asserted on the return value. Confirmed by direct execution (`result =
False` against the un-fixed mock). Fixed the mock to include a no-op `raise_for_status()` and added `assert
result is True`, so a genuine 2xx now provably exercises the `True` path this test's name claims to cover.

### 3. The three highest-stakes behaviors, tested directly

- **AI/Gemini failure fail-safe guard (`state.py:256`) — untouched, confirmed by behavior.** New tests
  `test_ai_failure_fail_safe_guard_is_untouched_by_delivery_gating` and the `api_error` variant wire a
  `FakeNotifier(returns=True)` (would deliver successfully if called) into a `parse_status="failed"`/
  `"api_error"` cycle and assert `notifier.calls == []` (push never even attempted),
  `current_verdict` unchanged, `alerted=False`. A regression here would fabricate advice; it does not occur.
- **Failed push → `alerted=False`, OLD verdict retained, automatic retry on next cycle** —
  `test_failed_push_leaves_state_pending_then_retries_and_succeeds` (AC5's exact named flow, one assertion
  block: fail once, confirm state pending, retry with the same new verdict, succeed, confirm state now
  advances).
- **Dry run → `alerted=False` but state DOES advance, no backlog dump** —
  `test_dry_run_push_logs_undelivered_but_still_advances_state_no_backlog` (AC6, both halves in one block
  per the AC's own reasoning, plus a following identical-verdict cycle confirmed genuinely `"quiet"`, not a
  second push).

**Also tested, not named by any single AC (flagged in the qa brief as the difference between a useful retry
and misleading advice):** `test_failed_push_then_verdict_changes_again_retries_current_not_stale_verdict` —
after a failed push leaves the crossing pending, if the AI's verdict changes AGAIN before the retry, the
retry pushes the CURRENT verdict, not a replay of the stale failed one. Passes.
`test_ai_failure_while_a_push_failed_crossing_is_pending_does_not_alert_or_advance` — interaction of both
DEEP-001/DEEP-002 fixes: an AI-call failure arriving while a push-failed crossing is already pending must
not disturb it (no push attempted, old verdict stays put). Passes.

### 4. New permanent tests added (AC-by-AC)

- **AC1** (`tests/test_run_orchestration.py`) — `test_heartbeat_is_partial_when_every_ticker_ai_call_fails`
  (both watchlist tickers `parse_status="failed"`/`"api_error"` → `run_heartbeat.status == "partial"`, the
  exact DEEP-001 scenario), `test_heartbeat_is_partial_for_mixed_no_read_and_quiet_batch` (one quiet + one
  no-read), `test_discovery_heartbeat_is_partial_when_every_candidate_ai_call_fails` (discovery side). All
  drive the REAL `run_hourly.main()`/`run_discovery.main()` entry points, not reimplemented logic.
- **AC4** (`tests/test_notify.py`) — `test_ntfy_notifier_returns_false_without_raising_on_non_2xx_response`
  (mocked 500, asserts `push()` returns `False` without raising, exactly as AC4 names), plus
  `test_dry_run_notifier_push_returns_none_explicitly`.
- **AC5/AC6/AC7** (`tests/test_state.py`) — see §3 above plus
  `test_discovery_candidate_dry_run_excluded_from_recent_pushed_dedup`,
  `test_discovery_candidate_failed_push_excluded_from_recent_pushed_dedup` (AC7, both undelivered paths),
  and `test_discovery_candidate_successful_push_is_deduped` (regression guard: a genuinely delivered push
  still IS deduped — proves the exclusion is delivery-status-driven, not a broken filter).
- **AC3** (`tests/test_dashboard_pill_logic.py`, new file) — see §5 below.
- **AC2/AC8** — verified by direct `grep`/`git diff` (matches dev's self-check; independently re-run, not
  taken on account).

### 5. AC3 — what could and could not be verified

No browser-automation tooling (playwright/puppeteer/selenium) is available in this environment (checked).
**The AC's own "manual/qa browser check" half — a real synthetic `call_log` row rendered and visually
confirmed in an actual browser — was NOT performed and remains genuinely unverified**, same posture as this
project's other environment-blocked live checks (e.g. INC-4 AC6). What was done instead, more rigorously
than dev's own throwaway (uncommitted) scratch script: `tests/test_dashboard_pill_logic.py` brace-matches
and extracts the REAL, current `botBlock()` function verbatim out of `pages/dashboard.html` and executes it
under real Node against synthetic rows for every relevant `parse_status`, asserting the actual rendered
HTML — not a source-text grep. Covers: `no_data`/`failed`/`api_error` all render the "no data" pill and
never a `Hold` pill; a genuine `parse_status="ok"` Hold/Buy/Sell still renders its real verdict pill
(regression guard the other direction); no `call_log` row renders nothing (FR21, pre-existing, guarded so
an INC-8 edit to the shared function can't silently break it); `pages/detail.html`'s pre-existing
`failed`/`api_error` special-case text is still present (confirms "no change needed there").

### 6. Regression suite

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **229 passed, 0 failed** (207 pre-INC-8
  baseline, 0 net regressions, +22 new INC-8 test cases: 9 new functions in `tests/test_state.py`, 2 in
  `tests/test_notify.py`, 3 in `tests/test_run_orchestration.py`, and `tests/test_dashboard_pill_logic.py`
  — new file, 6 functions / 8 test cases, one parametrized ×3 — the 8 pre-existing old-contract assertions
  were fixed in place, not added/removed, so the count doesn't include them).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **57 passed, 6 failed.** All 6
  failures are in `tests/admin_portal/build_bundle.test.ts` (`next build` fails in this environment:
  "Turbopack build failed... couldn't find the Next.js package... from the project directory"). **Confirmed
  pre-existing and unrelated to INC-8**, not a regression: re-ran the identical file against the pre-INC-8
  commit (`087f5dd`, before stashing/restoring dev's diff) and got the identical 6 failures with the
  identical error text — INC-8 touches zero `admin-portal/` files (confirmed by `git diff --name-only`
  above), so this is an environment/build-tooling issue in this execution sandbox, not a code defect from
  this increment. Not filed as an INC-8 bug (out of scope); flagged here for release/dev to investigate
  separately if it recurs outside this sandbox, since it diverges from the last recorded 63/63 baseline.

### 7. Shippability

- All three Python entry points (`run_hourly.py`, `run_discovery.py`, `publish_prices.py`) import cleanly
  under `SKIP_TUNABLES_FETCH=true`.
- `run_hourly.main()`/`run_discovery.main()` — the real entry-point functions, not reimplemented logic —
  driven end-to-end through `tests/test_run_orchestration.py`'s `wire_main`/`wire_discovery` fixtures
  (patches only the true I/O seams: Supabase client, notifier), including the new AC1 all-failed-batch
  scenarios above.
- `pages/dashboard.html` and `pages/detail.html`'s inline `<script>` blocks both pass `node --check` (no
  syntax error introduced).

### Verdict — INC-8

**PASS.** Python suite: 229 passed, 0 failed (207 baseline + 21 new, 0 regressions). TypeScript/admin-portal
suite: 57 passed, 6 failed — all 6 pre-existing and environment-caused, independently confirmed unrelated to
this increment's zero-`admin-portal/`-file diff. All 8 originally-failing tests were old-contract
assertions (not real defects); each fixed with its production-behavior classification recorded above, not
papered over. AC1, AC2, AC4, AC5, AC6, AC7, AC8 independently verified with new permanent tests or direct
grep/diff re-checks. AC3 is **partially** verified: the JS logic itself is proven correct against real
runtime execution (not just source grep), but the AC's own "actual browser" rendering check could not be
performed in this environment and remains open, consistent with this project's existing posture on
environment-blocked live checks — not treated as a silent PASS.

No bugs filed against production code — no defect was found in `scripts/state.py`, `scripts/notify.py`,
`scripts/run_hourly.py`, `scripts/run_discovery.py`, or `pages/dashboard.html`.

---

## Open bugs

None filed against INC-8. One environment observation carried forward (not a bug, not blocking): the
admin-portal TypeScript suite's `build_bundle.test.ts` (6 tests) fails in this execution sandbox on a
Turbopack workspace-root inference error, confirmed pre-existing (reproduces identically on the pre-INC-8
commit) and unrelated to any code this increment touched — see §6 above. Worth a release/dev look if it
recurs in CI, since it diverges from the last recorded 63/63 baseline.
