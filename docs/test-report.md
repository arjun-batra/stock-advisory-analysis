# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## Phase-4 whole-system closure — cross-increment interaction pass — 2026-07-30

**Scope.** Not diff-scoped to one increment — the final qa gate before `v0.1.0`, covering everything
merged across the entire `/big-guns` fix round: INC-8 (degraded-run visibility + delivery-confirmed
alerting), INC-9 (parse-attribution contract + closed-market stale-bar check), INC-10 (tunables write-time
validation + holdings-currency derivation), INC-11 (live-verification pass), INC-12 (kill-switch in-flight
boundary checks + mid-run-abort classification). All reviewer-cleared through Pass 29
(`docs/review-log.md`); all seven `/big-guns` DEEP findings closed. Read `docs/test-report.md`'s prior run
(now archived), `docs/handoff.md` in full, `docs/design/increment-plan.md`'s INC-8–INC-12 sections,
`docs/requirements.md` (including §11's Phase-4 delivery confirmation and Decision #36/#37/#38), and
`docs/review-log.md`'s live content through Pass 29. `docs/archive/` not read, per `CLAUDE.md`.

### Cross-increment interaction testing (the point of this pass)

Five increments touch overlapping code — `state.py` (INC-8, INC-10, INC-12), `run_hourly.py`/
`run_discovery.py` (INC-8, INC-12), `ai_judge.py` (INC-9, INC-10's REV-113 fix). Each increment's own
diff-scoped suite already proves its own fix in isolation, against the real code, not mocked outcomes —
this pass instead drives the SAME real `run_hourly.main()`/`run_discovery.main()`/`state.py`/`ingest.py`
code with two or more fixes triggered in the same run or across consecutive runs of the same fixture data.
New file: `tests/test_phase4_closure_e2e.py` (4 tests, all exercising real entry-point code, not
increment-level mocks).

1. **A pause abort (INC-12) interacting with delivery-confirmed alerting (INC-8)** — a crossing left
   pending by a failed push, then a pause before the automatic retry.
   `test_failed_push_then_paused_before_retry_leaves_crossing_pending_with_correct_abort_accounting`:
   cycle 1, a real confirmed push failure (`alerted=False`, `verdict_state` unchanged, heartbeat
   `"partial"`); cycle 2, the same still-pending crossing is retried but the kill switch is paused right
   at its own checkpoint 3 — asserts the retry never reaches `notifier.push`, no second `call_log` row, the
   crossing stays exactly as pending as cycle 1 left it, cycle 1's heartbeat row is untouched, and the
   abort row's `real_rows_this_cycle == 0` (cycle 1's push-failure does not leak into cycle 2's count —
   `outcomes` is a fresh `Counter()` per `main()` call). Cycle 3 resumes and proves the crossing finally
   advances — FR34/FR35's combined "no new resume logic needed" claim, now proven across a push failure
   AND a pause on the SAME crossing's history, not just one or the other in isolation.
2. **A currency-mismatched holding (INC-10) whose ticker also hits the stale-bar path (INC-9).**
   `test_currency_mismatched_holding_whose_ticker_also_hits_the_stale_bar_path`: runs the REAL
   `ingest.get_market_data` (frozen clock + a fake `yfinance.Ticker`, same technique as
   `tests/test_ingest.py`'s own stale-bar tests) through the REAL `run_hourly.main()`/`state.py` pipeline
   for one ticker across two cycles. Cycle 1: the ticker's only available bar is 3 days stale during a
   live-clock session — asserts `state.build_position` is never even reached (the skip happens first,
   proving INC-9's structural check and INC-10's mismatch guard don't double-fire or race), the row is
   logged as `no_data`, and the heartbeat reads `"partial"`. Cycle 2: the same ticker gets a genuinely live
   (same-day-bar) read whose fundamentals currency (CAD) disagrees with the recorded holding currency
   (USD) — asserts `build_position` IS reached this time with the disagreeing currencies, the stored
   `position.currency_mismatched == True`, and `position.pl_pct is None` (FR11, not computed from
   mismatched currencies) — all read back from the real `call_log` snapshot the real pipeline wrote, not
   from a direct unit call to `build_position`.
3. **An all-`no-read` run (INC-8's degraded accounting) that also aborts at a checkpoint (INC-12's FR35
   classification) — FR35 must not suppress a genuine degraded signal.**
   `test_all_no_read_batch_that_aborts_mid_cycle_preserves_the_degraded_count_in_the_abort_row`: two
   tickers get genuine AI parse/rate-limit failures (`no-read`, both logged per FR15) and a third aborts at
   its own checkpoint 3. Asserts no heartbeat row is written this cycle (FR35's correct expected-quiet
   suppression) **and** the abort row's `real_rows_this_cycle == 2` — the two genuine no-read outcomes are
   not lost, they survive in the one record this cycle does leave behind. **Confirmed load-bearing, not
   decorative**: temporarily mutated `run_hourly.py`'s `real_rows` tuple to drop `"no-read"` (the exact
   shape a regression would take) and re-ran this one test — it failed (`assert 0 == 2`), confirming it
   would catch FR35's accounting silently swallowing the degraded signal. Reverted immediately;
   `git diff --stat scripts/` confirmed clean before continuing (per this file's own "never fix production
   code" boundary — the mutation was a throwaway, uncommitted, immediately-reverted probe, not a fix).
4. **Discovery's candidate path, which INC-8, INC-9 and INC-12 all touch.**
   `test_discovery_candidate_path_combines_stale_skip_delivery_failure_and_pause_abort`: three candidates
   in one `run_discovery.main()` call — one hits the stale-bar ingest skip (INC-9, never reaches the AI or
   a push), one gets a real AI verdict and a confirmed push failure with no abort (INC-8,
   `alerted=False`), and the third aborts at its own checkpoint 3 (INC-12, nothing logged for it at all).
   Asserts all three outcomes land correctly in the same run, no heartbeat row is written (FR35), and the
   abort row's `real_rows_this_cycle == 1` — the confirmed push-failure counts (a genuine AI verdict was
   produced and a genuine delivery attempt was made and failed), the stale-bar skip does not (it never
   reached the AI at all) — the precise boundary FR35's causal-tie accounting draws, now proven on
   discovery's own candidate path, not just `run_hourly.py`'s watchlist path.

All 4 tests pass against current code; test 3 was independently confirmed to fail against a deliberately
reintroduced regression, per this file's standing convention for load-bearing-test verification.

### Full regression

- `python3 -m pytest -q --tb=short` → **281 passed, 0 failed** (baseline 277 + 4 new in
  `tests/test_phase4_closure_e2e.py`).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed**
  (unchanged).
- `cd admin-portal && npm run build` → succeeds; all 8 routes compile (`/`, `/_not-found`,
  `/auth/callback`, `/holdings`, `/login`, `/track-record`, `/tunables`, `/watchlist`), TypeScript check
  passes, Turbopack production build clean.

### Shippability

Beyond the unit-level suite: all four cross-increment tests above drive `run_hourly.main()` /
`run_discovery.main()` from their real entry-point functions (not internal helpers), through real
`state.py`/`ingest.py` code, exactly as GitHub Actions invokes them — this is a stronger shippability
signal than an import smoke test, since it exercises the real control flow across a full simulated cycle
(including the multi-cycle retry/resume behavior FR34/FR35 depend on). `tests/test_import_smoke.py`
(part of the full suite above) additionally confirms every entry point (`run_hourly.py`, `run_discovery.py`,
`publish_prices.py`) imports cleanly. The admin-portal build compiling all 8 routes with a clean TypeScript
check is the portal's equivalent shippability signal (no live Supabase in CI, per `docs/code-map.md`).

### Correction to a prior run's recorded expectation — `kill_switch_abort_log` grant query

The INC-12 fix-cycle-1 run (archived, `docs/archive/test-report-archive.md`) recorded a post-apply
follow-up for `sql/kill_switch_abort_log.sql`: run
`select grantee, privilege_type from information_schema.role_table_grants where
table_name='kill_switch_abort_log' and grantee in ('anon','authenticated','public')` against the live
project after applying, and named the expected result "0 rows." **That expectation was wrong, not the
implementation.** The query was executed live after the migration was applied and returned **six rows** —
`anon` and `authenticated` each hold `REFERENCES, SELECT, TRIGGER` (three verbs each). These are
Supabase's default public-schema grants placed on any newly created table, and this table's grant profile
is byte-identical to `admin_allowlist`, `kill_switch_audit`, and `kill_switch_state`'s — all three
previously reviewer-cleared with this exact same non-empty grant set. The four verbs that matter
(`INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`) are absent from all six rows, and `anon` INSERT was empirically
confirmed denied live: `permission denied for table kill_switch_abort_log`. **Corrected assertion for any
future reader of this table's grant state: the right check is "none of `INSERT`/`UPDATE`/`DELETE`/
`TRUNCATE` present for `anon`/`authenticated`/`public`," not "zero rows."** This closes REV-117's residual
PG16-vs-17.6.1 substitution follow-up (`docs/review-log.md` Pass 29 §4) with live evidence, on the
corrected expectation — `sql/kill_switch_abort_log.sql`'s grant lockdown is confirmed live and correct.

### Live-verification status (Decision #36) — reflected accurately

- **INC-3 AC3** (kill-switch resume-baseline / no-false-alarm) and **INC-4 AC6** (live-Gemini smoke test)
  are **PASS**, executed live 2026-07-30 — see the INC-11 evidence record in `docs/handoff.md` (dispatch
  suppressed while paused with zero new workflow runs; `kill_switch_audit` gained exactly one row per
  toggle; 90 consecutive live `call_log` rows all `parse_status='ok'`, zero fallbacks). `requirements.md`
  §11 correctly reflects both as Delivered.
- **INC-7 AC2/AC3 remain open — a genuine, named closure gap, not silently re-deferred and not marked
  passed.** Both require a real authenticated admin **browser** session against the portal's own
  `is_admin()`-gated RPC path (distinct from INC-3 AC3's service-role/direct-SQL path, which does not
  substitute for it) — no such session was available in this or any prior session. `requirements.md` §11
  correctly carries FR31/FR32 as Deferred and routes the decision to pm/the user rather than assuming it
  away. This qa pass does not change that status: no browser session was available here either.

### Verdict — Phase-4 whole-system closure

**PASS.** 281/0 Python (277 baseline + 4 new cross-increment tests), 82/0 TypeScript, portal build clean
(8/8 routes). Four targeted cross-increment interaction tests, all exercising real entry-point code, found
no interaction bug across the five increments' overlapping surfaces (`state.py`, `run_hourly.py`,
`run_discovery.py`, `ingest.py`, `ai_judge.py`); one test's own regression-catching power was independently
confirmed via a reverted mutation probe. No bugs filed this pass. One prior run's recorded expectation
(`kill_switch_abort_log`'s grant query) is corrected above with live evidence, per explicit instruction —
not a new bug, a documentation correction. No production code was modified by qa this pass; no SQL was
applied to the live project by qa this pass.

**What remains untested/open going into `v0.1.0`, precisely:**
1. **INC-7 AC2/AC3** — the admin portal's own authenticated-browser kill-switch RPC round-trip and live
   dispatch-suppression proof. Requires a real logged-in admin browser session; not producible in this
   environment. This is the one substantive gap this pass could not close — routed to pm/the user per
   `requirements.md` Decision #36, not resolved here.
2. **`pages/dashboard.html`'s AC3 manual/browser check** (INC-8) — a real synthetic `call_log` row visually
   confirmed in an actual browser to render the "no reading" pill. The underlying JS conditional logic was
   verified in isolation (Node extraction, dev's handoff) but never in a rendered DOM/browser session — a
   pre-existing, carried gap, not new to this pass.
3. **BUG-007** (below) — unchanged, minor, deferred by design, owner tech-lead.
4. Everything on `docs/review-log.md` Pass 29's own carried-forward minor list (REV-063 residual+071,
   REV-065, REV-066+052, REV-067, REV-072, REV-048, REV-049(b), REV-080, REV-079, REV-097, REV-100,
   REV-101, REV-102, REV-103/104/105, REV-106, REV-107, REV-109, REV-114, REV-120, REV-122, REV-123) — all
   minor, all non-blocking, none owned by qa except REV-048 (constants/citation drift test, still not
   built) and REV-107/REV-109/REV-114 (carried qa items, unchanged this pass — not re-investigated here, as
   this pass's brief was the cross-increment interaction sweep specifically, not a fresh pass over every
   carried minor).
5. **Reviewer's full whole-codebase 6-pass audit has not yet run** as of this qa pass — per the pipeline,
   that is the next Phase-4 step after this qa sign-off, not something qa's own pass substitutes for.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass. Full detail:
`docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
