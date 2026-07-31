# Increment plan — 2026-07-26 change request — INC-3–INC-7 all IMPLEMENTED; 2026-07-30 `/big-guns` fix round — INC-8/INC-9/INC-10 IMPLEMENTED (reviewer-CLEAR Passes 24/25/27); INC-11 approved, not yet executed; INC-12 (DEEP-007) IMPLEMENTED, reviewer-CLEAR Pass 29 — fix round complete; 2026-07-31 NFR8 change request — INC-13 IMPLEMENTED, reviewer-CLEAR Pass 35, merged to `main` (commit `da50ed8`, PR #46)

**Status:** GATE 3 was passed by the user for this plan. **INC-3 (kill-switch), INC-4 (AI provider
abstraction), and INC-5 (admin portal: auth, hosting, watchlist & holdings CRUD) are IMPLEMENTED** —
dev-built, qa-tested, and reviewer-reviewed through Pass 15 (INC-3/INC-4) and Pass 17 (INC-5)
(`docs/review-log.md`). "IMPLEMENTED" here does **not** mean fully live-verified for INC-3/INC-4:
INC-3's `sql/kill_switch.sql` **is applied and live** in the Supabase project — what remains deferred
(Arjun's explicit instruction, `review-log.md` REV-070) is the functional pause/resume verification test
(AC1–AC5), to be run as part of a final end-to-end pass covering all increments, not the SQL's
application; INC-4's AC6 (live-Gemini smoke test) is deferred, not failed, pending a real
`GEMINI_API_KEY` (`docs/handoff.md`); and INC-5's Pass 17 verdict is **CLEAR** — REV-081 (a minor,
not-currently-exploitable least-privilege gap on `admin_allowlist`'s grants), REV-082, and REV-083 are
all independently re-verified RESOLVED (`docs/review-log.md`), zero blockers, zero majors. Phase-4
closure must not treat FR24–FR26 as live-verified until INC-3's functional pause/resume test runs, nor
FR33 until INC-4's AC6 runs; FR27–FR29/NFR5–6 are reviewer-clear as of Pass 17. **INC-6 (admin portal:
tunables editor) is IMPLEMENTED and fully reviewer-clear** — dev-built, qa-tested (PASS —
`docs/test-report.md`; BUG-003 found and fixed), reviewer Pass 19 verdict **CLEAR** — REV-086/087/088/089
all independently re-verified RESOLVED, zero blockers, zero majors (`docs/review-log.md`). A
post-clearance, live-execution-only Postgres syntax bug was then found applying the cleared SQL live
(`CREATE POLICY ... FOR select, update` is not valid Postgres — a `FOR` clause accepts only one verb);
dev split it into two valid policies, and the fix was confirmed by a Pass 19 addendum (independently
re-verified live, `docs/review-log.md`). INC-6, together with INC-5's backfill (qa/reviewer clearance),
has since been merged to `main` (merge commit `887936b`). **INC-7 (admin portal: track-record view &
kill-switch UI) is IMPLEMENTED and reviewer-clear** — dev-built, qa-tested (PASS — zero bugs,
`docs/test-report.md`), reviewer Pass 20 verdict CLEAR — zero blockers, zero majors (two non-blocking
doc-hygiene minors, REV-093/094, both closed by tech-lead's design-doc update; `docs/review-log.md`).
This was the last increment in the approved build order — all seven increments (INC-3–INC-7) are now
IMPLEMENTED.

**2026-07-30 — `/big-guns` deep-review fix round.** `docs/review-log.md`'s "Deep review — 2026-07-29"
section logged DEEP-001 through DEEP-007 (one blocker, five majors, one minor). The user approved fixing
all six blocker/major findings before `v0.1.0` and running the three deferred live checks
(`requirements.md` Decision #36); pm sharpened NFR2/FR11/FR15/FR17/FR29/FR30 and added FR34 to make each
fix self-verifiable (Decisions #31–#35). **`DEEP-007` was excluded from this round** — an unresolved user
trade-off at the time, routed back to the user separately by pm; resolved 2026-07-30 (Decision #37) and now
built as **INC-12**, below. Four new increments were **approved by the user (GATE-3-equivalent) on
2026-07-30. INC-8, INC-9, and INC-10 are now IMPLEMENTED** — INC-8: dev-built, qa-tested (PASS, zero bugs,
`docs/test-report.md`), reviewer Pass 24 verdict CLEAR, zero blockers/majors (`docs/review-log.md`); INC-9:
dev-built, qa-tested (PASS, 244/0), reviewer Pass 25 verdict CLEAR, zero blockers/majors; INC-10: dev-built,
qa-tested (PASS across two fix cycles), reviewer Pass 27 verdict CLEAR, zero blockers/majors (both fix-cycle
findings, REV-112/REV-113, independently re-verified RESOLVED). **INC-11 is approved and not yet
executed**: **INC-8** (DEEP-001+002 — NFR2 heartbeat accounting + FR34 delivery-confirmed alerting),
**INC-9** (DEEP-003+004 — the parse-attribution contract + the FR17 stale-bar/holiday check), **INC-10**
(DEEP-005+006 — FR30 tunables write-time validation + FR29 holdings-currency derivation), **INC-11**
(Decision #36's three live-verification checks, no dev code). Sequencing (`big-guns`'s own recommendation, no deviation):
INC-8's two findings share the same two entry points (`run_hourly.py`/`run_discovery.py`) and the same
`outcomes`/degraded formula, so fixing them separately would touch that formula twice; INC-9's two findings
are both judgment-input-path integrity fixes (`ai_judge.py`/`ingest.py`), independent of the portal and of
INC-8; INC-10's two findings are both admin-portal write-validation fixes sharing `admin-portal/lib/
validation.ts`. INC-11 runs last since none of its three checks need to precede any code fix, and running
it last means the final pre-`v0.1.0` live verification exercises the fixed code (in particular, INC-4 AC6's
live-Gemini smoke test benefits from running after INC-9's parse-contract fix is merged). **No increment
starts before the previous one passes QA** (unchanged non-negotiable) — INC-8 → INC-9 → INC-10 → INC-11 in
that order; none of INC-8/9/10 has a code dependency on another, so this is a hygiene/traceability
sequencing choice, not a technical blocking dependency (documented per-increment below where it matters,
e.g. INC-11's live checks against INC-3/INC-7's already-shipped SQL have no dependency on INC-8/9/10 at
all and could in principle run earlier if the user wants results sooner — noted in INC-11, not re-ordered
here, since keeping the fix round as one contiguous unit is simpler to track against Decision #36).

Split out of `docs/design.md` (2026-07-28, doc hygiene — `design.md` exceeded the ~400-line module-split
guidance once the Pass-11 review fixes landed). See `docs/design.md` for the index, module map, §0
load-bearing decisions, retired-work pointer, and §15 requirement coverage map — read that first for
orientation. This file is the project plan (INC-3 through INC-7) referenced by the pipeline's Phase 3
increment loop.

Continues the project's increment numbering (INC-1/INC-2 were the retired shadow-pilot tracks, see
`docs/design.md`'s "Retired: shadow-pilot tracks" note — numbers are not reused). Sequencing follows the
approved build order: kill-switch first (self-contained, no dependency on the other two items), then the
AI provider abstraction (a contained refactor, independent of the portal), then the admin portal last,
split into vertical slices so each is independently shippable — the portal's kill-switch-UI slice (INC-7)
intentionally comes last because it depends on INC-3's backend flag/function already existing. **No
increment starts before the previous one passes QA (CLAUDE.md non-negotiable).**

**2026-07-27 revision (Decision #27, supersedes #24):** INC-6 (tunables editor) originally carried an
open design gap and a wider file footprint (a GitHub-PAT-holding Vercel proxy, plus edits to two
production workflow YAML files). Design-time investigation found Decision #24's premise false — only 2
of the 10 curated keys were actually wired from a GitHub Variable into the live workflows — and Arjun
approved moving the tunables source of truth to a new Supabase `tunables` table instead, reusing INC-5's
`is_admin()`/RLS mechanism directly rather than a separate GitHub-API code path. **INC-6 is now smaller
than originally planned, not larger: no GitHub API integration, no server-only secret, and the original
open design gap is resolved (not just deferred).** INC-6 now also has a **direct, literal dependency on
INC-5's `is_admin()`/`admin_allowlist` objects** (not just a shared pattern it happens to reuse) — the
`tunables` table's write policy calls the exact same function INC-5 creates for watchlist/holdings, so
INC-6 cannot be built or even meaningfully designed against a stub.

**2026-07-27 revision, second pass (Decision #28, refines #27):** the failed-Supabase-fetch fallback for
these 10 keys is no longer a fixed hardcoded Python literal — it's a repo-committed cache file
(`tunables_cache.json`) holding the last successfully-fetched value per key, reusing (in spirit)
`publish-prices.yml`'s already-proven commit-on-change mechanism. Decision #28 *proposed*
`hourly-watchlist.yml` (runs most frequently) as the **sole** writer, for Arjun to confirm or override;
`daily-discovery.yml` and `publish-prices.yml` were proposed as read-only consumers, as they already are
for the Supabase table itself. This adds one small workflow-YAML change to `hourly-watchlist.yml` — see
the 2026-07-28/REV-040 paragraph directly below for how that change actually landed, which is **not** a
verbatim copy of `publish-prices.yml`'s step, contrary to what an earlier draft of this paragraph said.

**2026-07-28, reviewer REV-040 + Decision #29 (pm, confirms #28's write-ownership proposal):** reviewer
found the verbatim-copy plan above race-prone (`hourly-watchlist.yml` and `publish-prices.yml` push to
`main` on the same `*/30` cadence window under *different* concurrency groups, so a lost push race would
red-X the trading workflow *after* its real work had already completed) and over-privileged
(`contents: write` at the workflow level on the file holding every production secret). REV-040 flagged
the write-ownership choice itself as a trade-off to re-put to Arjun rather than a defect in Decision #28.
**Arjun confirmed `hourly-watchlist.yml` stays the sole writer** — it's the workflow actually triggered
off the Supabase-scheduled jobs, the natural place to write state back — **on condition of** REV-040's
two mitigations, both now part of this design: (a) `hourly-watchlist.yml` and `publish-prices.yml` share
one `concurrency` group (`repo-commit`, renamed from their two separate groups) so their commit steps can
never be scheduled concurrently; (b) the new commit step's `permissions: contents: write` is scoped to
the job, not the workflow file, and its `git push` is wrapped in a bounded 3-attempt retry (the original
draft guarded only the `git pull --rebase`, leaving the push itself to fail the whole step outright on a
lost race). See `docs/design/tunables-workflow-writeback.md` §16.4 for the full mechanism and exact YAML
diff (and `docs/design/tunables-fallback.md` §16.4 for `scripts/config.py`'s fetch/fallback side).

### INC-3 — Kill-switch (FR24, FR25, FR26, NFR2) — **IMPLEMENTED** (dev-built, qa-tested, reviewer-cleared
zero blockers through Pass 15; `sql/kill_switch.sql` applied and live — functional pause/resume test
(REV-070) deferred to a final end-to-end pass, see status note above)
**Design:** `docs/design/operational-controls.md` §13. **Files:** new `sql/kill_switch.sql`
(`kill_switch_state`, `kill_switch_audit`, `set_kill_switch()`); edits to `dispatch_github_workflow` and
`check_pipeline_health` in `sql/scheduler_pgcron.sql` / `sql/phase5_monitoring.sql`. **No Python changes**
— enforcement is entirely at the SQL/pg_cron dispatch layer, per FR24.
**Acceptance criteria (dev self-verifiable):**
1. `kill_switch_state` (singleton), `kill_switch_audit`, and `set_kill_switch(p_paused, p_source)` exist
   in the live Supabase project (confirm via `list_tables` / `list_functions`).
2. With `select set_kill_switch(true);`, manually invoking any of the 5 dispatch paths (both watchlist
   gates, both discovery calls, publish-prices) during their normal trigger window makes **no** `pg_net`
   HTTP request (no new `net._http_response` row) and writes **no** `run_heartbeat` row. With
   `select set_kill_switch(false);`, the same calls dispatch normally (a `pg_net` request row appears).
3. `select check_pipeline_health();` with `paused=true` and a synthetically stale heartbeat produces
   **no** `monitor_alerts` change and **no** `send_ntfy` call. After `set_kill_switch(false, ...)`,
   re-running immediately (heartbeat still stale purely from the pause duration) still produces **no**
   false "stale" alert — confirms the resume-baseline fix (§13.4).
4. Each `set_kill_switch` call inserts exactly one `kill_switch_audit` row with the correct `action`
   (`pause`/`resume`), a non-null `actor`, and `changed_at` — verified across ≥2 toggles. This also
   proves RLS didn't break the audit insert (`operational-controls.md` §13.2, REV-033: both tables have
   RLS enabled and zero anon/authenticated policies; `kill_switch_audit` is additionally `force`d).
5. `select relrowsecurity, relforcerowsecurity from pg_class where relname in ('kill_switch_state',
   'kill_switch_audit')` shows RLS enabled on both and forced on `kill_switch_audit`; a direct REST call
   with the anon key (no session) to either table returns zero rows / a permissions error, not data
   (REV-033).
6. Full existing test suite passes unmodified; no `scripts/*.py` file is touched by this increment (grep
   confirms zero diff outside `sql/`).

### INC-4 — AI provider abstraction (FR33) — **IMPLEMENTED** (dev-built, qa-tested 5 of 6 AC,
reviewer-cleared zero blockers through Pass 15; AC6 live-Gemini smoke test deferred pending real
credentials — see status note above)
**Design:** `docs/design/operational-controls.md` §14. **Files:** new `scripts/ai_provider.py`; refactor
`scripts/ai_judge.py`. No other file changes — `run_hourly.py`/`run_discovery.py` are untouched.
**Acceptance criteria:**
1. `scripts/ai_provider.py` defines `AIProvider` (ABC), `ProviderResult`, `TokenUsage`, `ErrorClass`,
   `ProviderError`, `BatchVerdictSchema`, `GeminiProvider`, `get_provider()`, per §14.2.
2. `grep -n "genai\|types\." scripts/ai_judge.py` returns **zero** matches — all Gemini-SDK-specific
   imports/calls now live only in `ai_provider.py`.
3. `judge_batch()`'s public signature/return contract is unchanged (`{ticker: {verdict, confidence,
   rationale, raw_model_response, parse_status, model_used, usage, fallback_from, retry_count}}`);
   `git diff` shows **zero** changes to `run_hourly.py` and `run_discovery.py`.
4. Full existing test suite passes with no assertion changes (import-path updates only) — proves
   behavior parity, not a rewrite. `config.GEMINI_TIMEOUT_MS` / `GEMINI_MAX_RETRIES` /
   `GEMINI_RETRY_BASE_MS` still govern retry/backoff identically (same log lines, same jitter formula).
5. `config.AI_PROVIDER` (default `"gemini"`) added to `scripts/config.py` and the config audit baseline
   (`non-functional-ops.md` §9); `get_provider("bogus")` raises `SystemExit` with a clear message.
6. A real smoke-test batched call against live Gemini still returns valid verdicts through the new path.

### INC-5 — Admin portal: auth, hosting, watchlist & holdings CRUD (FR27, FR28, FR29, NFR5, NFR6) — **IMPLEMENTED** (dev-built, live-deployed `f48f5f7`/`6895db0`, qa-tested with a PASS verdict — `docs/test-report.md`; reviewer Pass 17 verdict CLEAR — REV-081/082/083 all RESOLVED, zero blockers — see status note above)
**Design:** `docs/design/admin-portal.md` §16.1–§16.3, §16.7–§16.8. **Files:** new `admin-portal/`
Next.js app (Vercel); new `sql/admin_portal_rls.sql` (`admin_allowlist`, `is_admin()`, watchlist/holdings
write policies).
**Note:** `admin_allowlist`/`is_admin()` built here are a **hard, literal dependency for INC-6** as of
Decision #27 — the tunables table's write policy calls this exact function, not just a shared pattern.
Keep the migration's function signature stable once INC-6 is built against it.
**Acceptance criteria:**
1. Portal deployed on Vercel at a stable URL; logged-out visits redirect to Google sign-in; no
   email/password or magic-link UI exists anywhere in the app (confirm both in the Supabase Auth
   provider config and the login page markup).
2. Signing in with a non-allowlisted Google account is signed out immediately with a visible
   "not authorized" message; devtools network tab shows no successful watchlist/holdings query for that
   session.
3. Signing in with the allowlisted admin account reaches the authenticated app.
4. Admin can add/edit/delete a `watchlist` row and a `holdings` row from the portal; each change is
   confirmed by querying Supabase directly.
5. The same writes attempted via a direct REST call with the anon key and **no** authenticated admin
   session are rejected by RLS (`curl` returns a permissions error) — proves NFR6's "no unauthenticated
   write path."
6. `admin_allowlist`/`is_admin()` exist and are used by both new RLS policies (grep the migration).
   `admin_allowlist` itself has RLS enabled with zero anon/authenticated policies (REV-033) — a direct
   REST call to it with the anon key returns zero rows, and a direct `insert` attempt (an unauthenticated
   caller trying to self-register as admin) is rejected.
7. No secret of any kind (there is none in this design — no GitHub PAT, no server-only credential) appears
   in the built client bundle or any browser network request; the portal's only "credential" is the
   signed-in user's own Supabase session, which is expected and RLS-gated.
8. **(REV-034) Existing-schema grant/policy audit, executed against the live Supabase project before
   INC-5 ships:** enumerate every grant and RLS policy on `watchlist`, `holdings`, `verdict_state`,
   `call_log`, `run_heartbeat`, `monitor_alerts`, and the `latest_call_per_ticker` view, by role (`select *
   from pg_policies where schemaname='public'` plus `information_schema.role_table_grants`), and record
   the result in `docs/handoff.md` or a scratch note for reviewer's traceability audit. Confirm an
   `authenticated`-but-not-allowlisted session (a signed-in Google account not in `admin_allowlist`, once
   INC-5's OAuth is live) can read/write **nothing beyond what the `anon` key already could** — i.e. no
   pre-existing policy is written `to authenticated`/`to public` with a permissive `using (true)` that
   INC-5's OAuth rollout would newly make reachable. This is a **verify-against-reality** criterion, not a
   design claim — `sql/schema.sql` (REV-035, `non-functional-ops.md`/`data-and-flow.md`) is the
   version-controlled starting point, but INC-5 must re-check the live project directly since it's the
   first increment that makes `authenticated` an internet-reachable principal at all.

### INC-6 — Admin portal: tunables editor (FR30) — **IMPLEMENTED, reviewer Pass 19 CLEAR, merged to `main`** (dev-built, qa-tested — PASS, BUG-003 found and fixed, `docs/test-report.md`; REV-086/087/088/089 all RESOLVED, zero blockers — see status note above) — REVISED 2026-07-27/28, Decisions #27 (supersedes #24), #28 (refines #27) and #29 (confirms #28's write-ownership proposal, conditioned on REV-040)
**Design:** `docs/design/admin-portal-tunables.md` §16.4 (schema/RLS/seed/portal UI),
`docs/design/tunables-fallback.md` §16.4 (`scripts/config.py`'s fetch/cache-fallback chain, timeout), and
`docs/design/tunables-workflow-writeback.md` §16.4 (which workflow commits the cache, REV-040's
race/privilege mitigations — split out 2026-07-28). **Files:** new
`sql/admin_portal_tunables.sql` (`tunables` table with key-registry CHECK, `_stamp_tunable_update()`
trigger, `admin_write_tunables` RLS policy scoped to `select, update` only, 10-row seed); new
`tunables_cache.json` at the **repo root** (10-key seed file, identical values to the SQL seed —
REV-046, not inside a `config/` subdirectory); new `admin-portal/app/tunables/` (portal UI); additions to
`scripts/config.py` (two-tier fallback chain — Supabase table → `tunables_cache.json`, no third
hardcoded-literal tier; fails loud via `SystemExit` if both tiers miss a key, or if a tier-1 value fails
to cast, see `tunables-fallback.md`'s 2026-07-28 revision — plus
`TUNABLES_FETCH_TIMEOUT_MS`/`SKIP_TUNABLES_FETCH`, validated `write_tunables_cache_if_fetched()`,
`TUNABLES_DEGRADED`, and the `ALERTS_ENABLED` AND-gate); one line added to `run_hourly.py`'s entry point;
**`.github/workflows/hourly-watchlist.yml`** gains a **job-scoped** `permissions: contents: write` block
(it has none today, REV-040b), its `concurrency.group` **renamed** from `hourly-watchlist` to
`repo-commit` (REV-040a), and a new "Commit tunables cache if changed" step with a **bounded 3-attempt
retry around the push** (REV-040, not a verbatim copy of `publish-prices.yml`'s step). **`publish-prices.yml`
also gets touched — one line**: its `concurrency.group` renamed from `publish-prices` to the same
`repo-commit` (REV-040a) — it stays a read-only tunables-cache consumer otherwise, gaining no commit
step, no new permission, no retry loop. `daily-discovery.yml` is the only workflow with **zero** changes.
**Depends on INC-5's `admin_allowlist`/`is_admin()` already existing.**
**Simplification note (still holds after Decisions #28/#29):** this increment remains **smaller** than
the original GitHub-PAT-proxy plan — no GitHub API integration, no PAT, no Vercel API route/proxy.
Decisions #28/#29 add a small, well-precedented workflow change (the tunables-cache commit step, adapted
— not copied verbatim — from a pattern already live and proven in `publish-prices.yml`, per REV-040's two
mitigations), not a new category of risk. All open questions from earlier passes — the GitHub-Variable
wiring gap, the failed-fetch fallback, and now the write-ownership trade-off REV-040 raised — are
resolved structurally, not deferred: Decision #29 keeps `hourly-watchlist.yml` as sole writer (Arjun's
reasoning: it's the workflow actually triggered off the Supabase-scheduled jobs) on condition of the two
REV-040 mitigations, both incorporated above.
**Acceptance criteria:**
1. `tunables` table exists, seeded with exactly the 10 FR30 keys at their current default
   value/description/example (matches `requirements.md` §10's per-key defaults — no behavior change at
   cutover, confirmed by diffing a fresh run's `data_snapshot`/discovery output against the pre-INC-6
   baseline for an unedited row). **`ALERTS_ENABLED`'s seed value is `"true"`** (today's actual live
   default via the `workflow_dispatch` input), not `config.py`'s bare `"false"` literal — verify this
   specific row explicitly, since seeding it wrong would silently break production alerting.
2. `tunables_cache.json` is committed with **exactly** the same 10 key/value pairs as the SQL
   seed above (byte-for-byte value match per key, including `ALERTS_ENABLED: "true"`) — diff the two
   seed sources directly, don't just eyeball them.
3. Writing to `tunables` with the anon key and **no** authenticated admin session is rejected by RLS
   (`curl` returns a permissions error) — same proof pattern as INC-5 item 5. RLS is enabled on
   `tunables` (`select relrowsecurity from pg_class where relname='tunables'`); the write policy is
   `select, update` only — a signed-in admin's `insert`/`delete` attempt against `tunables` is rejected
   too (REV-044, not just an anon check), and inserting/updating a row with a `key` outside the fixed 10
   fails the CHECK constraint.
4. Updating a row via the portal stamps `updated_at`/`updated_by` correctly (server-side, via the
   trigger — not client-supplied) and is visible on next read; `select * from tunables` after an edit
   confirms the new `value` and the signed-in admin's email in `updated_by`.
5. `scripts/config.py`'s `_tunable()`-derived values (e.g. `GEMINI_MODEL`, `DISCOVERY_GAINER_PCT`) pick
   up a table edit on the **next process start** (import-time fetch — not live/hot-reloaded mid-run,
   confirmed by editing a row, then re-running a script and observing the new value in its `[config]`
   startup log line).
6. **Cache write-back, unchanged case:** running `hourly-watchlist.yml` (or `run_hourly.py` locally
   against a live Supabase connection) when no `tunables` row has changed since the last run produces
   **zero** git commits — `git log` before/after shows no new commit touching
   `tunables_cache.json`.
7. **Cache write-back, changed case:** editing one `tunables` row via the portal, then triggering
   `hourly-watchlist.yml`, produces **exactly one** new commit authored by `github-actions[bot]`, message
   `chore: refresh tunables cache [skip ci]`, touching only `tunables_cache.json`, containing the
   new value and nothing else changed.
8. **Read-only workflows never write:** simulating a Supabase fetch failure (e.g. temporarily wrong
   `SUPABASE_URL`/blocked network) during a `daily-discovery.yml` or `publish-prices.yml` run — (a) the
   run falls back to `tunables_cache.json`'s values correctly (confirmed via the `[config]`
   startup log line naming the fallback tier used) and completes normally; (b) `git status`/`git log`
   shows **no** attempt to write or commit `tunables_cache.json` from either workflow — grep
   `run_discovery.py` and `publish_prices.py` for `write_tunables_cache_if_fetched` and confirm zero
   matches.
9. **Double-failure fails loud, not silent.** With the Supabase project unreachable (or the fetch
   returning no rows) **and** `tunables_cache.json` deleted or corrupted in a scratch test,
   importing `scripts/config.py` (and therefore any entry point that imports it —
   `run_hourly.py`/`run_discovery.py`/`publish_prices.py`) raises `SystemExit` naming the first
   unresolvable tunable key and both failed sources, and the process exits non-zero — it must **not**
   proceed with any value for that key (no hardcoded-literal floor exists to fall back to as of the
   2026-07-28 revision). A qa test performs exactly this: delete/corrupt the cache file, force the
   Supabase fetch to fail (bad URL or mocked exception), invoke the entry point, and assert non-zero
   exit + the `SystemExit` message naming the affected key.
10. `ALERTS_ENABLED`: with the `tunables` row set to `false`, a scheduled (no-`inputs`) run sends no real
    push even though the `workflow_dispatch` input defaults to `true` (table/cache suppresses). With the
    row `true` and a manual dry-run (`inputs.alerts_enabled=false`), no real push is sent either (input
    still wins as a floor) — proves the AND-gate direction is correct, not just "some interaction exists."
11. `git diff` shows **zero** changes to `daily-discovery.yml` for this increment. `publish-prices.yml`'s
    diff is limited to the one-line `concurrency.group` rename (REV-040a) — no other line changes.
    `hourly-watchlist.yml`'s diff is limited to: the `concurrency.group` rename (REV-040a), the new
    job-scoped `permissions:` block (REV-040b), and the one new commit step with its retry loop.
12. **(REV-036) Cache write-back validates and never shrinks.** With `SKIP_TUNABLES_FETCH` unset and a
    live fetch that returns 9 of the 10 keys (simulate by deleting one row), `write_tunables_cache_if_
    fetched()` leaves the 10th key's previously-cached value untouched in `tunables_cache.json` — the
    file's key count never decreases. Separately, editing a curated key via direct SQL to a value that
    fails its cast (e.g. `DISCOVERY_GAINER_PCT = '5%'`) and re-running an entry point raises `SystemExit`
    naming that key at import time (tier-1 cast failure, not a silent fall-through to cache) — confirms
    the bad value never reaches `tunables_cache.json`.
13. **(REV-041) Fetch timeout and offline seam.** `TUNABLES_FETCH_TIMEOUT_MS` is read from the
    environment (default present in `scripts/config.py` and the config audit baseline, `non-functional-
    ops.md` §9) and passed into the Supabase client options; with `SKIP_TUNABLES_FETCH=true`, importing
    `config.py` makes **zero** network calls (confirm via a network-call assertion/mock in the qa test)
    and resolves every curated key from `tunables_cache.json`. `qa` mocks `config._fetch_tunables`
    directly to exercise both the double-miss (AC9) and tier-2-degraded (AC14) paths deterministically.
14. **(REV-045) Degraded-tunables signal is monitor-visible.** Forcing tier-2 resolution for at least one
    curated key (e.g. via `SKIP_TUNABLES_FETCH=true` with a populated cache) and running
    `run_hourly.py`/`run_discovery.py`/`publish_prices.py` writes `run_heartbeat.status = 'partial'` (or
    the entry point's existing degraded value) even when no ticker-level error occurred — confirms
    `config.TUNABLES_DEGRADED` reaches the heartbeat write at all three entry points.
15. **(REV-040a) Shared concurrency group actually prevents the race.** `hourly-watchlist.yml` and
    `publish-prices.yml` both declare `concurrency: { group: repo-commit, cancel-in-progress: false }`
    (`grep concurrency -A2` both files — same group name, confirm neither still says `hourly-watchlist`
    or `publish-prices`). Dispatch both workflows at (near-)the same time (two manual `workflow_dispatch`
    calls back to back, or during a real overlapping `*/30` window) and confirm via the Actions run
    queue/logs that the second one visibly **waits** for the first rather than running concurrently — the
    primary defense is that their commit steps are never scheduled to overlap in the first place.
    Separately, confirm the pre-existing guarantee didn't regress: two overlapping `hourly-watchlist.yml`
    dispatches still serialize against each other (unchanged behavior, `non-functional-ops.md` §7.4) —
    the group rename must not have silently dropped this.
16. **(REV-040b) Push retry actually fires on a lost race, and permissions are job-scoped.** Simulate a
    lost race deterministically — e.g. push a throwaway commit to the branch between the step's `git
    pull --rebase` and its `git push` in a scratch test, or stub `git push` to fail on its first 1–2
    invocations — and confirm the step's log contains at least one `push attempt N/3 failed … retrying
    in`, followed by a successful push on a later attempt and a clean final commit graph (no
    duplicate/orphaned commits, no leftover local-only commit). Confirm a permanent failure (all 3
    attempts fail) exits non-zero with the `::error::` message naming the attempt count, rather than
    hanging or silently succeeding. Separately, confirm `permissions: contents: write` is declared under
    `jobs.watchlist`, not at the workflow's top level (`yq`/`grep` the YAML structure) — no top-level
    `permissions:` block exists in the file.

### INC-7 — Admin portal: track-record view & kill-switch UI (FR31, FR32) — **IMPLEMENTED, reviewer Pass 20 CLEAR** (dev-built, qa-tested — PASS, zero bugs, `docs/test-report.md`; zero blockers, zero majors — see status note above)
**Design:** `docs/design/admin-portal.md` §16.5–§16.6, `operational-controls.md` §13.3 (forward
reference). **Files:** `admin-portal/app/track-record/`; kill-switch toggle on the shared authenticated
layout; new `sql/kill_switch_portal_grant.sql` (extends `set_kill_switch`, adds
`kill_switch_state` SELECT policy). **Depends on INC-3.**
**Acceptance criteria:**
1. Read-only, paginated presentation of `call_log`/`latest_call_per_ticker` — no new aggregation/scoring
   beyond what's already logged (review confirms no derived-analytics code was added).
2. Kill-switch toggle shows the live `kill_switch_state.paused` value on load; flipping it calls
   `set_kill_switch(..., p_source:='admin-portal')` and produces a new `kill_switch_audit` row with
   `source='admin-portal'` and `actor` = the signed-in admin's email.
3. After toggling pause on via the portal, a subsequent dispatch call makes no `pg_net` request (reuses
   INC-3's verification method) — proves the UI is wired to the real flag.
4. All INC-5/INC-6 acceptance criteria still hold (full portal regression: auth gate, allowlist, RLS,
   no client-exposed secrets).

---

## 2026-07-30 fix round — INC-8 through INC-11 (approved by the user, GATE-3-equivalent, 2026-07-30; INC-8 IMPLEMENTED, INC-9–INC-11 approved-and-not-yet-built)

### INC-8 — Degraded-run visibility + delivery-confirmed alerting (NFR2, FR15, FR34; DEEP-001+DEEP-002) — **IMPLEMENTED** (dev-built, qa-tested — PASS, zero bugs, `docs/test-report.md`; reviewer Pass 24 verdict CLEAR — zero blockers, zero majors; one non-blocking minor, REV-107, carried to Phase-4 closure — `docs/review-log.md`)
**Design:** `docs/design/components.md` §4.6 (alerting), §4.8 (reliability/heartbeat); `docs/design/
data-and-flow.md` §6 (core flow pseudocode). **Files:** `scripts/state.py` (`process_ticker`,
`process_candidate`, `write_call_log`, `build_position` untouched here — DEEP-006 touches
`build_position`, INC-10), `scripts/notify.py` (`push()` return contract), `scripts/run_hourly.py` and
`scripts/run_discovery.py` (degraded formula, one line each), `pages/dashboard.html` (verdict-pill
special-case). **No SQL changes** — `check_pipeline_health()` already alerts on any `status <> 'ok'`; the
bug is entirely in which Python outcomes count as "not ok" (`components.md` §4.8).
**Depends on:** nothing outside this increment. **No config-schema change** — no new tunable.
**Acceptance criteria (dev self-verifiable):**
1. A qa test that drives every ticker in a batch to `parse_status="failed"` (mock the provider) and runs
   `run_hourly.main()`/`run_discovery.main()` asserts `run_heartbeat.status == "partial"` — the exact case
   DEEP-001 found reading `"ok"`. Same assertion for a mixed batch (some `no-read`, some `quiet`).
2. `grep -n 'outcomes\["no-read"\]' scripts/run_hourly.py scripts/run_discovery.py` and `grep -n
   'outcomes\["push-failed"\]\|outcomes\["candidate-push-failed"\]'` both return a match in the `degraded =
   ...` line of each file — confirms the formula change actually landed, not just a test.
3. `pages/dashboard.html`'s verdict-pill logic special-cases `parse_status` for all three of
   `"no_data"`/`"failed"`/`"api_error"` (grep the updated condition) — a synthetic `call_log` row with
   `parse_status="failed"` renders the "no reading" pill, not a `Hold` pill, in a manual/qa browser check.
   `pages/detail.html` needs no change (confirm via `git diff` showing zero changes to that file).
4. `NtfyNotifier.push()` returns `True` only on a response where `raise_for_status()` doesn't raise;
   returns `False` (not an exception propagating up) on any `requests` exception or non-2xx, logged via a
   distinct `[notify] ERROR push failed for {ticker}: ...` line. `DryRunNotifier.push()` returns `None`
   unconditionally. A qa test mocks `requests.post` to return a 500 and asserts `push()` returns `False`
   without raising.
5. On a simulated push failure (mock `notifier.push` to return `False`) for a watchlist ticker crossing a
   verdict: `call_log.alerted == False`, `verdict_state.current_verdict` is **unchanged** (still the OLD
   verdict), and a second call to `process_ticker` with the same new AI verdict on the next cycle fires
   `notifier.push` **again** for the same crossing (FR34's retry contract) — a qa test asserts all three in
   one flow (fail once, succeed on retry, confirm state now advances).
6. On a simulated dry run (`DryRunNotifier`) for a verdict crossing: `call_log.alerted == False` (honest —
   nothing was sent) but `verdict_state.current_verdict` **does** advance (no backlog buildup) — a qa test
   asserts both in the same assertion block, since these are the two halves of the same design decision
   (`components.md` §4.6) and a test asserting only one could pass on a regression that breaks the other.
7. Discovery: a candidate pushed via `DryRunNotifier` or a failed real push has `alerted=False`, and
   `state.recently_pushed_candidates()` does **not** include it — confirms the 7-day cooldown no longer
   dedupes an undelivered candidate (Decision #32).
8. Full existing test suite passes; `git diff` confirms no file outside the list above changed.

### INC-9 — Parse-attribution contract + closed-market structural check (FR17; DEEP-003+DEEP-004) — **IMPLEMENTED, reviewer Pass 25 CLEAR** (dev-built across two fix cycles — BUG-005/BUG-006 found and fixed — qa-tested PASS 244/0, `docs/test-report.md`; reviewer Pass 25 verdict CLEAR, zero blockers/majors; BUG-007 accepted as a documented, non-blocking limitation, `docs/review-log.md`)
**Design:** `docs/design/components.md` §4.2 (ingestion), §4.4/§4.4a (parse & retry); `docs/design/
non-functional-ops.md` §7.5 (delisting/holidays). **Files:** `scripts/ai_judge.py` (`_parse_batch`, new
`_normalize_ticker` helper, module docstring), `scripts/ingest.py` (`get_market_data`).
**Depends on:** nothing outside this increment; independent of INC-8. **No config-schema change.**
**Acceptance criteria:**
1. A qa test feeds `_parse_batch` a response array shorter than the requested list with a shifted/dropped
   ticker (the exact `[A,X,B]` requested-`[A,B,C]` scenario from DEEP-003's evidence) and asserts `C`
   resolves to `parse_status="failed"` (fail-safe Hold), **not** `B`'s verdict/rationale under `parse_status
   ="ok"`. A second test confirms the *legitimate* fallback case still works: a same-order response missing
   only the `ticker` label on one object still resolves that ticker with `parse_status="ok"`.
2. `grep -n "positional fallback used for" scripts/ai_judge.py` — the new log line exists and fires only
   on the legitimate path (confirm via the qa test's captured stdout).
3. `ai_judge.py`'s module docstring no longer makes the unqualified "can only ever MISS a signal" claim
   without naming the mechanism that makes it true (manual read, one paragraph).
4. A qa test constructs a `yfinance`-shaped history whose last bar's date is 3 days before "today" (frozen
   clock) during nominal market hours, calls `ingest.get_market_data(ticker)`, and asserts `has_price ==
   False` and a note naming the stale-bar reason — the exact DEEP-004 scenario (holiday, stale prior-close
   bar, `_session_state` says live). A second test with the last bar dated *today* is unaffected (`has_price
   == True`, normal pro-rating still applies when genuinely live).
5. `grep -n "last_bar_date" scripts/ingest.py` shows the comparison happens before `pct_change`/
   `volume_vs_avg` are computed — confirms the pro-rating math is structurally unreachable for a stale bar,
   not just skipped by a late-added guard (manual code read, one function).
6. Full existing test suite passes; `git diff` confirms no file outside `scripts/ai_judge.py` and
   `scripts/ingest.py` changed.

### INC-10 — Portal write-time validation + holdings-currency derivation (FR30, FR11, FR29; DEEP-005+DEEP-006) — **IMPLEMENTED, reviewer Pass 27 CLEAR** (dev-built across two fix cycles — REV-112/REV-113 found and fixed — qa-tested PASS, `docs/test-report.md`; reviewer Pass 27 verdict CLEAR, zero blockers/majors, `docs/review-log.md`)
**Design:** `docs/design/admin-portal-tunables.md` §16.4 (tunables validation); `docs/design/admin-portal.md`
§16.3 (holdings currency); `docs/design/non-functional-ops.md` §7.3 (currency enforcement). **Files:** new
`sql/tunables_validate_trigger.sql`, new `sql/holdings_currency_derivation.sql`; `admin-portal/lib/
validation.ts` (`validateTunableValue` becomes key-aware; `validateHoldingsRow` drops `currency`);
`admin-portal/app/(app)/tunables/page.tsx` (`ALERTS_ENABLED` renders as a `true`/`false` select, not free
text; per-key error surfacing); `admin-portal/app/(app)/holdings/page.tsx` (currency input removed, replaced
with a read-only derived label); `scripts/state.py` (`build_position` mismatch guard — the one line this
increment shares with INC-8's file, but a different function; no merge conflict risk since INC-8 doesn't
touch `build_position`); one seed-data correction (`ALERTS_ENABLED`'s `description` row).
**Depends on:** INC-5's `is_admin()` (already shipped) for both new triggers' `security definer` posture
convention — no new authorization mechanism. Independent of INC-8/INC-9.
**Acceptance criteria:**
1. Portal: attempting to save `ALERTS_ENABLED` with anything other than `true`/`false` is impossible via
   the UI (it's a select, not a text input — confirm via the rendered form) and, separately, submitting a
   malformed value for each of the 7 numeric curated keys via a direct API/RPC call (bypassing the select)
   is rejected client-side with `validateTunableValue`'s error message before any write attempt.
2. `GEMINI_MODEL_BACKUP` accepts and saves a blank value via the portal (confirms the fix to the
   shipped-but-wrong "value required" check that blocked disabling the fallback) — a qa test asserts an
   empty-string save succeeds.
3. Direct SQL: `update public.tunables set value='5%' where key='DISCOVERY_GAINER_PCT'` (run as an
   `authenticated`+`is_admin()` session, or as owner for the qa harness) raises an exception naming the key
   and the expected format — proves the DB trigger, not just the client, enforces the contract. Same test
   for `update ... set value='tru' where key='ALERTS_ENABLED'` — rejected. A **valid** edit to each of the
   10 keys still succeeds (regression: the trigger must not reject good values).
4. `select tgname from pg_trigger where tgrelid = 'public.tunables'::regclass order by tgname` shows the
   validate trigger firing before the stamp trigger (name ordering) — confirm via a qa test that a rejected
   update never touches `updated_at`/`updated_by` (no partial side effect from a failed write).
5. Holdings: the portal's add/edit form has no currency input; adding a TSX-market holding via the portal
   and then querying `select currency from holdings where ticker=...` directly shows `CAD`, not the old
   `USD` default — confirmed for one holding per market (US/TSX/NSE, 3 total).
6. A direct SQL `insert into holdings (ticker, shares, cost_basis, currency) values (<TSX ticker>, 10, 100,
   'USD')` (bypassing the portal entirely) still lands with `currency='CAD'` after insert — proves the
   trigger overrides even a client that tries to set it explicitly, not just a client that omits it.
7. `state.build_position()`: a qa test constructs a holding whose `currency` disagrees with
   `data["fundamentals"]["currency"]` (simulate the residual "watchlist.market wrong for this ticker" case)
   and asserts `pl_pct is None` with a logged warning — the case the DB trigger alone can't catch.
8. Full existing test suite (Python + `tests/admin_portal/*.test.ts`) passes; `git diff` confirms no file
   outside the list above changed.

### INC-11 — Live-verification pass (Decision #36; no dev code) — **APPROVED, not yet built** (GATE-3-equivalent, user approval 2026-07-30)
**Design:** n/a — this increment executes acceptance criteria already defined for INC-3, INC-4, and INC-7
above; it does not add or change design. **Files:** none in `scripts/`/`admin-portal/`/`sql/` — only
`docs/handoff.md` (dated evidence block, same pattern as the INC-5/INC-3 live-evidence records already in
that file) and `docs/test-report.md` (per-AC status flip from "deferred" to "PASS"/dated). **Depends on:**
INC-8/INC-9/INC-10 merged (so the checks below exercise the fixed code, per the sequencing note above) —
this is a scheduling preference, not a technical blocker; INC-3 AC3 and INC-7 AC2/AC3 have no code
dependency on INC-8/9/10 at all and may run earlier if the user wants results sooner.
**No dev build-plan step** — qa and release execute; dev has nothing to implement.
**Three checkable work items, separable — each can merge/close independently of the other two:**
1. **INC-3 AC3** (`increment-plan.md` above) — kill-switch resume-baseline / no-false-alarm test against
   the live Supabase project. **Not externally blocked** — the project and SQL are already live; this is
   pure execution. Owner: qa+release.
2. **INC-4 AC6** (`increment-plan.md` above) — live-Gemini smoke test. **Blocked on a real `GEMINI_API_KEY`
   in the execution environment** (none present as of the last check, `test-report.md`) — release obtains
   one (a $0–15/mo-cap-compatible key, NFR1) before this item can run; until then it stays "deferred,"
   correctly distinct from "delivered," per Decision #36. Owner: release (credential) then qa (execution).
3. **INC-7 AC2/AC3** (`increment-plan.md` above) — admin-portal kill-switch RPC round-trip and live
   dispatch-suppression proof. **Step 0, before AC2/AC3:** confirm `sql/kill_switch_portal_grant.sql` is
   actually applied to the live project (`select * from pg_policies where tablename='kill_switch_state'`
   and `select proname from pg_proc where proname='set_kill_switch'` — the same query pattern
   `docs/handoff.md`'s existing live-evidence blocks already use). `docs/design.md`'s FR31/FR32 coverage row
   states this SQL is already live and confirmed against production; if Step 0 confirms that, proceed
   directly to AC2/AC3 with no additional prerequisite work. If Step 0 finds it is **not** live (design.md
   stale on this point), apply the migration first, per the runbook's admin-portal deploy section, then
   proceed. Owner: release (Step 0 + apply if needed) then qa (AC2/AC3 execution).
**Acceptance criteria (dev self-verifiable is n/a here — these are qa/release-self-verifiable):**
1. All three items above produce a dated, attributed evidence block in `docs/handoff.md` (same format as
   the existing INC-3/INC-5 live-evidence records) — raw query/command + result, not a paraphrase.
2. `docs/test-report.md`'s per-AC table flips INC-3 AC3, INC-4 AC6, and INC-7 AC2/AC3 from "deferred" to a
   dated PASS (or a filed bug if one is found — routed through the normal qa→dev fix-cycle, not silently
   re-deferred).
3. pm's Phase-4 "every FR/NFR delivered or deferred" confirmation can then mark FR24–FR26, FR33, and
   FR31/FR32 as **delivered** (not merely "deferred, pending live execution") for exactly the two items that
   complete; **if INC-4 AC6 remains blocked on the credential at the time `v0.1.0` is otherwise ready to
   tag, that is a decision for pm/the user (per Decision #36's own text), not a decision this design makes
   silently** — routed back at closure if it comes to that, not resolved here.

---

## 2026-07-30 — INC-12 (DEEP-007 resolution, Decisions #37/#38) — IMPLEMENTED, reviewer-CLEAR Pass 29

### INC-12 — Kill-switch in-flight boundary checks + mid-run-abort classification (FR24, FR35) — **IMPLEMENTED** (dev-built, qa-tested PASS — all 9 literal ACs, `docs/test-report.md`; reviewer Pass 29 verdict CLEAR — REV-116 and REV-117 independently re-verified RESOLVED, DEEP-007 closed, zero blockers/majors, `docs/review-log.md`). `sql/kill_switch_abort_log.sql` is applied and live in production.
**Sequencing (Decision #37, binding):** strictly after INC-8 — designing the abort-accounting contract
before INC-8 settled what "the run produced real work, then stopped" means for NFR2/Decision #31 would have
meant guessing at a shape INC-8 might change out from under it. INC-8, INC-9, and INC-10 are all IMPLEMENTED
and reviewer-CLEAR (Passes 24/25/27) — INC-12 is now unblocked. Independent of INC-9/INC-10 otherwise (no
shared files).
**Design:** `docs/design/operational-controls.md` §13.6 (all five subsections — mechanism, the four
checkpoints, FR35's causal-tie classification, the NFR2/no-heartbeat-row decision, and the new table's
schema). **Files:** new `sql/kill_switch_abort_log.sql` (`kill_switch_abort_log` table, RLS+FORCE+REVOKE,
mirrors `kill_switch_audit`'s pattern); `scripts/state.py` (new `is_paused()`, new `KillSwitchAbort`
exception, new `write_kill_switch_abort()`, one checkpoint-3 call site each in `process_ticker` and
`process_candidate`); `scripts/run_hourly.py` (checkpoint 1 in `main()`, checkpoint 2 in `_process_group`,
a `try/except KillSwitchAbort` wrapping `main()`'s group-processing loop); `scripts/run_discovery.py` (same
shape — checkpoint 1 in `main()`, checkpoint 2 before its `judge_batch(...)` call, the same
`try/except KillSwitchAbort` wrapper); `scripts/publish_prices.py` (checkpoint 4 only, before the
`pages/prices.json` write). **No config-schema change** — no new tunable; `kill_switch_state`'s existing
schema is read, not extended.
**No user-visible behavior change beyond what Decision #37 already approved** — a paused run now visibly
stops mid-flight (fewer/partial per-cycle results) instead of completing silently to the badge's
disagreement; this is the literal guarantee Decision #37 chose, not a new trade-off. **Cost impact:
negligible** — one small append-only table, at most ~4 extra single-row Supabase reads per run
(§13.6.1) — well inside NFR1's existing cap, not requiring a fresh cost re-approval. Flagged to the user for
awareness (not re-approval) alongside this design: a future increment could surface `kill_switch_abort_log`
in the admin portal's track-record view for operator visibility; not built here (FR31 already bars new
analytics beyond what's logged, and no requirement asks for portal exposure of this table).
**Acceptance criteria (dev self-verifiable):**
1. `grep -n "def is_paused" scripts/state.py` exists; a qa test mocks the Supabase client's
   `kill_switch_state` read to return `paused=True`/`False` in turn and asserts `is_paused()` returns the
   matching bool in both cases.
2. Call-site count, confirmed by grep: exactly two `state.is_paused(sb)`/`is_paused(sb)` calls in
   `scripts/run_hourly.py` (checkpoint 1 in `main()`, checkpoint 2 in `_process_group`); exactly two in
   `scripts/run_discovery.py` (checkpoint 1, checkpoint 2); exactly two in `scripts/state.py` (checkpoint 3
   in `process_ticker` and `process_candidate`, each immediately before its own `notifier.push(...)` call);
   exactly one in `scripts/publish_prices.py` (checkpoint 4). `grep -n "class KillSwitchAbort" scripts/
   state.py` shows it subclasses `BaseException`, not `Exception`.
3. A qa test mocks `is_paused()` to return `True` before any ticker-level work and asserts
   `run_hourly.main()` / `run_discovery.main()` / `publish_prices.main()` each return having called none of
   `ingest.get_market_data`/`prefilter.find_candidates`/`ai_judge.judge_batch`/`notifier.push`/
   `state.write_heartbeat`/`state.write_kill_switch_abort` — checkpoint 1/4's abort is a bare, side-effect-free
   early return.
4. A qa test drives Phase 1 ingest to completion (non-empty `items`) then flips the mocked `is_paused()` to
   `True` at checkpoint 2 and asserts: `ai_judge.judge_batch` is never called, `state.write_heartbeat` is
   never called, `state.write_kill_switch_abort` is called exactly once with `checkpoint="ai_call"` and the
   correct `workflow` name.
5. A qa test processes at least one ticker to a real outcome (e.g. `quiet`, producing a genuine `call_log`
   row) so `real_rows_this_cycle` will be nonzero, then flips the mocked `is_paused()` to `True`
   immediately before the next ticker's verdict-crossing push, and asserts: `notifier.push` is never called
   for that ticker, no `write_call_log`/`verdict_state` write happens for it (the crossing stays exactly as
   pending as before this cycle touched it), `state.write_kill_switch_abort` is called once with
   `checkpoint="push"` and `real_rows_this_cycle` equal to the count of tickers already given a real outcome
   this cycle, and `state.write_heartbeat` is never called.
6. Re-running the same qa harness on the same fixture data with `is_paused()` now returning `False`
   throughout successfully pushes and advances `verdict_state` for the ticker AC5 left pending — proves
   FR35's "no new resume logic needed, the next cycle retries automatically" claim holds with zero
   additional code.
7. A qa test constructs a batch where checkpoint 3 fires partway through `_process_group`'s Phase 3 loop
   and asserts the loop's pre-existing `except Exception` guard around each ticker's processing does
   **not** catch it — it must propagate out of `_process_group` uncounted in `outcomes["error"]`, proving
   the `BaseException` choice is load-bearing, not cosmetic.
8. Live SQL (folded into INC-11's live-verification pass, not a merge blocker for this increment): `select
   relrowsecurity, relforcerowsecurity from pg_class where relname='kill_switch_abort_log'` shows both
   `true`; a direct REST call with the anon key returns zero rows or a permissions error (same proof
   pattern as INC-3 AC5). Pausing mid-run against a real dispatched run produces exactly one
   `kill_switch_abort_log` row with the correct `checkpoint`, and `check_pipeline_health()` raises no alert
   for that cycle, both while still paused (§13.4's blanket suppression) and after resuming (the existing
   `resume_baseline` guard).
9. Full existing test suite passes; `git diff` confirms no file outside the list above changed.

---

## 2026-07-31 — NFR8 change request (Decision #39) — INC-13, IMPLEMENTED, reviewer-CLEAR Pass 35, merged to `main` (commit `da50ed8`, PR #46)

pm flagged NFR8 (`requirements.md` §6, admin-portal UI/UX modernization) to tech-lead 2026-07-31, GATE 2
already passed by the user for NFR8 itself. This is one new increment appended after INC-12; none of
INC-3–INC-12 are marked stale by it (see the note at the end of this section).

**2026-07-31 update — gate cleared:** designer published `docs/ux-spec.md` with mockup directions
(A/C/D/E/F/G active, B rejected); Arjun reviewed and selected **Direction G — "Compact Toggle"**
(`docs/ux-mockups/direction-g-compact-toggle.html`, `docs/ux-spec.md` §7.4) as the final direction. INC-13
is now **IMPLEMENTED — merged to `main`.** See `docs/design/admin-portal.md` §16.10 for the updated
design content naming Direction G's exact reference files/details.

### INC-13 — Admin portal responsive & visual modernization (NFR8) — **IMPLEMENTED, reviewer Pass 35 CLEAR, merged to `main`**
(dev-built, qa-tested — PASS across a fix cycle, BUG-010/BUG-011 found and fixed; reviewer Pass 35 verdict CLEAR — REV-145/146/147 all RESOLVED, zero blockers/majors, `docs/review-log.md`; merged commit `da50ed8`, PR #46)
**Design:** `docs/design/admin-portal.md` §16.10 (breakpoints, layout mechanism, structural
enforcement rule, file allow-list). **Files:** `admin-portal/app/globals.css`, `admin-portal/app/
layout.tsx`, `admin-portal/app/(app)/layout.tsx`, `admin-portal/app/login/page.tsx`, `admin-portal/app/
(app)/watchlist/page.tsx`, `admin-portal/app/(app)/holdings/page.tsx`, `admin-portal/app/(app)/tunables/
page.tsx`, `admin-portal/app/(app)/track-record/page.tsx`, `admin-portal/components/AuthGuard.tsx`,
`admin-portal/components/KillSwitchToggle.tsx`, and at most one new presentational component (e.g.
`admin-portal/components/NavToggle.tsx`) — no other file, in any directory (`sql/`, `scripts/`,
`lib/*.ts`, `tests/`), is in scope. **No config-schema change** — presentation-layer only.

**Gate cleared 2026-07-31 (was: hard blocking dependency, distinct from the normal "no increment starts
before the previous passes QA" rule):** designer published `docs/ux-spec.md` with mockup directions
covering all five screens (login, watchlist, holdings, tunables, track-record), and the user (Arjun) has
selected **Direction G — "Compact Toggle"** (`docs/ux-mockups/direction-g-compact-toggle.html`,
`docs/ux-spec.md` §7.4, built on Direction F's density §7.3 and Direction E's toggle component §7.2).
**Dev may now begin a build plan for INC-13.** This increment plan entry defines the mechanism Direction
G is built through (breakpoints, responsive-table strategy, structural enforcement — unchanged by which
direction was picked, see `docs/design/admin-portal.md` §16.10); the acceptance criteria below now
reference Direction G specifically, per `docs/design/admin-portal.md` §16.10's detail on the exact
reference files dev implements against.

**Structural "no functional regression" enforcement:** every file above may only change CSS, JSX/TSX
markup, className/`data-label` attributes, and purely-presentational local component state. A `git diff`
grep across every touched file for `supabase\.|validateHoldingsRow|validateTunableValue|is_admin|
set_kill_switch|\.rpc\(|createClient` must return **zero** matches — this is acceptance criterion 5 below,
not a review-only convention.

**Acceptance criteria (dev self-verifiable):**
1. At three viewport widths — **375px** (phone band, ≤639px), **768px** (tablet band, 640–1023px), and
   **1280px** (desktop band, ≥1024px) — set via Chrome DevTools' device toolbar or
   `page.setViewportSize()` in a Playwright/qa script, each of the five screens plus the shared
   header/nav and kill-switch toggle renders with `document.documentElement.scrollWidth <=
   document.documentElement.clientWidth` (no page-level horizontal scrollbar) — confirmed for all five
   screens at all three widths (15 checks total).
2. At 375px, the watchlist and holdings `<table>`s render as a stacked card-per-row layout (no table-level
   horizontal overflow): every column's value is visible without sideways scrolling, each row carries a
   `data-label` attribute per cell matching its column header (grep `data-label=` in the rendered/source
   markup), and each row's edit/delete controls remain individually clickable/tappable.
3. At 375px and 768px, the shared nav collapses into a control that doesn't overflow the header's own
   width; every nav item (Watchlist, Holdings, Tunables, Track Record, sign-out) and the kill-switch
   toggle remain reachable by clicking/tapping that control — confirmed by driving each item via a qa
   script at both widths.
4. At 1280px, the layout is no longer capped at the pre-INC-13 fixed 900px `main` width — the watchlist
   and holdings screens render a **4-column** card grid (Direction G/F's desktop density,
   `docs/ux-spec.md` §7.3.2), matching `docs/ux-mockups/direction-g-compact-toggle.html` at a ≥1024px
   viewport (visual comparison against the mockup, not a fixed-pixel assertion beyond the column count).
5. **Structural enforcement:** `git diff --name-only main..inc-13-<slug>` contains only files from the
   allow-list above; `git diff main..inc-13-<slug> -- admin-portal/ | grep -E "supabase\.|
   validateHoldingsRow|validateTunableValue|is_admin|set_kill_switch|\.rpc\(|createClient"` returns
   **zero** matches.
6. Full existing `tests/admin_portal/*.test.ts` suite passes with **zero** assertion changes. qa
   additionally re-runs INC-5/INC-6/INC-7's manual regression checklist (auth gate + allowlist reject,
   watchlist/holdings CRUD writes confirmed in Supabase, tunables validation error paths, track-record
   pagination, kill-switch toggle round-trip producing a `kill_switch_audit` row) at all three viewport
   widths, confirming identical functional outcomes to pre-INC-13 — any difference is a regression, not a
   visual choice.
7. **Direction G visual conformance (`docs/ux-spec.md` §7.3/§7.4, `docs/ux-mockups/
   direction-g-compact-toggle.html`):** manual/qa visual comparison against the mockup at all three
   widths confirms: (a) flatter single-layer card shadows and the smaller `radius-md`/`radius-lg`
   tokens (8px/14px, not Direction C's 12px/20px) across watchlist, holdings, and track-record cards;
   (b) the tunables editor renders all 10 keys as always-visible compact cards with no
   expand/collapse — value input and Save visible without a tap; (c) every one of the 10 tunables cards
   shows the friendly-label heading from `docs/ux-spec.md` §2.3's mapping table as the primary heading,
   with the raw `SNAKE_CASE` key demoted to a small monospace subtitle directly beneath it (grep the
   rendered markup for all 10 raw keys still present, just visually secondary — confirms the mapping is
   presentational only, no key dropped).
8. **Kill-switch toggle-switch interaction (`docs/ux-spec.md` §7.4.2):** the kill-switch control renders
   as a sliding toggle-switch (track + thumb), not Direction F's static pill badge — grep
   `components/KillSwitchToggle.tsx` for a `.toggle` element (or equivalent class) rather than a bare
   `.pill` span. Clicking/tapping the toggle element pauses/resumes via the **existing**
   `set_kill_switch(..., p_source:='admin-portal')` Supabase RPC call already wired in INC-7 (§16.6) — no
   new backend logic, purely a visual-control swap (confirmed by AC5's grep showing zero
   `set_kill_switch`/`.rpc(` diff lines — the call site itself is unchanged, only its surrounding
   markup/CSS is). Toggling produces a new `kill_switch_audit` row exactly as INC-7 AC2 already proves;
   this AC only confirms the click target and visual state (slid right = running/emerald track, slid left
   = paused/grey track) match Direction G, reusing INC-7's existing round-trip proof rather than
   re-deriving it.
9. Best-effort accessibility (recorded, not a pass/fail gate per NFR8): keyboard-Tab reaches every
   interactive control in DOM order at all three widths; a quick manual contrast check on body text passes
   — recorded as a dated note in `docs/handoff.md`.

**Increments NOT made stale by NFR8:** none of INC-3–INC-12 touch admin-portal visual/layout code (INC-5/
INC-6/INC-7/INC-10 touched `admin-portal/app/**/*.tsx` for functional CRUD/validation/currency-derivation
work only, not styling) — all twelve remain valid and IMPLEMENTED as documented above. INC-11 (live
verification) is unrelated and unaffected. INC-13 is purely additive on top of the existing merged code.
