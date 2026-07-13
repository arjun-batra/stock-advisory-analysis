-- =====================================================================
-- NSE shadow verdict pilot — call_log_shadow_nse table
-- =====================================================================
-- Parallel, NON-PRODUCTION shadow verdict track for the NSE watchlist
-- (position-aware prompt variant). This table is a full mirror of
-- public.call_log_shadow (§13/§16) so the SAME wallet-sim recursive-CTE walk
-- runs unchanged against call_log_shadow_nse, plus the same two shadow-only
-- columns. Fully independent of call_log_shadow (US/CA): separate table, no
-- shared write surface, own kill switch (SHADOW_NSE_ENABLED) — see design §16,
-- load-bearing #11.
--
-- INTERNAL REVIEW ONLY: like call_log_shadow, this table gets NO anon SELECT
-- policy and NO grants to anon/authenticated. RLS is enabled with no permissive
-- policy, so the publishable (anon) key sees nothing; only the server secret
-- key (which bypasses RLS) writes/reads it, and the Supabase SQL editor /
-- wallet-sim harness read it directly. There is deliberately no read path into
-- the dashboard, the GitHub Pages output, or ntfy for this pilot phase.
--
-- Apply via Supabase apply_migration; mirrored here for reproducibility.

create table if not exists public.call_log_shadow_nse (
  -- --- mirror of public.call_log / public.call_log_shadow (same columns, types, defaults, checks) ---
  id            uuid primary key default gen_random_uuid(),
  ticker        text not null,
  verdict       text not null check (verdict = any (array['Buy'::text, 'Sell'::text, 'Hold'::text])),
  rationale     text,
  "timestamp"   timestamptz not null default now(),
  label         text not null check (label = any (array['watchlist'::text, 'new-candidate'::text])),
  alert_type    text check (alert_type = 'change'::text or alert_type is null),
  -- Shadow never alerts. Column kept for structural parity with call_log so the
  -- wallet-sim walk is identical; always false on this track.
  alerted       boolean not null default false,
  data_snapshot jsonb,

  -- --- shadow-only additions ---
  -- Which prompt variant produced this row. Lets future variants coexist in one
  -- table with no further migration; the pilot writes 'position_aware_v1'.
  prompt_variant text not null default 'position_aware_v1',
  -- What the shadow track believed its position was GOING INTO this call
  -- (holding/flat + entry price + entry date for THIS ticker), so we can audit
  -- the exact context the model was given, not just what it decided. Derived
  -- solely from this table's own prior rows via the wallet-walk, never from
  -- real call_log, and never from call_log_shadow (US/CA).
  shadow_position_state jsonb
);

-- Same access pattern as call_log / call_log_shadow (latest-per-ticker, and by label/time).
create index if not exists idx_call_log_shadow_nse_ticker_ts
  on public.call_log_shadow_nse using btree (ticker, "timestamp" desc);
create index if not exists idx_call_log_shadow_nse_label_ts
  on public.call_log_shadow_nse using btree (label, "timestamp" desc);

-- RLS on, but NO policy and NO grant to anon/authenticated: internal-only.
alter table public.call_log_shadow_nse enable row level security;

comment on table public.call_log_shadow_nse is
  'NSE shadow verdict pilot (non-production). Mirrors call_log_shadow so the wallet-sim '
  'walk runs unchanged; adds prompt_variant + shadow_position_state. Internal review '
  'only — RLS on with no anon policy/grant; no dashboard/Pages/ntfy read path. '
  'Fully independent of call_log_shadow (US/CA track) — separate table, own kill switch.';
comment on column public.call_log_shadow_nse.prompt_variant is
  'Prompt variant that produced this row (pilot: position_aware_v1). Lets variants coexist.';
comment on column public.call_log_shadow_nse.shadow_position_state is
  'Shadow position for THIS ticker going into the call: {state: holding|flat, entry_price, entry_date}. Derived only from call_log_shadow_nse history.';
