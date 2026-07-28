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
                         #   DRAFT (INC-6, admin-portal.md §16.4): gains `permissions: contents: write`
                         #   (this workflow has NONE today — confirmed by reading the file directly, not
                         #   assumed) + a new "Commit tunables cache if changed" step, mirroring
                         #   publish-prices.yml's existing commit-on-change step exactly. Sole writer of
                         #   config/tunables_cache.json (Decision #28).
  daily-discovery.yml    # workflow_dispatch only; concurrency group — DRAFT: no changes for INC-6;
                         #   reads config/tunables_cache.json read-only via config.py's fallback chain,
                         #   same as every script, no permissions change needed for a read.
  publish-prices.yml     # writes pages/prices.json (CORS fallback, frontend.md §11); already has
                         #   `permissions: contents: write` and the exact commit-on-change pattern INC-6's
                         #   tunables-cache step mirrors (admin-portal.md §16.4) — DRAFT: no changes for
                         #   INC-6 itself; read-only consumer of the tunables cache like daily-discovery.yml.
config/
  tunables_cache.json    # DRAFT (INC-6): last-known-good cache for the 10 FR30 curated tunables,
                         #   seeded at cutover with the same 10 values as the `tunables` table's seed
                         #   migration; written back only by hourly-watchlist.yml, read by every script
                         #   via config.py's fallback chain (admin-portal.md §16.4, Decision #28)
scripts/
  config.py              # market hours/gates, model Variables, discovery gates — all tunables
                         #   (shadow vars removed 2026-07-16 — see "Retired: shadow-pilot tracks")
                         #   DRAFT (INC-6): gains the 3-tier tunables fallback chain (Supabase table ->
                         #   config/tunables_cache.json -> hardcoded literal) and
                         #   write_tunables_cache_if_fetched() (admin-portal.md §16.4) — the first
                         #   module-level network call and first local-file write this file has ever had.
  ingest.py              # yfinance wrapper; market-agnostic; headline filter; session-aware price/vol
  prefilter.py           # Yahoo live screener + quality gates + signals + funnel; region-aware
  ai_judge.py            # Gemini batched judge_batch(models=...); BATCH_SYSTEM_PROMPT; schema + confidence
  state.py               # Supabase read/write; single-rule change machine; _snapshot()
  notify.py              # ntfy dispatch (provider-agnostic); per-market topic + timestamp
  textutil.py            # shared clip()
  run_hourly.py          # hourly watchlist orchestrator (per-market gate) — thin entry point.
                         #   DRAFT (INC-6): gains one line, config.write_tunables_cache_if_fetched(),
                         #   called early in main() — the only entry point that does.
  run_discovery.py       # daily discovery orchestrator (region-aware) — thin entry point. DRAFT: no
                         #   change for INC-6 — remains a pure read-only tunables-cache consumer.
  publish_prices.py      # fetch watchlist prices, write pages/prices.json — thin entry point. DRAFT: no
                         #   change for INC-6 — remains a pure read-only tunables-cache consumer.
sql/
  scheduler_pgcron.sql, phase5_monitoring.sql, dashboard_latest_call_view.sql
  kill_switch.sql, admin_portal_rls.sql, admin_portal_tunables.sql,
  kill_switch_portal_grant.sql                        # DRAFT, 2026-07-26/27 CR, INC-3/5/6/7
pages/
  detail.html, dashboard.html, prices.json
```

> **DRAFT additions (2026-07-26/27 CR, not yet implemented):** `scripts/ai_provider.py` (INC-4 —
> `AIProvider` interface + `GeminiProvider`, see `operational-controls.md` §14) and a new top-level
> `admin-portal/` directory (INC-5/6/7 — Next.js app deployed to Vercel, **no server-only secrets or API
> proxy routes**, see `admin-portal.md` §16.8, revised 2026-07-27/Decision #27). Neither exists in the
> repo yet; listed here in advance so this section stays the accurate map once they ship. `config.py`
> also gains a `_fetch_tunables()` / `_tunable()` fetch-with-fallback pair (INC-6, `admin-portal.md`
> §16.4) — the first module-level network call this file has ever made, short-timeout and
> exception-wrapped so a Supabase hiccup falls back to the existing hardcoded literals rather than
> hanging or crashing process startup.

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

> **DRAFT (2026-07-26 CR, INC-4, not yet implemented):** `AI_PROVIDER` (default `"gemini"`) — selects
> the `AIProvider` implementation `judge_batch()` uses; see `operational-controls.md` §14.4. Not on the
> admin portal's curated list (FR30) — single-valued today, nothing to edit.
>
> **DRAFT — REVISED 2026-07-27, Decisions #27 (supersedes the prior GitHub-Variable-AND-gate plan
> recorded here; superseded text is preserved in git history, not here — doc hygiene, don't restate
> retired plans verbatim) and #28 (refines #27's failed-fetch fallback):** the 10 FR30-curated keys
> (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, and the seven `DISCOVERY_*`
> gate/signal/shortlist/cooldown keys) no longer come from a GitHub Actions Variable at all. Instead,
> `scripts/config.py` fetches all 10 from a new Supabase `tunables` table at process start, falling back
> — on a failed fetch — to the last-known-good value cached in the repo-committed
> `config/tunables_cache.json` (a hardcoded Python literal is now only the third-tier floor for a
> missing/corrupted cache file, not the primary fallback; full detail in `admin-portal.md` §16.4).
> `ALERTS_ENABLED` is the one key with a second live input to reconcile (the pre-existing
> `workflow_dispatch` `inputs.alerts_enabled` manual-dry-run override, env var unchanged); resolved as a
> pure `scripts/config.py` AND (table/cache value can only *suppress*, never force on, over an explicit
> manual dry-run) — see `admin-portal.md` §16.4 for the exact logic. **One workflow YAML change is now
> part of INC-6** (Decision #28's write-back mechanism, not Decision #27's read path): `hourly-watchlist.
> yml` gains a `permissions: contents: write` block (it has none today) and a "commit tunables cache if
> changed" step mirroring `publish-prices.yml`'s existing pattern — it is the sole writer of
> `config/tunables_cache.json`; `daily-discovery.yml` and `publish-prices.yml` remain unchanged, read-only
> consumers. This is **not on this section's config-surface list** as a `${{ vars.X }}` workflow-Variable
> tunable the way `GEMINI_MAX_RETRIES` etc. are — it's a `config.py`-internal fetch against Supabase (with
> a file-based fallback), a third tunables surface alongside "`config.py` env-var defaults" and
> "workflow-YAML `vars.X`" described above. The pre-existing `${{ vars.GEMINI_MODEL || '...' }}` /
> `_BACKUP` Variable wiring already in `hourly-watchlist.yml` becomes a harmless, unread vestige once the
> table/cache chain takes precedence for those two keys (`_tunable()` never consults that env var) — safe
> to leave, not required to remove for correctness; noted as an optional future cleanup, not INC-6 scope.
