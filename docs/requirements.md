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
    written under FR15 for tickers processed before the abort point are real, complete work product — a
    genuine, timestamped per-ticker outcome for that cycle (an AI-judged verdict, or a fail-safe no-read
    Hold logged when the ticker's data could not be read), never a skipped no-op — and are retained
    exactly as logged, never deleted, retracted, or re-flagged as invalid on resume. ("Real," here and in
    this FR's opening paragraph, means non-skip — not exclusively "produced by a completed AI call" — so a
    no-read row counts as real work product for this purpose, consistent with how the implementation
    computes `real_rows_this_cycle`, §13.6.2/§13.6.3 of `design/operational-controls.md`.) No de-duplication or "resume where it left off" mechanism is required
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
  replacing manual SQL edits to the `watchlist` table. **As of the 2026-08-01 change request, this
  capability is presented via the merged Tickers screen (FR36), not a standalone "Watchlist" screen — the
  capability described here is unchanged, only its screen/navigation surface.**
- **FR29** — The portal can add, edit, and remove holdings data (shares, cost basis) for held tickers,
  replacing manual SQL edits to the `holdings` table. **Currency is not an independently admin-chosen
  field — it is derived automatically from the ticker's market (`watchlist.market`): US⇒USD, TSX⇒CAD,
  NSE⇒INR.** This removes the free-choice currency/market mismatch that FR11's gain/loss calculation
  depends on not existing (Decision #35). **As of the 2026-08-01 change request, this capability is
  presented via the merged Tickers screen's card/modal (FR36), not a standalone "Holdings" screen, and the
  watch-only↔held status transition that creates/updates/deletes this data is now gated per FR37 — the
  underlying CRUD capability and validation described here are otherwise unchanged.**
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
- **FR36** — (change request, 2026-08-01; Decision #40) The portal's watchlist and holdings screens are
  merged into a single screen, renamed **"Tickers"** (replacing the "Watchlist" label; the standalone
  "Holdings" screen and its separate nav item are removed — nav goes from four items to three: Tickers,
  Tunables, Track record). This is a **UI/navigation consolidation only**: the underlying `watchlist` and
  `holdings` tables, their schemas, and FR28/FR29's CRUD capability are unchanged — the Tickers screen
  reads/writes both tables, joined by `ticker`, from one screen instead of two. Each ticker renders as
  **one card per row** (not a multi-column grid, at phone, tablet, and desktop widths alike — this
  supersedes INC-13/14's watchlist/holdings 4-col/3-col/2-col card-grid density, which no longer applies
  once the two screens are merged into this one; the track-record view's own 3-col/2-col/1-col card grid,
  §16.10, is a separate screen and is unaffected). Each card shows:
  1. Watch-only or held status; if held, shares owned and price per share (the existing
     `holdings.shares`/`holdings.cost_basis` fields — "price per share" is a UI relabel of `cost_basis`,
     not a new field, since `cost_basis` is already used as a per-share value in FR11's gain/loss
     calculation);
  2. The latest verdict, its timestamp, and its **confidence level** — the model's self-rated confidence
     (`high`/`medium`/`low`), already produced by the AI judgment call and already stored per FR15 in
     `call_log.data_snapshot.confidence` (previously surfaced only on the public dashboard/detail page,
     FR21/FR14 — not new data, a new display surface for already-tracked data);
  3. The verdict's rationale.

  Clicking a card opens a modal (replacing today's small per-row edit-icon affordance) showing the
  ticker's full identifying info (ticker, market, type, status) plus the card's own content above, with a
  single combined edit form covering both the watchlist fields (market, type, status) and the holdings
  fields (shares, price per share) for that ticker, and a delete action. The modal is the sole edit
  surface for a ticker on this screen — FR28/FR29's existing validation rules (CHECK constraints,
  currency derivation per Decision #35) apply unchanged to whichever of the two tables the edit touches.
- **FR37** — (change request, 2026-08-01; Decision #40) Within the FR36 modal, changing a ticker's status
  from watch-only to held requires **shares owned and price per share** to be entered — both mandatory —
  before the change can be saved; save is blocked until both are provided and pass FR29's existing
  validation (`shares > 0`, `cost_basis > 0`). On save, this creates or updates the ticker's `holdings`
  row. Conversely, changing status from held to watch-only **deletes the ticker's `holdings` row**,
  behind a confirmation prompt naming the ticker and the shares/price being discarded — this keeps
  `watchlist.status = 'held'` and "a `holdings` row exists for this ticker" as a single enforced
  invariant, with no orphaned/stale holdings data left behind for a watch-only ticker that could
  silently reappear unconfirmed on a later status flip (pm's recommended default, since prior to this CR
  the two facts could already drift independently — see Configuration/Decision #40 note).
- **FR38** — (change request, 2026-08-01; Decision #40) The admin portal's user-facing name changes from
  "Admin Portal" to **"Sentinel Portal"** — the browser tab `<title>` and the header brand label. This is
  a UI string change only: this document's own §5.11 section name and other internal design-doc/code
  references to "admin portal" are unaffected unless separately requested (pm's recommended default).

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
- **NFR8 — Admin portal UI/UX quality (responsive & modern) (change request, 2026-07-31; Decision #39;
  amended 2026-08-01, Decision #40):**
  The admin portal's **four** screens — login (FR27), the merged Tickers screen (FR28/FR29/FR36/FR37), the
  tunables editor (FR30), the track-record view (FR31), and the kill-switch toggle (FR32, surfaced on the
  shared header, not its own screen) — must be visually modernized and fully responsive, with **no change
  to FR27–FR32's underlying CRUD/auth/tunables/track-record/kill-switch behavior, the `is_admin()`/RLS
  authorization model, or any data model/schema beyond what FR36/FR37 themselves specify**. This is a
  UI/UX-only requirement except where FR36/FR37/FR38 explicitly say otherwise. **(Screen count corrected
  2026-08-01 from the original "five screens": FR36 merges the former separate watchlist/holdings screens
  into one, per the 2026-08-01 change request — see Decision #40.)**
  - **Responsive (all four screens, all three device classes):** at phone, tablet, and desktop viewport
    widths, every screen renders with no horizontal scrolling, no overlapping/clipped/truncated content,
    and every interactive control (buttons, form fields, table rows/row-actions, the kill-switch toggle)
    remains reachable and operable. The exact breakpoint pixel values that define "phone/tablet/desktop"
    are a tech-lead design decision (`docs/design.md`), not a requirements decision — this NFR is
    satisfied when the three device classes Arjun actually uses render correctly, not by a specific
    pixel number.
  - **Navigation mechanism (added 2026-08-01, change request; Decision #40):** below the tech-lead-chosen
    breakpoint, the nav collapses behind a burger-menu control (unchanged mechanism). **At desktop width,
    the nav must render as a single, literal horizontal row — not a vertically stacked list.** This is
    stated explicitly here because a defect was found in the shipped INC-13/14 implementation (nav links
    rendering stacked vertically at desktop width instead of horizontally, as the approved design already
    intended) — **tech-lead is to root-cause and fix this as a defect against the already-approved
    design**, not treat it as new scope. Separately, as new design intent: if the full nav set doesn't fit
    un-scrolled at some tech-lead-determined mid-width tier, an intentionally horizontally-scrollable nav
    container is permitted at that tier as an alternative to the burger control. This is an explicit,
    narrow carve-out to this NFR's general "no horizontal scrolling" bar, scoped **only** to the nav
    container — it does not permit horizontal scrolling anywhere else on any screen.
  - **Modern visual design, via approved mockups:** the designer researches modern admin/SaaS UI patterns
    (no fixed reference or brand constraint given) and proposes 2–3 distinct mockup directions covering
    all four screens (and the merged Tickers screen's card-per-row/modal layout and new nav mechanism) in
    `docs/ux-spec.md`; the user selects one direction before any implementation begins (this selection is
    the GATE — dev may not start until it is made); the delivered UI must match the approved direction's
    mockups. This mockups-before-implementation sequencing is an explicit, non-skippable condition of this
    NFR, not merely a process preference. The existing approved Direction G mockups (§16.10) predate
    FR36–FR38 and must be extended/re-approved to cover the merged screen and new nav before dev builds
    against them.
  - **Accessibility — best-effort, no formal target:** no WCAG conformance level or other formal
    accessibility standard is required or tested against, per the user's explicit choice (single-user,
    internal-tool posture, consistent with this system's existing single-user framing throughout §3/§4).
    Reasonable best-effort practices (legible contrast, keyboard-focusable controls where practical) are
    encouraged but not a pass/fail gate.
  - **No functional regression:** qa's acceptance criteria for the increment(s) implementing this NFR
    must confirm zero behavioral regression to FR27, FR30–FR32 (login/auth, tunables validation,
    track-record data, kill-switch mechanics) and to FR28/FR29's underlying CRUD *capability* (not their
    former two-screen presentation, which FR36 explicitly and intentionally supersedes) alongside the
    visual/responsive changes and FR36/FR37's new merged-screen/modal behavior — this NFR adds a
    presentation-layer bar on top of those FRs, it does not modify their data-level guarantees.

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
| 39 | Admin Portal UI/UX modernization — **RESOLVED 2026-07-31** — scope confirmed by Arjun; added NFR8 | Arjun's CR: the admin portal (FR27–FR32) UI "is not screen size responsive" and "looks very basic" — modernize it. Explicitly **UI/UX enhancement only**: no change to FR27–FR32's functional behavior, `is_admin()`/RLS authorization model, or any table schema. Arjun's answers to pm's clarifying questions, resolving every open item: **(1) Screens in scope:** all five — login (FR27), watchlist/holdings CRUD (FR28/FR29), tunables editor (FR30), track-record view (FR31), kill-switch toggle (FR32). **(2) Breakpoints/devices:** phone + tablet + desktop, full responsive range (exact pixel breakpoints left to tech-lead as a design decision). **(3) "Modern" definition:** no fixed reference or brand constraint — the designer researches modern admin/SaaS UI patterns and proposes 2–3 distinct mockup directions in `docs/ux-spec.md`; Arjun picks one before implementation starts. **(4) Accessibility bar:** best-effort only, no formal WCAG target — single-user internal tool. Resolved into **NFR8** (§6). Gate unchanged and non-negotiable: designer's `docs/ux-spec.md` mockups/wireframes must be produced and the user must approve one direction before dev touches any code. | Same-class handling as DEEP-007 (Decision #37): a genuine, user-facing trade-off (scope/breakpoints/definition of "modern") is a decision for the user, not pm's or tech-lead's to infer or default. All four open items were answered directly by Arjun with no ambiguity remaining, so this decision is now closed and its content is captured as a testable NFR rather than left as an open record. |
| 40 | Admin Portal redesign change request (nav, branding, Tickers merge, clickable cards) — **RESOLVED 2026-08-01** — added FR36–FR38, amended FR28/FR29/NFR8 | Arjun's CR, itemized: (1) nav redesign (burger/horizontal-scroll by screen size); (2) rename "Admin Portal"→"Sentinel Portal"; (3) rename "Watchlist"→"Tickers" and merge Watchlist+Holdings into one screen; (4) ticker cards become clickable, opening a modal with full info + edit/delete, with a mandatory shares/price-per-share prompt when a card's status flips watch-only→held, and a reversion to one-card-per-row (reversing INC-13/14's grid density). pm's impact assessment found: **confidence level already exists** as tracked data (`ai_judge.py`'s `VALID_CONFIDENCE`, stored in `call_log.data_snapshot.confidence` per FR15, already surfaced on the dashboard/detail page) — not new AI-output/schema scope, a display-only extension (FR36). The Tickers merge/card-modal/mandatory-capture items are genuine functional scope, not pure UI — added **FR36** (merged Tickers screen, card content/layout, modal), **FR37** (mandatory shares/price-per-share on watch-only→held; delete-with-confirmation on held→watch-only), **FR38** (branding rename). Amended FR28/FR29 with forward-references to FR36/FR37 (capability unchanged, presentation surface changed) and NFR8 (four screens not five; new navigation-mechanism bullet; functional-regression bullet updated). **Arjun's answers to pm's clarifying questions:** data model — UI-only merge, no schema change (confirmed); Holdings page — replaced entirely, folded into the Tickers modal, nav goes 4→3 items (confirmed); price-per-share — same field as existing `cost_basis`, relabeled only (confirmed); nav — the "redesign" premise was wrong: current desktop/tablet nav is a **real defect** (links render stacked vertically instead of horizontally, contrary to the already-approved INC-13/14 design), routed to **tech-lead to root-cause and fix as a defect**, not new scope; on top of the fix, Arjun's original burger-or-horizontal-scroll intent stands as new design content, added to NFR8 as an explicit narrow carve-out to its "no horizontal scrolling" bar (nav container only). **pm's recommended defaults, applied since Arjun deferred to pm's judgment on these and asked them stated explicitly rather than silently assumed:** branding rename is UI-strings-only, no doc-reference renaming; held→watch-only deletes the holdings row behind a confirmation prompt (not keep-and-hide) to preserve "status=held ⇔ a holdings row exists" as a single enforced invariant; the modal's edit form combines both watchlist and holdings fields as one (since the two screens are merging anyway); one-card-per-row applies to the new Tickers screen only, at all three breakpoints, per the CR's literal ask; the track-record screen's existing card grid is unaffected; this CR is sequenced **after INC-14 closes** (INC-14 is an open defect-fix against the very screens this CR redesigns — layering new scope on an unresolved defect risks conflating the two). **Routed to tech-lead next:** the nav defect's root cause and fix design; the Tickers-merge screen/modal architecture; the card/modal visual redesign (in coordination with designer's mockup update, since Direction G's existing mockups predate FR36–FR38 and must be extended/re-approved before dev builds). | Per CLAUDE.md's change-request process: pm assesses impact and applies the no-inference rule before any requirement text is drafted; genuine functional scope (page merge, new mandatory-workflow trigger) is captured as FR IDs rather than absorbed into an NFR, per the same discipline Decision #39 itself was written to enforce (NFR8 governs presentation quality, not new capability). pm's defaults are stated explicitly, as directed, so they are visible and overridable by Arjun rather than silently assumed. |

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
| `NTFY_BASE_URL` | `https://ntfy.sh/` | ntfy push endpoint base URL (`notify.NtfyNotifier`) |
| `NTFY_TIMEOUT_SECONDS` | `10` | Per-request timeout (seconds) for the ntfy push call |
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

## 11. Phase 4 Closure — FR/NFR Delivery Confirmation (2026-07-30)

**Basis.** `docs/review-log.md` Pass 29: zero open blockers, zero open majors anywhere in the live log;
DEEP-001 through DEEP-007 (the `/big-guns` deep-review findings) all independently re-verified RESOLVED;
INC-3 through INC-12 all dev-built, qa-PASS, and reviewer-CLEAR. `docs/handoff.md`'s "Evidence record:
INC-11 live-verification pass (Decision #36)" section supplies the three live checks Decision #36 made
mandatory before this confirmation could be written. Per this document's role as the record of what was
promised, every FR/NFR below is marked **Delivered** (implemented, tested, reviewer-cleared, and — where
Decision #36 required it — live-verified) or **Deferred** (implemented and reviewer-cleared, but a
required live-verification step has not yet run). No FR/NFR is silently dropped; none was descoped.

### Delivered

FR1–FR10, FR12–FR14, FR16, FR18–FR23 — core v1 behavior (watchlist/holdings, discovery, monitoring,
alerting, dashboard, timestamps). Unchanged since original approval; no open reviewer finding disputes
their delivered behavior.

FR11, FR15, FR17, FR29, FR30, FR34 — each was sharpened mid-round by a `/big-guns` DEEP finding
(Decisions #31–#35) and independently confirmed to match its amended text, not just its original intent:
- **FR11/FR29** (currency derived from `watchlist.market`, not admin free-choice) — INC-10's
  `holdings_currency_derivation` trigger, live-confirmed present and enabled on `public.holdings`
  (handoff.md INC-11 evidence, item 6).
- **FR15** (`alerted` means confirmed-dispatched, not merely attempted) and **FR34** (delivery-confirmed
  alerting with automatic retry) — INC-8, reviewer Pass 24 CLEAR.
- **FR17** (structural stale-bar/closed-market check, no maintained holiday calendar) — INC-9, reviewer
  Pass 25 CLEAR.
- **FR30** (portal write-time validation mirrors `scripts/config.py`'s cast contract) — INC-10's
  `tunables_validate_trigger`, live-confirmed rejecting an invalid `ALERTS_ENABLED` value inside a
  rolled-back transaction against the production database (handoff.md INC-11 evidence, item 6 — DEEP-005
  proven closed live, not only against a local scratch database).

FR24, FR25, FR26 (kill-switch: pause/resume, dead-man-monitor pause-awareness, audit logging) — INC-3
implemented, reviewer-cleared; live-verified per Decision #36: INC-3 AC3 executed 2026-07-30 against the
production project — pause suppressed a scheduled dispatch (no `hourly-watchlist.yml` run created at
`19:12`), resume restored normal dispatch, and `kill_switch_audit` gained exactly one row per toggle
(`docs/handoff.md`, INC-11 evidence item 2). Moved from "deferred, pending live execution" to
**Delivered**.

FR35 (pause-triggered mid-run abort classification, follow-on to Decision #37/#38) — **Delivered.**
INC-12 implemented; reviewer Pass 29 independently re-verified RESOLVED (DEEP-007 closed): the causal-tie
mechanism, the non-suppression of a genuine same-run degraded signal, and the
checkpoint-1-precedes-tunables-write ordering were each re-traced directly against current code and two
new regression tests confirmed to fail on pre-fix code and pass on the fix. `sql/kill_switch_abort_log.sql`
— the table FR35's causal-tie audit trail writes to — was independently verified correct and idempotent
against two separate local Postgres instances (dev's and qa's) *and* has since been **applied to the live
Supabase project** (post-Pass-29, orchestrator-executed, verified directly): the table is present in
`public` with `rls_enabled = true`, `rls_forced = true`, `policy_count = 0` (the intended deny-all
posture), and an `anon` INSERT attempt was empirically denied (`permission denied for table
kill_switch_abort_log`) — no one can forge a proof-of-pause row. One expectation correction, not a defect:
the post-apply `role_table_grants` query returned **six rows, not zero** — `anon` and `authenticated` each
hold `REFERENCES, SELECT, TRIGGER`, which are Supabase's standard defaults on any new public-schema table,
identical to `admin_allowlist`, `kill_switch_audit`, and `kill_switch_state`. `TRUNCATE`/`INSERT`/`UPDATE`/
`DELETE` are absent from both roles' grants, which is what the REVOKE was actually written to guarantee;
qa's follow-up query's zero-rows expectation was the thing that was wrong, not the SQL or its application.
No outstanding pre-tag step remains for FR35.

FR33 (AI provider abstraction) — INC-4 implemented; reviewer Pass 15 CLEAR on 5 of 6 tests, with AC6 (a
live Gemini smoke test) previously deferred for lack of a `GEMINI_API_KEY` in any build environment.
Live-verified per Decision #36: 90 consecutive `call_log` rows in production, all `parse_status='ok'`,
`model_used='gemini-2.5-flash'`, `fallback_from=null` (`docs/handoff.md`, INC-11 evidence item 3) — stronger
evidence than the one-off smoke test AC6 originally asked for. Moved from "deferred, pending live
execution" to **Delivered**.

FR27, FR28 (admin portal: Google-OAuth login, watchlist CRUD) — INC-5, reviewer Pass 17 CLEAR.

NFR1, NFR3, NFR4, NFR5, NFR6, NFR7 — unchanged or additively documented (NFR7 added per Decision #30); no
open reviewer finding disputes delivered behavior.

NFR2 ("completes degraded" explicitly defined so an all-tickers-failed run cannot read heartbeat "ok") —
INC-8, reviewer Pass 24 CLEAR; code's `degraded` bucket (`skip`+`error`+`no-read`+`push-failed`) matches
the amended definition exactly.

### FR31, FR32 — Deferred, pending live execution (resolved by user decision, 2026-07-31)

**FR31, FR32** (admin portal: read-only track-record view, kill-switch UI toggle) — INC-7 implemented,
qa-PASS, reviewer Pass 20 CLEAR. Per Decision #36, two live checks gate these: INC-7 Step 0 (confirm
`sql/kill_switch_portal_grant.sql` is live) **passed** 2026-07-30 — the `admin_read_kill_switch` policy and
`set_kill_switch()` RPC are confirmed present and correctly `is_admin()`-gated against production
(`docs/handoff.md`, INC-11 evidence item 4). **INC-7 AC2/AC3 — the portal's own RPC round-trip and a live
proof that toggling the kill switch through the portal actually suppresses dispatch — have not run.** Both
require an authenticated admin **browser** session against the live Vercel-hosted portal (Google OAuth
login through the deployed UI); no subagent or the orchestrator had one available in this environment.

**What is and isn't verified, precisely:**
- **Verified:** INC-7 Step 0 — the `admin_read_kill_switch` policy and the `is_admin()`-gated
  `set_kill_switch()` RPC are confirmed live and correctly configured in production.
- **Verified, but via a different path:** the kill-switch mechanism itself — pause suppresses dispatch,
  resume restores it — was exercised live (INC-3 AC3, recorded in `docs/handoff.md`). That exercise ran
  under the `postgres` service-role credential directly via SQL, so the resulting `kill_switch_audit` row
  carries `actor='postgres'`, not an authenticated portal user.
- **Not verified — AC2/AC3 specifically:** (1) the portal's own authenticated-browser RPC round-trip
  through `set_kill_switch()`, and (2) dispatch suppression proven from a **portal-initiated** pause (i.e.,
  a `kill_switch_audit` row with an authenticated admin user, not `postgres`, as `actor`). Neither has run
  in any environment available during this build. It is the portal's own call path that is untested here —
  not the kill switch as a whole, which is independently proven live via the service-role path above.
- **Not verified — FR31 itself (gap identified per REV-142):** none of the checks above, nor the original
  five-step closure checklist, ever load the track-record view and confirm it renders real data. Step 6
  below closes this gap.

**pm's recommendation, offered to the user as a decision only they could make (not decided by pm):**
1. **Hold the `v0.1.0` tag** until the user could log into the deployed admin portal themselves (a
   two-minute check: toggle the kill switch via the portal UI, confirm the `kill_switch_audit` row shows an
   authenticated admin user as `actor`, and confirm no scheduled dispatch fires while paused), then tag once
   that passes — the option Decision #36 was written to force, closing the loop with the same standard every
   other deferred check in this project was held to (INC-3 AC3, INC-4 AC6, both closed the same way).
2. **Tag `v0.1.0` now with FR31/FR32 explicitly recorded as "deferred, pending live execution,"** on the
   reasoning that the code is reviewer-cleared with zero blockers/majors, the underlying RPC and its
   authorization gate are independently confirmed live (Step 0 passed), and the only unverified step is the
   portal UI's own call path to an RPC already proven safe via the identical service-role exercise — a
   materially smaller risk than the other two checks Decision #36 named, both of which are closed.

pm recommended **option 1** as the option that removes the one remaining assumption in an admin control
surface for a system that pauses real AI/push/commit side-effecting work, while noting **option 2** is a
defensible, explicitly-labeled fallback if portal access wasn't available before tagging. This
recommendation is retained here as part of the record — that option 1 was offered and consciously
declined, not omitted or overlooked.

**Decision (final): the user chose option 2, 2026-07-31.** FR31 and FR32 are tagged in `v0.1.0` as
**Deferred, pending live execution**, by the user's explicit choice, not by default or by pm's
recommendation. This is not an open-ended deferral: it closes on the concrete steps below, whenever the
user next has portal access.

**Steps to close FR31/FR32 (unchanged scope, no new design/code required unless a step fails):**
1. Sign in to the deployed admin portal as an allowlisted admin (Google OAuth).
2. Toggle the kill-switch UI to pause.
3. Confirm a new `kill_switch_audit` row appears with the authenticated admin user as `actor` (not
   `postgres`).
4. Confirm `run_heartbeat.last_run_at` does not advance past the pause — i.e., no new scheduled run
   executes while paused.
5. Resume via the same portal UI, and confirm `run_heartbeat.last_run_at` advances again on the next cycle.
6. **(FR31-specific — added per REV-142)** Confirm the track-record view (`/track-record`) renders
   non-empty, real `call_log` data for that same signed-in admin. Steps 1-5 exercise only FR32's
   kill-switch mechanics; none of them observes FR31's own surface. This step is the sole documented
   criterion for FR31 and must pass independently of steps 1-5.

On all six passing, a future changelog entry moves FR31/FR32 from Deferred to Delivered; a failure at any
step routes back through the normal qa/reviewer path, not a silent status change. (Step 6 exists because
BUG-009 — `call_log`'s RLS policy silently anon-only in production, leaving the track-record view empty for
every signed-in admin — was found only because qa went beyond this checklist's original five steps; without
step 6, all five could pass and FR31 be marked Delivered while the view itself was never confirmed to render
data.)

### Deployment status (added 2026-07-31 — does not change any FR/NFR status above)

The fix round behind INC-8 through INC-12 (the `/big-guns` DEEP-001–007 fixes several "Delivered"
determinations above cite by reviewer clearance and regression test) has been **merged to `main`**
(fast-forward `ef254d1..bf42ad6`, 2026-07-31). Before this merge, production ran pre-fix code:
`dispatch_github_workflow` dispatches scheduled runs with `ref: 'main'`, so INC-8 through INC-12's code
changes take effect starting with the **next scheduled dispatch after the merge**, not before it. This
does not revise any "Delivered" determination above — none of them rested on the application code being
live on `main`. The live-verification claims for FR11/FR29, FR30, and FR35 rest on the four SQL files
associated with this fix round (`sql/holdings_currency_derivation.sql`, `sql/tunables_validate_trigger.sql`,
`sql/admin_portal_tunables_alerts_enabled_description_fix.sql`, `sql/kill_switch_abort_log.sql`), which
were applied to production **ahead of** the code merge and independently verified harmless in that
ahead-of-code pairing; the FR24–FR26 and FR33 live-verification claims rest on the pre-existing
service-role/production-data paths described above, not on INC-8–12's code. No FR/NFR status changes as a
result of this note; it exists so a later reader of this closure record has the correct deploy timeline.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-07-29 | Doc-sync: added `TUNABLES_FETCH_TIMEOUT_MS` (default `5000`, ms) and `SKIP_TUNABLES_FETCH` (default `false`) to the §10 config audit baseline table (Core system), per reviewer finding REV-087 (Pass 18). Both were introduced in INC-6 (`scripts/config.py`, documented in `design/tunables-fallback.md` per Decision #28/REV-041) but never added to §10 — same class of gap as REV-074 (`AI_PROVIDER`) and REV-078 (`AI_TEMPERATURE`). No FR/NFR text changed. Archived the oldest live entry (2026-07-12, kill-switch fail-open/fail-closed wording correction) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Reviewer finding REV-087: every tunable must appear in the §10 config audit baseline, not only its design-doc mirror. |
| 2026-07-29 | Doc-sync (Phase 4 closure pass): corrected Decision #28 and the §10 Configuration note under FR30 — both still cited the stale `config/tunables_cache.json` path from an early design draft instead of the as-built `tunables_cache.json` at the **repo root** (a repo-root `config/` directory would shadow the flat `scripts/` import path — REV-046 fixed this in code/design on 2026-07-28, but the fix never propagated to this document). Also added the missing description of the fallback's actual shape: **two tiers only** (Supabase table, then the cache file — no third hardcoded-literal tier), and fail-loud via `SystemExit` on a genuine double-miss (key absent from both tiers, or a value present in either tier that fails to cast) rather than silently guessing a default. No FR/NFR IDs added or renumbered; FR30's text is unchanged, only Decision #28 and the §10 note were corrected. Closes reviewer finding REV-068 (open since Pass 15, carried unresolved through Pass 23's Phase-4-closure audit). Archived the oldest live entry (2026-07-16, shadow-track retirement CR) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Reviewer finding REV-068 (`[REQUIREMENTS-GAP]`, owner pm): the as-built cache location and two-tier/fail-loud behavior had drifted from what this document described; surfaced and fixed during pm's Phase-4 "every FR/NFR delivered or deferred" confirmation pass rather than left open into closure. |
| 2026-07-30 | **Change-request impact assessment — `/big-guns` deep review (DEEP-001–007), routed via change-request step 1.** Sharpened **NFR2** ("completes degraded" now explicitly defined so an all-tickers-failed run cannot read heartbeat "ok" — DEEP-001) and **FR17** (holiday/closed-market "no usable data" now explicitly requires a structural stale-bar check, since no holiday calendar exists — DEEP-004, refines Decision #8). Added **FR34** (§5.5: alert delivery/retry semantics — `alerted` means confirmed-delivered, not attempted; verdict state does not advance, and a failed push is retried automatically, until delivery succeeds — DEEP-002) and amended FR15's `alerted`-field definition to match. Amended **FR30** to require write-time validation mirroring `scripts/config.py`'s type/domain contract, so an invalid portal edit is rejected at write time instead of causing a silent behavior change or a system-wide `SystemExit` outage (DEEP-005). Amended **FR11** and **FR29** so holdings currency is derived from `watchlist.market` rather than admin free-choice, closing a latent wrong-P&L path (DEEP-006). Added Decisions Log **#31–#36** recording each fix-the-code/sharpen-the-claim call and a new binding decision (#36) that INC-3 AC3, INC-4 AC6, and INC-7 AC2/AC3 — all previously deferred — must be executed, not left indefinitely deferred, before FR24–FR26/FR33/FR31–FR32 are marked "delivered" at closure. **DEEP-003** (positional-fallback parse-attribution bug) has no requirements-level face — routed to tech-lead as a design/code contract issue, no FR/NFR added. **DEEP-007** (FR24's kill-switch boundary: does the guarantee cover an in-flight run, or only future dispatches) is an open trade-off with materially different cost/behavior implications — **not resolved here**; returned to the user as a question before tech-lead can design a fix (see this changelog's companion question, routed by the orchestrator). Archived the oldest live entry (2026-07-16, shadow-track retirement CR resolution) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | User's explicit 2026-07-30 direction: fix all six blocker/major `/big-guns` findings before tagging `v0.1.0`, and make the three deferred live checks requirement-traceable so closure cannot quietly skip them again; per-finding fix-vs-claim calls are pm's own, per the change-request process's no-inference rule (one genuine open trade-off, DEEP-007, held back for the user rather than guessed). |
| 2026-07-30 | **Follow-on to Decision #37 — added FR35, amended FR25, cross-referenced FR32 (pause-triggered mid-run abort).** Now that INC-8's heartbeat/degraded-accounting rewrite has landed (`run_hourly.py`/`run_discovery.py` as shipped: `degraded = outcomes["skip"] + outcomes["error"] + outcomes["no-read"] + outcomes["push-failed"]`), resolved the gap pm flagged when reworking FR24: FR25's "absence of runs is expected-quiet" only covers a run that never starts (FR24 checkpoint 1); it did not cover FR24 checkpoints 2/3 aborting a run that has already produced real, logged per-ticker work. Amended **FR25** (§5.10) to state explicitly which case it covers (checkpoint 1 only) and point to the new requirement for the rest. Added **FR35** (§5.10): a mid-run pause abort at checkpoint 2/3, after at least one real `call_log` row exists for the cycle, is expected-quiet for NFR2 purposes — but only when the classification is causally tied to the specific checkpoint-and-flag-read event (never inferred from an outcome count or missing heartbeat, which a genuine crash also produces), and never when it would suppress a real degraded signal already present in the same run (NFR2/Decision #31 keeps applying in full). Confirmed no new de-duplication/resume machinery is needed for track-record integrity — FR15's per-check logging plus FR7/FR8's existing crossings-only comparison already make re-evaluation on the next normal cycle safe. Checkpoint 1 stays under FR25 (unchanged); checkpoint 4 (`publish_prices.py`'s commit) stays under FR25 too, since no per-ticker logged work exists there to protect. Amended **FR32** to add FR35 to the list of behaviors the portal's kill-switch UI inherits automatically. Added **Decision #38**. Archived the oldest live entry (2026-07-26, kill-switch/admin-portal/AI-provider-abstraction CR) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Sequencing was itself part of Decision #37 (INC-12 strictly after INC-8, since designing the abort-accounting contract before INC-8 settled "degraded" would mean guessing at a shape INC-8 might change out from under it); with INC-8 landed (qa PASS, reviewer Pass 24 CLEAR) the shape is now known and this follow-on is resolvable. The causal-tie requirement exists specifically to prevent a genuine failure from being misreported as a deliberate pause, which the orchestrator flagged as the exact loophole to avoid. |
| 2026-07-30 | **Phase 4 closure — FR/NFR delivery confirmation (§11 added); FR24–FR26 and FR33 moved from "deferred, pending live execution" to Delivered on live evidence (Decision #36); FR31/FR32 remain Deferred, routed back to the user as a decision, not resolved here; FR35 wording corrected (REV-120); two missing tunables added to the §10 audit baseline (REV-066/REV-052, pm half).** Added §11 "Phase 4 Closure — FR/NFR Delivery Confirmation," walking every FR/NFR to Delivered or Deferred status per Decision #36's binding rule. FR24–FR26: Delivered — INC-3 AC3 executed live 2026-07-30 (dispatch suppressed while paused, `kill_switch_audit` gained exactly one row per toggle). FR33: Delivered — INC-4 AC6 satisfied by 90 consecutive live `call_log` rows, all `parse_status='ok'`, zero fallbacks, stronger evidence than the one-off smoke test the AC asked for. FR31/FR32: still Deferred — INC-7 AC2/AC3 (the portal's own authenticated-browser RPC round-trip and live dispatch-suppression proof) have not run in this environment; §11 records pm's explicit recommendation and both options for the user, per Decision #36's rule that this choice is not pm's to make silently. Also recorded, not a requirements change: `sql/kill_switch_abort_log.sql` (FR35's causal-tie audit table) — verified correct twice locally, and since applied live to the production project and independently confirmed (deny-all RLS posture, zero write/truncate grants for `anon`/`authenticated`, an `anon` INSERT empirically denied); the post-apply grant query returning six rows instead of zero was qa's expectation being wrong, not the SQL, since those six are Supabase's standard REFERENCES/SELECT/TRIGGER defaults already present on every comparable table in this project — no outstanding pre-tag step remains for FR35. Corrected **FR35**'s track-record-integrity bullet (§5.10): removed the overclaim that every "real" `call_log` row is "a real verdict from a real AI call" — a no-read row (fail-safe Hold, no AI call made) is real/non-skip work product for this FR's purposes exactly as the implementation computes `real_rows_this_cycle`, and the text now says so explicitly, closing reviewer finding REV-120 (no behavior/gating implication — the field is informational). Added `NTFY_BASE_URL` (`https://ntfy.sh/`) and `NTFY_TIMEOUT_SECONDS` (`10`) to the §10 Core-system config audit baseline table — present in `scripts/config.py` since before this pass but missing from this baseline, per reviewer finding REV-066/REV-052 (pm half; the `non-functional-ops.md` §9 half remains tech-lead's, still open). No FR/NFR IDs added; no FR/NFR text changed beyond FR35's wording correction. Archived the oldest live entry (2026-07-30, DEEP-007 resolution) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Phase-4 closure requires pm to confirm every FR/NFR delivered or deferred (`CLAUDE.md`); Decision #36 specifically forbids treating a deferred live check as silently terminal, so FR24–FR26/FR33 are moved only on dated live evidence and FR31/FR32's gap is routed to the user rather than assumed away. REV-120 and REV-066/REV-052 were open reviewer findings within pm's own document; fixed as part of the same closure pass rather than left open into the tag. |
| 2026-07-31 | **Closure decision recorded — FR31/FR32 deferred by explicit user choice; `v0.1.0` tagged in that state; INC-8–12 fix-round merge-to-`main` timeline recorded.** §11's "Deferred, pending live execution" section for FR31/FR32 was left as an open recommendation (2026-07-30) with two options for the user; the user has now chosen **option 2** — defer FR31/FR32 and tag `v0.1.0` now, rather than hold the tag for a live portal-browser check (option 1, pm's recommendation, retained in §11 as the record that it was offered and declined). §11 rewritten to state the final classification unambiguously: **FR31, FR32 = Deferred, pending live execution, by the user's explicit choice on 2026-07-31**, `v0.1.0` tagged with them in that state. Sharpened exactly what is/isn't verified: INC-7 **Step 0 passed** (the `admin_read_kill_switch` policy and the `is_admin()`-gated `set_kill_switch()` RPC are confirmed live in production); what remains unexecuted is **AC2/AC3 specifically** — the portal's own authenticated-browser RPC round-trip and dispatch suppression proven from a portal-initiated pause. The service-role path was exercised live (INC-3 AC3, `docs/handoff.md`), but under `actor='postgres'`, so it is the portal's own call path that is untested, not the kill-switch mechanism as a whole. Added five concrete steps to close FR31/FR32 later (sign in as admin, toggle pause, confirm `kill_switch_audit.actor` is the authenticated admin not `postgres`, confirm `run_heartbeat.last_run_at` does not advance past the pause, resume and confirm it does), so this is not an open-ended deferral. Also added a new §11 "Deployment status" note (informational, no FR/NFR status change): the INC-8–12 fix round has been merged to `main` (fast-forward `ef254d1..bf42ad6`, 2026-07-31); before that merge, production ran pre-fix code, since `dispatch_github_workflow` dispatches with `ref: 'main'` — so INC-8–12 take effect on the next scheduled dispatch, not before this closure record. The four SQL files tied to that fix round (`sql/holdings_currency_derivation.sql`, `sql/tunables_validate_trigger.sql`, `sql/admin_portal_tunables_alerts_enabled_description_fix.sql`, `sql/kill_switch_abort_log.sql`) were already applied to production ahead of the code and independently verified harmless in that pairing — unaffected by this note. No FR/NFR IDs or text changed outside §11; no changes to §5–§10. Archived the oldest live entry (2026-07-27, FR30 GitHub-Variables-to-Supabase-table reversal) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | User's explicit 2026-07-31 closure decision, per CLAUDE.md's rule that trade-offs go to the user, never decided silently by pm; §11 exists specifically to be the record of what was promised and what was actually decided, so the outcome (not just the recommendation) had to be made unambiguous before tagging. |
| 2026-07-31 | **Change request received (not yet actionable) — Admin Portal UI/UX modernization (responsive + modern visual design).** Arjun: "For admin portal, UI is not screen size responsive. And looks very basic. Improve UI to be more modern. Limit this change request to UI/UX enhancement only. Present mockups and wireframe prior to proceeding with implementation." Impact assessed against the existing admin portal (FR27–FR32, §5.11; NFR5/NFR6; `design/admin-portal.md`, `design/frontend.md`) — all screens are IMPLEMENTED and reviewer-cleared (INC-5/6/7/10). This CR is explicitly UI/UX-only: no change to any FR27–FR32 functional behavior, the authorization model, or the data model. **No FR/NFR ID is added yet.** Per the no-inference rule, the concrete scope (which screens, target breakpoints/devices, what "modern" means in testable terms, priority order, accessibility bar, whether the login screen is included) is undecided and must not be guessed — pm's clarifying questions are routed to the user before any requirement text is drafted. Once answered, this is expected to land as a new NFR (a testable UI-quality bar layered over the already-FR-defined screens) rather than a new functional FR, since no new capability is being requested. Logged as **Decision #39** (§8). Per CLAUDE.md's change-request process, tech-lead's `design.md`/`design/admin-portal.md` are not touched until requirements are finalized and approved (GATE 2); designer's `docs/ux-spec.md` (mockups/wireframes) must be produced and approved by the user before dev implements anything — the explicit gate Arjun asked for, and it must not be skipped. Archived the oldest live entry (2026-07-28, `AI_PROVIDER` §10 baseline doc-sync) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | User's 2026-07-31 change request, routed through CLAUDE.md's change-request step 1 (pm impact assessment); no-inference rule applies in full — scope, breakpoints, and the definition of "modern" are all undecided and must not be guessed. |
| 2026-07-31 | **Change-request resolution — Admin Portal UI/UX modernization: Decision #39 resolved, added NFR8.** Arjun answered pm's clarifying questions in full: all five admin-portal screens (login, watchlist/holdings CRUD, tunables editor, track-record view, kill-switch toggle) are in scope; target range is phone + tablet + desktop (exact breakpoints left to tech-lead); "modern" is designer-defined — the designer researches modern admin/SaaS UI patterns and proposes 2–3 mockup directions in `docs/ux-spec.md` for Arjun to choose from, no fixed reference/brand constraint given; accessibility is best-effort only, no formal WCAG target (single-user internal tool). Decision #39 (§8) updated from open to **RESOLVED** with these answers. Added **NFR8 — Admin portal UI/UX quality (responsive & modern)** (§6): responsive across phone/tablet/desktop with no horizontal scroll/clipped content and all controls operable at each device class; delivered UI must match a designer-proposed, user-approved mockup direction (`docs/ux-spec.md`; mockups-before-implementation is a non-skippable gate); accessibility best-effort only, no formal target; explicitly no change to FR27–FR32 functional behavior, the `is_admin()`/RLS model, or any schema, and qa must confirm zero functional regression alongside the visual/responsive work. No other FR/NFR text changed; no IDs renumbered besides the new NFR8. Archived the oldest live entry (2026-07-28, Reviewer Pass 11 findings routed to pm) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. **Ready for GATE 2 (user approval of this requirements update)**; on approval, hands off in parallel to tech-lead (design.md UI increment plan) and designer (`docs/ux-spec.md` mockup directions), per CLAUDE.md's change-request process step 2. | User's 2026-07-31 answers to pm's clarifying questions, closing every open item from Decision #39 with no ambiguity remaining; framed as an NFR (not a new FR) since no new functional capability is being added — a presentation-layer quality bar over the already-FR-defined FR27–FR32 screens. |
| 2026-07-31 | **REV-142 fix — §11's FR31/FR32 closure checklist gains a sixth, FR31-specific step.** Reviewer's Pass 33 audit found that both the five-step "Steps to close FR31/FR32" checklist and Decision #36's own live-check list only ever verify FR32 (kill-switch: sign in, toggle, check `kill_switch_audit.actor`, check `run_heartbeat` pauses/resumes) — none checks FR31 (the track-record view) itself, even though FR31 is deferred in the same bundle purely because it shipped in the same increment (INC-7). This was live: BUG-009 (`call_log`'s RLS silently anon-only in production, leaving the track-record view empty for every signed-in admin) was only caught because qa went beyond the letter of the checklist. Added **step 6** to §11's closure checklist: confirm the track-record view (`/track-record`) renders non-empty, real `call_log` data for the same signed-in admin — the one criterion that actually observes FR31, distinct from steps 1-5's FR32 mechanics. Also added a corresponding bullet to the "what is and isn't verified" list noting this gap existed. Updated "on all five passing" to "on all six passing." No FR/NFR IDs added or renumbered; FR31/FR32's Deferred status (Decision #36, user's 2026-07-31 closure choice) is unchanged — this only sharpens what closing the deferral requires. Archived the oldest live entry (2026-07-27, FR30 last-known-good-cache refinement) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | Reviewer finding REV-142 (`docs/review-log.md` Pass 33): a documented closure checklist that can fully pass without ever observing the FR it's meant to verify is a gap in the requirement, not just an implementation bug — BUG-009 already proved the cost of that gap once. Routed to pm per CLAUDE.md's reviewer-finding-routing rule; closing a reviewer-routed gap, not a user-driven scope change, so no re-run of the full change-request approval flow was needed. |
| 2026-08-01 | **Change-request resolution — Admin Portal redesign (nav, branding, Tickers merge, clickable cards): Decision #40 resolved.** Added **FR36** (§5.11: watchlist+holdings screens merged into one "Tickers" screen, one-card-per-row layout, card content — status/shares/price-if-held, latest verdict+timestamp+**confidence level**, rationale — click-to-open combined edit/delete modal), **FR37** (mandatory shares+price-per-share capture on a watch-only→held status change inside the FR36 modal; held→watch-only deletes the `holdings` row behind a confirmation prompt — pm's recommended default, to keep status/holdings-existence a single enforced invariant), and **FR38** (rename "Admin Portal"→"Sentinel Portal" in the `<title>`/header only — pm's recommended default, no doc-reference renaming). Amended **FR28/FR29** with forward-references noting their CRUD capability is unchanged but now presented via FR36/gated via FR37 rather than standalone screens. Amended **NFR8** (§6): "five screens" corrected to "four" (FR36's merge), added a **navigation-mechanism bullet** — the desktop nav rendering as a vertically stacked list instead of a horizontal row is confirmed a **defect** against the already-approved INC-13/14 design, routed to tech-lead to root-cause/fix (not new scope), separate from a new, narrow carve-out permitting an intentionally horizontally-scrollable nav container at a tech-lead-determined mid-width tier as an alternative to the burger control (the only exception to NFR8's "no horizontal scrolling" bar, scoped to the nav element only) — and updated the functional-regression bullet to cover FR36/FR37's new behavior. **Confirmed during impact assessment: "confidence level" is already-tracked data** (`ai_judge.py`'s `VALID_CONFIDENCE`, stored in `call_log.data_snapshot.confidence` per FR15, already shown on the dashboard/detail page) — FR36 is a display-only extension, not new AI-output/schema scope. Arjun's answers closing every open item: data model is a UI-only merge (no schema change); Holdings page is replaced entirely, folded into the Tickers modal (nav 4→3 items); "price per share" is the existing `cost_basis` field, relabeled only; the nav "redesign" premise was a misdiagnosis — it's a real rendering defect, now routed to tech-lead separately from the new burger/scroll-bar design intent. pm's recommended defaults (branding UI-strings-only; delete-with-confirmation over keep-and-hide; combined single edit form; one-card-per-row on the new Tickers screen only, all three breakpoints; track-record's own grid unaffected; sequence after INC-14 closes) are recorded explicitly in Decision #40 as overridable, not silently assumed. **Routed to tech-lead next:** nav defect root-cause/fix, Tickers-merge screen/modal architecture, and card/modal visual redesign coordinated with designer's mockup update (Direction G predates FR36–FR38). Archived the oldest live entry (2026-07-28, `AI_TEMPERATURE` §10 baseline doc-sync) to `docs/archive/requirements-changelog-archive.md` to hold the 10-most-recent cap. | User's (Arjun's) 2026-08-01 change request, routed through CLAUDE.md's change-request process step 1 (pm impact assessment, no-inference rule); genuine functional scope (page merge, new mandatory-workflow trigger, a real UI defect) separated from pure presentation scope, each captured at the right level (FR vs. NFR) rather than folded together; recommended defaults stated explicitly per the user's direction so they remain visible/overridable. |
