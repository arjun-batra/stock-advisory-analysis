# Stock Advisory Agent — Solution Design (as-built)

**Owner:** tech-lead. **Status:** DESCRIPTIVE / as-built. Phases 0–7 are live in production.
**Provenance:** This document was produced during the 2026-07-12 multi-agent-template adoption pass by
condensing the existing, code-verified solution design `requirements_docs/SD.md` (v20, ~1400 lines) into
this template's format, and by adding the previously-undocumented shadow wallet pilot section (§13) from
the actual code. It is **reverse documentation of a shipped system**, not forward design work. `SD.md`
and `requirements_docs/SD-history.md` remain in the repo as the historical/rationale record; where this
doc and `SD.md` disagree, the code wins and this doc is the one to fix.

**Requirement IDs** referenced throughout map to `docs/requirements.md` (FR1–FR23 / NFR1–NFR4 core;
FR24–FR31 / NFR5 experimental shadow pilot). Numbering is unchanged from the v5 source, so `SD.md`'s
existing FR references still line up (spot-checked: FR7/FR8 single-rule alerting, FR15 logging, FR21
dashboard freshness, FR23 timestamps, FR4 discovery all match).

---

## 0. Load-bearing decisions (read before changing anything)

These are the "why it is this way" calls that are cheap to reverse without realizing the cost. Full
provenance is in `requirements_docs/SD-history.md`; the load-bearing short version, preserved verbatim in
intent from `SD.md §0`:

1. **Single-rule alerting (FR7, FR8; §6).** Any verdict change → immediate alert; no change → silence.
   No cooldown, no debounce, no 7-day reminder (the old FR7 reminder is retired). The removed
   cooldown/reminder added state that wasn't earning its keep on a single-user push tool. Accepted cost:
   alert bursts on a choppy day. **Don't re-add a cooldown/debounce without a real, observed volume
   problem.**
2. **Signal on crossings, not standing states (FR8; §6).** A standing Buy/Sell that never changes is
   silent by design — there is no bootstrap re-announce. A logged change is one threshold crossing, not
   proof of a durable signal; read the track record that way.
3. **Gemini fallbacks were never quota/RPD (§4.4).** The real cause was a client-side timeout firing on
   slow-but-valid (already token-billed) responses, plus occasional 503s — fixed with
   `GEMINI_TIMEOUT_MS=180s`. The real reason is logged per call in `data_snapshot.fallback_from`;
   **don't call fallbacks "rate-limiting."**
4. **Supabase pg_cron is the clock, not GitHub cron (§4.1).** GitHub's shared scheduler silently dropped
   most ticks. The **runtime market gate, not the schedule, is the authority** on whether work happens —
   the schedule fires loosely and the market gate trims it. Never trust the schedule to mean "market
   open." (NFR2.)
5. **Reliability is an active dead-man monitor (§4.8, NFR2).** It must surface a run that *never
   triggers*, not only one that runs and fails. Known limit: it lives in the same pg_cron it watches
   (single point of failure, §2 item 6); an out-of-band ping is the unbuilt mitigation.
6. **One batched AI call per run, not per ticker (§4.4).** This is what keeps the system under the
   free-tier daily request cap (NFR1). `data_snapshot.tokens` is a **per-batch total replicated on every
   row** — dedup per run, never sum per row.
7. **Discovery uses Yahoo's live screener, not a maintained universe (§4.3).** The `candidate_universe`
   table was vestigial and has been dropped; there is no seed/quarterly-refresh ownership burden. Don't
   reintroduce one.
8. **AI fails safe to Hold (§4.4, FR9).** A parse/API failure logs a fail-safe Hold, and the change
   detector's cold-start/no-change guard stops it from being read as a real change — so a bug can only
   ever *miss* a signal, never *fabricate* one. Keep that guard.
9. **Market-close dispatch boundary is close + 5 min (SQL) / close + `RUNTIME_CLOSE_GRACE_MIN` (Python),
   not exact close (§4.1).** The two layers carry different close bounds **on purpose** — the SQL gate
   (16:05 ET / 15:35 IST) absorbs pg_cron sub-second jitter; the Python gate (16:00 +
   `RUNTIME_CLOSE_GRACE_MIN`, default 10 min) absorbs dispatch-to-execution latency (runner queue +
   checkout + pip install). Both bugs were confirmed and fixed. **Don't tighten either bound to the exact
   close, and don't "simplify" the two numbers into one** — they protect against different failure modes.
   Neither admits the following post-close `*/30` slot.
10. **Shadow pilot is triple-isolated and fail-open by policy (§13, FR27–FR30, NFR5).** The shadow track
    can never alert, can never be read by the dashboard/anon key, and can never fail production (three
    independent belts, §13.4). Its kill switch **defaults ON (fail-open)** — an accepted, recorded risk
    (FR30): an unset/mistyped `SHADOW_ENABLED` Variable *keeps the pilot running*. Only the literal string
    `false` disables it. Don't "fix" the fail-open to fail-closed without re-reading FR30/NFR5 — it is a
    deliberate opt-out design, valid only while the three isolation guarantees hold.

---

## 1. Purpose & confirmed architecture choices

The requirements doc closes the product questions; this doc closes the engineering ones — what runs
where, what persists, and the contracts a dev/QA team builds and tests against. Three architecture
decisions are locked:

| Decision | Choice |
|---|---|
| Candidate discovery method | Prefiltered live-screener universe (movers/volume/earnings/52w) → AI judges the shortlist (FR4) |
| AI model | Gemini Flash, free tier (model names are configurable repo Variables, §4.4) (NFR1) |
| State / control plane | Supabase (Postgres) — state persistence **plus** the scheduler and the watchdog (§4.1, §4.8) |

