# Test Report — Baseline Establishment (Adoption Pass)

**Owner:** qa. **Date:** 2026-07-12. **Type:** Baseline snapshot for an existing, already-live system —
NOT a claim that a full test campaign has been run against production. This is the first automated
`tests/` suite this repo has ever had.

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

### Suite result

**Run:** `python3 -m pytest tests/ -q` (Python 3.11.15, pytest 9.1.1, `requirements.txt` installed).

**Result: 130 passed / 1 failed / 131 total.**

---

## 3. Not covered in this pass (explicitly deferred, not silently skipped)

Per the adoption-pass scope instruction, this baseline does NOT include:
- `ai_judge.py`'s prompt/parse/retry logic (FR9, FR10) — would need a mocked `genai.Client`; higher
  effort, deferred to a follow-up increment.
- `ingest.py`'s yfinance-wrapping logic (headline relevance filter, session-aware pricing) — would need
  mocked `yf.Ticker`; deferred.
- `shadow.py`'s orchestration (`run_shadow.py`'s wallet-walk derivation, FR25/FR26) — deferred; the shadow
  prompt-construction fact (FR24/FR25, no separate prompt file) was verified by direct code reading for
  the `qa/test-plan-full-codebase.md` correction (§5 below) but has no automated test yet.
- Any live Supabase/GitHub Actions/dashboard/detail-page verification (FR1, FR3, FR6, FR14, FR17,
  FR19–FR23, NFR2, NFR4) — these require real infra and are the domain of
  `qa/test-plan-full-codebase.md` Phases 3–5, which remains the manual playbook for that layer. This
  automated suite does not attempt to replace it.
- A true end-to-end run from a real entry point against live Supabase/Gemini/ntfy — out of scope for a
  proportionate baseline pass per the task instructions ("don't try to build full integration/e2e coverage
  in one pass"). `tests/test_import_smoke.py` is the closest thing this pass has to a shippability check
  (confirms the entry points are import-clean, thin orchestrators with no import-time side effects) but is
  not a substitute for a real dry run.

**FR31** (committed, reproducible shadow evaluation harness) has no code to test — it is an acknowledged
open requirements gap (`docs/requirements.md` §10.2), not a missed test.

---

## 4. Bugs filed

### BUG-001 — FR30 / NFR5: `SHADOW_ENABLED` does not fail open on a mistyped value, contradicting the documented accepted-risk posture

- **Requirement violated:** FR30 ("**Only the literal string `false` disables it.** ... an unset/mistyped
  `SHADOW_ENABLED` Variable *silently keeps the pilot running*") and NFR5 (same posture, restated).
  `docs/design.md` §0 load-bearing item #10 and §13.6 both restate this identically: "an unset/mistyped
  Variable *keeps the pilot running*."
- **Increment / component:** `scripts/config.py` (adoption-pass baseline finding — pre-existing code, not
  introduced by this pass).
- **Reproduction:**
  1. `export SHADOW_ENABLED=flase` (a plausible typo of `false`)
  2. `python3 -c "import config; print(config.SHADOW_ENABLED)"`
  3. Automated repro: `tests/test_config.py::test_shadow_enabled_only_literal_false_disables_a_typo_stays_open`
- **Expected (per FR30/NFR5, verbatim from the requirements/design docs):** `True` — "only the literal
  string `false` disables it"; anything else, including a typo, should leave the pilot running.
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
- **Test status:** left failing in the suite (not skipped/xfailed) so it stays visible as an open
  discrepancy until dev/pm resolve it one way or the other.

No other bugs were found in this pass — all other 130 tests pass against the requirements/design docs as
written.

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

Everything else in `qa/test-plan-full-codebase.md` (Phases 0–5, 7, the Known Expected Findings and
Blocking Dependencies sections, P6-1/P6-3/P6-4) is unchanged.

---

## 6. Verdict

**Baseline established.** 130/131 automated tests pass; 1 genuine pre-existing doc-vs-code discrepancy
found and filed as BUG-001 (routed to dev/pm, not fixed here). This is a **starting point**, not a
completed regression campaign — see §3 for explicitly deferred coverage (`ai_judge.py`, `ingest.py`,
`shadow.py` orchestration, and all live-infra/dashboard verification, which remains
`qa/test-plan-full-codebase.md`'s domain). No production code was modified to produce this report.
