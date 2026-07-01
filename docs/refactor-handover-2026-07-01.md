# SAA behavior-preserving refactor — handover (2026-07-01)

**Audience:** Tech Lead · Product Lead
**Branch:** `claude/saa-behavior-preserving-refactor-dzea3u` — 8 refactor commits + 1 runner-generated
`prices.json` refresh, **merged to `main`** (per operator instruction, 2026-07-01; PR link in issue #27)
**Audit record:** [issue #27](https://github.com/arjun-batra/stock-advisory-analysis/issues/27)
(Phase 1 findings + execution comment)

---

## 1. Mandate and outcome

Cleanup-only pass over the live pipeline: **same behavior for every input, less code underneath.**
Net result: **−31 lines of Python across the pipeline modules**, one duplicated algorithm and one
duplicated data literal collapsed to single implementations, one dead DB table dropped, one naming
collision resolved, two stale/dead artifacts removed — and zero changes to alerting, scheduling,
timezone/DST handling, or any SD §0 load-bearing pattern.

Every entrypoint (`run_hourly.py`, `run_discovery.py`, `publish_prices.py`) produces identical
`call_log` rows, notifications, and dashboard/detail output for identical inputs. Evidence in §4.

## 2. What changed

### Code (branch commits, one logical change each)

| Commit | Change | Why it's safe |
|---|---|---|
| `e29b0a0` | `run_discovery.py`: removed unused `now` local + orphaned `datetime` import | Assigned, never read (pyflakes + grep) |
| `3ddd2f6` | `dashboard.html`: watchlist query no longer fetches `type` | `w.type` referenced nowhere in the page script; render identical |
| `8cbd73b` | Duplicated inline fail-safe verdict dict → `ai_judge.missing_verdict()` | Output asserted byte-identical for both wordings (ticker/candidate) |
| `5fe4f8d` | `ai_judge._clip` + `notify._clip_body` (identical algorithm ×2) → shared `textutil.clip()` | 120,078-case differential test: byte-identical to **both** removed originals, incl. dynamic push-body limits |
| `6a6eb3e` | Outcome tallies → `collections.Counter` (6 hand-rolled `get(k,0)+1` sites) | Missing-key reads return 0 without phantom keys; degraded/heartbeat status and printed `dict()` line identical (parity-tested) |
| `8eba709` | `publish_prices.py`: literal `sleep(2)` → `config.YF_PACING_SECONDS` | Default is 2.0; workflow sets no override; **live-verified** (§4) |
| `b826c0a` | `prefilter._market_for` → `_market_from_exchange` | Broke the same-name/different-semantics collision with `ingest._market_for` (suffix vs exchange-code mapping); pure rename, zero stale refs |
| `c6279c2` | `publish-prices.yml`: header comment updated to the live pg_cron scheduling reality | Comment-only; YAML validated; triggers/steps untouched |

`02dfbc3` is the normal `prices.json` refresh committed by the workflow run the push triggered —
not hand-written, and itself part of the verification evidence (§4).

### Database (applied live, auditable migration)

- **`drop_vestigial_candidate_universe`** — dropped `public.candidate_universe` (pre-approved;
  load-bearing decision #7). Verified before dropping: 0 rows; zero references from repo code, DB
  functions, views, cron jobs, or FKs. Public schema now holds exactly the six tables SD §5 documents.

### Already clean (no action needed)

Two of the three pre-approved cleanup targets were **already done** in the v7-era cleanup:
`notify.py` has no `kind="reminder"` path and `detail.html` carries no residual reminder logic.
Confirmed by grep; nothing existed to remove.

## 3. What was deliberately NOT touched

All eight SD §0 load-bearing patterns located and left byte-identical: dual-model fallback,
DST-superset cron + runtime gate, cold-start silence, skip-with-log + fail-safe-Hold guard,
per-batch AI call + per-batch `tokens`, separate dead-man monitor job, live-screener discovery,
and the `#gate[hidden]{display:none}` CSS rule.

Audit items ruled "leave as-is" (reasoning in issue #27): ingest-loop and HTML-page dedup,
log-prefix unification, monitor-SQL ET/IST dedup, the dashboard's `call_log` fetch shape.

## 4. Verification evidence

- **Differential tests per change:** fail-safe dict equality (both wordings); 120,078 (input, limit)
  clip cases vs both removed originals; Counter parity incl. missing-key reads and print format.
- **Static:** `py_compile` + `pyflakes` clean across all pipeline modules after every commit;
  per-commit `git diff` scope review (nothing outside the intended lines moved); no stale
  references to any removed/renamed name.
- **Live end-to-end:** the push triggered `publish-prices.yml` on the branch
  ([run 28550550020](https://github.com/arjun-batra/stock-advisory-analysis/actions/runs/28550550020),
  success) — the refactored script priced **25/25 tickers** and produced a `prices.json` that
  differs from the pre-refactor output **only in `generated_at`**. Same prices, same structure.
- **SD §10 tracing:** the hourly/discovery changes leave the single-rule state machine, gates, and
  notifier call sites untouched; the "Malformed AI response" scenario (the one path the fail-safe
  dict change touches) produces provably identical rows. No `FORCE_RUN` dry run was fired — during
  a live session it would consume real quota and advance `verdict_state` under a dry-run notifier,
  which can silently swallow a legitimate alert; the deterministic differential tests above are
  stronger evidence for these specific changes.

## 5. Open items — decisions owed

| # | Item | Owner | Detail |
|---|---|---|---|
| 1 | **`data_snapshot.market` latent gap** | Tech Lead + Product | `state._snapshot()` never writes `market`, so `detail.html`'s documented market-anchored currency/badge path (UI handoff v3) is dead in practice — every row falls back to fundamentals-currency / suffix inference, which happens to agree today. Fixing = writing a new snapshot field = behavior change → out of refactor scope, needs a ruling. Tracked on issue #27. |
| 2 | **SD §8 repo map** | SD doc owner | `scripts/textutil.py` (new, commit `5fe4f8d`) and the `candidate_universe` row in SD §5 need doc updates; `requirements_docs/` is read-only to the dev side. |
| 3 | ~~Merge~~ | — | Done — merged to `main` on operator instruction, 2026-07-01. |

## 6. Resume state (for any future session)

Refactor scope is **complete** — Phase 1 audit, pre-approved cleanups, and all ruled Phase 2 items
are executed and pushed. Issue #27 is the canonical record; do not re-audit. The only actionable
remainder is the table in §5.
