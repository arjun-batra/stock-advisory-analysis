# Handoff — INC-1: NSE Shadow Wallet Pilot

Source: `docs/design.md` §16 (NSE Shadow Wallet Pilot, FR32–FR39/NFR6) + §0 load-bearing #6/#11;
`docs/requirements.md` §10.3 (FR32–FR39/NFR6). User condition honored: read `shadow.py`, `run_shadow.py`,
`config.py`, `state.py`, `sql/shadow_call_log_migration.sql`, `hourly-watchlist.yml`, design.md §16,
requirements.md §10.3 in full before writing anything.

## Files created
- `sql/shadow_nse_call_log_migration.sql` — structural mirror of `shadow_call_log_migration.sql`,
  retargeted to `call_log_shadow_nse`. Same columns/types/checks/defaults/indexes, RLS enabled, no
  policy, no anon/authenticated grant.
- `scripts/run_shadow_nse.py` — new NSE shadow orchestrator, mirrors `run_shadow.py`'s cycle shape with
  NSE parameters (own table, own kill switch, NSE market gate, NSE model bucket).

## Files changed
- `scripts/config.py` — added `SHADOW_NSE_ENABLED` (fail-open-on-empty, same shape as `SHADOW_ENABLED`),
  `SHADOW_NSE_PROMPT_VARIANT` (default `position_aware_v1`), `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN` (default
  `20`). Corrected `GEMINI_MODEL` default `gemini-3.5-flash` → `gemini-2.5-flash` and
  `GEMINI_MODEL_BACKUP` default `gemini-3.1-flash-lite` → `gemini-2.5-flash-lite` (design.md Change 2 —
  the 3.x models showed stability issues; every other track already defaults to the 2.5-flash family).
  `NSE_GEMINI_MODEL`/`_BACKUP` and `DISCOVERY_GEMINI_MODEL`/`_BACKUP` untouched (already correct/inherit
  correctly).
- `scripts/shadow.py` — `judge_batch_shadow(items, models=None)` now takes an optional `models` list,
  threaded through `ai_judge._models_to_try(models)` (same pattern `ai_judge.judge_batch` already uses).
  Default `None` preserves today's US/CA behavior exactly (`run_shadow.py` calls it unchanged). Verified
  by reading the code (not trusting the doc) that `SHADOW_SYSTEM_PROMPT` / `_shadow_ticker_block` are
  already market-agnostic — the ticker block renders `data['market']` and `fundamentals.currency`
  generically, no US/CA-specific logic — so no second prompt was needed for NSE.
