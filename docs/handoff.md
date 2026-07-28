# Handoff — INC-3: Kill-switch (FR24, FR25, FR26, NFR2)

Branch: `claude/admin-portal-evaluation-txaehj` (no new `inc-N` branch cut — Arjun directed batching
this whole change request on the current branch rather than the per-increment branch/merge cycle).

**Design:** `docs/design/operational-controls.md` §13. **Plan/AC:** `docs/design/increment-plan.md`
"### INC-3 — Kill-switch". Traces to `docs/requirements.md` FR24-FR26, NFR2 (extended), Decisions Log
#19-21.

## Constraint honored
Arjun has explicitly deferred applying any SQL changes to the live Supabase project for this change
request. **No Supabase apply/execute/migration/DDL tool call was made.** All work below is
write-only-to-repo: new/edited `.sql` files, reviewed and ready to apply, not yet applied. No
read-only Supabase check was performed either (not needed to write code that matches the design doc's
already-specified integration points verbatim).

## Files changed
- **New `sql/kill_switch.sql`** — `kill_switch_state` (singleton flag table, `CHECK (id)` constraint,
  RLS enabled with zero policies — REV-033), `kill_switch_audit` (append-only log, RLS `enable`+`force`
  with zero policies plus an explicit `revoke insert/update/delete from public, anon, authenticated` —
  REV-033's belt-and-suspenders fix), and `set_kill_switch(p_paused boolean, p_source text default
  'sql-direct')` (`SECURITY DEFINER`, updates the flag + inserts one audit row per call, execute revoked
  from `public/anon/authenticated`). Copied verbatim from `operational-controls.md` §13.2/§13.3 — no
  deviation from the design doc's SQL.
- **`sql/scheduler_pgcron.sql`** — `dispatch_github_workflow` (the single choke point all five dispatch
  paths funnel through: both watchlist gates, both discovery crons, publish-prices) now reads
  `kill_switch_state.paused` first and returns `null` before the PAT lookup / `pg_net.http_post` if
  paused, logging a `raise notice`. One guard, one function, per §13.1's design decision (lower-risk
  diff than touching all five call sites, and a future sixth workflow inherits the guard for free as
  long as it dispatches through this function).
- **`sql/phase5_monitoring.sql`** — `check_pipeline_health` now reads `kill_switch_state` first;
  returns immediately if `paused` (FR25: no alert evaluation at all while deliberately paused). Added
  the resume-baseline fix (§13.4, load-bearing, not optional): `v_resume_baseline` = the last
  `kill_switch_state.updated_at` where `paused = false`; all four staleness comparisons (watchlist
  `wl_last` — both the ET and IST session branches share the same variable/check, discovery `disc_last`,
  discovery-in `disc_in_last`, publish-prices `pp_last`) now compare against
  `GREATEST(last_run_at, v_resume_baseline)` instead of the raw `last_run_at`, so lifting a pause
  doesn't immediately false-alarm on a heartbeat that's merely stale from the pause duration — the
  monitor gets one full dispatch cycle post-resume before it can alert. Alert *message text* still shows
  the real, un-adjusted `last_run_at`/`disc_last`/etc. (only the stale/not-stale decision uses the
  adjusted baseline) — unchanged per the design doc's explicit instruction.

Both edited files got a one-line header note pointing at the new `sql/kill_switch.sql`
apply-order dependency (`kill_switch_state` must exist before either function is applied).

## Confirmed: no Python changes
```
git diff --name-only -- scripts/   # empty output
```
Zero files under `scripts/` touched. All three changed/new files are under `sql/`.

## How to run / verify (what's verifiable now, pre-apply)
```
python3 -m pytest -q --tb=short   # 157 passed, both before and after this change — zero regressions,
                                   # zero new tests (pure SQL increment, no existing Python test surface
                                   # touches these functions/tables)
```
Dollar-quoted block balance and `begin`/`end` nesting spot-checked manually (no live DB, no `psql`
available in this environment to run an actual parse/EXPLAIN).

## Acceptance criteria status (per increment-plan.md's 6 ACs)
- **AC6 (full test suite passes unmodified; zero `scripts/*.py` diff)** — **PASS**, verified above.
- **AC1-AC5** — written and ready per the design doc, but require live Supabase verification
  (`list_tables`/`list_functions`, calling `select set_kill_switch(true/false);`, manually invoking the
  5 dispatch paths and checking `net._http_response`/`run_heartbeat`, calling
  `check_pipeline_health()` with a synthetic stale heartbeat pre/post-resume, checking
  `kill_switch_audit` rows across ≥2 toggles, querying `pg_class.relrowsecurity`/`relforcerowsecurity`,
  and an anon-key REST call against both new tables) that cannot happen until this SQL is actually
  applied to the live project. **Not attempted, not faked** — per Arjun's explicit deferral. Flagging
  for whoever applies this later: AC2/AC3's "manually invoking dispatch paths" verification requires
  toggling the flag on a project where the pg_cron jobs are live, so schedule that verification for a
  low-traffic window.

## Known limitations
- The manual-`workflow_dispatch` bypass (a human clicking "Run workflow" in the GitHub UI, or
  `gh workflow run`, skips pg_cron and therefore the kill-switch check entirely) is an **accepted risk**
  per §13.1 — FR24's text scopes the guarantee to scheduled dispatches only. Not a bug, not something to
  fix in this increment.
- `set_kill_switch()` is callable only via the SQL editor / service-role connection until INC-7 adds the
  `is_admin()`-gated portal caller (`grant execute ... to authenticated`) — this increment is designed
  to be fully self-contained with zero portal dependency, per the approved build order.
- This increment's SQL is **not applied** to the live Supabase project. Nothing in this change request
  is live yet; apply-time coordination is release's/Arjun's call, out of scope for dev.
