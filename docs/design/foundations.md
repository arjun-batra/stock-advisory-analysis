# Foundations — purpose, architecture choices, accepted risks

Part of `docs/design.md`'s module split (2026-07-25, REV-024). See `docs/design.md` for the index, module
map, §0 load-bearing decisions, and the requirement coverage map — read that first for orientation.
Section numbers below (§1–§3) are unchanged from the pre-split monolithic `docs/design.md`.

---

## 1. Purpose & confirmed architecture choices

The requirements doc closes the product questions; this doc closes the engineering ones — what runs
where, what persists, and the contracts a dev/QA team builds and tests against. Three architecture
decisions are locked:

| Decision | Choice |
|---|---|
| Candidate discovery method | Prefiltered live-screener universe (movers/volume/earnings/52w) → AI judges the shortlist (FR4) |
| AI model | Gemini Flash on Google's **paid tier** (model names are configurable repo Variables, `components.md` §4.4; standardized on the `gemini-2.5-flash` family across all tracks); cost held by low call volume within NFR1's $0–15/mo cap |
| State / control plane | Supabase (Postgres) — state persistence **plus** the scheduler and the watchdog (`components.md` §4.1, §4.8) |

Supabase is the **control plane**, not just the database: it persists state, triggers both workflows via
`pg_cron`, and runs the health monitor. That concentration is deliberate (one reliable mechanism beat
GitHub's flaky scheduler) but makes Supabase a single point of failure for the trigger-and-watchdog path
(§2 item 6, below).

---

## 2. Accepted risks (documented, not hidden)

Carried from `SD.md §2` plus the pilot additions. These are recorded so they are not silently
"discovered" and reversed later.

1. **Gemini may train on submitted prompts** (watchlist, holdings, cost basis flow through it). Gemini now
   runs on Google's **paid tier** system-wide, but data-handling posture is still governed by the account/
   API terms in effect, not assumed private. Accepted for the $0–15/mo budget (NFR1); tightening to an
   isolated/no-train model tier remains a small, isolated config change.
2. **Yahoo Finance API is unofficial** — no SLA, TSX/NSE fundamentals may be incomplete. Day-one
   smoke test per market is mandatory (done, `non-functional-ops.md` §9).
3. **The observed fallbacks were never quota/rate-limiting** — they were client-side timeout / 503,
   corrected (this held on free tier and holds on paid tier alike). Real cause logged in `fallback_from`
   (`docs/design.md` §0, load-bearing #3).
4. **No spam control** — non-deterministic verdicts surface directly as alerts; a choppy day pushes on
   every flip. Accepted cost of the single-rule design (FR8, `docs/design.md` §0 load-bearing #1).
5. **Holiday calendars are not consulted** (US/TSX/NSE) — a closed market falls through skip-with-log
   (FR17, `non-functional-ops.md` §7.5).
6. **Supabase is a single point of failure for trigger + watchdog** — an out-of-band uptime ping is the
   noted (unbuilt) mitigation (NFR2).
7. **Dashboard auth is client-side obfuscation, not real security** — acceptable only for read-only,
   informational, RLS-scoped data (FR19, Decision #11).
8. **Yahoo price API is browser-CORS-blocked** — dashboard reads a server-published `prices.json`
   snapshot same-origin (FR21, Decision #18, `frontend.md` §11).
9. **RETIRED (2026-07-16).** Formerly: "Shadow pilot kill switch defaults fail-open." Both shadow tracks
   and their kill switches are removed; see `docs/design.md`'s "Retired: shadow-pilot tracks" note. The
   risk no longer exists.

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
browser-CORS-blocked, `frontend.md` §11).

Entry points are thin orchestrators (`run_hourly.py`, `run_discovery.py`, `publish_prices.py`) — no
business logic; all logic lives in importable, testable modules (`non-functional-ops.md` §8). External
dependencies (Supabase client, Gemini client, yfinance, clock) are reached through module functions so
they can be substituted in tests.
