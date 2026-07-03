-- =====================================================================
-- Phase 5 — Reliability hardening: pipeline dead-man's switch
-- =====================================================================
-- GitHub emails only when a run EXECUTES and FAILS. It is silent when a run
-- never triggers (dropped cron, expired PAT, disabled job). run_heartbeat is
-- queryable but passive. This adds an active watcher: a pg_cron job that checks
-- whether the watchlist and discovery pipelines are still running and pushes an
-- ntfy alert when they go stale or degrade. Same in-stack pattern as the
-- pg_cron -> workflow_dispatch trigger (Phase 5 of the build plan).
--
-- Lives in Supabase (applied via the Supabase migration
-- phase5_pipeline_monitoring); committed here for version control / reproducibility.
-- Requires Vault secret 'ntfy_topic' (the ntfy topic to publish alerts to).
-- =====================================================================

-- --- alert state (dedup / state-machine) -----------------------------
create table if not exists public.monitor_alerts (
  check_name      text primary key,
  last_state      text not null default 'ok',   -- 'ok' | 'stale' | 'degraded'
  last_alerted_at timestamptz,
  updated_at      timestamptz not null default now()
);

-- --- ntfy publisher (JSON-to-root) -----------------------------------
create or replace function public.send_ntfy(
  p_title text, p_msg text, p_priority int default 4, p_tags text[] default array['warning']
) returns bigint
language plpgsql security definer set search_path = '' as $$
declare topic text; req_id bigint;
begin
  select decrypted_secret into topic from vault.decrypted_secrets where name = 'ntfy_topic' limit 1;
  if topic is null then
    raise warning 'send_ntfy: secret ntfy_topic not found in vault; skipping send';
    return null;
  end if;
  select net.http_post(
    url := 'https://ntfy.sh/',
    body := jsonb_build_object(
      'topic', topic, 'title', p_title, 'message', p_msg,
      'priority', p_priority, 'tags', to_jsonb(p_tags)
    )
  ) into req_id;
  return req_id;
end; $$;

-- --- raise: alert on entering/worsening a bad state, re-alert per cooldown ---
create or replace function public._raise_monitor(
  p_check text, p_state text, p_title text, p_msg text,
  p_priority int, p_cooldown interval
) returns void
language plpgsql security definer set search_path = '' as $$
declare prev public.monitor_alerts%rowtype;
begin
  select * into prev from public.monitor_alerts where check_name = p_check;
  if prev.check_name is null then
    insert into public.monitor_alerts(check_name, last_state, last_alerted_at, updated_at)
    values (p_check, p_state, now(), now());
    perform public.send_ntfy(p_title, p_msg, p_priority, array['rotating_light']);
    return;
  end if;
  -- send on any state change, or once per cooldown while still bad
  if prev.last_state is distinct from p_state
     or prev.last_alerted_at is null
     or now() - prev.last_alerted_at > p_cooldown then
    perform public.send_ntfy(p_title, p_msg, p_priority, array['rotating_light']);
    update public.monitor_alerts
       set last_state = p_state, last_alerted_at = now(), updated_at = now()
     where check_name = p_check;
  else
    update public.monitor_alerts set last_state = p_state, updated_at = now()
     where check_name = p_check;
  end if;
end; $$;

-- --- clear: one recovery notice when a bad state returns to ok --------
create or replace function public._clear_monitor(
  p_check text, p_title text, p_msg text
) returns void
language plpgsql security definer set search_path = '' as $$
declare prev public.monitor_alerts%rowtype;
begin
  select * into prev from public.monitor_alerts where check_name = p_check;
  if prev.check_name is not null and prev.last_state <> 'ok' then
    if p_title is not null then
      perform public.send_ntfy(p_title, p_msg, 3, array['white_check_mark']);
    end if;
    update public.monitor_alerts set last_state = 'ok', updated_at = now()
     where check_name = p_check;
  end if;
end; $$;

