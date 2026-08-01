-- INC-15 (FR37, docs/design/admin-portal.md §16.11.5) — the merged Tickers
-- screen's only new backend surface: two SECURITY DEFINER RPCs, nothing else.
--
-- WHY a plain client-side two-step write is not good enough here:
-- holdings.ticker is a foreign key to watchlist.ticker with NO ON DELETE
-- CASCADE (sql/schema.sql — Decision #40 forbids a schema change, so this FK
-- stays exactly as-is). Two structural facts follow: (1) a watch-only->held
-- transition must create `holdings` and flip `watchlist.status` together —
-- a partial failure would leave a ticker in a state FR37 says must never
-- exist (held with no holdings row, or watch-only with an orphaned holdings
-- row); (2) deleting a ticker with an existing holdings row must delete
-- holdings before watchlist, or the FK rejects the second delete outright.
-- The fix is the same pattern already established for set_kill_switch: wrap
-- both writes in one SECURITY DEFINER Postgres function, so partial failure
-- is structurally impossible (a function body is one transaction).
--
-- Both mirror set_kill_switch's exact shape (operational-controls.md §13,
-- admin-portal.md §16.6): SECURITY DEFINER, is_admin()-gated, `grant execute
-- ... to authenticated` only (no anon grant).
--
-- Plain field edits that do not change `status` (e.g. editing market/type on
-- an already-watch-only ticker, or shares/cost_basis on an already-held
-- ticker without flipping status) are NOT routed through these RPCs — they
-- remain direct supabase.from("watchlist").update(...) /
-- .from("holdings").update(...) calls under the existing
-- admin_write_watchlist/admin_write_holdings policies, exactly as today.

create or replace function public.set_ticker_holding_status(
  p_ticker text, p_status text, p_shares numeric default null, p_cost_basis numeric default null
) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then
    raise exception 'not authorized';
  end if;
  if p_status = 'held' then
    if p_shares is null or p_shares <= 0 or p_cost_basis is null or p_cost_basis <= 0 then
      raise exception 'shares and cost_basis must both be > 0 to mark a ticker held';
    end if;
    insert into public.holdings (ticker, shares, cost_basis, currency)
      values (p_ticker, p_shares, p_cost_basis, 'USD') -- currency is overwritten unconditionally by the
                                                        -- existing holdings_derive_currency trigger (§16.3)
    on conflict (ticker) do update set shares = excluded.shares, cost_basis = excluded.cost_basis;
    update public.watchlist set status = 'held' where ticker = p_ticker;
  elsif p_status = 'watch-only' then
    delete from public.holdings where ticker = p_ticker;
    update public.watchlist set status = 'watch-only' where ticker = p_ticker;
  else
    raise exception 'unknown status %', p_status;
  end if;
end; $$;

grant execute on function public.set_ticker_holding_status(text, text, numeric, numeric) to authenticated;

create or replace function public.delete_ticker(p_ticker text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then
    raise exception 'not authorized';
  end if;
  delete from public.holdings where ticker = p_ticker;   -- no-op if none exists
  delete from public.watchlist where ticker = p_ticker;
end; $$;

grant execute on function public.delete_ticker(text) to authenticated;

-- Known pre-existing gap, explicitly out of scope for this increment: editing
-- a held ticker's market (e.g. US->TSX) through the merged form does not
-- re-run holdings_derive_currency (that trigger fires only on writes *to*
-- holdings, not on watchlist.market changing) — this gap pre-dates INC-15 and
-- is not introduced or worsened by it (the separate pre-merge
-- watchlist/holdings screens had the identical gap). Not fixed here.
