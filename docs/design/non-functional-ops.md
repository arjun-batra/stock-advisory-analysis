# Non-functional design, repo structure, configuration surface

Part of `docs/design.md`'s module split (2026-07-25, REV-024). See `docs/design.md` for the index, module
map, §0 load-bearing decisions, and the requirement coverage map — read that first for orientation.
Section numbers below (§7–§9) are unchanged from the pre-split monolithic `docs/design.md`.

---

## 7. Non-functional design

- **7.1 Cost (NFR1):** public repo → unlimited free Actions minutes; secrets in Actions secrets +
  Supabase Vault; Supabase free tier; ntfy / GitHub Pages $0. **Gemini runs on Google's paid tier**
  (system-wide); one batched AI call per run per market group keeps call volume — and therefore paid-tier
  spend — low, holding NFR1's unchanged **$0–15/month** cap (spend is bounded by low call volume, not a
  free quota). The other data/push APIs (Yahoo, ntfy) remain free. (Prior to 2026-07-16 this also covered
  the now-retired shadow tracks' calls — see `docs/design.md`'s "Retired: shadow-pilot tracks" note;
  production-only cost is strictly lower.)
- **7.2 Security (NFR3):** no trade execution, no brokerage credentials anywhere. Secrets never in code.
  `dispatch_github_workflow` is `SECURITY DEFINER`, reads the PAT from Vault only, never echoes it. Detail
  page uses the read-only publishable key under RLS; `call_log.id` is a UUID. Every table has RLS.
- **7.3 Currency:** native per market — USD (US), CAD (TSX), INR (NSE) — no FX conversion.
- **7.4 Concurrency:** `concurrency: { group: hourly-watchlist, cancel-in-progress: false }` serializes
  overlapping runs so two runs never double-write `verdict_state` for a ticker.
- **7.5 Delisting / halts / new listings (FR17):** no-data ticker → skip-with-log, never fatal for
  others. New listings return valid price but short history → compute what history supports, mark 20d
  fields `n/a (newly listed)`, let the AI judge the rest.

---

## 8. Repo structure & module boundaries

```
.github/workflows/
  hourly-watchlist.yml   # workflow_dispatch only; concurrency group
                         #   (former shadow steps removed 2026-07-16 — see docs/design.md's
                         #    "Retired: shadow-pilot tracks" note)
  daily-discovery.yml    # workflow_dispatch only; concurrency group
  publish-prices.yml     # writes pages/prices.json (CORS fallback, frontend.md §11)
scripts/
  config.py              # market hours/gates, model Variables, discovery gates — all tunables
                         #   (shadow vars removed 2026-07-16 — see "Retired: shadow-pilot tracks")
  ingest.py              # yfinance wrapper; market-agnostic; headline filter; session-aware price/vol
  prefilter.py           # Yahoo live screener + quality gates + signals + funnel; region-aware
  ai_judge.py            # Gemini batched judge_batch(models=...); BATCH_SYSTEM_PROMPT; schema + confidence
  state.py               # Supabase read/write; single-rule change machine; _snapshot()
  notify.py              # ntfy dispatch (provider-agnostic); per-market topic + timestamp
  textutil.py            # shared clip()
  run_hourly.py          # hourly watchlist orchestrator (per-market gate) — thin entry point
  run_discovery.py       # daily discovery orchestrator (region-aware) — thin entry point
  publish_prices.py      # fetch watchlist prices, write pages/prices.json — thin entry point
sql/
  scheduler_pgcron.sql, phase5_monitoring.sql, dashboard_latest_call_view.sql
pages/
  detail.html, dashboard.html, prices.json
```

> **Shadow-track files removed 2026-07-16** (`scripts/shadow.py`, `scripts/run_shadow.py`,
> `scripts/run_shadow_nse.py`, `scripts/wallet_sim.py`, `scripts/eval_shadow.py`, both shadow SQL
> migrations, and the two shadow steps in `hourly-watchlist.yml`) — the work is finished and verified; see
> `docs/design.md`'s "Retired: shadow-pilot tracks" note for what was removed and how it was verified.

Contracts a dev/QA team builds against: the `data_snapshot` jsonb shape (`data-and-flow.md` §5), the
`judge_batch()` JSON array contract (`components.md` §4.4), the single-rule state machine
(`data-and-flow.md` §6), the config surface (§9, below). Entry points contain no logic; externals are
reached through module functions for substitutability in tests.

