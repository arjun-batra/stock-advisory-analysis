# Test Report — Latest Run

**Owner:** qa. Older run entries (baseline adoption pass, INC-1/INC-2 shadow pilot increments) moved to
`docs/archive/test-report-archive.md` per doc-hygiene rule — this file now holds only the latest run and
open bugs.

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
  a pointer to `docs/design.md` §18, replaced P3-7 ("Shadow isolation") with a retired stub, and updated
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

## Open bugs

None.
