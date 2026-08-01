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

3. **Apply SQL migrations in this exact order** (via Supabase SQL Editor or via the Supabase CLI `supabase db push`). This list is the single authority for apply order — `sql/kill_switch.sql` and `sql/schema.sql`'s own header comments point back here rather than restating it:
   - `sql/kill_switch.sql` **(added 2026-07-28, INC-3, FR24-26/NFR2; reviewer REV-063)** — creates `kill_switch_state`, `kill_switch_audit`, and `set_kill_switch()`. **Must be applied first**, before `scheduler_pgcron.sql` and `phase5_monitoring.sql`: both `dispatch_github_workflow()` (edited in `scheduler_pgcron.sql`) and `check_pipeline_health()` (in `phase5_monitoring.sql`) `select ... from public.kill_switch_state`, so applying either before this table exists hits a runtime error on a live project. This step was previously missing from this list entirely (reviewer REV-063) even though `kill_switch.sql`'s own header already stated the "apply first" requirement — it simply wasn't reflected here.
   - `sql/scheduler_pgcron.sql` (creates `dispatch_github_workflow()` function and base cron jobs for watchlist/discovery/prices)
   - `sql/schema.sql` **(added 2026-07-28, reviewer REV-035)** — creates `watchlist`, `holdings`, `verdict_state`, `call_log`, and `run_heartbeat`, with RLS enabled and the anon-read policies on `watchlist`/`call_log`. **This step was previously missing from this list entirely** — the old three-migration order, run against a fresh project, produced no tables for the pipeline to write to. Must be applied before `phase5_monitoring.sql`, since `check_pipeline_health()` reads `run_heartbeat`, defined here.
   - `sql/phase5_monitoring.sql` (creates health-monitor function `check_pipeline_health()`, dispatch gates for market hours, monitor alert state table, and schedules the health check itself). **This is now the sole, reconciled source of `check_pipeline_health()`** (reviewer REV-062, fixed 2026-07-28) — it carries the kill-switch pause-check + resume-baseline fix (FR25/NFR2), the discovery/publish-prices degraded-check branches, and the ET/IST watchlist dedup, all together. `sql/fix_missing_degraded_checks.sql` and `sql/dedup_watchlist_health_check.sql` are superseded and must **not** be applied (see below).
   - `sql/dashboard_latest_call_view.sql` (creates the `latest_call_per_ticker` view, used by the dashboard and detail page for fast read-only queries)
   - `sql/enable_monitor_alerts_rls.sql` **(added 2026-07-28, reviewer REV-033/REV-035)** — one-line RLS-enable for `monitor_alerts`, which `phase5_monitoring.sql`'s `create table` never included even though the live table has RLS enabled. Must come after `phase5_monitoring.sql` (the table doesn't exist yet before that).
   - `sql/admin_portal_rls.sql` **(added 2026-07-26, INC-5, FR27-29/NFR5/NFR6)** — creates `admin_allowlist` table, `is_admin()` authorization function, and write policies for `watchlist`/`holdings`. Must come after `schema.sql` (the tables it writes policies for must exist first). Must be applied before any portal writes can succeed; deployed to Vercel as part of INC-5.
   - `sql/admin_portal_tunables.sql` **(added 2026-07-27, INC-6, FR30/NFR5/NFR6)** — creates `tunables` table (source of truth for tunable overrides), the `tunables_stamp_update` trigger, and the write policy for the portal to edit them. Must come after `schema.sql`. Deployed as part of INC-6.
   - `sql/admin_portal_tunables_alerts_enabled_description_fix.sql` **(added 2026-07-30, INC-10, REV-112)** — corrective UPDATE to the ALERTS_ENABLED seed row's description, to accurately reflect that the effective value is table-value AND workflow input. INC-6's own seed INSERT carries the corrected text for fresh deploys; this file brings live projects already running INC-6 in sync. Must come after `admin_portal_tunables.sql` (the row being updated must exist). Idempotent (WHERE scoped to key='ALERTS_ENABLED'); verified re-runnable. **APPLIED AND LIVE** (confirmed against production 2026-07-30).
   - `sql/tunables_validate_trigger.sql` **(added 2026-07-30, INC-10, FR30/Decision #34)** — write-time validation trigger on `tunables` table, rejecting bad values before they are stored (DEEP-005 fix). Mirrors `scripts/config.py`'s per-key casts/domains exactly so portal edits and direct SQL edits are validated identically. Trigger named `tunables_0_validate_update` (sorts before `tunables_stamp_update` alphabetically) so it fires first and rejects before the stamp trigger runs. Must come after `admin_portal_tunables.sql` (the table must exist). Uses `create or replace trigger` (PG14+); idempotent and re-runnable. Verify correct fire order via `select tgname from pg_trigger where tgrelid = 'public.tunables'::regclass order by tgname;` — should show `tunables_0_validate_update` before `tunables_stamp_update`. **APPLIED AND LIVE** (confirmed against production 2026-07-30).
   - `sql/holdings_currency_derivation.sql` **(added 2026-07-30, INC-10, FR11/FR29/Decision #35)** — write-time trigger on `holdings` table to derive `currency` from the held ticker's `watchlist.market`, rather than allowing free-choice currency entry (DEEP-006 fix). Unconditionally overwrites `currency` on every write, ensuring holdings reflect accurate cost-basis currency. Must come after `schema.sql` (the holdings/watchlist tables and their FK must exist). Uses `create or replace trigger` (PG14+); idempotent and re-runnable. **APPLIED AND LIVE** (confirmed against production 2026-07-30).
   - `sql/kill_switch_portal_grant.sql` **(added 2026-07-29, INC-7, FR32/NFR6)** — extends `set_kill_switch()` with an `is_admin()` authorization check for authenticated portal callers, adds the `grant execute` for authenticated role, and adds a SELECT policy so the portal can read `kill_switch_state`. Also closes a TRUNCATE-grant gap on `kill_switch_state` and `kill_switch_audit` (same class as REV-081/REV-086 found on `admin_allowlist`/`tunables`). Must come after `kill_switch.sql` (both tables must exist). Deployed as part of INC-7.
   - `sql/schema_truncate_grant_closure.sql` **(added 2026-07-29, reviewer REV-099)** — closes TRUNCATE-grant gap on the six original schema tables (`watchlist`, `holdings`, `call_log`, `verdict_state`, `run_heartbeat`, `monitor_alerts`). RLS never governs TRUNCATE in Postgres; this REVOKE is the belt-and-suspenders lockdown preventing anon/authenticated TRUNCATE access on these tables. Carefully scoped per table: `watchlist`/`holdings` retain authenticated's INSERT/UPDATE/DELETE base grants (required for INC-5's live write policies), while the other four tables lose all four DML+TRUNCATE verbs. Must come after `schema.sql` and `phase5_monitoring.sql` (both tables must exist). Applied and live on this project as of 2026-07-29.
   - `sql/kill_switch_abort_log.sql` **(added 2026-07-30, INC-12, FR35/Decision #38)** — append-only audit table recording every deliberate kill-switch pause mid-run (causal tie: row exists iff pause was the direct cause of workflow abort). Standalone table with no interdependencies; uses `create table if not exists` + idempotent RLS/REVOKE. Does not require PG14+; applies cleanly on any Postgres version this project targets. **APPLIED AND LIVE** (verified re-runnable against local Postgres 16, confirmed against production 2026-07-30).
   - `sql/tickers_screen_rpc.sql` **(added 2026-08-01, INC-15, FR37)** — creates two SECURITY DEFINER RPC functions (`set_ticker_holding_status()` and `delete_ticker()`) for the admin portal's ticker screen, wrapping multi-table writes to prevent partial failures due to foreign-key constraints (docs/design/admin-portal.md §16.11.5, Decision #40). Both functions are gated by `is_admin()` and granted `EXECUTE` to authenticated role only (no anon). Must come after `schema.sql` (for watchlist/holdings tables) and `admin_portal_rls.sql` (for `is_admin()` function). Uses `create or replace function`; idempotent and re-runnable. **APPLIED AND LIVE** (both functions confirmed present, prosecdef=true verified, EXECUTE grant set confirmed exactly {postgres, service_role, authenticated} with no anon, against production 2026-08-01).

These fifteen migrations set up the entire control plane and admin-portal backend (`kill_switch.sql`'s two tables, `sql/schema.sql`'s five tables, `monitor_alerts` created by `phase5_monitoring.sql`, `admin_allowlist`/`tunables` created by the two portal-support migrations, plus the `latest_call_per_ticker` view, the validation/derivation triggers, the kill-switch abort audit table, plus the TRUNCATE-grant closures). The cron jobs will start firing immediately on the schedules defined below.

**Postgres version floor:** Two of these migrations (`tunables_validate_trigger.sql` and `holdings_currency_derivation.sql`) use `create or replace trigger` syntax, which requires **Postgres 14 or later**. The live project runs Postgres 17.6.1. A fresh environment must meet this floor; older Postgres versions will fail on those two files with a syntax error.

**Note:** `sql/drop_shadow_tables_migration.sql` is a one-time migration that was already applied to this project; it is not part of the fresh-deploy procedure (a fresh project never had those tables to drop). It remains in the repo as a historical record.

**Superseded — do not apply:** `sql/fix_missing_degraded_checks.sql` (REV-042) and `sql/dedup_watchlist_health_check.sql` (REV-047) each committed their own independent `check_pipeline_health()` body. Reviewer Pass 12 (REV-062, blocker) found no apply order among the three committed bodies (these two plus `phase5_monitoring.sql`'s INC-3 edit) produced a correct function — applying either of these two alone, as this runbook previously instructed, silently reverted INC-3's kill-switch pause-check/resume-baseline fix with no error. Both fixes are now folded into `phase5_monitoring.sql`'s single reconciled function (above); these two files no longer define the function at all (see each file's header) and are kept only as a historical/non-applyable record.

#### 2.4 Admin Portal Deployment (INC-5/6/7)

The admin portal (`admin-portal/` directory in this repo) is a Next.js application deployed to Vercel. It provides authenticated write access to the system's configuration (watchlist, holdings, tunables) and operational controls (kill-switch toggle and track-record view).

##### Vercel Project Setup

1. **Create a Vercel project** (if not already deployed):
   - Sign in to https://vercel.com with the appropriate account.
   - Import the `stock-advisory-analysis` repository (GitHub import).
   - **Set the project root to `admin-portal/`** — this is required for Vercel to deploy the Next.js app from the subdirectory.
   - Use default build settings (Vercel auto-detects Next.js).

2. **Environment variables in Vercel**:
   - Go to Settings > Environment Variables in the Vercel dashboard.
   - Add these **public environment variables** (safe to expose; these are the low-privilege Supabase anon keys):
     - `NEXT_PUBLIC_SUPABASE_URL`: The Supabase project URL (format: `https://<project-id>.supabase.co`)
     - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: The Supabase anon/publishable key (starts with `eyJ...`)
   - These are the same values used by the public dashboard and detail page; no new secrets are exposed.
   - No other environment variables are needed for the portal — it uses the Supabase client library to read/write via RLS, not a server-side proxy.

##### Google OAuth Configuration

The admin portal uses **Supabase Auth with Google OAuth as the only login provider**:

1. **Configure Google OAuth in Supabase Auth dashboard** (one-time setup at INC-5):
   - In Supabase dashboard, go to **Authentication > Providers > Google**.
   - Enable Google OAuth and enter your Google Cloud credentials (OAuth client ID and secret).
   - Set the Supabase auth callback URL (Supabase will display the exact URL during setup; point your Google app's authorized redirect URIs to it).

2. **Disable other auth methods in Supabase Auth dashboard**:
   - Go to **Authentication > Providers**.
   - **Disable** Email/Password and Magic Link sign-in.
   - **Only Google OAuth should be enabled.**

3. **Seed the admin allowlist** (one-time setup at INC-5):
   - After `sql/admin_portal_rls.sql` is applied, seed the `admin_allowlist` table with Arjun's Google account email (the one used to sign in):
   ```sql
   INSERT INTO public.admin_allowlist (email) VALUES ('arjun@example.com');
   ```
   - Replace `arjun@example.com` with the actual Google account email that should be the system admin.
   - This is the single source of truth for who can edit the portal; all RLS policies check `public.is_admin()`, which queries this table.

##### Portal Routes and Deployment Notes

- **Login/OAuth callback**: `/login` (sign-in with Google) and `/auth/callback` (OAuth code-exchange, Supabase Auth standard flow).
- **Configuration screens** (authenticated only):
  - `/watchlist` — add/edit/delete tickers (FR28, INC-5).
  - `/holdings` — add/edit/delete positions (FR29, INC-5).
  - `/tunables` — override AI model, retry, timeout settings (FR30, INC-6).
  - `/track-record` — read-only paginated view of the call log (FR31, INC-7).
- **Kill-switch toggle**: Displayed in the top-right header of every authenticated page (surfaced on shared layout, not a standalone route, INC-7).

All writes go through the Supabase client library with the signed-in user's session JWT, enforced by RLS policies in the database. There is no server-side API layer or GitHub-PAT proxy — the portal is a pure client-side app (except for the standard OAuth callback route).

##### Custom Domain Setup

The portal is deployed to a custom domain (configured in Vercel's domain settings). Point the domain's CNAME or nameservers to Vercel's servers per Vercel's documentation. Once deployed, the portal is accessible at the custom domain URL and the OAuth callback is routed via that same domain.

### Workflows and Their Schedules

After SQL migrations are applied, the four workflows are triggered as follows:

| Workflow | Schedule | Via | Purpose |
|---|---|---|---|
| `hourly-watchlist.yml` | Every 30 min, 13:00–21:59 UTC weekdays | `cron.schedule('watchlist-dispatch', '*/30 13-21 * * 1-5', ...)` in `scheduler_pgcron.sql` → `dispatch_watchlist_if_open()` gate in `phase5_monitoring.sql` → `dispatch_github_workflow('hourly-watchlist.yml')` | Intraday watchlist checks, run every ~30 min during market hours (gate trims to 09:30–16:05 ET / 09:15–15:35 IST, i.e., real session + buffer for jitter) |
| `daily-discovery.yml` | Once daily, 22:00 UTC Mon–Fri | `cron.schedule('discovery-dispatch', '0 22 * * 1-5', ...)` in `scheduler_pgcron.sql` → direct dispatch | Post-US-close candidate discovery scan; also fires NSE discovery at 10:00 UTC (separate cron: `discovery-dispatch-nse`) with `region=in` input |
| `publish-prices.yml` | Every 30 min, 03:00–10:59 and 13:00–21:59 UTC weekdays (market cadence) | `cron.schedule('publish-prices', '*/30 3-10,13-21 * * 1-5', ...)` in `scheduler_pgcron.sql` → direct dispatch | Fetches live prices via yfinance and commits `pages/prices.json` if prices changed (issue #18 CORS workaround; see `docs/design/frontend.md` §11 and `docs/requirements.md` Decision #18) |
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

- **What it is:** A pg_cron job (`check_pipeline_health()` in `sql/phase5_monitoring.sql`) that runs at :20 and :50 past the hour during specific UTC hour windows (4–11 and 14–23), Mon–Fri. (This schedule covers both the NSE session and the US/TSX session with some margin.)
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

1. **Gemini data privacy:** Paid-tier models do not train on submitted prompts (watchlist, holdings, cost basis) per Google's standard terms. **Current state:** Production uses paid-tier `gemini-2.5-flash` (see `docs/requirements.md` §6, NFR1).

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
   SELECT public.dispatch_github_workflow('hourly-watchlist.yml');
   -- Should return a request ID (a bigint)
   ```
   To verify success, check the corresponding row in `net._http_response`:
   ```sql
   SELECT status, content FROM net._http_response 
   WHERE id = <request_id_from_above> LIMIT 1;
   -- Should show status 204 (success) or 422 if workflow dispatch failed
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
   - Verify the password gate appears and you can log in (password is in your `DETAIL_PAGE_BASE` URL fragment or `pages/dashboard.html`).
   - Verify prices.json is populated: check `pages/prices.json` in the repo.

8. **Monitor sends alerts:**
   - Wait for the monitor cron job to fire (at :20 or :50 past the hour, weekdays, UTC).
   - Or manually dispatch: `SELECT public.check_pipeline_health();` in Supabase SQL Editor.
   - If the watchlist or discovery has run recently, the monitor should clear any stale alerts. If no run exists, it should send a stale alert to the ntfy topic.
   - Verify the ntfy push appears on your device (or check the ntfy web dashboard).

9. **Admin portal deployment to Vercel (INC-5/6/7):**
   - Verify the Vercel project is created and set to the `admin-portal/` root.
   - Verify `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are set in Vercel environment variables.
   - Navigate to the portal's custom domain (or the auto-generated Vercel domain if custom domain not yet configured).
   - Verify the `/login` page appears and Google OAuth sign-in is available.
   - Sign in with an email that has been added to `admin_allowlist` (seeded with `INSERT INTO public.admin_allowlist (email) VALUES ('...');` after `sql/admin_portal_rls.sql` is applied).
   - Verify the `/watchlist` page loads and displays the current tickers (read-only preview if you have not added any).
   - Verify the `/holdings` page loads (FR29, INC-5).
   - Verify the `/tunables` page loads (FR30, INC-6).
   - Verify the `/track-record` page loads with paginated `call_log` entries (FR31, INC-7).
   - Verify the kill-switch toggle appears in the header, shows the current state (PAUSED/RUNNING), and clicking the toggle button flips it — check `kill_switch_state.paused` in Supabase to confirm the database state changed.

10. **SQL migrations applied (INC-10/INC-12 additions, four new files):**
   - **Tunables validation trigger** (`sql/tunables_validate_trigger.sql`, FR30):
     ```sql
     SELECT tgname FROM pg_trigger WHERE tgrelid = 'public.tunables'::regclass ORDER BY tgname;
     ```
     Should return two rows: `tunables_0_validate_update` (FR30 validation, fires first) and `tunables_stamp_update` (INC-6 timestamp). Fire order is critical: 0 sorts before s, so validation always runs before stamping.
   - **Holdings currency derivation trigger** (`sql/holdings_currency_derivation.sql`, FR11/FR29):
     ```sql
     SELECT tgname FROM pg_trigger WHERE tgrelid = 'public.holdings'::regclass;
     ```
     Should return `holdings_derive_currency` trigger (fires before/after insert or update to derive currency from watchlist.market).
   - **ALERTS_ENABLED description fix** (`sql/admin_portal_tunables_alerts_enabled_description_fix.sql`):
     ```sql
     SELECT description FROM public.tunables WHERE key = 'ALERTS_ENABLED';
     ```
     Should include text mentioning "Effective value is this AND the workflow's alerts_enabled input" — if it still reads only "Master switch for real pushes" without the AND clause, the fix was not applied.
   - **Kill-switch abort audit table** (`sql/kill_switch_abort_log.sql`, FR35):
     ```sql
     SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'kill_switch_abort_log');
     ```
     Should return `true`. Then verify RLS/REVOKE posture (matching `admin_allowlist` and `kill_switch_audit`):
     ```sql
     SELECT grantee, privilege_type FROM information_schema.role_table_grants 
     WHERE table_name = 'kill_switch_abort_log' AND grantee IN ('anon', 'authenticated') 
     ORDER BY grantee, privilege_type;
     ```
     Should return **only** REFERENCES, SELECT, and TRIGGER privileges for both `anon` and `authenticated` — **NOT** INSERT, UPDATE, DELETE, or TRUNCATE. If any DML/TRUNCATE appears, the REVOKE was not applied or was reversed by mistake.

### Regression Test (Before Production Traffic Resumes)

After backfilling configuration and before resuming scheduled production runs:

1. **Run a full audit locally:**
   ```bash
   pip install -r requirements.txt
   pytest -q --tb=short
   ruff check .
   ruff check --select C90 .
   ```
   Both `ruff` invocations must be run — `.github/workflows/audit.yml` runs both, and `ruff check .`
   alone (the E/F/W ruleset in `ruff.toml`) does not catch a `C901` cyclomatic-complexity violation.
   A local check that only runs the first can pass while CI is red on the second.

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

The migrations in `sql/` (fourteen files per §2.3's apply order) define the complete control-plane schema
and admin-portal backend. No other DDL is needed; the tables and functions they create persist:

**Core schema and monitoring:**
- `kill_switch_state` — singleton pause flag read by `dispatch_github_workflow()` and
  `check_pipeline_health()` (`sql/kill_switch.sql`, FR24/FR25).
- `kill_switch_audit` — append-only history of every pause/resume toggle (`sql/kill_switch.sql`, FR26).
- `watchlist` — user's tickers and per-market settings (`sql/schema.sql`, FR28).
- `holdings` — user's position data (shares, cost basis) (`sql/schema.sql`, FR29).
- `verdict_state` — the last-seen verdict for each ticker, used to detect changes (`sql/schema.sql`).
- `call_log` — every check result: verdict, rationale, timestamp, data snapshot (JSON) (`sql/schema.sql`, FR15/FR16 audit trail).
- `run_heartbeat` — per-workflow metadata for monitoring staleness/degradation (`sql/schema.sql`).
- `monitor_alerts` — state machine for the health monitor's alert dedup (`sql/phase5_monitoring.sql`).
- `latest_call_per_ticker` (view) — dashboard read, filtered to only the most recent verdict per ticker
  (`sql/dashboard_latest_call_view.sql`).

**Admin-portal backend:**
- `admin_allowlist` — list of Google email addresses authorized to access the portal (`sql/admin_portal_rls.sql`, FR27).
- `is_admin()` — authorization function, checks if current user's email is in `admin_allowlist` (`sql/admin_portal_rls.sql`, FR27).
- `tunables` — source of truth for tunable overrides (AI model, retry, timeout settings) (`sql/admin_portal_tunables.sql`, FR30).
- `_validate_tunable_update()` + `tunables_0_validate_update` trigger — write-time validation rejecting bad tunable values before they are stored (DEEP-005 fix, `sql/tunables_validate_trigger.sql`, FR30/Decision #34). Verify fire order: `select tgname from pg_trigger where tgrelid = 'public.tunables'::regclass order by tgname;` should show `tunables_0_validate_update` before `tunables_stamp_update`.
- `_derive_holdings_currency()` + `holdings_derive_currency` trigger — unconditional currency derivation from `watchlist.market` on every holdings write, replacing free-choice currency (DEEP-006 fix, `sql/holdings_currency_derivation.sql`, FR11/FR29/Decision #35).

**Audit and operational control:**
- `kill_switch_abort_log` — append-only table recording every deliberate kill-switch pause mid-run, establishing causal tie (a row's existence proves pause was the cause of abort, not coincidence) (`sql/kill_switch_abort_log.sql`, FR35/Decision #38).

**Security lockdowns:**
- TRUNCATE grant revocations on kill-switch, original schema, and admin-portal tables (`sql/kill_switch_portal_grant.sql`, `sql/schema_truncate_grant_closure.sql`, REV-081/REV-086/REV-099).
- RLS and REVOKE on `kill_switch_abort_log` — no anon/authenticated access, same two-layer deny-all as `admin_allowlist` and `kill_switch_audit` (no INSERT/UPDATE/DELETE/TRUNCATE, even if a policy were added by mistake) (`sql/kill_switch_abort_log.sql`, Decision #37).

**RLS posture (REV-035, confirmed live via `list_tables` 2026-07-28, updated for INC-5/INC-7/INC-10/INC-12 additions):**
`watchlist`, `holdings`, `verdict_state`, `call_log`, `run_heartbeat`, and `monitor_alerts` all show
`rls_enabled: true`. `watchlist` and `call_log` have anon/authenticated SELECT policies (the
dashboard/detail-page read path); `watchlist` and `holdings` also have authenticated-role write policies
gated by `is_admin()` (`admin_write_watchlist` and `admin_write_holdings`, added in INC-5 `sql/admin_portal_rls.sql`);
`verdict_state` and `run_heartbeat` have RLS enabled with zero policies — read/written only by
secret-key workflows or `SECURITY DEFINER` functions. `monitor_alerts` has RLS enabled with zero policies
(internal monitor state, not touched by any anon/authenticated role). `sql/schema.sql` and
`sql/admin_portal_rls.sql` capture this posture in version control. `kill_switch_state` and `kill_switch_audit`
**ARE** part of this live-confirmed set (INC-3's SQL was applied to production early in the session); their
RLS/REVOKE posture is documented in `docs/design/operational-controls.md` §13.2 and verified in
`docs/handoff.md`'s dated INC-3 evidence block (2026-07-29 kill-switch pause/resume audit, confirming both
tables exist with RLS enabled, and `set_kill_switch()` works correctly). `kill_switch_state` has an
authenticated-role SELECT policy gated by `is_admin()` (`admin_read_kill_switch`, added in INC-7
`sql/kill_switch_portal_grant.sql`), permitting the portal to read the current pause state. `kill_switch_abort_log`
(added INC-12, `sql/kill_switch_abort_log.sql`) has RLS enabled with zero policies and a two-layer deny-all REVOKE
(no anon/authenticated INSERT/UPDATE/DELETE/TRUNCATE), matching the same posture as `admin_allowlist` and `kill_switch_audit`.
`tunables` (added INC-6, `sql/admin_portal_tunables.sql`) has RLS enabled with authenticated-role write policies gated by
`is_admin()` (`admin_read_tunables` and `admin_write_tunables`); the _validate_tunable_update() and _derive_holdings_currency()
functions (`sql/tunables_validate_trigger.sql` and `sql/holdings_currency_derivation.sql`, INC-10) are `SECURITY DEFINER`
triggers, not exposed as standalone objects to any role.

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
