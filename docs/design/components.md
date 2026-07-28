# Components

Part of `docs/design.md`'s module split (2026-07-25, REV-024). See `docs/design.md` for the index, module
map, §0 load-bearing decisions, and the requirement coverage map — read that first for orientation.
Section numbers below (§4, subsections 4.1–4.8) are unchanged from the pre-split monolithic `docs/design.md`.

---

## 4. Components

### 4.1 Scheduler — Supabase pg_cron → GitHub `workflow_dispatch` (FR6, FR17, NFR2)

- Both workflows are **`workflow_dispatch`-only** (native `schedule:` removed — GitHub's shared
  scheduler dropped ~13 of ~16 daily ticks, silently, the worst failure mode for a don't-miss-things
  system).
- `pg_cron` holds the schedule and calls a `SECURITY DEFINER` function
  `dispatch_github_workflow(workflow_file, inputs)` that reads a GitHub PAT from **Supabase Vault** and
  POSTs the dispatch via **`pg_net`**.
- **Load-bearing safety principle (`docs/design.md` §0, load-bearing #4):** the schedule fires more often
  than needed; the **runtime market gate is the real authority** on whether work happens.
- **ET/IST-aware, DST-correct gating.** `dispatch_watchlist_if_open()` gates US/TSX on
  `(now() at time zone 'America/New_York')::time between '09:30' and '16:05'` + weekday;
  `dispatch_watchlist_nse_if_open()` gates NSE on the IST session `09:15`–`15:35`. The wide
  `*/30 13-21 UTC` (US/TSX) and `*/30 3-10 UTC` (NSE) crons are DST supersets trimmed by the gates.
  The **16:05 / 15:35 upper bounds are close + 5 min** — deliberate jitter slack (`docs/design.md` §0,
  load-bearing #9).
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

**REV-048, 2026-07-28 — market-session constants duplication, made visible (not merged).** The open
bounds, base close bounds, monitor grace windows, and the staleness threshold each exist independently in
both the Python and SQL layers. **This is not a request to merge the two close bounds** — load-bearing
decision #9 (`docs/design.md` §0) deliberately keeps SQL at close+5 and Python at close+
`RUNTIME_CLOSE_GRACE_MIN`, and that split is sound and stays as-is. The gap REV-048 flags is narrower:
changing `MARKET_OPEN`/`MARKET_CLOSE` in `scripts/config.py` (a documented tunable, `requirements.md` §10)
would leave the SQL sites below silently disagreeing, since nothing currently reads `config.py`'s value
into SQL or vice versa. Documented here as one linked table so the duplication is trackable, not merged:

| Constant | Python (`scripts/config.py`) | SQL |
|---|---|---|
| US/TSX open | `MARKET_OPEN` (09:30 ET) | `dispatch_watchlist_if_open()`, `t >= '09:30'` (`scheduler_pgcron.sql:279`) |
| US/TSX base close | `MARKET_CLOSE` (16:00 ET) | `dispatch_watchlist_if_open()`, `t <= '16:05'` — close+5 (`scheduler_pgcron.sql:279`) |
| NSE open | `NSE_MARKET_OPEN` (09:15 IST) | `dispatch_watchlist_nse_if_open()`, `t >= '09:15'` (`scheduler_pgcron.sql:132`) |
| NSE base close | `NSE_MARKET_CLOSE` (15:30 IST) | `dispatch_watchlist_nse_if_open()`, `t <= '15:35'` — close+5 (`scheduler_pgcron.sql:132`) |
| Monitor grace after US/TSX open | n/a (Python has no monitor) | `check_pipeline_health()`, `et >= '10:15'` (`phase5_monitoring.sql:125`) |
| Monitor grace after NSE open | n/a | `check_pipeline_health()`, `ist >= '10:00'` (`phase5_monitoring.sql:153`) |
| Monitor watchlist/publish-prices staleness threshold | n/a | `interval '70 minutes'`, three copies (`phase5_monitoring.sql:129,157,229`) |
| Runtime close grace (execution-time defense-in-depth) | `RUNTIME_CLOSE_GRACE_MIN` (10 min), added to `MARKET_CLOSE`/`NSE_MARKET_CLOSE` in `is_market_open()`/`is_nse_open()` | n/a (SQL's own +5 jitter slack is separate, load-bearing #9) |

Suggested (not built in this pass, qa's to schedule): a cheap test that reads `sql/scheduler_pgcron.sql`
and `sql/phase5_monitoring.sql` as text and asserts their literal time constants match `config.py`'s
`MARKET_OPEN`/`NSE_MARKET_OPEN` (open bounds only — the close-bound split is intentional and the test
should not flag it) — the suite already parses workflow YAML in `docs/handoff.md`'s verify block, so the
pattern exists.

### 4.2 Data ingestion — `yfinance` (FR1, FR9, non-functional-ops.md §7 data sources)

Single wrapper module (`ingest.py`) used by all workflows. Pulls price/volume, basic fundamentals
(`tk.info`), and built-in news (`Ticker.news`) — one data dependency, no separate news vendor. US tickers
are bare, TSX use `.TO`, NSE use `.NS`. **Market-agnostic:** keys off the ticker suffix and the yfinance
`exchange` field, so adding a market is a config concern, not an ingestion rewrite. `ingest._market_for`
resolves per-ticker market, carried on the `data` dict and persisted (`data-and-flow.md` §5).

Two data-quality behaviors (v18/v20, feed the prompt correctly):
- **Headline relevance filter** — `_headlines()` drops titles mentioning neither the company name
  (distinctive tokens; generic words stop-listed) nor the ticker, before the 5-title cap; **fail-open**
  when no company name is available. Dropped counts go to `notes`.
- **Session-aware price/volume** — `_session_state()` (strict session bounds, *not* the
  grace-extended dispatch gates) flags `session_live` and pro-rates `volume_vs_avg` by elapsed session
  fraction (`n/a` in the first 10%). Prompt renders "live price (session in progress)"/"today so far"
  vs "last close"/"1d" accordingly. Both flags persist to `data_snapshot`.

**Skip-with-log:** a ticker returning no usable data is skipped, never fatal (FR17, `non-functional-ops.md`
§7.5). New listings (<~20 sessions) are *not* skipped — compute what history supports, mark 20d fields
`n/a (newly listed)`.

**REV-043 design call, 2026-07-28 — a narrow price-only path for `publish_prices.py`.**
`publish_prices.py` (the */30 dashboard-snapshot publisher, `non-functional-ops.md` §8) currently calls
the same `get_market_data()` every AI-judgment path uses, but only reads four fields
(`price`/`pct_change_1d`/`market`/`fundamentals.currency`) — `get_market_data()` still does the full
3-month history fetch, `tk.fast_info`, the full `tk.info` scrape, and `tk.news` + headline filtering for
every one of those calls, roughly four Yahoo requests per ticker where one would do, on ~32 dispatch slots
a weekday across both sessions (`sql/scheduler_pgcron.sql`'s `publish-prices` cron). That's avoidable load
against an unofficial API this pipeline has already been rate-limited by (issue #1), and it shares the
`YF_PACING_SECONDS` budget with the watchlist runs that actually need the AI-facing data.
**Decision: add `ingest.get_price_only(ticker) -> dict`** — `period='5d'` history (enough for `price` and
`pct_change_1d`) plus `tk.fast_info` for `market`/currency context, **no `tk.info` scrape, no `tk.news`
call**. `publish_prices.py` switches to this function; `get_market_data()` is **untouched** and remains
the only path the AI-judgment code (`run_hourly.py`/`run_discovery.py`) uses — this is reuse at the wrong
grain being narrowed, not a second ingestion module. Implementation (the actual function body, field
mapping, and yfinance call shape) is dev's at INC-time; this is a design decision, not code. Not gated
behind any of INC-3–INC-7 — an independent live-system fix `pm`/`release` can schedule separately.

**Related, not addressed here (pm question, not a design gap):** `publish_prices.py` is currently the only
dispatch path with no market-open gate (`sql/scheduler_pgcron.sql:152`'s `publish-prices` cron fires
`*/30 3-10,13-21` with no `dispatch_..._if_open()` gate wrapping it), so it also fires through the
11:00–13:00 UTC gap between the NSE and US/TSX sessions. Worth confirming with pm whether that's
intentional; not changed by this fix.

### 4.3 Candidate sourcing & prefilter — discovery only (FR4, FR5, Decisions #4/#9/#14/#16)

`prefilter.py` sources candidates from **Yahoo's live server-side screener** (not a maintained universe —
`docs/design.md` §0, load-bearing #7) and applies quality gates + signals locally:
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

- **Model:** Gemini Flash on Google's **paid tier**. Real operation runs the **`gemini-2.5-flash` family
  across the board** (`gemini-3.5-flash`/`gemini-3.1-flash-lite` showed stability issues). **Model names
  are configurable repo Variables, never hardcoded:** `GEMINI_MODEL` / `GEMINI_MODEL_BACKUP` (watchlist),
  `NSE_GEMINI_MODEL` / `_BACKUP` (NSE watchlist), `DISCOVERY_GEMINI_MODEL` / `_BACKUP` (discovery). Wired
  through `judge_batch(models=...)`. **Model-default correction (already applied):** the literal defaults
  in `scripts/config.py` (and the workflow fallbacks in `hourly-watchlist.yml`) were updated from the 3.x
  strings to `gemini-2.5-flash` / `gemini-2.5-flash-lite` to match real operation. This fix was originally
  bundled into the now-retired shadow-track INC-1 (see `docs/design.md`'s "Retired: shadow-pilot tracks"
  note) but is independent, production-facing, and remains in effect after the shadow-track removal.
- **Dual-model fallback:** each call attempts primary, falls back to backup; the two draw from separate
  per-model buckets (a resilience/isolation belt; no longer a free-tier-quota necessity on paid tier).
- **One batched call per run, not per ticker (`docs/design.md` §0, load-bearing #6):** the whole open-market
  group is judged in a single `judge_batch()` call returning a JSON array (one object per ticker). Each
  per-market group gets its own batched call with its own model try-order. On paid tier this keeps call
  volume — and thus spend — low, holding NFR1's $0–15/mo cap.
- Output is **strict JSON, schema-enforced**, validated and retried as a backstop (below).

**Prompt specification (the actual product).** `BATCH_SYSTEM_PROMPT` is the production system prompt.
Load-bearing content:
- **Verdict definitions** made explicit for HELD vs WATCH-ONLY: **Buy** = open/add now; **Sell** =
  reduce/exit now, judged on forward prospects **not** anchored to cost basis; **Hold** = no actionable
  change, the default and most common output. The bias toward Hold is the brake against manufacturing
  action from noise (`docs/design.md` §0, load-bearing #8).
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

> **The prompt is inline Python** in `ai_judge.py` (`BATCH_SYSTEM_PROMPT`). There is **no** separate
> prompt file. (The former shadow-variant prompt, `shadow.py`'s `SHADOW_SYSTEM_PROMPT`, was removed with
> the shadow-track retirement — see `docs/design.md`'s "Retired: shadow-pilot tracks" note.)

**Timeout & fallback (`docs/design.md` §0, load-bearing #3):** `GEMINI_TIMEOUT_MS` default 180,000 ms. On
any fallback the **real** exception (timeout / 503 / parse / genuine 429) is captured to
`data_snapshot.fallback_from` + a run warning — the log is the source of truth for "why did it fall back."

**Parse & retry (`docs/design.md` §0, load-bearing #8):** (1) request schema-enforced JSON, parse; (2) on
failure retry once with a terse "reply with ONLY the JSON array"; (3) on second failure **log, treat
verdict as `Hold` (no alert), move on** — a fail-safe Hold carries `confidence: null`, never fabricated.
(4) every raw response (incl. failures) is written to `data_snapshot`.

**Confidence (persisted, not yet consumed):** the model's self-rated `high`/`medium`/`low` is validated,
persisted in `data_snapshot.confidence`, surfaced on the cards, but **read by no gating logic today**
(known limitation, `frontend.md` §12).

**Token accounting (`docs/design.md` §0, load-bearing #6):** `data_snapshot.tokens {prompt, output,
thoughts, total}` is a **per-batch total replicated onto every row** — dedup per run, never sum per row.

### 4.5 State & persistence — Supabase (FR14, FR15)

All durable state in Postgres (schema `data-and-flow.md` §5). Chosen over a flat file because the detail
page (FR14) queries a specific log row directly. Supabase also hosts the scheduler and watchdog (§4.1,
§4.8, above).

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

A passive heartbeat no one reads is not a monitor (`docs/design.md` §0, load-bearing #5). Design:
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

**Known limit (`foundations.md` §2 item 6):** the monitor lives in the same Supabase pg_cron it watches —
it cannot catch a total Supabase/pg_cron outage. An out-of-band uptime ping is the documented, unbuilt
mitigation.
