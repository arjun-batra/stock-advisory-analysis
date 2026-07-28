-- =====================================================================
-- Fix: dead-man monitor never alerts on a DEGRADED discovery/publish-prices
-- run (reviewer Pass 11, REV-042)
-- =====================================================================
-- WHY: only the two watchlist branches (ET and IST) in check_pipeline_health()
-- implement the `status <> 'ok'` degraded check. The discovery branch already
-- SELECTS `disc_status` into a variable and never reads it — a dead read that
-- reads as if the check existed. run_discovery.py deliberately writes
-- `status='partial'` when `screens_errored` (the "quiet day" vs "screener
-- failure" distinction, issue #2's principle applied to discovery), and
-- publish_prices.py writes `status='partial'` when any ticker was skipped —
-- both terminate in a table nobody watches. docs/runbook.md §4 already
-- promises this alert ("Degraded alert: when run_heartbeat.workflow_name=
-- 'daily-discovery' shows status != 'ok'"), so the operator believes coverage
-- exists where it doesn't. NFR2 requires alerting on a run that "completes
-- degraded" without limiting that to the watchlist.
--
-- WHAT: adds an `elsif ... status <> 'ok'` branch to the discovery-NA,
-- discovery-IN, and publish-prices checks, mirroring the existing watchlist
-- branches' pattern (~6 lines each, same _raise_monitor/_clear_monitor
-- shape, same priority/cooldown values used elsewhere in this function).
-- discovery-IN and publish-prices didn't previously select `status` at all;
-- this adds that to their existing `select ... into` calls.
--
-- THIS IS A NEW MIGRATION FILE, NOT AN IN-PLACE EDIT of
-- sql/phase5_monitoring.sql (per this project's established pattern —
-- sql/scheduler_pgcron.sql's own header explains new fixes get new files,
-- reproducibility over rewriting history). `create or replace function`
-- below replaces the live function body wholesale with this corrected
-- version; every other branch is byte-identical to the version currently in
-- sql/phase5_monitoring.sql — only the three additions below (marked
-- `-- REV-042`) are new.
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
  disc_in_last timestamptz; disc_in_status text;   -- REV-042: disc_in_status added (was unread before)
  pp_last timestamptz; pp_status text;              -- REV-042: pp_status added (was unread before)
  mins numeric;
begin
  if dow > 5 then
    return;   -- weekends: nothing is scheduled, so nothing to watch
  end if;

  -- ===== WATCHLIST: stale or degraded, during the ET session + grace =====
  -- (unchanged from sql/phase5_monitoring.sql — already implements the
  -- degraded branch; included here only because create or replace function
  -- takes the whole body.)
  if et >= time '10:15' and et <= time '16:00' then
    select last_run_at, status into wl_last, wl_status
      from public.run_heartbeat where workflow_name = 'hourly-watchlist';

    if wl_last is null or p_now - wl_last > interval '70 minutes' then
      mins := extract(epoch from (p_now - coalesce(wl_last, p_now)))/60;
      perform public._raise_monitor(
        'watchlist', 'stale', '⚠️ Watchlist stalled',
        format('No hourly-watchlist run since %s (%s min ago). The pg_cron dispatch, PAT, or workflow may be down.',
               coalesce(to_char(wl_last,'Mon DD HH24:MI UTC'),'never'),
               coalesce(round(mins)::text,'?')),
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

  -- ===== NSE WATCHLIST: same checks during the IST session (10:00-15:30 IST) =====
  elsif ist >= time '10:00' and ist <= time '15:30' then
    select last_run_at, status into wl_last, wl_status
      from public.run_heartbeat where workflow_name = 'hourly-watchlist';

    if wl_last is null or p_now - wl_last > interval '70 minutes' then
      mins := extract(epoch from (p_now - coalesce(wl_last, p_now)))/60;
      perform public._raise_monitor(
        'watchlist', 'stale', '⚠️ Watchlist stalled',
        format('No hourly-watchlist run since %s (%s min ago) during the NSE session. The pg_cron dispatch, PAT, or workflow may be down.',
               coalesce(to_char(wl_last,'Mon DD HH24:MI UTC'),'never'),
               coalesce(round(mins)::text,'?')),
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
    elsif disc_status is not null and disc_status <> 'ok' then   -- REV-042: was a dead read before this fix
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
    select last_run_at, status into disc_in_last, disc_in_status   -- REV-042: status added (was last_run_at only)
      from public.run_heartbeat where workflow_name = 'daily-discovery-in';

    if disc_in_last is null or disc_in_last < date_trunc('day', p_now) + interval '9 hours 30 minutes' then
      perform public._raise_monitor(
        'discovery-in', 'stale', '⚠️ NSE discovery did not run',
        format('No daily-discovery (region=in) run in today''s window (last: %s).',
               coalesce(to_char(disc_in_last,'Mon DD HH24:MI UTC'),'never')),
        4, interval '6 hours');
    elsif disc_in_status is not null and disc_in_status <> 'ok' then   -- REV-042: new branch
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
    select last_run_at, status into pp_last, pp_status   -- REV-042: status added (was last_run_at only)
      from public.run_heartbeat where workflow_name = 'publish-prices';

    if pp_last is null or p_now - pp_last > interval '70 minutes' then
      perform public._raise_monitor(
        'publish-prices', 'stale', '⚠️ Dashboard prices stale',
        format('No publish-prices run since %s — pages/prices.json is not refreshing.',
               coalesce(to_char(pp_last,'Mon DD HH24:MI UTC'),'never')),
        3, interval '6 hours');
    elsif pp_status is not null and pp_status <> 'ok' then   -- REV-042: new branch
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
