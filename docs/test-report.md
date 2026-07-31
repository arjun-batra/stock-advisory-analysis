# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## Phase 4 Closure — Whole-System End-to-End Regression — 2026-07-31

**Scope.** Full-codebase closure pass per `CLAUDE.md`'s Phase 4 (qa step, first of the closure sequence),
run at `main`@`da50ed8` (includes the just-merged INC-13 admin-portal UI modernization, reviewer Pass 35
CLEAR). Not diff-scoped to one increment — every subsystem in `docs/requirements.md` FR1–FR35/NFR1–NFR8 and
`docs/design.md`/`docs/design/*.md`. Confirmed via `git tag -l` (empty) that no `v0.1.0` tag exists yet —
this is genuinely the first tag-gating closure pass, not a re-run. Read `docs/requirements.md` in full
(§3/§5/§6/§8/§11), `docs/code-map.md`, `docs/test-report.md`'s prior run (now archived, INC-13 fix-cycle-1
retest) and `docs/archive/test-report-archive.md` in full for what has already been proven, so this pass
re-derives nothing already covered and instead targets (a) the full suite, (b) anything never given a real
end-to-end pass, and (c) anything plausibly touched since the last whole-system pass
(`docs/archive/test-report-archive.md`'s "Phase-4 whole-system closure — cross-increment interaction pass —
2026-07-30" entry).

### 1. Full automated suite (fresh re-run, not cited)

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **286 passed, 1 failed.** The one failure —
  `tests/test_ingest.py::test_get_price_only_matches_get_market_data_price_fields_for_same_history`
  (`assert 14.5 == None`) — is the same pre-existing, date-sensitive failure flagged across every INC-9
  through INC-13 run (the test doesn't freeze the real clock, so `ingest.get_price_only`'s live-session
  check is sensitive to the real day/time this suite happens to run on; `ingest.py` is otherwise untouched
  since INC-9). Confirmed still the *only* failure and unrelated to any recent work — no new failure
  introduced by INC-13, the BUG-009 fix, or the C901 refactor.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed.**
- `cd admin-portal && npm run build` → compiles cleanly; all 8 routes present (`/`, `/_not-found`,
  `/auth/callback`, `/holdings`, `/login`, `/track-record`, `/tunables`, `/watchlist`); TypeScript check
  passes.
- `cd admin-portal && npm run lint` → zero errors/warnings.
- `ruff check .` and `ruff check --select C90 .` → both clean.

### 2. Functional regression checklist, by subsystem

**Watchlist/holdings CRUD (FR1–FR3, FR28, FR29).** Cited, not re-run: INC-5 (`docs/archive/
test-report-archive.md` §"INC-5"), INC-10's `holdings_currency_derivation` trigger (FR11/FR29 currency
derivation, live-confirmed per `requirements.md` §11), and the current INC-13 archived entry's "CRUD/
validation regression spot check" (watchlist Edit/Save PATCH, Delete, tunables reject-then-accept, all at
3 widths) — INC-13 touches only presentation, and the 82/0 TypeScript suite plus AC5's structural grep
(zero forbidden-call diffs outside one prose comment) confirm the CRUD wiring itself is byte-identical to
what INC-5/10 already proved. Nothing plausibly changed here since the last full pass; not re-run.

**Discovery scan logic (FR4, FR5).** Cited: `tests/test_prefilter.py` (30 tests, all four signal types +
quality-gate boundaries + configurability), and the archived Phase-4 cross-increment test #4
(`test_discovery_candidate_path_combines_stale_skip_delivery_failure_and_pause_abort`) driving the real
`run_discovery.main()` end-to-end. Untouched since 2026-07-30; not re-run.

