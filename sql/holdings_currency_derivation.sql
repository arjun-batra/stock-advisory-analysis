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
-- Not applied live by dev — release/INC-11 applies this against the live project per the orchestrator's
-- explicit instruction for this increment (this is new trigger logic on a live table other surfaces
-- already write to; application needs the user's involvement, not a code-review-time apply).

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
-- apply). `create or replace trigger` (PG14+) would be the one-line alternative, but this file is
-- meant to be applied to a live Supabase project whose exact Postgres major version hasn't been
-- confirmed from here — `drop trigger if exists` + `create trigger` is the conservative equivalent
-- and is safe: `holdings_derive_currency` is this file's own new object, not a pre-existing live
-- trigger, so dropping and recreating it changes nothing an external caller could observe.
drop trigger if exists holdings_derive_currency on public.holdings;

create trigger holdings_derive_currency
  before insert or update on public.holdings
  for each row execute function public._derive_holdings_currency();
