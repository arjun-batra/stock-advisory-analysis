-- =====================================================================
-- TRUNCATE-grant closure for the original five-table schema + monitor_alerts
-- (reviewer REV-099, major)
-- =====================================================================
-- Same gap class already found and fixed three times in this project
-- (REV-081 `admin_allowlist`, REV-086 `tunables`, INC-7's
-- `kill_switch_state`/`kill_switch_audit`): RLS never governs TRUNCATE in
-- Postgres — it's gated purely by the table-level TRUNCATE privilege, which
-- Supabase's default public-schema grants otherwise leave live for
-- `anon`/`authenticated` regardless of RLS. That gap was never closed for
-- the six tables below: `watchlist`, `holdings`, `verdict_state`,
-- `call_log`, `run_heartbeat` (`sql/schema.sql`) and `monitor_alerts`
-- (`sql/phase5_monitoring.sql`). `call_log` is the FR15/FR16 audit trail, so
-- this matters. Additive-only lockdown over already-applied tables — kept as
-- a separate file rather than edited into `sql/schema.sql`/
-- `sql/phase5_monitoring.sql`, which document the original CREATE TABLE
-- statements, following the same convention as
-- `sql/kill_switch_portal_grant.sql`'s TRUNCATE-grant closure over
-- `sql/kill_switch.sql`'s tables.
--
-- Per-table reasoning below is NOT a uniform copy-paste across all six —
-- `watchlist` and `holdings` each carry a live, is_admin()-gated write
-- policy from `sql/admin_portal_rls.sql` (INC-5, FR28/FR29) that needs its
-- `authenticated` INSERT/UPDATE/DELETE base grant preserved; `call_log`,
-- `verdict_state`, `run_heartbeat`, and `monitor_alerts` have no
-- anon/authenticated write policy at all, so all four DML+TRUNCATE verbs are
-- the gap on those.
--
-- NOTE on docs/runbook.md's RLS posture section (~line 364-372, REV-035,
-- 2026-07-28): it characterizes `holdings` as "RLS enabled with zero
-- policies — no anon/authenticated access at all". That was accurate when
-- written, but is now stale — `sql/admin_portal_rls.sql` (INC-5, applied and
-- live per `docs/design/increment-plan.md`'s INC-5 entry) added
-- `admin_write_holdings`, an authenticated-role, is_admin()-gated `for all`
-- policy, and `sql/schema.sql:74-75`'s own comment already documents this
-- ("INC-5 ... is this table's first policy"). Reviewer's REV-099 finding
-- (`docs/review-log.md`) and its suggested REVOKE snippet inherited this
-- same stale "zero policies" premise for `holdings` and would have revoked
-- `authenticated`'s INSERT/UPDATE/DELETE on it — breaking FR29 (portal
-- holdings CRUD) had it been applied as-is. This file revokes only TRUNCATE
-- from `authenticated` on `holdings` (and `watchlist`, same reasoning) for
-- that reason; `docs/runbook.md`'s RLS posture section should be refreshed
-- by its owner (release) to reflect the INC-5 policy addition.
--
-- NOT APPLIED. dev has no Supabase MCP/tool access this session — orchestrator
-- applies this against the live project after handoff, same process as
-- sql/admin_portal_rls.sql / sql/admin_portal_tunables.sql / sql/kill_switch_portal_grant.sql.
-- =====================================================================

-- --- watchlist (FR28): anon_read_watchlist (anon+authenticated SELECT) and
-- admin_write_watchlist (authenticated, is_admin()-gated, `for all`) both stay
-- intact. `anon` has no write policy at all, so its INSERT/UPDATE/DELETE are
-- already RLS-denied but revoked here too for defense-in-depth (same
-- belt-and-suspenders posture as admin_allowlist's REV-081 fix); TRUNCATE is
-- the actual, previously-open gap for both roles.
revoke insert, update, delete, truncate on public.watchlist from public, anon;
revoke truncate on public.watchlist from authenticated;

-- --- holdings (FR29): admin_write_holdings (authenticated, is_admin()-gated,
-- `for all`) stays intact — authenticated keeps its SELECT/INSERT/UPDATE/DELETE
-- base grant. `anon` has zero policies on this table, so all four verbs are
-- revoked from it; TRUNCATE is the actual gap for authenticated.
revoke insert, update, delete, truncate on public.holdings from public, anon;
revoke truncate on public.holdings from authenticated;

-- --- call_log (FR15/FR16 audit trail): anon_read_call_log (anon+authenticated
-- SELECT) stays intact. No write policy exists for either role on this table
-- at all — writes happen only via the secret-key workflows (service role,
-- unaffected by this REVOKE) — so all four DML+TRUNCATE verbs are the gap for
-- both anon and authenticated.
revoke insert, update, delete, truncate on public.call_log from public, anon, authenticated;

-- --- verdict_state, run_heartbeat, monitor_alerts: zero anon/authenticated
-- policies on any of the three (internal change-detection state, per-workflow
-- heartbeat, and monitor-dedup state respectively — all read/written only by
-- the secret-key workflows or a SECURITY DEFINER function running as table
-- owner). All four verbs are the gap on all three, same reasoning
-- admin_allowlist's fix used.
revoke insert, update, delete, truncate on public.verdict_state, public.run_heartbeat, public.monitor_alerts
  from public, anon, authenticated;
