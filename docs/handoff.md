# Handoff — Shadow tracks retirement (code removal)

Source: `docs/design.md` §18 (removal plan). Covers the code-side cleanup for the change request that
retired FR24-FR31/NFR5 and FR32-FR39/NFR6 in `docs/requirements.md` and design §§13/14/16/17. This is a
deletion/edit increment, not a new feature — no new acceptance criteria beyond "the shadow tracks are gone
and production is untouched."

## Files deleted
- `scripts/shadow.py`, `scripts/run_shadow.py`, `scripts/run_shadow_nse.py`, `scripts/wallet_sim.py`,
  `scripts/eval_shadow.py`
- `sql/shadow_call_log_migration.sql`, `sql/shadow_nse_call_log_migration.sql`

`wallet_sim.walk` had no production caller (confirmed via grep before deleting — only `run_shadow.py`/
`run_shadow_nse.py`/`eval_shadow.py` referenced it); production's own change-detection logic in
`state.py` is separate and was not touched.

## Files edited
- `scripts/config.py` — removed `SHADOW_ENABLED`/`SHADOW_PROMPT_VARIANT`/`SHADOW_SNAPSHOT_LOOKBACK_MIN`,
  `SHADOW_NSE_ENABLED`/`SHADOW_NSE_PROMPT_VARIANT`/`SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`, and
  `EVAL_WINDOW_DAYS`. Reworded the retry-loop comment (dropped the "shadow pilot" clause) and the
  `GEMINI_MAX_RETRIES`/`GEMINI_RETRY_BASE_MS` truthiness-trap comment (no longer references the deleted
  `SHADOW_ENABLED` block). `nse_models()` is kept — it's the production NSE model-pair helper
  (`run_hourly.py` calls it), unrelated to the shadow tracks despite the name overlap.
- `.github/workflows/hourly-watchlist.yml` — deleted both shadow step blocks in full ("Run shadow verdict
  track (US/CA pilot)" and "Run NSE shadow verdict track (NSE pilot)"), including their comment headers,
  `SHADOW_TIMEOUT_MINUTES`/`SHADOW_ENABLED`/`SHADOW_NSE_*` env references. Reworded the
  `GEMINI_MAX_RETRIES` production-step comment from "shared by the production and shadow tracks" to
  "shared by the production track." Production watchlist step and the NSE-production model-variable
  comments are untouched.
- `scripts/ai_judge.py` — dropped the shadow-pilot clause from the `_generate` docstring (cosmetic only,
  no behavior change).

## New file
- `sql/drop_shadow_tables_migration.sql` — `DROP TABLE IF EXISTS call_log_shadow;` /
  `DROP TABLE IF EXISTS call_log_shadow_nse;`. Committed for reproducibility per repo convention (design
  §8: schema changes are versioned files, not ad hoc SQL). **Not yet applied to the live Supabase
  project** — that is a separate, explicitly-authorized step for the orchestrator to run (e.g. via the
  Supabase MCP `apply_migration` or the SQL editor), not something dev executed as part of this
  increment.

## Repo-wide grep sweep
Ran `grep -rni shadow` across the repo (excluding `docs/archive/`, `.git/`) after the edits above.
Remaining hits are all outside dev's ownership (src/config/workflow) and are historical/other-owner
material, not live code:
- `docs/design.md`, `docs/requirements.md` — retired sections/changelog entries (tech-lead/pm-owned,
  correctly describe the retirement as historical).
- `docs/idea-brief.md`, `README.md` — pm-owned; `README.md` still describes the shadow pilot as a current
  feature (e.g. "An experimental, non-production 'shadow wallet' pilot runs alongside production...") —
  **flagging to pm** to update since it now describes removed functionality.
- `docs/review-log.md`, `docs/test-report.md` — reviewer/qa-owned historical entries.
- `qa/test-plan-full-codebase.md`, `tests/test_shadow.py`, `tests/test_run_shadow.py`,
  `tests/test_run_shadow_nse.py`, `tests/test_eval_shadow.py`, `tests/test_config.py`,
  `tests/test_import_smoke.py`, `tests/conftest.py` — already flagged by tech-lead in design §18.4 for qa
  to delete/edit next; not touched here per CLAUDE.md (dev never touches tests/).
- `.gitignore` — one entry, `.shadow-pilot-session-state.md` (a Claude Code build-session scratch file
  name, not a shadow-*feature* reference; unrelated to call_log_shadow/etc.). Left as-is — ambiguous
  ownership and zero functional impact; flagging in case someone wants to rename it for hygiene.
- `requirements_docs/stock-advisor-ui-handoff-v3-spec.md` — "no shadows" is a CSS box-shadow styling
  rule, unrelated to the shadow wallet feature. No action needed.

No hits remained in `scripts/`, `sql/`, or `.github/workflows/` after the edits.

## How to verify
```
python3 -m py_compile scripts/*.py
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/hourly-watchlist.yml'))"
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import config, ai_judge, ingest, notify, prefilter, run_discovery, run_hourly, publish_prices, state, textutil
assert not [a for a in dir(config) if 'SHADOW' in a.upper()]
assert not hasattr(config, 'EVAL_WINDOW_DAYS')
assert hasattr(config, 'nse_models')
print('ok')
"
```
All three passed in a clean venv (`pip install -r requirements.txt`) before this handoff. Full pytest
suite was NOT run by dev — qa owns `tests/` cleanup (design §18.4) and the full regression pass next; the
existing shadow-only test files (`test_shadow.py`, `test_run_shadow*.py`, `test_wallet_sim.py`,
`test_eval_shadow.py`) will currently fail to collect since their target modules are deleted, which is
expected until qa deletes/edits them per §18.4.

## Confirmation: production untouched
FR1-FR23 code paths (`run_hourly.py`, `run_discovery.py`, `publish_prices.py`, `ingest.py`, `ai_judge.py`'s
`judge_batch`, `notify.py`, `prefilter.py`, `state.py`, `textutil.py`, and `config.py`'s non-shadow
tunables including `nse_models()`/`NSE_GEMINI_MODEL*`/`is_nse_open`) are unmodified except for the two
comment rewords noted above (config.py retry-loop comment, ai_judge.py docstring) — no logic, defaults, or
signatures changed. The production step in `hourly-watchlist.yml` (`Run hourly watchlist check`) is
byte-identical except for the one comment reword.

## Known limitations / follow-ups for other agents
- `sql/drop_shadow_tables_migration.sql` is not yet applied to Supabase — orchestrator to authorize and
  run separately, then confirm via `list_tables` that `call_log_shadow`/`call_log_shadow_nse` are gone.
- qa: delete/edit the test files per design §18.4 (`test_shadow.py`, `test_run_shadow.py`,
  `test_run_shadow_nse.py`, `test_wallet_sim.py`, `test_eval_shadow.py` deleted outright;
  `test_config.py`/`test_import_smoke.py`/`conftest.py` edited to drop shadow-specific cases/fixtures) and
  rewrite the shadow-referencing rows in `qa/test-plan-full-codebase.md`.
- pm: `README.md` still describes the shadow wallet pilot as a live feature — needs an update to reflect
  the retirement (flagged above).
- reviewer: `docs/review-log.md` retains historical shadow-track entries (REV-001, REV-005, REV-015,
  REV-018, Pass 3, Pass 4) per design §18.5 — no action needed from dev, noted for traceability.
