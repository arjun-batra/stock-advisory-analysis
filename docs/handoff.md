# Handoff — INC-4: AI provider abstraction (FR33)

Branch: `claude/admin-portal-evaluation-txaehj` (same batching note as INC-3 — no new `inc-N` branch cut).
INC-3 (kill-switch) shipped, tested, and was reviewer-cleared before this increment started.

**Design:** `docs/design/operational-controls.md` §14 (§14.1 hand-rolled-vs-LiteLLM decision — already
made, not revisited; §14.2 exact interface shape; §14.3 `ai_judge.py` after the refactor; §14.4 config
addition). **Plan/AC:** `docs/design/increment-plan.md` "### INC-4 — AI provider abstraction (FR33)".
Traces to `docs/requirements.md` FR33.

## Files changed
- **New `scripts/ai_provider.py`** — the full provider-neutral interface per §14.2: `TokenUsage`,
  `ProviderResult` (frozen dataclasses), `ErrorClass` (str Enum), `ProviderError`, `BatchVerdictSchema`
  (frozen dataclass), `AIProvider` (ABC, one abstract `generate()` method), `GeminiProvider` (the sole
  concrete implementation — moved in, unchanged, from `ai_judge.py`: `genai.Client(http_options=...)`,
  typed `response_schema` built from `BatchVerdictSchema`, `response_mime_type="application/json"`,
  `temperature=0.2`, and `_classify()` carrying over `_is_retryable()`'s exact logic), `get_provider()`.
- **`scripts/ai_judge.py`** — refactored to remove every Gemini-SDK-specific import/call
  (`google.genai`, `google.genai.types`, `httpx`, `_client()`, `_usage()`, `_is_retryable()`,
  `_RETRYABLE_CODES`/`_RETRYABLE_STATUSES`, `_RESPONSE_SCHEMA`). `_generate()` is now the
  provider-neutral retry loop from §14.3 (takes an `AIProvider` + `max_retries`/`retry_base_ms` as
  parameters instead of reading `config.*` / a `genai.Client` directly; catches only `ProviderError`).
  `judge_batch()` gained an optional `provider=None` parameter (defaults to
  `get_provider(config.AI_PROVIDER)`) — its public signature is otherwise unchanged and its return
  contract is byte-identical (`_enrich()` now converts the `TokenUsage` dataclass back to a plain dict
  via `dataclasses.asdict()` before stamping it onto each ticker's result, so callers see exactly the
  same `{"prompt", "output", "thoughts", "total"}` shape as before). The "call config" log line
  (timeout/max_retries/retry_base) and the per-retry transient-error log line are printed with
  byte-identical text, just relocated to `judge_batch()`/`_generate()` respectively.
- **`scripts/config.py`** — added `AI_PROVIDER` (env var, default `"gemini"`).
- **`docs/design/non-functional-ops.md` §9** — added `AI_PROVIDER` to the core tunables baseline
  paragraph (the reviewer's hardcoding-audit source of truth); updated the old "DRAFT, INC-4 not yet
  implemented" stub to point at the now-implemented location instead of restating it.
- **`tests/conftest.py`** — `mock_gemini` fixture now patches `ai_provider._client` (was
  `ai_judge._client`) since the Gemini transport seam moved modules; docstrings updated to match. No
  test assertions changed anywhere — `git diff --stat` on every `tests/test_*.py` file is empty.

**Not touched, confirmed via `git diff --name-only`:** `scripts/run_hourly.py`, `scripts/run_discovery.py`.

## Acceptance criteria status (6 of 6 — see design doc's INC-4 AC list)
1. **PASS** — `ai_provider.py` defines `AIProvider`, `ProviderResult`, `TokenUsage`, `ErrorClass`,
   `ProviderError`, `BatchVerdictSchema`, `GeminiProvider`, `get_provider()` (verified by importing each
   by name).
2. **PASS** — `grep -n "genai\|types\." scripts/ai_judge.py` returns zero matches (exit code 1, no
   output).
3. **PASS** — `judge_batch()`'s signature is `(items, models=None, provider=None)`, return contract
   unchanged (verified by the unmodified `tests/test_ai_judge.py` suite passing as-is); `git diff` on
   `run_hourly.py`/`run_discovery.py` is empty (0 lines) and neither file appears in
   `git diff --name-only`.
4. **PASS** — full suite: 158 passed both before (baseline, via `git stash`) and after this change, with
   zero assertion changes in any test file (only `conftest.py`'s fixture-plumbing docstrings/target
   changed). `config.GEMINI_TIMEOUT_MS`/`GEMINI_MAX_RETRIES`/`GEMINI_RETRY_BASE_MS` are still the values
   `judge_batch()` passes into `_generate()`'s `timeout_ms`/`max_retries`/`retry_base_ms` parameters —
   same log lines, same `random.uniform(0, base*2**n)` full-jitter formula.
5. **PASS** — `config.AI_PROVIDER` exists (default `"gemini"`); manual check:
   `ai_provider.get_provider("bogus")` raises `SystemExit("Unknown AI_PROVIDER 'bogus'; supported:
   ['gemini']")`.
6. **BLOCKED — could not be executed in this environment.** No `GEMINI_API_KEY` (or any Google API
   credential) is present anywhere in this session's environment (`env | grep -i gemini` / `-i google` /
   `-i api_key` all empty; no secrets manager, `gh` CLI, or credential file found either). I did **not**
   fabricate a result. As the closest available substitute I ran a real network call through the new
   path with a deliberately invalid key (`GEMINI_API_KEY=invalid-test-key`) and confirmed it reaches
   Google's real endpoint end-to-end: `ClientError: 400 INVALID_ARGUMENT ... 'API key not valid'`,
   correctly classified `fatal` (0 transport retries, no backup-model retry burned), surfaced through
   `ai_judge.judge_batch()` as `parse_status: "api_error"` — i.e. the full `ai_provider.py` ->
   `GeminiProvider.generate()` -> `ai_judge._generate()` -> `judge_batch()` chain is wired correctly and
   reaches Gemini's real API through this sandbox's proxy; the only missing piece is a valid credential.
   **This needs a follow-up run with a real `GEMINI_API_KEY` before AC6 can be marked PASS** — either
   supply the key to this session, or run
   `python3 -c "import ai_judge; print(ai_judge.judge_batch([<a real item>]))"` from `scripts/` in an
   environment that has it (e.g. the production GitHub Actions runner, or locally with the real secret).

## How to run
```
cd scripts && python3 -m pytest -q --tb=short   # from repo root: pytest -q --tb=short (tests/ + scripts/ on sys.path via conftest.py)
```
`ai_provider.get_provider("bogus")` manual check (SystemExit):
```
python3 -c "import ai_provider; ai_provider.get_provider('bogus')"
```

## Known limitations
- AC6 (live smoke test) is unresolved per above — flagging to the orchestrator/Arjun rather than
  guessing or faking a pass.
- `AI_PROVIDER` is intentionally not on the admin portal's curated tunables list (FR30) — single-valued
  today (only `"gemini"` implemented), nothing to edit; a second provider would be its own change
  request that also updates FR30's curated list if it should be portal-editable (§14.4).
- No new dependency added (`requirements.txt` unchanged) — `google-genai` was already a dependency and
  simply moved which file imports it.

---

# Handoff — Reviewer Pass 14 fixes: REV-075, REV-076, REV-078 (INC-4 follow-up)

Design: `docs/design/operational-controls.md` §14.2-14.4, `docs/design/non-functional-ops.md` §9 (both
updated by tech-lead before this fix pass — read there for the exact decisions, not restated here). All
three are internal, behavior-preserving fixes; no interface/signature changes.

## Files changed
- **`scripts/config.py`** — REV-075: fixed the stale comment near `GEMINI_MAX_RETRIES`/
  `GEMINI_RETRY_BASE_MS` (formerly "logged at call setup (`ai_judge._client`)") to point at
  `ai_provider._client`, the current location since INC-4's refactor. REV-078: added
  `AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.2"))`, placed next to the other Gemini
  call-shape tunables (`GEMINI_TIMEOUT_MS`, `GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BASE_MS`), same
  env-var-with-literal-default pattern.
- **`scripts/ai_provider.py`** — REV-076: `GeminiProvider.__init__` now caches `self._client = None` /
  `self._client_timeout_ms = None`; `generate()` builds a client only when none is cached yet or the
  requested `timeout_ms` differs from the cached one, otherwise reuses `self._client`. Restores 1 client
  build per `judge_batch()` call (was rebuilding on every retry attempt, up to ~16/batch). REV-078:
  `temperature=0.2` literal replaced with `temperature=config.AI_TEMPERATURE`.

## How to run
```
cd scripts && python3 -m pytest -q --tb=short   # from repo root: pytest -q --tb=short
```
Manual verification of the caching fix (no live API key needed — `_client` mocked):
```python
from unittest.mock import MagicMock, patch
import ai_provider
calls = {"n": 0}
def fake_client(api_key, timeout_ms):
    calls["n"] += 1
    m = MagicMock(); m.models.generate_content.return_value = MagicMock(text="[]", usage_metadata=None)
    return m
with patch.object(ai_provider, "_client", side_effect=fake_client):
    p = ai_provider.GeminiProvider("key")
    schema = ai_provider.BatchVerdictSchema()
    for _ in range(3):
        p.generate(model="m", system_prompt="s", user_prompt="u", schema=schema, timeout_ms=1000)
    assert calls["n"] == 1   # same timeout_ms -> cached, built once
    p.generate(model="m", system_prompt="s", user_prompt="u", schema=schema, timeout_ms=2000)
    assert calls["n"] == 2   # different timeout_ms -> rebuilt
```

## Test results
Full suite: 158 passed, both before and after this change (`python3 -m pytest -q --tb=short`), confirming
these are non-breaking as tech-lead's docs predicted — no test patches the construction cadence or
asserts a hardcoded `0.2`.

## Known limitations
None new. `AI_TEMPERATURE`, like `AI_PROVIDER`, is intentionally not on the admin portal's curated
tunables list (FR30) per `non-functional-ops.md` §9 — a `config.py`/repo-Variable-level tunable is
sufficient today.