---

## 9. Configuration surface (tunables — the hardcoding-audit baseline)

All user-tunable values live in `scripts/config.py`, read from environment / GitHub Actions secrets &
Variables; nothing sensitive hardcoded. This mirrors the Configuration section of `docs/requirements.md`
(the reviewer's audit baseline). Core: `GEMINI_MODEL`/`_BACKUP`, `NSE_GEMINI_MODEL`/`_BACKUP`,
`DISCOVERY_GEMINI_MODEL`/`_BACKUP`, `GEMINI_TIMEOUT_MS` (180000), `GEMINI_MAX_RETRIES` (3),
`GEMINI_RETRY_BASE_MS` (10000), `NTFY_TOPIC`, `NSE_NTFY_TOPIC` (falls back to `NTFY_TOPIC`),
`DETAIL_PAGE_BASE`, `ALERTS_ENABLED` (false), `FORCE_RUN` (false), `MIN_HISTORY_ROWS` (21),
`YF_PACING_SECONDS` (2 — unified yfinance/screener call spacing; as of REV-007 this **also** governs
prefilter's live-screener call pacing, replacing five formerly-hardcoded `sleep(1)` sites, so inter-screen
pacing there is now 2s, not 1s — a deliberate low-risk timing change), `YF_BACKOFF_SECONDS` (10),
`YF_HISTORY_RETRIES` (2 — Yahoo history-fetch retry count, `ingest._fetch_history`), `YF_HISTORY_PERIOD`
(`"3mo"` — yfinance history window, same function), `HEADLINES_LIMIT` (5 — per-ticker headline cap,
`ingest._headlines`), `MARKET_OPEN`/`CLOSE` (09:30/16:00 ET), `NSE_MARKET_OPEN`/`CLOSE` (09:15/15:30 IST),
`RUNTIME_CLOSE_GRACE_MIN` (10), `NOTIF_BODY_MAX` (150 — push body clip, `notify.py`), `RATIONALE_MAX`
(280 — stored rationale clip, `ai_judge.py`). Discovery: the `DISCOVERY_*` gate/signal/shortlist/cooldown
keys (`components.md` §4.3), incl. `DISCOVERY_EARNINGS_RECENT_DAYS` (2 — the "just reported" look-back
side of the earnings signal in `prefilter._signals`).
Dashboard auto-refresh interval is build-time config (FR22). **The dashboard auto-refresh interval and all
discovery thresholds are tunables, not requirements — no tunable may live only in code.**

> **RETIRED (2026-07-16):** the shadow-track tunable groups (`SHADOW_ENABLED`, `SHADOW_PROMPT_VARIANT`,
> `SHADOW_SNAPSHOT_LOOKBACK_MIN`, `SHADOW_NSE_ENABLED`, `SHADOW_NSE_PROMPT_VARIANT`,
> `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`) and the wallet-sim harness tunable (`EVAL_WINDOW_DAYS`) are removed
> along with the shadow tracks — see `docs/design.md`'s "Retired: shadow-pilot tracks" note. The
> **model-default correction** (`GEMINI_MODEL`/`GEMINI_MODEL_BACKUP` → `gemini-2.5-flash`/
> `gemini-2.5-flash-lite`) is unrelated and remains in effect (`components.md` §4.4).

**Workflow-level (YAML) tunables — a distinct surface from `config.py`.** A few operational knobs are
evaluated by GitHub's workflow engine *before* the Python process starts, so they cannot be `config.py`
env-var tunables (config.py only sees them after the runner is already provisioned). `config.py` is the
home for **application/business** tunables; the workflow-engine settings are their own surface. This repo's
established convention for workflow knobs an operator may need to change **without a commit** is a repo
**Variable with a literal fallback** — `${{ vars.X || '<default>' }}` — used throughout
`hourly-watchlist.yml` (`GEMINI_MODEL`, `GEMINI_MAX_RETRIES`, …).
Genuinely fixed toolchain/structural facts (`runs-on`, `python-version`, action `@vN` pins, the
`concurrency` group) stay as bare literals and are **not** tunables.

> **RETIRED (2026-07-16):** the `SHADOW_TIMEOUT_MINUTES` repo Variable and its `timeout-minutes` binding
> on the two shadow workflow steps were removed along with those steps. No replacement is needed — there
> is no shadow work left to bound.
