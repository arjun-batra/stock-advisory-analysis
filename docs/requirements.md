# Stock Advisory Agent — Requirements

**Owner:** pm (product) — Arjun is the stakeholder/single user.
**Source of truth provenance:** FR1–FR23 / NFR1–NFR4, the Problem/Goals/Scope sections, and the
Decisions Log below are **ported verbatim (lightly reformatted, no meaning changes)** from
`requirements_docs/stock-advisory-agent-requirements.md` (v5) during the multi-agent-template adoption
pass on 2026-07-12. The original v5 doc and its change-note history are retained untouched in
`requirements_docs/` as the historical record. See the changelog at the bottom for the full document
history, including an experimental shadow-wallet track that was added and later retired and removed
outright (git history holds the full FR/NFR text if ever needed).

> **Numbering note:** Core requirement IDs (FR1–FR23, NFR1–NFR4) keep the exact numbering from v5 — do
> not renumber. Note that v5 has no FR-numbering gaps in §5 as ordered, but FR15/FR16 (Track Record) are
> grouped in §5.9 below rather than in strict numeric position, exactly as in the source doc.

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
- System-wide operational kill-switch: pause/resume all scheduled workflows from a single control point
  (§5.10)
- Authenticated admin portal for operational management — watchlist/holdings CRUD, a curated tunables
  editor, a read-only track-record view, and the kill-switch UI — separate from any future user-facing
  portal (§5.11)
- AI provider abstraction layer behind the AI judgment call path; Gemini remains the sole implemented/live
  provider (§5.12)

### Out of scope (explicit)
- Trade execution or order placement of any kind
- Brokerage account integration or read access — holdings are entered manually
- Options, crypto, derivatives, or any asset class beyond stocks/ETFs
- Multi-user or shared/team access
- Licensed financial advice — this is a personal informational tool, not a registered advisory service
- A user-facing portal/dashboard beyond the existing read-only GitHub Pages dashboard (FR19-FR22) —
  planned as a separate, later increment, not part of the admin portal in §5.11
