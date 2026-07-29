-- INC-6: admin portal tunables editor (FR30) — `tunables` table, key-registry CHECK, server-stamped
-- update trigger, admin_write_tunables RLS policy, 10-row seed.
-- Design: docs/design/admin-portal-tunables.md §16.4 (exact schema/trigger/policy block, REV-044).
-- Depends on INC-5's public.is_admin() (sql/admin_portal_rls.sql) already existing — this policy is a
-- direct, literal caller of it, not a re-implementation.
--
-- Not applied live by dev (no Supabase MCP tool access this session, same constraint as INC-5's
-- sql/admin_portal_rls.sql) — orchestrator applies this against the live project after handoff.

-- --- tunables -----------------------------------------------------------------
create table public.tunables (
  key         text primary key check (key in (           -- REV-044: fixed FR30 key registry — the
    'GEMINI_MODEL', 'GEMINI_MODEL_BACKUP', 'ALERTS_ENABLED',                 -- portal can never widen
    'DISCOVERY_GAINER_PCT', 'DISCOVERY_LOSER_PCT', 'DISCOVERY_VOL_SPIKE',    -- its own reach by
    'DISCOVERY_MIN_MARKET_CAP', 'DISCOVERY_MIN_MARKET_CAP_INR',             -- inserting a row for a
    'DISCOVERY_SHORTLIST_MAX', 'DISCOVERY_PUSH_COOLDOWN_DAYS'                -- key nothing reads
  )),
  value       text not null,               -- stored as text; scripts/config.py casts per key
  description text not null,               -- human-readable purpose (FR30: never a bare input box)
  example     text not null,               -- an example legal value
  updated_at  timestamptz not null default now(),
  updated_by  text
);
alter table public.tunables enable row level security;

-- actor stamped server-side on every write, same "never trust the client's
-- self-reported identity" principle as kill_switch_audit (operational-controls.md §13.3):
create or replace function public._stamp_tunable_update() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  new.updated_at := now();
  new.updated_by := coalesce(auth.jwt() ->> 'email', session_user);
  return new;
end; $$;

create trigger tunables_stamp_update
  before update on public.tunables
  for each row execute function public._stamp_tunable_update();

-- REV-044 fix: `for select, update` only (NOT `for all`) — FR30 needs UPDATE on the ten
-- migration-seeded rows, nothing more. No insert/delete policy exists for any role, including
-- `authenticated` — with RLS enabled, that means insert/delete on this table is denied to everyone
-- except the table owner (the seed insert below, run as owner, is unaffected). The CHECK constraint
-- above is the second half of this fix: even a same-admin UPDATE (the only op this policy allows)
-- cannot rename a row's `key` to something outside the fixed 10.
create policy "admin_write_tunables" on public.tunables
  for select, update to authenticated
  using (public.is_admin())
  with check (public.is_admin());

-- --- seed migration (Decision #27's explicit "no behavior change at cutover" requirement) -----------
-- One row per curated key, at the value/description/example already documented for these keys in
-- requirements.md §10 / scripts/config.py's existing comments.
--
-- ALERTS_ENABLED needs care here: scripts/config.py's own bare literal default for this key is the
-- conservative "false", but the system's actual LIVE default is effectively true on every scheduled
-- run today via the workflow_dispatch input's own YAML default (hourly-watchlist.yml /
-- daily-discovery.yml). Seeding this row as "false" would silently break production alerting the
-- moment the table becomes authoritative. The seed value for ALERTS_ENABLED is therefore "true",
-- matching today's actual live behavior, NOT config.py's bare literal default.
insert into public.tunables (key, value, description, example) values
  ('GEMINI_MODEL', 'gemini-2.5-flash', 'Primary watchlist AI model', 'gemini-2.5-flash'),
  ('GEMINI_MODEL_BACKUP', 'gemini-2.5-flash-lite', 'Fallback model (leave empty to disable the fallback model)', 'gemini-2.5-flash-lite'),
  ('ALERTS_ENABLED', 'true', 'Master switch for real pushes (matches today''s live default; a manual off-hours dry run can still suppress this via workflow_dispatch)', 'true'),
  ('DISCOVERY_GAINER_PCT', '5', 'Mover threshold (%) — gainer side', '5'),
  ('DISCOVERY_LOSER_PCT', '-5', 'Mover threshold (%) — loser side', '-5'),
  ('DISCOVERY_VOL_SPIKE', '2.0', 'Volume-spike signal: multiple of the 3-month average volume', '2.0'),
  ('DISCOVERY_MIN_MARKET_CAP', '2000000000', 'US/CA market-cap floor ($)', '2000000000'),
  ('DISCOVERY_MIN_MARKET_CAP_INR', '50000000000', 'NSE market-cap floor (₹)', '50000000000'),
  ('DISCOVERY_SHORTLIST_MAX', '15', 'Max candidates sent to the AI in the daily discovery batch', '15'),
  ('DISCOVERY_PUSH_COOLDOWN_DAYS', '7', 'Per-candidate re-push cooldown (days)', '7');
