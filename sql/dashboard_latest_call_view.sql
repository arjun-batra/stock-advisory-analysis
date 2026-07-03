-- =====================================================================
-- Dashboard read 2 — latest_call_per_ticker view (SD §13)
-- =====================================================================
-- 2026-07-03 review, gap 3 (applied live via Supabase migration
-- latest_call_per_ticker_view; mirrored here for reproducibility).
--
-- WHY: the dashboard previously fetched the newest 1000 FULL call_log rows
-- (select=*) on every refresh tick and computed latest-per-ticker client-side.
-- That dragged data_snapshot.raw_model_response — the whole batch model reply,
-- replicated onto every row of a run (SD §4.4a) — at multi-MB per refresh
-- against the Supabase free-tier egress budget (NFR1). It also had a
-- correctness edge: after a long market closure a quiet ticker's newest row
-- could age out of the fixed 1000-row window, silently dropping its last-run
-- block and breaking FR21's "columns persist once >=1 check exists."
--
-- This view does DISTINCT ON server-side and exposes ONLY the columns the
-- dashboard renders (price and parse_status are extracted from data_snapshot;
-- raw_model_response, tokens, headlines etc. never leave the database).
--
-- SECURITY: `security_invoker = true` — the view runs as the CALLER, so the
-- publishable (anon) key is still governed by call_log's own RLS SELECT
-- policy. Same exposure as querying call_log directly; no definer bypass.
create or replace view public.latest_call_per_ticker
with (security_invoker = true) as
select distinct on (ticker)
  id,
  ticker,
  verdict,
  rationale,
  "timestamp",
  label,
  alerted,
  data_snapshot->>'parse_status'                as parse_status,
  nullif(data_snapshot->>'price', '')::float8   as price
from public.call_log
order by ticker, "timestamp" desc;

comment on view public.latest_call_per_ticker is
  'Most recent call_log row per ticker (any alerted value), slim columns only — dashboard read 2 (SD §13). security_invoker: call_log RLS applies to the caller.';

grant select on public.latest_call_per_ticker to anon, authenticated;
