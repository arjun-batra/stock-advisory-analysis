# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## REV-077/REV-076/REV-078 follow-up — `ai_provider.py` permanent coverage — 2026-07-28

**Scope:** `docs/review-log.md` REV-077 (Pass 14 finding: `get_provider()` selection logic had zero
permanent test coverage despite being on both production entry points' critical path via
`ai_judge.judge_batch()` → `ai_provider.get_provider()`), plus two related fixes in the same file that
also had zero permanent coverage: REV-076 (`GeminiProvider` caches its `genai.Client` on the instance,
keyed by `timeout_ms`, instead of rebuilding it per retry attempt) and REV-078 (`temperature=0.2`
promoted to `config.AI_TEMPERATURE`, default `0.2`). Read `scripts/ai_provider.py` in full (current code)
and `tests/conftest.py` / `tests/test_ai_judge.py` for this project's mocking conventions before writing
tests, per the task brief.

**New file:** `tests/test_ai_provider.py` (12 tests). Kept separate from `test_ai_judge.py` rather than
appended to it: `test_ai_judge.py` is scoped to `judge_batch()`'s control flow (parse-retry,
model-fallback, fail-safe-to-Hold) through the shared `mock_gemini` fixture, while these tests exercise
`GeminiProvider`/`get_provider()` directly (provider selection, client caching, config plumbing) and need
a config-capturing fake that `mock_gemini`'s shared `FakeGeminiModels` doesn't retain — a distinct concern
matching this repo's one-file-per-module convention (`test_config.py`, `test_ingest.py`, etc.).

### What was added

1. **`get_provider()` selection (REV-077)** — 6 tests:
   - `get_provider("gemini")` returns a `GeminiProvider` instance, with the configured API key.
   - `get_provider("GEMINI")` (case-insensitivity, per `name.lower()` in source).
   - `get_provider()` with no arg falls through to `config.AI_PROVIDER` (monkeypatched to `"gemini"`) and
     still returns a working `GeminiProvider` — the config-default path, not just the explicit-arg path.
   - `get_provider("bogus")` raises `SystemExit` naming the bad value and the supported provider list
     (explicit-arg path).
   - `get_provider()` with `config.AI_PROVIDER` monkeypatched to `"bogus"` also raises the same
     `SystemExit` (config-default path) — mirrors exactly how qa's INC-4 pass manually verified both paths
     by hand (`docs/archive/test-report-archive.md`, INC-4 AC5), now permanent.

2. **Client caching keyed by `timeout_ms` (REV-076)** — 3 tests, spying on `ai_provider._client` via
   `monkeypatch.setattr`:
   - 3 `generate()` calls on the same `GeminiProvider` instance with identical `timeout_ms` → exactly 1
     client construction (mirrors dev's manual smoke test: 3 same + 1 different = 1 build then 1 rebuild).
   - A 4th call with a different `timeout_ms` → a 2nd, distinct client construction (rebuild), builder
     called with `[180000, 90000]` in order.
   - Two separate `GeminiProvider` instances each build their own client (cache is instance-scoped, not
     module/global state) — not explicitly asked for in the brief but a direct consequence of "cached on
     the instance" worth locking down given it's a correctness property, not just a call-count property.

3. **`config.AI_TEMPERATURE` plumbing (REV-078)** — 3 tests, using a local `_CapturingClient` fake that
   retains the `GenerateContentConfig` object passed to `generate_content` (the shared conftest fake
   doesn't retain it, only the model name):
   - Default (`0.2`) flows into the `GenerateContentConfig.temperature` passed to the SDK call.
   - Monkeypatching `config.AI_TEMPERATURE` directly changes what's passed (unit-level override).
   - A real env-var override (`AI_TEMPERATURE=0.75` + `importlib.reload(config)`, matching
     `test_config.py`'s established reload pattern) also changes what's passed — the explicit
     "change a config value, verify behavior changes" configurability check via the actual `os.environ`
     path, not just an attribute patch.

### Suite results

- **Before:** `python3 -m pytest -q --tb=short` → **158 passed, 0 failed**.
- **After:** `python3 -m pytest -q --tb=short` (`tests/test_ai_provider.py` alone, then full suite) →
  `tests/test_ai_provider.py`: **12 passed, 0 failed**. Full suite: **170 passed, 0 failed** (158 + 12,
  zero regressions).

### Shippability

Not re-run end-to-end for this narrow follow-up (no production code changed, no increment boundary
crossed — this is coverage-only work per the task brief). The existing `test_import_smoke.py` glob-based
parametrization already covers `ai_provider.py` importing cleanly, and `run_hourly.py`/`run_discovery.py`'s
call surface into `ai_judge.judge_batch()` was verified unchanged at INC-4 (see archived entry) and is
untouched by this pass.

### Bugs filed

**None.** REV-076 and REV-078's fixes both behave as documented: the client is cached per-instance keyed
by `timeout_ms` exactly as described, and `config.AI_TEMPERATURE` flows through to the SDK call config and
responds to both direct attribute overrides and real env-var overrides. No discrepancy found between the
code and either review-log entry's description while writing these tests.

### Verdict

**PASS.** `tests/test_ai_provider.py`: 12/12 passed. Full regression: 170/170 passed (158 baseline + 12
new, 0 regressions). No bugs filed. No production code was modified by qa.

---

## Open bugs

None currently open.
