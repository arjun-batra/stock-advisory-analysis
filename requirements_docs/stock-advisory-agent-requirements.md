# Stock Advisory Agent — Requirements Document (v4)
 
**Owner:** Arjun (solo build reference)
**Status:** Phases 0–5 code-complete; QA batch issues #6–#12 resolved
 
---
 
## v4 Change Note
 
*Wording/decision-log corrections from the 2026-06-30 cross-functional doc review. No scope changes, no FR renumbering.*
 
| Change | What updated | Why |
|---|---|---|
| FR17 reworded | FR17 (§5.6 NSE-Specific Behavior) | Old wording implied dedicated NSE holiday-calendar logic that was never built and isn't planned. Aligned to the existing accepted skip-with-log posture (Decision #8) — a holiday closure surfaces as no usable data and falls through the generic skip-with-log path. |
| Detail-page access control decision added | Decisions Log row #17 (new) | Makes explicit that FR19's access-control requirement applies to the dashboard, not the detail page. Detail page stays unguessable-UUID-only — a deliberate accepted posture (NFR3), not an oversight. |
| Dashboard access mechanism resolved | Decisions Log row #11 amended | The build-time mechanism decision is now resolved: client-side JS password gate, accepted as sufficient for v1 given the dashboard's data is informational, read-only, and RLS-scoped to two tables. |
 
---
 
## v3 Change Note
 
*Two new requirement areas added: India NSE expansion and a read-only dashboard. No existing FRs renumbered or reopened.*
 
| Change | What updated | Why |
|---|---|---|
| NSE added as third market | FR1, FR4 updated; FR17–FR18 new | Arjun wants India NSE tickers with same alerting behavior, NSE-aware market gating, and a separate ntfy topic for filtering |
| Dashboard added | FR19–FR22 new; Section 5.7 new | Read-only GitHub Pages view showing all tickers with live price, last run verdict, grouped by market with holdings/watch-only differentiation |
 
---
 
## v2 Change Note
 
*v2 updated three behavioral areas to reflect already-ruled decisions. No decisions were re-opened.*
 
| Change | What updated | Why |
|---|---|---|
| Alerting model rewritten | FR7, FR8, Decisions Log row 2 | Single-rule model replaced the 24h cooldown + reminder: any verdict change → immediate alert, no change → silence, no exceptions. The cooldown and the standing-verdict reminder are both retired. |
| Reliability upgraded | NFR2 | System now runs an active dead-man monitor that pushes an alert on stale/missed/degraded runs — "silence = healthy," not "last-run timestamp, check it yourself." |
| Track record scope clarified | FR15 | Every check writes a log row (including no-change, alerted=false) — not only alerts. Makes the success criterion in Section 2 fully auditable. |
| Cadence phrasing softened | FR6 | "Hourly" → "regular intraday cadence (currently hourly)" so a tuning change isn't a requirements violation. Behavior unchanged. |
 
*Status update — Phases 0–5 code-complete, QA batch #6–#12 resolved.* The single-rule alerting model (FR7/FR8) and the active dead-man monitor (NFR2) are both shipped. The open note on the solution design side — "FR7 reconciliation owed" — is now closed. The canonical spec (this doc) and the build agree: the single rule is the implemented, merged FR7+FR8.
 
---
 
## 1. Problem Statement
 
Manual stock-checking is inconsistent and emotion-driven. The goal is a system that applies the same disciplined judgment every time, on a personal watchlist, without requiring daily manual review.
 
## 2. Goals & Success Criteria
 
**Primary goal:** Catch a real, actionable signal on a held or watched stock that would otherwise have been missed by manual checking.
 
