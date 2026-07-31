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
- **7.2 Security (NFR7):** no trade execution, no brokerage credentials anywhere. Secrets never in code.
  `dispatch_github_workflow` is `SECURITY DEFINER`, reads the PAT from Vault only, never echoes it. Detail
  page uses the read-only publishable key under RLS; `call_log.id` is a UUID. Every table has RLS (REV-058,
  2026-07-28: retitled from "NFR3" — NFR3 is the Disclaimer requirement; NFR7, added by pm the same day,
  is this system's dedicated core-security-posture ID. `sql/schema.sql`, REV-035, is this posture captured
  in version control).
- **7.3 Currency:** native per market — USD (US), CAD (TSX), INR (NSE) — no FX conversion. **Enforced, not
  assumed, as of the DEEP-006/INC-10 fix (FR11/FR29, Decision #35):** this used to be an assumption about
  the input data that nothing checked — the admin portal's `holdings.currency` was a free-choice field
  (defaulting to USD for every market) never reconciled against the held ticker's own `watchlist.market`.
  Two independent layers now hold the invariant: (1) a `holdings` `BEFORE INSERT/UPDATE` trigger derives
  `currency` from the row's `watchlist.market` (US⇒USD, TSX⇒CAD, NSE⇒INR) and **overwrites whatever was
  submitted** — same-currency-by-construction, not by client cooperation — covering the portal, a direct
  SQL edit, and any future write path alike (`admin-portal.md` §16.3). (2) defense-in-depth in
  `state.build_position`: if `holdings.currency` and the independently-fetched
  `data["fundamentals"]["currency"]` (Yahoo's own currency for the ticker) ever disagree — e.g. a
  `watchlist.market` that doesn't actually match the ticker's real listing — `pl_pct` is suppressed
  (`None`) rather than computed from mismatched currencies, per FR11's explicit requirement. **One layer
  further, added in INC-10 fix-cycle-2 (REV-113):** `build_position`'s mismatch flag alone left the raw,
  unlabeled `cost_basis`/`price` figures still rendered next to each other in the AI prompt with no
  guardrail against the model computing its own ratio from them — `ai_judge._ticker_block`
  (`ai_judge.py:101-116`) now withholds both raw figures on a mismatch too, replacing them with an
  omission sentence naming both currencies, rather than relying on the model reliably obeying a
  don't-compute instruction. Full mechanism: `admin-portal.md` §16.3, `components.md` §4.4/§4.7 (detail-page
  consumer unaffected — it already just renders whatever `position.currency`/`pl_pct` holds).
- **7.4 Concurrency:** `concurrency: { group: hourly-watchlist, cancel-in-progress: false }` serializes
  overlapping runs so two runs never double-write `verdict_state` for a ticker. **DRAFT (INC-6, Decision
  #29/REV-040):** this group is renamed `repo-commit` and shared with `publish-prices.yml`'s own group —
  the serialization guarantee above is preserved (see `docs/design/tunables-workflow-writeback.md` for
  why), a second workflow is just added to the same queue.
- **7.5 Delisting / halts / new listings / closed-market days (FR17, Decision #8):** no-data ticker →
  skip-with-log, never fatal for others. New listings return valid price but short history → compute what
  history supports, mark 20d fields `n/a (newly listed)`, let the AI judge the rest.
  **Closed-market (holiday) detection, DEEP-004/INC-9, Decision #33 — the documented "holiday ⇒ no usable
  data ⇒ skip-with-log" behavior did not previously exist in code:** neither the SQL dispatch gate nor
  `config.is_market_open()`/`is_nse_open()` consult a holiday calendar (accepted — Decision #8, no
  maintained-calendar burden), so on an actual holiday the workflow still dispatches; `yfinance` then
  returns the *prior* session's bar, which `_session_state()`'s weekday/clock-only check read as a live,
  in-progress session — pro-rating a stale, zero-trading day's volume into a fabricated "spike" that could
  fire a real, wrong alert. **Fix:** `get_market_data()` now compares the last available bar's date to
  today's date in the market's own local calendar; when they disagree while `_session_state()` says "live,"
  the ticker takes the same skip-with-log path as any other no-data day — full mechanism and code shape in
  `components.md` §4.2. This is the structural check FR17's sharpened text requires precisely because no
  maintained holiday calendar exists (Decision #8): a closed market must be detected from the data itself.
  Same posture across US, TSX, and NSE (Decision #33 — no market gets special-cased).

---

## 8. Repo structure & module boundaries

```
.github/workflows/
  hourly-watchlist.yml   # workflow_dispatch only; concurrency group
                         #   (former shadow steps removed 2026-07-16 — see docs/design.md's
                         #    "Retired: shadow-pilot tracks" note)
                         #   IMPLEMENTED (INC-6, tunables-workflow-writeback.md, reviewer-CLEAR Pass 19):
                         #   a JOB-scoped `permissions: contents: write` (this workflow had NONE
                         #   before) + a "Commit tunables cache if changed" step with a bounded push
                         #   retry (REV-040b); its `concurrency.group` is `repo-commit`, shared with
                         #   publish-prices.yml (REV-040a). Sole writer of tunables_cache.json.
  daily-discovery.yml    # workflow_dispatch only; concurrency group — no changes for INC-6; reads
                         #   tunables_cache.json read-only via config.py's fallback chain, same as
                         #   every script, no permissions change needed for a read.
  publish-prices.yml     # writes pages/prices.json (CORS fallback, frontend.md §11); already has
                         #   `permissions: contents: write` and a commit-on-change pattern —
                         #   IMPLEMENTED (INC-6): its `concurrency.group` is `repo-commit` (REV-040a,
                         #   shared with hourly-watchlist.yml) and nothing else changed — remains a
                         #   read-only tunables-cache consumer, has no commit step of its own.
scripts/
  config.py              # market hours/gates, model Variables, discovery gates — all tunables
                         #   (shadow vars removed 2026-07-16 — see "Retired: shadow-pilot tracks")
                         #   IMPLEMENTED (INC-6): the two-tier tunables fallback chain (Supabase table
                         #   -> repo-root tunables_cache.json, fails loud via SystemExit if both tiers
                         #   miss a key — full mechanism in docs/design/tunables-fallback.md §16.4, not
                         #   restated here) and write_tunables_cache_if_fetched() — the first
                         #   module-level network call and first local-file write this file has ever had.
  ingest.py              # yfinance wrapper; market-agnostic; headline filter; session-aware price/vol.
                         #   IMPLEMENTED (REV-043, live-system fix not gated on any increment): a narrow
                         #   get_price_only(ticker) for publish_prices.py — see components.md §4.2.
                         #   IMPLEMENTED (DEEP-004, INC-9, reviewer-CLEAR Pass 25): get_market_data()
                         #   gains the stale-bar/closed-market structural check — see components.md §4.2.
  prefilter.py           # Yahoo live screener + quality gates + signals + funnel; region-aware
  ai_provider.py         # IMPLEMENTED (INC-4, 2026-07-28, FR33): AIProvider interface + GeminiProvider
                         #   (operational-controls.md §14); the sole owner of google.genai imports and
                         #   Gemini-SDK error classification. get_provider() resolves config.AI_PROVIDER.
  ai_judge.py            # provider-neutral judge_batch(models=..., provider=None) — talks only to
                         #   AIProvider/ProviderResult/ProviderError (ai_provider.py), no Gemini-SDK
                         #   coupling since INC-4; BATCH_SYSTEM_PROMPT; schema + confidence
                         #   IMPLEMENTED (DEEP-003, INC-9, reviewer-CLEAR Pass 25): _parse_batch's
                         #   positional fallback narrowed to ticker-corroborated, unambiguous matches
                         #   only — see components.md §4.4.
  state.py               # Supabase read/write; single-rule change machine; _snapshot()
                         #   IMPLEMENTED (DEEP-002, INC-8): process_ticker/process_candidate gate
                         #   alerted/verdict-state-advance on notifier.push()'s delivery result — see
                         #   components.md §4.6. IMPLEMENTED (DEEP-006, INC-10, reviewer-CLEAR Pass 27):
                         #   build_position() suppresses pl_pct on a currency mismatch — see §7.3 above.
                         #   IMPLEMENTED (INC-12, reviewer-CLEAR Pass 29 — DEEP-007 closed,
                         #   `docs/review-log.md`): gains is_paused(), KillSwitchAbort,
                         #   write_kill_switch_abort() and a checkpoint-3 call in process_ticker/
                         #   process_candidate — see operational-controls.md §13.6.
  notify.py              # ntfy dispatch (provider-agnostic); per-market topic + timestamp
                         #   FIX ROUND (DEEP-002, INC-8): push() returns True|False|None (delivered/
                         #   failed/dry-run) instead of nothing — see components.md §4.6.
  textutil.py            # shared clip()
  run_hourly.py          # hourly watchlist orchestrator (per-market gate) — thin entry point.
                         #   IMPLEMENTED (INC-6): gains config.write_tunables_cache_if_fetched(),
                         #   called early in main(); status computation gains `or
                         #   config.TUNABLES_DEGRADED` (REV-045) — the only entry point that writes back.
                         #   IMPLEMENTED (DEEP-001+002, INC-8): degraded formula gains outcomes["no-read"]
                         #   + outcomes["push-failed"] — see components.md §4.8. IMPLEMENTED (INC-12,
                         #   reviewer-CLEAR Pass 29 — DEEP-007 closed, `docs/review-log.md`):
                         #   gains checkpoint 1 (entry) + checkpoint 2 (before
                         #   judge_batch) — see operational-controls.md §13.6.2.
  run_discovery.py       # daily discovery orchestrator (region-aware) — thin entry point. IMPLEMENTED
                         #   (INC-6): the same `or config.TUNABLES_DEGRADED` (REV-045).
                         #   IMPLEMENTED (DEEP-001+002, INC-8): same degraded-formula fix as run_hourly.py.
                         #   IMPLEMENTED (INC-12, reviewer-CLEAR Pass 29 — DEEP-007 closed,
                         #   `docs/review-log.md`): same checkpoint 1/2 shape as
                         #   run_hourly.py — see operational-controls.md §13.6.2.
  publish_prices.py      # fetch watchlist prices, write pages/prices.json — thin entry point.
                         #   IMPLEMENTED (INC-6): the same `or config.TUNABLES_DEGRADED` (REV-045);
                         #   IMPLEMENTED (REV-043, live-system, independent of INC-6): switches to
                         #   ingest.get_price_only() instead of get_market_data(). IMPLEMENTED (INC-12,
                         #   reviewer-CLEAR Pass 29 — DEEP-007 closed,
                         #   `docs/review-log.md`): gains checkpoint 4, immediately before the
                         #   prices.json write — see operational-controls.md §13.6.2.
sql/
  scheduler_pgcron.sql, schema.sql, phase5_monitoring.sql, dashboard_latest_call_view.sql
                         #   schema.sql added 2026-07-28 (REV-035) — captures the 5 core tables +
                         #   RLS/grants that previously existed only live; see runbook.md §2.3.
  enable_monitor_alerts_rls.sql   # NEW 2026-07-28 (REV-033/035) — the one RLS-enable statement
                         #   phase5_monitoring.sql's monitor_alerts table was missing; apply order:
                         #   after phase5_monitoring.sql (see that file's own header).
  fix_missing_degraded_checks.sql, dedup_watchlist_health_check.sql
                         #   SUPERSEDED 2026-07-28 (REV-062 reconciliation) — each independently committed
                         #   a full check_pipeline_health() body that conflicted with INC-3's edit to
                         #   phase5_monitoring.sql; no apply order produced a correct function. Their
                         #   REV-042/REV-047 fixes are now folded into phase5_monitoring.sql's single
                         #   reconciled function (see that file's header). These two files no longer
                         #   define the function and must NOT be applied; kept only as non-applyable
                         #   historical markers (git history has the original bodies).
  kill_switch.sql, admin_portal_rls.sql, admin_portal_tunables.sql,
  kill_switch_portal_grant.sql                        # IMPLEMENTED, 2026-07-26/27 CR, INC-3/5/6/7 —
                                                       # applied and live, see docs/runbook.md §2.3/§2.4.
  tunables_validate_trigger.sql        # IMPLEMENTED (DEEP-005, INC-10, reviewer-CLEAR Pass 27):
                                        #   BEFORE UPDATE trigger mirroring config.py's per-key tunable
                                        #   cast/domain contract — see admin-portal-tunables.md §16.4.
  holdings_currency_derivation.sql     # IMPLEMENTED (DEEP-006, INC-10, reviewer-CLEAR Pass 27):
                                        #   BEFORE INSERT/UPDATE trigger deriving holdings.currency
                                        #   from watchlist.market — see admin-portal.md §16.3.
  admin_portal_tunables_alerts_enabled_description_fix.sql   # IMPLEMENTED (INC-10 fix-cycle-2, REV-112,
                                        #   reviewer-CLEAR Pass 27): one-column, one-row corrective
                                        #   UPDATE, additive/idempotent — see admin-portal-tunables.md §16.4.
  kill_switch_abort_log.sql            # IMPLEMENTED, APPLIED AND LIVE (INC-12, reviewer-CLEAR Pass 29 —
                                        #   REV-117's missing `truncate` fixed in operational-controls.md
                                        #   §13.6.5, `docs/review-log.md`): new append-only table, FR35's
                                        #   causal-tie record — see operational-controls.md §13.6.5.
pages/
  detail.html, dashboard.html, prices.json   # FIX ROUND (DEEP-001, INC-8): dashboard.html's per-row
                                              #   verdict pill widens its "no reading" special-case from
                                              #   parse_status=="no_data" to also cover "failed"/
                                              #   "api_error" — see components.md §4.8.
tunables_cache.json      # IMPLEMENTED (INC-6): repo-ROOT last-known-good cache for the 10 FR30 curated
                         #   tunables (REV-046 — deliberately NOT inside a config/ subdirectory, which
                         #   would collide with the scripts/config.py module name); seeded at cutover
                         #   with the same 10 values as the tunables table's seed migration; written
                         #   back only by hourly-watchlist.yml (tunables-workflow-writeback.md)
```

> **IMPLEMENTED (INC-4, 2026-07-28):** `scripts/ai_provider.py` (`AIProvider` interface + `GeminiProvider`,
> see `operational-controls.md` §14) has shipped and is listed in the repo map above under `scripts/`.
> This stub is retained only as a pointer to §14, so this section's history stays legible.
>
> **IMPLEMENTED (INC-5/6/7, all reviewer-CLEAR Passes 17/19/20):** the top-level `admin-portal/`
> directory (Next.js app deployed to Vercel, **no server-only secrets or API proxy routes**, see
> `admin-portal.md` §16.8) has shipped and is live. `config.py` also has `_fetch_tunables()` /
> `_tunable()` (INC-6, `docs/design/tunables-fallback.md` §16.4) — the first module-level network call this
> file has ever made, an explicit timeout (`TUNABLES_FETCH_TIMEOUT_MS`) and a deterministic offline test
> seam (`SKIP_TUNABLES_FETCH`), and a **fail-loud `SystemExit`** on a double-miss rather than hanging or
> silently guessing — full mechanism in that file, not restated here (see §9 below for the two-tier chain's
> one-sentence summary).

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
`DETAIL_PAGE_BASE`, `ALERTS_ENABLED` (false), `FORCE_RUN` (false), `AI_PROVIDER` (`"gemini"` — selects the
`AIProvider` implementation `ai_judge.judge_batch()` uses, `operational-controls.md` §14.4; not on the
admin portal's curated list, FR30 — single-valued today), `AI_TEMPERATURE` (0.2 — Gemini call sampling
temperature, `ai_provider.GeminiProvider.generate`; REV-078, 2026-07-28, `operational-controls.md` §14.3;
not on the admin portal's curated list, FR30), `MIN_HISTORY_ROWS` (21),
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

> **IMPLEMENTED (INC-4, 2026-07-28):** `AI_PROVIDER` is now listed in the core baseline paragraph above,
> alongside the rest of `config.py`'s tunables — this stub is retained only as a pointer to
> `operational-controls.md` §14 (the hand-rolled-vs-LiteLLM decision and the `AIProvider`/`GeminiProvider`
> interface shape) and `scripts/ai_provider.py` (the implementation).
>
> **DRAFT — REVISED 2026-07-27/28, Decisions #27/#28/#29 (2026-07-28 fix, REV-037): stated once, here
> only a pointer.** The 10 FR30-curated keys (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`,
> and the seven `DISCOVERY_*` gate/signal/shortlist/cooldown keys) no longer come from a GitHub Actions
> Variable at all — they're a **third tunables surface**, alongside "`config.py` env-var defaults" and
> "workflow-YAML `vars.X`" described above: a `config.py`-internal fetch against a Supabase `tunables`
> table, with a **two-tier** fallback (table → repo-root `tunables_cache.json`; **no third,
> hardcoded-literal tier** — a double-miss fails loud via `SystemExit`, it does not fall back to a
> hardcoded default). Full mechanism, the exact `hourly-watchlist.yml` write-back diff, and the
> `ALERTS_ENABLED` AND-gate: `docs/design/tunables-fallback.md` and
> `docs/design/tunables-workflow-writeback.md` (§16.4, both) — not restated here, so this stub can't drift
> from those files again the way it did before this fix. Two new non-curated `config.py` tunables support
> this fetch: `TUNABLES_FETCH_TIMEOUT_MS` (default `5000`, explicit fetch timeout) and
> `SKIP_TUNABLES_FETCH` (default `false`, deterministic offline path for tests/local runs). The
> pre-existing `${{ vars.GEMINI_MODEL || '...' }}` / `_BACKUP` Variable wiring already in
> `hourly-watchlist.yml` becomes a harmless, unread vestige once the table/cache chain takes precedence for
> those two keys — safe to leave, not required to remove for correctness; optional future cleanup, not
> INC-6 scope.
