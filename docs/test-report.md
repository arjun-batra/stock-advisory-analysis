# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-9 — Parse-attribution contract + closed-market structural check (FR17; DEEP-003+DEEP-004) — 2026-07-30

**Scope.** `scripts/ai_judge.py` (`_parse_batch`, new `_normalize_ticker`, module docstring),
`scripts/ingest.py` (`get_market_data`) — confirmed via `git diff --stat f66d693..HEAD -- scripts/`
(exactly these two files). Read against `docs/design/increment-plan.md`'s INC-9 section (6 ACs),
`docs/design/components.md` §4.2/§4.4a, `docs/design/non-functional-ops.md` §7.5, `docs/requirements.md`
FR17 + Decisions #33/#34, and `docs/review-log.md`'s DEEP-003/DEEP-004 entries — not from dev's handoff
summary.

### 1. Baseline reconciliation

Dev claimed 229 passed / 0 failed pre-INC-9, with **no pre-existing test encoding the old (buggy)
behavior** — unlike INC-8, nothing needed rewriting. Independently confirmed rather than accepted on
account: `git stash`'d this session's new test files and reran the suite against dev's INC-9 commit
(`d006eb2`) — **229 passed, 0 failed**, exact match. Confirmed `229` is also exactly the pre-INC-9 baseline
by running the identical suite against `f66d693` (last reviewer-cleared commit) — also 229/0. Dev's "no
tension to flag" claim holds: the fixes are additive/narrowing, not a contract change any existing test
asserted the old shape of.

### 2. New tests, and whether each is a genuine regression test

Every new test below was run against **both** the INC-9 commit (`d006eb2`, current) and the pre-INC-9
baseline (`f66d693`, dev's code swapped out and back in via `git show <rev>:<path>`, not a branch
checkout) to confirm it actually discriminates old-vs-new behavior rather than passing by construction.

