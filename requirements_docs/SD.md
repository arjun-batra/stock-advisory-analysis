# Stock Advisory Agent — Solution Design (v14)

**Owner:** Arjun (solo build reference)
**Status:** Phases 0–7 all live. **v14 reflects the Part-1 issue cleanup + Phase 6 (NSE) + Phase 7
(dashboard) build**, executed 2026-07-01 across PRs #19–#26. All five genuine gaps from the v12/v13
review (**#13–#17**) are fixed and merged. Phase 6 (India NSE, §12) is live — 10 tickers, per-market
gate, separate ntfy topic, region-aware discovery — activated via a deliberate dry-run → alerts-on
staged go-live so cold-start silence (§6.3) never risked an alert dump. Phase 7 (dashboard, §13) is
live, but **not as originally designed**: issue #18's CORS smoke test proved the browser cannot fetch
Yahoo prices directly (blocked for all three markets, confirmed both by header inspection and a real
in-browser fetch), so the live-price read was reworked mid-build to a server-published `prices.json`
read same-origin — a real architecture change to §13, ratified by Arjun directly (not inferred), and
documented as such below. Two Phase-6 D5 defaults (NSE discovery INR thresholds, NSE-only filtering)
were flagged for ratification during the build and were **confirmed by Arjun on 2026-07-01** — see §12.
**Companion docs:** `stock-advisory-agent-requirements.md` (**v4 — source of truth**);
`stock-advisor-ui-handoff-v3-spec.md` (**v3 — rendering authority**);
`stock-advisory-agent-solution-design-history.md` (change history). **All four docs now live in the
repo** at `requirements_docs/`, committed 2026-07-01 so Claude Code sessions can read them directly.

> **Change history moved out (token hygiene).** The full v2–v13 dated change-note stack lives in
> `stock-advisory-agent-solution-design-history.md`. This working document carries the **current-state**
> design only. The handful of decisions whose *rationale* is load-bearing — the ones a future reader
> could otherwise undo by accident — are distilled in §0 below.

---

## 0. Load-bearing decisions (read before changing anything)

These are the "why it is this way" calls that are easy to reverse without realizing the cost. Full
provenance is in the history file; the short version:

1. **Single-rule alerting (issue #11, §6.3).** Any verdict change → immediate alert; no change →
   silence. No cooldown, no debounce, no 7-day reminder (FR7 retired). The old cooldown/reminder added
   state that wasn't earning its keep on a single-user push tool. Accepted cost: alert bursts on a
   choppy day. **Don't re-add a cooldown/debounce without a real, observed volume problem.**
2. **Signal on crossings, not standing states (§2 item 4, §6.3).** A standing Buy/Sell that never
   changes is silent by design — there is no bootstrap re-announce. A logged change is one threshold
   crossing, not proof of a durable signal; read the track record that way.
3. **Gemini fallbacks were never quota/RPD (§2 item 3, §4.4a).** The real cause was a client-side
   timeout firing on slow-but-valid (already token-billed) responses, plus occasional 503s — fixed
   with `GEMINI_TIMEOUT_MS=180s`. The real reason is logged in `fallback_from`; **don't call fallbacks
   "rate-limiting."**
4. **Supabase pg_cron is the clock, not GitHub cron (§4.1).** GitHub's shared scheduler silently
   dropped most ticks. The **runtime market gate, not the schedule, is the authority** on whether work
   happens — the schedule fires loosely and the ET gate trims it. Never trust the schedule to mean
   "market open."
5. **Reliability is an active dead-man monitor (§4.8, NFR2).** It must surface a run that *never
   triggers*, not only one that runs and fails. Known limit: it lives in the same pg_cron it watches
   (single point of failure, §2 item 6); an out-of-band ping is the unbuilt mitigation.
6. **One batched AI call per run, not per ticker (§4.4, §4.4a).** This is what keeps the system under
   the free-tier daily request cap. `data_snapshot.tokens` is a **per-batch total replicated on every
   row** — dedup per run, never sum per row.
7. **Discovery uses Yahoo's live screener, not a maintained universe (§4.3).** `candidate_universe`
   is vestigial — there is no seed/quarterly-refresh ownership burden. Don't reintroduce one.
8. **AI fails safe to Hold (§4.4a, §6.3).** A parse/API failure logs a fail-safe Hold, and the
   non-reading guard stops it from being read as a real change — so a bug can only ever *miss* a
   signal, never *fabricate* one. Keep that guard.
## 1. Purpose of This Document

The requirements doc closes the product questions. This doc closes the engineering ones — how the
system is actually built, what runs where, what persists, and what a dev/test team needs to execute
without guessing. Three architecture decisions were confirmed before v1 and remain locked:

| Decision | Choice |
|---|---|
| Candidate discovery method | Prefiltered universe (movers/volume/earnings) → AI judges shortlist |
| AI model | Gemini Flash, free tier (model names now configurable, §4.4) |
| State persistence | Supabase (Postgres) — now also the **scheduler and the watchdog** (§4.1, §4.8) |

A v6-era shift worth stating up front: Supabase has grown from "the database" into the **control
plane** — it persists state, triggers both workflows (pg_cron), and runs the health monitor. That
concentration is deliberate (one reliable mechanism beat GitHub's flaky scheduler) but it makes
Supabase a single point of failure for the whole trigger-and-watchdog path — see §2, item 6.

---

## 2. Accepted Risks (documented, not hidden)

1. **Gemini free tier trains on your prompts.** Google's free-tier terms allow using submitted
   prompts/responses to improve their models — paid tier and Vertex AI don't. This system sends your
   watchlist, holdings, and cost basis through that pipeline. Accepted for v1 given the $0–15/month
   budget; the swap to Claude Haiku via the Anthropic API is a small, isolated change (§4.4).
2. **Yahoo Finance's API is unofficial** — no SLA, no guarantee TSX (or NSE, §12) fundamentals stay
   complete. Day-one smoke test is mandatory (§9, Phase 0) before anything builds on top of it.
3. **Free-tier quotas move — but the observed fallbacks were never quota (corrected v7).** Google
   tightened Gemini free-tier limits twice in the past year; re-verify model names and RPM/RPD against
   live docs at build time. **What the doc previously implied — that fallbacks were RPD/quota — was
   wrong.** Live captured data (issue #10) shows the actual fallback cause was a **503 high-demand**
   response, and the original *recurring* fallbacks were a **client-side timeout firing on slow-but-
   valid responses** — not 429/RPD exhaustion at all. The 180s timeout fix (§4.4a) was the correct
   remedy; only the attribution was off. The real exception is now captured per call in
   `call_log.data_snapshot.fallback_from`, so "why did it fall back" is read from the log, never guessed.
   Actual RPD *sustainability* is a separate standing ops note, not this fallback story — see §11.
4. **No spam control — verdict non-determinism surfaces directly as alerts (v6, issue #11).**
   Gemini's verdict isn't deterministic — the same data can return Buy on one run and Hold on the
   next. With the debounce (removed v3) **and now the 24h cooldown (removed v6)** both gone, every
   verdict change alerts immediately and **nothing caps the frequency.** On a choppy day, a verdict
   that oscillates Buy→Hold→Buy (whether from real volatility or model noise) pushes on *every* flip.
   This is the accepted cost of the single-rule design's simplicity (§6.3). The track record (§ success
   criterion in requirements) must be read with this in mind: a logged change is the model crossing a
   threshold once, not proof of a real signal. **Corollary (v7): the system signals on threshold
   *crossings*, not standing states** — a verdict that is actionable but unchanged (e.g. a standing Buy
   after cold start) is deliberately silent, because nothing crossed. If alert volume becomes a problem
   in practice, the documented re-adds are the "2 of last 3 runs agree" debounce or a minimal cooldown
   — both live in git history.
5. **NYSE/TSX holiday calendars diverge.** The two markets share trading *hours* but not *holidays*.
   The open-market gate is hours-and-weekday only (now per-market, §4.1/§6.1) and does not consult a
   per-exchange holiday calendar; a closed market's tickers fall through to skip-with-log (§7.5).
   Accepted over wiring a market-calendar library. (NSE, §12, adds a third holiday calendar — same
   posture.)
6. **Supabase is a single point of failure for trigger + watchdog (new, v6).** Scheduling (pg_cron
   dispatch) *and* monitoring (pg_cron health-monitor) both live in Supabase. If Supabase pg_cron
   stops, nothing dispatches **and** nothing warns that nothing dispatched — the dead-man monitor
   dies with the thing it's supposed to watch. Accepted for a single-user free-tier tool; the honest
   mitigation if this ever matters is an external uptime ping (e.g. a free cron-monitor hitting a
   heartbeat URL) as an out-of-band watcher. Noted, not built.
7. **Dashboard auth is constrained by a static host (new, v8).** The dashboard (§13) lives on GitHub
   Pages, which has **no server-side auth** — so access control can only be a client-side gate (a JS
   password prompt against a hashed value) or a host-level layer in front (e.g. Cloudflare Access).
   FR19 forbids unauthenticated public access; a JS gate is *obfuscation, not real security* (the data
   is reachable by anyone who reads the anon-key requests). Acceptable only because the data is
   informational and read-only (NFR3) and the anon key is RLS-scoped to two tables (§13). If the
   data sensitivity bar ever rises, Cloudflare Access (or moving the dashboard off a static host) is
   the real fix. The mechanism choice is a build-time decision (§13); the *constraint* is recorded here.
   **(Ratified v13: the JS-gate choice is now a Product decision — Requirements Decision Log #11 — not
   just an SD-side architecture call.)**
8. **Yahoo's price API is server-reachable but browser-CORS-blocked (new, v14, issue #18).** Confirmed
   by smoke test: `v8/finance/chart` returns `HTTP 200` with valid data when called from a GitHub Actions
   runner, but carries no `Access-Control-Allow-Origin` header, and a real headless-Chromium `fetch()`
   from a foreign origin fails outright for all three markets (US/TSX/NSE tested individually). This
   is a Yahoo-side property (confirmed via `vary: Origin`, meaning Yahoo *does* CORS-gate selectively —
   just not to arbitrary origins), not an artifact of the test environment. **Consequence:** the
   dashboard cannot fetch live prices client-side from Yahoo at all, in any environment. §13's original
   design assumed it could; §13 now reflects the corrected architecture (server-published `prices.json`,
   read same-origin). See §13 for the accepted freshness tradeoff this introduces.
---

## 3. High-Level Architecture

```mermaid
flowchart LR
    subgraph SBCTRL["Supabase — control plane"]
        CRON["pg_cron jobs"]
        NET["pg_net (HTTP)"]
        FN["dispatch_github_workflow()\ncheck_pipeline_health()"]
        DB[("Postgres state")]
    end
    subgraph GH["GitHub Actions (workflow_dispatch only)"]
        H["hourly-watchlist.yml"]
        D["daily-discovery.yml"]
        PP["publish-prices.yml"]
    end
    YF[("Yahoo Finance / yfinance")]
    GM["Gemini Flash API\n(primary + backup)"]
    NTFY["ntfy.sh"]
    PAGE["Detail Page — GitHub Pages"]
    DASH["Dashboard — GitHub Pages"]

    CRON --> FN
    FN --> NET
    NET -->|workflow_dispatch REST| H
    NET -->|workflow_dispatch REST| D
    NET -->|workflow_dispatch REST| PP
    CRON -->|health-monitor| FN
    FN -->|alerts| NTFY
    H --> YF
    D --> YF
    PP --> YF
    H --> GM
    D --> GM
    H --> DB
    D --> DB
    H --> NTFY
    D --> NTFY
    NTFY -->|tap-through link| PAGE
    PAGE -->|read-only, anon key| DB
    PP -->|commits pages/prices.json| DASH
    DASH -->|read-only, anon key| DB
```

The shape changed in v6: the trigger arrow no longer originates inside GitHub. **Supabase pg_cron
is the clock**; it calls GitHub's dispatch API over `pg_net`, and a third pg_cron job is the
watchdog. GitHub Actions is now purely an execution surface. **v14 adds `publish-prices.yml`** — a
third scheduled workflow that writes `pages/prices.json`, which the dashboard reads same-origin
instead of fetching Yahoo directly from the browser (§13, issue #18).

---

## 4. Components

### 4.1 Scheduler — Supabase pg_cron → GitHub `workflow_dispatch` (rewritten in v6)

**What changed and why.** v5 specified GitHub Actions native `schedule:` cron. In production that
proved unreliable to the point of breaking the product — GitHub's shared scheduler silently *drops*
scheduled events under load (observed: a `*/30` schedule executed roughly 3 of ~16 expected daily
ticks). Dropped ticks fail *silently*, which is the worst failure mode for a system whose whole job
is to not miss things.

**Current design (live):**
- Both workflows are **`workflow_dispatch`-only**; the native `schedule:` blocks are removed.
- Supabase **`pg_cron`** holds the schedule and calls a `SECURITY DEFINER` function
  `dispatch_github_workflow(workflow_file, inputs)` which reads a GitHub PAT from **Supabase Vault**
  and POSTs the dispatch via **`pg_net`**.
- This makes the *trigger* reliable. It does **not** make the trigger smart about market hours —
  and that distinction is the load-bearing safety principle, carried over verbatim from v5:
> **Never trust the schedule alone to mean "the market is open."** The schedule fires more often
> than strictly needed; the **runtime market gate is the real authority** on whether work happens.
> This is the single most common bug in scheduled trading scripts, and moving to a reliable
> scheduler does not retire the gate — it just means the gate now runs against a clock that actually
> ticks.

**ET-aware, DST-correct gating (live — issues #9, #12).** The gate/window math previously used fixed
UTC offsets, which couldn't track the ET market close across daylight-saving transitions — the symptom
was post-close no-op dispatches (#9) and a daily false "watchlist stalled" alert (#12). **Now shipped:**
- `public.dispatch_watchlist_if_open()` gates the watchlist dispatch on
  `(now() at time zone 'America/New_York')::time between '09:30' and '16:00'` **plus** a weekday check,
  then calls `dispatch_github_workflow('hourly-watchlist.yml')`. The watchlist-dispatch cron is
  re-pointed at this gate.
- The wide `*/30 13-21 UTC` cron **stays as the DST superset** — it fires more often than needed and
  the ET gate trims it down to the live session, so the schedule never has to be edited twice a year.
  This is the "schedule fires loosely, the gate is the authority" principle made concrete.
- Python `is_market_open()` **remains as execution-time defense-in-depth** — the dispatch gate and the
  runtime gate now agree, both computed in `America/New_York`. **All market-hour gating is computed in
  ET, never in fixed UTC offsets.** (§12 extends this to a per-market gate with a second IST window.)
- Migration `issue_9_12_et_aware_gating` + a `cron.alter_job` re-point; commits `07d10e7f`, `516cbba0`.
**Safe forced-test pattern (live — issue #7).** `FORCE_RUN=true` bypasses the market gate; if
`ALERTS_ENABLED=true` at the same time, it fires **real** ntfy pushes regardless of market hours (one
such test push was briefly mistaken for a defect). `is_market_open()` itself is correct. Now shipped:
`run_hourly` prints a **`[gate]` audit line** (`market_open`, `force_run`, `alerts`, and both UTC + ET
time) on every run, and the `FORCE_RUN` branch documents that `ALERTS_ENABLED=true` sends real pushes
off-hours. **Documented safe pattern: for any off-hours forced run, set `ALERTS_ENABLED=false`.**

`daily-discovery.yml` is dispatched once after US/TSX market close on the same mechanism (fixed 22:00
UTC — discovery is not ET-gated, see §4.8). **NSE (v14, live):** a second `nse-watchlist-dispatch` cron
(IST gate, `*/30 3-10`) and a second `discovery-dispatch-nse` cron (fixed 10:00 UTC, `region=in`) run
on the same mechanism — see §12.

### 4.2 Data Ingestion — `yfinance`
Single wrapper module used by both workflows. Pulls price/volume, basic fundamentals, and built-in
news headlines (`Ticker.news`) — one data dependency, no separate news vendor. US tickers are bare,
TSX use `.TO`, NSE (§12) use `.NS`. The ingestion layer is **market-agnostic** — it keys off the
ticker suffix and the `exchange` field yfinance returns, so adding a market is a config concern, not
an ingestion rewrite.

### 4.3 Candidate Sourcing & Prefilter (discovery only)
Makes FR4 ("scan beyond the watchlist, no fixed buy/sell criteria") buildable. **v9 correction:** the
SD previously described a maintained `candidate_universe` table pulled via `yf.download()`; that is
**not** how it works. The code (`prefilter.py`) sources candidates from **Yahoo's live server-side
screener** and applies quality gates + signals locally:
- **Sourcing — live screener, not a static universe.** Each day it pulls Yahoo's predefined screens
  `day_gainers`, `day_losers`, `most_actives` (US) plus a custom `region=ca` EquityQuery for Canada
  and (v14, live) a `region=in` EquityQuery for NSE — see §12 D5 for the India-specific corrections
  (NSE-only filtering, INR thresholds). There is **no maintained universe table**; the
  `candidate_universe` table in §5 is **vestigial** (seeded by no one, read by nothing) and should be
  dropped or ignored. This removes the "seed-and-quarterly-refresh" ownership burden the old SD
  invented — there's nothing to maintain.
- **Quality gates (all tunable, per-region):** minimum market cap (~$2B US/CA; **₹5e10 for NSE, v14** —
  a direct USD gate would leave almost nothing given INR-denominated market caps), price (~$5 US/CA;
  **₹50 for NSE, v14**), daily volume (~500k), and an allow-list of real primary exchanges (NYSE/Nasdaq
  tiers + Toronto + **NSI-only for India, v14** — `region=in` returns both NSE and BSE listings,
  filtered to NSE to avoid dual-listed duplicates) — excludes OTC/pink/secondary.
- **Signals — a survivor must trip ≥1 of these (all four are FR4-backed per Requirements v3, Decision #14):**
  (1) **mover** — abs % change past the gainer/loser threshold;
  (2) **volume spike** — today's volume ≥ a multiple of the 3-month average;
  (3) **earnings proximity** — earnings within a near-term window *(FR4's third criterion; **live in
  `prefilter._signals()`**, tunable via `DISCOVERY_EARNINGS_DAYS`. Best-effort: applied only when the
  screener carries an earnings timestamp, tagging a name whose earnings are imminent or just reported)*;
  (4) **52-week-extreme** — price within a small fraction of its 52-week high/low. *FR4's fourth
  signal, canonicalized in Requirements v3 (FR4 + Decision #14). Previously flagged to Product as a
  proposed add; that add has landed, so it is now part of the canonical spec, not an extra.*
- The ranked shortlist (capped ~15/day) is the **only** thing that goes to the AI.
- **Dedup before notifying:** watchlist tickers are excluded up front; a candidate pushed in the last
  7 days is logged but not re-pushed ("log always, push conditionally").
- **Push policy — Buys only (v9, documented).** Discovery **pushes only `Buy` candidates**; `Sell`/
  `Hold` candidates are logged silently (no notification). This keeps discovery to high-signal nudges.
**Pre-gate observability + threshold tuning (live — issue #8).** Discovery can legitimately return 0
candidates on a quiet day, and the logs previously couldn't tell **"screened N, 0 passed the gate"**
from **"screened 0 (something upstream broke)."** Now shipped: `find_candidates()` returns a **funnel
dict** (`raw → after_dedup → passed_quality → passed_signal`) and `run_discovery` logs the
stage-by-stage drop-off, plus a count of screens that errored so a silent screener failure can't
masquerade as a quiet day. *3 consecutive zero-signal days is a tuning signal, not normal.* Commits
`253599fc`, `d4ef8681`.

**NSE discovery is live (v14, §12, D5)** — `find_candidates(region='in')` runs the same
screener/gate/signal pipeline as US/TSX with NSE-specific quality-gate thresholds and exchange
filtering (above); the dispatch schedule is NSE-close-timed (10:00 UTC), separate from the US/TSX
22:00 UTC run, per §12 D5.

### 4.4 AI Judgment Layer
- Model: Gemini Flash free tier. **Model names are configurable repo Variables, never hardcoded:**
  `GEMINI_MODEL` / `GEMINI_MODEL_BACKUP` (watchlist) and `DISCOVERY_GEMINI_MODEL` /
  `DISCOVERY_GEMINI_MODEL_BACKUP` (discovery), wired through `judge_batch(models=...)`. Swappable from
  the GitHub UI with no commit. **This Variable-driven pattern is the standard for any model-bearing
  component** — including the NSE pair (`NSE_GEMINI_MODEL` / `NSE_GEMINI_MODEL_BACKUP`, live v14, §12).
- **Dual-model fallback:** each call attempts the primary model, falling back to the backup. The two
  draw from **separate per-model quota buckets**, so backup capacity survives primary RPD exhaustion.
- **One batched call per run, not per ticker (v9 correction).** The whole watchlist is judged in a
  **single** `judge_batch()` Gemini call (and the discovery shortlist in one more) — a JSON array of
  verdicts, one object per ticker. This is what keeps the system far under the free-tier daily request
  cap, and it's why the token total is a per-batch number (§4.4a, §5). The earlier "one call per
  ticker" wording was wrong. Ingestion (yfinance) is still paced per ticker; the AI step is one call.
  **v14:** each per-market group (§4.1, §12 D2) gets its own batched call with its own model try-order.
- Output is **strict JSON**, validated and retried — see 4.4a.
### 4.4a AI Prompt Specification (the actual product)

The system's value lives in this prompt. Specified so two developers build the same product.

**Verdict definitions** (operational):
- **Buy** — conditions favor opening or adding now.
- **Sell** — conditions favor reducing or exiting now. For held positions, relative to recorded cost
  basis and position size.
- **Hold** — no actionable change. The *default* and the most common output. Hold means "do nothing,"
  not "actively neutral." If the model is unsure, the answer is Hold.
The bias toward Hold is the brake that stops the system manufacturing action out of noise.

**Prompt template** (system + user split; fill `{...}` at runtime):

```
SYSTEM:
You are a disciplined, unemotional equity analyst. You output ONLY a single JSON
object and nothing else — no markdown, no code fences, no prose before or after.
Default to "Hold" unless the data clearly supports action. You do not assume any
fixed investment style or time horizon; weigh each stock on its own context.

Schema (all fields required):
{
  "verdict": "Buy" | "Sell" | "Hold",
  "rationale": "<one or two short, plain-language sentences; ≤280 chars stored>"
}

USER:
Ticker: {ticker} ({market})
Position: {held? "HELD" : "WATCH-ONLY"}
{if held:}  Shares: {shares}, Cost basis: {cost_basis} {currency},
            Current price: {price}, Unrealized P/L: {pl_pct}%
Price/volume (recent): {ohlcv_summary}
Fundamentals: {fundamentals_summary}
Recent news headlines: {news_headlines}

Give your verdict as JSON per the schema.
```

**Context serialization** — keep each block compact:
- `ohlcv_summary`: last close, % change 1d/5d/20d, volume vs. 20d average. **Newly-listed tickers:**
  a name with <~20 sessions can't fill the 20-day window — compute 1d/5d where history supports,
  pass the 20d fields as explicit `n/a (newly listed)`, never omit or fabricate.
- `fundamentals_summary`: P/E, market cap, 52w range — whatever yfinance reliably returns for *both*
  markets in scope. Phase 0 confirms per-market coverage; don't promise fields the source won't give.
- `news_headlines`: top 3–5 from `Ticker.news`, titles only.
**Model settings & batching (v9).** In the live code this prompt is sent as a **batch**: one call
carrying a numbered block per ticker and a `BATCH_SYSTEM_PROMPT` asking for a JSON *array* (one object
per ticker, every ticker exactly once); the single-ticker template above is the conceptual contract.
The call sets **`temperature=0.2`** (low, to reduce run-to-run drift — but verdicts are still
non-deterministic, §2 item 4) and `response_mime_type="application/json"`. **Rationale length:** the
model is asked for one or two short sentences; the stored value is capped at **280 chars**
(`RATIONALE_MAX`) and the push-notification body is separately clipped to **150 chars**
(`NOTIF_BODY_MAX`), on a word boundary with an ellipsis. UI handoff v3 is aligned to these limits
(280 stored / 150 push).

**Timeout & fallback handling (root cause confirmed by live data, v7):**
- The Gemini client uses an explicit **`GEMINI_TIMEOUT_MS` (default 180,000 ms / 180 s)** (commit
  `a0c86b00`). The prior default was too tight: it fired *before* a slow-but-valid response returned,
  the completed and **already-token-billed** response was discarded, and the call fell back to the
  backup model. The fallbacks looked like a quota problem and weren't.
- **Confirmed from live capture (issue #10):** the recurring fallbacks were that **client-side
  timeout**, and the remaining genuine fallbacks were transient **503 high-demand** responses —
  **not** 429/RPD exhaustion. The timeout fix was the right remedy; the earlier *attribution* to quota
  was wrong. Do not describe these fallbacks as rate-limiting.
- On any fallback, **the real exception is captured** (timeout, 503 high-demand, parse failure, or —
  if it ever genuinely occurs — 429/RPD) and written to `call_log.data_snapshot.fallback_from`, plus a
  run-level warning. The log is now the source of truth for "why did it fall back," not a guess.
**Parsing & retry strategy:**
1. Request JSON. Parse it.
2. On parse/schema failure → retry once with a terse "reply with ONLY the JSON object" appended.
3. On second failure → **log the failure, treat verdict as `Hold` (no alert), move on.** A malformed
   response never crashes the run and never gets guessed-at — failing safe to Hold means a parse bug
   can only ever *miss* a signal, never *fabricate* one.
4. Every raw model response (including failures) is written to `call_log.data_snapshot`.

**Fail-safe rationale wording (v14, issue #17, live).** `_FAIL_SAFE_API` no longer asserts
"rate-limited" — that phrasing contradicted load-bearing decision #3 (the real cause is a client-side
timeout or a transient 503, captured separately in `fallback_from`). Wording is now neutral, matching
`_FAIL_SAFE_PARSE`'s tone.

**Token accounting (v6):** `usage_metadata` is logged into `data_snapshot.tokens
{prompt, output, thoughts, total}`. **Critical consumer contract:** `tokens` is a **per-batch total
replicated onto every row of that run** — to report usage, dedup per run, **never sum per row**, or
you'll multiply the true number by the ticker count.

Note: even with strict JSON the verdict is non-deterministic across runs. As of v6 this is **not**
dampened at all — see §2 item 4. The single-rule §6.3 has no cooldown to cap how often
non-determinism surfaces as an alert.

### 4.5 State & Persistence — Supabase
All durable state here (schema §5). Chosen over a flat file because the detail page (FR14) queries a
specific log row directly. In v6 Supabase also hosts the scheduler and watchdog (§4.1, §4.8).

### 4.6 Alerting — ntfy.sh
Free, no account, topic-based push, `click` field for tap-through (FR12–14). The notify module is
provider-agnostic behind a small interface (Pushover is a drop-in later). In v6 there is **one alert
kind for the watchlist — `change`** ("Changed to Buy"); the `reminder` kind is **retired** with FR7
(§6.3). Discovery pushes are labeled `new-candidate`. Health-monitor pushes come from Supabase
directly via `send_ntfy` (§4.8), not from the workflow.

**Notification timestamp — single market-matched timezone (FR23). ✅ Live.** A
push is **formatted server-side at send time**, where the device timezone is unavailable — so the
notification carries **one** timezone, chosen by the alert's market, and **no secondary**:
- US / TSX alerts → **ET** (`America/New_York`), e.g. `10:30 AM ET`
- NSE alerts → **IST** (`Asia/Kolkata`), e.g. `8:00 PM IST`
`notify._market_timestamp(market)` returns the market's wall-clock label; `_compose_body` prefixes it
to the rationale (`"{timestamp} · {rationale}"`) within `NOTIF_BODY_MAX=150`, word-boundary clipped.
Unknown/missing market falls back to ET.

**Separate NSE ntfy topic (v14, D7, FR18, live).** `notify._topic_for(market)` routes NSE alerts to
`NSE_NTFY_TOPIC`, US/TSX to the default `NTFY_TOPIC`. **Falls back to the default topic if
`NSE_NTFY_TOPIC` is unset**, so an alert is never dropped for a missing config value — it just lands
on the shared topic until the NSE-specific one is provisioned.

This is deliberately *not* the dual-timezone display used on the client-rendered surfaces (§4.7,
§13) — the server can't detect the device, and the market's own timezone is the unambiguous anchor
for "when did this happen." **Notification copy (titles/body for `change` and `new-candidate`) is
owned by UI handoff v3 — build to the handoff, not to prose invented here.**

### 4.7 Detail Page — GitHub Pages
Minimal static page; reads `log_id` from the query string, fetches that `call_log` row via a
read-only Supabase **publishable key** (`sb_publishable_…`, the client-safe key, RLS-scoped to read
`call_log`) — the **secret key** (`SUPABASE_SECRET_KEY`, server-only, bypasses RLS) is used by the
workflows, never shipped to the page. *(v9: "anon key" everywhere in this doc means the new-style
publishable/secret keys the code uses — Supabase renamed them.)* Security is "unguessable URL," which
only holds because `call_log.id` is a **UUID, not a serial** — a serial would be trivially enumerable.
Fine for informational data (NFR3).

**Held-position block (UI handoff). ✅ Live.** The handoff specifies a "Your
position" block on the detail page for held tickers — shares, cost basis, current price, unrealized
P/L — omitted for watch-only. **Shipped:** `state.build_position()` computes the P/L, `state._snapshot()`
persists a `position` object into `data_snapshot` for held tickers (absent for watch-only), and
`detail.html` renders the `posBlock` only when `snap.position` is present — no empty block. This makes
the "personalized to your holdings" promise (FR2/FR11) visible on the page. *(Note: exercised only when
a ticker is actually held — the live `watchlist` currently has 0 held tickers and `holdings` is empty,
so the block is correct but dormant until holdings are populated; ruled working-as-intended, not a gap.)*

**Detail-page access posture (ratified v13 — Requirements Decision #17).** The detail page has **no
auth gate** — security is the UUID-unguessable URL described above, and nothing more. This is now an
explicit Product decision, not an unstated SD assumption: FR19's access-control requirement scopes to
the **dashboard only**; the detail page's read-only/informational nature (NFR3) is the accepted
rationale for leaving it at UUID-only. If that scope ever needs to widen, it's a Requirements change,
not an SD one.

**New-candidate rows carry no market badge (v14, issue #13, live).** `detail.html` previously guessed
a market badge from the ticker suffix on `new-candidate` rows, which have no `watchlist` row and thus
no authoritative market. The badge is now suppressed entirely for `label==='new-candidate'`;
`watchlist`-labeled rows render the badge unchanged.

**NSE badge + currency (v14, D9, live).** Currency symbol is derived from `watchlist.market`
(`$`/`CA$`/`₹`), not the ticker suffix or a possibly-missing fundamentals currency code, per UI-handoff
v3 — with a `.NS`-aware badge fallback so an NSE row with no snapshot market still badges NSE.

**Timestamp — client-rendered dual timezone (FR23). ✅ Live.** The detail page runs in the browser, so
the device timezone *is* available — it renders **device timezone primary, IST secondary in brackets**
(`Jun 19 · 10:04 AM ET (8:34 PM IST)`) via `Intl.DateTimeFormat().resolvedOptions().timeZone`, deduped
to a single timestamp if the device is already IST. `call_log.timestamp` is UTC (§5); conversion is
client-side (`detail.html fmtTs`/`clockIn`/`tzLabel`). Page layout and all variants are owned by
UI handoff v3.

### 4.8 Reliability — active dead-man monitor (rewritten in v6, NFR2)

**What changed and why.** v5's reliability story was "GitHub emails on failure + a queryable
heartbeat row." That only catches a run that *executes and fails*. It is blind to the failure mode
that actually bit us — a run that **never triggers at all** (dropped pg_cron tick, expired PAT,
disabled workflow). A passive heartbeat row no one reads is not a monitor.

**Current design (Phase 5, live):**
- A third pg_cron job, **`health-monitor`**, runs **`check_pipeline_health()`** on a schedule
  independent of the two workflows.
- It actively raises an **ntfy alert** (via `send_ntfy`) when: the watchlist heartbeat is **stale
  during market hours**, the daily **discovery run didn't fire**, or a run **completed degraded**.
- **`monitor_alerts`** (state table) dedups: alert on **state change** into a bad state, **re-alert
  per cooldown** while it stays bad, and emit **one recovery notice** when it clears. Helpers
  `_raise_monitor` / `_clear_monitor` encapsulate the transitions.
- DDL is version-controlled at **`sql/phase5_monitoring.sql`**.
**ET-aware monitor window (live — issue #12).** The monitor's watchlist staleness window is now
computed in ET: `(p_now at time zone 'America/New_York')::time between '10:15' and '16:00'`. It
previously used a **fixed UTC 14:30–21:30** window, which ran ~90 minutes past the EDT close and fired
a **daily false "stalled" alert at 20:50 UTC** — the defect #12 described. The **discovery** check
stays UTC-based (it watches the fixed 22:00 UTC dispatch, which has no DST dependency). Commit
`07d10e7f`; `sql/phase5_monitoring.sql` updated and re-applied.

**IST monitor window (v14, D4, live).** `check_pipeline_health()` gained a second IST-appropriate
watchlist window, sharing the same `hourly-watchlist` heartbeat key as US/TSX (the two sessions never
overlap, §12 D2, so one heartbeat correctly represents both). The `health-monitor` cron itself was
widened (`4-10,14-23` UTC) so the IST window actually gets evaluated.

**Known limit (see §2 item 6):** the monitor lives in the same Supabase pg_cron that triggers the
workflows, so it cannot catch a total Supabase/pg_cron outage. An out-of-band uptime ping is the
documented (unbuilt) mitigation.

---

## 5. Data Model (Supabase / Postgres)

| Table | Key columns | Purpose |
|---|---|---|
| `watchlist` | ticker, market (US/TSX/NSE), type (stock/ETF), status (held/watch-only), date_added | The ticker list (FR1, FR3); `market` now three-valued (§12), CHECK widened v14 |
| `holdings` | ticker, shares, cost_basis, currency | Position data for gain/loss (FR2, FR11); `currency` now three-valued (§12); `shares > 0` / `cost_basis > 0` guards live (v14) |
| `candidate_universe` | ticker, market, active | **Vestigial (v9)** — not read by code; discovery uses Yahoo's live screener (§4.3). Drop or ignore. |
| `verdict_state` | ticker, current_verdict, last_checked_at | Change-detection for the single rule (§6.3) |
| `call_log` | id (**uuid**), ticker, verdict, rationale, timestamp, label (watchlist/new-candidate), alert_type (**change/null**, CHECK tightened v14), alerted (bool), data_snapshot (jsonb) | Track record (FR15); detail-page source |
| `monitor_alerts` | check_name (PK), last_state, last_alerted_at, updated_at | Dead-man monitor dedup state (§4.8) |
| `run_heartbeat` | workflow_name, last_run_at, status | Per-workflow heartbeat the monitor reads (NFR2) |

**`verdict_state` is now physically three columns (v7): `ticker`, `current_verdict`,
`last_checked_at`.** Retiring the cooldown (issue #11) and the reminder (FR7) removed everything the
table carried to serve them — `last_alert_verdict`, `last_alert_at`, `reminder_due_at`, **and the
`bootstrapped` flag** (the v5-era #5 bootstrap mechanism, dropped with the single-rule cleanup) — are
all **gone**, along with the two-clock cold-start machinery v5 needed. The single rule only needs the
last-seen verdict to diff against and a checked-at timestamp. Migration `issue_11_shrink_verdict_state`.
This is the schema shrinking to match a simpler rule, deliberately.

**`call_log.alert_type` CHECK tightened to `change`/null only (v14, issue #14, live).** The
`reminder` value — retired in code since v6 (FR7) — is no longer a permitted CHECK value. No code
ever emitted it; this closes the vestigial constraint gap, it's not a behavior change.
Discovery `new-candidate` rows carry `alert_type=null`; the detail-page/notification headline keys off
`label` first (a `new-candidate` shows the bare verdict, no "changed to" prefix).

**`data_snapshot` (jsonb) contract (corrected to live code, v9):**
```json
{
  "price": 0.0, "pct_change_1d": 0.0, "pct_change_5d": 0.0,
  "pct_change_20d": 0.0,
  "volume_vs_avg": 0.0, "fundamentals": { "pe": 0, "market_cap": 0, "range_52w": [0,0], "currency": "USD" },
  "headlines": ["...", "..."],
  "raw_model_response": "<verbatim, for debugging>",
  "parse_status": "ok | retried | failed | api_error | no_data",
  "model_used": "<gemini model string that produced this>",
  "tokens": { "prompt": 0, "output": 0, "thoughts": 0, "total": 0 },
  "fallback_from": "<null | timeout | 503 | 429-rpd | parse | ...>",
  "discovery_signals": ["mover", "volume", "52w-high"],
  "rate_limited": false,
  "position": { "shares": 0, "cost_basis": 0.0, "currency": "USD", "pl_pct": 0.0 }
}
```
**v9 corrections vs the old contract:** added `pct_change_20d` (string `"n/a (newly listed)"` for young
listings), `model_used`, `discovery_signals` (present only on discovery rows), and `rate_limited`
(present on skip rows). `parse_status` also takes **`api_error`** (model unreachable) and **`no_data`**
(ingest skip) beyond `ok | retried | failed`. **`position` is now persisted (v12):** for held tickers,
`state._snapshot()` writes a `position` object (`shares`, `cost_basis`, `currency`, `pl_pct` from
`build_position()`) so the detail-page block (§4.7) can render; it is **absent** for watch-only tickers
and for discovery rows (no holding).
**`tokens` is a per-batch total replicated across every row of the run — dedup per run, never sum per
row.** `fallback_from` records the *real* reason a call fell to the backup model (§4.4a), null if the
primary succeeded.

**Supabase objects.** Functions: `dispatch_github_workflow` (live), `dispatch_watchlist_if_open`
(**live** — ET-aware dispatch gate, §4.1), `dispatch_watchlist_nse_if_open` (**live, v14** — IST gate,
§12 D1/D2), `send_ntfy`, `_raise_monitor`, `_clear_monitor`, `check_pipeline_health`. Extensions:
`pg_cron`, `pg_net`. Vault secrets: `github_workflow_pat`, `ntfy_topic`.

**Timestamps are stored in UTC; rendering is per-surface (FR23, v8):**
- **Notifications** (server-formatted, §4.6): one market-matched timezone — ET for US/TSX, IST for NSE.
- **Detail page (§4.7) and dashboard (§13)** (client-rendered): device timezone primary + IST
  secondary in brackets, deduped if the device is IST.
- **Relative time** ("2 hours ago", FR21, §13) is computed **client-side at render** from
  `call_log.timestamp`. Contract: `timestamp` is UTC `timestamptz`; the client diffs it against
  `Date.now()` and also formats the absolute dual-timezone string from the same value. No
  server-side relative-time field is stored — it would be stale the moment it's written.
- Market-hour *gating* is computed in `America/New_York` (and `Asia/Kolkata` for NSE, §12) — never
  fixed UTC offsets (§4.1).
**Manual-edit validation (v14, live — issue #15).** `holdings.shares` and `holdings.cost_basis` now
carry `CHECK (shares > 0)` / `CHECK (cost_basis > 0)` guards, added in the same migration as the
NSE/INR constraint widening (§12). This is a basic input-validation floor, not a full validation
layer — a bad *ticker* (non-existent, delisted) still fails at runtime, not entry, and degrades
gracefully (skip-with-log, §7.5).

---

## 6. Core Flows

### 6.1 Intraday Watchlist Check — 30-min cadence (per-market gate, v6; NSE live v14)

> **Cadence is every 30 minutes** (Requirements FR6, NFR1, NFR4; live cron `*/30 13-21 UTC` trimmed
> by the ET gate). The word "hourly" survives only as a **legacy identifier** — the workflow file is
> still named `hourly-watchlist.yml` and the heartbeat is keyed `hourly-watchlist` — and does **not**
> describe the actual cadence. Don't read those names as a 60-minute interval. *(Side note for
> Product: Requirements v4 has since cleaned up the FR6/v2-note inconsistency this paragraph used to
> flag; the build runs at 30 min, and the docs now agree.)*

```mermaid
sequenceDiagram
    participant PGCRON as Supabase pg_cron
    participant FN as dispatch fn (pg_net)
    participant GH as GitHub Actions
    participant SB as Supabase
    participant YF as Yahoo Finance
    participant AI as Gemini Flash
    participant NTFY as ntfy.sh

    PGCRON->>FN: scheduled tick
    FN->>FN: which market is open now? (ET for US/TSX, IST for NSE §12)
    alt no market open
        FN->>FN: no dispatch, exit
    else a market is open
        FN->>GH: workflow_dispatch hourly-watchlist.yml
        GH->>SB: Fetch watchlist + holdings + verdict_state
        loop each ticker, yfinance-paced
            GH->>YF: Fetch price/volume/news/fundamentals (skip-with-log on no data)
        end
        GH->>AI: ONE batched call per open market group — all its tickers in a single JSON-array prompt
        AI-->>GH: Verdict + rationale per ticker (primary→backup)
        loop each ticker result
            GH->>GH: Compare to verdict_state.current_verdict
            alt verdict changed
                GH->>SB: Insert call_log (alert_type=change, alerted=true)
                GH->>SB: Update verdict_state (current, last_checked_at)
                GH->>NTFY: Push "Changed to X" + detail link (topic per market, §4.6)
            else unchanged (incl. cold start)
                GH->>SB: Insert call_log (alert_type=null, alerted=false)
                GH->>SB: Update verdict_state (current, last_checked_at)
            end
        end
        GH->>SB: Write run_heartbeat
    end
```

The **per-market gate** (filter the watchlist to whichever market is currently open) is the v6
generalization of v5's single ET gate. **Live since v14 (§12 D2):** each wake-up filters to whichever
session is open — US/TSX via ET, NSE via IST — and each open group runs its own batched AI call.
Sessions never overlap (verified across DST regimes), so one group runs per wake-up; the shared
`hourly-watchlist` heartbeat covers both.

### 6.2 Daily Discovery Scan

```mermaid
sequenceDiagram
    participant PGCRON as Supabase pg_cron
    participant FN as dispatch fn (pg_net)
    participant GH as GitHub Actions
    participant SB as Supabase
    participant YF as Yahoo Finance
    participant AI as Gemini Flash
    participant NTFY as ntfy.sh

    PGCRON->>FN: post-close tick (22:00 UTC US/TSX, 10:00 UTC NSE)
    FN->>GH: workflow_dispatch daily-discovery.yml (region=na or region=in)
    GH->>SB: Fetch watchlist + recent new-candidate logs (7d)
    GH->>YF: Yahoo live screener (day_gainers/losers/most_actives + region=ca, or region=in for NSE)
    GH->>GH: Quality-gate (region-specific thresholds) + tag signals (mover/volume/earnings/52w); drop watchlist; rank; log funnel #8
    GH->>AI: ONE batched call over shortlist (~15, region-appropriate models, primary→backup)
    AI-->>GH: Verdict + rationale per candidate
    loop each candidate
        GH->>SB: Insert call_log (label=new-candidate, alert_type=null)
        alt verdict==Buy AND not pushed in last 7d
            GH->>NTFY: Push + detail link, labeled "new candidate" (topic per market, §4.6)
        else Sell/Hold, or flagged within 7d
            GH->>GH: Logged only, push suppressed
        end
    end
    GH->>SB: Write run_heartbeat
```

### 6.3 Alert Logic — single rule (rewritten v6, implemented v7, issue #11)

**Why this section changed.** The v3 hybrid (change alert + 24h cooldown + 7-day reminder) is
replaced by **one rule**, now **implemented in code, not just specified** (commits `cdd75ce4`,
`58bcca52`):

> **Any verdict change → immediate alert. No change → silence. No cooldown, no debounce, no
> reminder.**

The 24h cooldown is removed; the debounce was already gone in v3; and **FR7's 7-day standing-verdict
reminder is retired** (owner ruling) — "no change → silence" is now **absolute**, with no exception.
The cold-start baseline is the only special case, and it's a no-alert, not an exception to the rule.
The dead cooldown/reminder config constants were also deleted in this cleanup.

**Bootstrap path removed (v7).** The v5-era **post-cold-start bootstrap** (the #5 fix, which used the
now-dropped `bootstrapped` flag, §5) was **removed** as part of the single-rule cleanup. Consequence,
stated explicitly because the doc never described the bootstrap: **a standing Buy/Sell that is
actionable at cold start is now silent until it changes** — the SPCX / TD.TO case. The system never
re-announces a verdict it already established; it signals only on the *crossing*. This is exactly the
§2 item 4 posture (signal on threshold crossings, not standing states), now true in code. **This is
also why NSE go-live (v14, §12) did not dump the 10 seeded tickers with alerts** — cold start is
silent by design.

**Requirements-doc reconciliation — complete (Requirements v3, unchanged through v4).** FR7 carries
the single-rule model (any verdict change → immediate alert, no cooldown) and FR8 carries the silence
rule; the SD and the source-of-truth doc agree. The single rule is effectively the merged FR7+FR8.

```
for each ticker in (watchlist filtered to the currently-open market):
    new_verdict = ai_judge(ticker)            # JSON-validated, fails safe to Hold (§4.4a)
    state = get_verdict_state(ticker)

    # ---- cold start: establish baseline, no alert (avoids go-live dump) ----
    if state is None:
        create_verdict_state(ticker, current=new_verdict, last_checked_at=now)
        write_call_log(ticker, new_verdict, alert_type=NULL, alerted=False)
        continue

    # ---- no change → silence (still logged for the track record, FR15) ----
    if new_verdict == state.current_verdict:
        state.last_checked_at = now
        write_call_log(ticker, new_verdict, alert_type=NULL, alerted=False)
        save_verdict_state(state)
        continue

    # ---- change → immediate alert, no cooldown ----
    write_call_log(ticker, new_verdict, alert_type="change", alerted=True)
    send_push(ticker, new_verdict, rationale, kind="change")     # "Changed to X"
    state.current_verdict = new_verdict
    state.last_checked_at = now
    save_verdict_state(state)
```

**Consequences, stated plainly:**
- **A change to Hold still alerts** — a held Buy weakening to Hold is a real signal ("the case to
  hold just got weaker"). Style it neutral (not a warning color), but it fires.
- **No frequency cap.** A choppy day that oscillates a verdict will push on every flip. This is the
  accepted risk in §2 item 4 — the price of the single rule's simplicity, and the thing to watch in
  the first weeks live. The documented re-add if it hurts is a minimal cooldown or the "2 of 3"
  debounce, both in git history.
- **Every check still logs (FR15).** No-change and cold-start rows write `call_log` with
  `alerted=false`, so the track record can reconstruct what the system thought on silent days.
---

## 7. Non-Functional Design

### 7.1 Cost (NFR1: $0–15/month target)
Hosted as a **public repo** — public repos get unlimited free Actions minutes (the v1 private-repo
math was 2×+ over the free allowance). No secrets in code (all in Actions secrets / Supabase Vault),
so visible code is acceptable. Supabase free tier covers pg_cron, pg_net, and this data volume.
Gemini Flash, ntfy.sh, GitHub Pages all $0. **v14:** the new `publish-prices.yml` workflow adds
negligible Actions minutes (same public-repo unlimited-minutes posture). **Total ≈ $0/month**, full
$15 headroom unused.

### 7.2 Security
No trade execution, no brokerage credentials anywhere (out of scope). Secrets in GitHub Actions
encrypted secrets and **Supabase Vault** (`github_workflow_pat`, `ntfy_topic`). The
`dispatch_github_workflow` function is `SECURITY DEFINER` and must be written to read the PAT from
Vault only — never echo it into logs or `pg_net` debug output. Detail page uses a read-only
**publishable key** under RLS (the server uses the **secret key**, §4.7); `call_log.id` is a UUID
(§4.7). **`monitor_alerts` has RLS** like every other table
(issue #6 — applied via migration `20260624121047`; it turned out already fixed when audited).
**`watchlist` SELECT RLS (v14, issue #16, live):** a read-only SELECT policy mirroring `call_log`'s
was added so the publishable key can read `watchlist` — required for the dashboard (§13).

### 7.3 Currency
Gain/loss in each position's native currency — **USD (US), CAD (TSX), INR (NSE §12)** — no FX
conversion. The detail page shows a market badge and the native currency symbol per position.

### 7.4 Concurrency & Run Safety
pg_cron dispatch is reliable but a slow run could still overlap the next. Guard with
`concurrency: { group: hourly-watchlist, cancel-in-progress: false }` so GitHub serializes runs
instead of letting two mutate `verdict_state` for the same ticker at once. The loop is bounded
(≤~15 tickers, paced); a run that runs long is itself a signal the monitor will surface.

### 7.5 Delisting / Halts / New Listings
A ticker returning no usable price data is **skip-with-log**, never a crash — one broken ticker must
not take down the run for the others. **New listings** are *not* a skip: a recent IPO returns valid
price data but too little history for the 20-day window — compute what history supports, mark the
20d fields `n/a (newly listed)` (§4.4a), let the AI judge on the rest. Phase 0 classifies this `NEW`,
not `FAIL`.

---

## 8. Repo Structure

```
stock-advisory-analysis/                # actual repo name
├── .github/workflows/
│   ├── hourly-watchlist.yml      # workflow_dispatch ONLY (no schedule:), concurrency group
│   ├── daily-discovery.yml       # workflow_dispatch ONLY (no schedule:), concurrency group
│   ├── publish-prices.yml        # v14: writes pages/prices.json (issue #18 fallback, §13)
│   ├── cors-smoke-test.yml       # v14: issue #18 probe (runner-based, Yahoo egress-blocked locally)
│   ├── phase0-smoke-test.yml     # Phase-0 yfinance smoke test (manual)
│   └── phase4-smoke.yml          # Phase-4 screener-shape smoke test (manual)
├── scripts/
│   ├── config.py                 # market hours/gate, model Variables, discovery gates/thresholds
│   ├── ingest.py                 # yfinance wrapper (US bare / .TO / .NS; new-listing handling)
│   ├── prefilter.py              # Yahoo live screener + quality gates + signals + funnel (#8); region-aware (v14)
│   ├── ai_judge.py               # Gemini batched judge_batch(models=...) + timeout/fallback
│   ├── state.py                  # Supabase read/write, single-rule change machine (§6.3)
│   ├── notify.py                 # ntfy.sh dispatch (provider-agnostic); per-market topic routing (v14)
│   ├── run_hourly.py             # hourly watchlist orchestrator, per-market gate (§6.1)
│   ├── run_discovery.py          # daily discovery orchestrator, region-aware (§6.2)
│   ├── publish_prices.py         # v14: fetches watchlist prices, writes pages/prices.json (issue #18)
│   ├── phase0_smoke_test.py      # Phase-0 data smoke test (NSE exchange-string check added, §12)
│   ├── phase4_screener_smoke.py  # Phase-4 screener smoke test
│   ├── india_screener_smoke.py   # v14: region=in screener shape probe (fed §12 D5)
│   └── cors_smoke_test.py        # v14: issue #18 probe script
├── sql/
│   ├── scheduler_pgcron.sql      # dispatch fns (incl. NSE, v14) + all cron jobs; matches live cron
│   └── phase5_monitoring.sql     # monitor_alerts, send_ntfy, check_pipeline_health, ET+IST gates
├── pages/
│   ├── detail.html               # GitHub Pages detail view
│   ├── dashboard.html            # v14: Phase 7 read-only dashboard, live (§13)
│   └── prices.json               # v14: published by publish-prices.yml, read same-origin by dashboard
├── requirements_docs/            # v14: Requirements, UI-handoff, SD, SD-history — committed to repo
└── requirements.txt              # yfinance, google-genai, supabase, requests, tzdata
```

---

## 9. Build Phases

| Phase | Scope | Status / Exit criteria |
|---|---|---|
| 0 | Yahoo Finance smoke test vs. real watchlist tickers (US + TSX) | ✅ Done — price/volume/fundamentals confirmed; `NEW` IPO case found (SPCX) |
| 1 | Supabase schema + watchlist/holdings populated | ✅ Done |
| 2 | Hourly workflow: ingest → AI verdict → single-rule change detection → log | ✅ Done (now single-rule, §6.3) |
| 3 | Push notification + detail page | ✅ Done |
| 4 | Daily discovery: universe → prefilter → AI shortlist → log + alert | ✅ Done — pre-gate observability (#8) **live**: `find_candidates()` funnel logged stage-by-stage |
| 5 | **Reliability hardening — active dead-man monitor** | ✅ Done — `health-monitor` pg_cron runs `check_pipeline_health()`; `monitor_alerts` dedup (state-change alert, cooldown re-alert, one recovery); live ntfy push confirmed; DDL in `sql/phase5_monitoring.sql`. ET-aware monitor window (#12) **live** (`10:15–16:00` ET) |
| — | **Scheduling migration (cross-cutting)** | ✅ Done — pg_cron + `workflow_dispatch` replaced GitHub native cron (§4.1) |
| 6 | **India NSE — watchlist + discovery** | ✅ **Done, live (v14).** §12. 10 NSE tickers on the IST watchlist dispatch + monitor window; NSE discovery live on its own NSE-close-timed dispatch (region=in, NSE-only, INR-thresholded); separate NSE ntfy topic (D7); INR rendering per UI handoff. Go-live (alerts on) landed same day as build; cold-start silence meant no alert dump on activation. |
| 7 | **Read-only dashboard** | ✅ **Done, live (v14).** §13. Built (#22) against the original direct-Yahoo-fetch design; **reworked (#24) after issue #18's CORS smoke test proved that design infeasible** — live price now reads a server-published `pages/prices.json` (same-origin) instead. All other FR19–22 behavior (market grouping, conditional last-run block, access gate, FR23 timestamps) unchanged from the original build. |

---

## 10. Test Scenarios (for QA)

- **Cold start:** first run logs every ticker, sends zero notifications, sets `current_verdict`.
- **Change alert fires immediately:** a verdict transition (Hold→Buy) sends one "Changed to Buy"
  push and logs `alert_type=change` — **no cooldown gate** (v6).
- **Change to Hold alerts:** Buy→Hold pushes "Changed to Hold," styled neutral, not suppressed.
- **No-change is silent but logged:** an unchanged verdict sends nothing and writes a `call_log` row
  with `alerted=false` (FR15).
- **Choppy day, multiple alerts (accepted):** a verdict oscillating Buy→Hold→Buy within a day fires
  an alert on **each** flip — confirms the no-cooldown behavior in §2 item 4, not a regression.
- **No reminder ever (v6):** a ticker sitting at Buy untouched for weeks sends **nothing** — the FR7
  reminder is retired; verify no `reminder` path exists.
- **Malformed AI response:** force non-JSON → one retry, then fail-safe Hold, raw response in
  `data_snapshot`, `parse_status=failed`, no crash.
- **Slow-but-valid Gemini response:** a response slower than the old default but within
  `GEMINI_TIMEOUT_MS` is **kept**, not discarded to fallback (regression test for the v6 timeout fix).
- **Fallback reason is real:** force a 503 and a timeout separately → `fallback_from` records each
  distinctly, not a hardcoded "rate-limited."
- **Token accounting:** a multi-ticker run's `tokens` total is **not** the per-row sum — verify
  consumers dedup per run.
- **Scheduler reliability:** confirm pg_cron dispatch actually fires the workflow (the failure mode
  that motivated the migration); a missing dispatch surfaces via the monitor.
- **Dead-man monitor:** simulate (a) stale watchlist heartbeat in market hours, (b) discovery
  no-show, (c) degraded run → each raises one ntfy alert; `monitor_alerts` dedups; clearing fires
  exactly one recovery notice.
- **ET-aware gate (#9, #12) — live regression:** across a DST boundary, no post-close dispatch and no
  false "stalled" alert. The dispatch gate (`09:30–16:00` ET) and the monitor window (`10:15–16:00`
  ET) both track the close correctly; the old 20:50 UTC false alert no longer fires.
- **Safe forced test (#7) — live:** `FORCE_RUN=true` + `ALERTS_ENABLED=false` runs off-hours with
  **no** real push; the `[gate]` audit line records `market_open`, `force_run`, `alerts`, and UTC+ET
  time. `ALERTS_ENABLED=true` off-hours *does* push (documented, not a defect).
- **Standing-state silence (#11, v7):** a ticker actionable (Buy/Sell) at cold start and never
  changing sends **nothing** — no bootstrap announcement. Verify the SPCX/TD.TO case stays silent
  until the verdict actually crosses.
- **Concurrent runs:** two overlapping hourly runs are serialized by the `concurrency` group;
  `verdict_state` never double-written.
- **Holiday/weekend:** gate no-ops cleanly, no false "data missing."
- **Stale/missing data & delisted ticker:** skip-with-log, never fatal for the other tickers.
- **Detail page security:** anon key can only read `call_log`, cannot write or read other tables;
  guessing a numeric id returns nothing (UUID).
- **Discovery dedup & labeling:** watchlist tickers never reach discovery; a candidate flagged two
  days running logs both days, pushes once; labeled `new-candidate` end-to-end.
**FR23 timestamps (v8):**
- **US/TSX notification:** timestamp renders in **ET only**, no IST, no brackets.
- **NSE notification:** timestamp renders in **IST only**, no ET, no brackets.
- **Detail page timezone:** device in ET → `ET (IST)`; device in PT → `PT (IST)`; device in IST →
  **IST only**, no bracketed duplicate.
- **Dashboard timezone:** same three device cases as the detail page.
**NSE (v14, Phase 6 — live):**
- **NSE watchlist gate — verified.** During the IST session NSE tickers are checked and US/TSX are
  not (and vice-versa); 0 overlaps confirmed across EDT/EST/Sat at 5-minute resolution.
- **NSE discovery timing — verified.** The NSE discovery dispatch fires after the NSE close (10:00
  UTC), not on the 22:00 UTC US/TSX run; candidates are screened on the current NSE session's data.
- **NSE currency/badge — verified.** INR symbol and NSE badge render per UI handoff; no FX conversion.
- **NSE topic routing — verified.** US/TSX→default topic, NSE→`NSE_NTFY_TOPIC`, NSE-topic-unset→
  falls back to default (never drops an alert), case-insensitive market matching.
- **NSE discovery filtering — verified.** `region=in` results filtered to NSE only (`exchange='NSI'`),
  BSE (`.BO`) duplicates dropped; INR market-cap/price gates applied; `NSI→NSE` market mapping correct.
- **Still to observe (flagged by dev session, 2026-07-01):** a live NSE trading-session run — go-live
  landed after that day's NSE window had already closed; first live confirmation is the next NSE
  session.
**Dashboard (v14, Phase 7 — live):**
- **No `call_log` rows:** a ticker with zero log rows shows live price only — last-run columns
  **absent** (not rendered, not placeholdered), per UI handoff.
- **Only `alerted=false` rows:** last-run columns **present**, showing the silent verdict + rationale
  — confirms the dashboard reflects what the system last *thought*, not only what it *pushed*.
- **Mixed `alerted` rows:** the **most recent** `call_log` row renders regardless of its `alerted`
  value (query orders by `timestamp DESC`, no `alerted` filter).
- **Auto-refresh cycle:** on each tick the live price re-reads `prices.json` (§13) and the latest
  `call_log` per ticker re-reads from Supabase; the "prices updated Ns ago" clock keys off
  `prices.json`'s `generated_at` field (honest data-age against the publish cadence, not the browser
  tick), staying visually distinct from the per-card verdict age.
- **Access gate — verified.** Client-side SHA-256 passcode gate (session-scoped) blocks unauthenticated
  access; smoke-tested in headless Chromium.
- **Relative time:** a row checked 30 min ago shows "30 minutes ago"; the same row 2 h later shows
  "2 hours ago" — recomputed client-side at render (FR21).
- **Dashboard security:** anon key can read **only** `call_log` and `watchlist`; no other table is
  reachable; no write path exists.
---

## 11. Open Items Carried Forward

*Closed in v14: all five genuine gaps from the v12/v13 review — #13, #14, #15, #16, #17 — are fixed
and merged. Phase 6 (NSE) and Phase 7 (dashboard) are both built and live. Issue #18 (CORS
feasibility) is resolved with a documented architecture change (§13). The Part-1/Phase-6/Phase-7
build plan handed to the dev conversation is complete.*

Still open:

- **Supabase single-point-of-failure** (§2 item 6) — scheduling *and* monitoring both live in
  Supabase pg_cron; an out-of-band uptime ping is the unbuilt mitigation. Decide if it's worth adding.
- **RPD sustainability — standing ops note, not a defect (#10 Problem 2).** This is *not* the old
  fallback story (that was timeout/503, never RPD — §2 item 3, §4.4a). It's a genuine ongoing watch
  item: real RPD consumption against free-tier caps, now with a third market's worth of load. It's
  manageable by design — the model is a configurable repo Variable per market, dual-model fallback
  draws from **separate per-model buckets**, and `data_snapshot.tokens` makes consumption trackable.
  **Tracking contract:** dedup the per-batch token total **per run**, never sum across rows. Watch it;
  act only if a cap is actually approached.
- **First live NSE session not yet observed** — go-live (v14) landed after the NSE session had closed
  for the day; confirm a clean `hourly-watchlist` heartbeat and correct topic routing on the next
  live IST session.
- **Confirm current Gemini free-tier model names + RPM/RPD** against live docs at build time —
  standing item, now covering three model-Variable pairs (US/TSX, discovery, NSE).
- **SD §8 self-reference stale (minor, doc-only).** §8 previously said the requirements/SD docs "live
  outside the repo" — no longer true as of the docs being committed to `requirements_docs/`. Corrected
  in this v14 pass.
---

## 12. India NSE Expansion — live (v14)

> **Status: live in production (v14).** Built across PRs #20–#21, #23–#26; went from Phase-0 smoke
> test through dry-run activation to alerts-on go-live in a single build cycle. This section now
> describes **what's running**, not planned scope — history of the design decisions (D1–D9) is
> preserved below since the *why* is still load-bearing for anyone touching this code.

**What it is.** NSE as a third exchange alongside US and TSX: a 10-ticker watchlist plus NSE
participation in the daily discovery scan.

**Live NSE watchlist** (Yahoo `.NS` symbols; Nifty-50 heavyweights, watch-only, seeded via migration
`phase6_seed_nse_watchlist`): `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS`, `BHARTIARTL.NS`, `ICICIBANK.NS`,
`INFY.NS`, `SBIN.NS`, `HINDUNILVR.NS`, `ITC.NS`, `LT.NS`.

**The core challenge — timezone / session.** NSE trades 09:15–15:30 IST = **03:45–10:00 UTC**,
entirely outside the US/TSX 13:00–21:00 UTC window. IST has **no DST** (fixed UTC+5:30), so its UTC
window is stable. This broke the system's original "one shared ET session" assumption — the fix
teaches the **scheduler** and the **open-market gate** that there are now **two non-overlapping
sessions**, verified with a 5-minute-resolution sweep across both DST regimes (0 overlaps).

**Design decisions (D1–D9) — as built:**

- **D1 — Scheduling (watchlist). Live.** A second `nse-watchlist-dispatch` pg_cron
  (`*/30 3-10 * * 1-5`) reuses `hourly-watchlist.yml` — no new workflow. *(§4.1)*
- **D2 — Per-market open gate. Live.** `run_hourly.py` filters the watchlist to whichever session is
  open (US/TSX via ET, NSE via IST) and runs each open group through its own batched AI call with its
  own model try-order. Runtime gate remains the authority (load-bearing decision #4). Shared
  `hourly-watchlist` heartbeat. *(§4.1, §6.1)*
- **D3 — Quota. Live.** `NSE_GEMINI_MODEL` / `NSE_GEMINI_MODEL_BACKUP` repo Variables, same pattern as
  §4.4, wired through `nse_models()`. *(§4.4)*
- **D4 — Monitoring. Live.** `check_pipeline_health()` gained a second IST-appropriate window; shared
  `hourly-watchlist` heartbeat covers both sessions. *(§4.8)*
- **D5 — Discovery. Live.** NSE candidates run through `find_candidates(region='in')` on a dedicated
  NSE-close-timed dispatch (`discovery-dispatch-nse`, fixed 10:00 UTC — the existing 22:00 UTC US/TSX
  dispatch would have screened stale pre-open data). Two real gaps surfaced by the India screener
  smoke test (`india_screener_smoke.py`) and resolved during build:
  - `region=in` returns **both NSE and BSE** listings (45%/55% split, dual-listed) — filtered to
    **NSE only** (`exchange='NSI'`), dropping BSE (`.BO`) duplicates. **Ratified 2026-07-01** (Tech
    Lead, see PR #24 comment thread): BSE stays excluded.
  - Market caps are **INR-denominated** — the USD $2B gate would leave almost nothing, so
    NSE-specific thresholds apply: `DISCOVERY_MIN_MARKET_CAP_INR` = **₹5e10** (~₹5,000cr / ~$0.6B,
    set from the probe's observed median mover market cap) and `DISCOVERY_MIN_PRICE_INR` = **₹50**.
    **Ratified 2026-07-01** (Tech Lead) — both stand as shipped.
  - `candidate_universe` remains vestigial and was **not** reintroduced for NSE (load-bearing
    decision #7 held). *(§4.3, §4.1-pattern)*
- **D6 — Currency. Live.** INR native, no FX (§7.3); NSE badge + `₹` on detail page and dashboard.
  *(§7.3, §13, UI handoff)*
- **D7 — Separate ntfy topic. Live.** `notify._topic_for(market)` routes NSE alerts to
  `NSE_NTFY_TOPIC`, falling back to the default topic if unset (never drops an alert). *(§4.6, FR18)*
- **D8 — go-live sequencing.** Activation was deliberately staged: dry-run first (PR #25 — NSE
  dispatch + monitor + discovery all live but `alerts_enabled=false`, so the pipeline could be
  observed without risking a false alert burst), then flipped to alerts-on (PR #26) once
  `NSE_NTFY_TOPIC` was provisioned. Cold-start silence (§6.3) meant go-live did **not** dump alerts
  for the 10 seeded tickers.
- **D9 — Detail-page rendering. Live.** Currency symbol from `watchlist.market`, `.NS`-aware badge
  fallback. *(§4.7)*

**Phase-0 NSE smoke test — passed.** Confirmed via `phase0_smoke_test.py` run on a GitHub-hosted
runner (Actions run `28495067459`): all 10 tickers report `exchange=NSI` as expected, with
fundamentals and `Ticker.news` coverage present for all 10.

**Schema change — applied (issue #15).** The `watchlist.market` CHECK now admits `NSE` and
`holdings.currency` admits `INR`, alongside the bundled `holdings.shares > 0` / `holdings.cost_basis
> 0` validation guards (§5). Migration landed before any NSE rows were inserted, per the original gate.

**Not yet observed:** a full live NSE trading-session run — go-live landed after that day's NSE
window had already closed. First live confirmation is the next NSE session (§11).

---

## 13. Read-Only Dashboard — live (v14)

> **Status: live in production (v14).** Built in two passes: the original design (PR #22, direct
> browser→Yahoo fetch per the original UI-handoff spec) and a **necessary rework (PR #24)** once
> issue #18's CORS smoke test proved that design infeasible. This section describes the **as-built**
> architecture — the original "browser fetches Yahoo directly" design is superseded, not just
> supplemented.

**What it is.** A static page on **GitHub Pages, same host as the detail page (§4.7)**, **access-
controlled** (FR19). Strictly **read-only** — no write path of any kind. Shows every watchlist ticker
grouped by market, each with a live price and (conditionally) its most recent verdict.

**Two independent reads per refresh cycle — architecture corrected in v14 (issue #18).**

1. **Live current price — now a server-published snapshot, not a direct browser fetch.** The original
   design assumed the browser could fetch Yahoo's price endpoint directly. **Issue #18's smoke test
   proved this false for all three markets**: Yahoo's `v8/finance/chart` returns `HTTP 200` with valid
   data when called server-side (confirmed via a GitHub Actions runner) but carries no
   `Access-Control-Allow-Origin` header, and a real headless-Chromium `fetch()` from a foreign origin
   fails outright (`TypeError: Failed to fetch`) — this is a property of Yahoo's server (it CORS-gates
   selectively, confirmed via `vary: Origin`), not a fixable client-side workaround.
   **As-built:** `publish-prices.yml` runs on the market cadence, fetches price + 1d change per
   watchlist ticker via the existing `yfinance` path (server-side, where it works), and commits
   `pages/prices.json` (`{generated_at, prices: {ticker: {price, chg, market, currency}}}`). The
   dashboard's `loadPrices()` reads this file via a **relative URL** — same-origin wherever GitHub
   Pages serves from, so no CORS involved at all. **Accepted freshness tradeoff:** "live" price is now
   "as of the last publish run" (the ~30-min market cadence), not tick-live: the "prices updated Ns
   ago" indicator keys off `prices.json`'s own `generated_at` field, which is an honest data-age
   signal rather than a browser-refresh-tick illusion of liveness. This is a **deliberate, documented
   downgrade from the original spec**, not a silent one — the UI copy reflects it.
2. **Last-run data** — the **most recent `call_log` row per ticker**, `ORDER BY timestamp DESC LIMIT
   1` per ticker, read from Supabase via the anon key. **The query does NOT filter on `alerted=true`**
   — it returns the latest row whatever its alert status, so the dashboard shows **what the system
   last *thought*, not only what it last *pushed*.** This is "how fresh is the verdict," and is
   unaffected by the read-1 architecture change — it was never Yahoo-dependent.

**Conditional last-run columns (FR21). Live, unchanged from original design.** For a ticker with
**zero `call_log` rows**, the last-run columns are **not rendered at all** — no placeholder, no empty
cells (the row's bottom block, `tc-bot`, is absent from the DOM, not CSS-hidden). As soon as **≥1 row
exists (any `alerted` value)**, the columns appear, showing: price at last check, verdict, rationale,
and relative time computed client-side from `call_log.timestamp` at render (FR21, §5).

**Layout contract (per UI handoff v3). Live, unchanged.** Tickers grouped **US & Canada** and **India
(NSE)** (separate, labelled groups); held vs watch-only shown by a badge sourced from
`watchlist.status` (text + icon, not colour alone). Native currency symbol per market (`$` / `CA$` /
`₹`), no FX. Mobile-first, ~480px cap.

**Auto-refresh (FR22). Live, semantics updated for the read-1 change.** A **configurable** timer
(build-time config, not hardcoded). On each tick: re-fetch `prices.json` (read 1) and re-read the
latest `call_log` per ticker (read 2). The "prices updated Ns ago" indicator now reflects
`prices.json`'s publish cadence rather than resetting on every browser tick — this is the honest
version of the original "resets each auto-refresh tick" behavior, corrected for the fact that a
browser refresh no longer implies a genuinely fresher price. The per-row "N ago" (verdict age, read 2)
is unaffected and remains visually distinct.

**Timestamps (FR23) — client-rendered, unchanged.** Device timezone primary + IST secondary in
brackets, deduped if the device is IST. Relative time is the primary per-row display; the absolute
dual-timezone string is secondary. All conversion is client-side from the UTC `call_log.timestamp`.

**Security. Live.** Read-only anon key scoped to `call_log` and `watchlist` only — no other table
reachable, no write access. **`watchlist` SELECT RLS policy applied (issue #16)** — the publishable
key can now read both tables the dashboard needs.

**Access control (FR19) — live (Requirements Decision #11, amended, ratified v13).** Client-side
SHA-256 passcode gate, session-scoped. Acknowledged as obfuscation, not real security — accepted given
the data is informational, read-only, and RLS-scoped to two tables (§2 item 7). Cloudflare Access
remains the documented upgrade path if data sensitivity ever rises.

**Schema.** No new tables or columns beyond the `watchlist` SELECT RLS policy (issue #16, above). The
`call_log.timestamp` UTC contract (§5) drives both the relative-time and absolute dual-timezone render.