**Success criteria:** Within 3 months, at least one verdict the system surfaced is later validated as correct and would not have been caught manually. This requires the system to log calls — see Section 5.9 (resolved: logging is in for v1, since it's the only way to prove this criterion).
 
## 3. Scope
 
### In scope
- Single-user personal advisory tool (Arjun only, no multi-user/shared access)
- Watchlist of 5–15 tickers per market: US, Canadian (TSX), and India (NSE) listed stocks and ETFs
- User-maintained holdings data: shares owned + cost basis per position
- AI-driven discovery of new candidates beyond the explicit watchlist, using a computational prefilter to shortlist candidates before AI evaluation, across all three markets
- Regular intraday checks during each market's trading hours
- Buy / Sell / Hold verdict + one-line rationale per alert
- Push notification delivery — US/TSX and NSE on separate ntfy topics
- AI judgment grounded in price/volume, news, and fundamentals — no fixed buy/sell rules, no fixed investment style
- Read-only dashboard (GitHub Pages) showing all tickers grouped by market with live price and last run verdict
### Out of scope (explicit)
- Trade execution or order placement of any kind
- Brokerage account integration or read access — holdings are entered manually
- Options, crypto, derivatives, or any asset class beyond stocks/ETFs
- Multi-user or shared/team access
- Licensed financial advice — this is a personal informational tool, not a registered advisory service
## 4. Users
 
One user: Arjun. No external users, no handoff to another team — this doc exists as a solo build reference, not a spec for a contractor.
 
## 5. Functional Requirements
 
### 5.1 Watchlist & Holdings
- **FR1** — Maintain a watchlist of stocks/ETFs across three markets: US, Canadian (TSX), and India (NSE). Each ticker is identified by its market so market-specific gating and grouping can be applied correctly.
- **FR2** — For held positions, record shares owned and cost basis; this personalizes the verdict (e.g., gain/loss context relative to entry).
- **FR3** — Tickers can be watch-only (no position held, no cost basis required).
### 5.2 Candidate Discovery
- **FR4** — Periodically scan beyond the explicit watchlist for AI-flagged candidates across all three markets (US, TSX, NSE). A computational prefilter shortlists candidates before AI evaluation using four signals: significant price movers, volume spikes above the recent average, earnings announcements within a near-term window, and price proximity to the 52-week high or low. A candidate that trips at least one signal (and clears quality gates on market cap, price, volume, and listing exchange) reaches the AI. The AI then evaluates only this shortlist and decides which candidates are worth surfacing — no fixed buy/sell criteria. Of the AI's verdicts, only Buy results generate a push notification; Hold and Sell verdicts from discovery are logged silently. Specific thresholds for signals and quality gates are tunable at build time. Runs on a separate daily cadence, decoupled from the intraday watchlist loop (discovery isn't time-sensitive, and decoupling roughly halves AI call volume vs. running both scans on the same cadence).
- **FR5** — Discovered candidates are clearly labeled as "new candidate" vs. "watchlist update" when delivered.
### 5.3 Monitoring & Triggering
- **FR6** — Checks run every 30 minutes during market hours. No fixed daily/weekly digest format.
- **FR7** — Any verdict change triggers an immediate alert — Buy, Sell, or Hold transitions all qualify, including a change *to* Hold (a held Buy weakening to Hold is itself a signal). No cooldown, no debounce, no delay.
- **FR8** — If a check returns the same verdict as the previous check, no alert fires and no notification is sent. There is no cooldown, no debounce, and no periodic standing-verdict reminder — "no change → silence" is absolute. On a choppy day, a verdict that oscillates will push on every flip; this is accepted behavior, not a bug.
### 5.4 AI Analysis
- **FR9** — Verdicts are generated by AI judgment from price/volume data, recent news, and fundamentals — not fixed deterministic rules.
- **FR10** — No fixed investment style or horizon is assumed; the model weighs each call per stock's own context.
- **FR11** — For held positions, reasoning incorporates cost basis and position size (e.g., flags how a call relates to current gain/loss).
### 5.5 Alerting & Delivery
- **FR12** — Alerts delivered via push notification (e.g., ntfy.sh or Pushover) rather than SMS — removes the need for any SMS provider/Twilio account, and push naturally supports a tap-through link.
- **FR13** — Alert format: Buy/Sell/Hold + one-line rationale in the notification body. No long-form reasoning inline.
- **FR14** — Each notification links to a simple page showing the full reasoning behind that call, pulled directly from the log in 5.9. Natural fit for push (tap-through), avoids building two-way SMS infra.
### 5.6 NSE-Specific Behavior
- **FR17** — Checks for NSE tickers respect NSE market hours (fixed UTC window, no DST). NSE holidays are not separately detected via a maintained calendar — same as US/TSX, a holiday closure surfaces as no usable data and falls through the generic skip-with-log path: no alert, clean no-op.
- **FR18** — NSE alerts are delivered on a separate ntfy topic from US/TSX alerts. Both topics land in the same app on the same device; the separation exists so NSE and US/TSX notifications can be filtered, muted, or managed independently.
### 5.7 Dashboard
- **FR19** — A read-only dashboard is hosted on GitHub Pages (same host as the detail page, FR14). It is access-controlled via a client-side JS password gate — accepted as sufficient for v1 given the dashboard's data is informational, read-only, and RLS-scoped to two tables; unauthenticated public access is not acceptable.
- **FR20** — Tickers are grouped by market: US/TSX in one group, NSE in a separate group. Within each group, holdings and watch-only tickers are visually differentiated via a badge or label on each row — not by position or color alone, so the distinction is legible at a glance.
- **FR21** — Each ticker row displays: current price (live-pulled on each refresh cycle) and last run price, verdict, rationale, and relative time (e.g. "2 hours ago", "3 days ago") sourced from the most recent call log entry for that ticker, regardless of whether an alert was sent. The last-run columns are hidden entirely for a ticker until at least one check has completed for it — no placeholder, no empty cells.
- **FR22** — The dashboard auto-refreshes on a configurable timer while the page is open. The refresh interval is a build-time configuration, not hardcoded.
### 5.8 Timestamps & Timezone
- **FR23** — Timestamps behave differently across surfaces because push notifications are formatted server-side (no device timezone available) while the detail page and dashboard are client-rendered (device timezone is available via the browser).
  - **Push notifications:** timestamp uses the market's own timezone — ET for US/TSX alerts, IST for NSE alerts. Single timezone only, no secondary. Format: `10:30 AM ET` or `8:00 PM IST`.
  - **Detail page and dashboard:** timestamp shows the user's device timezone as primary (auto-detected by the browser) and IST as a fixed secondary in brackets. Format: `10:30 AM ET (8:00 PM IST)`. If the device timezone is already IST, only one timestamp is shown — no duplicate.