-- --- the monitor (p_now injectable for testing) ----------------------
-- 2026-07-03 review (gap 2 + improvement 1, applied via Supabase migration
-- monitor_nse_discovery_and_publish_prices): adds (a) an NSE-discovery check —
-- run_discovery now writes a per-region 'daily-discovery-in' heartbeat, watched
-- after 11:00 UTC, so a dead region=in dispatch alerts instead of hiding behind
-- the shared key the NA run overwrote — and (b) a publish-prices staleness
-- check during either session, so a dead prices pipeline pushes an alert
-- instead of only aging the dashboard's "prices updated" line.
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
  disc_in_last timestamptz;
  pp_last timestamptz;
  mins numeric;
begin
  if dow > 5 then
    return;   -- weekends: nothing is scheduled, so nothing to watch
  end if;

  -- ===== WATCHLIST: stale or degraded, during the ET session + grace =====
  -- #9/#12 fix: gate on real Eastern time, not a fixed UTC window. The old
  -- 14:30-21:30 UTC window ran ~90 min past the ET close in EDT, firing a false
  -- "stalled" alert at 20:50 UTC (post-close no-op runs don't write a heartbeat).
  -- ET 10:15 = grace after the 09:30 open (lets the first run land); 16:00 = close.
  -- (p_now at time zone 'America/New_York') is DST-aware in both EST and EDT.
  -- Stale if newest heartbeat > 70 min old (~2 missed */30 cycles, allows a slow run).
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
  -- Phase 6 D4. ET and IST sessions never overlap, so this shares the 'watchlist'
  -- monitor key + the hourly-watchlist heartbeat; only one window is active at a
  -- time. IST 10:00 = grace after the 09:15 open; 15:30 = close (fixed offset).
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
    else
      perform public._clear_monitor('discovery', '✅ Discovery recovered',
        format('daily-discovery ran (last run %s).', to_char(disc_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;

  -- ===== DISCOVERY (NSE, region=in): dispatched 10:00 UTC; check after 11:00 UTC =====
  -- 2026-07-03 review gap 2 (NFR2): the two regional runs previously shared one
  -- 'daily-discovery' heartbeat key, so only the 22:00 UTC NA run was ever
  -- validated — a silently-dead NSE dispatch never alerted, and the NA run
  -- overwrote its heartbeat evidence the same day. Expect today's region=in run
  -- after 09:30 UTC (the dispatch fires at 10:00).
  if t >= time '11:00' then
    select last_run_at into disc_in_last
      from public.run_heartbeat where workflow_name = 'daily-discovery-in';

    if disc_in_last is null or disc_in_last < date_trunc('day', p_now) + interval '9 hours 30 minutes' then
      perform public._raise_monitor(
        'discovery-in', 'stale', '⚠️ NSE discovery did not run',
        format('No daily-discovery (region=in) run in today''s window (last: %s).',
               coalesce(to_char(disc_in_last,'Mon DD HH24:MI UTC'),'never')),
        4, interval '6 hours');
    else
      perform public._clear_monitor('discovery-in', '✅ NSE discovery recovered',
        format('daily-discovery (region=in) ran (last run %s).',
               to_char(disc_in_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;

  -- ===== PUBLISH-PRICES: dashboard price snapshot stale during a session =====
  -- 2026-07-03 review improvement 1 (NFR2): publish_prices.py now writes a
  -- 'publish-prices' heartbeat. It runs */30 across both sessions; older than
  -- 70 min (~2 missed ticks) while a session is open means pages/prices.json is
  -- not refreshing — previously that failed silently (the dashboard just showed
  -- an ever-growing "prices updated Nh ago").
  if (et >= time '10:15' and et <= time '16:00')
     or (ist >= time '10:00' and ist <= time '15:30') then
    select last_run_at into pp_last
      from public.run_heartbeat where workflow_name = 'publish-prices';

    if pp_last is null or p_now - pp_last > interval '70 minutes' then
      perform public._raise_monitor(
        'publish-prices', 'stale', '⚠️ Dashboard prices stale',
        format('No publish-prices run since %s — pages/prices.json is not refreshing.',
               coalesce(to_char(pp_last,'Mon DD HH24:MI UTC'),'never')),
        3, interval '6 hours');
    else
      perform public._clear_monitor('publish-prices', '✅ Dashboard prices recovered',
        format('publish-prices running again (last run %s).',
               to_char(pp_last,'Mon DD HH24:MI UTC')));
    end if;
  end if;
end; $$;

-- --- lock down execute (these read Vault + hit the network) -----------
revoke execute on function public.send_ntfy(text,text,int,text[]) from public, anon, authenticated;
revoke execute on function public._raise_monitor(text,text,text,text,int,interval) from public, anon, authenticated;
revoke execute on function public._clear_monitor(text,text,text) from public, anon, authenticated;
revoke execute on function public.check_pipeline_health(timestamptz) from public, anon, authenticated;

-- =====================================================================
-- #9/#12 — DST-correct ET-aware dispatch gate
-- =====================================================================
-- The watchlist-dispatch cron fires every 30 min over a wide */30 13-21 UTC
-- window. That window is a DST *superset* of the ET trading day; on its own it
-- dispatches post-close no-op runs in EDT (#9). This gate sits between the cron
-- and dispatch_github_workflow: it only dispatches during the real ET session
-- (09:30-16:00 ET, weekdays). Postgres handles DST via 'America/New_York', so it
-- self-corrects across the EST/EDT boundary with no hardcoded UTC offsets.
-- The wide cron stays as the superset; this trims it to the live session.
-- (Python is_market_open() remains as execution-time defense-in-depth.)
-- No per-exchange holiday calendar (accepted risk; closed-day tickers fall
-- through to skip-with-log downstream).
create or replace function public.dispatch_watchlist_if_open()
returns void
language plpgsql security definer set search_path = '' as $$
declare
  et_now timestamp := (now() at time zone 'America/New_York');
  dow int := extract(isodow from et_now);
  t   time := et_now::time;
begin
  -- Weekday + ET regular session only. Upper bound is 16:05, not the 16:00 exact
  -- close, to absorb pg_cron sub-second execution jitter: at the exact-close */30
  -- slot, now() lands a few hundred ms past 16:00 and an exact `<= '16:00'` test
  -- silently dropped the final dispatch of every trading day. 16:05 catches that
  -- slot; the next slot (16:30) still falls outside and stays excluded, so no
  -- post-close no-op is introduced. (Migration fix_market_close_boundary_jitter.)
  if dow > 5 then
    return;
  end if;
  if t >= time '09:30' and t <= time '16:05' then
    perform public.dispatch_github_workflow('hourly-watchlist.yml');
  end if;
end; $$;

revoke execute on function public.dispatch_watchlist_if_open() from public, anon, authenticated;

-- Re-point the watchlist-dispatch cron at the gate (was a direct
-- dispatch_github_workflow call). Schedule unchanged — still the DST superset.
select cron.alter_job(
  (select jobid from cron.job where jobname = 'watchlist-dispatch'),
  command => 'select public.dispatch_watchlist_if_open();'
);

-- --- schedule: :20 and :50 past the hour, weekdays -------------------
-- Covers BOTH sessions' watchlist windows (IST 04-10 UTC + ET 14-23 UTC), the
-- post-22:00 US/TSX discovery check, and the post-11:00 NSE discovery check.
-- Phase 6 D4 widened this from '14-23' to add '4-10'; the 2026-07-03 review
-- (gap 2) widened '4-10' to '4-11' so the 11:00 UTC NSE-discovery window in
-- check_pipeline_health actually gets evaluated (applied live via cron.alter_job
-- in migration monitor_nse_discovery_and_publish_prices).
select cron.schedule('health-monitor', '20,50 4-11,14-23 * * 1-5',
  $cron$ select public.check_pipeline_health(); $cron$);

-- --- heartbeat seeds (one-time, migration monitor_nse_discovery_and_publish_prices) ---
-- The 'daily-discovery-in' and 'publish-prices' keys are written by the
-- workflows from 2026-07-03 on; seeded once at migration time (on conflict do
-- nothing) so the first in-session monitor tick after rollout didn't fire a
-- false 'never ran' stale alert before the workflows completed one cycle.
insert into public.run_heartbeat (workflow_name, last_run_at, status)
values ('daily-discovery-in', now(), 'ok'),
       ('publish-prices', now(), 'ok')
on conflict (workflow_name) do nothing;
