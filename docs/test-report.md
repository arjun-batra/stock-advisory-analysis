# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-3 — Kill-switch (FR24, FR25, FR26, NFR2) — 2026-07-28

**Scope:** `docs/design/increment-plan.md` "### INC-3 — Kill-switch" (6 acceptance criteria), design
`docs/design/operational-controls.md` §13, dev handoff `docs/handoff.md`. Files under test: new
`sql/kill_switch.sql`, edits to `sql/scheduler_pgcron.sql` and `sql/phase5_monitoring.sql`. No Python
changes claimed by this increment.

**Constraint honored (same as dev's):** Arjun has explicitly deferred applying any SQL to the live
Supabase project. AC1–AC5 all require live verification (`list_tables`/`list_functions`, calling
`set_kill_switch()`, checking `pg_class.relrowsecurity`/`relforcerowsecurity`, anon-key REST calls) that
cannot happen pre-apply. No Supabase tool call was made to fake or simulate this. Those 5 criteria were
instead exercised via a line-by-line static/code review of the actual SQL against the design doc and
against each other, specifically hunting for the kind of defect a live test would otherwise catch
(dispatch paths that skip the guard, RLS/force gaps, GREATEST()/resume-baseline logic errors, etc.).

### AC-by-AC result

1. **`kill_switch_state`, `kill_switch_audit`, `set_kill_switch()` exist** — reviewed, no defect found.
   `sql/kill_switch.sql` defines all three exactly as designed (diffed programmatically against
   `operational-controls.md` §13.2/§13.3's fenced SQL blocks — statement bodies are byte-identical, only
   comment/header lines were added). **Pending live verification at apply-time** (`list_tables`/
   `list_functions` cannot run pre-apply).

2. **Pause blocks all 5 dispatch paths; unpause restores them** — reviewed, no defect found. Traced every
   scheduled dispatch path in `sql/scheduler_pgcron.sql` + `sql/phase5_monitoring.sql` back to
   `dispatch_github_workflow`: `dispatch_watchlist_if_open()` (US/TSX gate) → `dispatch_watchlist_nse_if_
   open()` (NSE gate) → `daily-discovery.yml` direct call (NA) → `daily-discovery.yml` with
   `region=in` (NSE) → `publish-prices.yml` direct call — all 5 funnel through the one function, and it
   checks `kill_switch_state.paused` and `return null`s *before* the PAT lookup / `pg_net.http_post`, so
   no HTTP request is constructed while paused. No dispatch path bypasses the choke point with its own
   direct `net.http_post` call (grepped for `net.http_post` outside `dispatch_github_workflow` — only other
   call site is `send_ntfy`, unrelated to dispatch). `run_heartbeat` rows are written by the Python
   workflow itself post-dispatch (not by SQL), so blocking the HTTP call transitively blocks the heartbeat
   write too — consistent with AC2's "writes no `run_heartbeat` row." **Pending live verification**
   (requires toggling the flag against a live project with pg_cron active).

3. **`check_pipeline_health()` pause-awareness + resume-baseline** — reviewed, no defect found.
   `check_pipeline_health` reads `paused`/computes `v_resume_baseline` first and `return`s immediately
   when `paused`, before any `_raise_monitor`/`_clear_monitor` call — and `send_ntfy` is only ever called
   from inside those two helpers, so the early return structurally guarantees zero `monitor_alerts` writes
   and zero `send_ntfy` calls while paused. Resume-baseline logic checked for off-by-one/logic errors:
   `v_resume_baseline := (case when not paused then updated_at end)` — since the singleton row is only
   ever mutated by `set_kill_switch()`, when the current state is unpaused, `updated_at` is necessarily the
   timestamp of the *last resume* (the last write to the row set `paused=false`), which is exactly what
   the design calls for. All four staleness checks (`wl_last` ×2 session branches, `disc_last`,
   `disc_in_last`, `pp_last`) correctly use `GREATEST(last_run_at, v_resume_baseline)` for the
   stale/not-stale *decision* only — alert message text still interpolates the raw, un-adjusted
   `*_last` variable, matching the design's explicit instruction. On a never-paused system,
   `v_resume_baseline` is the table's initial-insert timestamp (far in the past) and `GREATEST` correctly
   ignores it in favor of the real `last_run_at`; Postgres's `GREATEST` also ignores a NULL argument, so a
   not-yet-applied `kill_switch_state` row degrades safely rather than erroring. **Pending live
   verification** (requires a synthetic stale heartbeat + real pre/post-resume timing against a live DB).

4. **Exactly one `kill_switch_audit` row per toggle, correct `action`/`actor`/`changed_at`** — reviewed, no
   defect found. `set_kill_switch()` performs exactly one `update` and exactly one `insert` per call, with
   `action` derived directly from `p_paused` (`'pause'`/`'resume'`) and `actor` from
   `coalesce(auth.jwt() ->> 'email', session_user)` (never null — `session_user` is always non-null).
   **Pending live verification** (needs ≥2 real toggles against a live DB to confirm the insert actually
   succeeds post-RLS, per the file's own "dev must confirm at apply time" note — this is exactly the kind
   of claim static reading cannot settle, since RLS+BYPASSRLS interaction is a live-behavior question).

5. **RLS enabled on both tables, forced on `kill_switch_audit` only; anon REST calls denied** — reviewed,
   no defect found. `kill_switch_state`: `enable row level security`, no `force`, zero policies (line 29).
   `kill_switch_audit`: `enable` + `force row level security`, zero policies, plus an explicit
   `revoke insert, update, delete ... from public, anon, authenticated` (lines 50–52) — matches AC5's
   exact expected `pg_class` result (`relrowsecurity=true` both, `relforcerowsecurity=true` only on
   `kill_switch_audit`). **Pending live verification** (anon-key REST call, `pg_class` query).

6. **Full suite passes unmodified; zero `scripts/*.py` diff** — **VERIFIED, PASS.** Ran fresh (not just
   trusting dev's report):
   - `python3 -m pytest -q --tb=short` → **157 passed, 0 failed**.
   - `git diff --name-only -- scripts/` → empty.
   - `git show --stat` on the INC-3 commit confirms only `docs/handoff.md`, `sql/kill_switch.sql`,
     `sql/phase5_monitoring.sql`, `sql/scheduler_pgcron.sql` changed — no file under `scripts/` touched.

### Full regression

`python3 -m pytest -q --tb=short` (repo root, fresh run, not dev's cached result): **157 passed / 0
failed**, 0 collection errors. No SQL test infra exists in this repo (`tests/` has no SQL-targeting file),
consistent with this being a SQL-only increment with no existing Python surface touching these new
functions/tables — expected, not a gap introduced by this increment.

### Shippability check

Real entry point for this increment is the SQL itself applied to Supabase — which is, by explicit
constraint, not applied. There is nothing to run end-to-end yet; shippability of INC-3's actual runtime
behavior is deferred to apply-time, consistent with dev's handoff. The Python entry points
(`run_hourly.py`/`run_discovery.py`/`publish_prices.py`) are unaffected (zero diff) and continue to pass
their own suite, so nothing already-shipped was broken by this increment.

### Bugs filed

**BUG-002 — Contradictory apply-order documentation between `sql/kill_switch.sql` and its two dependent
files (minor/doc, non-blocking for merge, blocking for apply).**
- **Increment:** INC-3.
- **Files:** `sql/kill_switch.sql` header (lines 8–13), `sql/scheduler_pgcron.sql` header (lines 12–18),
  `sql/phase5_monitoring.sql` header (lines 15–17), `docs/handoff.md` (apply-order summary paragraph).
- **FR/NFR:** not a functional-requirement violation per se, but a real risk against FR24's guarantee if
  followed literally — a window where `dispatch_github_workflow` exists but `kill_switch_state` doesn't
  yet would make the function error at runtime on the next `pg_cron` tick instead of dispatching or
  gracefully skipping.
- **Repro:** read `sql/kill_switch.sql` lines 8–9: *"Apply order: after sql/scheduler_pgcron.sql and
  sql/phase5_monitoring.sql"* — i.e., apply `kill_switch.sql` **last**. Then read
  `sql/scheduler_pgcron.sql` lines 16–18: *"apply that file [kill_switch.sql] before (or in the same
  session as) this one"* — apply `kill_switch.sql` **first**. `sql/phase5_monitoring.sql` lines 15–17 say
  the same as `scheduler_pgcron.sql` ("apply that file before..."). `docs/handoff.md`'s own summary
  ("kill_switch_state must exist before either function is applied") agrees with the *other two* files,
  not with `kill_switch.sql`'s own header.
- **Expected:** all apply-order guidance across the three files (and the handoff summary) should agree on
  one order. Given the actual dependency (`dispatch_github_workflow`/`check_pipeline_health` `select ...
  from public.kill_switch_state`), the correct order is `kill_switch.sql` **first** (or same transaction),
  then `scheduler_pgcron.sql`, then `phase5_monitoring.sql` — matching `scheduler_pgcron.sql`/
  `phase5_monitoring.sql`/`handoff.md`, not `kill_switch.sql`'s own header.
- **Actual:** `kill_switch.sql`'s header states the reverse order from the other three sources.
- **Severity:** does not block merge (no code-behavior defect — `create or replace function` in plpgsql
  doesn't validate referenced-table existence at creation time, so applying in *either* order without a
  live cron tick in between would still succeed). It **does** need fixing before this SQL is handed to
  release/Arjun for live application, since whoever applies it will hit directly conflicting instructions
  and — if they follow `kill_switch.sql`'s literal (wrong) instruction as separate non-transactional
  migrations with the cron jobs already live from a prior deploy — could hit a runtime "relation does not
  exist" error on `dispatch_github_workflow`/`check_pipeline_health` during the gap.
- **Fix:** correct `sql/kill_switch.sql`'s header comment (lines 8–9) to match the other two files: apply
  `kill_switch.sql` first (or in the same session/transaction as the other two), not after.

No other defects found in the static review. AC1, AC2, AC3, AC4, AC5 are **reviewed, no defect found,
pending live verification at apply-time** — this is not a substitute for actually running them once the
SQL is applied; it only rules out defects visible from the code/design as written.

### Verdict

**PASS, conditional** — INC-3 is shippable as a repo-committed, not-yet-applied SQL change:
- AC6: **VERIFIED PASS** (157/157, zero `scripts/` diff, fresh run).
- AC1–AC5: **static review clean** (no defect found against the design or against each other's logic),
  each explicitly **pending live verification** once Arjun/release apply the SQL — cannot be marked
  verified-PASS by qa without live Supabase access, consistent with the project's explicit deferral.
- **BUG-002 filed** (apply-order doc inconsistency) — recommend dev fix the one-line header in
  `sql/kill_switch.sql` before this is handed to release for live application. Does not block reviewer's
  diff-scoped audit or merge to main; does block sign-off on "ready to apply as documented."

---

## Open bugs

**BUG-002** — `sql/kill_switch.sql`'s apply-order header contradicts `sql/scheduler_pgcron.sql` /
`sql/phase5_monitoring.sql` / `docs/handoff.md` (see INC-3 entry above for full repro/fix). Owner: dev.
