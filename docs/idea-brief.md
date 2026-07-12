# Stock Advisory Agent — Idea Brief (as-built)

**Nature of this document:** This is a *retroactive* brief for a system that is already live
(Phases 0–7 in production for weeks). It was written during the multi-agent-template adoption pass by
porting the existing, current source-of-truth docs in `requirements_docs/` — chiefly
`stock-advisory-agent-requirements.md` (v5) §1–§3 and `SD.md` (v20) §0–§2. It describes what the
system *is*, not a forward-looking pitch. The authoritative requirement/design detail lives in
`docs/requirements.md` (ported) and `requirements_docs/` (historical record, left untouched).

---

## Problem statement

Manual stock-checking is inconsistent and emotion-driven. A person watching a handful of positions
checks them irregularly, applies different judgment each time depending on mood and attention, and
misses signals simply because nobody looked that day. The system exists to apply the *same disciplined
judgment every time*, on a personal watchlist, on a regular cadence, without requiring daily manual
review — and to push a notification only when something actually changes.

## Target user

A single user (Arjun). This is a solo, personal advisory tool — no external users, no multi-user or
shared/team access, no handoff to a contractor. The user is technical enough to maintain a watchlist,
enter holdings/cost-basis data by hand, and read a track-record log. The doc exists as a solo build
reference, not a spec for a third party.

## What it does (as built)

- Maintains a watchlist of 5–15 tickers per market across US, Canada (TSX), and India (NSE), each
  ticker identified by market.
- Holds user-entered position data (shares + cost basis) for held names; watch-only names carry no
  position.
- Runs AI-driven checks every ~30 minutes during each market's trading hours, producing a Buy/Sell/Hold
  verdict plus a one-line rationale per ticker. Verdicts come from AI judgment over price/volume, news,
  and fundamentals — no fixed buy/sell rules, no fixed investment style/horizon.
- Alerts on a single rule: any verdict *change* pushes immediately; no change is silent. No cooldown,
  no debounce, no standing-verdict reminder.
- Runs a separate daily candidate-discovery scan across all three markets: a computational prefilter
  (movers, volume spikes, earnings proximity, 52-week-extreme proximity, plus quality gates) shortlists
  candidates for the AI; only Buy verdicts from discovery push, Hold/Sell are logged silently.
- Delivers pushes via ntfy (US/TSX on one topic, NSE on a separate topic), each linking to a detail
  page with the full reasoning.
- Serves a read-only GitHub Pages dashboard (password-gated client-side) showing all tickers grouped by
  market with a near-live server-published price snapshot and the last-run verdict.
- Logs every check (including no-change and skipped cycles) so the success criterion is auditable.
- Runs an active dead-man monitor: it alerts when a scheduled run is missed, fails, or degrades —
  silence from the monitor means healthy.

## Architecture at a glance (as built)

- **Control plane:** Supabase (Postgres) — state persistence, the scheduler (pg_cron dispatch), and the
  health monitor (pg_cron). Deliberately concentrated; this makes Supabase a single point of failure for
  the trigger+watchdog path (accepted risk).
- **Compute:** GitHub Actions workflows do the fetch/AI/alert work; the runtime market gate (not the
  schedule) is the authority on whether work happens.
- **AI:** Gemini Flash, free tier, one batched call per run; fails safe to Hold on any parse/API error.
- **Data:** Yahoo Finance unofficial API for price/volume/fundamentals across all three markets.

## v1 scope

### In scope
- Single-user personal advisory tool (Arjun only).
- Watchlist across US, TSX, and NSE; user-maintained holdings (shares + cost basis).
- AI candidate discovery with computational prefilter across all three markets.
- Regular intraday checks during each market's hours; Buy/Sell/Hold + one-line rationale.
- Push delivery, US/TSX and NSE on separate ntfy topics.
- AI judgment grounded in price/volume, news, fundamentals — no fixed rules or style.
- Read-only GitHub Pages dashboard with near-live snapshot price and last-run verdict.
- Full track-record logging (every check, including no-change and skips).
- Active dead-man reliability monitor.

### Out of scope (hard boundaries, not soft preferences)
- Trade execution or order placement of any kind.
- Brokerage account integration or read access — holdings are entered manually.
- Options, crypto, derivatives, or any asset class beyond stocks/ETFs.
- Multi-user or shared/team access.
- Licensed/registered financial advice — this is a personal informational tool.

## Constraints
- **Budget:** $0–15/month. Drives free-tier data APIs, free push (ntfy), and one batched Gemini call
  per run to stay under the free-tier daily request cap.
- **Data lag:** ~30-minute cadence means up to ~30 minutes of lag is acceptable; the system is
  explicitly not suited to intraday/fast-moving trade timing.
- **Static dashboard host:** GitHub Pages has no server-side auth, so dashboard access control can only
  be a client-side gate (accepted given read-only, RLS-scoped, informational data).
- **Browser CORS:** Yahoo's price API is browser-CORS-blocked, so the dashboard reads a server-published
  `prices.json` snapshot same-origin rather than fetching live client-side.

## Success criteria
Within 3 months, at least one verdict the system surfaced is later validated as correct and would not
have been caught by manual checking. This is only auditable because every check is logged.

## Open risks (accepted, documented — from SD.md §2)
1. Gemini free tier may train on submitted prompts (which include watchlist, holdings, cost basis).
   Accepted for the budget; swap to a paid/isolated model is a small change.
2. Yahoo Finance API is unofficial — no SLA, TSX/NSE fundamentals may be incomplete.
3. Free-tier quotas move; observed fallbacks were client-side timeout / 503, not quota (attribution
   corrected). The real cause is logged per call.
4. No spam control — non-deterministic verdicts surface directly as alerts; a choppy day can push on
   every flip. Accepted cost of the single-rule design.
5. NYSE/TSX/NSE holiday calendars are not consulted; a closed market falls through to skip-with-log.
6. Supabase is a single point of failure for trigger + watchdog; an out-of-band uptime ping is the noted
   (unbuilt) mitigation.
7. Dashboard auth is client-side obfuscation, not real security; acceptable only for read-only,
   informational, RLS-scoped data.
8. Yahoo price API is browser-CORS-blocked; dashboard uses a server-published snapshot (accepted
   freshness tradeoff).

## Experimental addition (NOT core v1 scope): shadow wallet pilot
A parallel, **non-production** AI verdict track for US/CA (TSX) watchlist tickers only (no NSE). It
reuses production's already-fetched market-data snapshot and model-call machinery but swaps in a
position-aware prompt variant that tracks its own simulated buy/sell position per ticker (a
"wallet-walk" derived purely from its own history) and requires the model to cite a reversal-since-entry
when selling a simulated holding. Purpose: A/B test whether position-awareness changes verdict
quality/behavior versus production's watch-only-style prompt. It writes only to its own isolated table,
never alerts, and cannot affect production if it fails. It is gated by a kill switch that defaults ON
(fail-open — an accepted risk). It is documented as an experimental track in `docs/requirements.md`
(FR24–FR30 / NFR5), explicitly outside core v1 scope, and currently lacks a committed, reproducible
evaluation method (a flagged gap that must be closed before the pilot could graduate).