- A second, live AI provider implementation — §5.12 is an abstraction layer only; no second provider is
  built or wired up as part of this scope

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
  call relates to current gain/loss). **This calculation requires the cost basis and the current price to
  be expressed in the same currency — the ticker's native market currency (USD for US, CAD for TSX, INR
  for NSE; no FX conversion is performed, per §7 Data Sources).** If a holding's recorded currency does not
  match its ticker's market, the system must not compute or surface a gain/loss figure from mismatched
  currencies — see FR29 for how currency is captured to prevent this at entry (Decision #35).

### 5.5 Alerting & Delivery
- **FR12** — Alerts delivered via push notification (e.g., ntfy.sh or Pushover) rather than SMS —
  removes the need for any SMS provider/Twilio account, and push naturally supports a tap-through link.
- **FR13** — Alert format: Buy/Sell/Hold + one-line rationale in the notification body. No long-form
  reasoning inline.
- **FR14** — Each notification links to a simple page showing the full reasoning behind that call,
  pulled directly from the log in §5.9. Natural fit for push (tap-through), avoids building two-way SMS
  infra.
- **FR34** — A verdict-change alert is not considered delivered, and the stored verdict state is not
  advanced, until the push notification provider confirms successful dispatch (e.g., a 2xx HTTP response).
  If a push attempt fails or errors, the failure is logged (distinctly from a successful send), but the
  underlying verdict transition remains pending: the next check cycle re-evaluates the same crossing
  against the still-unadvanced prior verdict and retries the alert automatically. This is not a new
  cooldown/reminder mechanism — FR7/FR8's crossings-only, no-standing-reminder design is unchanged — it is
  the mechanism by which a crossing that failed to deliver is not silently and permanently lost. Applies
  identically to the watchlist and discovery push paths; discovery's re-push cooldown/dedup logic
  (`DISCOVERY_PUSH_COOLDOWN_DAYS`, §10) must key off confirmed delivery, not attempted delivery, for the
  same reason (Decision #32).

### 5.6 NSE-Specific Behavior
- **FR17** — Checks for NSE tickers respect NSE market hours (fixed UTC window, no DST). NSE holidays
  are not separately detected via a maintained calendar — same as US/TSX, a holiday closure surfaces as
  no usable data and falls through the generic skip-with-log path: no alert, clean no-op.
  **"No usable data" is defined to include the case where the most recently available price bar predates
  the market's current trading session in that market's own local calendar** — i.e., the market is closed
  today (holiday or otherwise) but a prior session's closing bar is still returned by the data source. In
  that case the system must not treat the stale bar as a live, in-progress session, must not derive an
  intraday price/volume signal by pro-rating a stale bar's numbers as if trading were underway today, and
  must take the skip-with-log path exactly as it does for any other detected non-trading day. This
  structural check (comparing the latest available bar's session date to today's date) is required
  precisely because no maintained holiday calendar exists (Decision #8) — a closed market must be detected
  from the data itself, not assumed already filtered out upstream. Applies identically to US, TSX, and NSE,
  per Decision #8's "same posture across markets" rationale (Decision #33).
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
  **"Whether an alert was sent" (the `alerted` field) means the push was confirmed dispatched successfully
  by the notification provider (e.g., a 2xx response), not merely attempted** — see FR34 for the
  delivery/retry contract this implies (Decision #32).
- **FR16** — Logging is confirmed in for v1 — it's the only way to validate §2's success criterion. Kept
  minimal: no accuracy dashboard or analytics layer in v1.

### 5.10 Operational Control — Kill-Switch
- **FR24** — A single control point (a flag held in Supabase, `kill_switch_state.paused`) can pause the
  system. Enforcement is layered, not a single gate:
  - **Dispatch layer (unchanged):** the `pg_cron` `SECURITY DEFINER` dispatch functions
    (`dispatch_github_workflow`) check the flag before dispatching a new scheduled run. While paused, no
    new run is triggered for either watchlist loop (US/TSX and NSE), either discovery region, or the
    price-snapshot publisher.
  - **In-flight boundary checks (new):** a run that is already dispatched and executing reads
    `kill_switch_state.paused` directly (Python layer, via the same `SUPABASE_SECRET_KEY` service
    credential already used elsewhere — no new SQL object, grant, or secret) at four checkpoints, each
    placed immediately before an irreversible action:
    1. Entry to `main()` in `run_hourly.py` and `run_discovery.py` — if paused, the run aborts before any
       Yahoo fetch or AI call is made.
    2. Immediately before the batched AI judgment call — if paused, the call is not made; no verdict is
       produced or logged for that cycle.
    3. Immediately before the push-notification call (watchlist and discovery push paths alike) — if
       paused, the push is not attempted; the pending verdict crossing is left unadvanced and is retried
       automatically once resumed, per FR34's existing failed-delivery mechanism.
    4. Immediately before `publish_prices.py`'s `contents: write` commit — if paused, the commit is not
       made; the previously published snapshot remains current.

  **The guarantee this delivers:** no new irreversible action (a fresh AI call, a push, or a commit)
  begins after a checkpoint has observed the pause flag set. **It does not deliver instantaneous
  mid-action cessation** — work already underway *inside* a single irreversible action at the moment the
  flag is set (an AI call already sent, a push HTTP request already in flight, a commit already issued)
  completes rather than being cancelled mid-call; there is no interruption of an in-progress network call.
  The residual window this leaves is bounded to, at most, one already-started irreversible action per
  checkpoint the run has already passed — never a full run, and never a subsequent action past the next
  checkpoint. This is a materially stronger and more precisely bounded guarantee than "no new dispatches;
  a run already in flight completes" (considered and rejected — see Decision #37): a paused run stops at
  its next checkpoint rather than running to completion. Unsetting the flag resumes normal operation with
  no other action required.
- **FR25** — While the system is deliberately paused (FR24), NFR2's active dead-man monitor treats the
  absence of runs as expected-quiet, not a failure — no monitor alert fires for a missed/skipped run caused
  by a deliberate pause. Monitor alerting resumes normally once the pause is lifted. **This covers the case
  where a run never starts** — FR24 checkpoint 1 (entry to `main()`) aborts it before any ticker-level work
  begins, so no `call_log` row exists for that cycle and the cycle is structurally indistinguishable from
  one the `pg_cron` dispatch layer never dispatched at all. **It does not cover a run that starts, produces
  real per-ticker work, and then aborts partway through** at FR24 checkpoint 2 or 3 — that case has already
  produced logged, real work and is governed by FR35, not by this requirement.
- **FR35** — A run that has already written at least one real (non-skip) `call_log` row for the current
  cycle under FR15, and then aborts before completion because FR24 checkpoint 2 (the AI-call boundary) or
  checkpoint 3 (the push boundary) observed `kill_switch_state.paused = true`, must be classified for
  NFR2's purposes as expected-quiet, the same non-alerting treatment FR25 already gives a run that never
  started — no monitor alert fires for the run's incompleteness.
  - **Classification must be causally tied to the checkpoint's flag read, never inferred.** This
    classification is valid only when the run's own record shows the abort was directly caused by a
    checkpoint observing `paused = true` — the record must identify which checkpoint fired and that the
    flag read is what triggered the abort. It must never be inferred after the fact from an indirect signal
    (e.g., an outcome count lower than the full ticker list for that cycle, or a heartbeat that was never
    written) — a genuine unhandled exception or a system-wide ingest/AI failure produces those same
    indirect signals, and inferring "pause" from them would let a real failure be misreported as a
    deliberate stop and silently escape NFR2. The exact mechanism (a heartbeat field, a dedicated log row,
    a run-log line) is a design decision for tech-lead; the requirement is that such a record must exist
    and must be checkable by qa against the specific checkpoint-and-flag-read event that caused the abort,
    not against its downstream symptoms.
  - **A pause never suppresses a real degraded/failure signal in the same run.** If the same run also
    contains outcomes that independently qualify as "completes degraded" under NFR2/Decision #31 (e.g., a
    ticker's AI call failed for a real reason before the abort point) that degraded signal must still
    surface and alert exactly as NFR2 requires. Observing the pause flag later in the same run never
    downgrades, cancels, or reclassifies a real failure that already occurred earlier in it.
  - **Track-record integrity — no special-case handling needed or permitted.** `call_log` rows already
    written under FR15 for tickers processed before the abort point are real, complete work product (real
    verdicts from a real AI call) and are retained exactly as logged — never deleted, retracted, or
    re-flagged as invalid on resume. No de-duplication or "resume where it left off" mechanism is required
    to guard against double-counting: FR15 already logs every check as its own timestamped row rather than
    a cumulative count, and FR7/FR8's existing crossings-only comparison against `verdict_state` already
    treats an unchanged verdict as silence — so a ticker re-evaluated on the next normal cycle behaves
    identically whether or not it was already processed in the aborted run. No new catch-up or resume logic
    should be built for this case; unsetting the pause flag resuming normal operation (FR24) already covers
    it.
  - **Scope.** Applies identically to `run_hourly.py` and `run_discovery.py` (FR24's checkpoints 2 and 3
    exist in both entry points). Checkpoint 1 (entry to `main()`) is unaffected — it remains fully covered
    by FR25 above, since no ticker-level work exists to protect. Checkpoint 4 (`publish_prices.py`'s
    commit) is also out of scope for FR35: an abort there discards no per-ticker logged work (there is none
    in that script) and leaves the previously published snapshot current, per FR24's own text — that case
    is already fully covered by FR25's "absence" treatment, since nothing new was produced to lose.
- **FR26** — Every kill-switch state change (pause on, pause off) is logged with a timestamp and the
  actor/source of the change (e.g., admin portal, direct SQL), consistent with FR15's logging posture — the
  pause/resume history is part of the auditable record, not a blind spot.

### 5.11 Admin Portal
A single-user, authenticated, operational/back-office tool — **not** a redesign or replacement of the
existing read-only GitHub Pages dashboard (FR19-FR22), and explicitly **not** the future user-facing
portal (ticker views, graphs) that Arjun is planning as a separate, later increment. Scope is limited to
the operational chores below.
- **FR27** — Access to the admin portal requires authentication via Google OAuth (Supabase Auth). No
  email/password or magic-link login path; no anonymous access.
- **FR28** — The portal can add, edit, and remove watchlist entries (ticker, market, type, status),
  replacing manual SQL edits to the `watchlist` table.
- **FR29** — The portal can add, edit, and remove holdings data (shares, cost basis) for held tickers,
  replacing manual SQL edits to the `holdings` table. **Currency is not an independently admin-chosen
  field — it is derived automatically from the ticker's market (`watchlist.market`): US⇒USD, TSX⇒CAD,
  NSE⇒INR.** This removes the free-choice currency/market mismatch that FR11's gain/loss calculation
  depends on not existing (Decision #35).
- **FR30** — The portal includes a tunables editor covering a curated subset of `scripts/config.py` values
  (listed below) — not the full tunables surface. Each field displays a human-readable description, an
  example value, and the current effective default/value — never a bare input box with no context. Edits
  write directly to a dedicated `tunables` table in Supabase (columns: key, value, description, example,
  updated_at, updated_by), which is the source of truth for these 10 keys at runtime — `scripts/config.py`
  fetches them from this table at run start, falling back to the last successfully-fetched value, cached
  in a repo-committed file, itself seeded from an initial hardcoded default on first run, if the fetch
  fails (same fail-safe posture already used elsewhere, e.g. the AI call path, adapted per Decision #28
  so the fallback tracks reality instead of a fixed literal). The write path uses the portal's
  authenticated Supabase session, gated by an admin-scoped RLS write policy — the same authorization
  mechanism already used for FR28/29 watchlist/holdings CRUD — so no GitHub PAT or other broad-scope
  credential is used or stored by the portal (see NFR6). **Before any write is accepted (portal UI and
  database alike), the value must validate against the same type/domain contract `scripts/config.py`
  applies when loading that key** (e.g., numeric fields must parse as their expected numeric type;
  `ALERTS_ENABLED` must resolve to an unambiguous boolean, not a free-text string that can silently coerce
  to a default) — an invalid value must be rejected at write time with a clear error, not accepted and
  only surfaced later as a runtime failure or a silent behavior change. A single invalid tunable value
  must never be able to take down every scheduled entry point (watchlist, discovery, price-publisher)
  simultaneously; catching the error before it is ever written is what prevents that (Decision #34). This
  supersedes the original
  GitHub-Actions-Variables-proxy mechanism recorded in Decision #24; see Decision #27 and Decision #28.
  Curated subset: `GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`,
  `DISCOVERY_LOSER_PCT`, `DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_MARKET_CAP_INR`,
  `DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`. All other tunables in §10 remain
  editable only via GitHub Actions Variables / code defaults, not through the portal.
- **FR31** — The portal includes a read-only track-record view: a cleaner presentation of `call_log` data
  already captured under FR15. No new analytics, aggregation, scoring, or trend computation beyond what is
  already logged.
- **FR32** — The portal includes a kill-switch control (a UI toggle) that reads and writes the FR24 pause
  flag. It inherits FR25's monitor pause-awareness, FR35's mid-run-abort classification, and FR26's audit
  logging automatically, since it operates on the same backend flag rather than a separate mechanism.

### 5.12 AI Provider Abstraction
- **FR33** — The AI judgment call path (`scripts/ai_judge.py`) abstracts Gemini-specific SDK calls, request/
  response schema handling, and error/retry classification behind a provider-neutral interface (a batch
  verdict request/response contract). Gemini remains the sole implemented/live provider — no second
  provider is built or wired up as part of this requirement. The interface exists so that adding a future
  provider is an additive change rather than a rewrite of the judgment layer.

  > **Note for tech-lead (design-time, not a requirement):** Arjun asked about using LiteLLM (a unified
  > multi-provider SDK/library) as the implementation approach for FR33, instead of a hand-rolled
  > interface. This is explicitly a design/implementation decision, not a requirements decision — evaluate
  > hand-rolled vs. LiteLLM (or any other viable approach) when writing `design.md` for this increment, on
  > normal engineering tradeoffs. Flagged here only so it isn't lost between requirements approval and
  > design.

## 6. Non-Functional Requirements

- **NFR1 — Cost:** Target $0–15/month (unchanged cap). Gemini now runs on Google's **paid tier** (not
  free tier); the budget is held by keeping call volume low — one batched Gemini call per run per track
  (production watchlist, NSE watchlist, and daily discovery), on the ~30-minute cadence, against
  otherwise-free data APIs. Push notification services (ntfy.sh is free, Pushover is a small one-time fee
  per platform) remove the per-message SMS cost entirely.
- **NFR2 — Reliability:** The system actively alerts the user when a scheduled run is missed, fails to
  trigger, or completes degraded — silence from the monitor means healthy. Passive "last run" visibility
  is not sufficient; a run that never triggers must surface as loudly as one that runs and fails.
  **"Completes degraded" is defined as, at minimum: any run in which one or more requested tickers failed
  to produce a valid AI verdict for any reason (parse failure, API/provider error, timeout, or any other
  exception in the judgment path) — regardless of internal bucket naming, and regardless of whether that
  failure count is the run's dominant outcome.** A run in which **every** requested ticker fails this way
  is not merely degraded — it must be surfaced with at least the same urgency as a fully skipped/errored
  run; a heartbeat status of "healthy/ok" is never correct when zero verdicts were produced. This applies
  identically to the watchlist and discovery entry points, and exists specifically so a silent, system-wide
  judgment-layer failure (e.g., an expired API key, a provider outage, or a bad model string) cannot look
  identical to a normal healthy run on the dashboard or the monitor (Decision #31).
- **NFR3 — Disclaimer:** Every alert is informational, not licensed financial advice. No regulatory
  registration is implied or required for personal use.
- **NFR4 — Data freshness:** The 30-minute cadence means up to ~30 minutes of lag is acceptable. This
  system is not suited for intraday/fast-moving trade timing — that was explicitly traded away for
  cost/simplicity.
- **NFR5 — Admin portal cost:** Hosting (Vercel) and authentication (Google OAuth via Supabase Auth) are
  expected to fit within free tiers with no new recurring spend. If actual usage ever exceeds free-tier
  limits, any resulting cost still falls under NFR1's existing $0-15/month cap, not a separate budget.
- **NFR6 — Admin portal security:** Write access (watchlist, holdings, tunables, kill-switch) requires
  authenticated Google OAuth login (FR27); no unauthenticated write path exists. All portal writes —
  including the FR30 `tunables` table — are additionally gated at the database layer by an admin-scoped
  Supabase RLS write policy, not solely by the client-side auth check, consistent with NFR7's core
  security posture (secrets never in code) and `scripts/config.py`'s existing "nothing sensitive
  hardcoded" convention. This item covers the admin-portal-specific write controls added on top of
  NFR7's pre-existing baseline.
- **NFR7 — Core security posture:** Row-Level Security (RLS) scopes Supabase table access to what each
  surface legitimately needs (e.g., the dashboard's anon read is RLS-scoped to two tables, FR19).
  Secrets (API keys, DB credentials, the admin-portal dispatch PAT) live in Supabase Vault or GitHub
  encrypted secrets, never hardcoded in code — `scripts/config.py`'s existing "nothing sensitive
  hardcoded" convention. The system holds no brokerage credentials and has no trade-execution capability
  of any kind (§3 Out of scope). The detail page (FR14) uses an unguessable UUID-only URL with no auth
  gate as its deliberate access-control posture (Decision #17). This is the system's pre-existing
  security baseline, predating the admin portal; NFR6 covers the portal-specific write-access controls
  layered on top of it.

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
| 17 | Detail-page access control | Unguessable UUID URL only, no auth gate. FR19's access-control requirement applies to the dashboard, not the detail page. | Detail page is read-only/informational (NFR3) and covered by NFR7's core security posture; UUID-only is a deliberate accepted posture for this surface, not an oversight |
| 18 | Dashboard "current price" freshness | Server-published snapshot (`prices.json`) refreshed on the ~30-min market cadence, read same-origin by the dashboard; the "prices updated" age keys off the snapshot's `generated_at`. | Yahoo's price API is browser-CORS-blocked for all three markets (SD issue #18) — a direct client fetch is infeasible. Publish-cadence freshness matches the system's own 30-min cadence posture (NFR4); the honest data-age indicator was preferred over a refresh-tick illusion of liveness |
| 19 | Kill-switch scope | Full-system pause — all scheduled workflows (both watchlist loops, both discovery regions, price publisher), enforced at the `pg_cron` dispatch layer | Closest to the documented Supabase single-point-of-failure (idea-brief risk #6); a partial pause (alerts-only or AI-only) doesn't stop cost/dispatch and doesn't match "pause the whole system" |
| 20 | Kill-switch + dead-man monitor | NFR2's monitor treats a deliberate pause as expected-quiet, not an outage (FR25) | Otherwise flipping the kill-switch pages the user via the very monitor built to catch real failures |
| 21 | Kill-switch audit trail | Every toggle (on/off) logged with timestamp + actor/source (FR26) | Consistent with FR15's "log everything" posture; an unlogged pause/unpause would be a blind spot in the audit trail |
| 22 | Admin portal scope boundary | Purely operational/back-office (watchlist/holdings CRUD, tunables editor, track-record view, kill-switch UI); explicitly not the future user-facing dashboard | Keeps this item bounded and avoids designing the portal to double as, or evolve into, the read-facing product surface (planned as a separate future increment) |
| 23 | Admin portal hosting & auth | Vercel (frontend + serverless functions); Google OAuth via Supabase Auth for login (FR27) | Arjun has an existing Vercel account and already uses this exact secrets pattern on another repo; Google OAuth was his explicit preference over email/password or magic link |
| 24 | **SUPERSEDED 2026-07-27 — see #27.** Admin portal tunables source of truth | GitHub Actions Variables remain the source of truth; the portal edits them via a server-side proxy holding a GitHub PAT (FR30) | Avoids re-plumbing how the production workflow loads its config; a lightweight backend is cheap and available via Vercel either way, so this is lower-risk than migrating live tunables into Supabase |
| 25 | Admin portal tunables subset | Curated list only (FR30), not the full ~28-key surface — see FR30 for the list | These are the tunables actually plausible to adjust after observing the system run day-to-day; the rest are set-once/infra knobs tuned from a specific incident or smoke test and don't need a portal form |
| 26 | AI provider abstraction scope | Interface-only (FR33): abstract Gemini specifics behind a provider-neutral contract; Gemini remains the sole implemented/live provider, no second provider built now | Motivation is general vendor-optionality, not a specific cost/reliability problem to fix; building a second provider with no concrete target risks guessing the interface shape wrong |
| 27 | Admin portal tunables source of truth (supersedes #24) | Tunables move to a new `tunables` table in Supabase, seeded via migration with the 10 curated keys at their current default values (no behavior change at cutover); `scripts/config.py` fetches them at run start with a fallback to hardcoded Python defaults if the fetch fails; the portal writes to the table via its authenticated Supabase session, gated by the same admin-scoped RLS write policy already planned for FR28/29/32; no GitHub PAT or GitHub-API proxy is used (FR30, NFR6) | During design, tech-lead found #24's premise false: only 2 of the 10 curated keys (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`) are actually wired from GitHub Variables into the running workflows — `ALERTS_ENABLED` is a `workflow_dispatch` input on scheduled runs, not read from a Variable, and the 7 `DISCOVERY_*` keys aren't wired in at all. "Don't touch the production config-loading path" was never achievable, so fixing the wiring gap requires touching it either way. Given that, moving to Supabase (a) removes the two-system split that caused the gap, (b) is consistent with Supabase already being the system's control plane (watchlist, holdings, and the FR24 kill-switch flag), and (c) removes the need for the portal to hold a GitHub PAT, replacing it with the same auth mechanism already being built for FR28/29 — net one fewer secrets store and one fewer code path. The other ~18 non-curated tunables are unaffected; they remain GitHub Variables/code defaults. Approved by Arjun after discussion. |
| 28 | Admin portal tunables fail-safe: fallback source (refines #27) | On a **failed** Supabase fetch, `scripts/config.py` no longer falls back to a fixed hardcoded Python literal per key. Instead it reads a repo-committed cache file, `tunables_cache.json` at the **repo root** (not a `config/` subdirectory — corrected per REV-046: `scripts/` is a flat, non-package directory on `sys.path`, and a repo-root `config/` directory would shadow it), holding the **last successfully-fetched value** for each of the 10 curated keys. The fallback chain is **two tiers only** — Supabase table, then this cache file; a third, permanent hardcoded-literal tier considered during design was rejected. If a key is missing from both tiers, or a value present in either tier fails to cast to its expected type, `scripts/config.py` fails loud (`SystemExit`) at startup rather than silently guessing a default. That file is seeded on day one with the then-current hardcoded defaults (so a fresh checkout still has a bottom-of-the-chain value), and is updated — diff-checked and committed back to the repo only if a value actually changed — on every **successful** Supabase fetch, reusing the exact "commit only if changed" pattern `.github/workflows/publish-prices.yml` already uses for `pages/prices.json` (diff-check, `git add`, `git diff --cached --quiet` guard, commit with `[skip ci]`, `git pull --rebase` before push to handle concurrent writes). Decision #27's core reversal (Supabase table as source of truth) is unchanged; this refines only what happens on a failed fetch. **Open, design-level (tech-lead to finalize in design.md):** which workflow(s) write back to the cache file vs. read-only-consume it. Proposed shape, for Arjun to confirm or override: `hourly-watchlist.yml` (most frequent run, every 30 min in-hours) is the sole writer; the two discovery-region workflows and `publish-prices.yml` remain read-only consumers, since Supabase is still every workflow's primary source regardless — only the fallback source is changing. | A fixed hardcoded literal freezes at whatever value happened to be in the code the last time that line was edited, so it can silently drift weeks or months stale from what's actually been curated via the portal in day-to-day use — defeating the point of having a portal-editable source of truth. A rolling last-known-good cache stays close to actual practice. Reuses a mechanism already proven working in this exact codebase (`publish-prices.yml`) rather than inventing a new one. Approved by Arjun after discussion. |
| 29 | Tunables-cache write-ownership — **RESOLVED (refines #28, REV-040)** | Decision #28's proposed shape (`hourly-watchlist.yml` as sole cache writer) was confirmed by Arjun and carried into `design.md` as settled. Reviewer's Pass 11 audit (REV-040) then found two real issues with that shape: **(a) race** — `publish-prices.yml` already commits/pushes to `main` on the same ~30-min cadence window with a *different* `concurrency` group, and the copied "commit only if changed" step's `git push` is unguarded, so a lost race intermittently fails the **trading** workflow (`hourly-watchlist.yml`) even though its real work already completed — alarming and misleading; **(b) privilege** — granting `contents: write` to `hourly-watchlist.yml`, the workflow holding every production secret and processing third-party input, is the largest privilege increase in the whole change request. Reviewer's suggested alternative: make `publish-prices.yml` the sole cache writer instead — zero new permissions, zero new commit logic. **Final call (Arjun): `hourly-watchlist.yml` stays the sole writer.** Rationale given: it's the workflow that reads/triggers off the Supabase-scheduled jobs, so it's the natural owner of writing state back. Arjun accepted the race and privilege-increase tradeoffs reviewer flagged, **conditioned on both of reviewer's suggested mitigations being implemented, not left as optional follow-up:** (i) a `concurrency` group shared between `hourly-watchlist.yml` and `publish-prices.yml` so the two committing workflows cannot race on the same push, and (ii) a bounded retry around the `git push` step itself (not just the existing `git pull --rebase` guard). tech-lead is implementing both mitigations in `docs/design/admin-portal-tunables.md`'s workflow diff as a condition of this decision. | A same-cadence race that intermittently red-Xs the trading workflow, and the largest privilege increase in the CR, are real architectural tradeoffs surfaced by reviewer's deeper audit (REV-040); Arjun weighed them against `hourly-watchlist.yml` being the natural read/trigger owner of this state and chose to keep the original shape, with the two mitigations as a binding condition rather than accepting the risk unmitigated. |
| 30 | NFR citation gap (REV-058) — added NFR7 | `requirements.md` had no dedicated core-security NFR; `design/non-functional-ops.md` and `design.md`'s coverage map were citing NFR3 (Disclaimer) for the system's actual pre-existing security posture (RLS, Vault, no brokerage credentials/execution, UUID-only detail-page URLs) — a mislabeled citation, not a real NFR3 match. Added **NFR7 — Core security posture** (§6) to document this baseline under its own ID; NFR6 (admin portal security) now cross-references NFR7 as the portal-specific layer on top of it, replacing its prior (incorrect) NFR3 citation. | A dedicated ID is leaner and more accurate than a footnote saying "no such NFR exists": the posture is real and already implemented, and now has a correct citation target — NFR3 remains solely the Disclaimer requirement, matching its original v5 text unchanged. Chosen over the alternative (a Configuration-section note disclaiming any security NFR) because NFR6 already needed something concrete to reference, and inventing a citation redirect note would have been more document surface for the same information. |
| 31 | NFR2 "completes degraded" sharpened (DEEP-001) | `/big-guns` found that a run in which 100% of AI calls fail still writes heartbeat `status="ok"`, because the code's `degraded` bucket omits the fail-safe-Hold ("no-read") outcome — the exact case NFR2 already promised to catch. The requirement was correct; the code was wrong. Sharpened NFR2's text (§6) to define "completes degraded" explicitly (any run with one or more failed-to-verdict tickers, regardless of bucket naming; an all-failed run must not read "ok") so the fix is self-verifiable and the gap cannot recur silently. | The requirement expressed the behavior actually wanted (silence-means-healthy must never be true when zero verdicts were produced); a vague definition of "degraded" is what let the code drift out of compliance without anyone noticing. Fix-the-code, sharpen-the-claim. |
| 32 | Alert delivery/retry semantics — new FR34 (DEEP-002) | `/big-guns` found `call_log.alerted=true` is written on push *attempt*, not confirmed delivery, and `verdict_state.current_verdict` advances regardless of outcome — so a failed push (bad topic, ntfy outage, rate limit) permanently and silently loses that verdict crossing under FR7/FR8's no-reminder design. Added **FR34** (§5.5): `alerted` means confirmed-delivered; verdict state does not advance until delivery succeeds; a failed push is retried automatically on the next cycle via the same crossings-only comparison (no new cooldown/reminder mechanism). Amended FR15's `alerted`-field definition and discovery's re-push cooldown (FR34, §10) to match. | Resolvable from existing requirements without a new user trade-off: FR7/FR8/Decision #2 already establish that a verdict change must reliably alert, and §2's success criterion depends on the log being trustworthy. Fix-the-code (retry-on-failure) plus a new FR stating the delivery contract explicitly, since "was sent" was previously undefined. |
| 33 | Holiday/closed-market structural detection — FR17 sharpened (refines #8, DEEP-004) | `/big-guns` found the documented "holiday ⇒ no usable data ⇒ skip-with-log" behavior (FR17, Decision #8, idea-brief risk #5) does not exist in code: on a closed-market day, `yfinance` still returns the prior session's bar, the system treats it as live, and pro-rates a stale volume ratio into a fabricated "spike" that can trigger a real, wrong alert. The requirement (and Decision #8) expressed the behavior actually wanted; the code never implemented the detection needed to reach the skip path. Sharpened FR17 to require a structural check — compare the latest available bar's session date to today's date in the market's own calendar — since no maintained holiday calendar exists to short-circuit the run earlier. | Fix-the-code, sharpen-the-claim, same class as DEEP-001. Structural date-comparison is the only reliable way to detect "closed today" without building/maintaining a holiday calendar, which was explicitly rejected as out of scope back when Decision #8 was made. |
| 34 | Portal tunables validation must mirror `config.py`'s cast contract — FR30 sharpened (DEEP-005) | `/big-guns` found the FR30 tunables editor validates only non-emptiness; two of the ten curated keys (`ALERTS_ENABLED`, `GEMINI_MODEL`/`_BACKUP`) have casts that can never raise, so a typo silently and invisibly changes system behavior (e.g., `ALERTS_ENABLED="tru"` silently disables all real pushes with no error, no monitor signal), while a typo in a numeric key instead takes down every scheduled entry point at once via `SystemExit`. Sharpened FR30 to require write-time validation against the same type/domain contract `scripts/config.py` enforces, so an invalid value is rejected before it is ever written rather than causing a silent behavior change or a system-wide outage. | Requirement-level fix, not implementation-prescriptive — leaves the validator mechanism (client-side, DB constraint, or both) to tech-lead/dev. Consistent with the existing fail-loud posture (Decision #28): the goal is to prevent an invalid value from ever reaching that posture in the first place. |
| 35 | Holdings currency derived from ticker market, not free-choice — FR11/FR29 sharpened (DEEP-006) | `/big-guns` found the admin portal's holdings currency field is free-choice (defaults to USD for every market) and never reconciled against the holding's ticker market, so a TSX/NSE position entered at its natural default silently produces a wrong unrealized P&L that FR11 explicitly feeds to the AI as fact and the detail page renders as real — latent today only because the live watchlist holds zero positions. Sharpened FR29 so currency is derived automatically from `watchlist.market` (US⇒USD, TSX⇒CAD, NSE⇒INR) rather than admin-entered; sharpened FR11 to state the same-currency requirement the P&L calculation depends on. | Design already assumes no-FX-conversion, native-per-market pricing (`non-functional-ops.md` §7.3); the portal's free-choice currency field was the one place that assumption wasn't enforced. Deriving currency from already-known data (the ticker's market, via the existing FK) removes the mismatch at its source rather than adding a reconciliation check downstream. |
| 36 | Deferred live-verification checks are mandatory before closure, not optional | Three live checks have been deferred across multiple review passes without being scheduled to actually run: INC-3 AC3 (kill-switch functional pause/resume against the live Supabase project), INC-4 AC6 (live-Gemini smoke test — requires a real `GEMINI_API_KEY` in the execution environment; none present as of the last check, `test-report.md:196`), and INC-7 AC2/AC3 (admin-portal kill-switch RPC round-trip and live dispatch-suppression proof, gated on `sql/kill_switch_portal_grant.sql`'s live application). Arjun's explicit 2026-07-30 direction: all three must be executed before `v0.1.0` is tagged. Until executed, FR24–FR26 (INC-3), FR33 (INC-4), and FR31/FR32 (INC-7) remain **"deferred, pending live execution"** — a distinct, non-terminal status — in pm's Phase-4 "every FR/NFR delivered or deferred" confirmation; they may not be marked "delivered" until the corresponding AC actually runs against live infrastructure. | Two of these three (INC-3 AC3, INC-7's round-trip) were previously deferred through several review passes without a concrete plan to execute them; recording this as a decision, not just a scheduling note, ensures Phase-4 closure cannot quietly treat "deferred" as terminal again. The credential gap for INC-4 AC6 is a real, currently-open constraint, not assumed resolved — flagged plainly rather than guessed away. |
| 37 | DEEP-007 kill-switch boundary — Arjun's resolution: in-flight boundary checks, not a future-dispatches-only rescope | DEEP-007 (`review-log.md`, "Deep review — 2026-07-29") found FR24's absolute wording ("no AI calls, no Yahoo fetches, no pushes, no price-snapshot updates" while paused) is not what the code delivers: enforcement lives only at the `pg_cron` dispatch layer, so a run already dispatched runs to full completion — including a real push and a `contents: write` commit to `main` — while the portal badge already reads PAUSED. Two options were on the table: (a) rescope FR24's wording down to what dispatch-layer-only enforcement actually gives ("no new dispatches; a run already in flight completes"), or (b) add Python-layer boundary checks so an in-flight run itself can be stopped before its next irreversible action, and reword FR24 up to match that stronger behavior. **Arjun chose (b).** Four checkpoints, each immediately before an irreversible action: entry to `run_hourly.py`/`run_discovery.py` `main()`, immediately before the batched AI call, immediately before the push call, and immediately before `publish_prices.py`'s commit. Each reads `kill_switch_state.paused` directly via the Python layer's existing `SUPABASE_SECRET_KEY` (already bypasses RLS — no new SQL object, grant, or secret required; `NtfyNotifier.push`, `scripts/notify.py:92`, was independently confirmed to post directly over HTTP with no `send_ntfy` SECURITY DEFINER gate today, so the push checkpoint is a genuine new control, not a redundant one). FR24 is reworded (§5.10) to state the guarantee actually delivered — enforcement at defined boundaries with an explicitly bounded residual window — rather than either the prior absolute wording or the rejected future-dispatches-only rescope. **Sequencing: this work is INC-12 and must land strictly after INC-8, not in parallel.** Aborting a partially-processed run raises "what does the heartbeat report for an aborted-not-failed cycle?" — the same degraded-accounting seam INC-8 is rewriting per NFR2/Decision #31; designing the abort-accounting contract before INC-8 settles what "degraded" means would mean guessing at a shape that INC-8 might then change out from under it. | The label on an operator's safety control for an advice-generating system must match its actual behavior — rescoping the requirement down to match a weaker implementation was rejected because it launders a real gap into a documentation fix rather than closing it. Full continuous polling (checking the flag on some fixed interval throughout the run, independent of action boundaries) was considered and also rejected: between the four boundary points, the run is doing pure computation (parsing a response, formatting a rationale) with no irreversible side effect pending, so polling there buys no additional safety margin over checking immediately before the next irreversible action — it would only add complexity and CPU-cycle overhead for the same bound already achieved by boundary placement. |
| 38 | Pause-triggered mid-run abort — new FR35 (follow-on to Decision #37, deferred until INC-8 landed) | Decision #37 flagged that FR24's checkpoints 2/3 (the AI-call and push boundaries) can abort a run *after* it has already produced real, logged per-ticker work — a case distinct from both FR25's "run never started" and NFR2/Decision #31's "completes degraded," and one that INC-8's heartbeat/degraded-accounting rewrite needed to settle first (both entry points now compute `degraded = outcomes["skip"] + outcomes["error"] + outcomes["no-read"] + outcomes["push-failed"]`, per `run_hourly.py`/`run_discovery.py` as shipped). Without a defined classification, a pause-aborted run would either coalesce into a misleading "ok" (masking that later checkpoints were never reached) or count as degraded and fire an NFR2 alert on every ordinary use of the kill switch — training the operator to ignore the monitor, defeating NFR2's purpose. Added **FR35** (§5.10): a run with at least one real logged ticker that then aborts at checkpoint 2/3 due to `paused=true` is expected-quiet, not alerting — but only when the classification is causally tied to the specific checkpoint-and-flag-read event (never inferred from an outcome count or a missing heartbeat, both of which a genuine crash also produces), and never when it would suppress a real degraded signal already present in the same run. Confirmed no new de-duplication/resume logic is needed for track-record integrity: FR15's per-check logging plus FR7/FR8's existing crossings-only comparison already make a ticker's re-evaluation on the next normal cycle safe, whether or not it was already processed in the aborted run. Checkpoint 1 (no ticker-level work yet) stays under FR25 unchanged; checkpoint 4 (`publish_prices.py`'s commit) stays under FR25 unchanged too, since no per-ticker logged work exists there to protect. Cross-referenced from FR32 (portal kill-switch UI inherits FR35 the same way it already inherits FR25/FR26). | Closes the gap pm flagged when rewriting FR24 (Decision #37): the boundary checks that make the kill switch stronger also introduce a new run shape (started-then-deliberately-aborted) that neither "never ran" nor "ran and failed" describes. The causal-tie requirement exists specifically to prevent the loophole where a genuine failure could be misreported as a deliberate pause; the no-new-resume-logic call keeps the fix requirement-only (no design/code prescribed beyond the observable contract qa needs to test against) and avoids inventing machinery the existing FR7/FR8/FR15 mechanics already make unnecessary. |

## 9. Out of Scope — Explicit Confirmation

No trade execution. No brokerage integration. No options/crypto/derivatives. No multi-user access. Not a
registered advisory service. These are hard boundaries for v1, not soft preferences.

## 10. Configuration (tunables audit baseline)

All user-tunable values live in the config surface (`scripts/config.py`, values read from environment /
GitHub Actions secrets & Variables — nothing sensitive hardcoded). This section is the reviewer's
hardcoding-audit baseline. Values below are the current defaults as documented in code/SD; they are
tunables, not fixed requirements.

### Core system
| Key | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `gemini` | Selects which AI provider `ai_judge.py` uses via `ai_provider.get_provider()`; only `gemini` is currently implemented (FR33/Decision #26) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Primary watchlist AI model |
| `GEMINI_MODEL_BACKUP` | `gemini-2.5-flash-lite` | Fallback model (empty disables fallback) |
| `NSE_GEMINI_MODEL` / `NSE_GEMINI_MODEL_BACKUP` | inherit US/TSX pair | NSE watchlist model pair (quota isolation option) |
| `DISCOVERY_GEMINI_MODEL` / `_BACKUP` | `gemini-2.5-flash` / `-lite` | Discovery model pair (separate daily quota bucket) |
| `GEMINI_TIMEOUT_MS` | `180000` | Per-request Gemini timeout (ms) |
| `GEMINI_MAX_RETRIES` | `3` | Retries after the initial Gemini attempt |
| `GEMINI_RETRY_BASE_MS` | `10000` | Exponential backoff base delay (ms), full jitter |
| `AI_TEMPERATURE` | `0.2` | Gemini generation temperature; lower values reduce verdict-to-verdict drift for the same inputs — default chosen for consistency, operator-adjustable if ever needed |
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
| `TUNABLES_FETCH_TIMEOUT_MS` | `5000` | Explicit timeout (ms) for the Supabase `tunables` table fetch itself; non-curated — bootstraps that fetch, so it can't live in the `tunables` table it's used to fetch (Decision #28, REV-041) |
| `SKIP_TUNABLES_FETCH` | `false` | Offline/test-only switch; forces the tier-2 cache path with zero network calls at import time. Used by `tests/conftest.py` to make the test suite deterministic (Decision #28, REV-041) |

> **Historical note (closed) — `GEMINI_MODEL` / `GEMINI_MODEL_BACKUP`:** these keys previously carried a
> doc-vs-actual-operation mismatch — the literal defaults in `scripts/config.py` were `gemini-3.5-flash` /
> `gemini-3.1-flash-lite` while real operation ran the `gemini-2.5-flash` family (paid tier) due to
> stability issues with the 3.x models. That gap is now **CLOSED**: INC-1 (2026-07-13 change request)
> changed the literal `scripts/config.py` defaults to `gemini-2.5-flash` / `gemini-2.5-flash-lite`, so
> code and operation now agree — the table above states the current true defaults. qa's `test-report.md`
> §9.2 asserts `config.GEMINI_MODEL == "gemini-2.5-flash"`.

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

> **Admin portal exposure (FR30):** the admin portal's tunables editor exposes a curated subset of the
> tunables above — `GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`,
> `DISCOVERY_LOSER_PCT`, `DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_MARKET_CAP_INR`,
> `DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS` — with a description, example, and current
> value shown per field. **As of 2026-07-27 (Decision #27, supersedes #24), these 10 keys are sourced from
> a dedicated `tunables` table in Supabase, not GitHub Actions Variables** — the table is seeded via
> migration at their current default values and is what `scripts/config.py` reads at run start for these
> keys; the portal writes to this table directly under an admin-scoped RLS policy, with no GitHub PAT or
> proxy involved. **Fail-safe on a failed fetch (Decision #28, refines #27):** `scripts/config.py` falls
> back to a repo-committed cache file, `tunables_cache.json` at the **repo root** (not `config/` — REV-046
> fix; a repo-root `config/` directory would shadow the flat `scripts/` import path), holding the last
> successfully-fetched value per key, not a fixed hardcoded literal. The chain is **two tiers only** —
> Supabase table, then this cache file; a third, permanent hardcoded-literal tier was rejected during
> design. The cache file is seeded on day one with the then-current hardcoded defaults, and is updated
> (diff-checked, committed only if changed) on every successful Supabase fetch — the same commit-on-change
> mechanism already used by `.github/workflows/publish-prices.yml` for `pages/prices.json`. **On a genuine
> double-miss** (a key absent from both tiers, or a value present in either tier that fails to cast to its
> expected type), `scripts/config.py` fails loud via `SystemExit` at startup rather than silently guessing
> a value. Write-ownership is **settled:
> `hourly-watchlist.yml` is the sole writer** (Decision #28, reconfirmed by Arjun as Decision #29 after
> reviewer's Pass 11 audit (REV-040) flagged a race and a privilege-increase risk with this shape), **on
> the condition that two mitigations ship with it**: a `concurrency` group shared with
> `publish-prices.yml` so the two committing workflows cannot race on the same push, and a bounded retry
> around the `git push` step itself. All other tunables in the tables above remain
> GitHub-Actions-Variable/code-default only; the portal does not expose them and this
> reversal/refinement does not affect them.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-07-30 | **DEEP-007 resolution — FR24 reworded to add in-flight boundary-check enforcement, not rescoped to future-dispatches-only.** Arjun's decision (Decision #37): the kill switch will stop an in-flight run at four defined checkpoints (entry to `run_hourly.py`/`run_discovery.py` `main()`, before the batched AI call, before the push call, before `publish_prices.py`'s commit), each reading `kill_switch_state.paused` directly via the Python layer. FR24 (§5.10) reworded to state the guarantee this actually delivers — enforcement at defined irreversible-action boundaries with an explicitly bounded residual window, not instantaneous cessation and not the rejected "no new dispatches; in-flight run completes" alternative. No other FR/NFR text changed in this entry; FR25's interaction with a boundary-triggered abort (what the dead-man monitor/heartbeat reports for a run that aborts mid-execution due to pause, as distinct from a completed-degraded run under NFR2/Decision #31) is flagged to tech-lead as a likely follow-on amendment once INC-8's heartbeat/accounting rewrite lands, not resolved here — sequencing this work (INC-12) strictly after INC-8 is itself part of Decision #37. Archived the oldest live entry (2026-07-16, shadow-experiment removal) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | User's explicit 2026-07-30 answer to the DEEP-007 trade-off pm escalated per the change-request process (open trade-offs go to the user, not decided silently); recorded per this project's established decision-then-changelog pattern. |
| 2026-07-27 | **Reversal — FR30 tunables editor moves from GitHub-Variables-proxy to a Supabase `tunables` table.** During design, tech-lead found Decision #24's premise false: only 2 of the 10 curated keys (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`) are actually wired from GitHub Variables into the running workflows — `ALERTS_ENABLED` is a `workflow_dispatch` input on scheduled runs (not read from a Variable) and the 7 `DISCOVERY_*` keys aren't wired in at all. "Don't touch the production config-loading path" was never achievable, so closing that gap requires touching it regardless of mechanism. Revised FR30 to describe the new mechanism: a `tunables` Supabase table (key, value, description, example, updated_at, updated_by) seeded via migration at current defaults (no behavior change at cutover); `scripts/config.py` fetches these 10 keys from the table at run start with a fallback to hardcoded Python defaults on fetch failure; the portal writes directly to the table under an admin-scoped RLS policy (same mechanism as FR28/29/32) — no GitHub PAT or proxy. Revised NFR6 to drop the GitHub-PAT-specific line, replaced with the general RLS-write-policy requirement. Marked Decision #24 SUPERSEDED and added Decision #27 recording the new decision and rationale. Updated the §10 Configuration note under FR30 to describe the table-based mechanism. The other ~18 non-curated tunables are unaffected — they remain GitHub Variables/code defaults, since the portal doesn't touch them. Archived the next-oldest changelog entry (2026-07-12, Experimental Tracks section) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Arjun approved this direction after discussion with tech-lead once the wiring-gap discovery invalidated Decision #24's original premise; recorded here per the change-request/reversal process, not a fresh discovery round. |
| 2026-07-27 | **Refinement — FR30 tunables editor fail-safe now falls back to a last-known-good cache, not a fixed hardcoded literal.** On a failed Supabase fetch, `scripts/config.py` now falls back to the last successfully-fetched value per curated key, read from a repo-committed cache file (`config/tunables_cache.json`), rather than a fixed hardcoded Python default. The cache file is seeded on day one with the then-current hardcoded defaults, and is updated (diff-checked, committed only if changed) on every successful Supabase fetch, reusing the same commit-on-change pattern `.github/workflows/publish-prices.yml` already uses for `pages/prices.json`. Decision #27's core reversal (Supabase table remains source of truth) is unchanged; this refines only the failed-fetch fallback. Added Decision #28 (refines #27). Updated FR30's fail-safe clause and the §10 Configuration note under FR30 accordingly. Flagged as an open note for tech-lead: which workflow(s) own writing back to the cache vs. read-only-consuming it — proposed shape is `hourly-watchlist.yml` as sole writer (most frequent run) with the two discovery-region workflows and `publish-prices.yml` as read-only consumers, pending Arjun's one-line confirmation if he expects a different shape (e.g. every workflow writing back independently). No new FR/NFR IDs — refinement recorded via Decision #28 per this project's established pattern (see #27). Archived the oldest changelog entry (2026-07-12, §11→§10 tunables-baseline sync) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Arjun approved this direction in discussion: a fixed hardcoded literal can silently drift weeks/months stale from what's actually been curated in practice via the portal, defeating the purpose of a portal-editable source of truth; a rolling last-known-good cache stays close to actual practice and reuses a mechanism already proven working in this exact codebase rather than inventing a new one. |
| 2026-07-28 | Doc-sync: added `AI_PROVIDER` (default `gemini`) to the §10 config audit baseline table (Core system), per reviewer finding REV-074 (Pass 14). INC-4's AC5 had only directed dev to add it to `design/non-functional-ops.md` §9; §10 in this document — the table both the runbook and that design doc cite as the actual authoritative baseline — was missed. Same class of gap as REV-019 (2026-07-15). No FR/NFR text changed. | Reviewer finding REV-074: every tunable must appear in the config audit baseline (§10), not only the design-doc mirror. |
| 2026-07-28 | **Reviewer Pass 11 findings routed to pm (REV-040, REV-058, REV-059(b)).** (1) REV-040: Decision #28's confirmed cache-writer shape (`hourly-watchlist.yml` sole writer) was re-opened pending Arjun's reconfirmation — added Decision #29 laying out reviewer's race/privilege findings and the two options (keep `hourly-watchlist.yml` with mitigations, or switch to `publish-prices.yml` per reviewer's recommendation). **Same-day resolution:** Arjun confirmed `hourly-watchlist.yml` stays the sole writer (natural owner — it's the workflow that reads/triggers off the Supabase-scheduled jobs), conditioned on both of reviewer's mitigations shipping: a `concurrency` group shared with `publish-prices.yml`, and a bounded retry around the `git push` step. Decision #29 updated to RESOLVED; the §10 Configuration note under FR30 updated to state the settled shape and its two binding conditions. (2) REV-058: added **NFR7 — Core security posture** (§6) covering RLS, Vault/secrets-never-in-code, no brokerage credentials/execution, and UUID-only detail-page URLs (Decision #17) — content previously mis-cited under NFR3 (Disclaimer) in `design/non-functional-ops.md` and `design.md`'s coverage map. NFR6 now cross-references NFR7 instead of NFR3; Decision #17's rationale column updated to add the NFR7 citation alongside its existing NFR3 one. Added Decision #30 recording the choice and rationale. (3) No FR/NFR text changed beyond the new NFR7; no IDs renumbered. Archived the oldest changelog entry (2026-07-13, NSE shadow wallet pilot) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Reviewer's Pass 11 audit (`docs/review-log.md` REV-040, REV-058, REV-059(b)) routed items to pm per CLAUDE.md's reviewer-finding-routing rule; REV-040 was an open question for Arjun (trade-offs go to the user, not decided silently by pm), resolved same-day by his explicit answer; REV-058's ID choice was pm's call per reviewer's routing note; REV-059(b) resolved as part of the same pass since it interacted directly with REV-040's re-opening. |
| 2026-07-28 | Doc-sync: added `AI_TEMPERATURE` (default `0.2`) to the §10 config audit baseline table (Core system, grouped with the other Gemini call-path tunables), per tech-lead's decision (`review-log.md` REV-078; `design/operational-controls.md` §14.2-14.4) to promote the previously-hardcoded `temperature=0.2` constant to a config tunable. No FR/NFR text changed. Same-class fix as REV-074 (2026-07-28, `AI_PROVIDER`) — this entry exists specifically to avoid that gap recurring (a tunable landing in only one of the two baseline tables: this doc's §10 and `design/non-functional-ops.md` §9). While updating, found the live changelog had grown to 11 entries (one over the 10-most-recent cap) because the REV-074/`AI_PROVIDER` entry above was added without an accompanying archive step — archived the two oldest entries (2026-07-13 paid-tier correction, 2026-07-15 `EVAL_WINDOW_DAYS` doc-sync) to `docs/archive/requirements-changelog-archive.md` to both correct that miss and hold this entry within the 10-most-recent cap. | tech-lead's REV-078 decision, relayed for the §10 baseline-table update; cap correction is routine document hygiene per CLAUDE.md, not a scope change. |
| 2026-07-29 | Doc-sync: added `TUNABLES_FETCH_TIMEOUT_MS` (default `5000`, ms) and `SKIP_TUNABLES_FETCH` (default `false`) to the §10 config audit baseline table (Core system), per reviewer finding REV-087 (Pass 18). Both were introduced in INC-6 (`scripts/config.py`, documented in `design/tunables-fallback.md` per Decision #28/REV-041) but never added to §10 — same class of gap as REV-074 (`AI_PROVIDER`) and REV-078 (`AI_TEMPERATURE`). No FR/NFR text changed. Archived the oldest live entry (2026-07-12, kill-switch fail-open/fail-closed wording correction) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Reviewer finding REV-087: every tunable must appear in the §10 config audit baseline, not only its design-doc mirror. |
| 2026-07-29 | Doc-sync (Phase 4 closure pass): corrected Decision #28 and the §10 Configuration note under FR30 — both still cited the stale `config/tunables_cache.json` path from an early design draft instead of the as-built `tunables_cache.json` at the **repo root** (a repo-root `config/` directory would shadow the flat `scripts/` import path — REV-046 fixed this in code/design on 2026-07-28, but the fix never propagated to this document). Also added the missing description of the fallback's actual shape: **two tiers only** (Supabase table, then the cache file — no third hardcoded-literal tier), and fail-loud via `SystemExit` on a genuine double-miss (key absent from both tiers, or a value present in either tier that fails to cast) rather than silently guessing a default. No FR/NFR IDs added or renumbered; FR30's text is unchanged, only Decision #28 and the §10 note were corrected. Closes reviewer finding REV-068 (open since Pass 15, carried unresolved through Pass 23's Phase-4-closure audit). Archived the oldest live entry (2026-07-16, shadow-track retirement CR) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Reviewer finding REV-068 (`[REQUIREMENTS-GAP]`, owner pm): the as-built cache location and two-tier/fail-loud behavior had drifted from what this document described; surfaced and fixed during pm's Phase-4 "every FR/NFR delivered or deferred" confirmation pass rather than left open into closure. |
| 2026-07-30 | **Change-request impact assessment — `/big-guns` deep review (DEEP-001–007), routed via change-request step 1.** Sharpened **NFR2** ("completes degraded" now explicitly defined so an all-tickers-failed run cannot read heartbeat "ok" — DEEP-001) and **FR17** (holiday/closed-market "no usable data" now explicitly requires a structural stale-bar check, since no holiday calendar exists — DEEP-004, refines Decision #8). Added **FR34** (§5.5: alert delivery/retry semantics — `alerted` means confirmed-delivered, not attempted; verdict state does not advance, and a failed push is retried automatically, until delivery succeeds — DEEP-002) and amended FR15's `alerted`-field definition to match. Amended **FR30** to require write-time validation mirroring `scripts/config.py`'s type/domain contract, so an invalid portal edit is rejected at write time instead of causing a silent behavior change or a system-wide `SystemExit` outage (DEEP-005). Amended **FR11** and **FR29** so holdings currency is derived from `watchlist.market` rather than admin free-choice, closing a latent wrong-P&L path (DEEP-006). Added Decisions Log **#31–#36** recording each fix-the-code/sharpen-the-claim call and a new binding decision (#36) that INC-3 AC3, INC-4 AC6, and INC-7 AC2/AC3 — all previously deferred — must be executed, not left indefinitely deferred, before FR24–FR26/FR33/FR31–FR32 are marked "delivered" at closure. **DEEP-003** (positional-fallback parse-attribution bug) has no requirements-level face — routed to tech-lead as a design/code contract issue, no FR/NFR added. **DEEP-007** (FR24's kill-switch boundary: does the guarantee cover an in-flight run, or only future dispatches) is an open trade-off with materially different cost/behavior implications — **not resolved here**; returned to the user as a question before tech-lead can design a fix (see this changelog's companion question, routed by the orchestrator). Archived the oldest live entry (2026-07-16, shadow-track retirement CR resolution) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | User's explicit 2026-07-30 direction: fix all six blocker/major `/big-guns` findings before tagging `v0.1.0`, and make the three deferred live checks requirement-traceable so closure cannot quietly skip them again; per-finding fix-vs-claim calls are pm's own, per the change-request process's no-inference rule (one genuine open trade-off, DEEP-007, held back for the user rather than guessed). |
| 2026-07-30 | **Follow-on to Decision #37 — added FR35, amended FR25, cross-referenced FR32 (pause-triggered mid-run abort).** Now that INC-8's heartbeat/degraded-accounting rewrite has landed (`run_hourly.py`/`run_discovery.py` as shipped: `degraded = outcomes["skip"] + outcomes["error"] + outcomes["no-read"] + outcomes["push-failed"]`), resolved the gap pm flagged when reworking FR24: FR25's "absence of runs is expected-quiet" only covers a run that never starts (FR24 checkpoint 1); it did not cover FR24 checkpoints 2/3 aborting a run that has already produced real, logged per-ticker work. Amended **FR25** (§5.10) to state explicitly which case it covers (checkpoint 1 only) and point to the new requirement for the rest. Added **FR35** (§5.10): a mid-run pause abort at checkpoint 2/3, after at least one real `call_log` row exists for the cycle, is expected-quiet for NFR2 purposes — but only when the classification is causally tied to the specific checkpoint-and-flag-read event (never inferred from an outcome count or missing heartbeat, which a genuine crash also produces), and never when it would suppress a real degraded signal already present in the same run (NFR2/Decision #31 keeps applying in full). Confirmed no new de-duplication/resume machinery is needed for track-record integrity — FR15's per-check logging plus FR7/FR8's existing crossings-only comparison already make re-evaluation on the next normal cycle safe. Checkpoint 1 stays under FR25 (unchanged); checkpoint 4 (`publish_prices.py`'s commit) stays under FR25 too, since no per-ticker logged work exists there to protect. Amended **FR32** to add FR35 to the list of behaviors the portal's kill-switch UI inherits automatically. Added **Decision #38**. Archived the oldest live entry (2026-07-26, kill-switch/admin-portal/AI-provider-abstraction CR) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Sequencing was itself part of Decision #37 (INC-12 strictly after INC-8, since designing the abort-accounting contract before INC-8 settled "degraded" would mean guessing at a shape INC-8 might change out from under it); with INC-8 landed (qa PASS, reviewer Pass 24 CLEAR) the shape is now known and this follow-on is resolvable. The causal-tie requirement exists specifically to prevent a genuine failure from being misreported as a deliberate pause, which the orchestrator flagged as the exact loophole to avoid. |
