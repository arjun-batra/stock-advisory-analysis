# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## REV-055 test-coverage-gap fix — orchestrator decision-logic coverage — 2026-07-28

**Scope:** `docs/review-log.md` REV-055 (`[TEST-GAP]`, minor) — `tests/test_import_smoke.py:34-42` was the
only coverage touching `scripts/run_hourly.py`, `scripts/run_discovery.py`, `scripts/publish_prices.py`,
and it asserted only clean import + presence of `main()`. Five specific decision-logic paths, each tracing
to a past production defect (issues #2, #7, #8), had zero regression coverage:

1. `run_hourly._sessions()` (`run_hourly.py:34-49`) — which market session group(s) run for given US/TSX
   and NSE open/closed states, and that NSE draws its own model pair.
2. `run_hourly.main()`'s `FORCE_RUN`-with-everything-closed branch (`:130-134`) — a manual/backfill run
   outside all market hours must still process every group, not no-op.
3. `run_hourly.main()`'s both-sessions-open warning (`:113-117`) — sessions are designed never to overlap;
   if they ever do, the run must say so loudly and still process both groups.
4. `run_hourly.main()`'s `partial`-vs-`ok` heartbeat rule (`:154-156`) — issue #2: any skip or error in the
   run must demote the heartbeat off a clean `ok`.
5. `run_discovery.main()`'s quiet-day-vs-screener-failure distinction (`:55-66`) — issue #8: zero candidates
   with screens erroring must report `partial`, never mask as a genuine quiet day.

No FR/NFR IDs changed; this is qa-only test-suite work per the reviewer's finding, no dev/design changes.

### What qa did

Read the current implementations of all five behaviors directly in `scripts/run_hourly.py` and
`scripts/run_discovery.py` before writing anything (verified against code, not the review-log description).
Reviewed `tests/test_state.py` (the `FakeSupabase`/`FakeNotifier` in-memory Supabase double and the
`_wl_row`/`_data`/`_ai` builders) and `tests/conftest.py` (shared fixture/patching conventions) to follow
the suite's existing patterns rather than inventing new ones.

Added `tests/test_run_orchestration.py` (new file — existing test files are split one-per-`scripts/`-module,
and no single existing module owns `run_hourly.py`+`run_discovery.py` orchestration logic, so a dedicated
file fits the established split better than bolting onto `test_import_smoke.py`, which is deliberately
import-only per its own docstring). **13 new tests:**

- `_sessions()` (pure function, 3 tests): US/TSX-open/NSE-closed with default models; NSE-open with its own
  `nse_models()` pair; both-closed (real weekend gate, no monkeypatch).
- `run_hourly.main()` end-to-end against `FakeSupabase`/`FakeNotifier`, patching only the true I/O seams
  (`ingest.get_market_data`, `ai_judge.judge_batch`) as needed (7 tests): all-closed-no-force is a no-op
  (heartbeat never written); `FORCE_RUN` with everything closed runs BOTH groups (verified via per-group
  ticker-count log lines, not just the message text); both-sessions-open prints the WARNING and still
  processes both groups; no warning when only one session is open; heartbeat `partial` on a skip; heartbeat
  `ok` on an all-clean run (real ticker through `state.process_ticker`, not a degenerate empty watchlist);
  heartbeat `partial` on a mid-run ingest exception.
- `run_discovery.main()` against `FakeSupabase`/`FakeNotifier`, patching `prefilter.find_candidates` (3
  tests): all-screens-ok zero-candidates day reports `ok`; some-screens-errored zero-candidates day reports
  `partial` with the "NOT a quiet day" log line; all-screens-errored is still `partial` (not further
  differentiated, correctly).

### Suite result

**Run:** `python -m pytest -q --tb=short` (repo root).

- Before: **144 passed / 0 failed**.
- After: **157 passed / 0 failed** (13 new, zero regressions, zero collection errors).

### Shippability check

Not re-run this pass — no production code changed (test-only addition per REV-055's scope: "Owner: qa").
Last shippability confirmation remains the shadow-tracks-retirement entry in
`docs/archive/test-report-archive.md`.

### Bugs filed

**None.** All 13 new tests passed against the current implementation on first run — the five REV-055 gaps
now have regression coverage; no defect was found in `run_hourly.py`/`run_discovery.py` while writing it.

### Verdict

**PASS.** 157/157 full suite passing (13 new / 0 failed / 0 regressions). REV-055 closed from qa's side —
all five named decision-logic paths now have dedicated automated coverage.

---

## Open bugs

None.
