-- INC-5: admin portal foundation — admin_allowlist, is_admin(), watchlist/holdings write policies.
-- Design: docs/design/admin-portal.md §16.2-§16.3. Exact SQL copied from §16.2's block per the
-- increment-plan brief (REV-033 fix — admin_allowlist gets RLS enabled but ZERO policies).
--
-- is_admin()'s signature (returns boolean, no arguments, SECURITY DEFINER) is a hard, literal
-- dependency for INC-6's tunables write policy (docs/design/increment-plan.md "### INC-5" note) —
-- do not change this signature once INC-6 is built against it.

-- --- admin_allowlist --------------------------------------------------------
create table public.admin_allowlist (
  email text primary key
);
-- Seeded once, manually, with Arjun's Google account email (an ops step at INC-5
-- rollout — the email itself isn't a secret, but it's not a literal baked into
-- migration SQL either; insert it via the SQL editor at deploy time).
alter table public.admin_allowlist enable row level security;
-- REV-033 fix: no policy is created for this table. With RLS enabled and zero
-- policies, anon/authenticated get zero rows via PostgREST — correct, since
-- nothing outside this table's own migration/ops-seed step and is_admin()
-- (below, a SECURITY DEFINER function that reads it as the table owner,
-- exempt from RLS the same way every other SECURITY DEFINER function in this
-- codebase already is) should ever read or write it. Without this, Supabase's
-- default public-schema grants would let ANY signed-in Google account (or
-- even anon) read the allowlist and, worse, INSERT their own email into it —
-- which would make them "the admin" and defeat is_admin() for every RLS
-- policy in INC-5/6/7 at once, since it is their single source of truth.

-- --- is_admin() --------------------------------------------------------------
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(auth.jwt() ->> 'email', '') in (select email from public.admin_allowlist);
$$;

-- --- watchlist / holdings write policies (FR28, FR29) ------------------------
-- watchlist keeps its existing anon-SELECT policy from sql/schema.sql, untouched
-- — this is an additional authenticated-role policy, not a replacement.
create policy "admin_write_watchlist" on public.watchlist
  for all to authenticated
  using (public.is_admin())
  with check (public.is_admin());

-- holdings currently has RLS enabled with no policies at all (zero
-- anon/authenticated access) — this is the first policy it gets.
create policy "admin_write_holdings" on public.holdings
  for all to authenticated
  using (public.is_admin())
  with check (public.is_admin());
