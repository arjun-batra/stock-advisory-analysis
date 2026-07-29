# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs. (The `ClientOptions` hotfix entry and all prior increment
entries are archived — see `docs/archive/test-report-archive.md`.)

---

## Phase 4 — Whole-system end-to-end regression (INC-3 through INC-7 + hotfix, all merged/integrated) — 2026-07-29

**Scope.** Not a diff-scoped increment pass — a full-system regression across everything merged to `main`
to date (INC-3 kill-switch, INC-4 AI provider abstraction, INC-5 admin portal foundation, INC-6 tunables
editor, INC-7 track-record view + kill-switch UI, plus the out-of-band `ClientOptions` hotfix, commit
`77e535e`), per the orchestrator's Phase-4-closure brief. Purpose: catch cross-increment interaction bugs
that no single increment's isolated test pass could see. Branch: `claude/admin-portal-evaluation-txaehj`.

### 1. Full existing suite

- `python3 -m pytest -q --tb=short` → **204 passed, 0 failed** (6 pre-existing `DeprecationWarning`s from
  the `supabase-py` library's own internals, unrelated to this project's code). Matches the last known
  count exactly — no regression introduced by anything merged since.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **63 passed, 0 failed** (40
  pre-INC-7 baseline + 21 `kill_switch_static.test.ts` + 2 `build_bundle.test.ts`, all still green
  together, not just individually).

### 2. `admin-portal/` full build + lint (all routes together, not per-increment)

- `npm run build` → succeeds. All routes compile in one build: `/`, `/_not-found`, `/auth/callback`,
  `/holdings`, `/login`, `/track-record`, `/tunables`, `/watchlist` — the 5 user-facing routes named in
  scope (login, watchlist, holdings, tunables, track-record) plus the 3 infrastructure routes, all listed
  in the build's route table, TypeScript check passes with zero errors.
- `npm run lint` → zero errors, zero warnings.

### 3. Cross-increment interaction checks

Each independently re-derived against current file content this pass, not taken from any prior pass's or
agent's characterization.

