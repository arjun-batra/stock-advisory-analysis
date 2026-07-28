# Test Report Archive

Older qa run entries, moved out of `docs/test-report.md` per the doc-hygiene rule (keep only the latest
run + open bugs in the live report). Agents do not read this file during normal work.

---

# Test Report — Baseline Establishment (Adoption Pass)

**Owner:** qa. **Date:** 2026-07-12 (original baseline); updated 2026-07-12 (debt-cleanup pass, see §7).
**Type:** Baseline snapshot for an existing, already-live system — NOT a claim that a full test campaign
has been run against production. This is the first automated `tests/` suite this repo has ever had.

---

## 1. Starting state (before this pass)

- **No `tests/` directory existed anywhere in the repo before this pass.** `git log` / directory listing
  confirm the repo had zero automated tests (no pytest, no unit tests, nothing under any `test_*`/`*_test`
  naming convention) at any point prior to 2026-07-12.
- The only existing test artifact was `qa/test-plan-full-codebase.md` — a **manual, Claude-Code-executed
  test plan** (Playwright + direct Supabase/GitHub CLI calls against live infra), not an automated
  regression suite. It is a runbook a human/agent executes interactively; it does not run in CI, has no
  pass/fail history checked into the repo, and cannot be run with `pytest`.
- **Honest conclusion: prior to this pass, FR1–FR31 / NFR1–NFR5 had zero automated regression coverage.**
  Any historical confidence in this system's correctness came from manual execution of the plan above (no
  results from that execution are stored in the repo) plus production having run without a total outage.
  This report does not retroactively claim otherwise.

---

## 2. What this pass added