Supabase is the **control plane**, not just the database: it persists state, triggers both workflows via
`pg_cron`, and runs the health monitor. That concentration is deliberate (one reliable mechanism beat
GitHub's flaky scheduler) but makes Supabase a single point of failure for the trigger-and-watchdog path
(§2 item 6).

---

## 2. Accepted risks (documented, not hidden)

Carried from `SD.md §2` plus the pilot additions. These are recorded so they are not silently
"discovered" and reversed later.

1. **Gemini free tier trains on submitted prompts** (watchlist, holdings, cost basis flow through it).
   Accepted for the $0–15/mo budget (NFR1); swap to a paid/isolated model is a small, isolated change.
2. **Yahoo Finance API is unofficial** — no SLA, TSX/NSE fundamentals may be incomplete. Day-one
   smoke test per market is mandatory (done, §9).
3. **Free-tier quotas move; the observed fallbacks were never quota** — they were client-side
   timeout / 503, corrected. Real cause logged in `fallback_from` (load-bearing #3).
4. **No spam control** — non-deterministic verdicts surface directly as alerts; a choppy day pushes on
   every flip. Accepted cost of the single-rule design (FR8, load-bearing #1).
5. **Holiday calendars are not consulted** (US/TSX/NSE) — a closed market falls through skip-with-log
   (FR17, §7.5).
6. **Supabase is a single point of failure for trigger + watchdog** — an out-of-band uptime ping is the
   noted (unbuilt) mitigation (NFR2).
7. **Dashboard auth is client-side obfuscation, not real security** — acceptable only for read-only,
   informational, RLS-scoped data (FR19, Decision #11).
8. **Yahoo price API is browser-CORS-blocked** — dashboard reads a server-published `prices.json`
   snapshot same-origin (FR21, Decision #18, §11).
9. **Shadow pilot kill switch defaults fail-open (FR30, NFR5)** — accepted only while isolation
   guarantees FR27–FR29 hold; if any is weakened, revisit the default.

---

## 3. High-level architecture

```
Supabase (control plane)                    GitHub Actions (execution only, workflow_dispatch)
  pg_cron jobs ──► dispatch_github_workflow()   hourly-watchlist.yml ─┐
       │              │ (pg_net HTTP REST)       daily-discovery.yml  ├─► yfinance (Yahoo)
       │              └────────────────────────► publish-prices.yml ──┘        │
       │                                                │                       ├─► Gemini Flash
       ├─ health-monitor ─► check_pipeline_health() ─► ntfy.sh (monitor alerts) │   (primary+backup)
       │                                                │                       │
  Postgres state ◄──────────────── workflows read/write │                       └─► ntfy.sh
       ▲                                                │                            (change / new-candidate)
       │  publishable key (read-only, RLS)              │                            └─► tap-through
       ├─ Detail page (GitHub Pages) ◄──────────────────┘                                 detail page
       └─ Dashboard (GitHub Pages) ◄─ reads call_log/watchlist (anon) + prices.json (same-origin)
```

Key shape: the trigger arrow originates in **Supabase pg_cron**, calls GitHub's dispatch API over
`pg_net`, and a third pg_cron job is the watchdog. GitHub Actions is purely an execution surface.
`publish-prices.yml` writes `pages/prices.json`, which the dashboard reads same-origin (Yahoo is
browser-CORS-blocked, §11).

Entry points are thin orchestrators (`run_hourly.py`, `run_discovery.py`, `publish_prices.py`,
`run_shadow.py`) — no business logic; all logic lives in importable, testable modules (§8). External
dependencies (Supabase client, Gemini client, yfinance, clock) are reached through module functions so
they can be substituted in tests.

---

## 4. Components

### 4.1 Scheduler — Supabase pg_cron → GitHub `workflow_dispatch` (FR6, FR17, NFR2)

- Both workflows are **`workflow_dispatch`-only** (native `schedule:` removed — GitHub's shared
  scheduler dropped ~13 of ~16 daily ticks, silently, the worst failure mode for a don't-miss-things
  system).
- `pg_cron` holds the schedule and calls a `SECURITY DEFINER` function
  `dispatch_github_workflow(workflow_file, inputs)` that reads a GitHub PAT from **Supabase Vault** and
  POSTs the dispatch via **`pg_net`**.
- **Load-bearing safety principle (load-bearing #4):** the schedule fires more often than needed; the
  **runtime market gate is the real authority** on whether work happens.
- **ET/IST-aware, DST-correct gating.** `dispatch_watchlist_if_open()` gates US/TSX on
  `(now() at time zone 'America/New_York')::time between '09:30' and '16:05'` + weekday;
  `dispatch_watchlist_nse_if_open()` gates NSE on the IST session `09:15`–`15:35`. The wide
  `*/30 13-21 UTC` (US/TSX) and `*/30 3-10 UTC` (NSE) crons are DST supersets trimmed by the gates.
  The **16:05 / 15:35 upper bounds are close + 5 min** — deliberate jitter slack (load-bearing #9).
- **Python execution-time defense-in-depth.** `config.is_market_open()` / `is_nse_open()` recompute the
  gate in ET/IST; their close bound is **16:00 / 15:30 + `RUNTIME_CLOSE_GRACE_MIN` (default 10 min)** —
  wider than the SQL slack because it absorbs dispatch-to-execution latency (load-bearing #9). Open bound
  stays exact.
- `daily-discovery.yml` is dispatched post-close: 22:00 UTC (`region=na`) and 10:00 UTC (`region=in`);
  discovery is not intraday-gated (§4.3, FR4 Decision #4).
- **Safe forced-test pattern.** `FORCE_RUN=true` bypasses the market gate; if `ALERTS_ENABLED=true` at
  the same time it fires **real** pushes off-hours. `run_hourly` prints a `[gate]` audit line every run.
  Documented safe pattern: for any off-hours forced run, set `ALERTS_ENABLED=false`.

SQL lives at `sql/scheduler_pgcron.sql` (dispatch fns + all cron jobs, matches live cron).

### 4.2 Data ingestion — `yfinance` (FR1, FR9, §7 data sources)

Single wrapper module (`ingest.py`) used by all workflows. Pulls price/volume, basic fundamentals
(`tk.info`), and built-in news (`Ticker.news`) — one data dependency, no separate news vendor. US tickers
are bare, TSX use `.TO`, NSE use `.NS`. **Market-agnostic:** keys off the ticker suffix and the yfinance
`exchange` field, so adding a market is a config concern, not an ingestion rewrite. `ingest._market_for`
resolves per-ticker market, carried on the `data` dict and persisted (§5).

Two data-quality behaviors (v18/v20, feed the prompt correctly):
- **Headline relevance filter** — `_headlines()` drops titles mentioning neither the company name
  (distinctive tokens; generic words stop-listed) nor the ticker, before the 5-title cap; **fail-open**
  when no company name is available. Dropped counts go to `notes`.
- **Session-aware price/volume** — `_session_state()` (strict session bounds, *not* the
  grace-extended dispatch gates) flags `session_live` and pro-rates `volume_vs_avg` by elapsed session
  fraction (`n/a` in the first 10%). Prompt renders "live price (session in progress)"/"today so far"
  vs "last close"/"1d" accordingly. Both flags persist to `data_snapshot`.

**Skip-with-log:** a ticker returning no usable data is skipped, never fatal (FR17, §7.5). New listings
(<~20 sessions) are *not* skipped — compute what history supports, mark 20d fields `n/a (newly listed)`.

### 4.3 Candidate sourcing & prefilter — discovery only (FR4, FR5, Decisions #4/#9/#14/#16)

`prefilter.py` sources candidates from **Yahoo's live server-side screener** (not a maintained universe —
load-bearing #7) and applies quality gates + signals locally:
- **Sourcing:** daily pull of `day_gainers` / `day_losers` / `most_actives` (US) plus custom
  EquityQueries for Canada (`region=ca`) and NSE (`region=in`), each including a day-volume-sorted
  most-actives-style query (`_volume_query`, floored at `DISCOVERY_MIN_VOLUME`) so a pure volume-spike
  candidate is reachable in all regions.
- **Quality gates (all tunable, per-region):** min market cap (`DISCOVERY_MIN_MARKET_CAP` ~$2B US/CA;
  `DISCOVERY_MIN_MARKET_CAP_INR` ₹5e10 NSE), min price (`DISCOVERY_MIN_PRICE` $5; `_INR` ₹50), min daily
  volume (`DISCOVERY_MIN_VOLUME` 500k), and an allow-list of primary exchanges
  (`DISCOVERY_ALLOWED_EXCHANGES` NYSE/Nasdaq/Toronto; `DISCOVERY_ALLOWED_EXCHANGES_IN` = `{NSI}` only,
  dropping BSE dual-listings).
- **Signals — a survivor must trip ≥1** (FR4's four criteria, code tag values in `prefilter._signals`):
  (1) `mover` — abs % change past `DISCOVERY_GAINER_PCT`/`DISCOVERY_LOSER_PCT`;
  (2) `volume` — today's volume ≥ `DISCOVERY_VOL_SPIKE` × 3-month avg;
  (3) `earnings` — earnings within `DISCOVERY_EARNINGS_DAYS` (best-effort, when the screener carries an
  earnings timestamp);
  (4) `52w-high` / `52w-low` — price within `DISCOVERY_52W_PROXIMITY` of the 52-week extreme.
- **Shortlist** ranked and capped at `DISCOVERY_SHORTLIST_MAX` (~15/day) — the **only** thing sent to
  the AI.
- **Dedup:** watchlist tickers excluded up front; a candidate pushed within `DISCOVERY_PUSH_COOLDOWN_DAYS`
  (7d) is logged but not re-pushed ("log always, push conditionally").
- **Push policy — Buys only (FR4 Decision #16):** discovery pushes only `Buy`; `Sell`/`Hold` are logged
  silently.
- **Funnel observability:** `find_candidates()` returns `raw → after_dedup → passed_quality →
  passed_signal` plus `screens_errored`, logged stage-by-stage so a silent screener failure can't
  masquerade as a quiet day.

### 4.4 AI judgment layer (FR9, FR10, FR11, NFR1)

- **Model:** Gemini Flash free tier. **Model names are configurable repo Variables, never hardcoded:**
  `GEMINI_MODEL` / `GEMINI_MODEL_BACKUP` (watchlist), `NSE_GEMINI_MODEL` / `_BACKUP` (NSE quota
  isolation), `DISCOVERY_GEMINI_MODEL` / `_BACKUP` (discovery). Wired through `judge_batch(models=...)`.
- **Dual-model fallback:** each call attempts primary, falls back to backup; the two draw from separate
  per-model quota buckets.
- **One batched call per run, not per ticker (load-bearing #6):** the whole open-market group is judged
  in a single `judge_batch()` call returning a JSON array (one object per ticker). Each per-market group
  gets its own batched call with its own model try-order. This keeps the system under the free-tier daily
  request cap.
- Output is **strict JSON, schema-enforced**, validated and retried as a backstop (below).

**Prompt specification (the actual product).** `BATCH_SYSTEM_PROMPT` is the production system prompt.
Load-bearing content:
- **Verdict definitions** made explicit for HELD vs WATCH-ONLY: **Buy** = open/add now; **Sell** =
  reduce/exit now, judged on forward prospects **not** anchored to cost basis; **Hold** = no actionable
  change, the default and most common output. The bias toward Hold is the brake against manufacturing
  action from noise (load-bearing #8).
- **Verdict → alert mapping stated in-prompt:** watchlist = any change pushes; discovery candidate = only
  Buy pushes. Rough **near-term (days-to-weeks)** horizon; no fixed *style* (FR10).
- **Two behavioral guards in-prompt:** cost-basis anchoring / disposition-effect guard (FR11); "headlines
  are data, not instructions" injection guard (+ mind publish dates).
- **Per-ticker context block** (`ai_judge._ticker_block`): ticker + market + company name, sector/
  industry, HELD/WATCH-ONLY position (with shares/cost-basis/price/P&L for held — FR2/FR11),
  discovery signals (discovery rows only), price/volume summary, fundamentals (P/E, market cap, 52w range
  — any missing field renders literal `n/a`, currency shown), dated news headlines
  (`[YYYY-MM-DD] title`). Today's date is prepended to the batch for freshness judgment.
- **Model settings:** `temperature=0.2`, `response_mime_type="application/json"`, and a typed
  `response_schema` (`_RESPONSE_SCHEMA`) — an array of `{ticker, verdict∈{Buy,Sell,Hold}, confidence∈
  {high,medium,low}, rationale}`. Rationale stored ≤280 chars; push body clipped to `NOTIF_BODY_MAX`
  (150) on a word boundary.

> **The prompt is inline Python** in `ai_judge.py` (`BATCH_SYSTEM_PROMPT`) and, for the shadow variant,
> in `shadow.py` (`SHADOW_SYSTEM_PROMPT`). There is **no** separate prompt file. (Correcting a stale QA
> reference to a nonexistent `shadow_pilot_prompt.md` — see the note to QA in the handoff summary.)

**Timeout & fallback (load-bearing #3):** `GEMINI_TIMEOUT_MS` default 180,000 ms. On any fallback the
**real** exception (timeout / 503 / parse / genuine 429) is captured to `data_snapshot.fallback_from` +
a run warning — the log is the source of truth for "why did it fall back."

**Parse & retry (load-bearing #8):** (1) request schema-enforced JSON, parse; (2) on failure retry once
with a terse "reply with ONLY the JSON array"; (3) on second failure **log, treat verdict as `Hold` (no
alert), move on** — a fail-safe Hold carries `confidence: null`, never fabricated. (4) every raw response
(incl. failures) is written to `data_snapshot`.

**Confidence (persisted, not yet consumed):** the model's self-rated `high`/`medium`/`low` is validated,
persisted in `data_snapshot.confidence`, surfaced on the cards, but **read by no gating logic today**
(known limitation, §12).

**Token accounting (load-bearing #6):** `data_snapshot.tokens {prompt, output, thoughts, total}` is a
**per-batch total replicated onto every row** — dedup per run, never sum per row.

### 4.5 State & persistence — Supabase (FR14, FR15)

All durable state in Postgres (schema §5). Chosen over a flat file because the detail page (FR14) queries
a specific log row directly. Supabase also hosts the scheduler and watchdog (§4.1, §4.8).

### 4.6 Alerting — ntfy.sh (FR12, FR13, FR14, FR18, FR23, NFR3)

Free, no account, topic-based push, `click` field for tap-through. `notify.py` is provider-agnostic
(Pushover is a drop-in). One watchlist alert kind — `change` ("Changed to Buy"); the `reminder` kind is
retired (FR7). Discovery pushes are labeled `new-candidate`. Health-monitor pushes come from Supabase
directly via `send_ntfy`.

- **Notification timestamp (FR23):** formatted server-side, so **one** market-matched timezone, no
  secondary — US/TSX → ET (`10:30 AM ET`), NSE → IST (`8:00 PM IST`). `notify._market_timestamp(market)`;
  `_compose_body` prefixes it within `NOTIF_BODY_MAX=150`. Unknown market → ET.
- **Separate NSE topic (FR18):** `notify._topic_for(market)` routes NSE → `NSE_NTFY_TOPIC`, US/TSX →
  `NTFY_TOPIC`, **falling back to the default topic if `NSE_NTFY_TOPIC` is unset** (never drops an alert)
  and emitting an operator-visible `[FR18 fallback]` run-log line if it does.
- Notification copy (titles/body) is owned by the UI handoff (`requirements_docs/
  stock-advisor-ui-handoff-v3-spec.md`, v4) — build to the handoff.

### 4.7 Detail page — GitHub Pages (FR14, FR2, FR11, FR23, NFR3, Decision #17)

Static page; reads `log_id` from the query string and fetches that `call_log` row via a read-only
Supabase **publishable key** (RLS-scoped to read `call_log`). The workflows use the **secret key**
(bypasses RLS), never shipped to the page. Security is the **unguessable URL**, which holds only because
`call_log.id` is a **UUID, not a serial**. **No auth gate** (Decision #17 — FR19's access control scopes
to the dashboard only; NFR3 informational data is the accepted rationale).

- **Held-position block:** rendered only when `data_snapshot.position` is present (held tickers) —
  shares, cost basis, current price, unrealized P/L (FR2/FR11). Currently dormant (live watchlist has 0
  held tickers); ruled working-as-intended.
- **Market badge / currency:** derived from `data_snapshot.market` (`$` / `CA$` / `₹`); suppressed on
  `new-candidate` rows (no authoritative market). `.NS`-suffix + fundamentals-currency fallbacks remain
  only for legacy rows.
- **Timestamp (FR23):** client-rendered, device timezone primary + IST secondary in brackets, deduped if
  the device is IST. `call_log.timestamp` is UTC; conversion is client-side.
- **No-data rows:** a `parse_status=='no_data'` row shows a "skipped, no verdict made" note.
- Layout/variants owned by the UI handoff (v4).

### 4.8 Reliability — active dead-man monitor (NFR2)

A passive heartbeat no one reads is not a monitor (load-bearing #5). Design:
- A third pg_cron job, **`health-monitor`**, runs **`check_pipeline_health()`** independently of the two
  workflows.
- It actively raises an **ntfy alert** (via `send_ntfy`) when: the watchlist heartbeat is **stale during
  market hours** (ET window `10:15`–`16:00`, plus a second IST window for NSE), a **discovery run didn't
  fire** (per-region: `daily-discovery` NA checked after 23:00 UTC, `daily-discovery-in` NSE checked
  after 11:00 UTC), the **dashboard price snapshot stops refreshing** (`publish-prices` heartbeat >70 min
  old during a session), or a run **completed degraded**.
- **`monitor_alerts`** (state table) dedups: alert on state change into a bad state, re-alert per
  cooldown while bad, one recovery notice when it clears. Helpers `_raise_monitor` / `_clear_monitor`.
- The `health-monitor` cron window is `4-11,14-23` UTC (covers both sessions + both discovery checks).
- DDL: `sql/phase5_monitoring.sql`.

**Known limit (§2 item 6):** the monitor lives in the same Supabase pg_cron it watches — it cannot catch
a total Supabase/pg_cron outage. An out-of-band uptime ping is the documented, unbuilt mitigation.

---

## 5. Data model (Supabase / Postgres)

| Table | Key columns | Purpose / FR |
|---|---|---|
| `watchlist` | ticker, market (US/TSX/NSE), type, status (held/watch-only), date_added | Ticker list (FR1, FR3); `market` CHECK admits NSE |
| `holdings` | ticker, shares, cost_basis, currency | Position data (FR2, FR11); `currency`∈{USD,CAD,INR}; `shares>0`/`cost_basis>0` CHECK guards |
| `verdict_state` | ticker, current_verdict, last_checked_at | Change-detection for the single rule (FR7/FR8); shrunk to 3 cols when cooldown/reminder retired |
| `call_log` | id (**uuid**), ticker, verdict, rationale, timestamp (UTC), label (watchlist/new-candidate), alert_type (change/null), alerted (bool), data_snapshot (jsonb) | Track record (FR15); detail-page source (FR14) |
| `monitor_alerts` | check_name (PK), last_state, last_alerted_at, updated_at | Dead-man monitor dedup (NFR2) |
| `run_heartbeat` | workflow_name, last_run_at, status | Per-workflow heartbeat (NFR2). Keys: `hourly-watchlist` (shared across sessions), `daily-discovery` (NA), `daily-discovery-in` (NSE), `publish-prices` |

**View `latest_call_per_ticker`** (`sql/dashboard_latest_call_view.sql`): most recent `call_log` row per
ticker (`DISTINCT ON (ticker) … ORDER BY ticker, timestamp DESC`), slim columns only (`id, ticker,
verdict, rationale, timestamp, label, alerted, parse_status, price, confidence`). `security_invoker=true`
so the publishable key is still governed by `call_log`'s RLS. Replaces a client-side scan that shipped
multi-MB `raw_model_response` per refresh (FR21, NFR1).

**`data_snapshot` (jsonb) contract — the load-bearing consumer contract:**
```json
{
  "market": "US | TSX | NSE",
  "price": 0.0, "pct_change_1d": 0.0, "pct_change_5d": 0.0, "pct_change_20d": 0.0,
  "volume_vs_avg": 0.0, "session_live": false, "volume_pro_rated": false,
  "fundamentals": { "pe": 0, "market_cap": 0, "range_52w": [0,0], "currency": "USD",
                    "name": "...", "sector": "...", "industry": "..." },
  "headlines": ["[2026-06-30] ...", "..."],
  "raw_model_response": "<verbatim>",
  "confidence": "high | medium | low | null",
  "parse_status": "ok | retried | failed | api_error | no_data",
  "model_used": "<gemini model string>",
  "tokens": { "prompt": 0, "output": 0, "thoughts": 0, "total": 0 },
  "fallback_from": "<null | timeout | 503 | 429-rpd | parse | ...>",
  "discovery_signals": ["mover", "volume", "52w-high"],
  "rate_limited": false,
  "position": { "shares": 0, "cost_basis": 0.0, "currency": "USD", "pl_pct": 0.0 }
}
```
- `tokens` is a **per-batch total replicated across every row — dedup per run, never sum per row**
  (load-bearing #6).
- `discovery_signals` present only on discovery rows; `position` present only on held tickers; `market`
  written on both write paths by `state._snapshot()`.
- `confidence` is `null` on any fail-safe path, never a guessed default; not yet read by any consumer
  (§12).

**Timestamps stored in UTC; rendering per-surface (FR23):** notifications = one market timezone
(server); detail page + dashboard = device primary + IST secondary (client); relative time computed
client-side at render from `call_log.timestamp` (never stored). Market-hour gating computed in ET/IST,
never fixed UTC offsets.

**Supabase objects.** Functions: `dispatch_github_workflow`, `dispatch_watchlist_if_open`,
`dispatch_watchlist_nse_if_open`, `send_ntfy`, `_raise_monitor`, `_clear_monitor`,
`check_pipeline_health`. View: `latest_call_per_ticker`. Extensions: `pg_cron`, `pg_net`. Vault secrets:
`github_workflow_pat`, `ntfy_topic`. RLS is on for every table; publishable key has SELECT policies on
`call_log` and `watchlist` only. **`call_log_shadow` (§13) has RLS on with NO anon policy/grant.**

---

## 6. Core flow — single-rule change detection (FR6, FR7, FR8, FR15)

Cadence is **every 30 minutes** during market hours (the workflow is legacy-named `hourly-watchlist.yml`
and heartbeat `hourly-watchlist`, which do **not** mean 60 minutes). Each wake-up filters the watchlist to
whichever session is open (US/TSX via ET, NSE via IST — sessions never overlap, verified) and runs that
group through its own batched AI call.

The single alerting rule (load-bearing #1/#2), implemented in `state.py`:

```
for each ticker in (watchlist filtered to the currently-open market):
    new_verdict = ai_judge(...)                 # JSON-validated, fails safe to Hold
    state = get_verdict_state(ticker)

    if state is None:                           # cold start: baseline, no alert (avoids go-live dump)
        create_verdict_state(ticker, new_verdict, now)
        write_call_log(ticker, new_verdict, alert_type=NULL, alerted=False)   # FR15
        continue

    if new_verdict == state.current_verdict:    # no change -> silence, still logged (FR15/FR8)
        state.last_checked_at = now
        write_call_log(ticker, new_verdict, alert_type=NULL, alerted=False)
        continue

    # change -> immediate alert, no cooldown (FR7)
    write_call_log(ticker, new_verdict, alert_type="change", alerted=True)
    send_push(ticker, new_verdict, rationale, kind="change")   # "Changed to X", topic per market
    state.current_verdict = new_verdict
    state.last_checked_at = now
```

Consequences (stated plainly): a change **to Hold** still alerts (a weakening Buy is a signal); there is
**no frequency cap** (choppy day pushes every flip — accepted, §2 item 4); **every check logs** (FR15),
including no-change and cold-start rows with `alerted=false`. A standing actionable verdict at cold start
is **silent until it crosses** (load-bearing #2) — this is why NSE go-live did not dump 10 alerts.

Daily discovery (`run_discovery.py`) runs the sourcing/prefilter (§4.3) → one batched AI call → logs every
candidate as `label='new-candidate'`, `alert_type=null`, pushing only `Buy` not flagged within 7 days.
Ingest skips are logged the same way (FR15).

---

## 7. Non-functional design

- **7.1 Cost (NFR1):** public repo → unlimited free Actions minutes; secrets in Actions secrets +
  Supabase Vault; Supabase free tier; Gemini Flash / ntfy / GitHub Pages all $0. One batched AI call per
  run keeps under the free-tier daily cap. Total ≈ $0/month.
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
  hourly-watchlist.yml   # workflow_dispatch only; concurrency group; + shadow step (§13)
  daily-discovery.yml    # workflow_dispatch only; concurrency group
  publish-prices.yml     # writes pages/prices.json (CORS fallback, §11)
scripts/
  config.py              # market hours/gates, model Variables, discovery gates, shadow vars — all tunables
  ingest.py              # yfinance wrapper; market-agnostic; headline filter; session-aware price/vol
  prefilter.py           # Yahoo live screener + quality gates + signals + funnel; region-aware
  ai_judge.py            # Gemini batched judge_batch(models=...); BATCH_SYSTEM_PROMPT; schema + confidence
  state.py               # Supabase read/write; single-rule change machine; _snapshot()
  notify.py              # ntfy dispatch (provider-agnostic); per-market topic + timestamp
  textutil.py            # shared clip()
  run_hourly.py          # hourly watchlist orchestrator (per-market gate) — thin entry point
  run_discovery.py       # daily discovery orchestrator (region-aware) — thin entry point
  publish_prices.py      # fetch watchlist prices, write pages/prices.json — thin entry point
  shadow.py              # SHADOW pilot: position-aware prompt variant + judge_batch_shadow (§13)
  run_shadow.py          # SHADOW pilot orchestrator — thin entry point (§13)
sql/
  scheduler_pgcron.sql, phase5_monitoring.sql, dashboard_latest_call_view.sql,
  shadow_call_log_migration.sql (§13)
pages/
  detail.html, dashboard.html, prices.json
```

Contracts a dev/QA team builds against: the `data_snapshot` jsonb shape (§5), the `judge_batch()` JSON
array contract (§4.4), the single-rule state machine (§6), the config surface (§10). Entry points contain
no logic; externals are reached through module functions for substitutability in tests.

---

## 9. Configuration surface (tunables — the hardcoding-audit baseline)

All user-tunable values live in `scripts/config.py`, read from environment / GitHub Actions secrets &
Variables; nothing sensitive hardcoded. This mirrors `docs/requirements.md §11` (the reviewer's audit
baseline). Core: `GEMINI_MODEL`/`_BACKUP`, `NSE_GEMINI_MODEL`/`_BACKUP`, `DISCOVERY_GEMINI_MODEL`/`_BACKUP`,
`GEMINI_TIMEOUT_MS` (180000), `GEMINI_MAX_RETRIES` (3), `GEMINI_RETRY_BASE_MS` (10000), `NTFY_TOPIC`,
`NSE_NTFY_TOPIC` (falls back to `NTFY_TOPIC`), `DETAIL_PAGE_BASE`, `ALERTS_ENABLED` (false), `FORCE_RUN`
(false), `MIN_HISTORY_ROWS` (21), `YF_PACING_SECONDS` (2), `YF_BACKOFF_SECONDS` (10),
`MARKET_OPEN`/`CLOSE` (09:30/16:00 ET), `NSE_MARKET_OPEN`/`CLOSE` (09:15/15:30 IST),
`RUNTIME_CLOSE_GRACE_MIN` (10). Discovery: the `DISCOVERY_*` gate/signal/shortlist/cooldown keys (§4.3).
Dashboard auto-refresh interval is build-time config (FR22). Shadow: see §13.5. **The dashboard
auto-refresh interval and all discovery thresholds are tunables, not requirements — no tunable may live
only in code.**

---

## 10. Detail page & dashboard rendering authority

Detail page: §4.7. Dashboard (FR19–FR23): static GitHub Pages page, same host as the detail page,
**client-side SHA-256 passcode gate** (FR19, obfuscation-not-security, accepted for read-only RLS-scoped
data). Two reads per refresh cycle: (1) **live price** from server-published `pages/prices.json` read via
a relative URL (same-origin) — Yahoo is browser-CORS-blocked, §11; "prices updated Ns ago" keys off the
snapshot's own `generated_at` (honest data age, FR21/Decision #18); (2) **last-run data** from
`latest_call_per_ticker` via the anon key — **not** filtered on `alerted`, so the dashboard shows what
the system last *thought*. Tickers grouped **US & Canada** / **India (NSE)** (FR20); held vs watch-only
by badge (text+icon, not color alone). Last-run columns are **absent from the DOM** until ≥1 `call_log`
row exists (FR21). Auto-refresh on a **configurable** timer (FR22). Timestamps client-rendered, device +
IST (FR23). Anon key scoped to `call_log` + `watchlist` only, read-only. Full layout/copy authority:
`requirements_docs/stock-advisor-ui-handoff-v3-spec.md` (v4).

---

## 11. Browser-CORS constraint (Decision #18)

Yahoo's `v8/finance/chart` returns HTTP 200 server-side but carries no `Access-Control-Allow-Origin`
header; a headless-Chromium `fetch()` from a foreign origin fails for all three markets (Yahoo CORS-gates
selectively, `vary: Origin`). Consequence: the dashboard cannot fetch live prices client-side.
`publish-prices.yml` fetches prices server-side on the market cadence and commits `pages/prices.json`
(`{generated_at, prices: {ticker: {price, chg, market, currency}}}`), read same-origin by the dashboard.
Accepted freshness tradeoff: "live" price is "as of last publish" (~30-min cadence), matching NFR4.

---

## 12. Known limitations (recorded, not resolved)

Carried from `SD.md §11` — active watch items, not defects:
- **`confidence` field has no consumer** — requested, validated, persisted, surfaced on cards, but no
  push/alert/suppression logic reads it. Intended future use is push-gating; not built.
- **Schema-enforcement's effect on parse-retry rate is unmeasured** — expected to cut the fail-safe path;
  confirm against live `parse_status` distribution.
- **Supabase single point of failure (§2 item 6, NFR2)** — scheduler + monitor both in pg_cron; an
  out-of-band uptime ping is the unbuilt mitigation.
- **RPD sustainability** — a standing ops note (not the fallback story, which was timeout/503).
  Manageable by design (configurable per-market models, separate quota buckets, tracked tokens).
- **First live NSE close-slot run with the runtime grace, and ca/in volume screens, not yet observed.**
- **Shadow pilot has no committed evaluation method (FR31)** — see §13.6.

---

## 13. Shadow wallet pilot — as-built (FR24–FR31, NFR5) — EXPERIMENTAL / non-production

> **Status: shipped but non-production.** This section documents undocumented code that pm formalized
> into requirements FR24–FR31 / NFR5 during the adoption pass. It is **outside core v1 scope** and, by
> design, invisible to production. Files: `scripts/shadow.py`, `scripts/run_shadow.py`,
> `sql/shadow_call_log_migration.sql`, shadow vars in `scripts/config.py`, and the shadow step in
> `.github/workflows/hourly-watchlist.yml`.

### 13.1 Purpose & scope (FR24)
A parallel AI verdict track producing an independent Buy/Sell/Hold verdict per **US/CA (TSX) watchlist
ticker only** (NSE excluded, `US_CA_MARKETS = {"US", "TSX"}`), using a **position-aware** prompt variant.
Sole purpose: A/B test whether position-awareness changes verdict quality/behavior vs production's
current watch-only-style prompt. It reuses production's model-call machinery so the position-awareness
variable is isolated.

### 13.2 Prompt variant (FR24, FR25 — inline Python, no separate file)
`shadow.SHADOW_SYSTEM_PROMPT` = production's `ai_judge.BATCH_SYSTEM_PROMPT` **verbatim** + an appended
position-awareness addendum. The addendum tells the model each stock carries a `Current shadow position:
HOLDING at <price> since <date>` or `FLAT` line, to treat HOLDING as HELD and FLAT as WATCH-ONLY for the
verdict rubric, and — the load-bearing constraint — **a Sell on a HOLDING name must cite the specific
reversal-since-entry** (a concrete thesis change, not a fresh independent read). It deliberately does
**not** suppress Buy-while-holding or Sell-while-flat at the prompt level (the wallet-walk ignores those;
suppressing them would pollute the verdict-count comparison). Everything else — headlines, fundamentals,
confidence rubric, JSON contract, `temperature=0.2`, `response_schema` — is byte-identical to production.
`shadow._shadow_ticker_block` reproduces `ai_judge._ticker_block`'s market-data lines exactly (reusing the
same `ai_judge` helpers), differing only in the two position lines. **The prompt is inline Python; there
is no `shadow_pilot_prompt.md` file.**

`judge_batch_shadow()` mirrors `ai_judge.judge_batch()`'s orchestration — single batched call, one retry
on a bad reply, fail-safe-to-Hold on hard failure, the **same model try-order** (`GEMINI_MODEL`/`_BACKUP`
via `ai_judge._models_to_try(None)`), the **same** `ai_judge._generate` transport with the same
timeout/backoff/jitter, and the same `_parse_batch` — shared config and shared functions, never copies.

### 13.3 Orchestration & wallet-walk (`run_shadow.py`) (FR25, FR26)
Each cycle (all-or-nothing):
1. **Kill switch** (`config.SHADOW_ENABLED`) + the **same US/TSX market-open gate production uses**
   (`config.is_market_open` or `FORCE_RUN`). Closed and not forced → no-op.
2. **Same-data reuse (FR26):** `_latest_production_snapshots()` reads THIS cycle's already-written
   production `call_log` `label='watchlist'` rows for the US/CA tickers, latest-per-ticker within a
   `SHADOW_SNAPSHOT_LOOKBACK_MIN` (default 20 min) window, and rebuilds each ticker's market data from the
   persisted `data_snapshot` (`_usable_market_data`). It **reuses** production's snapshot, never
   re-fetches Yahoo. The 20-min lookback **must stay under the 30-min dispatch cadence** so it can never
   pick up a prior cycle's snapshot.
3. **Wallet-walk (FR25):** `_derive_shadow_positions()` derives each ticker's simulated position **purely
   from `call_log_shadow`'s own history** (ordered oldest→newest): a `Buy` flips flat→holding (recording
   entry price from the snapshot and entry date from the row timestamp), a `Sell` flips holding→flat, a
   `Hold` (including every fail-safe Hold) is a no-op. Empty history → flat. Never reads real `call_log`
   for position. The going-in position (state + entry price + entry date) is recorded per row for
   auditability.
4. **One batched position-aware call** (`shadow.judge_batch_shadow`).
5. **One atomic INSERT** of all rows (judged + skip-trace rows) into `call_log_shadow` — fully recorded
   or not at all, so a mid-write death can't corrupt derived position state. Unusable/absent production
   rows are written as queryable `parse_status='no_data'` skip rows (a Hold → no-op in the walk), never
   silent; a cycle with no usable production data at all is logged as a gap and skipped (self-heals next
   cycle — missed cycles are never backfilled).

### 13.4 Isolation — three independent belts (FR27, FR28, FR29, NFR5)
- **Never alerts (FR28):** `run_shadow.py` / `shadow.py` do not import or invoke `notify` at all; every
  row is `alert_type=None`, `alerted=False`. The workflow step passes **no** `NTFY_*` env vars.
- **Isolated storage, no anon/dashboard read path (FR27):** writes only to `call_log_shadow`, never
  `call_log`. That table has **RLS enabled with NO policy and NO grant** to anon/authenticated — only the
  server **secret key** (which bypasses RLS) can read/write it. The publishable/anon key sees nothing.
  There is no read path from the shadow table into the dashboard, GitHub Pages output, or any
  notification channel.
- **Cannot fail production (FR29):** three belts — (1) the shadow step runs strictly **after**
  production's step in the same workflow, as a separate process; production has already finished and
  written its rows before shadow starts, so there is no code path back to it; (2) the workflow step is
  **`continue-on-error: true`**; (3) `run_shadow.main()` wraps everything in a top-level try/except and
  always exits 0. Real holdings/cost-basis never leak into shadow rows — position is derived solely from
  `call_log_shadow`.

### 13.5 Storage schema (`sql/shadow_call_log_migration.sql`)
`call_log_shadow` is a **structural mirror of `call_log`** (same columns/types/checks/defaults) plus two
shadow-only columns: `prompt_variant` (text, default `'position_aware_v1'` — lets future variants coexist
with no migration) and `shadow_position_state` (jsonb: `{state: holding|flat, entry_price, entry_date}`,
the position going into the call, derived only from this table). Same indexes as `call_log`
(ticker/timestamp, label/timestamp). **RLS enabled, no permissive policy, no anon/authenticated grant.**

### 13.6 Configuration & accepted risk (FR30, NFR5)
| Key | Default | Purpose |
|---|---|---|
| `SHADOW_ENABLED` | **`true` — fail-OPEN (accepted risk, FR30/NFR5)** | Kill switch, checked both at the workflow step (`if: vars.SHADOW_ENABLED != 'false'`) and again in `config.py`/`run_shadow.py`. **Only the literal string `false` disables it**; an unset/empty/mistyped Variable *keeps the pilot running*. |
| `SHADOW_PROMPT_VARIANT` | `position_aware_v1` | Tag written to `call_log_shadow.prompt_variant`. |
| `SHADOW_SNAPSHOT_LOOKBACK_MIN` | `20` | Lookback to reuse the same-cycle production snapshot; **must stay under the 30-min cadence** (FR26). |

**Accepted risk, recorded (FR30, NFR5, load-bearing #10):** the fail-open default is deliberate (toggling
off is a one-Variable opt-out) but means a deleted/mistyped Variable *silently keeps the pilot running*.
Acceptable only while the three isolation guarantees (FR27–FR29) hold; if any is weakened, the fail-open
default must be revisited.

### 13.7 Open gap — FR31 [REQUIREMENTS-GAP], BLOCKS graduation
**There is no committed, reproducible evaluation method in the repo.** The SQL migration's own comments
reference a "wallet-sim recursive-CTE walk" and a "wallet-sim harness" that **do not exist anywhere in the
codebase** (verified across `sql/`); they are described as living only in the ad hoc Supabase SQL editor.
So there is no reproducible way to run the two-week shadow-vs-production evaluation the pilot exists for.
Recorded here exactly as `SD.md` records other known limits (e.g. §4.8's monitor single-point-of-failure)
— **this design does not attempt to solve it.** Per FR31, before the pilot can graduate a defined,
committed, reproducible evaluation method (the wallet-sim walk/harness, versioned in the repo) must exist;
owner is dev (harness) with QA (reproducibility). Until then the pilot cannot be assessed and must not
graduate. See the increment plan (§14).

---

## 14. Increment plan

This is an **adoption pass over an already-live system** — Phases 0–7 shipped weeks ago and this design
is descriptive, so there is **no new-build increment plan**. Every FR1–FR30 / NFR1–NFR5 requirement is
already delivered in code (traceability in §§4–13). The only open, un-delivered item is:

| INC | Requirement | Status | Notes |
|---|---|---|---|
| INC-1 (future, not yet scheduled) | **FR31** — committed, reproducible shadow evaluation harness | **OPEN GAP** — not designed here | Detailed design and vertical-slice increment deferred to a later prioritization decision (user call whether the shadow pilot graduates or is retired, per `docs/requirements.md` open item). When scheduled: a versioned SQL/script wallet-sim walk over `call_log_shadow` + a reproducible shadow-vs-production comparison, owned by dev, verified reproducible by QA. It is a self-contained analysis artifact reading an existing table — no change to any FR1–FR30 behavior. |

No other increments are open. If the user requests the FR31 harness be built, this section gets a proper
vertical-slice increment then.

---

## 15. Requirement coverage map

| Requirement | Where satisfied |
|---|---|
| FR1, FR3 | §4.2, §5 `watchlist` |
| FR2, FR11 | §4.4 prompt (held block), §4.7 detail position block, §5 `holdings`/`position` |
| FR4, FR5 | §4.3 prefilter + signals + Buy-only push, §6 discovery flow |
| FR6 | §4.1 scheduler, §6 30-min cadence |
| FR7, FR8 | §0 #1/#2, §6 single-rule change detector |
| FR9, FR10 | §4.4 AI judgment (no fixed rules/style), §0 #8 fail-safe |
| FR12, FR13, FR14 | §4.6 ntfy, §4.7 detail page |
| FR15, FR16 | §5 `call_log`, §6 (every check logged, incl. no-change/cold-start/skip) |
| FR17 | §4.1 gates, §7.5 skip-with-log |
| FR18 | §4.6 per-market topic routing |
| FR19–FR22 | §10 dashboard, §11 CORS/prices.json |
| FR23 | §4.6 (notifications), §4.7/§10 (client dual-tz), §5 UTC contract |
| NFR1 | §4.4 batched call, §7.1 cost |
| NFR2 | §4.1 gate authority, §4.8 dead-man monitor |
| NFR3 | §4.6, §4.7, §7.2 |
| NFR4 | §4.1 cadence, §11 freshness posture |
| FR24–FR30, NFR5 | §13.1–§13.6 shadow pilot |
| **FR31** | **§13.7, §14 — OPEN GAP, not delivered** |

**Coverage:** FR1–FR30 and NFR1–NFR5 are covered as-built. **FR31 is the single uncovered requirement**
(no committed evaluation harness — documented, not designed).
</content>
</invoke>