### 5.9 Track Record
- **FR15** — Every check writes a log row: ticker, verdict, timestamp, key data points used, and whether an alert was sent. This includes no-change and cold-start checks (logged with alert=false) — not only the checks that push a notification. The full log is what makes Section 2's success criterion auditable.
- **FR16** — Logging is confirmed in for v1 — it's the only way to validate Section 2's success criterion. Kept minimal: no accuracy dashboard or analytics layer in v1.
## 6. Non-Functional Requirements
 
- **NFR1 — Cost:** Target $0–15/month. Checks every 30 minutes against free-tier data APIs keeps this realistic; push notification services (ntfy.sh is free, Pushover is a small one-time fee per platform) remove the per-message SMS cost entirely.
- **NFR2 — Reliability:** The system actively alerts the user when a scheduled run is missed, fails to trigger, or completes degraded — silence from the monitor means healthy. Passive "last run" visibility is not sufficient; a run that never triggers must surface as loudly as one that runs and fails.
- **NFR3 — Disclaimer:** Every alert is informational, not licensed financial advice. No regulatory registration is implied or required for personal use.
- **NFR4 — Data freshness:** The 30-minute cadence means up to ~30 minutes of lag is acceptable. This system is not suited for intraday/fast-moving trade timing — that was explicitly traded away for cost/simplicity (Section 8 history).
## 7. Data Sources
 
- **Price/volume:** Yahoo Finance unofficial API — covers US tickers, TSX (`.TO` suffix), and NSE (`.NS` suffix), free. Confirmed as the v1 source for all three markets.
- **News:** free headline/news feed (specific vendor TBD at build time — low-risk choice, not blocking)
- **Fundamentals:** free-tier basic financials/earnings data (same source as price/volume where possible)
- **Known risk:** Yahoo Finance's API is unofficial — no SLA, no guarantee it stays available or that TSX/NSE fundamentals data is complete. A smoke test against real tickers from each market is a mandatory day-one check before building on top of it.
## 8. Decisions Log (Resolved)
 
| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Track record logging | In, minimal (no dashboard/analytics in v1) | Only way to validate the success criterion in Section 2 |
| 2 | Re-alert/dedup logic | Single rule: any verdict change → immediate alert; no change → silence. No cooldown, no debounce, no standing-verdict reminder. | Cooldown + reminder added state that wasn't earning its keep on a single-user push tool. Tradeoff accepted: a choppy day may produce bursts of alerts on every verdict flip. |
| 3 | Detail-on-request | Tap-through link from the push notification to a page reading from the log | Avoids two-way SMS infra; fits push naturally |
| 4 | Discovery scan cadence | Daily, decoupled from the intraday watchlist loop | Discovery isn't time-sensitive; roughly halves AI call volume |
| 5 | Data vendor | Yahoo Finance unofficial API (price/volume/fundamentals, US + TSX + NSE) | Free, covers all three markets; unofficial-API risk noted in Section 7; smoke test mandatory per market before build |
| 6 | Notification channel | Push notification (ntfy.sh or Pushover), not SMS | Cheaper than SMS, no Twilio/CA-number dependency, supports tap-through links for detail-on-request |
| 7 | NSE notification separation | Separate ntfy topic from US/TSX (same app, same device) | Allows NSE and US/TSX alerts to be filtered or muted independently without needing a second device or app |
| 8 | NSE holiday handling | Skip-with-log, same posture as US/TSX holidays and weekends | Consistent behavior across all markets; no alert, no crash, logged for auditability |
| 9 | NSE discovery | Included in the daily scan alongside US/TSX candidates | Same behavioral rules apply to all markets; no reason to treat NSE discovery differently |
| 10 | Dashboard hosting | GitHub Pages, same host as the detail page | Free, no new infra; static constraint means auth mechanism is a build-time decision |
| 11 | Dashboard access | Access-controlled via a client-side JS password gate — accepted as sufficient for v1 given the data is informational, read-only, and RLS-scoped to two tables. | Personal data; unauthenticated public access not acceptable even though it's informational |
| 12 | Dashboard price refresh | Auto-refresh on configurable timer while page is open | "Current price" needs to stay fresh during an active session; interval is a tunable, not hardcoded |
| 13 | Dashboard last-run columns | Hidden until at least one check has completed for that ticker | No placeholder noise for cold-start tickers with no call log entries yet; columns appear as soon as the system has run once for that ticker, regardless of whether it alerted |
| 14 | Discovery prefilter criteria | Four signals: price movers + volume spikes + earnings proximity + 52-week high/low proximity; thresholds tunable at build time; candidate must trip ≥1 signal and clear quality gates (market cap, price, volume, exchange) to reach the AI; quality gate thresholds also tunable | Narrows universe to a manageable AI shortlist without hardcoding buy/sell logic; 52-week-extreme canonicalized from implemented code — earns its keep as a legitimate "worth a look" trigger |
| 15 | Timestamp display | Notifications: single timezone, market-specific (ET for US/TSX, IST for NSE). Detail page + dashboard: device auto-detect as primary, IST as secondary in brackets; dedup if device is already IST | Server can't detect device timezone at send time; market timezone is the correct anchor for notifications. Client-rendered surfaces can do auto-detect so both timezones are always visible |
| 16 | Discovery verdict suppression | Buys only generate a push notification from discovery; Hold and Sell verdicts are logged silently | A Sell on a stock you don't own is noise; Hold from discovery is not actionable; only Buy surfaces a new candidate worth knowing about |
| 17 | Detail-page access control | Unguessable UUID URL only, no auth gate. FR19's access-control requirement applies to the dashboard, not the detail page. | Detail page is read-only/informational (NFR3); UUID-only is a deliberate accepted posture for this surface, not an oversight |
 
## 9. Out of Scope — Explicit Confirmation
 
No trade execution. No brokerage integration. No options/crypto/derivatives. No multi-user access. Not a registered advisory service. These are hard boundaries for v1, not soft preferences.
 