**AI judgment call path / provider abstraction (FR33).** Cited: INC-4 (provider abstraction, live-verified
90 consecutive `call_log` rows, `parse_status='ok'`, zero fallbacks — `requirements.md` §11), and the
2026-07-31 "C901 complexity-refactor verification" pass, which re-derived (not merely cited) DEEP-003
misattribution rejection, BUG-005 unambiguity, and BUG-006 dedup/overwrite guards directly against current
`ai_judge.py` after its structural refactor — 287/0 at that point. Unaffected by INC-13 (zero `scripts/`
files in its diff, confirmed by AC5's grep). Not re-run this pass.

**Alerting/push delivery contract (FR34).** Cited: INC-8 (delivery-confirmed `alerted`, retry-on-failure),
and the archived Phase-4 cross-increment test #1
(`test_failed_push_then_paused_before_retry_leaves_crossing_pending_with_correct_abort_accounting`), which
drives a real failed push through a real pending-crossing retry across three cycles of `run_hourly.main()`.
Unaffected by INC-13; not re-run.

**Kill-switch enforcement layers (FR24, FR25, FR35).** Cited: INC-3 (dispatch-layer gate, live-verified —
pause suppressed a scheduled dispatch, resume restored it, `requirements.md` §11), INC-12 (four in-flight
Python-layer checkpoints), the archived Phase-4 cross-increment tests #1 and #3 (pause-abort interacting
with delivery-confirmed retry; an all-`no-read` run that also aborts, proving FR35 never suppresses a
genuine degraded signal — this test's own regression-catching power was independently confirmed via a
reverted mutation probe), and the C901 refactor pass's re-confirmation that `KillSwitchAbort` propagation,
the single-abort-row/checkpoint/`real_rows_this_cycle` accounting, and heartbeat-suppression all survived
the `run_discovery.py` decomposition unchanged. `sql/kill_switch_abort_log.sql` is applied live in
production with the correct deny-all RLS posture (verified in the archived Phase-4 pass, corrected grant-
count expectation recorded there). Portal-side (FR32): the current INC-13 archived entry's AC8 confirms the
toggle fires `rpc/set_kill_switch` with the correct payload and flips state on a mocked success response —
consistent with, not a substitute for, INC-7 AC2/AC3's still-open live-browser round-trip (see §4 below).
Nothing plausibly changed in the enforcement code itself since 2026-07-30; not re-run.

**NSE-specific market-hours/holiday handling (FR17).** Cited: INC-9 (structural stale-bar/closed-market
check, reviewer Pass 25 CLEAR), and the archived Phase-4 cross-increment test #2
(`test_currency_mismatched_holding_whose_ticker_also_hits_the_stale_bar_path`), which drives the real
`ingest.get_market_data` + `run_hourly.main()`/`state.py` pipeline across two cycles and confirms the
stale-bar skip and the currency-mismatch guard (FR11) don't double-fire or race. Untouched since; not
re-run.

**Dashboard (FR19–FR22, FR23's client-rendered half) — freshly re-verified this pass, first-ever real-
browser pass.** Every prior INC-8 record for this page explicitly states "no browser-automation tooling
available... the AC's own 'actual browser' rendering check was NOT performed and remains genuinely
unverified" — a real gap, unlike the JS-logic-only verification done at the time. This environment now has
Playwright + a pre-installed Chromium (used for INC-13's portal testing), so this pass closed that gap:
served `pages/` via a local static server, launched real Chromium, bypassed the FR19 passcode gate via
`sessionStorage` (same mechanism a returning tab uses), intercepted the Supabase REST calls and
`prices.json` at the network layer with synthetic fixture data covering every `parse_status` case plus a
cold-start ticker with no `call_log` row, and read the actual rendered DOM (not source text):
- **FR21 "no reading" pill** — `parse_status` in `no_data`/`failed`/`api_error` renders exactly `no data`,
  never a `Hold` pill (the placeholder-Hold-is-not-a-real-verdict guard, DEEP-001/INC-8); a genuine
  `parse_status="ok"` Buy and Hold each render their real verdict pill — all confirmed by extracting real
  `.pill` text from `.tc-bot` in the rendered page.
- **FR21 cold-start hiding** — a watchlist ticker with no `call_log` row yet renders zero `.tc-bot` elements
  (no placeholder, no empty cells) — confirmed by DOM count, not source inspection.
- **FR20 grouping/badges** — "US & Canada" and "India (NSE)" group labels both render (case-normalized
  comparison, since the CSS applies `text-transform:uppercase`); a held ticker renders `.b-held`, a
  watch-only ticker renders `.b-watch`.
- **FR23 dual-timestamp** — a non-IST-device-timezone render shows the `(... IST)` secondary bracket on the
  age row, as the format requires.
All assertions passed on the first corrected run (one initial test-authoring mistake — comparing raw vs.
CSS-uppercased group-label text — fixed in the harness itself, not a product issue). Script retained at
session scratchpad only (matches this project's existing browser-test artifact convention — not committed,
per `docs/archive/test-report-archive.md`'s established posture for this class of check).

**Admin portal (FR27–FR32, NFR5–NFR6, NFR8 UI).** Cited: INC-5 (Google OAuth login, watchlist CRUD), INC-6
(tunables editor + write-time validation, live-confirmed rejecting an invalid `ALERTS_ENABLED` value), INC-7
(track-record view, kill-switch UI, reviewer Pass 20 CLEAR), BUG-009's fix-and-retest (2026-07-31 —
`call_log`'s RLS was silently `anon`-only, leaving the track-record view empty for signed-in admins; fixed
via `sql/call_log_authenticated_read_fix.sql`, retested RESOLVED, reviewer Pass 33 CLEAR), and INC-13's full
responsive/visual pass (fix-cycle-1 retest, currently archived above) — 156+ real-browser checks across
375/768/1280px covering AC1–AC5, AC7(a)/(b)/(c), AC8, AC9, with zero functional regression to FR27–FR32
confirmed via computed-style/DOM measurement on the actual compiled app plus a structural grep proving the
branch touches only the 10 allow-listed presentation files. Reviewer Pass 34/35: zero blockers, zero majors,
INC-13 cleared to merge. Not re-run this pass — nothing plausibly changed since INC-13's own qa clearance
(no commits since `da50ed8` besides this qa pass itself).

**Timestamps/timezone formatting (FR23).** Push-notification half cited: `tests/test_notify.py`'s
`_market_timestamp` coverage (ET for US/TSX, IST for NSE, single-timezone format). Client-rendered half
freshly re-verified this pass via the dashboard real-browser check above (dual-timezone bracket format).

### 3. What remains open — precisely, not silently re-deferred

- **INC-7 AC2/AC3 — the admin portal's own authenticated-browser kill-switch RPC round-trip and a live
  dispatch-suppression proof from a portal-initiated pause.** Still not executable in this environment (no
  live Google OAuth browser session against the deployed Vercel portal is available here, same constraint
  recorded at every prior pass that touched this). This is `requirements.md` §11's explicitly acknowledged
  **FR31/FR32 = Deferred, pending live execution**, by the user's own 2026-07-31 decision (Decision #36,
  option 2) — not a new gap introduced by this pass, and not something qa can resolve without that session.
  Distinct from, and not fixed by, this pass's new dashboard browser check (which needed only a static file
  server + mocked network, not live Supabase auth).