| Test (file) | On `d006eb2` (new) | On `f66d693` (pre-fix) | Genuine regression test? |
|---|---|---|---|
| `test_parse_batch_misattributed_shifted_array_fails_safe_not_borrowed` (`test_ai_judge.py`) | PASS | **FAIL** — `TSLA` resolves `MSFT`'s verdict/rationale under `parse_status="ok"`, the exact DEEP-003 shape | Yes |
| `test_parse_batch_legitimate_fallback_missing_ticker_label_still_resolves` (`test_ai_judge.py`) | PASS | **FAIL** — old code has no `used_fallback` log line at all (AC2 is new behavior), so the log-line assertion fails even though the resolution itself was already correct pre-fix | Yes (for AC2's log line; the underlying resolution behavior was already correct pre-fix, only the new log line is what regresses) |
| `test_parse_batch_normalize_ticker_suffix_stripping_must_not_collide_cross_market` (`test_ai_judge.py`) | **FAIL** (see BUG-005) | **FAIL** (same root symptom, pre-existing, unfixed by INC-9's narrowing) | Not a new regression — pre-existing defect the fix's own `_normalize_ticker` mechanism does not close; see BUG-005 |
| `test_get_market_data_stale_bar_during_live_clock_skips_before_prorating` (`test_ingest.py`) | PASS | **FAIL** — `has_price=True`, pro-rating ran, the fake ticker's `.fast_info`/`.info`/`.news` (rigged to raise if touched) were actually called | Yes |
| `test_get_market_data_same_day_bar_during_live_clock_is_unaffected` (`test_ingest.py`) | PASS | PASS (expected — negative case, no behavior change either side) | N/A by design (regression guard for the *other* direction) |
| `test_get_market_data_nse_stale_bar_with_tz_aware_kolkata_index` (`test_ingest.py`) | PASS | **FAIL** — same as the US case, NSE path | Yes |
| `test_get_market_data_nse_same_day_bar_with_tz_aware_kolkata_index` (`test_ingest.py`) | PASS | PASS (negative case) | N/A by design |
| `test_get_market_data_nse_same_day_bar_robust_even_if_index_tz_were_utc` (`test_ingest.py`) | PASS | PASS (negative case, both sides — see §4) | N/A by design |

Verified by literally running the assertions against both revisions (not inferred from the diff) —
methodology in §5 below.

### 3. AC-by-AC verification

1. **PASS.** `test_parse_batch_misattributed_shifted_array_fails_safe_not_borrowed` — the `[A,B,C]`
   request / `[A,X,B]` response shape from DEEP-003's evidence: `TSLA` (the dropped ticker) fails safe
   (`parse_status="failed"`), never receives `MSFT`'s verdict/rationale under `"ok"`. Second test,
   `test_parse_batch_legitimate_fallback_missing_ticker_label_still_resolves`, confirms the legitimate
   no-label case still resolves positionally with `parse_status="ok"`.
2. **PASS.** `grep -n "positional fallback used for" scripts/ai_judge.py` returns the line; both new tests
   assert on captured stdout directly (not just grep) — fires for the legitimate-fallback ticker, does
   NOT fire for the rejected misattribution candidate.
3. **PASS.** Confirmed by direct read: `ai_judge.py`'s module docstring (lines 1–12) no longer states the
   unqualified "can only ever MISS a signal" claim — it names `_parse_batch`'s narrowed positional-fallback
   acceptance test as the mechanism. One caveat, not an AC3 failure: the docstring's claim is not fully
   true given BUG-005 below (a residual fabrication path); flagged there, not re-litigated here since AC3
   only asks whether the docstring text itself was corrected, which it was.
4. **PASS.** `test_get_market_data_stale_bar_during_live_clock_skips_before_prorating` — weekday,
   mid-session US clock, last bar 3 days stale → `has_price=False`, note contains "market appears closed
   today", both dates named, and (stronger than the AC's own text) the fake ticker's `.fast_info`/`.info`/
   `.news` are rigged to raise `AssertionError` if ever touched — proving `_fundamentals()`/`_headlines()`
   and the pro-rating math genuinely never ran, not merely that their output was discarded.
   `test_get_market_data_same_day_bar_during_live_clock_is_unaffected` — same-day bar, unaffected:
   `has_price=True`, `session_live=True`, normal pro-rating path reached.
5. **PASS.** `grep -n "last_bar_date" scripts/ingest.py` — both occurrences sit between the empty-history
   guard and `close = h["Close"].dropna()` (line 270), before any of `pct_change_1d/5d/20d`/
   `volume_vs_avg` — confirmed by direct read of `get_market_data`, matching the AC's "structurally
   unreachable, not a late-added guard" framing.
6. **PASS.** `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **236 passed, 1 failed** (229
   baseline + 8 new INC-9 tests; 1 new test fails, documenting BUG-005, a residual defect — not a
   regression from a clean baseline). `git diff --stat f66d693..HEAD -- scripts/` confirms exactly
   `scripts/ai_judge.py` and `scripts/ingest.py` changed (tech-lead's own doc-only commits are outside this
   diff scope, as dev's handoff notes).

### 4. Timezone assumption (dev's flagged inherited risk) — verified, not a latent bug

Dev flagged: `h.index[-1].date()` is taken at face value as already exchange-local, with no explicit
tz conversion, and every pre-existing fixture uses a **naive** `pd.date_range` index, so this was
previously untested against a real tz-aware index. Checked directly for NSE (furthest UTC offset,
+5:30, no DST) with three new tests using **tz-aware** `Asia/Kolkata`-localized pandas indices (matching
what live `yfinance` actually returns — exchange-local via the ticker's own `exchangeTimezoneName`),
not naive ones:

- Stale-bar and same-day-bar NSE scenarios both pass with a genuinely tz-aware Kolkata index — the
  assumption holds for the realistic case, closing the "only tested against naive fixtures" gap.
- A third test deliberately builds the index as **UTC**-localized instead (probing the failure mode: what
  if `yfinance` ever returned a non-exchange-local index) — still passes. This is not luck: NSE's live
  session (9:15–15:30 IST = 03:45–10:00 UTC) never crosses a UTC midnight boundary, so `.date()` on a bar
  timestamp taken during NSE's own trading hours reads the same calendar date whether the Timestamp
  carries `Asia/Kolkata` or `UTC` tzinfo. The same arithmetic holds for US (13:30–20:00 UTC) and TSX
  (same session as US).

**Verdict: verified safe, not a latent bug, and no longer untestable** — closed the gap dev flagged with a
tz-aware fixture rather than leaving it as an inherited, unexercised assumption. Would only become a real
defect for a market whose live trading hours straddle UTC midnight while its index were mislocalized —
not a configuration any of the three current markets (US/TSX/NSE) has.

### 5. Regression suite & methodology

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **236 passed, 1 failed** (229 baseline +
  8 new INC-9 tests, 1 failing — BUG-005, not a regression, see below).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` (run from repo root —
  `tests/admin_portal/`, not `admin-portal/tests/`) → **63 passed, 0 failed**, matching the last recorded
  baseline exactly; `admin-portal/node_modules` is present this session (the prior INC-8 run's 6
  `build_bundle.test.ts` environment failures are gone). INC-9 touches zero `admin-portal/` files.
- Old-vs-new discrimination (§2 table): for each new test, the production files under test
  (`scripts/ai_judge.py`, `scripts/ingest.py`) were swapped for their `f66d693` (pre-INC-9) content via
  `git show f66d693:<path> > <path>`, the specific new tests re-run, then restored via the session's own
  saved copies and confirmed `git diff` clean before continuing. This is stronger evidence than reasoning
  from the diff — every regression test named above was directly proven to fail on the pre-fix code.

### 6. Shippability

Real entry point, not reimplemented logic: `run_hourly.main()` driven end-to-end with only `yf.Ticker`
faked (`ingest.get_market_data` itself REAL, so the DEEP-004 structural check actually executes inside
the real pipeline) and `ai_judge.judge_batch` mocked (no live Gemini call). Watchlist of two US tickers —
`AAPL` (normal, same-day bar) and `HOLIDAY` (stale bar, frozen weekday/live clock). Confirmed: `HOLIDAY`
is skipped-with-log (`state.log_skip`, `parse_status="no_data"`, `alerted=False`) **before** it ever
reaches `ai_judge.judge_batch` (only `AAPL` is in the batch); `AAPL` resolves a normal `cold-start`
outcome; `run_heartbeat.status == "partial"` (the skip is visible, not silently absorbed into "ok"),
matching FR17/NFR2. Script not committed (session-scratchpad only), reproducible from this description.

### Verdict — INC-9

**Bugs filed.** ACs 1–6 all independently verified PASS (§3). Python suite: 236 passed, 1 failed (229
baseline + 8 new, 0 regressions — the 1 failure is a newly-written test documenting a genuine pre-existing
defect, not a broken assertion). TypeScript suite: 63 passed, 0 failed, unaffected. Shippability confirmed
via the real `run_hourly.main()` entry point. Timezone assumption dev flagged: verified safe for NSE, not
a latent bug (§4). One bug filed against production code — **BUG-005** (below); the DEEP-003 fix ships as
designed and closes the exact scenario in DEEP-003's evidence and increment-plan.md's AC1, but does not
close a related, narrower cross-market collision the fix's own `_normalize_ticker` mechanism introduces.

---

## Open bugs

**BUG-005 — `_normalize_ticker`'s `.TO`/`.NS` suffix-stripping creates a cross-market misattribution
`_parse_batch`'s narrowed positional-fallback check doesn't catch — major — INC-9, FR17/DEEP-003 residual.**

**Where:** `scripts/ai_judge.py`, `_parse_batch` (`:239–250`), via `_normalize_ticker` (`:184–192`).

**Repro (`tests/test_ai_judge.py::test_parse_batch_normalize_ticker_suffix_stripping_must_not_collide_cross_market`):**
request `["ABC.TO", "ABC.NS"]`; model response `[{no ticker field, verdict/rationale A}, {"ticker":
"ABC.TO", verdict/rationale B}]`. `ABC.TO` resolves correctly via its own direct label (rationale B).
`ABC.NS` has no object of its own — falls to the positional-fallback check at its own array index (1),
which is `ABC.TO`'s own already-consumed labeled object. `_normalize_ticker("ABC.TO")` and
`_normalize_ticker("ABC.NS")` both strip their suffix to `"ABC"` and compare equal, so the check accepts
it: `ABC.NS` silently inherits `ABC.TO`'s verdict/rationale (rationale B) under `parse_status="ok"`.

**Expected (FR17/DEEP-003's own invariant, restated in `ai_judge.py`'s corrected docstring, "never
fabricate, only miss"):** `ABC.NS` has no object of its own in the response and must fail safe
(`parse_status="failed"`), not borrow a different, already-attributed ticker's verdict.

**Actual:** `ABC.NS` gets `parse_status="ok"`, `rationale="abc-to-reason"` (identical to `ABC.TO`'s row) —
a genuine fabrication under a status that downstream (`state.py`'s `parse_status in ("failed",
"api_error")` guard) is treated as trustworthy enough to fire a real alert if it crosses a verdict change.

**Not a new regression from INC-9** — reproduced identically against the pre-INC-9 commit (`f66d693`),
where the unconditional (unnarrowed) fallback has the same symptom for the same reason (no ticker-field
check existed at all pre-fix). INC-9's narrowing fix closes DEEP-003's own named scenario (a misaligned
array within one market) but does not close this adjacent case, because `_normalize_ticker`'s suffix
stripping — added specifically to make the narrowing fix work — treats two *different*, real watchlist
tickers as if they corroborate each other whenever they share a base symbol across markets. Realistic
whenever a watchlist holds the same base symbol cross-listed on two of US/TSX/NSE (FR20 groups tickers by
market but nothing prevents this).

**Suggested fix (dev's/tech-lead's call, not prescribed here):** the positional-fallback corroboration
check should also confirm the candidate hasn't already been consumed by another ticker's direct-label
match in the same `by_ticker` build pass — e.g. track consumed array indices, or require an exact
(non-normalized) match when the candidate object DOES carry an explicit `ticker` field, reserving
normalization only for candidates with no `ticker` field at all (the "model forgot the label" case
`_normalize_ticker` was designed for, which never needs cross-suffix comparison because there's no
foreign label to compare against in the first place).

**Owner:** dev (with tech-lead recording the corroboration-check decision in `components.md` §4.4a, same
pattern as the original DEEP-003 fix).
