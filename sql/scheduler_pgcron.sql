-- =====================================================================
-- Scheduler — Supabase pg_cron -> GitHub workflow_dispatch (control plane)
-- =====================================================================
-- WHY THIS FILE EXISTS (v9 code review, gap #3): the scheduler is the heart of
-- the system (solution design §4.1), but its DDL lived ONLY inside Supabase and
-- was never committed. sql/phase5_monitoring.sql held the monitor + the ET gate
-- re-point, but NOT the dispatch function or the base cron jobs — so the trigger
-- path could not be rebuilt from the repo. This file captures the live
-- definitions (extracted from production via pg_get_functiondef / cron.job) so
-- the whole control plane is reproducible from version control.
--
-- Apply order: this file FIRST (defines dispatch_github_workflow + base crons),
-- then phase5_monitoring.sql (defines dispatch_watchlist_if_open, re-points the
-- watchlist cron at the gate, and schedules health-monitor).
--
-- PREREQUISITES (create once, manually — secrets are NOT in version control):
--   • extensions:  pg_cron, pg_net   (enable in Supabase dashboard)
--   • Vault secret 'github_workflow_pat'  -> a GitHub PAT with `actions:write`
--                                            on arjun-batra/stock-advisory-analysis
--   • Vault secret 'ntfy_topic'           -> the ntfy topic (used by send_ntfy)
-- =====================================================================

-- --- dispatch function: POST a workflow_dispatch to GitHub via pg_net --------
-- Reads the PAT from Vault (never hardcoded), POSTs to the Actions dispatch API
-- on ref 'main'. SECURITY DEFINER + locked search_path; execute is revoked from
-- public/anon/authenticated below so only the cron jobs (postgres) can call it.
CREATE OR REPLACE FUNCTION public.dispatch_github_workflow(
  workflow_file text,
  inputs jsonb DEFAULT '{}'::jsonb
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
declare
  pat text;
  req_id bigint;
  payload jsonb;
begin
  select decrypted_secret into pat
  from vault.decrypted_secrets
  where name = 'github_workflow_pat'
  limit 1;

  if pat is null then
    raise warning 'dispatch_github_workflow: secret github_workflow_pat not found in vault; skipping';
    return null;
  end if;

  payload := jsonb_build_object('ref', 'main');
  if inputs is not null and inputs <> '{}'::jsonb then
    payload := payload || jsonb_build_object('inputs', inputs);
  end if;

  select net.http_post(
    url := 'https://api.github.com/repos/arjun-batra/stock-advisory-analysis/actions/workflows/'
           || workflow_file || '/dispatches',
    body := payload,
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || pat,
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'User-Agent', 'supabase-pg-cron',
      'Content-Type', 'application/json'
    )
  ) into req_id;

  return req_id;
end;
$function$;

revoke execute on function public.dispatch_github_workflow(text, jsonb)
  from public, anon, authenticated;

-- --- base cron jobs (live schedules, extracted from cron.job) -----------------
-- NOTE on watchlist-dispatch: it is created here calling the ET-aware gate
-- public.dispatch_watchlist_if_open() (its current live state). That gate is
-- DEFINED in phase5_monitoring.sql, so apply this file's cron.schedule for the
-- watchlist AFTER phase5_monitoring.sql has created the gate — or create the job
-- first and let phase5's cron.alter_job re-point it (that is how production got
-- here). The schedule itself (the */30 13-21 UTC DST superset) is unchanged.

-- watchlist: every 30 min over the DST superset window, weekdays; the gate trims
-- it to the live 09:30-16:00 ET session.
select cron.schedule(
  'watchlist-dispatch',
  '*/30 13-21 * * 1-5',
  $cron$ select public.dispatch_watchlist_if_open(); $cron$
);