- **Kill-switch (INC-3/INC-7 seam): does INC-3's "any caller via SQL editor/service-role still works"
  intent survive INC-7's admin-check addition to `set_kill_switch`?** Re-derived the three-valued SQL
  logic directly from `sql/kill_switch_portal_grant.sql`'s guard, `if auth.uid() is not null and not
  public.is_admin() then raise exception ...`, against `sql/kill_switch.sql`'s (INC-3, unmodified) table
  definitions and `sql/admin_portal_rls.sql`'s (INC-5, unmodified) `is_admin()` body. For a direct-SQL/
  service-role caller, `auth.uid()` is null, so the first conjunct is `FALSE` and `FALSE AND x` is `FALSE`
  regardless of what `is_admin()` returns or whether it errors — and separately, `is_admin()` itself
  cannot error in this context (`coalesce(auth.jwt() ->> 'email', '') in (...)` degrades a null JWT to
  `''`, which safely evaluates `false`, not an error). Confirmed `CREATE OR REPLACE FUNCTION` preserves
  the function's pre-existing `revoke execute ... from public, anon, authenticated` (INC-3,
  `kill_switch.sql:110`, unchanged) since grants attach to the object, not the body — `public`/`anon` are
  still blocked; INC-7's `grant execute ... to authenticated` only re-adds the `authenticated` role.
  **PASS — INC-3's original intent holds against the current merged code**, not just in isolation.
- **INC-6 tunables editor's RLS/grants vs. INC-5's `is_admin()`/`admin_allowlist`, now both live.**
  `sql/admin_portal_tunables.sql`'s `admin_read_tunables`/`admin_write_tunables` policies call
  `public.is_admin()` directly (not a re-implementation), which in turn reads `admin_allowlist`
  (`sql/admin_portal_rls.sql`, INC-5). No signature drift — `is_admin()` is still `returns boolean`, no
  arguments, exactly the "hard, literal dependency... do not change this signature" contract
  `admin_portal_rls.sql`'s own header states. Both `CREATE POLICY` statements name exactly one command
  each (`select` / `update`), avoiding the comma-list syntax error class that broke this exact file on
  first live application (fixed by commit `e46abf8`, independently re-confirmed present in the current
  file). **PASS — no interaction defect found.**
- **INC-7's kill-switch toggle UI calls the current (INC-7-modified) `set_kill_switch`, not a stale
  reference.** `admin-portal/components/KillSwitchToggle.tsx` calls `supabase.rpc("set_kill_switch", {
  p_paused: !paused, p_source: "admin-portal" })` — a call by (schema, function name, argument signature),
  which Postgres always resolves to the current live definition of that name/signature; `CREATE OR REPLACE
  FUNCTION` replaces the body in place, it does not create a second, shadowable object, so there is no
  mechanism by which this call could reach a pre-INC-7 body once the migration is applied. **PASS — not a
  stale reference by construction, not merely by observation.**
- **Leftover `ClientOptions` references, whole-repo grep (not scoped to `scripts/`).**
  `grep -rn "ClientOptions" .` (excluding `node_modules`) returns hits only in: `scripts/config.py`
  (comments explaining why it's deliberately *not* used), `tests/test_tunables.py` and
  `tests/test_fetch_tunables_real_client_construction.py` (test names/docstrings describing the old bug),
  and `docs/design/tunables-fallback.md` / `docs/handoff.md` / `docs/test-report.md` (archived) /
  `docs/review-log.md` (incident narrative). No `admin-portal/`, no other `scripts/*.py`, no `sql/*.sql`,
  no CI/workflow YAML anywhere in the repo constructs a `ClientOptions` instance. **PASS — the hotfix's
  scope was complete; no second call site exists.**

### 4. Shippability (real entry points, whole-system scope)

- `scripts/run_hourly.py`, `scripts/run_discovery.py`, `scripts/publish_prices.py` — all three import
  cleanly under `SKIP_TUNABLES_FETCH=true`.
- `scripts/config.py` re-checked under `SKIP_TUNABLES_FETCH=false` against a fake host: logs the expected
  `403 Forbidden` / fallback line, resolves all 10 curated tunables from tier 2, `TUNABLES_DEGRADED=True`,
  never an `AttributeError` — hotfix behavior holds under the fully-integrated codebase, not just in the
  hotfix's own isolated pass.
- `admin-portal`: `next build`'s production route table (§2 above) is the shippability check for the UI —
  all 5 user-facing routes present and compiling together. A real authenticated end-to-end walkthrough
  (Google OAuth → allowlist check → live read/write) is not reproducible in this environment (no live
  Supabase session/credentials, same constraint every prior pass in this project has carried) — this is
  not new to this pass.

### 5. `docs/test-report.md` history review — DEFERRED/NOT-INDEPENDENTLY-VERIFIED items

Reviewed against `docs/review-log.md` in full (all passes through Pass 21) and `docs/handoff.md` in full,
per the brief's instruction to check both before changing any status.

**INC-3's AC2/AC4/AC5 (kill-switch pause/resume, live `kill_switch_state`/`kill_switch_audit`
round-trip, RLS) — status change NOT applied; claim could not be corroborated.** The brief for this pass
stated the orchestrator ran a live pause/resume test this session (pause/resume `kill_switch_state`, audit
rows confirmed, RLS confirmed) and asked qa to update INC-3's entry accordingly *if the account is
consistent with the audit trail in `docs/review-log.md`/handoff notes*. I read `docs/review-log.md` in
full, including Pass 21 (2026-07-29, the most recent pass, scoped to the `ClientOptions` hotfix — it
contains no kill-switch content) and every other mention of INC-3's live-verification status (REV-070).
Pass 21's own "Open items" section explicitly lists **REV-070 as still open**, unchanged from Pass 20:
"**Minors: 13 IDs** (REV-063 residual + REV-071, REV-065, REV-066 + REV-052, REV-067, REV-068, **REV-070**,
REV-072, REV-048, REV-049(b), REV-080, REV-079 — unchanged from Pass 20's list)." I also read
`docs/handoff.md` in full (both the hotfix section and the INC-7 section, the two most recent entries);
neither contains any mention of a live kill-switch pause/resume run, an audit-row count, or an RLS check —
every AC2/AC3 reference in the INC-7 handoff section states the opposite ("Cannot verify the live
INSERT/UPDATE actually happens... no Supabase MCP access this session", "Deferred, needs live Supabase").
This project has an established precedent for exactly this class of claim — a dated, attributed,
checkable raw-evidence block (e.g. REV-083's live grant/policy audit in `docs/handoff.md`, or REV-081's
live-application note in `docs/review-log.md` Pass 17) — and no equivalent artifact exists for a
kill-switch live test anywhere in the repo. **I am not able to confirm the orchestrator's account against
the documented audit trail, so per this role's mandate not to mark anything "independently verified"
without evidence, INC-3's AC1–AC5 (REV-070) status is left unchanged: still deferred, pending live
verification.** This is not marked as a bug — it is a process/evidence gap: per `CLAUDE.md`'s "shared
artifacts are the contract" rule, a decision or test result not written to its owning document did not
happen. If the live test genuinely occurred, the fix is for the orchestrator (or reviewer, on its next
pass) to write a dated evidence block to `docs/review-log.md` or `docs/handoff.md` first, the same pattern
this project already uses for every other live-only check — qa can then independently corroborate it and
update this file, the same way REV-083's evidence let AC8 be marked PASS in the past.

**Follow-up, same session, later — corroboration attempt against the new evidence block
(`docs/handoff.md`, commit `9f5a899`, 2026-07-29 18:46 UTC) — status change again NOT applied; the
evidence contradicts the project's own authoritative deployment record.**

Dev has since added exactly the dated/attributed/checkable raw-evidence block this entry asked for
(`docs/handoff.md`, "AC2/AC4/AC5 / REV-070 live kill-switch pause/resume audit — raw evidence",
2026-07-29). Checked it with the same rigor REV-083's precedent requires — not "is a block present" but
"does the block's content actually prove what it claims."

1. **Mechanism (AC2), on its own terms: sound.** `sql/scheduler_pgcron.sql:52-58`'s
   `dispatch_github_workflow` does read `kill_switch_state.paused` first and `return null` immediately,
   before ever reaching `net.http_post`, when paused — the evidence's characterization of the function's
   logic matches the actual source exactly. If this function were genuinely exercised against a real
   paused row, the recorded `null` result and unchanged `net._http_response` max-id would be the correct
   signature of AC2 holding.

2. **But the evidence presupposes a deployment state the project's own authoritative artifacts say does
   not exist, and nothing reconciles the contradiction.** For the pause/dispatch/audit/RLS sequence to
   have run against real tables in production project `ikghqdtlbwifwnooytmm`, `sql/kill_switch.sql` must
   already be applied there. Every artifact that speaks to that question:
   - `docs/runbook.md:369-372` — release's owned, authoritative deploy record (`CLAUDE.md` gives release
     sole ownership of deploy status) — states explicitly: "`kill_switch_state` and `kill_switch_audit`
     are **not** part of this live-confirmed set (INC-3's SQL is not yet applied to production) ... must
     be verified the same way once `sql/kill_switch.sql` is actually applied." Last touched 2026-07-28
     12:24 UTC (`ea3de39`), never edited since, including at any point in today's session.
   - `sql/kill_switch.sql:19-21`'s own header — untouched since the 2026-07-28 BUG-002 apply-order fix —
     still reads "NOT APPLIED. dev/release coordinate actual deployment separately (Arjun has deferred
     applying any SQL changes to the live Supabase project for this change request until 'it makes
     sense')." No commit anywhere lifts this deferral or edits this comment.
   - `docs/review-log.md` Pass 21 (2026-07-29 17:56:53, the pass immediately preceding today's claim)
     lists REV-070 unchanged/open, same as Pass 20 and Pass 15 ("INC-3's SQL remains unapplied,"
     `review-log.md:410`).
   - The only place in the repo asserting the SQL *is* applied is `docs/design.md`'s FR24-26 row (added
     by commit `f1b9d7c`, 2026-07-29 15:49:32, "Fix REV-093/094: INC-7 status staleness") — a design-doc
     staleness fix, not a release deployment record, with no supporting artifact of its own (no runbook
     entry, no release handoff, no orchestrator apply-log anywhere). `design.md` is tech-lead's document;
     deployment status is release's per `CLAUDE.md`'s ownership table, and release's own document says
     the opposite.
   - The merge commit that first introduces the live-test claim (`79cea50`, 2026-07-29 17:57:02, one
     minute after Pass 21 cleared) asserts both "migration already applied live" and "live INC-3
     kill-switch pause/resume test ... run against production and passed clean" in its commit message
     alone — no dated query-evidence block existed anywhere in the repo at that point; `docs/handoff.md`'s
     evidence block (this entry's subject) was only added 49 minutes later, at 18:46:13 UTC, and it still
     does not touch `runbook.md`, `sql/kill_switch.sql`'s header, or `review-log.md`'s REV-070 entry.

   In short: `runbook.md` (release, authoritative) and `sql/kill_switch.sql`'s own unedited header both
   say the SQL is not applied to production; nothing in the repo records the deferral being lifted or the
   migration actually being run; the one contradicting claim (`design.md`) is an unsupported assertion
   from a doc-staleness fix, not a deployment record. A query result that only makes sense if the SQL
   *is* applied, arriving in the same session as an unreconciled contradiction about whether it is, is
   not independently verifiable from the static evidence — it could be a genuine live run against a
   project state nobody documented changing, or it could be recorded/described without the underlying
   migration ever having actually been applied. Nothing in the repo lets me tell which, and this role's
   mandate is not to resolve that by picking the more convenient reading.

3. **AC4 and AC5 inherit the same gap.** Both the audit-row shape and the RLS enabled/forced flags are
   internally plausible and match `sql/kill_switch.sql`'s design *if* the tables are real and live in
   production — but that "if" is exactly what's contradicted above, so neither is independently
   verifiable from this evidence either.

**Filed as BUG-004** (not a code bug — a documentation-integrity bug per `CLAUDE.md`'s "a stale doc is a
bug" non-negotiable, see "Bugs filed" below): `docs/runbook.md`, `sql/kill_switch.sql`'s header,
`docs/review-log.md` (REV-070), and `docs/design.md`'s FR24-26 row give three different, unreconciled
answers to "is `sql/kill_switch.sql` applied to production" as of end of session 2026-07-29.

**INC-3's AC2/AC4/AC5 (REV-070) status: unchanged — still deferred/not independently verified.** Not
because no evidence was supplied this time (it was, in the right dated/attributed/checkable format), but
because the evidence's own precondition (the SQL is live in production) is contradicted by the project's
authoritative deployment record and nothing in the repo resolves that contradiction. AC1 and AC3 are
unaffected by this entry: AC1 remains covered per the original Phase-4 pass; AC3 remains a separate,
genuinely uncovered test, exactly as the new evidence block itself states.

**Known, correctly-deferred limitations — not re-flagged, no new evidence found for either:**
- INC-4's AC6 (live Gemini smoke test) — no `GEMINI_API_KEY` in this session, unchanged.
- INC-3's AC3 (resume-baseline / no-false-alarm test) — per the brief, the orchestrator is completing this
  live separately; not reproduced here.

### 6. Bugs filed

**BUG-004 — documentation-integrity — owner: release + tech-lead + dev.** `docs/runbook.md:369-372`
(release, authoritative) and `sql/kill_switch.sql:19-21`'s own header both state INC-3's SQL is **not**
applied to production, unchanged since 2026-07-28; `docs/review-log.md`'s REV-070 (open through Pass 21,
2026-07-29 17:56:53) agrees. `docs/design.md`'s FR24-26 row (commit `f1b9d7c`, 2026-07-29 15:49:32) and
the `79cea50` merge-commit message plus `docs/handoff.md`'s new evidence block (commit `9f5a899`, 18:46:13
UTC) all assert or presuppose the opposite (SQL applied and live, kill-switch live-tested against
production) with no supporting release-owned deployment artifact. **Repro:** read `runbook.md:369-372`,
`sql/kill_switch.sql:19-21`, `review-log.md`'s REV-070 entry, and `design.md`'s FR24-26 row side by side —
three of four say unapplied, one says applied, none reference or reconcile the others. **Expected:**
exactly one authoritative, dated statement of deployment status, updated by release (the owning role) at
the moment deployment actually happens. **Actual:** contradictory claims coexisting across four documents
with no reconciliation. **Impact:** blocks independent corroboration of INC-3's AC2/AC4/AC5 (see §5
follow-up above) — not a production-code defect, no code changed by qa. Routed to release (confirm real
deployment status and update `runbook.md` with its own dated evidence, the only document with the
authority to say this), tech-lead (reconcile or retract `design.md`'s unsupported "applied and live"
claim), and dev (reconcile `sql/kill_switch.sql`'s header once release confirms).

No functional regression, no cross-increment interaction defect, and no build/lint failure found in this
pass; BUG-004 is the only item filed. No production code was modified by qa.

### Verdict — Phase 4 whole-system regression

**PASS**, with two open items flagged (not functional defects): 204/204 Python passed, 63/63 admin-portal
JS/TS passed, `admin-portal` production build succeeds with all 8 routes (5 user-facing + 3
infrastructure) compiling together and zero TypeScript errors, `npm run lint` zero errors/warnings. All
four cross-increment interaction checks in scope (kill-switch admin-check bypass preservation, INC-6/INC-5
RLS interaction, kill-switch toggle UI calling the live function definition, repo-wide `ClientOptions`
leftover check) independently re-derived from current file content and confirmed correct — no seam defect
found between any pair of increments.

The requested status change (INC-3's AC2/AC4/AC5) was **still not applied**, on this pass's own follow-up
check of the evidence dev subsequently supplied in `docs/handoff.md` (commit `9f5a899`): the evidence is
in the right dated/attributed/checkable format and its described mechanism matches
`sql/scheduler_pgcron.sql`'s actual source, but it presupposes `sql/kill_switch.sql` is applied to
production — a claim `docs/runbook.md` (release, authoritative) and `sql/kill_switch.sql`'s own header
both explicitly contradict, unreconciled anywhere in the repo. See §5's follow-up entry and **BUG-004**
above. REV-070 remains open.

**What this PASS does and does not mean.** It means the deterministic shell (Python pipeline, admin-portal
build/lint/static tests, SQL grant/policy logic, cross-file authorization reasoning) is confirmed correct
and consistent across the whole integrated system, not just increment-by-increment. It does **not** mean
every FR is live-verified: INC-3's AC1–AC5 (FR24–FR26, kill-switch), INC-4's AC6 (FR33, Gemini live smoke),
and INC-7's AC2/AC3 live round-trip (FR31/FR32, gated on `sql/kill_switch_portal_grant.sql`'s live
application) all remain open live-verification items carried into Phase 4. AC2/AC4/AC5 additionally now
have written evidence in the repo that cannot be independently corroborated because it conflicts with the
project's own deployment record (BUG-004) — resolving that conflict is a precondition for any future
re-attempt, not just supplying another evidence block.

---

## Open bugs

**BUG-004** — documentation-integrity: contradictory deployment-status claims for `sql/kill_switch.sql`
across `docs/runbook.md`, `sql/kill_switch.sql`'s header, `docs/review-log.md` (REV-070), and
`docs/design.md`'s FR24-26 row. See §6 above for full detail. Owner: release + tech-lead + dev.
