-- =====================================================================
-- call_log authenticated-read fix (BUG-009, FR31, docs/design/admin-portal.md §16.5)
-- =====================================================================
-- Doc/reality drift, not a straightforward "add a policy" gap: sql/schema.sql:100-105 documents a
-- policy named `anon_read_call_log`, `for select to anon, authenticated using (true)` — i.e.
-- schema.sql's committed text already claims `authenticated` has read access to call_log, and
-- §16.5's design text ("no new RLS needed... the anon SELECT policy on call_log already covers it")
-- was written on the strength of that same claim. Confirmed directly against production (project
-- ikghqdtlbwifwnooytmm) via pg_policies that this was never actually true: the live policy on
-- public.call_log is named "anon read call_log" (spaces, not underscores — a different object than
-- the one schema.sql documents), scoped `TO anon` only, `cmd: SELECT`, `qual: true`. `authenticated`
-- is not a member of `anon` (confirmed via pg_auth_members), so every portal query after Google OAuth
-- sign-in (admin-portal/lib/supabase-client.ts, a browser client carrying the signed-in session) runs
-- as role `authenticated` and gets zero rows back — RLS filtering, not an error, so the track-record
-- view (FR31, admin-portal/app/(app)/track-record/page.tsx) renders an empty table with no error
-- message for every signed-in admin. Data itself is fine (8,890 rows in call_log, confirmed live).
--
-- Root cause of the drift: schema.sql's documented state was never actually applied for this table
-- (or was superseded by a different, undocumented deploy at some point) — the live object predates
-- or diverged from what's on disk. This file does not touch sql/schema.sql itself (the established
-- convention here is to leave the original CREATE TABLE file alone and layer fixes in new files, same
-- as schema_truncate_grant_closure.sql and kill_switch_portal_grant.sql).
--
-- Fix: drop the stale, misnamed, under-scoped live policy and recreate it under schema.sql's own
-- canonical name/shape, rather than leaving two overlapping SELECT policies on the same table (one
-- anon-only, one anon+authenticated) — recreating under the canonical name keeps exactly one
-- clearly-named policy governing this read path, matching what schema.sql has claimed all along and
-- what every other anon/authenticated SELECT policy in this codebase (watchlist, tunables, etc.) does.
-- Also governs the security_invoker=true `latest_call_per_ticker` view
-- (sql/dashboard_latest_call_view.sql), same as the original policy did.

-- Both drops named explicitly (not just the misnamed one) so this file re-applies cleanly whether
-- run once or twice — Postgres has no `CREATE OR REPLACE POLICY`, and a bare `create policy
-- anon_read_call_log` would error "already exists" on a second run once the fix is live.
drop policy if exists "anon read call_log" on public.call_log;
drop policy if exists "anon_read_call_log" on public.call_log;

create policy "anon_read_call_log" on public.call_log
  for select to anon, authenticated
  using (true);

-- NOT APPLIED LIVE by dev — no Supabase MCP/DB credentials available in this task. Orchestrator
-- applies this against project ikghqdtlbwifwnooytmm, same process as every prior sql/ fix file.
