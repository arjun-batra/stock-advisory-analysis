-- =====================================================================
-- Dedup: check_pipeline_health's near-identical ET/IST watchlist branches
-- (reviewer Pass 11, REV-047)
-- =====================================================================
-- WHY: the ET and IST watchlist branches in check_pipeline_health() are
-- ~25 duplicated lines differing only in one message string ("during the
-- NSE session"). Identical threshold (70 min), identical priorities (5 for
-- stale, 3 for degraded), identical cooldowns (6h / 12h), identical recovery
-- text. A future change to the staleness rule (e.g. INC-3's
-- `GREATEST(last_run_at, resume_baseline)` change, which
-- `docs/design/operational-controls.md` §13.4 already says must touch all
-- four checks) must currently be made twice, correctly, in both branches —
-- exactly the kind of duplicated state CLAUDE.md's hardcoding-audit posture
-- exists to catch.
--
-- WHAT: collapses the two branches into one, computing which session (if
-- any) is active first, then evaluating the stale/degraded/ok logic exactly
-- once, parameterized by a `v_session_label` variable used only in the one
-- message string that actually differed.
--
-- This migration is built ON TOP of sql/fix_missing_degraded_checks.sql
-- (REV-042) — the degraded-check additions for discovery-NA/discovery-IN/
-- publish-prices are included below so this file is a complete, correct
-- final state, not a partial diff that would regress REV-042 if applied
-- after it. **Apply this file INSTEAD of fix_missing_degraded_checks.sql**
-- (or after it — either order leaves the same final function body; this
-- file is simply the more complete of the two, in the same
-- `create or replace function` shape).
--
-- NOT APPLIED. dev/release coordinate actual deployment against the live
-- Supabase project separately — this file is a reviewed, ready-to-apply
-- design artifact, not a change already in production.
-- =====================================================================

create or replace function public.check_pipeline_health(p_now timestamptz default now())
returns void
language plpgsql security definer set search_path = '' as $$
declare
  dow int  := extract(isodow from p_now);          -- 1=Mon .. 7=Sun
  t   time := (p_now at time zone 'UTC')::time;
  et  time := (p_now at time zone 'America/New_York')::time;  -- #9/#12: ET-based watchlist window
  ist time := (p_now at time zone 'Asia/Kolkata')::time;      -- Phase 6 D4: NSE/IST watchlist window
  wl_last timestamptz; wl_status text;
  disc_last timestamptz; disc_status text;
  disc_in_last timestamptz; disc_in_status text;
  pp_last timestamptz; pp_status text;
  mins numeric;
  -- REV-047: which watchlist session (if any) is active right now, and its
  -- label — computed once, replacing the old duplicated ET-block/IST-block.
  v_session_active boolean := false;
  v_session_label  text;
