-- =====================================================================
-- Kill-switch mid-run-abort classification (FR35, Decision #38) — INC-12
-- =====================================================================
-- Design: docs/design/operational-controls.md §13.6.5. Data model copied verbatim from that section.
-- Depends on nothing else in sql/ — this is a new, standalone, append-only table. It does NOT redefine
-- kill_switch_state or kill_switch_audit (sql/kill_switch.sql, already live).
--
-- FR35's causal-tie requirement (§13.6.3): this table is written ONLY from `scripts/state.py`'s
-- `write_kill_switch_abort()`, called ONLY inside the `except state.KillSwitchAbort` branch each entry
-- point's `main()` adds (run_hourly.py/run_discovery.py) — a direct, synchronous consequence of a
-- checkpoint's own `is_paused()` call returning true. No other code path in the repo ever inserts into
-- this table; that exclusivity is what makes a row's existence proof of a deliberate pause rather than an
-- inference from a symptom a genuine crash could also produce.
--
-- Idempotency (per this round's live-application caution, same bar `sql/tunables_validate_trigger.sql`/
-- `sql/holdings_currency_derivation.sql` were held to after BUG-008): `create table if not exists` makes
-- the CREATE itself safely re-runnable (no trigger in this file, so BUG-008's `create or replace trigger`
-- concern — PG14+ syntax — does not apply here at all); `alter table ... enable/force row level security`
-- and `revoke` are idempotent by nature (re-running either is a silent no-op, not an error) on every
-- Postgres version this project targets. Verified by applying this file twice to a local Postgres 16
-- scratch database and confirming the second apply is clean (see docs/handoff.md's INC-12 entry).
--
-- Not applied live by dev — release/INC-11-style live application applies this against the live project
-- (per the orchestrator's explicit instruction: do not apply to the live Supabase project this session).
-- The live project's Postgres major version has not yet been confirmed; nothing in this file requires
-- PG14+ (no trigger, no `create or replace trigger`), so it should apply cleanly regardless of that
-- outcome.

create table if not exists public.kill_switch_abort_log (   -- append-only, never updated/deleted
  id                    uuid primary key default gen_random_uuid(),
  workflow              text not null,             -- 'hourly-watchlist' | 'daily-discovery' | 'daily-discovery-in'
  checkpoint            text not null check (checkpoint in ('ai_call', 'push')),
  aborted_at            timestamptz not null default now(),
  real_rows_this_cycle  integer not null default 0  -- informational only (§13.6.3); NOT a gating condition
);

alter table public.kill_switch_abort_log enable row level security;
alter table public.kill_switch_abort_log force row level security;
revoke insert, update, delete, truncate on public.kill_switch_abort_log from public, anon, authenticated;
-- Same two-layer deny-all posture as kill_switch_audit (sql/kill_switch.sql, REV-033) and
-- admin_allowlist (sql/admin_portal_rls.sql, REV-081) — the REVOKE blocks anon/authenticated regardless of
-- any policy added later by mistake; RLS+FORCE with zero policies denies every role except one with
-- BYPASSRLS (Supabase's `postgres` role, and therefore the SUPABASE_SECRET_KEY service connection every
-- script already authenticates with) — no new grant, policy, or secret needed to write this table, per
-- Decision #37's own text. REV-117 fix (Pass 28, docs/review-log.md): the REVOKE must name `truncate`
-- explicitly — RLS never governs TRUNCATE in Postgres (it's gated purely by the table privilege, which
-- Supabase's default public-schema grants leave live for anon/authenticated), the same gap class already
-- closed for admin_allowlist (REV-081), tunables (REV-086), kill_switch_state/kill_switch_audit
-- (kill_switch_portal_grant.sql), and six more tables (schema_truncate_grant_closure.sql, REV-099) — this
-- table has no legitimate write path at all, same as admin_allowlist, so it gets the identical four-verb
-- shape. No SELECT policy for anon/authenticated is added by this increment — nothing reads this table
-- yet; a future admin-portal observability view would add one additively, the same pattern INC-7 used for
-- kill_switch_state's first SELECT policy, not a redesign.

-- `checkpoint`'s two values match `state.KillSwitchAbort.checkpoint`'s two values exactly ('ai_call',
-- 'push') — checkpoint 1 (main() entry) and checkpoint 4 (publish_prices.py's commit) never write this
-- table (§13.6.2 — both are bare, side-effect-free early returns), so no 'entry'/'commit' value is needed.