`tests/` — a new pytest suite, 131 tests across 6 files, added as a baseline. Scope was deliberately
limited per the adoption-pass instruction ("a solid baseline of the highest-risk pure-logic modules... not
a full test-everything campaign"): pure/near-pure logic modules that are cheap to test in isolation and
load-bearing per `docs/design.md` §0, plus a cheap import-level shippability smoke check. **No production
code was changed.** All externals (Gemini, yfinance, Supabase, ntfy) are mocked or simply never invoked —
nothing in this suite makes a real network call.

| File | Tests | FR/NFR IDs covered | What it exercises |
|---|---|---|---|
| `tests/test_state.py` | 24 | **FR7, FR8, FR15**, FR2/FR11 (partial), FR4 Decision #16 | The single-rule verdict-change state machine (`state.process_ticker`): cold start (silent baseline), no-change (silence, still logged), every verdict-pair change (incl. the FR7-explicit "change to Hold" case), no-frequency-cap on repeated flips, the load-bearing fail-safe-Hold guard (a parse failure can never fabricate a change alert or advance state), `log_skip`, `build_position`, and discovery's Buy-only push gate (`process_candidate`) |
| `tests/test_prefilter.py` | 30 | **FR4** | Discovery quality-gate boundaries (market cap / price / volume / exchange, US and NSE/INR profiles, exact-threshold and just-below/above cases), all four signal types (mover, volume-spike, earnings-proximity, 52-week-extreme) at their exact boundaries, NSE-vs-BSE exchange filtering, and two explicit configurability checks (changing `DISCOVERY_GAINER_PCT` / `DISCOVERY_MIN_MARKET_CAP` measurably changes behavior — proof the thresholds aren't hardcoded) |
| `tests/test_config.py` | 29 | **FR30, NFR5**, config surface (`docs/requirements.md` §11 / `docs/design.md` §9) | Env-var override propagation for `GEMINI_MODEL`/`_BACKUP`, `NSE_GEMINI_MODEL`, `GEMINI_TIMEOUT_MS`, `DISCOVERY_MIN_MARKET_CAP`, `ALERTS_ENABLED`, the empty-string `or`-default trap on `GEMINI_MAX_RETRIES`; defaults-when-unset for all the above (**including locking in the corrected default `GEMINI_MODEL=gemini-3.5-flash`**, see §4 below); the `SHADOW_ENABLED` fail-open kill switch; the market-hours gate boundary (open/close/weekend) with an explicit configurability check that changing `RUNTIME_CLOSE_GRACE_MIN` measurably shifts the close boundary; `require_secrets()` fail-fast behavior |
| `tests/test_notify.py` | 18 | **FR12, FR13, FR18, FR23** | `_market_timestamp` (US/TSX→ET, NSE→IST, unknown→ET, format), `_topic_for` (FR18 NSE routing + the operator-visible `[FR18 fallback]` log line when `NSE_NTFY_TOPIC` is unprovisioned), title/body composition and clipping, `DryRunNotifier`/`get_notifier` selection logic, and `NtfyNotifier.push` with `requests.post` mocked (URL, headers, click-through link, and that a network exception is swallowed rather than crashing the run) |
| `tests/test_textutil.py` | 14 | supports FR13/FR14/FR23 (rationale + push-body clipping) | `clip()`: empty string, whitespace-only, exact-limit boundary, over-limit, word-boundary (never cuts mid-word), trailing-punctuation stripping before the ellipsis, unicode/non-ASCII text (NSE company names, currency symbols), internal-whitespace normalization, very small limits |
| `tests/test_import_smoke.py` | 16 | shippability baseline (all FR/NFR indirectly — "does the code run at all") | Every module in `scripts/` imports cleanly against a minimal mocked env (`GEMINI_API_KEY`/`SUPABASE_URL`/`SUPABASE_SECRET_KEY` faked, no real client ever contacted); the four entry points (`run_hourly.py`, `run_discovery.py`, `run_shadow.py`, `publish_prices.py`) expose `main()` and do nothing on import — confirming they're thin orchestrators, not scripts with side effects at import time |
| `tests/test_ai_judge.py` | 8 | **FR9, FR10** (REV-003 follow-up, added 2026-07-12) | `judge_batch`'s control flow with `google.genai.Client` fully mocked (shared fake in `tests/conftest.py`): happy path (single- and multi-ticker valid JSON), empty-items no-op, the parse-retry-once-then-fail-safe-to-Hold path (asserts exactly 2 calls made and the correct `fallback_from` note), a reply that parses but omits a requested ticker fails safe for that ticker only, the model-fallback path (primary exhausts `GEMINI_MAX_RETRIES` transport retries on a retryable 503, backup succeeds — asserts `model_used`, `retry_count`, `fallback_from`, and per-model call counts), a non-retryable 4xx is never retried before falling back, and a hard failure of every model fails every ticker safe to Hold with `parse_status="api_error"` |
| `tests/test_ingest.py` | 11 | supports FR9, FR17 (REV-004 follow-up, added 2026-07-12) | `yfinance.Ticker` fully mocked: the headline relevance filter (`_headlines`/`_mentions_company`) drops the real-world unrelated-same-acronym case from the code's own comment (SBIN.NS / "SBI Holdings" Japan crypto story) while keeping a genuinely relevant headline, fails OPEN (drops nothing) when no company name is available to match against, respects the headline limit after filtering, and handles a `tk.news` fetch exception gracefully; `_session_state`'s pro-rating boundary logic at well-into-session (~50%), just-after-open (<10%), exact-open (0%), after-close (not live), weekend (not live), and the NSE/IST session |
| `tests/test_shadow.py` | 14 | **FR24–FR29** (REV-005 follow-up, added 2026-07-12) | `shadow.judge_batch_shadow`'s control flow reusing the same fake-Gemini machinery as `test_ai_judge.py` (confirms it really shares `ai_judge._client`/`_generate`, not a copy — asserts the SHADOW system prompt, not production's, is what's actually sent), empty-items no-op, and hard-failure fail-safe-to-Hold; `run_shadow._derive_shadow_positions`'s wallet-walk (Buy flat→holding, Sell holding→flat, Hold is a no-op, a redundant Buy while already holding is a no-op and does NOT overwrite the original entry price/date, a full Buy→Sell→Buy cycle re-sets the entry on the second Buy, multiple tickers derived independently, empty history ⇒ flat) with a fake in-memory Supabase double; `run_shadow._usable_market_data`'s same-data reuse returning `None` on a no-price/`no_data`/missing-snapshot production row and a merged dict when a price is present |

### Suite result

**Run:** `python3 -m pytest tests/ -q` (Python 3.11.15, pytest 9.1.1, `requirements.txt` installed).

**Original baseline result (2026-07-12, before this debt-cleanup pass): 130 passed / 1 failed / 131 total**
(the 1 failure was the intentionally-left-failing `tests/test_config.py::test_shadow_enabled_only_literal_false_disables_a_typo_stays_open`, filed as BUG-001 — see §4).

**Current result (2026-07-12, after this debt-cleanup pass — see §7): 164 passed / 0 failed / 164 total.**

---

## 3. Not covered (explicitly deferred, not silently skipped)

As of the 2026-07-12 debt-cleanup pass (§7), `ai_judge.py`, `ingest.py`'s headline/session logic, and
`shadow.py`/`run_shadow.py`'s wallet-walk + same-data-reuse logic are now covered — see the coverage table
above (`tests/test_ai_judge.py`, `tests/test_ingest.py`, `tests/test_shadow.py`). What remains explicitly
out of scope for this automated suite:
- Any live Supabase/GitHub Actions/dashboard/detail-page verification (FR1, FR3, FR6, FR14, FR17,
  FR19–FR23, NFR2, NFR4) — these require real infra and remain the domain of
  `qa/test-plan-full-codebase.md` Phases 3–5, the manual playbook for that layer. This automated suite
  does not attempt to replace it. **Tracked as REV-006 in `docs/review-log.md`, marked ACCEPTED-DEBT**:
  automating this layer would require live Supabase/GitHub Actions/GitHub Pages infrastructure, which is
  out of proportion for a `tests/` regression-suite cleanup pass; it is correctly and deliberately
  `qa/test-plan-full-codebase.md`'s domain (manual, Claude-Code-executed against live infra) by design, not
  a gap to close with more pytest.
- A true end-to-end run from a real entry point against live Supabase/Gemini/ntfy — out of scope for a
  proportionate automated-suite pass. `tests/test_import_smoke.py` is the closest thing this suite has to
  a shippability check (confirms the entry points are import-clean, thin orchestrators with no import-time
  side effects) but is not a substitute for a real dry run; that real dry run is `qa/test-plan-full-codebase.md`'s
  job.
- `ai_judge.py`/`shadow.py`'s exact prompt-string wording (as opposed to control flow) — per the task
  brief for this pass, deliberately not exhaustively tested; the load-bearing guarantee under test is the
  control flow (parse-retry, model-fallback, fail-safe-to-Hold), not every sentence of prompt text.

**FR31** (committed, reproducible shadow evaluation harness) has no code to test — it is an acknowledged
open requirements gap (`docs/requirements.md` §10.2), not a missed test.

---

## 4. Bugs filed

### BUG-001 — FR30 / NFR5: `SHADOW_ENABLED` does not fail open on a mistyped value, contradicting the documented accepted-risk posture — RESOLVED 2026-07-12 (REV-001, doc correction)

**Status: RESOLVED.** Resolved via the user's chosen Option B: **the docs were corrected, not the code**
(reviewer's REV-001, `docs/review-log.md`). `docs/requirements.md` FR30/NFR5 and `docs/design.md` §0/§13.6
were rewritten by pm/tech-lead to accurately state: the kill switch fails open **only** on a truly
unset/empty `SHADOW_ENABLED` Variable; any explicitly-set-but-wrong value (including a typo like `flase`)
fails **closed** and disables the pilot. This is now an accurate description of `scripts/config.py`'s
actual behavior — no code changed.

`tests/test_config.py` was updated to match: the test that asserted the old (now-corrected-away) claim,
`test_shadow_enabled_only_literal_false_disables_a_typo_stays_open`, was renamed to
`test_shadow_enabled_any_non_true_explicit_value_fails_closed_typo` and now asserts
`SHADOW_ENABLED is False` for a typo'd value (`"flase"`) — matching the corrected FR30/NFR5. The companion
case — a truly empty/unset Variable still resolves to `True` (fails open only in that case) — was already
covered by the adjacent `test_shadow_enabled_defaults_true_when_empty_string` and
`test_shadow_enabled_defaults_true_when_unset` and needed no change. Full suite re-run: 164/164 passing
(§7), including this test.

Original finding (kept verbatim below for the record):

- **Requirement violated:** FR30 ("**Only the literal string `false` disables it.** ... an unset/mistyped
  `SHADOW_ENABLED` Variable *silently keeps the pilot running*") and NFR5 (same posture, restated).
  `docs/design.md` §0 load-bearing item #10 and §13.6 both restate this identically: "an unset/mistyped
  Variable *keeps the pilot running*."
- **Increment / component:** `scripts/config.py` (adoption-pass baseline finding — pre-existing code, not
  introduced by this pass).
- **Reproduction:**
  1. `export SHADOW_ENABLED=flase` (a plausible typo of `false`)
  2. `python3 -c "import config; print(config.SHADOW_ENABLED)"`
  3. Automated repro (original, now superseded — see resolution above): the test formerly named
     `tests/test_config.py::test_shadow_enabled_only_literal_false_disables_a_typo_stays_open`, now
     `test_shadow_enabled_any_non_true_explicit_value_fails_closed_typo` and asserting the corrected
     expectation.
- **Expected (per FR30/NFR5 AS ORIGINALLY WRITTEN, verbatim from the requirements/design docs at the
  time):** `True` — "only the literal string `false` disables it"; anything else, including a typo,
  should leave the pilot running. **(This expectation was the part that was wrong and has since been
  corrected — see resolution above; do not use this as the current spec.)**
- **Actual:** `False`. The implementation is
  `SHADOW_ENABLED = (os.environ.get("SHADOW_ENABLED", "").strip().lower() or "true") == "true"`. The `or
  "true"` fallback only triggers when the env value is the **empty string** (falsy) — Python's `or` does
  not fall through for any other value, so a non-empty string that is neither `"true"` nor `"false"` (e.g.
  `"flase"`, `"no"`, `"0"`, `"disabled"`) evaluates the right-hand `== "true"` comparison directly and
  resolves to `False`. In other words: the code actually fails **open** only on **unset/empty**, and fails
  **closed** (disables the pilot) on **any other non-`"true"` value including a typo** — the opposite of
  what FR30/NFR5 and the load-bearing design note both explicitly claim about mistyped values.
- **Severity assessment (informational, not a QA call):** this is arguably a *safer* runtime behavior than
  what's documented (a typo silently disabling a non-production pilot is lower-risk than a typo silently
  keeping it running) — but the doc and the code disagree on a requirement marked HARD/accepted-risk, and
  that disagreement should be resolved explicitly (either fix the code to match the fail-open intent, or
  correct FR30/NFR5/design.md's wording to describe what the code actually does) rather than left as a
  silent mismatch. Routed to dev/pm per the standard bug-handling flow; qa does not fix production code or
  requirements docs.
- **Test status (historical):** was left failing in the suite (not skipped/xfailed) so it stayed visible
  as an open discrepancy until dev/pm resolved it. Now resolved — see the top of this entry.

No other bugs were found in the original baseline pass — all other 130 tests passed against the
requirements/design docs as written at the time. No new bugs were found while adding the REV-003/004/005
coverage in the 2026-07-12 debt-cleanup pass either (§7) — all new tests pass against the current,
corrected requirements/design docs.

---

## 5. `qa/test-plan-full-codebase.md` corrections made in this pass

qa owns this file; the following factual-staleness fixes were made (content otherwise left as-is, per the
adoption-pass instruction not to rewrite a reasonable manual plan):

1. **Authority line** — added a 2026-07-12 correction note: the plan's "Solution Design v15" reference is
   superseded by `docs/design.md` (as-built, code-verified, condensed from `requirements_docs/SD.md` which
   is now at v20) and `docs/requirements.md` (FR1–FR31/NFR1–NFR5). Individual "SD v15" references
   scattered through the body (P1-3, P2-3, P2-6, P3-1–P3-4, P3-8, P6-4) were deliberately left as-is per
   the adoption-pass scope (only factually-wrong items were corrected, not every stale version pointer).
2. **P1-6** — corrected the asserted production model default from `gemini-3-flash` to `gemini-3.5-flash`
   (verified against `scripts/config.py` and `docs/requirements.md` §11).
3. **P6-2** — replaced the false claim that the shadow prompt lives in a `shadow_pilot_prompt.md` file (no
   such file exists in the repo) with the actual mechanism: `SHADOW_SYSTEM_PROMPT` in `scripts/shadow.py`,
   built by appending a position-awareness addendum to `ai_judge.BATCH_SYSTEM_PROMPT`. Also corrected the
   model-identity claim from `gemini-3-flash` to the real default pair
   (`gemini-3.5-flash`/`gemini-3.1-flash-lite`) and pointed at `ai_judge._models_to_try` as the shared
   model-resolution mechanism.
4. **Phase 6 header** — added a note mapping the phase to `docs/requirements.md` §10 (FR24–FR31, NFR5) and
   `docs/design.md` §13, replacing the prior ad hoc/undocumented shadow assumptions the phase was
   originally written against.
5. **P6-5** — changed the pass criterion from an implied "query executes → pass" to an explicit **BLOCKED
   on FR31** status: no committed, reproducible evaluation harness exists anywhere in the repo (the SQL
   migration's own comments reference a "wallet-sim recursive-CTE walk / harness" that lives only in the
   ad hoc Supabase SQL editor, not as versioned SQL/scripts — verified across `sql/`). The plan now
   instructs future executors not to mark this PASS by hand-running an ad hoc query, and to re-run once
   FR31's harness is committed.

Everything else in `qa/test-plan-full-codebase.md` (Phases 0–5, 7, P6-1/P6-3/P6-4) was unchanged in this
original pass. See §7 for further corrections made to this file's "Known Expected Findings" section in the
2026-07-12 debt-cleanup pass (REV-013).

---

## 6. Verdict (original baseline pass)

**Baseline established.** 130/131 automated tests passed; 1 genuine pre-existing doc-vs-code discrepancy
found and filed as BUG-001 (routed to dev/pm, not fixed here). This was a **starting point**, not a
completed regression campaign — see the original §3 deferred-coverage list (superseded by §7 below, which
closes most of it). No production code was modified to produce this report.

**This §6 verdict is superseded by §7's final verdict below**; kept here for the historical record of what
this pass looked like before the debt-cleanup follow-up.

---

## 7. Debt-cleanup pass — 2026-07-12 (user's "fix them all" following reviewer's adoption-pass audit)

Following reviewer's `docs/review-log.md` adoption-pass audit, the user asked qa to fix every item in its
own ownership: the intentionally-failing test (BUG-001/REV-001), the deferred coverage gaps (REV-003,
REV-004, REV-005), and the stale reference in this file's own test plan (REV-013). REV-006 was explicitly
out of scope for automation (see below). No production code (`scripts/`) was changed in this pass — only
`tests/`, this report, and `qa/test-plan-full-codebase.md`, all of which qa owns.

### 7.1 BUG-001 / REV-001 — resolved (doc correction, not code fix)

See §4 above for the full resolution writeup. `tests/test_config.py`'s stale test was renamed and
corrected to assert the now-accurately-documented behavior (typo fails closed; only truly empty/unset
fails open).

### 7.2 REV-003, REV-004, REV-005 — new automated coverage added

Added three new test files (see the coverage table in §2 for the full breakdown):
- `tests/test_ai_judge.py` (8 tests, FR9/FR10) — `judge_batch` control flow, mocked `google.genai.Client`.
- `tests/test_ingest.py` (11 tests, supports FR9/FR17) — headline relevance filter + session-aware
  pro-rating boundaries, mocked `yfinance.Ticker`.
- `tests/test_shadow.py` (14 tests, FR24–FR29) — `shadow.judge_batch_shadow` control flow (reusing the
  same fake-Gemini machinery as `test_ai_judge.py`, added as shared fixtures in `tests/conftest.py`) plus
  `run_shadow.py`'s wallet-walk derivation and same-data-reuse logic, with an in-memory fake Supabase
  double.

All externals remain fully mocked — no real network/API/DB call is made anywhere in this suite, consistent
with the existing suite's style (`tests/conftest.py`, `tests/test_notify.py`'s `requests.post` mock,
`tests/test_state.py`'s in-memory Supabase double).

### 7.3 REV-006 — ACCEPTED-DEBT, not automated

REV-006 (live-infra-dependent FR/NFR set: FR1, FR3, FR6, FR14, FR17, FR19–FR23, NFR2, NFR4) is **not**
addressed by new pytest coverage in this pass, by deliberate decision. It requires live Supabase/GitHub
Actions/GitHub Pages infrastructure to exercise meaningfully; automating it would mean either (a) mocking
so much of the real infra that the tests would no longer be testing the actual integration, which is
false confidence, or (b) standing up live-infra test fixtures, which is out of proportion for a `tests/`
regression-suite cleanup pass. This layer is — and was already correctly identified by reviewer as —
`qa/test-plan-full-codebase.md`'s domain by design: a manual, Claude-Code-executed playbook run against
real Supabase/GitHub Actions/GitHub Pages. **Marked `ACCEPTED-DEBT`** here; reviewer owns marking it as
such in `docs/review-log.md` (qa does not edit that file). Relayed to the orchestrator/user for visibility.

### 7.4 REV-013 — `qa/test-plan-full-codebase.md` corrected

The "Known Expected Findings" section (and the P1-2, P2-5, P4-5 cells that fed it) still described
`notify.py`'s `kind="reminder"` path as an expected/don't-fix *dead* (unreachable) branch. Reviewer
confirmed by reading current `scripts/notify.py` that this code path has been **fully removed**, not left
unreachable (`docs/design.md` §4.6: "the `reminder` kind is retired"). Corrected:
- **P1-2** (dead code scan) — replaced the "confirm it's still unreachable" instruction with a note that
  the branch no longer exists at all.
- **P2-5** (`notify.py` isolated path) — dropped the "confirm `kind="reminder"` never invoked" check;
  nothing to invoke.
- **P4-5** (`detail.html` per-ticker view) — clarified that "residual reminder handling" is not a known
  finding to look for; if a future run surfaces reminder-related UI text, that would be a NEW finding.
- **Known Expected Findings list** — removed the two reminder-related bullets entirely and added a
  correction note explaining why, so a future executor doesn't go looking for a dead branch that doesn't
  exist.

### 7.5 Suite re-run

**Run:** `python3 -m pytest tests/ -q` (Python 3.11.15, pytest 9.1.1, `requirements.txt` installed).

**Result: 164 passed / 0 failed / 164 total.**

(131 original baseline tests, with the 1 previously-failing test now fixed and passing, plus 33 new tests
across `tests/test_ai_judge.py`, `tests/test_ingest.py`, and `tests/test_shadow.py`.)

### 7.6 Shippability check

`tests/test_import_smoke.py` (16 tests, part of the full run above) re-confirms every module in `scripts/`
— including `ai_judge.py`, `ingest.py`, `shadow.py`, `run_shadow.py` — still imports cleanly against a
minimal mocked env, and that all four entry points (`run_hourly.py`, `run_discovery.py`, `run_shadow.py`,
`publish_prices.py`) still expose `main()` with no import-time side effects. No production code changed in
this pass, so no regression to the shippability baseline was possible or observed.

## 8. Verdict (final, this pass)

**PASS.** All owned debt-cleanup items resolved: BUG-001/REV-001 fixed (doc correction confirmed by a
corrected, passing test), REV-003/REV-004/REV-005 coverage gaps closed with 33 new mocked tests, REV-013's
stale test-plan reference corrected. REV-006 explicitly marked `ACCEPTED-DEBT` (out of proportion to
automate; remains `qa/test-plan-full-codebase.md`'s domain by design) rather than silently left off a
checklist. Full suite: **164 passed / 0 failed / 164 total.** No production code (`scripts/`) was changed
to produce this pass — only `tests/`, this report, and `qa/test-plan-full-codebase.md`.

---

## 9. INC-1 — NSE Shadow Wallet Pilot (FR32–FR39, NFR6) — 2026-07-14

**Owner:** qa. Tested dev's commit `e738d6f` ("dev: implement INC-1 NSE shadow wallet pilot (FR32–FR39,
NFR6) — pending QA") against `docs/requirements.md` §10.3 and `docs/design.md` §16, not against what the
code happened to do. `docs/handoff.md` read in full first.

### 9.1 Files added/extended this pass
- **NEW** `tests/test_run_shadow_nse.py` (29 tests) — FR32–FR39 coverage for `scripts/run_shadow_nse.py` /
  `scripts/shadow.py`'s new `models` param / the SQL migration / the workflow YAML.
- **EXTENDED** `tests/test_config.py` (+12 tests) — `SHADOW_NSE_ENABLED` fail-open/fail-closed matrix
  (mirroring the existing `SHADOW_ENABLED` pattern), kill-switch mutual independence, `SHADOW_NSE_PROMPT_VARIANT`,
  `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN` (incl. the FR34 under-30-min assertion), `config.nse_models()`. Also
  **corrected the two now-outdated model-default assertions** (Change 2): renamed
  `test_default_model_is_gemini_3_5_flash` → `test_default_model_is_gemini_2_5_flash`, asserting
  `GEMINI_MODEL == "gemini-2.5-flash"`; `test_default_backup_model` now asserts
  `GEMINI_MODEL_BACKUP == "gemini-2.5-flash-lite"`. These were the two intentionally-failing tests dev's
  handoff flagged as qa's to fix.
- **EXTENDED** `tests/test_import_smoke.py` (+1 parametrized case) — `run_shadow_nse` added to the
  entry-point list (`main()` present, no import-time side effects).

### 9.2 Requirement-by-requirement verification

| ID | What was checked | Result |
|---|---|---|
| **FR32** | `run_shadow_nse.NSE_MARKETS == {"NSE"}` (no US/TSX); source grepped/asserted for no `call_log_shadow` (US/CA table) write reference. | PASS |
| **FR33** | Wallet-walk ported to `test_run_shadow_nse.py` (Buy flat→holding, Sell holding→flat, Hold no-op, entry price/date recorded, empty history→flat, per-ticker independence) against `run_shadow_nse._derive_shadow_positions`, using a fake Supabase double that **raises `AssertionError` on any read from a table other than `call_log_shadow_nse`** — proves the walk never touches `call_log` or `call_log_shadow`, not just that it produces the right numbers. | PASS |
| **FR34** | `_latest_production_snapshots` asserted to read table `call_log`, filter `label="watchlist"`, `in_("ticker", …)`, newest-first-wins-per-ticker dedup. `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN` default confirmed `20` and asserted `< 30` (the NSE dispatch cadence) directly in the test, not just eyeballed. | PASS |
| **FR35 (HARD)** | `sql/shadow_nse_call_log_migration.sql` diffed structurally against `sql/shadow_call_log_migration.sql`: RLS enabled on both, no `create policy`, no actual `grant` **SQL statement** (comment-stripped before the check — first draft of this test false-positived on a comment that merely *mentions* "grant"; fixed in my own test, not production code), identical column set, both shadow-only columns present, same 2-index shape. Source-level check confirms `run_shadow_nse.py` writes only to `call_log_shadow_nse`. | PASS |
| **FR36 (HARD)** | `inspect.getsource` on both `run_shadow_nse.py` and `shadow.py` asserts no `import notify` / `notify.` reference. Workflow-level: NSE step's `env` block asserted to contain none of `NTFY_TOPIC`/`NSE_NTFY_TOPIC`/`DETAIL_PAGE_BASE`. | PASS |
| **FR37 (HARD)** | See §9.3 below — the most extensively tested requirement this increment. | PASS (+ 1 pre-existing bug found, not in INC-1 scope — see §9.4) |
| **FR38** | `SHADOW_NSE_ENABLED` matrix: unset→True, empty→True, `"false"`→False, `"FALSE"`→False, typos `"flase"`/`"no"`/`"0"`→False (all three explicitly parametrized, not just one typo). | PASS |
| **FR39** | `_run_cycle`'s source order asserted kill-switch check precedes `is_nse_open` check (string-offset assertion on the real source, not a re-implementation). Real-entry-point run with no env at all → clean no-op, exit 0 (§9.5). Unit-level: kill-switch-off and market-closed-and-not-forced cases both return without ever reaching `require_secrets()`/DB. | PASS |
| **Model config correction (Change 2)** | `config.GEMINI_MODEL == "gemini-2.5-flash"`, `config.GEMINI_MODEL_BACKUP == "gemini-2.5-flash-lite"` confirmed via the two corrected test_config.py assertions. `NSE_GEMINI_MODEL`/`_BACKUP` and `DISCOVERY_GEMINI_MODEL`/`_BACKUP` confirmed untouched (existing tests still pass unchanged). | PASS |
| **Non-negotiable: no hardcoded tunables** | All three new NSE config values (`SHADOW_NSE_ENABLED`, `SHADOW_NSE_PROMPT_VARIANT`, `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`) confirmed to read from `os.environ` with configurability tests that change the env var and assert the resulting behavior actually changes (not just that the attribute exists). | PASS |
| **`judge_batch_shadow(items, models=None)` non-negotiable** | Explicit test asserts passing `models=["nse-model-a", "nse-model-b"]` drives the call with that exact order; a **separate** test asserts the **default** (`models` omitted) resolves through `ai_judge._models_to_try(None)` to `config.GEMINI_MODEL`/`_BACKUP` exactly as before — i.e. the existing US/CA caller (`run_shadow.py`, which calls `judge_batch_shadow(items)` with no `models` arg) is unaffected. | PASS |

### 9.3 FR37 — mutual isolation, tested at three levels

1. **Kill-switch independence** (`test_config.py`): flipping `SHADOW_NSE_ENABLED` off leaves `SHADOW_ENABLED`
   `True` and vice versa — both directions tested in one function.
2. **Exception safety, incl. the SystemExit gap dev found and fixed:**
   - `run_shadow_nse.main()` with a mocked `_run_cycle` raising a plain `RuntimeError` → swallowed, `main()`
     returns normally. PASS.
   - `run_shadow_nse.main()` with a mocked `_run_cycle` raising `SystemExit` (simulating
     `config.require_secrets()`'s real failure mode) → **swallowed**, `main()` returns normally. This proves
     dev's `except (Exception, SystemExit)` fix actually works, both at the unit level and confirmed live at
     the real entry point (§9.5, test 3: `FORCE_RUN=true` + no secrets → `exit=0`).
   - Independently confirmed dev's claim that **`run_shadow.py` (US/CA) has the identical, unfixed bug**: a
     test mocks `run_shadow._run_cycle` to raise `SystemExit` and asserts (`pytest.raises(SystemExit)`) that
     `run_shadow.main()` does **not** swallow it — the `except Exception` catch in the shipped US/CA module
     does not catch `SystemExit` (a `BaseException` subclass). Confirmed live at the real entry point too
     (§9.5, test 4): `FORCE_RUN=true python3 scripts/run_shadow.py` with no secrets set exits **1**, not 0.
     **Filed below as a finding, not fixed** (out of INC-1 scope; production code is dev's).
3. **Workflow-level:** both the US/CA and NSE shadow steps asserted to carry `continue-on-error: true` and a
   positive `timeout-minutes`; step order asserted `production < US/CA shadow < NSE shadow`; each step's
   `if:` gate asserted to reference its own independent kill-switch Variable
   (`vars.SHADOW_ENABLED`/`vars.SHADOW_NSE_ENABLED` respectively, never the other). These tests use
   `pytest.importorskip("yaml")` since PyYAML is not a `requirements.txt` dependency (qa does not add
   production/test dependencies unilaterally to dev-owned `requirements.txt`); they run and pass in an
   environment with `pyyaml` installed (confirmed this pass) and skip cleanly without it.

### 9.4 Finding — pre-existing bug in shipped `run_shadow.py` (confirmed, out of INC-1 scope)

**Not filed as a numbered BUG-NNN** (no FR/NFR of THIS increment is violated by it — `run_shadow.py` is
existing, already-shipped code, not new/changed in INC-1's file list) but flagged here explicitly per the
task brief, for tech-lead/dev awareness on a future increment:

- **What:** `scripts/run_shadow.py::main()` (line ~212-215) catches only `except Exception`. `SystemExit`
  is a `BaseException` subclass, not an `Exception` subclass, so it is **not** caught. `config.require_secrets()`
  raises `SystemExit` on a missing secret. If `_run_cycle()` reaches that call and a secret is missing,
  `main()` propagates `SystemExit` instead of swallowing it — breaking the "main() always exits 0, shadow
  can never affect the production run" guarantee that FR29/NFR5 (the US/CA analogs of FR37/NFR6) require,
  in that one edge case.
- **Confirmed independently by qa, two ways:** (1) unit test
  `test_run_shadow_main_us_ca_track_has_the_same_systemexit_gap` — `pytest.raises(SystemExit)` around
  `run_shadow.main()` with a mocked `SystemExit`-raising `_run_cycle`. (2) Live at the real entry point:
  `env -i PATH="$PATH" FORCE_RUN=true python3 scripts/run_shadow.py` with no secrets set → prints the
  `require_secrets()` message and **exits 1**, whereas the equivalent NSE command
  (`python3 scripts/run_shadow_nse.py`) exits 0.
- **Mitigating factor:** the workflow step's `continue-on-error: true` still prevents this from failing the
  overall Actions run — so it is a defense-in-depth gap (the module's own documented guarantee is broken),
  not a currently-observable production incident.
- **Disposition:** dev fixed this in the new `run_shadow_nse.py` (`except (Exception, SystemExit)`) but did
  not backport the fix to `run_shadow.py` (correctly out of INC-1's stated file scope). Recommend a small
  follow-up increment/ticket to apply the same one-line fix to `run_shadow.py` for consistency — routed here
  for tech-lead/dev, not fixed by qa. **(Moot as of the 2026-07-16 shadow-tracks retirement — both files
  are deleted.)**

### 9.5 Shippability check — real entry point, INC-1 scope

Ran `scripts/run_shadow_nse.py` directly (not just via pytest mocks), from a clean environment
(`env -i PATH="$PATH" ...`, no `.env`, no leaked shell state):

1. No env at all (market closed at test time, no `FORCE_RUN`) → `[shadow-nse] NSE closed (force_run=False)
   — no-op.` — **exit 0**.
2. `SHADOW_NSE_ENABLED=false` → `[shadow-nse] SHADOW_NSE_ENABLED=false — NSE shadow track disabled, no-op.`
   — **exit 0**. Confirms the independent kill switch actually works at the real entry point, not only
   under test mocks.
3. `FORCE_RUN=true`, no secrets set → `[shadow-nse] ERROR (cycle skipped, production/US-CA-shadow
   unaffected): SystemExit: Missing required environment secrets: ...` — **exit 0**. Confirms dev's
   SystemExit fix live.
4. `FORCE_RUN=true`, fake (non-resolvable) Supabase URL + fake keys → real network `ConnectError` raised
   inside `_run_cycle`, caught, logged — **exit 0**.
5. For contrast, the same test #3 conditions against `scripts/run_shadow.py` (US/CA) → **exit 1** (§9.4).

All four NSE-track scenarios behaved as designed at the real entry point — this is a genuinely shippable
increment, not just something that passes isolated unit tests.

### 9.6 Full regression

**Run:** `python3 -m pytest tests/ -q` (Python 3.11.15, pytest 9.1.1, `requirements.txt` + `pyyaml`
installed in an isolated venv per this repo's established pattern — no project-level test-runner config
exists yet, so this mirrors dev's own smoke-test setup described in `docs/handoff.md`).

**Before this pass (dev's INC-1 commit, unmodified):** 163 passed / 2 failed / 165 total — the 2 failures
were the expected, dev-flagged stale model-default assertions (§9.1).

**After this pass:** **207 passed / 0 failed / 207 total.** 42 new tests added this increment (29 in the
new `tests/test_run_shadow_nse.py`, 12 new in `tests/test_config.py`, 1 new parametrized case in
`tests/test_import_smoke.py`), plus the 2 corrected assertions now passing. **Zero unexpected
regressions** — every pre-existing test (FR1–FR31/NFR1–NFR5 baseline coverage) still passes unchanged.

Existing US/CA shadow pilot behavior confirmed byte-for-byte unchanged in outcome: all of
`tests/test_shadow.py`'s original 14 tests (control flow, wallet-walk, same-data reuse) still pass without
modification, and the new `judge_batch_shadow(items, models=None)` default-path test in
`tests/test_run_shadow_nse.py` independently re-confirms the default resolves exactly as before.

### 9.7 Verdict — INC-1 (FR32–FR39, NFR6)

**PASS.** All 8 functional/hard requirements (FR32–FR39) and NFR6 verified against `docs/requirements.md`
§10.3 / `docs/design.md` §16, with tests written against the requirement text, not reverse-engineered from
the implementation. Both intentionally-stale `test_config.py` assertions corrected. Full suite: **207
passed / 0 failed**. Real-entry-point shippability check passed for all NSE-track scenarios. No production
code was modified by qa.

**One finding logged for tech-lead/dev, not a blocker for INC-1:** the pre-existing `SystemExit`-swallowing
gap in `scripts/run_shadow.py::main()` (§9.4) — confirmed real, out of INC-1's file scope, does not violate
any FR/NFR this increment claims, mitigated by `continue-on-error: true` at the workflow level. Recommend a
follow-up fix for consistency with the now-corrected `run_shadow_nse.py`.

**Ready for reviewer.**

---

## 10. INC-2 — Shared Wallet-Sim Evaluation Harness (FR31) — 2026-07-14

**Owner:** qa. Tested dev's commit `2d2cc13` ("dev: implement INC-2 shared wallet-sim evaluation harness
(FR31)") against `docs/requirements.md` §10.2 (FR31) and `docs/design.md` §17, not against what the code
happened to do. `docs/handoff.md` (INC-2) read in full first.

### 10.1 Files added this pass
- **NEW** `tests/test_wallet_sim.py` (20 tests) — direct unit tests of `wallet_sim.walk`, the pure state
  machine, plus the zero-I/O non-negotiable.
- **NEW** `tests/test_eval_shadow.py` (34 tests) — `build_report`/`render_report` correctness, the FR31
  determinism acceptance test, the read-only-guarantee regression guard, CLI parsing (`_parse_args`),
  `default_window`/`parse_window_bound`, the `fetch_shadow_rows`/`fetch_production_rows` I/O seam against a
  fake Supabase double, and an `EVAL_WINDOW_DAYS` configurability check through `main()`.
- **NEW** `tests/test_run_shadow.py` (9 tests) — closes the gap the handoff flagged under "Known
  limitations": no dedicated test file existed for `run_shadow.py`'s (US/CA) `_derive_shadow_positions`
  before this pass. Mirrors `test_run_shadow_nse.py`'s wallet-walk coverage, retargeted to the US/CA track,
  confirming the refactored `wallet_sim.walk`-backed implementation is correct on its own (not just
  "unchanged since the old inline version worked").
- **EXTENDED** `tests/test_config.py` (+2 tests) — `EVAL_WINDOW_DAYS` default (14) and env-override
  propagation.

### 10.2 Requirement-by-requirement verification

| ID | What was checked | Result |
|---|---|---|
| **FR31 — core state machine** | `wallet_sim.walk` tested directly with no DB: Buy flat→holding, Sell holding→flat, Hold no-op (both flat and holding), Buy-while-holding no-op (entry price/date provably unchanged), Sell-while-flat no-op, empty input → flat/no round-trips/no open position, multiple round-trips in one sequence with correct per-trip `return_pct`, `_return_pct` formula verified against the literal `(exit/entry - 1) * 100` rounded-to-4dp spec, `_return_pct(None, x)`/`_return_pct(x, None)`/`_return_pct(0, x)` all return `None` without raising (zero-entry-price divide-by-zero guard explicitly tested), a `Sell` with no price yields `return_pct: None` not a crash, `mark_price` marks an open position with correct `unrealized_return_pct`, and marking is skipped (open=None) when flat. | PASS |
| **FR31 — determinism (THE acceptance criterion, design §17.3)** | `test_build_report_is_deterministic_identical_input_identical_output`: two `build_report()` calls on identical shadow/production row lists assert `report1 == report2` (dict equality, not just "no error"). Also: order-independence (shuffled input row order produces the same output — tickers/timestamps are sorted internally), `render_report()` determinism, and `json.dumps(..., sort_keys=True)` byte-identical across two builds (the property `--output` relies on). | PASS |
| **FR31 — read-only guarantee (HARD, design §17.3)** | Automated regression guard (not a one-off manual grep): `inspect.getsource` + regex for `\.insert\(`/`\.update\(`/`\.upsert\(`/`\.delete\(` against both `eval_shadow.py` and `wallet_sim.py` with the module docstring text stripped first (so the docstring's own prose mentioning these strings doesn't false-positive); a second test reads the raw file from disk (not just the loaded module object) and asserts every regex match is the docstring's own "No .insert(..." prose line, reproducing dev's manual grep as a committed, re-runnable test. | PASS |
| **`build_report`/`render_report` correctness** | Synthetic shadow rows (AAPL: Buy→Hold→Sell round trip, winning; MSFT: Buy→Hold, still open) + production rows: verdict counts correct per-ticker and total, round-trip count/wins/win-rate/`realized_return_pct_sum` math correct (checked against the literal formula, not just "some number"), a losing round trip correctly counted as 0 wins, per-ticker breakdown keys/values correct, `open_position` correctly marked to the latest snapshot price with correct `unrealized_return_pct`. `render_report()` does not crash on `win_rate=None` (MSFT, zero round trips) or on a fully empty report (zero tickers) — renders `"n/a"` in both cases as designed. | PASS |
| **CLI parsing (`_parse_args`)** | `--track` omitted → `SystemExit` (argparse required-arg error). `--track bogus` → `SystemExit` (choices violation). `--track us_ca`/`--track nse` both accepted. `--since`/`--until` optional, pass through verbatim when given, `None` when omitted (so `main()`'s defaulting logic is what applies `EVAL_WINDOW_DAYS`). `--output` optional. `default_window(now, days)` returns `[now-days, now]` and a different `days` value measurably shifts the window (configurability check). `parse_window_bound` accepts a bare date, a full ISO datetime, anchors a naive datetime to UTC (`tzinfo == timezone.utc`), and preserves an explicit non-UTC offset unchanged. | PASS |
| **Refactor behavior-preservation** | `tests/test_run_shadow_nse.py`'s existing 6 wallet-walk tests re-run unmodified and still pass (confirmed as part of the full-suite run, §10.4) — the NSE track's refactored `_derive_shadow_positions` is provably unchanged in observable behavior. New `tests/test_run_shadow.py` independently exercises the same Buy/Sell/Hold/no-op/empty/multi-ticker matrix directly against the US/CA `_derive_shadow_positions` (previously untested in isolation — the handoff's own "Known limitations" flagged this gap), closing it rather than just trusting the handoff's manual-equivalence claim. | PASS |
| **`EVAL_WINDOW_DAYS` config** | Default confirmed `14` when unset (`test_eval_window_days_defaults_to_14`); env-override confirmed to propagate (`EVAL_WINDOW_DAYS=7` → `config.EVAL_WINDOW_DAYS == 7`). A further end-to-end configurability test drives `eval_shadow.main(["--track", "us_ca"])` with `config.EVAL_WINDOW_DAYS` monkeypatched to `3` and a fake Supabase double, spying on the actual `since`/`until` window passed to `fetch_shadow_rows`, and asserts the queried window is exactly 3 days wide — proving the value is read live from config at call time, not hardcoded anywhere in `eval_shadow.py`. Confirmed by inspection: `grep -rn EVAL_WINDOW_DAYS scripts/` shows the only definition is in `config.py`; `eval_shadow.py` references it only via `config.EVAL_WINDOW_DAYS`. | PASS |

### 10.3 Non-negotiables checked

- **`wallet_sim.py` zero I/O:** `grep -n "^import\|^from" scripts/wallet_sim.py` returns **nothing** — the
  file has no imports at all (not even stdlib), confirming it is a pure function over plain dicts. Also
  asserted in `tests/test_wallet_sim.py` via `inspect.getsource` (no `import state`/`supabase`/`requests`/
  `state.client` anywhere in the module).
- **`eval_shadow.py` never writes to any table:** confirmed both by the automated regression guard (§10.2
  above) and by re-running dev's exact manual grep command
  (`grep -n "\.insert(\|\.update(\|\.upsert(\|\.delete(" scripts/eval_shadow.py scripts/wallet_sim.py`) —
  the only match is the docstring's own prose line.
- **`EVAL_WINDOW_DAYS` is config-driven, not hardcoded elsewhere:** confirmed by inspection (see table above)
  and by the live configurability test.

### 10.4 Shippability check — real entry point

Ran `scripts/eval_shadow.py` directly as a CLI, not just via pytest function calls:
1. `python3 eval_shadow.py` (no `--track`) → argparse usage error, **exit 2**. Correct required-arg behavior.
2. `python3 eval_shadow.py --help` → renders full usage/help text, **exit 0**.
3. `python3 eval_shadow.py --track bogus` → argparse choices error (`invalid choice: 'bogus'`), **exit 2**.
4. Full end-to-end run through the real `main(argv)` entry point (real argv-style CLI args
   `--track us_ca --since ... --until ... --output ...`) with `state.client` monkeypatched to a fake
   Supabase double serving synthetic `call_log_shadow`/`call_log` rows: printed a correct, well-formed
   report to stdout (verdict counts, round-trip P&L, per-ticker breakdown) and wrote a valid JSON file to
   `--output` whose contents matched the printed report. This exercises argparse, config defaulting,
   `build_report`, `render_report`, and the JSON-write path all through the actual entry point, not through
   directly-called internals only.

Also confirmed `run_shadow.py`, `run_shadow_nse.py`, `wallet_sim.py`, `eval_shadow.py`, and `config.py` all
import cleanly (no import-time side effects, no circular-import issues introduced by the new `wallet_sim`
import in both orchestrators).

### 10.5 Full regression

**Run:** `python3 -m pytest tests/ -q` (Python 3.11.15, `requirements.txt` + `pytest` + `pyyaml` installed
in an isolated venv, same pattern as INC-1).

**Before this pass (dev's INC-2 commit, unmodified — INC-1 baseline):** 209 passed / 0 failed / 209 total
(per `docs/handoff.md`).

**After this pass: 274 passed / 0 failed / 274 total.** 65 new tests added this increment: 20 in
`tests/test_wallet_sim.py`, 34 in `tests/test_eval_shadow.py`, and 9 in `tests/test_run_shadow.py` (all
three new files, combined new-file total 63), plus 2 new tests added to the pre-existing
`tests/test_config.py`, for 65 net new. **Zero regressions** — every pre-existing test (FR1–FR39/NFR1–NFR6
baseline coverage, incl. both shadow tracks' wallet-walk tests) still passes unchanged.

### 10.6 Bugs filed

**None.** No FR31 violation, no read-only violation, no determinism failure, and no refactor regression
found. The implementation matches `docs/design.md` §17 and `docs/requirements.md` §10.2 as written.

### 10.7 Verdict — INC-2 (FR31)

**PASS.** FR31 (committed, reproducible, read-only shared evaluation harness covering both shadow tracks)
verified against the requirement text: `wallet_sim.walk` is a correct, zero-I/O, unit-tested pure function;
`build_report`/`render_report` are correct and — the explicit FR31 acceptance bar — deterministic across
repeated calls on identical input; the harness never writes to any table (automated regression guard, not
just a one-time grep); both live orchestrators' refactored `_derive_shadow_positions` are behavior-preserving
and now each have dedicated direct test coverage; `EVAL_WINDOW_DAYS` is genuinely config-driven. Full suite:
**274 passed / 0 failed**, zero regressions vs. the INC-1 baseline. Real-entry-point shippability check
passed (argparse error paths + a full `main()` run producing a correct report and JSON file). No production
code was modified by qa.

**Ready for reviewer.**

### 10.8 Addendum — REV-018 fix: stale test corrected 2026-07-15

dev fixed REV-018: `scripts/run_shadow.py::main()` now catches `except (Exception, SystemExit)`, matching
`run_shadow_nse.py`'s existing pattern (see §9.4 finding, now resolved). This made
`test_run_shadow_main_us_ca_track_has_the_same_systemexit_gap` (in `tests/test_run_shadow_nse.py`) stale —
it was a `pytest.raises(SystemExit)` assertion written specifically to confirm the bug existed, and with the
bug fixed that assertion is now inverted (would fail against correct behavior).

**Fix applied by qa (test-only, no production code touched):** renamed the test to
`test_run_shadow_main_us_ca_track_now_swallows_systemexit_matching_nse` and repurposed it to assert the
fixed behavior: `run_shadow.main()` is called with a mocked `_run_cycle` that raises `SystemExit`, and the
test now asserts `main()` completes normally without raising — mirroring
`test_run_shadow_nse_main_swallows_systemexit_and_returns`'s existing structure for the NSE track. Coverage
of the SystemExit-swallowing guarantee is preserved (upgraded, not deleted) for both tracks.

**Full regression after this fix:** `python3 -m pytest tests/ -q` → **274 passed / 0 failed**. Test count
unchanged (assertion corrected, not added/removed), zero regressions.

### 10.9 Addendum — REV-015 cleanup fix caused a regression: stale test assertion corrected 2026-07-15

**Regression found:** the orchestrator's pre-closure full-suite run turned up a genuine failure —
`tests/test_run_shadow_nse.py::test_both_shadow_steps_have_continue_on_error_and_timeout_minutes` (273
passed / 1 failed). Root cause: as part of the REV-015 fix (making the shadow-step timeout configurable via
a repo Variable rather than a hardcoded literal), dev changed both shadow steps in
`.github/workflows/hourly-watchlist.yml` from a literal `timeout-minutes: 15` to the expression
`timeout-minutes: ${{ fromJSON(vars.SHADOW_TIMEOUT_MINUTES || '15') }}`. This is the correct, intended fix —
it removes a hardcoded tunable per the project's non-negotiable config rule. But the test's assertion,
written back in INC-1 against the literal form, did `isinstance(s.get("timeout-minutes"), int)`.
`_workflow_steps()` parses the workflow YAML with `yaml.safe_load`, which does not evaluate GitHub Actions
`${{ }}` expressions — it returns the raw string `"${{ fromJSON(vars.SHADOW_TIMEOUT_MINUTES || '15') }}"` —
so the `isinstance(..., int)` check started failing the moment the literal was replaced.

**Process gap (the actual lesson):** REV-015's own fix verification only confirmed "the YAML still parses
as valid" (i.e., `test_workflow_parses_as_valid_yaml` and a manual/CI YAML-lint check), not "the full test
suite still passes." A workflow-file edit was declared done without qa re-running `pytest tests/ -q`, so a
test that encoded an assumption about the *old* literal form went undetected until this later full-suite
check. Per this project's pipeline, no fix — including a cleanup fix to a non-code artifact like a workflow
file — should be considered complete without a full-suite regression run; that step was skipped here.

**Fix applied by qa (test-only, no production code touched):** rewrote the assertion in
`test_both_shadow_steps_have_continue_on_error_and_timeout_minutes` to validate the *intent* ("a
hang-isolation timeout bound is configured on both shadow steps, driven by `SHADOW_TIMEOUT_MINUTES` with a
sane fallback") rather than the raw YAML type. The test now accepts either form: a literal positive int
(in case a literal is ever reintroduced), or a string that both contains `fromJSON`/`vars.SHADOW_TIMEOUT_MINUTES`
and contains a `||` fallback default — i.e., it now positively verifies the configurability property REV-015
was introducing, rather than accidentally asserting against it.

**Audit for the same stale assumption elsewhere:** grepped all of `tests/` for `timeout-minutes` and
`SHADOW_TIMEOUT_MINUTES`. No other test file references either string — this was the only place the old
literal-form assumption existed.

**Full regression after this fix:** `python3 -m pytest tests/ -q` → **274 passed / 0 failed** (same total
as before the regression was introduced — one assertion corrected, nothing added or removed). Zero other
regressions.

---

## Shadow tracks retirement — removal regression pass — 2026-07-16

**Scope:** the US/TSX and NSE shadow wallet pilots (FR24–FR31/NFR5, FR32–FR39/NFR6) were retired; dev
deleted their code (`scripts/shadow.py`, `scripts/run_shadow.py`, `scripts/run_shadow_nse.py`,
`scripts/wallet_sim.py`, `scripts/eval_shadow.py`, both shadow SQL migrations, both workflow steps) and
edited `scripts/config.py`/`.github/workflows/hourly-watchlist.yml`/`scripts/ai_judge.py` — see the
"Retired: shadow-pilot tracks" note in `docs/design.md` (removal plan) and `docs/handoff.md`. This is a removal-only change; no new FR/NFR IDs
to cover, no new production behavior. QA's job: delete/edit the now-orphaned tests, confirm the suite is
clean, and confirm FR1–FR23 production paths are unaffected.

### What qa did

- **Deleted** (target modules no longer exist): `tests/test_shadow.py`, `tests/test_run_shadow.py`,
  `tests/test_run_shadow_nse.py`, `tests/test_eval_shadow.py`, `tests/test_wallet_sim.py`.
- **Edited** `tests/test_config.py` — removed the `SHADOW_ENABLED`/`SHADOW_NSE_ENABLED` fail-open/closed
  matrices, `SHADOW_NSE_PROMPT_VARIANT`, `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`, and `EVAL_WINDOW_DAYS` test
  cases; kept the `nse_models()` tests (production NSE helper, unrelated to the shadow tracks despite the
  name overlap) and all non-shadow config/market-hours coverage. Trimmed the module docstring's shadow
  reference.
- **Edited** `tests/test_import_smoke.py` — removed `run_shadow`/`run_shadow_nse` from the entry-point
  parametrization (now `run_hourly`, `run_discovery`, `publish_prices` only) and the module docstring's
  `run_shadow.py` mention.
- **Edited** `tests/conftest.py` — reworded the shared-Gemini-fake comments/docstrings that referenced
  `test_shadow.py`/`shadow.judge_batch_shadow` (no dedicated shadow fixtures existed to remove; the fake
  Gemini client machinery is still used by `test_ai_judge.py` and was kept as-is).
- **Edited** `qa/test-plan-full-codebase.md` — marked "Phase 6 — Shadow Pipeline" (P6-1..P6-5) RETIRED with
  a pointer to the "Retired: shadow-pilot tracks" note in `docs/design.md`, replaced P3-7 ("Shadow
  isolation") with a retired stub, and updated
  P3-1's pass criteria to no longer expect `call_log_shadow` (noting the drop migration
  `sql/drop_shadow_tables_migration.sql` had not yet been applied to the live project as of this update).

### Suite result

**Run:** `python3 -m pytest -q --tb=short` (Python 3.11, `requirements.txt` + `pytest` installed).

**144 passed / 0 failed / 144 total.** Zero collection errors (no import failures from the deleted shadow
modules). Confirmed by targeted grep: no test file references `SHADOW_ENABLED`/`SHADOW_NSE_ENABLED`/
`EVAL_WINDOW_DAYS`, and no test imports `scripts.shadow`/`scripts.run_shadow`/`scripts.run_shadow_nse`/
`scripts.wallet_sim`/`scripts.eval_shadow`.

Remaining suite: `tests/test_ai_judge.py`, `tests/test_config.py`, `tests/test_import_smoke.py`,
`tests/test_ingest.py`, `tests/test_notify.py`, `tests/test_prefilter.py`, `tests/test_state.py`,
`tests/test_textutil.py` — all FR1–FR23 production-path coverage, unchanged in behavior, all passing.

### Shippability check

Ran the real-entry-point import smoke check dev's handoff documented (`docs/handoff.md` "How to verify"),
independently reproduced by qa:
```
import config, ai_judge, ingest, notify, prefilter, run_discovery, run_hourly, publish_prices, state, textutil
assert not [a for a in dir(config) if 'SHADOW' in a.upper()]
assert not hasattr(config, 'EVAL_WINDOW_DAYS')
assert hasattr(config, 'nse_models')
assert hasattr(run_hourly, 'main') and hasattr(run_discovery, 'main') and hasattr(publish_prices, 'main')
```
All assertions passed — every production entry point still imports cleanly and exposes `main()`; `config.py`
exposes no `SHADOW_*`/`EVAL_WINDOW_DAYS` names; `nse_models()` (the production NSE model-pair helper,
unrelated to the shadow tracks) is intact.

### Full regression — FR1–FR23 production paths

`tests/test_state.py` (verdict-transition state machine, FR7/FR8/FR15), `tests/test_prefilter.py`
(discovery gates, FR4), `tests/test_notify.py` (alerting, FR12/FR13/FR18/FR23), `tests/test_ai_judge.py`
(FR9/FR10), `tests/test_ingest.py` (FR9/FR17), `tests/test_textutil.py`, and the remaining
`tests/test_config.py`/`tests/test_import_smoke.py` coverage all pass unmodified in behavior — only shadow-
specific cases were removed from `test_config.py`/`test_import_smoke.py`, nothing FR1–FR23-relevant was
touched. This is a removal-only change to `scripts/`; regression is clean as expected.

### Bugs filed

**None.** No test/production-code mismatch found. dev's removal matches the "Retired: shadow-pilot tracks"
note in `docs/design.md` exactly:
`scripts/config.py` exposes no `SHADOW_*`/`EVAL_WINDOW_DAYS` names, all seven deleted files are gone, the
workflow YAML's shadow steps are gone, and no `scripts/`/`sql/`/`.github/workflows/` file still references
"shadow" (confirmed by grep, matching dev's own handoff sweep).

### Verdict

**PASS.** 144/144 tests passing, zero collection errors, zero regressions in FR1–FR23 production-path
coverage. Test suite and `qa/test-plan-full-codebase.md` fully align with the shadow-tracks retirement.

**Not qa's action item, flagged for the orchestrator/other agents (already noted in `docs/handoff.md`):**
`sql/drop_shadow_tables_migration.sql` has not yet been applied to the live Supabase project — the
`call_log_shadow`/`call_log_shadow_nse` tables may still exist in the live DB. Not a test-suite concern (no
automated test in this repo queries live Supabase), but relevant to `qa/test-plan-full-codebase.md` P3-1
next time that manual plan is executed against live infra.

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