begin
  if dow > 5 then
    return;   -- weekends: nothing is scheduled, so nothing to watch
  end if;

  -- ===== WATCHLIST: stale or degraded, during EITHER session + grace =====
  -- REV-047 dedup: was two near-identical branches (ET 10:15-16:00,
  -- IST 10:00-15:30), collapsed into one. Sessions never overlap (verified,
  -- docs/design/data-and-flow.md §6), so at most one of these is ever true.
  if et >= time '10:15' and et <= time '16:00' then
    v_session_active := true;
    v_session_label := 'ET';
  elsif ist >= time '10:00' and ist <= time '15:30' then
    v_session_active := true;
    v_session_label := 'IST';
  end if;

  if v_session_active then
    select last_run_at, status into wl_last, wl_status
      from public.run_heartbeat where workflow_name = 'hourly-watchlist';

    if wl_last is null or p_now - wl_last > interval '70 minutes' then
      mins := extract(epoch from (p_now - coalesce(wl_last, p_now)))/60;
      perform public._raise_monitor(
        'watchlist', 'stale', '⚠️ Watchlist stalled',
        format('No hourly-watchlist run since %s (%s min ago)%s. The pg_cron dispatch, PAT, or workflow may be down.',
               coalesce(to_char(wl_last,'Mon DD HH24:MI UTC'),'never'),
               coalesce(round(mins)::text,'?'),
               case when v_session_label = 'IST' then ' during the NSE session' else '' end),
        5, interval '6 hours');
    elsif wl_status is not null and wl_status <> 'ok' then
      perform public._raise_monitor(
        'watchlist', 'degraded', '⚠️ Watchlist degraded',
        format('Latest hourly-watchlist run status = %s (%s). Some tickers skipped/errored.',
               wl_status, to_char(wl_last,'Mon DD HH24:MI UTC')),
        3, interval '12 hours');
    else
      perform public._clear_monitor('watchlist', '✅ Watchlist recovered',
        format('hourly-watchlist running cleanly again (last run %s).',
               to_char(wl_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;

  -- ===== DISCOVERY (US/TSX): did it run in today's window? (check after 23:00 UTC) =====
  if t >= time '23:00' then
    select last_run_at, status into disc_last, disc_status
      from public.run_heartbeat where workflow_name = 'daily-discovery';

    if disc_last is null or disc_last < date_trunc('day', p_now) + interval '21 hours' then
      perform public._raise_monitor(
        'discovery', 'stale', '⚠️ Discovery did not run',
        format('No daily-discovery run in today''s window (last: %s).',
               coalesce(to_char(disc_last,'Mon DD HH24:MI UTC'),'never')),
        4, interval '6 hours');
    elsif disc_status is not null and disc_status <> 'ok' then   -- REV-042
      perform public._raise_monitor(
        'discovery', 'degraded', '⚠️ Discovery degraded',
        format('Latest daily-discovery run status = %s (%s). Some screens errored or tickers skipped.',
               disc_status, to_char(disc_last,'Mon DD HH24:MI UTC')),
        3, interval '12 hours');
    else
      perform public._clear_monitor('discovery', '✅ Discovery recovered',
        format('daily-discovery ran (last run %s).', to_char(disc_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;

  -- ===== DISCOVERY (NSE, region=in): dispatched 10:00 UTC; check after 11:00 UTC =====
  if t >= time '11:00' then
    select last_run_at, status into disc_in_last, disc_in_status   -- REV-042: status added
      from public.run_heartbeat where workflow_name = 'daily-discovery-in';

    if disc_in_last is null or disc_in_last < date_trunc('day', p_now) + interval '9 hours 30 minutes' then
      perform public._raise_monitor(
        'discovery-in', 'stale', '⚠️ NSE discovery did not run',
        format('No daily-discovery (region=in) run in today''s window (last: %s).',
               coalesce(to_char(disc_in_last,'Mon DD HH24:MI UTC'),'never')),
        4, interval '6 hours');
    elsif disc_in_status is not null and disc_in_status <> 'ok' then   -- REV-042
      perform public._raise_monitor(
        'discovery-in', 'degraded', '⚠️ NSE discovery degraded',
        format('Latest daily-discovery (region=in) run status = %s (%s). Some screens errored or tickers skipped.',
               disc_in_status, to_char(disc_in_last,'Mon DD HH24:MI UTC')),
        3, interval '12 hours');
    else
      perform public._clear_monitor('discovery-in', '✅ NSE discovery recovered',
        format('daily-discovery (region=in) ran (last run %s).',
               to_char(disc_in_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;

  -- ===== PUBLISH-PRICES: dashboard price snapshot stale/degraded during a session =====
  if (et >= time '10:15' and et <= time '16:00')
     or (ist >= time '10:00' and ist <= time '15:30') then
    select last_run_at, status into pp_last, pp_status   -- REV-042: status added
      from public.run_heartbeat where workflow_name = 'publish-prices';

    if pp_last is null or p_now - pp_last > interval '70 minutes' then
      perform public._raise_monitor(
        'publish-prices', 'stale', '⚠️ Dashboard prices stale',
        format('No publish-prices run since %s — pages/prices.json is not refreshing.',
               coalesce(to_char(pp_last,'Mon DD HH24:MI UTC'),'never')),
        3, interval '6 hours');
    elsif pp_status is not null and pp_status <> 'ok' then   -- REV-042
      perform public._raise_monitor(
        'publish-prices', 'degraded', '⚠️ Dashboard prices degraded',
        format('Latest publish-prices run status = %s (%s). Some tickers skipped.',
               pp_status, to_char(pp_last,'Mon DD HH24:MI UTC')),
        3, interval '12 hours');
    else
      perform public._clear_monitor('publish-prices', '✅ Dashboard prices recovered',
        format('publish-prices running again (last run %s).',
               to_char(pp_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;
end; $$;

-- Ownership/execute lockdown is unchanged (already applied live and in
-- sql/phase5_monitoring.sql); `create or replace function` preserves the
-- existing `revoke execute ... from public, anon, authenticated` since
-- REVOKE is not part of the function definition. Not repeated here.
