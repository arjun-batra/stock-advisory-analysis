# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-4 — AI provider abstraction (FR33) — 2026-07-28

**Scope:** `docs/design/increment-plan.md` "### INC-4 — AI provider abstraction" (6 acceptance criteria),
design `docs/design/operational-controls.md` §14, dev handoff `docs/handoff.md`. Files under test: new
`scripts/ai_provider.py`, refactored `scripts/ai_judge.py`, `scripts/config.py`, `tests/conftest.py`,
`docs/design/non-functional-ops.md`. Verified independently against §14's design text and the pre-INC-4
commit (`99524e6`), not against dev's self-report alone.

**AC6 (live smoke test against real Gemini) is explicitly deferred to the final end-to-end test**, same
treatment as INC-3's live-Supabase-dependent criteria — no `GEMINI_API_KEY` (or any Google credential)
exists in this sandbox. No live call was faked or simulated to produce a pass.

### AC-by-AC result

1. **`ai_provider.py` defines the full §14.2 interface — VERIFIED, PASS.** Imported `AIProvider`,
   `ProviderResult`, `TokenUsage`, `ErrorClass`, `ProviderError`, `BatchVerdictSchema`, `GeminiProvider`,
   `get_provider()` by name directly (not via dev's report). Confirmed `AIProvider` is an `abc.ABC` with
   exactly one abstract method (`generate`), `GeminiProvider` is a concrete subclass, `ProviderResult`
   fields are `{text, usage}`, `TokenUsage` fields are `{prompt, output, thoughts, total}`, `ErrorClass`
   has exactly `RETRYABLE`/`FATAL` members, `BatchVerdictSchema` fields are `{verdicts, confidences}` —
   all match §14.2's fenced code block field-for-field.

2. **Zero `genai`/`types.` references in `ai_judge.py` — VERIFIED, PASS.** Ran
   `grep -n "genai\|types\." scripts/ai_judge.py` myself: exit code 1, zero matches. Confirmed by reading
   `ai_judge.py` in full: its only imports are `dataclasses`, `json`, `random`, `time`, `datetime`,
   `config`, `ai_provider.{BatchVerdictSchema, ErrorClass, ProviderError, TokenUsage, get_provider}`,
   `textutil.clip` — no `google.genai`/`httpx` anywhere.

3. **`judge_batch()` signature/return contract unchanged; zero diff to `run_hourly.py`/`run_discovery.py`
   — VERIFIED, PASS.** `judge_batch(items, models=None, provider=None)` — the added `provider` param is
   optional and defaults to `get_provider(config.AI_PROVIDER)`, so every existing call site is unaffected.
   Return dict shape read directly from `_enrich()`/`_parse_batch()`: still
   `{ticker: {verdict, confidence, rationale, raw_model_response, parse_status, model_used, usage,
   fallback_from, retry_count}}`; `usage` is now built via `dataclasses.asdict()` from the provider's
   `TokenUsage`, producing the same `{"prompt","output","thoughts","total"}` plain-dict shape as before.
   `git show --stat 3e3e34d` (the INC-4 commit) confirms `run_hourly.py`/`run_discovery.py` are absent
   from the changed-file list; both modules still `import ai_judge` and call
   `ai_judge.judge_batch(...)` with no `provider=` argument, confirmed by grep.

4. **Full suite passes, no assertion changes, retry/backoff logic byte-preserved — VERIFIED, PASS.**
   - `python3 -m pytest -q --tb=short` (fresh run, repo root): **158 passed, 0 failed**, matching dev's
     reported count.
   - `git diff 99524e6 3e3e34d -- 'tests/test_*.py'` → empty (confirmed no test file changed at all, not
     just "no assertion changes" — zero diff on every `test_*.py`). Only `tests/conftest.py` changed, and
     reading that diff directly confirms it is docstring/target-only: the single functional change is
     `monkeypatch.setattr(ai_judge, "_client", ...)` → `monkeypatch.setattr(ai_provider, "_client", ...)`
     (the transport seam moved modules, as documented), with the same `lambda` shape and the same
     `time.sleep` stub.
   - Read `git diff 99524e6 3e3e34d -- scripts/ai_judge.py` directly (not the summary): `_generate()`'s
     retry loop is character-identical except for parameter names (`client`→`provider`,
     `config.GEMINI_MAX_RETRIES`→`max_retries` etc., now passed in rather than read from `config`
     directly) — same `cap_s = retry_base_ms * (2 ** retries) / 1000.0`, same
     `delay_s = random.uniform(0, cap_s)` full-jitter formula, same retry-count/log-line text (just
     interpolating a parameter instead of a `config.*` global). `_RETRYABLE_CODES = {429, 503, 504}` /
     `_RETRYABLE_STATUSES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED"}` and the
     httpx-timeout/bare-`TimeoutError` check moved into `ai_provider._classify()` with identical logic
     (confirmed by direct comparison of the old `_is_retryable()` body against the new `_classify()` body
     in the diff — same conditions, same order). The "call config" log line
     (`timeout=...ms, max_retries=..., retry_base=...ms (full jitter)`) is still printed with the same
     text, relocated from `_client()` into `judge_batch()`.

5. **`config.AI_PROVIDER` (default `"gemini"`) exists; `get_provider("bogus")` raises `SystemExit` —
   VERIFIED, PASS.** `python3 -c "import config; print(config.AI_PROVIDER)"` → `'gemini'`. Manual checks
   run directly (not a permanent test — reasonable for one defensive branch, per the task brief):
   - `ai_provider.get_provider("bogus")` → `SystemExit: Unknown AI_PROVIDER 'bogus'; supported: ['gemini']`.
   - `AI_PROVIDER=notreal` env override → `config.AI_PROVIDER == 'notreal'`, and
     `ai_provider.get_provider()` (no arg, falls through to `config.AI_PROVIDER`) also raises the same
     `SystemExit` — confirms the config-driven default path, not just the explicit-argument path, is
     genuinely wired (a configurability check, not just an existence check).
   - `docs/design/non-functional-ops.md` §9 diffed (`git diff 99524e6 3e3e34d`): `AI_PROVIDER` added to
     the core tunables baseline paragraph with a correct §14.4 pointer; the old "DRAFT, INC-4 not yet
     implemented" stub was updated to "IMPLEMENTED (INC-4, 2026-07-28)" rather than left stale.

6. **Live Gemini smoke test — DEFERRED (not pass/fail).** No `GEMINI_API_KEY` or other Google credential
   is available in this sandbox. Not attempted to fake. dev's handoff documents a partial substitute (an
   invalid-key call reaching Google's real endpoint end-to-end, correctly classified `fatal`) which
   demonstrates the wiring is live but does not satisfy AC6's "returns valid verdicts" bar. **Carried
   forward to qa's final end-to-end test**, same as INC-3's live-Supabase-dependent AC1–AC5 — requires a
   real `GEMINI_API_KEY` supplied to a qa session (or a run on infra that has one).

### Full regression

`python3 -m pytest -q --tb=short` (repo root, fresh run, independent of dev's report): **158 passed / 0
failed**, 0 collection errors. `tests/test_import_smoke.py`'s glob-based module parametrization
automatically picked up the new `scripts/ai_provider.py` with no dev/qa edit required — it imports cleanly
and is covered by the existing shippability smoke check.

### Shippability check

Real entry points (`scripts/run_hourly.py`, `scripts/run_discovery.py`) both import cleanly post-refactor
and still call `ai_judge.judge_batch(...)` with their pre-existing argument shapes (no `provider=`
argument at either call site — confirmed by direct grep, not just trusting the "unchanged" claim). This is
not itself a full live run (that requires AC6's deferred `GEMINI_API_KEY`), but confirms the refactor did
not break the two production orchestrators' import/call surface.

### Bugs filed

**None.** No FR33 violation, no return-contract change, no retry/backoff-behavior drift found. The
implementation matches `docs/design/operational-controls.md` §14 as written.

### Verdict

**PASS (5 of 6), DEFERRED (1 of 6).**
- AC1–AC5: **VERIFIED PASS**, independently — every claim in dev's handoff was checked directly against
  the code/diff/design rather than trusted (interface shape via direct import, zero-`genai` grep re-run,
  signature/contract read from source + `git show --stat` on the commit, fresh 158/158 suite run + direct
  diff read of `ai_judge.py`/`conftest.py` to confirm behavior parity and jitter-formula preservation,
  manual `SystemExit` check via both the explicit-arg and config-default paths).
- AC6: **DEFERRED** to the closure end-to-end test — no `GEMINI_API_KEY` in this sandbox, consistent with
  how qa handled INC-3's live-Supabase-dependent criteria. Not scored pass or fail.
- Full regression: **158 passed / 0 failed**, zero regressions vs. the INC-3 baseline (157 + 1 net-new
  from `ai_provider.py`'s participation in the existing import-smoke parametrization — no new test file
  was added specifically for `ai_provider.py`, which is acceptable since `test_ai_judge.py`'s mocked
  suite already exercises `GeminiProvider.generate()` through the shared `mock_gemini` fixture).
- No bugs filed. No production code was modified by qa.

**Ready for reviewer**, with AC6 flagged as outstanding for the closure end-to-end pass (same status as
INC-3's AC1–AC5 live-verification items — tracked, not silently dropped).

---

## Open bugs

None currently open.

**BUG-002 — RESOLVED** (was carried forward from the INC-3 archive entry without re-checking current
status; re-verified now, see correction below). `sql/kill_switch.sql`'s apply-order header no longer
contradicts `sql/scheduler_pgcron.sql`/`sql/phase5_monitoring.sql`: all three now consistently state
"apply `kill_switch.sql` first." Fixed by dev before INC-4 started; independently confirmed both by qa
(re-read the current header text in all three SQL files directly, 2026-07-28) and by reviewer's Pass 13
(`docs/review-log.md`, REV-062/REV-063 verification), which traced the fix across all four affected
files. Full history retained in `docs/archive/test-report-archive.md`'s INC-3 entry.