- `.github/workflows/hourly-watchlist.yml` — added `timeout-minutes: 15` to the existing US/CA shadow
  step (per design.md's INC-1 hardening note) and to the new NSE step; added the new "Run NSE shadow
  verdict track (NSE pilot)" step, gated `if: vars.SHADOW_NSE_ENABLED != 'false'`, `continue-on-error:
  true`, running strictly after both the production step and the US/CA shadow step, passing
  `NSE_GEMINI_MODEL`/`_BACKUP` (same vars/fallback chain NSE production already uses),
  `SHADOW_NSE_ENABLED`, `SHADOW_NSE_PROMPT_VARIANT`, `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`, and **no**
  `NTFY_*` vars at all. Also corrected the `|| 'gemini-3.5-flash'` literal fallbacks (production step,
  US/CA shadow step, new NSE step) to `|| 'gemini-2.5-flash'` to match the config.py correction above.

## How to run it
```
FORCE_RUN=true GEMINI_API_KEY=... SUPABASE_URL=... SUPABASE_SECRET_KEY=... \
  python3 scripts/run_shadow_nse.py
```
Normal operation is via the new workflow step (`.github/workflows/hourly-watchlist.yml`), which fires
automatically after the US/CA shadow step on every hourly dispatch, gated by NSE market hours (or
`FORCE_RUN` from a manual `workflow_dispatch`). `SHADOW_NSE_ENABLED=false` (repo Variable) disables the
whole track with no code change.

**Migration not yet applied to the live Supabase project** — I don't have Supabase MCP/DB tool access in
this session (only Read/Write/Edit/Grep/Glob/Bash). `sql/shadow_nse_call_log_migration.sql` is committed
and versioned but still needs to be applied (e.g. via `apply_migration` or the SQL editor) before
`run_shadow_nse.py` can write successfully in production — until then every cycle will fail at the
`sb.table("call_log_shadow_nse").insert(...)` call, get caught by the top-level try/except, log an ERROR
line, and exit 0 (harmless no-op, but no rows will land).

## Isolation checks (FR35, FR36, FR37 — verified explicitly)
1. **Never alerts (FR36):** `grep notify scripts/run_shadow_nse.py scripts/shadow.py` — no import/call
   of `notify` in either file (only a doc-comment mention). Every row written has `alert_type=None,
   alerted=False`. The workflow step passes no `NTFY_TOPIC`/`NSE_NTFY_TOPIC`/`DETAIL_PAGE_BASE` — verified
   by grepping the new step's `env:` block.
2. **Isolated storage, no anon read path (FR35):** `sql/shadow_nse_call_log_migration.sql` enables RLS
   with no policy and no `grant` statement to `anon`/`authenticated` — structurally identical to
   `shadow_call_log_migration.sql`. `run_shadow_nse.py` only ever calls
   `sb.table("call_log_shadow_nse")` — greped, confirmed no reference to `call_log` or `call_log_shadow`
   as a write target (only as an upstream *read* source for the production snapshot, which is FR34's
   intended reuse, not a write).
3. **Cannot fail production or the US/CA shadow track (FR37):** separate process/entry point
   (`run_shadow_nse.main()`), top-level `try/except (Exception, SystemExit)` always exits 0 (smoke-tested
   below, including the missing-secrets and network-failure paths), separate workflow step with
   `continue-on-error: true` and `timeout-minutes: 15`, runs strictly after both prior steps, separate
   table, separate independent kill switch (`SHADOW_NSE_ENABLED`, verified fail-open-on-empty and
   fail-closed-on-typo by smoke test).
4. **Real holdings/cost-basis never leak into NSE shadow rows:** `run_shadow_nse.py` never calls
   `state.get_holdings_map` or `state.build_position` — positions come only from
   `_derive_shadow_positions`, which reads only `call_log_shadow_nse`. Grepped to confirm.
5. **Separate kill switches, separate market gates:** `SHADOW_NSE_ENABLED` is independent of
   `SHADOW_ENABLED`; `is_nse_open` (IST) is independent of `is_market_open` (ET) — flipping/misfiring one
   cannot touch the other track.

## Deviation from design.md §16 (and why — flagged, not silently resolved)
- **§16.3 "avoid duplicating the cycle body... factor a shared `run_shadow_cycle(track)` / `ShadowTrack`
  spec" vs. duplication:** design.md explicitly leaves this as "dev's choice of mechanism," and the task
  brief additionally steered toward the simpler/duplicate option consistent with this codebase's existing
  US/TSX-vs-NSE convention (`run_hourly.py._sessions`). I duplicated `run_shadow.py`'s cycle body into
  `run_shadow_nse.py` rather than introducing a shared helper. This is **not** a contradiction of design's
  hard requirement: design.md §17.2 ("the wallet-walk state machine MUST be the single shared function")
  is explicitly INC-2 scope (`wallet_sim.walk`, not yet built) — §17.2 itself describes the refactor as
  something both orchestrators do *when INC-2 lands*, implying separate inline walks exist until then.
  No design/requirements contradiction; this is sequencing, not a gap.
- **`timeout-minutes` value (15 min) is not specified anywhere as a config tunable.** Treated as a
  GitHub Actions structural setting (like `runs-on`/`python-version` elsewhere in the same file), not a
  business tunable — no config.py entry added for it. Flag to tech-lead only if this reasoning should
  change.

## Real bug found and fixed while verifying FR37 (not a design deviation, a correctness fix)
`config.require_secrets()` raises `SystemExit`, which `except Exception` does **not** catch (`SystemExit`
subclasses `BaseException`, not `Exception`). Smoke-tested: `FORCE_RUN=true` with no secrets set exited 1
on the original `except Exception` pattern — silently breaking the literal "main() always exits 0"
guarantee in that one edge case (though `continue-on-error: true` at the workflow level still would have
prevented it from failing the run — a second belt catching what the first missed). I widened
`run_shadow_nse.py`'s catch to `except (Exception, SystemExit)`. **The identical gap exists in the
shipped `scripts/run_shadow.py`** (verified by the same smoke test against it) — out of INC-1's scope to
touch, not fixed there, flagged here for tech-lead/qa awareness.

## What qa should pay special attention to
- The two `tests/test_config.py` failures (`test_default_model_is_gemini_3_5_flash`,
  `test_default_backup_model`) are **expected** — they assert the old, incorrect model-default strings
  that design.md's Change 2 explicitly requires correcting. All other 163 existing tests pass unchanged
  (full suite: 165 total, 2 expected failures, 0 unexpected). qa owns updating these two assertions to the
  new defaults.
- Cross-track isolation: confirm a kill-switch flip or induced failure on one shadow track never appears
  in the other track's table/log output.
- The `_derive_shadow_positions` wallet-walk in `run_shadow_nse.py` is a byte-for-byte port of
  `run_shadow.py`'s, just pointed at `call_log_shadow_nse` — worth a diff-based regression check against
  `run_shadow.py`'s version if/when INC-2's `wallet_sim.walk` consolidates them.
- The migration file is committed but **not yet applied** to Supabase (see above) — qa cannot verify live
  writes until it's applied.

## Smoke tests performed
- Installed `requirements.txt` into a clean venv; all new/changed modules import cleanly
  (`config`, `shadow`, `run_shadow_nse`, `run_shadow`, `run_hourly`, `ai_judge`, `state`, `ingest`,
  `notify`).
- `config.SHADOW_NSE_ENABLED`/`SHADOW_NSE_PROMPT_VARIANT`/`SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`/
  `nse_models()`/corrected `GEMINI_MODEL`/`GEMINI_MODEL_BACKUP` all verified by direct import.
  `SHADOW_NSE_ENABLED=false` → `False`; `SHADOW_NSE_ENABLED=flase` (typo) → `False` (fails closed, per
  FR38).
- `python3 scripts/run_shadow_nse.py` with no env at all (market closed at test time) → clean no-op, exit
  0.
- `FORCE_RUN=true` with no secrets → caught, logged, exit 0 (post-fix; was exit 1 pre-fix).
- `FORCE_RUN=true` with fake secrets (real network call to an invalid Supabase host) → caught, logged,
  exit 0.
- `.github/workflows/hourly-watchlist.yml` parses as valid YAML (`yaml.safe_load`).
- `python3 -m pytest tests/ -q` from repo root: **163 passed, 2 failed** (the two expected
  model-default assertions above). No other regressions.

## Known limitations
- SQL migration not applied to live Supabase (no DB tool access this session) — needs applying before
  the track can write.
- `wallet_sim.walk` consolidation (§17.2) deliberately deferred to INC-2, per design.md's own phasing.
- `timeout-minutes: 15` is a judgment-call value, not derived from any requirement; revisit if real NSE
  shadow batches run close to that bound.
