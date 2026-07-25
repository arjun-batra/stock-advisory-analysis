# Stock Advisory Agent — Deployment Runbook

**Owner:** release. **Status:** reverse-documented for a live, production system (backfill of REV-027). Everything in this document describes what is already deployed and running as of 2026-07-25; it is not forward planning.

---

## 1. Architecture Summary

The system deploys across three layers:

- **Compute (GitHub Actions):** Four workflows orchestrate the work — hourly intraday watchlist checks (`hourly-watchlist.yml`), daily candidate discovery (`daily-discovery.yml`), dashboard price snapshot publishing (`publish-prices.yml`), and repository CI checks (`audit.yml`). Workflows are triggered via Supabase pg_cron (not GitHub's native schedule) to avoid the reliability issues documented in `docs/design/components.md` §4.1.

- **Control plane (Supabase Postgres):** Centralizes state persistence (watchlist, holdings, verdicts, call logs), the scheduler (pg_cron dispatch to GitHub Actions via `workflow_dispatch` API), and the active health monitor (dead-man watch on workflow staleness — `docs/design/components.md` §4.8, `docs/requirements.md` NFR2). The concentration is deliberate and accepted as a single point of failure; see §2 item 6 of `docs/idea-brief.md` (Open risks).

- **Frontend (GitHub Pages + ntfy):** Dashboard served at a GitHub Pages URL (password-gated client-side per `docs/design/frontend.md` §10), with push notifications to ntfy.sh (US/TSX on one topic, NSE on a separate topic for independent filtering). Dashboard prices are published to `pages/prices.json` on the market cadence to work around browser CORS restrictions on Yahoo Finance APIs; see `docs/requirements.md` Decision #18.

Full architecture and design rationale: `docs/design.md`.

---

## 2. Deploy / Fresh Clone Setup

### Prerequisites

Before any workflows run, provision the Supabase project and GitHub Actions secrets and variables.

#### 2.1 GitHub Actions Secrets

In the repository's **Settings > Secrets and variables > Actions > Secrets tab**, create these **encrypted secrets** (values never committed, not accessible in logs):

| Secret name | Purpose | Example / notes |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key (paid-tier) | Obtained from console.cloud.google.com; production uses `gemini-2.5-flash` family on Google's paid tier, not free tier (§4.4, `docs/design/components.md`) |
| `SUPABASE_URL` | Supabase project URL | Format: `https://<project-id>.supabase.co` |
| `SUPABASE_SECRET_KEY` | Supabase service-role key (new-style `sb_secret_...`) | Bypasses RLS; server-only secret, never exposed client-side or in public keys |
| `NTFY_TOPIC` | ntfy.sh push topic for US/TSX alerts | URI of the ntfy topic, e.g., `https://ntfy.sh/my-stock-topic` |
| `NSE_NTFY_TOPIC` | ntfy.sh push topic for NSE alerts (optional) | If unset, NSE alerts fall back to `NTFY_TOPIC`; omitting this allows both regions on one topic for simplicity during pilot |
| `DETAIL_PAGE_BASE` | Base URL for the detail-page tap-through link in alerts | E.g., `https://arjun-batra.github.io/stock-advisory-analysis/detail.html` |

#### 2.2 GitHub Actions Variables (Optional, User-Tunable)

In **Settings > Secrets and variables > Actions > Variables tab**, create these **plain-text variables** (not secret — model names are not sensitive and change frequently):

| Variable name | Default (if unset) | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | Primary watchlist AI model |
| `GEMINI_MODEL_BACKUP` | `gemini-2.5-flash-lite` | Fallback model for watchlist; leave empty to disable fallback |
| `NSE_GEMINI_MODEL` | (inherits `GEMINI_MODEL`) | NSE watchlist model (separate quota bucket); empty or unset → uses primary model |
| `NSE_GEMINI_MODEL_BACKUP` | (inherits `GEMINI_MODEL_BACKUP`) | NSE watchlist fallback model; empty or unset → no NSE fallback |
| `DISCOVERY_GEMINI_MODEL` | `gemini-2.5-flash` | Discovery prefilter model (separate quota from watchlist) |
| `DISCOVERY_GEMINI_MODEL_BACKUP` | `gemini-2.5-flash-lite` | Discovery fallback model |
| `GEMINI_MAX_RETRIES` | `3` | Retries after initial Gemini attempt (§4.4, `docs/design/components.md`) |
| `GEMINI_RETRY_BASE_MS` | `10000` | Exponential backoff base (ms) with full jitter; empty → uses default |
| `GEMINI_TIMEOUT_MS` | `180000` | Per-request timeout (ms); unset → defaults to 180s (corrected from prior 20s timeout; see `docs/design/components.md` §4.4) |

All other tunables (discovery thresholds, market hours, pacing, etc.) are documented in `scripts/config.py` and read from environment variables set by the workflows. Change them in `scripts/config.py` or as workflow env vars — not hardcoded anywhere else.

#### 2.3 Supabase Project Setup

Create a Supabase project if one doesn't exist. Then:

1. **Enable extensions** (in Supabase dashboard, SQL Editor or via migration):
   - `pg_cron` (scheduler)
   - `pg_net` (HTTP from SQL to GitHub API)

2. **Create Vault secrets** (in Supabase dashboard, Vault section under Project Settings > Vault):
   - Secret name: `github_workflow_pat` → value: GitHub Personal Access Token with `actions:write` scope on the target repository
   - Secret name: `ntfy_topic` → value: the ntfy.sh topic URI (e.g., `https://ntfy.sh/my-stock-topic`) — used by the health monitor's `send_ntfy()` function

3. **Apply SQL migrations in this exact order** (via Supabase SQL Editor or via the Supabase CLI `supabase db push`):
   - `sql/scheduler_pgcron.sql` (creates `dispatch_github_workflow()` function and base cron jobs for watchlist/discovery/prices)
   - `sql/phase5_monitoring.sql` (creates health-monitor function `check_pipeline_health()`, dispatch gates for market hours, monitor alert state table, and schedules the health check itself)
   - `sql/dashboard_latest_call_view.sql` (creates the `latest_call_per_ticker` view, used by the dashboard and detail page for fast read-only queries)
   - `sql/drop_shadow_tables_migration.sql` (removes shadow-pilot tables if migrating from an older version; safe to run even if tables don't exist — `IF EXISTS` is used)

These migrations set up the entire control plane. They will create the `run_heartbeat` and `monitor_alerts` tables automatically, and the cron jobs will start firing immediately on the schedules defined below.

### Workflows and Their Schedules

After SQL migrations are applied, the four workflows are triggered as follows:

| Workflow | Schedule | Via | Purpose |
|---|---|---|---|
| `hourly-watchlist.yml` | Every 30 min, 13:00–21:59 UTC weekdays | `cron.schedule('watchlist-dispatch', '*/30 13-21 * * 1-5', ...)` in `scheduler_pgcron.sql` → `dispatch_watchlist_if_open()` gate in `phase5_monitoring.sql` → `dispatch_github_workflow('hourly-watchlist.yml')` | Intraday watchlist checks, run every ~30 min during market hours (gate trims to 09:30–16:05 ET / 09:15–15:35 IST, i.e., real session + buffer for jitter) |
| `daily-discovery.yml` | Once daily, 22:00 UTC Mon–Fri | `cron.schedule('discovery-dispatch', '0 22 * * 1-5', ...)` in `scheduler_pgcron.sql` → direct dispatch | Post-US-close candidate discovery scan; also fires NSE discovery at 10:00 UTC (separate cron: `discovery-dispatch-nse`) with `region=in` input |
| `publish-prices.yml` | Every 30 min, 03:00–10:59 and 13:00–21:59 UTC weekdays (market cadence) | `cron.schedule('publish-prices', '*/30 3-10,13-21 * * 1-5', ...)` in `scheduler_pgcron.sql` → direct dispatch | Fetches live prices via yfinance and commits `pages/prices.json` if prices changed (issue #18 CORS workaround; see `docs/design/components.md` §4.7 and `docs/requirements.md` Decision #18) |
| `audit.yml` | On every push and pull request (GitHub native) | GitHub's own trigger | Runs gitleaks, linting (ruff/eslint), and tests; defined in `.github/workflows/audit.yml`, not pg_cron-triggered |

No GitHub-native `schedule:` triggers are used in any workflow because GitHub's shared cron scheduler was silently dropping ticks (issue #4, `docs/design/components.md` §4.1). The runtime market gate (Python `is_market_open()` in `scripts/config.py` for the watchlist, SQL gates in Supabase) is the authority on whether work happens — the schedule fires loosely, and the gate trims it.

---

## 3. Rollback Procedure

Since the system is entirely code-as-config (GitHub Actions workflows + SQL in Supabase, no traditional deploy artifacts or container images), "rollback" means reverting the problematic code change and re-running the affected workflow.

### Standard Rollback (Code Change)

1. **Identify the bad commit** on the `main` branch (the deployable branch).
2. **Revert the commit** via `git revert <commit-sha>` and push to `main` (creates a new commit that undoes the change).
3. **Re-run the affected workflow manually** via GitHub Actions UI (Settings > Actions > select the workflow > "Run workflow" button), or wait for the next scheduled cron tick, or manually dispatch via Supabase SQL: `SELECT public.dispatch_github_workflow('hourly-watchlist.yml');`.

### Emergency Shutdown (Alert Suppression)

If a workflow is misbehaving and sending false alerts, disable live alerts without reverting code:

1. **Disable alerts via workflow input:**
   - Manually dispatch the workflow with `alerts_enabled=false` (in GitHub Actions UI, "Run workflow" dialog).
   - The workflow will run but use `DryRunNotifier`, logging the composed push instead of sending it.
   - This is a one-off dry run, not persistent; live alerts resume on the next scheduled cron dispatch.

2. **Disable workflow entirely (if necessary):**
   - Comment out or delete the corresponding cron job in Supabase SQL (e.g., `SELECT cron.unschedule('watchlist-dispatch');`).
   - This stops the schedule from firing; manual dispatch still works.
   - Remember to re-enable after the fix: `SELECT cron.schedule('watchlist-dispatch', '*/30 13-21 * * 1-5', 'SELECT public.dispatch_watchlist_if_open();');`.

3. **Temporarily block Supabase dispatch function (last resort):**
   - Rename or drop `public.dispatch_github_workflow()` in Supabase; all pg_cron jobs will silently fail to dispatch (pg_cron logs the failure but doesn't alert).
   - Restore the function when the issue is fixed.
   - This is a blunt instrument; prefer the workflow-input or cron-unschedule approach.

### Rollback of SQL Migrations

If a migration caused a data problem:

1. **Supabase migrations cannot be rolled back easily** — the platform's migration system doesn't track reversions the way some frameworks do.
2. **Instead:**
   - Write a corrective SQL script and apply it manually in Supabase SQL Editor.
   - Document the corrective step in a new comment in the migration file or in `docs/handoff.md`.
   - Ensure the corrective script is idempotent (e.g., `DROP TABLE IF EXISTS`, `CREATE OR REPLACE FUNCTION`, etc.).

**No data rollback strategy is currently documented.** If a workflow or SQL change corrupts the call log or verdict state, the only recourse is to truncate/repair the affected table and backfill from GitHub logs or manual inspection. This is an accepted limitation for a single-user, monitoring-only system; see §2 item 6 of `docs/idea-brief.md` (single point of failure).

---

## 4. Monitoring and On-Call

The system includes an **active dead-man monitor** to alert when workflows are stalled, missed, or degraded. Silence from the monitor means healthy.

### Monitor Overview

- **What it is:** A pg_cron job (`check_pipeline_health()` in `sql/phase5_monitoring.sql`) that runs at :20 and :50 past each hour, Mon–Fri.
- **What it checks:** Staleness and degradation of three pipelines (watchlist, discovery US/TSX, discovery NSE, publish-prices).
- **How it alerts:** Sends ntfy pushes to the same ntfy topic provisioned in Vault secret `ntfy_topic` when a pipeline enters or worsens a bad state.
- **Alert states:** `ok` (healthy), `stale` (no run for >70 min during session), `degraded` (latest run has status != ok).

### Alert Thresholds

| Pipeline | Watch window | Stale threshold | Degraded alert |
|---|---|---|---|
| **Watchlist (US/TSX)** | ET 10:15–16:00 (grace after 09:30 open, close included) | >70 min since last `run_heartbeat` | When latest heartbeat has `status` != 'ok' |
| **Watchlist (NSE)** | IST 10:00–15:30 (grace after 09:15 open, close included) | >70 min since last `run_heartbeat` | When latest heartbeat has `status` != 'ok' |
| **Discovery (US/TSX)** | After 23:00 UTC check (21:00 UTC post-close + margin) | No run since 21:00 UTC the same day | When `run_heartbeat.workflow_name='daily-discovery'` shows `status` != 'ok' |
| **Discovery (NSE)** | After 11:00 UTC check (10:00 UTC dispatch + margin) | No run since 09:30 UTC the same day (dispatch at 10:00 UTC IST = 04:30 UTC, execution window 09:30–11:00 UTC) | When `run_heartbeat.workflow_name='daily-discovery-in'` shows `status` != 'ok' |
| **Publish-prices** | ET 10:15–16:00 or IST 10:00–15:30 (either session open) | >70 min since last run | When `run_heartbeat.workflow_name='publish-prices'` shows `status` != 'ok' |

### How Workflows Report Status

Each workflow writes a `run_heartbeat` row at startup or completion (implementation detail: `run_heartbeat` table, columns `workflow_name`, `last_run_at`, `status`). Status is:
- `ok` — run completed without errors
- `partial` or `errors` — run completed but some tickers were skipped due to data fetch failures or AI errors (logged, not alerted)

On a run that never triggers, no heartbeat is written — the monitor detects this as staleness (no row, or row > 70 min old).

### What To Do When An Alert Fires

1. **Stale alert (e.g., "Watchlist stalled, no run since 1 hour ago"):**
   - Check if we're in a market session right now (is it weekday, and is the current time between market hours?).
   - If in session: the workflow should have fired. Likely causes:
     - GitHub Actions runner is down or overloaded (check GitHub status: status.github.com).
     - Supabase `pg_cron` job or `dispatch_github_workflow()` function is broken (check Supabase logs in the database).
     - GitHub PAT in Vault secret `github_workflow_pat` is expired or revoked (refresh it in Supabase dashboard).
     - The workflow file (`.github/workflows/hourly-watchlist.yml`, etc.) has a syntax error (check the last push; revert if necessary).
   - If NOT in session (weekend, before 09:30 ET, after 16:05 ET, etc.): the alert is a false positive — the monitor's session gate is off, so the workflow intentionally didn't run. This can happen if the monitor's session gate is looser than the workflow's own market gate, or if there's a dispatch-to-execution delay past the close. Acknowledge and dismiss; not a bug.

2. **Degraded alert (e.g., "Watchlist degraded, status = partial"):**
   - One or more tickers had data-fetch or AI errors but the workflow didn't crash.
   - Check the workflow's run log (GitHub Actions UI > select the run) for the error details.
   - Most common causes: Yahoo Finance rate-limiting (increases `YF_PACING_SECONDS` or `YF_BACKOFF_SECONDS`), Gemini API transient error (automatic retry in `ai_judge._generate` should handle most; if persistent, check Gemini quota/status), ticker delisted or renamed (remove from watchlist).
   - The monitor will re-alert every 12 hours until the status returns to `ok`.

3. **Recovery alert (e.g., "✅ Watchlist recovered"):**
   - Workflow is running cleanly again.
   - Confirms the stale/degraded condition has resolved.
   - No action needed.

### Manual Checks During Incident

If an alert doesn't fire but you suspect a workflow is stuck:

```sql
-- In Supabase SQL Editor:
SELECT * FROM public.run_heartbeat
WHERE workflow_name IN ('hourly-watchlist', 'daily-discovery', 'publish-prices')
ORDER BY last_run_at DESC;
```

If a heartbeat is missing or > 70 min old during market hours, manually dispatch:

```sql
SELECT public.dispatch_github_workflow('hourly-watchlist.yml');
```

Then wait ~2–5 min for the workflow to start (GitHub Actions runner queue is usually <1 min, but checkout + pip install adds ~1–2 min) and check the `run_heartbeat` table again.

---

## 5. Known Operational Risks and Limitations

### Risks Accepted at v1 Launch

Refer to `docs/idea-brief.md` §"Open risks (accepted, documented)" for the full list. Key ones:

1. **Gemini data privacy:** Free-tier models may train on submitted prompts (watchlist, holdings, cost basis). **Mitigation:** Swap to Gemini paid tier (already done; see `docs/requirements.md` §6, NFR1). Production uses paid-tier `gemini-2.5-flash`, not free tier.

2. **Yahoo Finance API is unofficial:** No SLA; TSX/NSE fundamentals may be incomplete or missing. **Mitigation:** Smoke test before relying on any market's data; fall-through skip-with-log when data is unavailable.

3. **Holiday calendars not consulted:** NYSE, TSX, NSE closures are not detected via a calendar; a closed market's tickers simply return no data and fall through to skip-with-log. No false alert. **Accepted:** the system is informational, not for automated trading.

4. **Supabase is a single point of failure:** Both the trigger path (pg_cron dispatch) and the watchdog (health monitor, also pg_cron) live in the same Supabase database. If Supabase is down, no workflows run and the monitor doesn't alert — exactly silent failure that the monitor is designed to catch, but the monitor itself is down too. **Noted mitigation (unbuilt):** out-of-band uptime ping (a third-party monitoring service, e.g., healthchecks.io, that pings a Supabase function or webhook at regular intervals and alerts if a ping is missed).

5. **Non-deterministic verdicts on choppy days:** A stock that oscillates between Buy/Hold/Sell will fire an alert on every flip, even if the pattern repeats the same way. No cooldown, no debounce — this is the single-rule design's accepted tradeoff. **Not a bug.**

6. **Dashboard auth is client-side obfuscation:** GitHub Pages has no server-side auth. The dashboard password gate is JavaScript-obfuscated, not cryptographically secure. **Accepted for:** read-only, informational, RLS-scoped data (detail page uses UUID-only URLs, no auth at all).

7. **Browser CORS blocks Yahoo price API:** Dashboard reads a server-published `pages/prices.json` snapshot (refreshed on the ~30-min market cadence) instead of fetching prices client-side. **Accepted freshness tradeoff:** the dashboard's "prices updated 5 minutes ago" indicator reflects the snapshot's real age; this is honest, not an illusion of liveness.

### Operational Gaps with No Current Mitigation

1. **No data backup:** Supabase provides automatic snapshots, but the system has no application-level backup or restore procedure. If the Supabase project is corrupted or deleted, all call logs and verdict history are lost. **Noted:** acceptable for a monitoring tool (no financial consequences), but would need a procedure for a trading system.

2. **No incident-response runbook:** This document covers deploy and monitoring; it does not include playbooks for specific failure modes (e.g., "Gemini API is unreachable for >4 hours," "Yahoo Finance API is down for a market session," "NSE/NYSE is closed for a holiday the calendar doesn't know about"). **Noted:** incidents are expected to be rare; add playbooks if patterns emerge.

3. **No capacity planning:** The system is single-user, so scaling is not a design concern. If expanded to multi-user, the Gemini paid-tier budget (NFR1, $0–15/month) would need re-evaluation based on call volume.

### What This System Is Not Suited For

- **Real-time intraday trading:** The ~30-min cadence and ~30-min data lag mean the system sees yesterday's news. Not suitable for day traders or scalping.
- **Automated order placement:** Verdicts are informational only; they are not connected to any brokerage API.
- **Multi-user or shared access:** Single-user personal tool only.
- **Regulatory/licensed advice:** Purely informational; no financial advisory registration.

---

## 6. Testing and Verification of a Fresh Deploy

### Smoke Test Checklist (After Fresh Setup)

1. **Supabase is running and accessible:**
   ```sql
   SELECT NOW();
   ```

2. **Extensions are enabled:**
   ```sql
   SELECT * FROM pg_extension WHERE extname IN ('pg_cron', 'pg_net');
   -- Should return two rows
   ```

3. **Vault secrets are readable by functions:**
   ```sql
   SELECT decrypted_secret FROM vault.decrypted_secrets 
   WHERE name = 'github_workflow_pat' LIMIT 1;
   -- Should return a non-null string
   ```

4. **Dispatch function exists and is callable:**
   ```sql
   SELECT public.dispatch_github_workflow('audit.yml');
   -- Should return a request ID (a bigint)
   ```

5. **Cron jobs are scheduled:**
   ```sql
   SELECT * FROM cron.job WHERE jobname IN ('watchlist-dispatch', 'discovery-dispatch', 'publish-prices', 'health-monitor');
   -- Should return four rows
   ```

6. **Workflows run manually (via GitHub Actions UI or by manually triggering a cron dispatch):**
   - Manually dispatch `hourly-watchlist.yml` with `alerts_enabled=false` (dry-run mode).
   - Check the workflow log in GitHub Actions UI — should complete without errors.
   - In Supabase, query `SELECT * FROM call_log ORDER BY timestamp DESC LIMIT 5;` — should show rows from the test run.

7. **Dashboard is accessible:**
   - Navigate to the GitHub Pages URL (specified in `DETAIL_PAGE_BASE`).
   - Verify the password gate appears and you can log in (password is in your `DETAIL_PAGE_BASE` URL fragment or `pages/index.html`).
   - Verify prices.json is populated: check `pages/prices.json` in the repo.

8. **Monitor sends alerts:**
   - Wait for the monitor cron job to fire (at :20 or :50 past the hour, weekdays, UTC).
   - Or manually dispatch: `SELECT public.check_pipeline_health();` in Supabase SQL Editor.
   - If the watchlist or discovery has run recently, the monitor should clear any stale alerts. If no run exists, it should send a stale alert to the ntfy topic.
   - Verify the ntfy push appears on your device (or check the ntfy web dashboard).

### Regression Test (Before Production Traffic Resumes)

After backfilling configuration and before resuming scheduled production runs:

1. **Run a full audit locally:**
   ```bash
   pip install -r requirements.txt
   pytest -q --tb=short
   ruff check .
   ```

2. **Dry-run each workflow manually with `alerts_enabled=false`:**
   - `hourly-watchlist.yml` — manually dispatch, verify call log entries are written without sending alerts.
   - `daily-discovery.yml` — manually dispatch, verify discovery candidates are logged.
   - `publish-prices.yml` — manually dispatch, verify prices.json is updated.
   - Verify the detail page renders correctly with the test data.

3. **Verify monitor logic:**
   - Manually call `SELECT public.check_pipeline_health(NOW());` and check the monitor state.
   - Simulate staleness by setting a test heartbeat far in the past: `UPDATE public.run_heartbeat SET last_run_at = NOW() - INTERVAL '2 hours' WHERE workflow_name = 'hourly-watchlist';` then rerun the monitor — should alert.
   - Restore the heartbeat: `UPDATE public.run_heartbeat SET last_run_at = NOW() WHERE workflow_name = 'hourly-watchlist';` and rerun — should clear the alert.

---

## 7. Configuration Reference

### Environment Variables (All Sourced from GitHub Actions Secrets/Variables)

Every tunable and secret is listed in `scripts/config.py` with defaults and descriptions. The workflow files wire them in via `${{ secrets.X }}` (encrypted) and `${{ vars.X }}` (plain-text). The Python code reads them via `os.environ.get()`.

**Secrets:** `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `NTFY_TOPIC`, `NSE_NTFY_TOPIC` (optional), `DETAIL_PAGE_BASE`.

**Variables (all optional, defaults applied if unset):** `GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `NSE_GEMINI_MODEL`, `NSE_GEMINI_MODEL_BACKUP`, `DISCOVERY_GEMINI_MODEL`, `DISCOVERY_GEMINI_MODEL_BACKUP`, `GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BASE_MS`, `GEMINI_TIMEOUT_MS`.

**Other tunables (set in `scripts/config.py`, tunable via workflow environment if needed):** discovery prefilter thresholds (`DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_PRICE`, etc.), market hours (`MARKET_OPEN`, `MARKET_CLOSE`, `NSE_MARKET_OPEN`, `NSE_MARKET_CLOSE`), retry/backoff (`YF_PACING_SECONDS`, `YF_HISTORY_RETRIES`), display clip lengths (`NOTIF_BODY_MAX`, `RATIONALE_MAX`).

See `docs/requirements.md` §10 (Configuration audit baseline) for the full table and current defaults.

### SQL Migrations and Schema

The four migrations in `sql/` define the complete control-plane schema and logic. No other DDL is needed; the tables and functions they create persist:

- `watchlist` — user's tickers and per-market settings.
- `holdings` — user's position data (shares, cost basis).
- `verdict_state` — the last-seen verdict for each ticker, used to detect changes.
- `call_log` — every check result: verdict, rationale, timestamp, data snapshot (JSON).
- `run_heartbeat` — per-workflow metadata for monitoring staleness/degradation.
- `monitor_alerts` — state machine for the health monitor's alert dedup.
- `latest_call_per_ticker` (view) — dashboard read, filtered to only the most recent verdict per ticker.

All modifications to this schema must be applied as new SQL migrations (or via Supabase's migration UI), never by direct ALTER commands.

---

## 8. Post-Deploy Maintenance

### Regular Checks

- **Weekly:** Spot-check the monitor alert state in Supabase. Are there any entries with `last_state != 'ok'`? If so, investigate.
- **Monthly:** Review the call log volume and Gemini token spend (logged in `data_snapshot.tokens` on every call). Is cost staying under budget? (NFR1: $0–15/month.)
- **Per deployment:** After any code change merged to `main`, wait for the next scheduled workflow run and verify the call log entries are written and alerts (if any) are sent correctly.

### Configuration Tuning

All discovery prefilter thresholds, retry/backoff settings, and market-hours tunables can be changed without code changes:

1. **Via Variables (recommended for model swaps):** Update the Variable in GitHub Actions Settings; the next workflow dispatch will pick up the new value.
2. **Via workflow file edits:** Commit a change to `.github/workflows/` and push; the next run will use the new values.
3. **Via `scripts/config.py` defaults:** Edit the file and commit; this changes the fallback if a Variable is unset.

Test any tuning change by manually dispatching with `alerts_enabled=false` before enabling live alerts.

### Incident Response

See §4 (Monitoring and On-Call) for alert interpretation and first-response steps. Key escalation paths:

- **Persistent staleness despite manual redispatches:** GitHub Actions or Supabase is down. Check status.github.com and Supabase status page. No action until platform recovers.
- **Degraded status (partial errors) on every run:** Likely a data source issue (Yahoo Finance, Gemini quota/error). Check Gemini usage in the Google Cloud console; check Yahoo Finance API docs for rate-limits or service announcements. Increase `YF_PACING_SECONDS` or `GEMINI_TIMEOUT_MS` if needed.
- **Runaway alert spam:** Verdict is oscillating on a choppy ticker. This is expected behavior (single-rule design, no debounce). Acknowledge in ntfy; no action needed unless it's legitimately a data error (e.g., stock split, ticker error).

---

## 9. Contacts and Escalation

- **Release issues (this runbook, CI/CD config, deploy procedures):** Route to the `release` role (orchestrator will identify the assigned agent).
- **Design/architecture questions:** Route to `tech-lead` (owns `docs/design.md`).
- **Feature/requirement changes:** Route to `pm` (owns `docs/requirements.md`).
- **Incident response (workflows down, data corruption, alerts firing wrongly):** First check this runbook's §4–6. If unresolved, escalate to the agent who owns the affected component (release for CI/CD, tech-lead for Supabase logic, dev for application code bugs).

---

## Appendix A: Quick Reference — Workflows

| File | Trigger | Runs | Purpose |
|---|---|---|---|
| `audit.yml` | Push, PR | ~1–2 min | Gitleaks, linting, tests; CI baseline |
| `hourly-watchlist.yml` | pg_cron every 30 min (13–21 UTC) | ~3–5 min | Watchlist AI checks; intraday cadence |
| `daily-discovery.yml` | pg_cron once daily (22:00 UTC, 10:00 UTC NSE) | ~2–4 min | Candidate discovery scan |
| `publish-prices.yml` | pg_cron every 30 min market cadence, or manual push | ~1–2 min | Fetch prices, commit to pages/prices.json |

---

## Appendix B: Quick Reference — Supabase Functions

| Function | Callable by | Purpose |
|---|---|---|
| `dispatch_github_workflow(workflow_file text, inputs jsonb)` | pg_cron only (revoked from public) | POST to GitHub Actions workflow_dispatch API |
| `dispatch_watchlist_if_open()` | pg_cron only (revoked from public) | Gate: dispatch watchlist only during ET market hours (09:30–16:05) |
| `dispatch_watchlist_nse_if_open()` | pg_cron only (revoked from public) | Gate: dispatch watchlist only during IST market hours (09:15–15:35) |
| `check_pipeline_health(p_now timestamptz)` | pg_cron only (revoked from public) | Health monitor: check staleness/degradation, send ntfy alerts |
| `send_ntfy(title, message, priority, tags)` | monitor functions only (revoked from public) | Publish alert to ntfy.sh topic |

---

**Last updated:** 2026-07-25 (backfill for REV-027, reverse-documented from live system).
