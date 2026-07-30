# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-12 fix cycle 1 — REV-116 (DEEP-007 residual) + REV-117 (SQL REVOKE gap) — verified 2026-07-30

**Scope.** Reviewer Pass 28 (`docs/review-log.md`) held `v0.1.0` NOT CLEAR on two majors: REV-116
(`run_hourly.py`'s `config.write_tunables_cache_if_fetched()` — a real `contents: write` commit path —
ran unconditionally as `main()`'s first statement, before checkpoint 1's pause read, so a paused run
could still commit to `main`) and REV-117 (`sql/kill_switch_abort_log.sql`'s `REVOKE` omitted
`truncate`). dev's fix-cycle-1 handoff at commit `fc0beab`. Read `docs/review-log.md` Pass 28's REV-116/
REV-117 entries, `docs/handoff.md`'s INC-12 fix-cycle-1 entry, and the changed
`scripts/run_hourly.py`/`sql/kill_switch_abort_log.sql` directly (not accepted on dev's account).

### REV-116 — the test problem, solved rather than worked around

**The trap.** Every test in the suite runs with `SKIP_TUNABLES_FETCH=true` (`tests/conftest.py`), which
empties `config._TUNABLES` at import time. `write_tunables_cache_if_fetched()`'s own
`if not _TUNABLES: return` guard then makes it a silent no-op **regardless of call ordering** — this is
exactly why 22 prior boundary tests (`tests/test_kill_switch_boundary.py`) all stayed green while the
defect was live: none of them could distinguish "the call happens after the pause check" from "the call
never does anything at all." Any future test author writing a boundary test in this file needs to know
this trap exists — a green suite alone does not prove an entry-point call site's position is correct if
the function it calls is masked by `SKIP_TUNABLES_FETCH`.

**The fix (`tests/test_kill_switch_boundary.py`, two new tests + one new fixture).** Added
`real_tunables_write_spy` (a fixture that deliberately bypasses the mask): it monkeypatches
`config._TUNABLES`/`config._TUNABLES_CACHE` directly with values that differ (so a real write would
actually occur), points `config._CACHE_PATH` at `tmp_path` (never touches the repo's real
`tunables_cache.json`), and wraps — not replaces — the real `write_tunables_cache_if_fetched` with a
call-counting spy, so the assertion is against the function actually doing its real merge/validate/write
work, not a stub that would pass regardless of where the call sits.
- `test_rev116_tunables_cache_write_not_reached_while_paused` — paused run, asserts 0 calls and no file
  written.
- `test_rev116_tunables_cache_still_refreshes_on_closed_market_when_not_paused` — market closed, no
  `FORCE_RUN`, not paused: asserts exactly 1 call, the file is written, and it contains the expected
  merged value — this is also the permanent regression test for the closed-market cache-refresh design
  property (see below).

**Confirmed the test genuinely fails on the pre-fix code, not just passes on the fixed code.** Per the
brief's explicit requirement not to ship a test that "cannot fail on the buggy code," loaded the pre-fix
`scripts/run_hourly.py` (`git show d875078:scripts/run_hourly.py`) into a scratch module via
`importlib.util.spec_from_file_location` under a distinct module name, without touching the working
tree, with `config`/`state`/`notify`/etc. still resolving to the real, current modules via `sys.path`.
Wired the identical `KillSwitchFakeSupabase`/spy setup and ran the paused scenario against that old
module: **`write_tunables_cache_if_fetched` was called 1 time and the cache file was written, while
paused** — the exact defect Pass 28 found, reproduced directly. Against the current (fixed) code the
identical scenario yields 0 calls, no file. The new test discriminates buggy from fixed code; it is not
decorative.

**Closed-market cache-refresh design property (`docs/design/tunables-fallback.md`) — holds.** dev
rejected the simpler fix (moving the tunables write below the old checkpoint-1 position) specifically
because that design doc states, as an explicit property, that the cache "refreshes on every dispatch
regardless of whether the market check inside `main()` goes on to skip work" — moving only the write
down would have silently broken that on every closed-market invocation (most of the day). Verified
directly: `test_rev116_tunables_cache_still_refreshes_on_closed_market_when_not_paused` (above) exercises
exactly this scenario against the real, fixed `run_hourly.main()` and confirms the write still fires
exactly once before the closed-market early return. Property preserved, not just claimed.

**Other entry points — independently confirmed clean, not accepted on dev's claim.** Read
`run_discovery.py` and `publish_prices.py` directly, top to bottom. `run_discovery.main()`:
`require_secrets()` → `client()` → `notifier` → checkpoint 1, nothing irreversible precedes it (the
Yahoo-fetch screener call is after checkpoint 1). `publish_prices.main()`: `require_secrets()` →
`client()` → watchlist read → Yahoo-fetch loop (not irreversible) → checkpoint 4 immediately before the
file write; checkpoint 1 is correctly out of scope for this file per §13.6.2. Grepped
`scripts/` for `write_tunables_cache_if_fetched` — the only call site anywhere is `run_hourly.py:138`.
dev's claim that the pattern does not recur elsewhere holds.

### REV-117 — re-verified independently, not re-run from dev's local instance

Stood up a fresh scratch Postgres 16 cluster in this session (sandbox has no Docker/PG17 either — same
constraint dev hit) and applied `sql/kill_switch_abort_log.sql` twice: both applies clean, second is a
verbatim no-op (`NOTICE: relation ... already exists, skipping`). Independently queried
`\dp public.kill_switch_abort_log` and `information_schema.role_table_grants` — zero rows for
`anon`/`authenticated`/`public`, no default `PUBLIC` grant remains. Confirmed denial directly:
`set role anon; truncate public.kill_switch_abort_log;` and the same under `authenticated` both failed
with `permission denied for table kill_switch_abort_log`; also spot-checked INSERT and SELECT denial
(both correctly denied via the pre-existing REVOKE/RLS+FORCE). Matches dev's local result exactly.
`docs/design/operational-controls.md:516`'s code sample already carries the corrected `truncate` clause.

**PG16-vs-17.6.1 substitution — judgment: low residual risk, not a blocker, but not fully closed either.**
Nothing in `sql/kill_switch_abort_log.sql` is version-sensitive — no trigger, no `create or replace
trigger` (the one construct in this codebase that actually is PG14+-specific), no PG17-specific
RLS/GRANT semantics; `REVOKE`/`ENABLE ROW LEVEL SECURITY`/`FORCE ROW LEVEL SECURITY` behave identically
across 16 → 17.6.1. What this substitution does **not** cover: any custom default-privilege, extension,
or role configuration specific to the live project (`ikghqdtlbwifwnooytmm`) that a fresh local PG16
cluster with hand-created `anon`/`authenticated` roles doesn't reproduce.

- **Named follow-up (owner: release/orchestrator, before/at live application):** after applying
  `sql/kill_switch_abort_log.sql` to the live project, run the same
  `select grantee, privilege_type from information_schema.role_table_grants where
  table_name='kill_switch_abort_log' and grantee in ('anon','authenticated','public')` query used in this
  verification (expect: 0 rows) to close this residual for good — same pattern as REV-081's live
  corroboration precedent (`docs/review-log.md` Pass 17).

### Regression

- `python3 -m pytest -q --tb=short` → **277 passed, 0 failed** (baseline 275 + 2 new REV-116 tests in
  `tests/test_kill_switch_boundary.py`).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed**
  (unchanged — this fix cycle touched no TypeScript).
- Shippability: full suite re-run clean; `run_hourly.py`/`run_discovery.py`/`publish_prices.py`/`state.py`
  import cleanly; the two new tests independently exercise `run_hourly.main()` end to end through its
  real entry point, not just through mocked internals.

### Stale docstrings fixed (qa-owned files, flagged by dev, not edited by dev per `CLAUDE.md`)

- `tests/test_kill_switch_boundary.py::test_checkpoint1_run_hourly_aborts_before_any_named_side_effect` —
  docstring updated: checkpoint 1 now sits at the top of `main()`, before `notifier`/the tunables-cache
  write/the market gate (was stale, described the pre-fix "after notifier is constructed" placement).
- `tests/test_run_orchestration.py::test_all_markets_closed_without_force_run_is_a_noop` — comment
  updated: `state.client()` and checkpoint 1's `is_paused()` are now reached on a closed-market no-op
  (REV-116 fix); only `state.write_heartbeat()` is not.

### Verdict — REV-116 / REV-117 fix cycle 1

**PASS. REV-116 verified 2026-07-30. REV-117 verified 2026-07-30.** Both majors independently
re-verified against current file content and a genuine reproduction, not accepted on dev's account:
REV-116's regression test is confirmed to fail against the pre-fix code (1 call + file written, while
paused) and pass against the fix (0 calls); the closed-market cache-refresh design property is confirmed
to survive the fix via the same fixture. REV-117's SQL re-applied twice on an independent local instance
with the same clean/idempotent result dev reported, and TRUNCATE denial independently confirmed for both
`anon` and `authenticated`. Open follow-up: live post-apply grant query on the real project (named above)
to close the PG16→17.6.1 substitution's residual once `sql/kill_switch_abort_log.sql` is applied live —
not a blocker to this verdict. 277/0 Python, 82/0 TypeScript, no regressions.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass. Full detail:
`docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