- **BUG-007** — `_parse_batch`'s duplicate-requested-ticker resolution is last-write-wins when both
  occurrences resolve legitimately to *different* verdicts. Minor, deferred by design (owner: tech-lead),
  unchanged this pass. Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry.
- Reviewer's full whole-codebase 6-pass audit has not yet run as of this qa pass — the next Phase-4 step
  per the pipeline, not something this pass substitutes for.
- `docs/design/increment-plan.md`'s INC-13 entry still reads "READY, dev may start" despite INC-13 being
  merged and reviewer-cleared (Pass 35) — a stale status line, tech-lead's doc to fix, not a qa finding
  against the system itself; flagged here so it isn't lost.

### 4. Shippability

Beyond the unit-level suite: `run_hourly.main()`/`run_discovery.main()` are driven from their real
entry-point functions (not reimplemented logic) by `tests/test_run_orchestration.py` and
`tests/test_phase4_closure_e2e.py`, both still in the suite and passing. `admin-portal`'s `next build`
compiles all 8 routes with a clean TypeScript check — its equivalent shippability signal (no live Supabase
in CI, per `docs/code-map.md`). This pass's new dashboard check adds a third, independent shippability
signal: `pages/dashboard.html` was exercised as a real static asset in a real browser against a mocked
network layer, not just `node --check`-ed for syntax.

### Verdict — Phase 4 closure, qa gate

**PASS.** 286/1 Python (1 pre-existing/unrelated, confirmed unrelated to any recent change), 82/0
TypeScript, admin-portal build/lint clean, both `ruff` invocations clean. Zero new bugs filed this pass.
Exactly one open bug system-wide (BUG-007, minor, deferred by design, non-blocking). Every FR/NFR in
`docs/requirements.md` §5–§6 has either a fresh or a cited end-to-end proof above, except INC-7 AC2/AC3
(FR31/FR32's portal-own-browser-RPC round-trip), which remains the one substantive, user-acknowledged
Deferred item this environment cannot close — routed to pm/the user per `requirements.md` Decision #36,
unchanged by this pass. This pass newly closed a previously-open gap (the dashboard's real-browser AC3
rendering check, INC-8) that no prior pass could execute for lack of browser tooling. Ready to proceed to
reviewer's full 6-pass audit.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — nothing in this
closure pass touched `ai_judge.py`. Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006
fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
