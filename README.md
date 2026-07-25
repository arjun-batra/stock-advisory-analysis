# Stock Advisory Agent

A single-user, personal stock advisory tool that applies the same disciplined judgment to a personal
watchlist on a regular cadence — so a real, actionable signal on a held or watched stock isn't missed
just because nobody checked that day.

## The problem it solves

Manual stock-checking is inconsistent and emotion-driven: you look when you remember to, apply
different judgment each time, and miss signals by simply not looking. This system does the checking for
you, the same way every time, and notifies you only when something actually changes.

## What it does

- **Watches a personal list** of 5–15 tickers per market across US, Canada (TSX), and India (NSE),
  including held positions (with shares + cost basis) and watch-only names.
- **Checks every ~30 minutes** during each market's trading hours and produces a Buy / Sell / Hold
  verdict with a one-line rationale, from AI judgment over price/volume, news, and fundamentals — no
  fixed buy/sell rules and no fixed investment style.
- **Alerts only on change.** Any verdict change pushes a notification immediately; no change is silent.
  No cooldown, no debounce, no periodic reminder.
- **Discovers new candidates** once a day across all three markets: a computational prefilter (movers,
  volume spikes, earnings proximity, 52-week-extreme proximity, plus quality gates) shortlists names for
  the AI; only Buy verdicts surface as a push.
- **Delivers via push** (ntfy), with US/TSX and NSE on separate topics so they can be filtered
  independently; each push links to a detail page with the full reasoning.
- **Shows a read-only dashboard** (GitHub Pages) of all tickers grouped by market, with a near-live
  price snapshot and the last-run verdict.
- **Logs every check** (including no-change and skipped cycles) so the track record is auditable.
- **Watches itself** with an active dead-man monitor that alerts when a scheduled run is missed, fails,
  or degrades — silence from the monitor means healthy.

This is a personal, informational tool. It does not place trades, does not connect to any brokerage,
covers only stocks/ETFs, is single-user, and is not licensed/registered financial advice.

## Architecture at a glance

- **Supabase (Postgres)** is the control plane: it persists state, schedules both workflows (pg_cron),
  and runs the health monitor.
- **GitHub Actions** runs the fetch → AI → alert work; the runtime market gate (not the schedule)
  decides whether work actually happens.
- **Gemini Flash** (Google's paid tier; cost is held by keeping call volume low — one batched call per
  run per track — rather than a free-tier daily cap) generates verdicts, failing safe to Hold on any
  error.
- **Yahoo Finance** (unofficial API) supplies price/volume/fundamentals for all three markets.

## How to run

> **Note:** This section is a best-effort reconstruction from the solution design
> (`requirements_docs/SD.md`), the config surface (`scripts/config.py`), and `docs/runbook.md` (the
> dedicated deploy runbook, owned by release, covering general deploy procedure — not to be confused
> with `docs/handoff.md`, which covers only the shadow-tracks-removal increment). Steps confirmed
> against `docs/runbook.md` are stated directly below; any remaining *(inferred)* marker is not covered
> by the runbook and should still be verified before being relied on.

The system is not a locally-run app; it runs on a schedule in the cloud.

1. **Control plane — Supabase.** A Supabase (Postgres) project holds the schema (watchlist, holdings,
   `call_log`, views) and drives scheduling and health monitoring via pg_cron.
   Apply the SQL migrations in `sql/` in the exact order documented in `docs/runbook.md` §2.3 —
   `scheduler_pgcron.sql` → `phase5_monitoring.sql` → `dashboard_latest_call_view.sql` →
   `drop_shadow_tables_migration.sql` — to provision the schema and objects.
2. **Compute — GitHub Actions.** The workflows in `.github/workflows/` (e.g.
   `hourly-watchlist.yml`) do the actual fetch/AI/alert work. They are dispatched by Supabase pg_cron
   and can also be triggered manually via **workflow_dispatch** (use `FORCE_RUN=true` to run outside
   market hours for testing/backfill).
3. **Dependencies.** Python dependencies are pinned in `requirements.txt`; the workflow installs them on
   each run (`pip install -r requirements.txt`) using Python 3.12, per `python-version: "3.12"` in the
   three cron-triggered workflows (`hourly-watchlist.yml`, `daily-discovery.yml`,
   `publish-prices.yml`; the `audit.yml` CI workflow uses `3.x`). This is confirmed directly from the
   workflow files, not from `docs/runbook.md`, which does not state a Python version.
4. **Secrets & configuration.** Set as GitHub Actions encrypted **secrets** and **Variables**. Required
   secrets: `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (the code fails fast if any are
   missing), plus `NTFY_TOPIC` / `NSE_NTFY_TOPIC` and `DETAIL_PAGE_BASE` for delivery. Behavior toggles
   include `ALERTS_ENABLED` (flip to `true` to send real pushes). The full tunable surface (models,
   timeouts, retries, discovery thresholds, market hours) is documented in the Configuration section of
   `docs/requirements.md` and defined in `scripts/config.py`.
5. **Dashboard.** The read-only dashboard is served from GitHub Pages (the `pages/` output, with the
   price snapshot published to `pages/prices.json` on the market cadence) behind a client-side password
   gate.

## Documentation

- `docs/idea-brief.md` — the as-built product brief (problem, users, scope, risks).
- `docs/requirements.md` — the current FR/NFR requirements, Decisions Log, and Configuration.
- `requirements_docs/` — the original, detailed source-of-truth docs (requirements v5, solution design
  v20, UI handoff v4, history, and prior reviews), retained as the historical record.
