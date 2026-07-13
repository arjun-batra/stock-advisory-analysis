# Stock Advisory Agent — Requirements

**Owner:** pm (product) — Arjun is the stakeholder/single user.
**Source of truth provenance:** FR1–FR23 / NFR1–NFR4, the Problem/Goals/Scope sections, and the
Decisions Log below are **ported verbatim (lightly reformatted, no meaning changes)** from
`requirements_docs/stock-advisory-agent-requirements.md` (v5) during the multi-agent-template adoption
pass on 2026-07-12. The original v5 doc and its change-note history are retained untouched in
`requirements_docs/` as the historical record. The **Experimental Tracks** section (FR24+ / NFR5) is
new in this doc and covers the previously-undocumented shadow wallet pilot; it is explicitly **not part
of core v1 scope**. See the changelog at the bottom.

> **Numbering note:** Core requirement IDs (FR1–FR23, NFR1–NFR4) keep the exact numbering from v5 — do
> not renumber. New experimental IDs continue from where v5 leaves off (FR24 onward, NFR5 onward). Note
> that v5 has no FR-numbering gaps in §5 as ordered, but FR15/FR16 (Track Record) are grouped in §5.9
> below rather than in strict numeric position, exactly as in the source doc.

---

## 1. Problem Statement

Manual stock-checking is inconsistent and emotion-driven. The goal is a system that applies the same
disciplined judgment every time, on a personal watchlist, without requiring daily manual review.

## 2. Goals & Success Criteria

**Primary goal:** Catch a real, actionable signal on a held or watched stock that would otherwise have
been missed by manual checking.

