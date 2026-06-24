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
create or replace function public.check_pipeline_health(p_now timestamptz default now())
returns void
language plpgsql security definer set search_path = '' as $$
declare
  dow int  := extract(isodow from p_now);          -- 1=Mon .. 7=Sun
  t   time := (p_now at time zone 'UTC')::time;
  wl_last timestamptz; wl_status text;
  disc_last timestamptz; disc_status text;
  mins numeric;
begin
  if dow > 5 then
    return;   -- weekends: nothing is scheduled, so nothing to watch
  end if;

  -- ===== WATCHLIST: stale or degraded, during the session + grace =====
  -- Runs every 30 min over ~13:30-21:00 UTC. Evaluate from 14:30 (lets the
  -- first run land) through 21:30 UTC. Stale if newest heartbeat > 70 min old
  -- (~2 missed */30 cycles, allowing for a slow run).
  if t >= time '14:30' and t <= time '21:30' then
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
  end if;

  -- ===== DISCOVERY: did it run in today's window? (check after 23:00 UTC) =====
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
end; $$;

-- --- lock down execute (these read Vault + hit the network) -----------
revoke execute on function public.send_ntfy(text,text,int,text[]) from public, anon, authenticated;
revoke execute on function public._raise_monitor(text,text,text,text,int,interval) from public, anon, authenticated;
revoke execute on function public._clear_monitor(text,text,text) from public, anon, authenticated;
revoke execute on function public.check_pipeline_health(timestamptz) from public, anon, authenticated;

-- --- schedule: :20 and :50 past the hour, 14-23 UTC, weekdays ---------
-- Covers the watchlist session window and the post-22:00 discovery check.
select cron.schedule('health-monitor', '20,50 14-23 * * 1-5',
  $cron$ select public.check_pipeline_health(); $cron$);
