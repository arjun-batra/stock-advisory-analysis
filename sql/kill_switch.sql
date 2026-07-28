-- =====================================================================
-- Kill-switch (FR24, FR25, FR26, NFR2) — INC-3
-- =====================================================================
-- Design: docs/design/operational-controls.md §13. Data model + write path
-- copied verbatim from §13.2/§13.3 (RLS/REVOKE lockdown per reviewer's
-- REV-033 blocker finding, already fixed in the design doc this implements).
--
-- Apply order: this file FIRST, before sql/scheduler_pgcron.sql and
-- sql/phase5_monitoring.sql — dispatch_github_workflow and
-- check_pipeline_health (edited in those two files) both `select ... from
-- public.kill_switch_state`, so applying them before this table exists would
-- hit a runtime error on a live project. This file only adds new tables/a new
-- function; the edits those two files need — the pause check inside
-- dispatch_github_workflow, and the pause-awareness + resume-baseline fix
-- inside check_pipeline_health — are committed as `create or replace
-- function` blocks directly in those files, not here, so each function's
-- full current definition stays in one place.
--
-- NOT APPLIED. dev/release coordinate actual deployment separately (Arjun
-- has deferred applying any SQL changes to the live Supabase project for
-- this change request until "it makes sense").
-- =====================================================================

-- --- kill_switch_state: singleton flag, fast-read on every dispatch/monitor tick ---
create table public.kill_switch_state (
  id         boolean primary key default true,   -- singleton row; CHECK (id) below
  paused     boolean not null default false,
  updated_at timestamptz not null default now(),
  updated_by text                                  -- actor of the last change
);
alter table public.kill_switch_state add constraint kill_switch_state_singleton check (id);
insert into public.kill_switch_state (id, paused) values (true, false);
alter table public.kill_switch_state enable row level security;
-- No policy is created here — REV-033 fix, 2026-07-28. With RLS enabled and
-- zero policies, PostgREST denies anon/authenticated ALL access (Supabase's
-- default public-schema grants to those roles are not enough by themselves;
-- RLS is the actual gate and it was simply never turned on for this table).
-- The table owner (and set_kill_switch()/check_pipeline_health(), both
-- SECURITY DEFINER functions that run as the owner) is exempt from RLS by
-- Postgres default and keeps reading/writing exactly as designed above — no
-- functional change, this closes only the anon/authenticated exposure.
-- INC-7 (admin-portal.md §16.6) adds the first real policy — an
-- `authenticated`+`is_admin()`-gated SELECT — when the portal needs to read
-- the flag; until then this table is fully deny-all for every non-owner role.

-- --- kill_switch_audit: append-only history, FR26 ---------------------------
create table public.kill_switch_audit (            -- append-only, never updated/deleted
  id         uuid primary key default gen_random_uuid(),
  action     text not null check (action in ('pause','resume')),
  actor      text not null,                         -- email (portal, from INC-7) or 'sql-direct'/session_user
  source     text not null default 'sql-direct',     -- 'admin-portal' | 'sql-direct'
  changed_at timestamptz not null default now()
);
alter table public.kill_switch_audit enable row level security;
alter table public.kill_switch_audit force row level security;
revoke insert, update, delete on public.kill_switch_audit from public, anon, authenticated;
-- REV-033 fix, 2026-07-28 (append-only was previously asserted in a comment
-- only, enforced by nothing). Two layers, each independently sufficient:
--   1. The REVOKE above removes the base insert/update/delete grant from
--      every non-owner role — this alone blocks anon/authenticated regardless
--      of any RLS policy that might be added later by mistake.
--   2. `enable` + `force` row level security with ZERO policies denies
--      SELECT/INSERT/UPDATE/DELETE to every role, including the table owner,
--      UNLESS that role has the `BYPASSRLS` attribute — which Supabase's
--      built-in `postgres` role has (used by the SQL editor, migrations, and
--      every SECURITY DEFINER function's owner in this codebase), so
--      `set_kill_switch()`'s insert and Arjun's own ad-hoc `select * from
--      kill_switch_audit` in the SQL editor are both unaffected. FORCE exists
--      here specifically so a future non-bypassrls context (a different
--      owner, a self-hosted Postgres fork, a stricter role assignment) is
--      still safe by construction, not by convention. **No policy grants
--      anon or authenticated any access to this table at all** — this is the
--      one new table in the whole change request with zero live write path
--      other than through `set_kill_switch()`.
-- Dev must confirm at apply time (INC-3 AC4: "Each set_kill_switch call
-- inserts exactly one kill_switch_audit row ... verified across ≥2 toggles")
-- that the insert still succeeds post-RLS — if the live project's `postgres`
-- role does NOT carry BYPASSRLS (unexpected, but worth verifying empirically
-- rather than assuming), an explicit `for insert to public with check (true)`
-- policy would be needed in addition to the REVOKE (the REVOKE alone still
-- blocks anon/authenticated in that case; only the function's own insert
-- would need the extra policy).

-- `kill_switch_state` is the fast-read flag `dispatch_github_workflow` and
-- `check_pipeline_health` check on every invocation; `kill_switch_audit` is
-- FR26's append-only history. Both are written ONLY through `set_kill_switch()`
-- below — never directly — so the audit trail can't be bypassed by a stray
-- UPDATE. Neither table grants the anon/authenticated roles any access as of
-- INC-3 (REV-033) — the only callers are the two SECURITY DEFINER functions
-- (this one, and dispatch_github_workflow/check_pipeline_health which only
-- read kill_switch_state) and a trusted direct-SQL/service-role connection.

-- --- set_kill_switch: the only write path, FR26 -----------------------------
create or replace function public.set_kill_switch(
  p_paused boolean,
  p_source text default 'sql-direct'
) returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_actor text := coalesce(auth.jwt() ->> 'email', session_user);
begin
  update public.kill_switch_state
     set paused = p_paused, updated_at = now(), updated_by = v_actor
   where id = true;

  insert into public.kill_switch_audit(action, actor, source)
  values (case when p_paused then 'pause' else 'resume' end, v_actor, p_source);
end; $$;

revoke execute on function public.set_kill_switch(boolean, text) from public, anon, authenticated;

-- At INC-3 time this function is callable ONLY via the SQL editor / service-role
-- connection (Arjun directly) — same lockdown posture as every other SECURITY
-- DEFINER function in this codebase (dispatch_github_workflow, send_ntfy, etc.,
-- all revoke from public, anon, authenticated). There is no Supabase Auth user
-- population yet (the portal doesn't exist until INC-5), so auth.jwt() is
-- always null at this point and actor resolves to session_user ('sql-direct'
-- toggles: `select set_kill_switch(true);` / `select set_kill_switch(false);`).
-- FR24-FR26 are fully satisfiable with zero portal dependency — this is what
-- makes the increment self-contained, per the approved build order.
--
-- Forward reference (INC-7 extends this, doesn't replace it): when the admin
-- portal's kill-switch UI ships, INC-7 (admin-portal.md §16.5) adds an
-- internal is_admin() authorization check inside this same function and
-- `grant execute ... to authenticated`, so the function gains a second,
-- admin-gated caller (the portal, source='admin-portal', actor = the
-- signed-in Google email) without changing its contract. No redesign needed
-- at that point — additive only.
