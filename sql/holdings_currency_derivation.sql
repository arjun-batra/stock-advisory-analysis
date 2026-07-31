-- =====================================================================
-- Holdings currency derivation (FR11/FR29 sharpened, Decision #35) — INC-10
-- =====================================================================
-- Design: docs/design/admin-portal.md §16.3 ("FIX ROUND (DEEP-006, INC-10)"), exact function/trigger
-- block copied below. Depends on sql/schema.sql's existing `holdings.ticker -> watchlist(ticker)` FK
-- (already live) — this file adds one new function + one new trigger on top of it; it does NOT
-- redefine `holdings`, `watchlist`, or sql/admin_portal_rls.sql's `admin_write_holdings` policy.
--
-- DEEP-006: `holdings.currency` was a free-choice portal field (defaulting to "USD" for every market)
-- never reconciled against the held ticker's own `watchlist.market`, even though the FK makes the
-- market known at write time — e.g. a .TO position entered at its natural USD default produced a wrong
-- unrealized P&L fed to the AI as fact (FR11) and rendered on the detail page. Fix: derive currency from
-- `watchlist.market` unconditionally, for every write path (portal, direct SQL, any future caller
-- alike) — not just the one UI that exists today.
--
-- Existing-row note (there are none live today, non-functional-ops.md §4.7 calls the position block
-- "dormant"): this is a BEFORE INSERT OR UPDATE trigger — it fires only on a write. A pre-existing row
-- that is never subsequently written to keeps whatever `currency` it already has; this migration does
-- NOT backfill/UPDATE existing rows (a data change, not a schema change, and out of scope for a
-- code-review-time SQL file per this round's live-application caution). Any future UPDATE to an
-- existing row — even one that only touches `shares`/`cost_basis` — re-derives and overwrites
-- `currency` from `watchlist.market` as a side effect, since the trigger fires on the row regardless of
-- which columns changed; this is intentional (self-healing on next write) but not automatic/immediate
-- for a row nobody touches.
--
-- APPLIED AND LIVE (2026-07-30, applied and confirmed directly against production, project
-- ikghqdtlbwifwnooytmm, Postgres 17.6.1): trigger present and enabled. This file's header previously
-- read "Not applied live by dev" (REV-125) — stale once release applied it; the SQL below went live
-- and was simply never updated afterward.

create or replace function public._derive_holdings_currency() returns trigger
language plpgsql security definer set search_path = '' as $$
declare v_market text; v_currency text;
begin
  select market into v_market from public.watchlist where ticker = new.ticker;
  if v_market is null then
    raise exception 'holdings.ticker % has no matching watchlist row', new.ticker;
  end if;
  v_currency := case v_market when 'US' then 'USD' when 'TSX' then 'CAD' when 'NSE' then 'INR' end;
  if v_currency is null then
    raise exception 'watchlist.market % for ticker % has no known currency mapping', v_market, new.ticker;
  end if;
  new.currency := v_currency;
  return new;
end; $$;

-- BUG-008 fix: `create trigger` alone is not re-runnable (errors "already exists" on a second
-- apply). Fixed with `create or replace trigger` (PG14+) rather than a drop-then-recreate pair,
-- same rationale as sql/tunables_validate_trigger.sql's identical fix: qa's repro confirmed
-- Postgres 16 accepts it, this project's local reference Postgres is 16, and a single atomic
-- statement avoids any window where `public.holdings` writes could land with the trigger absent.
-- Kept consistent with the tunables file rather than mixing mechanisms across the two.
create or replace trigger holdings_derive_currency
  before insert or update on public.holdings
  for each row execute function public._derive_holdings_currency();
