-- =====================================================================
-- Core data-plane schema — captured from the live Supabase project
-- =====================================================================
-- WHY THIS FILE EXISTS (reviewer Pass 11, REV-035): the same defect class
-- sql/scheduler_pgcron.sql was written to fix ("the DDL lived ONLY inside
-- Supabase and was never committed") existed, uncorrected, for the entire
-- data plane: watchlist, holdings, verdict_state, call_log, run_heartbeat,
-- and every RLS policy on them. docs/runbook.md's fresh-deploy procedure
-- listed four migrations as "the complete control-plane schema" — following
-- it produced a project with no tables for the pipeline to write to.
--
-- This file captures the FIVE tables above (not `monitor_alerts`, which is
-- already defined in sql/phase5_monitoring.sql, and not the
-- `latest_call_per_ticker` view, already in sql/dashboard_latest_call_view.sql
-- — this file doesn't duplicate either). Columns and CHECK constraints are
-- taken from docs/design/data-and-flow.md §5 and docs/requirements.md §10,
-- both independently confirmed accurate against the live code by reviewer;
-- market/currency/verdict/label/alert_type CHECK sets and the RLS/grant
-- posture below were supplied directly from a live `list_tables` /
-- `pg_policies` check (all six existing tables show `rls_enabled: true`).
--
-- THIS FILE IS A CAPTURE OF WHAT ALREADY EXISTS LIVE, NOT NEW DDL TO APPLY
-- TO THE LIVE PROJECT. It is written idempotently (`create table if not
-- exists`) so it is SAFE to run against a project that already has these
-- objects (the `create table` statements no-op; a `create policy` against an
-- already-live policy of the same name will error — expected and fine, since
-- this file's purpose against the live project is verification/diffing, not
-- re-application). Against a FRESH project (disaster recovery, or a new
-- deploy per docs/runbook.md), this file is the missing piece that makes the
-- documented apply order actually produce a working schema.
--
-- Apply order (fresh deploy): sql/scheduler_pgcron.sql, THIS FILE,
-- sql/phase5_monitoring.sql, sql/dashboard_latest_call_view.sql,
-- sql/enable_monitor_alerts_rls.sql (last — see that file's header for why
-- it can't be folded into this one). (THIS FILE must come before
-- phase5_monitoring.sql, since check_pipeline_health() reads run_heartbeat,
-- defined here.) See docs/runbook.md §2.3 for the full, corrected order.
--
-- NOT independently re-verified against the live project by tech-lead this
-- pass (no live Supabase/MCP access in this session) — built from the
-- sources above per the orchestrator's brief. dev/release should confirm
-- column-for-column against `list_tables`/`pg_policies` before treating this
-- as authoritative for a real fresh deploy.
-- =====================================================================

-- --- watchlist --------------------------------------------------------
create table if not exists public.watchlist (
  ticker      text primary key,
  market      text not null check (market in ('US', 'TSX', 'NSE')),
  type        text not null default 'stock' check (type in ('stock', 'ETF')),
  status      text not null check (status in ('held', 'watch-only')),
  date_added  timestamptz not null default now()
);
alter table public.watchlist enable row level security;

-- anon (dashboard, detail page, publish_prices.py via secret key) reads the
-- full list; writes go through the secret key (workflows) or, from INC-5 on,
-- the admin portal's is_admin()-gated policy (sql/admin_portal_rls.sql).
create policy "anon_read_watchlist" on public.watchlist
  for select to anon, authenticated
  using (true);

-- --- holdings -----------------------------------------------------------
create table if not exists public.holdings (
  ticker      text primary key references public.watchlist(ticker),
  shares      numeric not null check (shares > 0),
  cost_basis  numeric not null check (cost_basis > 0),
  currency    text not null check (currency in ('USD', 'CAD', 'INR'))
);
alter table public.holdings enable row level security;
-- No anon/public policy — RLS enabled with zero policies today, i.e.
-- zero anon/authenticated access (confirmed live: rls_enabled=true, no
-- policies). Only the secret-key workflows read it (bypasses RLS); INC-5
-- (admin-portal.md §16.3) is this table's first policy, an authenticated
-- is_admin()-gated write.

-- --- verdict_state --------------------------------------------------------
-- Shrunk to 3 columns when the FR7 cooldown/reminder was retired
-- (docs/design.md §0, load-bearing #1/#2) — no longer tracks a reminder
-- timestamp or streak count, just the last-seen verdict for change detection.
create table if not exists public.verdict_state (
  ticker            text primary key references public.watchlist(ticker),
  current_verdict   text not null check (current_verdict in ('Buy', 'Sell', 'Hold')),
  last_checked_at   timestamptz not null default now()
);
alter table public.verdict_state enable row level security;
-- No anon/authenticated policy — internal change-detection state, read/
-- written only by the secret-key workflows (state.py).

-- --- call_log --------------------------------------------------------
-- The track record (FR15/FR16) and the detail page's source (FR14). `id` is
-- a UUID, not a serial — the detail page's entire access-control posture
-- (Decision #17, no auth gate) rests on this ID being unguessable.
create table if not exists public.call_log (
  id              uuid primary key default gen_random_uuid(),
  ticker          text not null,
  verdict         text not null check (verdict in ('Buy', 'Sell', 'Hold')),
  rationale       text,
  "timestamp"     timestamptz not null default now(),
  label           text not null check (label in ('watchlist', 'new-candidate')),
  alert_type      text check (alert_type in ('change') or alert_type is null),
  alerted         boolean not null default false,
  data_snapshot   jsonb
);
alter table public.call_log enable row level security;

-- anon/authenticated read every row (the dashboard's superseded direct scan
-- and the detail page's single-row fetch both go through this policy; the
-- `latest_call_per_ticker` view, sql/dashboard_latest_call_view.sql, is
-- security_invoker=true so this same policy governs it too) — writes only
-- via the secret-key workflows.
create policy "anon_read_call_log" on public.call_log
  for select to anon, authenticated
  using (true);

-- --- run_heartbeat --------------------------------------------------------
-- Per-workflow last-run marker (NFR2). Keys: hourly-watchlist (shared across
-- both watchlist sessions), daily-discovery (NA), daily-discovery-in (NSE),
-- publish-prices. Read by check_pipeline_health() (sql/phase5_monitoring.sql,
-- SECURITY DEFINER, bypasses RLS) — no anon/authenticated policy needed.
create table if not exists public.run_heartbeat (
  workflow_name   text primary key,
  last_run_at     timestamptz not null default now(),
  status          text not null default 'ok'
);
alter table public.run_heartbeat enable row level security;
-- No anon/authenticated policy — written by the secret-key workflows, read
-- by check_pipeline_health() (SECURITY DEFINER, bypasses RLS).

-- =====================================================================
-- `monitor_alerts` (dead-man monitor dedup state, NFR2) is defined in
-- sql/phase5_monitoring.sql, not here — not duplicated. Its missing RLS
-- statement is captured separately, in sql/enable_monitor_alerts_rls.sql
-- (REV-033/035), since `monitor_alerts` doesn't exist yet at the point in
-- the apply order this file runs (see that file's header for why it can't
-- live here despite being the same finding).
-- `latest_call_per_ticker` (dashboard read view) is defined in
-- sql/dashboard_latest_call_view.sql, not here. Not duplicated.
-- =====================================================================
