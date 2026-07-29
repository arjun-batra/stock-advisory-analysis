-- =====================================================================
-- Kill-switch portal grant (FR32) — INC-7
-- =====================================================================
-- Design: docs/design/admin-portal.md §16.6 (exact function/grant/policy block, copied verbatim
-- below) + a TRUNCATE-grant closure this increment is the right place to make (see comment below).
-- Depends on sql/kill_switch.sql (INC-3, already live: kill_switch_state, kill_switch_audit,
-- set_kill_switch(boolean, text)) and sql/admin_portal_rls.sql (INC-5, already live: is_admin()).
-- Additive-only over INC-3's objects — does not redefine kill_switch_state/kill_switch_audit.
--
-- NOT APPLIED. dev has no Supabase MCP/tool access this session; orchestrator applies this against
-- the live project after handoff, same process as sql/admin_portal_rls.sql / sql/admin_portal_tunables.sql.

-- --- TRUNCATE-grant closure (same class of gap as REV-081/admin_allowlist, REV-086/tunables) -------
-- RLS never governs TRUNCATE in Postgres — it's gated purely by the TRUNCATE table privilege, which
-- Supabase's default public-schema grants otherwise leave live for anon/authenticated regardless of
-- RLS. sql/kill_switch.sql (INC-3) enabled RLS-with-zero-policies on kill_switch_state (closing
-- SELECT/INSERT/UPDATE/DELETE via PostgREST) and revoked insert/update/delete on kill_switch_audit —
-- but neither REVOKE included truncate, unlike admin_allowlist's and tunables' REVOKEs once this
-- exact gap class was found (REV-081, REV-086). Closed here, at the first increment that touches
-- either table again after those two findings landed.
revoke insert, update, delete, truncate on public.kill_switch_state from public, anon, authenticated;
-- kill_switch_state gets all four verbs revoked: there is no legitimate anon/authenticated write path
-- to this table at all (writes only ever happen through set_kill_switch(), which runs as the table
-- owner and is therefore unaffected by this REVOKE) — same posture as admin_allowlist. The new
-- admin_read_kill_switch SELECT policy below is unaffected; this REVOKE never touches SELECT.

revoke truncate on public.kill_switch_audit from public, anon, authenticated;
-- kill_switch_audit already had insert/update/delete revoked by sql/kill_switch.sql — only the
-- missing truncate verb is added here, not restated, to keep this file's diff scoped to the actual
-- gap (repeating already-revoked verbs would be harmless but redundant). No SELECT/INSERT/UPDATE/
-- DELETE policy exists for this table either (RLS enabled + FORCEd + zero policies, from INC-3) —
-- entries are only ever inserted by set_kill_switch() running as the table owner, so there is no
-- legitimate direct authenticated write path to add a policy for here.

-- --- extend set_kill_switch (INC-3) with admin authorization, INC-7 §16.6, copied verbatim --------
create or replace function public.set_kill_switch(
  p_paused boolean, p_source text default 'sql-direct'
) returns void
language plpgsql security definer set search_path = '' as $$
declare v_actor text := coalesce(auth.jwt() ->> 'email', session_user);
begin
  if auth.uid() is not null and not public.is_admin() then
    raise exception 'not authorized';
  end if;
  update public.kill_switch_state
     set paused = p_paused, updated_at = now(), updated_by = v_actor where id = true;
  insert into public.kill_switch_audit(action, actor, source)
  values (case when p_paused then 'pause' else 'resume' end, v_actor, p_source);
end; $$;
-- auth.uid() is null (no Supabase Auth session — the SQL editor or a service-role connection) still
-- bypasses the admin check entirely, preserving INC-3's original trusted-direct-SQL path unchanged.
-- An authenticated-role caller (the portal) is now required to pass is_admin().

grant execute on function public.set_kill_switch(boolean, text) to authenticated;

create policy "admin_read_kill_switch" on public.kill_switch_state
  for select to authenticated
  using (public.is_admin());
-- Single command (select) — not a comma list — matching the fix already applied to
-- admin_read_tunables/admin_write_tunables after the REV-092-class "CREATE POLICY ... FOR select,
-- update" syntax error was caught on live application in INC-6.