-- discovery: once daily at 22:00 UTC (post US/TSX close), weekdays. Not ET-gated
-- (uses the last close); dispatched directly.
select cron.schedule(
  'discovery-dispatch',
  '0 22 * * 1-5',
  $cron$ select public.dispatch_github_workflow('daily-discovery.yml'); $cron$
);

-- health-monitor: scheduled in sql/phase5_monitoring.sql
--   ('20,50 14-23 * * 1-5' -> public.check_pipeline_health()). Not duplicated here.

-- =====================================================================
-- Phase 6 — India NSE activation (dry-run): dispatch + crons
-- =====================================================================
-- Applied via Supabase migrations phase6_nse_watchlist_dispatch_dryrun and
-- phase6_nse_discovery_and_prices_crons; mirrored here for reproducibility.
-- Sessions never overlap (fixed IST offset vs DST-aware ET), so the NSE dispatch
-- is a parallel gate mirroring dispatch_watchlist_if_open().

-- NSE watchlist dispatch gate: mirrors the ET gate but on the IST session
-- (09:15-15:30 IST). DRY-RUN — passes alerts_enabled=false so NSE runs process +
-- log but send no real pushes. GO-LIVE: drop the inputs (default true) once the
-- NSE ntfy topic is provisioned. The Python per-market gate re-checks is_nse_open.
create or replace function public.dispatch_watchlist_nse_if_open()
returns void
language plpgsql security definer set search_path = '' as $$
declare
  ist_now timestamp := (now() at time zone 'Asia/Kolkata');
  dow int := extract(isodow from ist_now);
  t   time := ist_now::time;
begin
  if dow > 5 then
    return;
  end if;
  if t >= time '09:15' and t <= time '15:30' then
    perform public.dispatch_github_workflow(
      'hourly-watchlist.yml',
      jsonb_build_object('alerts_enabled', 'false')   -- DRY-RUN; drop for go-live
    );
  end if;
end; $$;

revoke execute on function public.dispatch_watchlist_nse_if_open() from public, anon, authenticated;

-- NSE watchlist cron: every 30 min over 03:00-10:59 UTC (brackets the 03:45-10:00
-- UTC IST session); the gate trims it to the live session.
select cron.schedule('nse-watchlist-dispatch', '*/30 3-10 * * 1-5',
  $cron$ select public.dispatch_watchlist_nse_if_open(); $cron$);

-- NSE discovery cron: 10:00 UTC (15:30 IST / NSE close) — NOT the 22:00 UTC US run
-- (which would screen stale pre-open India data). region=in + DRY-RUN alerts off.
select cron.schedule('discovery-dispatch-nse', '0 10 * * 1-5',
  $cron$ select public.dispatch_github_workflow('daily-discovery.yml', '{"region":"in","alerts_enabled":"false"}'::jsonb); $cron$);

-- Dashboard prices (issue #18 fallback): refresh the same-origin prices.json on the
-- market cadence across both sessions. The workflow commits only when prices moved.
select cron.schedule('publish-prices', '*/30 3-10,13-21 * * 1-5',
  $cron$ select public.dispatch_github_workflow('publish-prices.yml'); $cron$);

-- =====================================================================
-- Live cron inventory (post Phase-6 activation):
--   watchlist-dispatch      */30 13-21 * * 1-5   -> dispatch_watchlist_if_open()        [US/TSX, live]
--   discovery-dispatch      0 22 * * 1-5         -> dispatch_github_workflow(daily-discovery.yml)  [US, live]
--   health-monitor          20,50 4-10,14-23 * * 1-5 -> check_pipeline_health()         [both sessions]
--   nse-watchlist-dispatch  */30 3-10 * * 1-5    -> dispatch_watchlist_nse_if_open()    [NSE, DRY-RUN]
--   discovery-dispatch-nse  0 10 * * 1-5         -> daily-discovery.yml region=in       [NSE, DRY-RUN]
--   publish-prices          */30 3-10,13-21 * * 1-5 -> publish-prices.yml               [prices.json]
-- =====================================================================