**Success criteria:** Within 3 months, at least one verdict the system surfaced is later validated as
correct and would not have been caught manually. This requires the system to log calls — see §5.9
(resolved: logging is in for v1, since it's the only way to prove this criterion).

## 3. Scope

### In scope
- Single-user personal advisory tool (Arjun only, no multi-user/shared access)
- Watchlist of 5–15 tickers per market: US, Canadian (TSX), and India (NSE) listed stocks and ETFs
- User-maintained holdings data: shares owned + cost basis per position
- AI-driven discovery of new candidates beyond the explicit watchlist, using a computational prefilter
  to shortlist candidates before AI evaluation, across all three markets
- Regular intraday checks during each market's trading hours
- Buy / Sell / Hold verdict + one-line rationale per alert
- Push notification delivery — US/TSX and NSE on separate ntfy topics
- AI judgment grounded in price/volume, news, and fundamentals — no fixed buy/sell rules, no fixed
  investment style
- Read-only dashboard (GitHub Pages) showing all tickers grouped by market with a near-live price
  (server-published snapshot, refreshed on the market cadence — see FR21/Decision #18) and last run
  verdict

### Out of scope (explicit)
- Trade execution or order placement of any kind
- Brokerage account integration or read access — holdings are entered manually
- Options, crypto, derivatives, or any asset class beyond stocks/ETFs
- Multi-user or shared/team access
- Licensed financial advice — this is a personal informational tool, not a registered advisory service

## 4. Users

One user: Arjun. No external users, no handoff to another team — this doc exists as a solo build
reference, not a spec for a contractor.

## 5. Functional Requirements

### 5.1 Watchlist & Holdings
- **FR1** — Maintain a watchlist of stocks/ETFs across three markets: US, Canadian (TSX), and India
  (NSE). Each ticker is identified by its market so market-specific gating and grouping can be applied
  correctly.
- **FR2** — For held positions, record shares owned and cost basis; this personalizes the verdict
  (e.g., gain/loss context relative to entry).
- **FR3** — Tickers can be watch-only (no position held, no cost basis required).

### 5.2 Candidate Discovery
- **FR4** — Periodically scan beyond the explicit watchlist for AI-flagged candidates across all three
  markets (US, TSX, NSE). A computational prefilter shortlists candidates before AI evaluation using
  four signals: significant price movers, volume spikes above the recent average, earnings announcements
  within a near-term window, and price proximity to the 52-week high or low. A candidate that trips at
  least one signal (and clears quality gates on market cap, price, volume, and listing exchange) reaches
  the AI. The AI then evaluates only this shortlist and decides which candidates are worth surfacing —
  no fixed buy/sell criteria. Of the AI's verdicts, only Buy results generate a push notification; Hold
  and Sell verdicts from discovery are logged silently. Specific thresholds for signals and quality
  gates are tunable at build time. Runs on a separate daily cadence, decoupled from the intraday
  watchlist loop (discovery isn't time-sensitive, and decoupling roughly halves AI call volume vs.
  running both scans on the same cadence).
- **FR5** — Discovered candidates are clearly labeled as "new candidate" vs. "watchlist update" when
  delivered.

### 5.3 Monitoring & Triggering
- **FR6** — Checks run every 30 minutes during market hours. No fixed daily/weekly digest format.
- **FR7** — Any verdict change triggers an immediate alert — Buy, Sell, or Hold transitions all qualify,
  including a change *to* Hold (a held Buy weakening to Hold is itself a signal). No cooldown, no
  debounce, no delay.
- **FR8** — If a check returns the same verdict as the previous check, no alert fires and no
  notification is sent. There is no cooldown, no debounce, and no periodic standing-verdict reminder —
  "no change → silence" is absolute. On a choppy day, a verdict that oscillates will push on every flip;
  this is accepted behavior, not a bug.

### 5.4 AI Analysis
- **FR9** — Verdicts are generated by AI judgment from price/volume data, recent news, and fundamentals
  — not fixed deterministic rules.
- **FR10** — No fixed investment style or horizon is assumed; the model weighs each call per stock's own
  context.
- **FR11** — For held positions, reasoning incorporates cost basis and position size (e.g., flags how a
  call relates to current gain/loss).

### 5.5 Alerting & Delivery
- **FR12** — Alerts delivered via push notification (e.g., ntfy.sh or Pushover) rather than SMS —
  removes the need for any SMS provider/Twilio account, and push naturally supports a tap-through link.
- **FR13** — Alert format: Buy/Sell/Hold + one-line rationale in the notification body. No long-form
  reasoning inline.
- **FR14** — Each notification links to a simple page showing the full reasoning behind that call,
  pulled directly from the log in §5.9. Natural fit for push (tap-through), avoids building two-way SMS
  infra.

### 5.6 NSE-Specific Behavior
- **FR17** — Checks for NSE tickers respect NSE market hours (fixed UTC window, no DST). NSE holidays
  are not separately detected via a maintained calendar — same as US/TSX, a holiday closure surfaces as
  no usable data and falls through the generic skip-with-log path: no alert, clean no-op.
- **FR18** — NSE alerts are delivered on a separate ntfy topic from US/TSX alerts. Both topics land in
  the same app on the same device; the separation exists so NSE and US/TSX notifications can be
  filtered, muted, or managed independently.

### 5.7 Dashboard
- **FR19** — A read-only dashboard is hosted on GitHub Pages (same host as the detail page, FR14). It is
  access-controlled via a client-side JS password gate — accepted as sufficient for v1 given the
  dashboard's data is informational, read-only, and RLS-scoped to two tables; unauthenticated public
  access is not acceptable.
- **FR20** — Tickers are grouped by market: US/TSX in one group, NSE in a separate group. Within each
  group, holdings and watch-only tickers are visually differentiated via a badge or label on each row —
  not by position or color alone, so the distinction is legible at a glance.
- **FR21** — Each ticker row displays: current price — refreshed from a server-published snapshot on the
  ~30-min market cadence (the browser cannot fetch the price source directly; accepted freshness
  posture, Decision #18 / SD §13) — and last run price, verdict, rationale, and relative time (e.g. "2
  hours ago", "3 days ago") sourced from the most recent call log entry for that ticker, regardless of
  whether an alert was sent. The dashboard's "prices updated" indicator reflects the snapshot's own
  generation time, so the displayed age is the real data age. The last-run columns are hidden entirely
  for a ticker until at least one check has completed for it — no placeholder, no empty cells.
- **FR22** — The dashboard auto-refreshes on a configurable timer while the page is open. The refresh
  interval is a build-time configuration, not hardcoded.

### 5.8 Timestamps & Timezone
- **FR23** — Timestamps behave differently across surfaces because push notifications are formatted
  server-side (no device timezone available) while the detail page and dashboard are client-rendered
  (device timezone is available via the browser).
  - **Push notifications:** timestamp uses the market's own timezone — ET for US/TSX alerts, IST for NSE
    alerts. Single timezone only, no secondary. Format: `10:30 AM ET` or `8:00 PM IST`.
  - **Detail page and dashboard:** timestamp shows the user's device timezone as primary (auto-detected
    by the browser) and IST as a fixed secondary in brackets. Format: `10:30 AM ET (8:00 PM IST)`. If
    the device timezone is already IST, only one timestamp is shown — no duplicate.

### 5.9 Track Record
- **FR15** — Every check writes a log row: ticker, verdict, timestamp, key data points used, and whether
  an alert was sent. This includes no-change and cold-start checks (logged with alert=false) — not only
  the checks that push a notification. The full log is what makes §2's success criterion auditable.
- **FR16** — Logging is confirmed in for v1 — it's the only way to validate §2's success criterion. Kept
  minimal: no accuracy dashboard or analytics layer in v1.

## 6. Non-Functional Requirements

- **NFR1 — Cost:** Target $0–15/month. Checks every 30 minutes against free-tier data APIs keeps this
  realistic; push notification services (ntfy.sh is free, Pushover is a small one-time fee per platform)
  remove the per-message SMS cost entirely.
- **NFR2 — Reliability:** The system actively alerts the user when a scheduled run is missed, fails to
  trigger, or completes degraded — silence from the monitor means healthy. Passive "last run" visibility
  is not sufficient; a run that never triggers must surface as loudly as one that runs and fails.
- **NFR3 — Disclaimer:** Every alert is informational, not licensed financial advice. No regulatory
  registration is implied or required for personal use.
- **NFR4 — Data freshness:** The 30-minute cadence means up to ~30 minutes of lag is acceptable. This
  system is not suited for intraday/fast-moving trade timing — that was explicitly traded away for
  cost/simplicity.

## 7. Data Sources

- **Price/volume:** Yahoo Finance unofficial API — covers US tickers, TSX (`.TO` suffix), and NSE
  (`.NS` suffix), free. Confirmed as the v1 source for all three markets.
- **News:** free headline/news feed.
- **Fundamentals:** free-tier basic financials/earnings data (same source as price/volume where
  possible).
- **Known risk:** Yahoo Finance's API is unofficial — no SLA, no guarantee it stays available or that
  TSX/NSE fundamentals data is complete. A smoke test against real tickers from each market is a
  mandatory day-one check before building on top of it.

## 8. Decisions Log (Resolved)

| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Track record logging | In, minimal (no dashboard/analytics in v1) | Only way to validate the success criterion in §2 |
| 2 | Re-alert/dedup logic | Single rule: any verdict change → immediate alert; no change → silence. No cooldown, no debounce, no standing-verdict reminder. | Cooldown + reminder added state that wasn't earning its keep on a single-user push tool. Tradeoff accepted: a choppy day may produce bursts of alerts on every verdict flip. |
| 3 | Detail-on-request | Tap-through link from the push notification to a page reading from the log | Avoids two-way SMS infra; fits push naturally |
| 4 | Discovery scan cadence | Daily, decoupled from the intraday watchlist loop | Discovery isn't time-sensitive; roughly halves AI call volume |
| 5 | Data vendor | Yahoo Finance unofficial API (price/volume/fundamentals, US + TSX + NSE) | Free, covers all three markets; unofficial-API risk noted in §7; smoke test mandatory per market before build |
| 6 | Notification channel | Push notification (ntfy.sh or Pushover), not SMS | Cheaper than SMS, no Twilio/CA-number dependency, supports tap-through links for detail-on-request |
| 7 | NSE notification separation | Separate ntfy topic from US/TSX (same app, same device) | Allows NSE and US/TSX alerts to be filtered or muted independently without needing a second device or app |
| 8 | NSE holiday handling | Skip-with-log, same posture as US/TSX holidays and weekends | Consistent behavior across all markets; no alert, no crash, logged for auditability |
| 9 | NSE discovery | Included in the daily scan alongside US/TSX candidates | Same behavioral rules apply to all markets; no reason to treat NSE discovery differently |
| 10 | Dashboard hosting | GitHub Pages, same host as the detail page | Free, no new infra; static constraint means auth mechanism is a build-time decision |
| 11 | Dashboard access | Access-controlled via a client-side JS password gate — accepted as sufficient for v1 given the data is informational, read-only, and RLS-scoped to two tables. | Personal data; unauthenticated public access not acceptable even though it's informational |
| 12 | Dashboard price refresh | Auto-refresh on configurable timer while page is open | "Current price" needs to stay fresh during an active session; interval is a tunable, not hardcoded |
| 13 | Dashboard last-run columns | Hidden until at least one check has completed for that ticker | No placeholder noise for cold-start tickers with no call log entries yet; columns appear as soon as the system has run once for that ticker, regardless of whether it alerted |
| 14 | Discovery prefilter criteria | Four signals: price movers + volume spikes + earnings proximity + 52-week high/low proximity; thresholds tunable at build time; candidate must trip ≥1 signal and clear quality gates (market cap, price, volume, exchange) to reach the AI; quality gate thresholds also tunable | Narrows universe to a manageable AI shortlist without hardcoding buy/sell logic; 52-week-extreme canonicalized from implemented code |
| 15 | Timestamp display | Notifications: single timezone, market-specific (ET for US/TSX, IST for NSE). Detail page + dashboard: device auto-detect as primary, IST as secondary in brackets; dedup if device is already IST | Server can't detect device timezone at send time; market timezone is the correct anchor for notifications. Client-rendered surfaces can do auto-detect so both timezones are always visible |
| 16 | Discovery verdict suppression | Buys only generate a push notification from discovery; Hold and Sell verdicts are logged silently | A Sell on a stock you don't own is noise; Hold from discovery is not actionable; only Buy surfaces a new candidate worth knowing about |
| 17 | Detail-page access control | Unguessable UUID URL only, no auth gate. FR19's access-control requirement applies to the dashboard, not the detail page. | Detail page is read-only/informational (NFR3); UUID-only is a deliberate accepted posture for this surface, not an oversight |
| 18 | Dashboard "current price" freshness | Server-published snapshot (`prices.json`) refreshed on the ~30-min market cadence, read same-origin by the dashboard; the "prices updated" age keys off the snapshot's `generated_at`. | Yahoo's price API is browser-CORS-blocked for all three markets (SD issue #18) — a direct client fetch is infeasible. Publish-cadence freshness matches the system's own 30-min cadence posture (NFR4); the honest data-age indicator was preferred over a refresh-tick illusion of liveness |

## 9. Out of Scope — Explicit Confirmation

No trade execution. No brokerage integration. No options/crypto/derivatives. No multi-user access. Not a
registered advisory service. These are hard boundaries for v1, not soft preferences.

---

## 10. Experimental Tracks (NOT core v1 scope)

> **Status:** Experimental / non-production. The requirements in this section describe a pilot that runs
> alongside the production system but is explicitly **outside core v1 scope** (§3). These IDs
> (FR24–FR30, NFR5) were added during the 2026-07-12 adoption pass to document previously-undocumented
> shadow-wallet code that already ships in the repo. Nothing here may weaken or alter any FR1–FR23 /
> NFR1–NFR4 behavior; the pilot's whole design premise is that it is invisible to production.

### 10.1 Shadow Wallet Pilot

**Context.** A parallel, non-production AI verdict track ("shadow wallet") for US/CA (TSX) watchlist
tickers only. It reuses production's already-fetched market-data snapshot from the same cycle and
production's model-call machinery (same Gemini model, timeout, and retry config), but swaps in a
position-aware prompt variant. Files: `scripts/shadow.py`, `scripts/run_shadow.py`,
`sql/shadow_call_log_migration.sql`, shadow vars in `scripts/config.py`, and a shadow step in
`.github/workflows/hourly-watchlist.yml`.

- **FR24 — Existence & purpose.** The system MAY run a shadow verdict track that produces an independent
  Buy/Sell/Hold verdict per US/CA watchlist ticker using a *position-aware* prompt variant, for the sole
  purpose of A/B testing whether position-awareness changes verdict quality/behavior versus production's
  current watch-only-style prompt. It MUST cover US/CA (TSX) watchlist tickers only and MUST NOT include
  NSE tickers.
- **FR25 — Self-derived simulated position ("wallet-walk").** The shadow track MUST track its own
  simulated buy/sell position per ticker, derived *purely from its own prior shadow history*: a Buy
  flips flat→holding, a Sell flips holding→flat, a Hold is a no-op. When the model issues a Sell against
  a simulated holding, the prompt variant MUST require it to cite a specific reversal-since-entry. The
  simulated position going into each call MUST be recorded (state, entry price, entry date) so the exact
  context given to the model is auditable.
- **FR26 — Same-data reuse.** To isolate the position-awareness variable, the shadow call MUST judge the
  *same* market-data snapshot production judged in that cycle, reusing production's persisted snapshot
  rather than re-fetching. The lookback window used to locate that snapshot is configurable (see
  Configuration) and MUST stay under one dispatch cadence step so it can never pick up a prior cycle's
  snapshot.
- **FR27 — Isolated storage; no dashboard/anon read path (HARD).** The shadow track MUST write only to
  its own dedicated table (`call_log_shadow`), never to production's `call_log`. That table MUST have
  RLS enabled with **no** anon/authenticated policy or grant, so it is readable/writable *only* by the
  server secret key (which bypasses RLS). It MUST NOT be readable by the anon/dashboard (publishable)
  key. There MUST be no read path from the shadow table into the dashboard, the GitHub Pages output, or
  any notification channel.
- **FR28 — MUST NOT alert (HARD).** The shadow track MUST NOT send any alert or push notification on any
  channel. It does not import or invoke any notification code; `alerted` is always false on this track.
- **FR29 — MUST NOT affect production if it fails (HARD).** A shadow failure, hang, or timeout MUST NOT
  affect or block the production pipeline. The shadow step MUST run strictly *after* production's step in
  the same workflow and MUST be `continue-on-error: true` so a shadow fault can never fail the run.
  Real holdings / cost-basis data MUST NOT leak into shadow rows.
- **FR30 — Kill switch.** The shadow track MUST be gated by a kill switch (`SHADOW_ENABLED`) checked both
  at the workflow-step level and again in code, so it can be disabled with a zero-code-change config
  flip. **Accepted risk (recorded, not hidden):** the kill switch defaults **fail-OPEN, but only on a
  truly unset/empty Variable** — when the `SHADOW_ENABLED` GitHub Variable is unset or empty, the value
  resolves to `true` and the pilot runs. This is a deliberate choice (toggling off is a one-Variable
  opt-out). Any explicitly-set value that is not the literal (case- and whitespace-insensitive) string
  `true` disables the pilot: `false`, and *any other non-empty value including a typo* (e.g. `flase`,
  `no`, `0`), all **fail CLOSED** and stop the pilot. So the only fail-open case is a genuinely
  absent/empty Variable; a mistyped or deleted-and-recreated-with-garbage Variable stops the pilot
  rather than silently keeping it running. This residual fail-open-on-empty risk is accepted for the
  pilot and is recorded here as a requirement-level item (mirroring the SD.md §2 accepted-risk style),
  not left implicit in a code comment.

### 10.2 Shared Evaluation Method (both shadow tracks — in scope)

- **FR31 — Committed, reproducible evaluation method (both shadow tracks).** The entire purpose of the
  shadow pilots is comparing shadow vs. production verdict/wallet performance, but no committed, versioned
  evaluation mechanism exists in the repo. The `call_log_shadow` SQL migration's own comments reference a
  "wallet-sim recursive-CTE walk" and a "wallet-sim harness" that do **not** exist anywhere in the
  codebase (verified across `sql/`); they are described as living only in the ad hoc Supabase SQL editor.
  There is therefore no reproducible way to actually run the evaluation the pilots exist for.
  **Requirement:** a defined, committed, reproducible evaluation method (the wallet-sim walk/harness,
  versioned in the repo as SQL/scripts) MUST exist, and it MUST cover **both** the US/CA shadow track
  (`call_log_shadow`, FR24–FR30) **and** the NSE shadow track (`call_log_shadow_nse`, FR32–FR39). Neither
  shadow pilot can graduate to any production consideration until this evaluation method exists and is
  demonstrated reproducible. **Owner:** dev (to commit the wallet-sim walk/harness as versioned
  SQL/scripts covering both tracks), with qa to define and verify the evaluation is reproducible.
  **Status (2026-07-13 change request):** upgraded from an open [REQUIREMENTS-GAP] to an in-scope
  requirement — the user explicitly pulled the evaluation method into scope as part of the NSE-shadow
  change request (decision #5). It is no longer a deferred gap; it is deliverable work for this change.

### 10.3 NSE Shadow Wallet Pilot (NOT core v1 scope)

> **Status:** Experimental / non-production. Added 2026-07-13 by user change request: run an independent
> shadow-wallet experiment on NSE tickers, mirroring the US/CA pilot (§10.1) but as a fully separate
> track. Same hypothesis (position-aware prompt vs. production's watch-only-style prompt), applied to NSE
> watchlist tickers (decision #1). Nothing here may weaken or alter any FR1–FR23 / NFR1–NFR4 behavior,
> and it must not affect production **or** the US/CA shadow track (§10.1).

**Context.** A second parallel, non-production AI verdict track ("NSE shadow wallet") for NSE watchlist
tickers only. Like §10.1 it reuses production's already-fetched market-data snapshot from the same cycle
and production's model-call machinery, and swaps in the same position-aware prompt variant — the only
change from §10.1 is that it operates on NSE tickers, writes to its own dedicated table, and is gated by
its own kill switch and NSE market hours. The specific model/quota bucket used for the NSE shadow call is
a design detail deferred to tech-lead (the user did not require an NSE-specific model pairing — decision
#1).

- **FR32 — Existence & purpose.** The system MAY run an NSE shadow verdict track that produces an
  independent Buy/Sell/Hold verdict per **NSE** watchlist ticker using the same *position-aware* prompt
  variant as §10.1, for the sole purpose of A/B testing whether position-awareness changes verdict
  quality/behavior versus production's current watch-only-style prompt. It MUST cover NSE watchlist
  tickers only and MUST NOT include US or TSX tickers (those belong to the §10.1 track).
- **FR33 — Self-derived simulated position ("wallet-walk").** The NSE shadow track MUST track its own
  simulated buy/sell position per ticker, derived *purely from its own prior NSE-shadow history* (in
  `call_log_shadow_nse`): a Buy flips flat→holding, a Sell flips holding→flat, a Hold is a no-op. When
  the model issues a Sell against a simulated holding, the prompt variant MUST require it to cite a
  specific reversal-since-entry. The simulated position going into each call (state, entry price, entry
  date) MUST be recorded so the exact context given to the model is auditable. This history MUST be
  derived solely from `call_log_shadow_nse` — never from `call_log`, never from `call_log_shadow`.
- **FR34 — Same-data reuse.** To isolate the position-awareness variable, the NSE shadow call MUST judge
  the *same* market-data snapshot production judged for NSE tickers in that cycle, reusing production's
  persisted snapshot rather than re-fetching. The lookback window used to locate that snapshot is
  configurable (see Configuration) and MUST stay under one dispatch cadence step so it can never pick up
  a prior cycle's snapshot.
- **FR35 — Isolated storage; no dashboard/anon read path (HARD).** The NSE shadow track MUST write only
  to its own dedicated table (`call_log_shadow_nse`), never to `call_log` and never to `call_log_shadow`.
  That table MUST have RLS enabled with **no** anon/authenticated policy or grant, so it is
  readable/writable *only* by the server secret key (which bypasses RLS). It MUST NOT be readable by the
  anon/dashboard (publishable) key. There MUST be no read path from the NSE shadow table into the
  dashboard, the GitHub Pages output, or any notification channel. (Mirrors FR27's isolation pattern for
  the new table.)
- **FR36 — MUST NOT alert (HARD).** The NSE shadow track MUST NOT send any alert or push notification on
  any channel (including the NSE ntfy topic, FR18). It does not import or invoke any notification code;
  `alerted` is always false on this track. (Mirrors FR28.)
- **FR37 — MUST NOT affect production OR the US/CA shadow track if it fails (HARD).** An NSE shadow
  failure, hang, or timeout MUST NOT affect or block the production pipeline, and MUST NOT affect the
  US/CA shadow track (§10.1) either. The three tracks are mutually isolated: a fault, hang, timeout, or
  kill-switch flip in any one MUST NOT be able to take down either of the others. The NSE shadow step MUST
  run in a way that a fault in it cannot fail the run (e.g. strictly after production and
  `continue-on-error`, the mechanism being a design detail for tech-lead), and its execution MUST be
  structurally separate from the US/CA shadow track's execution. Real holdings / cost-basis data MUST NOT
  leak into NSE shadow rows. (Extends FR29 with the additional cross-shadow-track isolation the user
  required — decision #3.)
- **FR38 — Independent kill switch.** The NSE shadow track MUST be gated by its own independent kill
  switch (`SHADOW_NSE_ENABLED`), separate from the US/CA track's `SHADOW_ENABLED`, so the NSE track can be
  toggled without touching the US/CA track and vice versa. It MUST be checked both at the workflow-step
  level and again in code, so it can be disabled with a zero-code-change config flip. **Accepted risk
  (recorded, not hidden), mirroring FR30:** the kill switch defaults **fail-OPEN, but only on a truly
  unset/empty Variable** — when the `SHADOW_NSE_ENABLED` Variable is unset or empty, the value resolves to
  `true` and the NSE pilot runs. Any explicitly-set value that is not the literal (case- and
  whitespace-insensitive) string `true` disables the NSE pilot (`false`, or *any other non-empty value
  including a typo* such as `flase`, `no`, `0`, all **fail CLOSED**). So the only fail-open case is a
  genuinely absent/empty Variable. This residual fail-open-on-empty risk is accepted for the NSE pilot,
  the same accepted-risk shape as FR30, recorded here at requirement level (decision #4).
- **FR39 — NSE market-hours gating.** The NSE shadow track MUST be gated by the same NSE market-hours
  window production uses for NSE (fixed IST window, no DST — see FR17). Outside that window (and absent a
  force-run), the NSE shadow track is a clean no-op. NSE holidays are not separately detected; a closure
  surfaces as no usable data and falls through the skip-with-log path, same posture as production NSE
  (FR17).

## 11. Configuration (tunables audit baseline)

All user-tunable values live in the config surface (`scripts/config.py`, values read from environment /
GitHub Actions secrets & Variables — nothing sensitive hardcoded). This section is the reviewer's
hardcoding-audit baseline. Values below are the current defaults as documented in code/SD; they are
tunables, not fixed requirements.

### Core system
| Key | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.5-flash` | Primary watchlist AI model |
| `GEMINI_MODEL_BACKUP` | `gemini-3.1-flash-lite` | Fallback model (empty disables fallback) |
| `NSE_GEMINI_MODEL` / `NSE_GEMINI_MODEL_BACKUP` | inherit US/TSX pair | NSE watchlist model pair (quota isolation option) |
| `DISCOVERY_GEMINI_MODEL` / `_BACKUP` | `gemini-2.5-flash` / `-lite` | Discovery model pair (separate daily quota bucket) |
| `GEMINI_TIMEOUT_MS` | `180000` | Per-request Gemini timeout (ms) |
| `GEMINI_MAX_RETRIES` | `3` | Retries after the initial Gemini attempt |
| `GEMINI_RETRY_BASE_MS` | `10000` | Exponential backoff base delay (ms), full jitter |
| `NTFY_TOPIC` | (secret) | US/TSX push topic |
| `NSE_NTFY_TOPIC` | (secret, falls back to `NTFY_TOPIC`) | NSE push topic |
| `DETAIL_PAGE_BASE` | (env) | Base URL for tap-through detail page |
| `ALERTS_ENABLED` | `false` | Master switch for real pushes |
| `FORCE_RUN` | `false` | Manual override to run when market closed (testing/backfill) |
| `MIN_HISTORY_ROWS` | `21` | Sessions needed for 20-day metrics |
| `YF_PACING_SECONDS` | `2` | Per-ticker pacing for Yahoo fetch |
| `YF_BACKOFF_SECONDS` | `10` | Backoff on Yahoo rate-limit error |
| `YF_HISTORY_RETRIES` | `2` | Retry attempts for Yahoo price-history fetch |
| `YF_HISTORY_PERIOD` | `3mo` | Look-back window for Yahoo price-history fetch |
| `HEADLINES_LIMIT` | `5` | Max headlines pulled per ticker for AI context |
| `NOTIF_BODY_MAX` | `150` | Max chars in a push-notification body |
| `RATIONALE_MAX` | `280` | Max chars in an AI rationale string |
| `MARKET_OPEN` / `MARKET_CLOSE` | `09:30` / `16:00` ET | US/TSX session bounds |
| `NSE_MARKET_OPEN` / `NSE_MARKET_CLOSE` | `09:15` / `15:30` IST | NSE session bounds |
| `RUNTIME_CLOSE_GRACE_MIN` | `10` | Runtime close-grace minutes (dispatch-to-execution latency) |

### Discovery prefilter / quality gates (all tunable)
| Key | Default | Purpose |
|---|---|---|
| `DISCOVERY_MIN_MARKET_CAP` | `2000000000` ($2B) | US/CA market-cap floor |
| `DISCOVERY_MIN_PRICE` | `5` ($5) | US/CA price floor |
| `DISCOVERY_MIN_VOLUME` | `500000` | US/CA daily volume floor |
| `DISCOVERY_ALLOWED_EXCHANGES` | NYSE/Nasdaq/Toronto set | Allowed primary exchanges |
| `DISCOVERY_ALLOWED_EXCHANGES_IN` | `{NSI}` | NSE-only filter (drops BSE dups) |
| `DISCOVERY_MIN_MARKET_CAP_INR` | `50000000000` (₹5e10) | NSE market-cap floor |
| `DISCOVERY_MIN_PRICE_INR` | `50` | NSE price floor (rupees) |
| `DISCOVERY_GAINER_PCT` / `DISCOVERY_LOSER_PCT` | `5` / `-5` | Mover thresholds (%) |
| `DISCOVERY_VOL_SPIKE` | `2.0` | Volume-spike multiple of 3-month avg |
| `DISCOVERY_52W_PROXIMITY` | `0.02` | 52-week-extreme proximity fraction |
| `DISCOVERY_EARNINGS_DAYS` | `7` | Earnings-proximity window (days) |
| `DISCOVERY_EARNINGS_RECENT_DAYS` | `2` | Recent-earnings look-back window (days) |
| `DISCOVERY_SHORTLIST_MAX` | `15` | Max candidates in the daily batch |
| `DISCOVERY_PUSH_COOLDOWN_DAYS` | `7` | Per-candidate re-push cooldown (days) |
| Dashboard refresh interval | build-time config (FR22) | Auto-refresh timer while page open |

### Experimental — shadow wallet pilot
| Key | Default | Purpose |
|---|---|---|
| `SHADOW_ENABLED` | `true` when unset/empty (fail-OPEN-on-empty — accepted risk, FR30) | Kill switch; enabled only on unset/empty or literal `true`; `false` or any other non-empty value (incl. typos) disables (fails closed) |
| `SHADOW_PROMPT_VARIANT` | `position_aware_v1` | Prompt-variant tag written to `call_log_shadow.prompt_variant` |
| `SHADOW_SNAPSHOT_LOOKBACK_MIN` | `20` | Lookback window to reuse the same-cycle production snapshot (must stay under the 30-min cadence) |

### Experimental — NSE shadow wallet pilot (§10.3)
| Key | Default | Purpose |
|---|---|---|
| `SHADOW_NSE_ENABLED` | `true` when unset/empty (fail-OPEN-on-empty — accepted risk, FR38) | Independent kill switch for the NSE shadow track; enabled only on unset/empty or literal `true`; `false` or any other non-empty value (incl. typos) disables (fails closed). Separate from `SHADOW_ENABLED` |
| `SHADOW_NSE_PROMPT_VARIANT` | `position_aware_v1` | Prompt-variant tag written to `call_log_shadow_nse.prompt_variant` (same variant as §10.1) |
| `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN` | `20` | Lookback window to reuse the same-cycle production NSE snapshot (must stay under the NSE dispatch cadence) |

> **Note (for tech-lead):** the exact model/quota bucket the NSE shadow call uses (production NSE's
> `NSE_GEMINI_MODEL` pair vs. the US/CA `GEMINI_MODEL` pair the §10.1 shadow reuses) is a design decision,
> not fixed by this change request — the user did not require an NSE-specific model pairing (decision #1).
> Resolve it in design.md; if it needs a user trade-off (e.g. free-tier quota pressure), route it back to
> pm.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-07-12 | **Adoption-pass port.** Created `docs/requirements.md` by porting FR1–FR23 / NFR1–NFR4, the Problem/Goals/Scope sections, and the full Decisions Log (#1–#18) verbatim (lightly reformatted, no meaning changes) from `requirements_docs/stock-advisory-agent-requirements.md` (v5). Original v5 doc retained untouched in `requirements_docs/` as historical record. Added a Configuration section (§11) as the reviewer hardcoding-audit baseline, populated from `scripts/config.py` and SD.md. | Multi-agent-template adoption: port current source-of-truth docs into the new `docs/` locations without altering meaning. |
| 2026-07-12 | **New Experimental Tracks section (§10).** Added FR24–FR30 + NFR5 for the previously-undocumented shadow wallet pilot, and FR31 [REQUIREMENTS-GAP] for its missing evaluation method. IDs continue from where v5 (FR23/NFR4) leaves off; FR1–FR23/NFR1–NFR4 numbering unchanged. Marked explicitly as experimental / non-production, outside core v1 scope. Recorded the kill-switch fail-open default as an accepted risk (FR30 / NFR5). | Documenting shipped-but-undocumented shadow code as explicit requirements per user decision #2, with hard non-production/isolation constraints and the flagged evaluation gap. |
| 2026-07-12 | **Synced §11 audit baseline with 6 newly-extracted tunables.** Added `YF_HISTORY_RETRIES` (`2`), `YF_HISTORY_PERIOD` (`3mo`), `HEADLINES_LIMIT` (`5`), `NOTIF_BODY_MAX` (`150`), `RATIONALE_MAX` (`280`) to the Core system table and `DISCOVERY_EARNINGS_RECENT_DAYS` (`2`) to the Discovery prefilter table. Each default equals the literal it replaced (no behavior change from these keys). Baseline-only sync; no new/changed FR/NFR. | Dev's debt-cleanup pass moved these previously-hardcoded literals into `scripts/config.py` as env-overridable tunables, resolving reviewer findings REV-007–REV-012; the hardcoding-audit baseline table must list every tunable. |
| 2026-07-13 | **Change request — NSE shadow wallet pilot (new §10.3, FR32–FR39, NFR6) + FR31 upgraded to in-scope.** User (Arjun) requested an independent shadow experiment on NSE stocks mirroring the US/CA shadow pilot. Added §10.3 with FR32 (existence/purpose — same position-aware hypothesis, NSE tickers only), FR33 (self-derived wallet-walk from `call_log_shadow_nse`), FR34 (same-cycle NSE snapshot reuse), FR35 (isolated `call_log_shadow_nse` table, RLS/no-anon-read — HARD), FR36 (never alerts — HARD), FR37 (must not affect production **or** the US/CA shadow track — HARD, cross-track isolation), FR38 (independent `SHADOW_NSE_ENABLED` kill switch, same fail-open-on-empty accepted risk as FR30), FR39 (NSE market-hours gating per FR17). Added NFR6 mirroring NFR5 for the NSE track incl. mutual isolation of all three tracks. Added `SHADOW_NSE_ENABLED` / `SHADOW_NSE_PROMPT_VARIANT` / `SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN` to §11. **Upgraded FR31 from an open [REQUIREMENTS-GAP] to an in-scope requirement** (renamed §10.2 to "Shared Evaluation Method"): the committed, versioned, reproducible wallet-sim harness must now be delivered as part of this change and must cover BOTH shadow tracks. Grounded in the 5 user decisions relayed 2026-07-13: (1) same hypothesis, NSE tickers, no NSE-specific model requirement; (2) new dedicated `call_log_shadow_nse` table; (3) isolated from production AND the US/CA shadow track; (4) independent kill switch, same fail-open-on-empty posture; (5) evaluation method pulled into scope, covering both tracks. Model/quota-bucket choice for the NSE shadow call flagged to tech-lead as a design decision. Core FR1–FR23/NFR1–NFR4 untouched; still explicitly outside core v1 scope. | User change request per CLAUDE.md Change Requests process; all ambiguities resolved by the user before writing (no-inference rule satisfied). |
| 2026-07-12 | **Corrected kill-switch behavior wording (FR30, NFR5, §11 config table).** Fixed the factually-wrong claim that a *mistyped* `SHADOW_ENABLED` Variable silently keeps the pilot running. The actual code (`scripts/config.py:65`, `(... or "true") == "true"`) fails open ONLY on a truly unset/empty Variable; any explicitly-set-but-wrong value — including a typo like `flase`, `no`, or `0` — compares unequal to `true` and fails **closed**, disabling the pilot. Accepted-risk framing retained; only the factual description was corrected (fail-open scope narrowed to unset/empty). No change to the requirement itself or the risk-acceptance decision. | Resolving REV-001 (major) / BUG-001 doc-vs-code contradiction via user's chosen Option B (correct the docs, not the code). |

> **Open item flagged for the user:** FR31's evaluation-method requirement is now **in scope** (pulled in
> by the 2026-07-13 change request) rather than a deferred gap — it must be delivered covering both shadow
> tracks. FR30/FR38's fail-open-on-empty kill-switch defaults remain recorded accepted risks. If the user
> wants either shadow pilot to graduate or be retired, that is a user decision — captured here so it is
> not silently defaulted.

---

## NFR — Experimental

- **NFR5 — Shadow pilot isolation & fail-open posture (non-production).** The shadow pilot MUST remain
  operationally invisible to production: no alerts (FR28), no anon/dashboard read path (FR27), no
  ability to fail the production pipeline (FR29). Its kill switch defaults fail-open (FR30) — an
  **accepted risk** recorded explicitly at requirement level, but scoped precisely: only an *unset or
  empty* `SHADOW_ENABLED` Variable leaves the pilot running. Any explicitly-set-but-wrong value
  (including a typo such as `flase`) fails **closed** and stops the pilot, which is the safer outcome.
  This posture is acceptable only while the pilot is fully isolated per FR27–FR29; if any isolation
  guarantee is weakened, the fail-open-on-empty default MUST be revisited.

- **NFR6 — NSE shadow pilot isolation & fail-open posture (non-production).** The NSE shadow pilot
  (§10.3) MUST remain operationally invisible to production AND to the US/CA shadow pilot: no alerts
  (FR36), no anon/dashboard read path (FR35), no ability to fail the production pipeline or the US/CA
  shadow track (FR37). The three tracks (production, US/CA shadow, NSE shadow) MUST be mutually isolated
  so a fault or kill-switch flip in one can never take down another. The NSE track's kill switch defaults
  fail-open (FR38) — an **accepted risk** recorded explicitly at requirement level, scoped precisely to
  only an *unset or empty* `SHADOW_NSE_ENABLED` Variable; any explicitly-set-but-wrong value (including a
  typo) fails **closed** and stops the NSE pilot, the safer outcome. This posture is acceptable only
  while the NSE pilot is fully isolated per FR35–FR37; if any isolation guarantee is weakened, the
  fail-open-on-empty default MUST be revisited.
