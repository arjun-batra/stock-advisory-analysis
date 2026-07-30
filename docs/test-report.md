# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-10 — BUG-008 fix-cycle-1 re-test — 2026-07-30

**Scope.** Re-test of INC-10 (FR30, FR11, FR29; DEEP-005+DEEP-006 — full original verdict archived,
`docs/archive/test-report-archive.md`) after dev's fix-cycle-1 for BUG-008 (SQL idempotency). Read
`docs/handoff.md`'s "BUG-008 fix (fix cycle 1 of 3)" section, `sql/tunables_validate_trigger.sql`,
`sql/holdings_currency_derivation.sql` as they now stand, and this file's own prior BUG-008 entry. Dev
changed approach mid-work: an intermediate `drop trigger if exists` + `create trigger` version was
briefly committed (`a500b37`), superseded by dev's final answer at `19013e2`, `create or replace trigger`
— qa's own originally suggested fix. 1 of 3 fix cycles used.

### 1. Independent re-verification of the double-apply property

Did not inherit dev's verification claim. Started a fresh local Postgres 16.13 instance (this repo's
reference Postgres, matching dev's own environment), built a scratch database with `watchlist`/`holdings`
(per `sql/schema.sql`) and `sql/admin_portal_tunables.sql` applied verbatim (stubbing `auth.jwt()`/
`is_admin()`, live-Supabase-only functions), then for each of the two fixed files independently:

- Applied once — succeeded (`CREATE FUNCTION` / `CREATE TRIGGER`).
- Recorded object state: `pg_trigger` fire order (`tunables_0_validate_update` before
  `tunables_stamp_update`, confirmed via `tgname` ordering query) and function OIDs (`_validate_tunable_
  update`=24813, `_derive_holdings_currency`=24815).
- Inserted one holding per market (US/TSX/NSE, all submitted with `currency='USD'`) — confirmed derivation
  to `USD`/`CAD`/`INR`.
- **Applied each file again, verbatim — both second applies succeeded, exit code 0, no error.** BUG-008's
  exact repro (`trigger "..." already exists`) no longer reproduces.
- Re-checked object state after the second apply: **trigger fire order unchanged, function OIDs
  unchanged** (identical to before), **row data byte-identical** (`tunables.updated_at`/`updated_by` and
  all 10 values unchanged; `holdings` rows unchanged).
- Re-confirmed behavior after the second apply, not just object metadata: `DISCOVERY_GAINER_PCT='5%'` and
  `ALERTS_ENABLED='tru'` still rejected; a rejected write still leaves `updated_at`/`updated_by` untouched;
  a direct `UPDATE holdings SET currency='USD'` on the TSX row is still overridden back to `CAD`; a ticker
  absent from `watchlist` still raises `holdings.ticker % has no matching watchlist row`.
- Scratch database dropped, local Postgres cluster stopped after verification; nothing left running.

**Confirms dev's report exactly** (trigger fire order, function OIDs, row data, behavior all independently
re-verified unchanged, not accepted on trust). **BUG-008 is genuinely fixed — RESOLVED 2026-07-30.** Full
original bug text moved to `docs/archive/test-report-archive.md` with this closure noted.

### 2. Atomicity reasoning — assessed, holds

Dev's stated reason for preferring `create or replace trigger` over drop-then-recreate: it is one atomic
DDL statement, whereas `drop trigger` + `create trigger` are two separately auto-committed statements
under `psql -f` (no `-1`/`--single-transaction`), leaving a window where a concurrent write could commit
while the trigger is absent. **Empirically confirmed, not just reasoned about:** re-running `psql -f`
against both files in this pass showed two distinct command tags per file (`CREATE FUNCTION` /
`CREATE TRIGGER`), consistent with each top-level statement auto-committing independently absent an
explicit transaction wrapper — the window dev describes is real under that invocation method. Postgres DDL
is transactional, so a single `create or replace trigger` statement has no such window by construction
(MVCC hides the catalog change from other sessions until commit, and there is only one statement to
commit). One nuance worth naming: `docs/runbook.md` §2.3 specifies live application via the Supabase SQL
Editor or `supabase db push`, not raw `psql -f` — a multi-statement string sent as one round trip may be
implicitly transactional under either of those paths, which would narrow (not eliminate) the gap
drop-then-recreate exposes. This doesn't weaken the conclusion: `create or replace trigger` is atomic
under every plausible application method at zero behavioral cost beyond the version floor addressed in
§3 below, so it is the strictly safer choice regardless of which deployment path is actually used. **Dev's
reasoning holds.**

### 3. Stale assertion — fixed, chose the property over the syntax

`tests/admin_portal/tunables_static.test.ts:144-153` hard-coded a regex matching only literal
`create trigger`, broken by the `create or replace trigger` fix. Dev's suggested minimal fix (relax to
`create (or replace )?trigger`) was applied to restore the fire-order test's own property (trigger name
sorts before `tunables_stamp_update`) — that assertion is still worth keeping, syntax-relaxed.

**But also went further, per this task's instruction to consider testing the property that actually
matters.** Added a new permanent test to each affected file's static-check suite —
`tunables_static.test.ts` (for `sql/tunables_validate_trigger.sql`) and `static_source_checks.test.ts`
(for `sql/holdings_currency_derivation.sql`) — asserting the file's trigger-creation statement is
literally the idempotent `create or replace trigger` form, not a bare `create trigger` (SQL comments
stripped before matching, since both files' own BUG-008 explanatory comments mention the literal string
`create trigger` in prose). This is a direct regression guard for BUG-008 itself: **verified it actually
fails** against a bare `create trigger` (reverted `sql/tunables_validate_trigger.sql` locally, confirmed
the new test fails, restored the file — `git diff` on the SQL files is clean, qa never edits production
code) and passes against the real fixed file. Chose to add this rather than only relax the regex because
the regex-only fix tests syntax; this test tests the property the whole bug was about (re-runnability),
so a future regression to bare `create trigger` in either file is now caught immediately rather than only
resurfacing on a live re-apply.

### 4. PG14+ dependency — residual risk, explicit INC-11 prerequisite

`create or replace trigger` requires Postgres 14+. Dev could not confirm the live Supabase project's
actual major version (no live access this session) and said so plainly, offering circumstantial evidence
only: qa's original BUG-008 repro ran on local PG16, this environment's reference Postgres is PG16
(confirmed again this pass — 16.13), and Supabase's current default for active projects is PG15+. **That
is inference, not confirmation**, and qa did not attempt to confirm it against the live project (out of
scope — no live application performed, per this task's explicit instruction).

**Position:** this is an acceptable residual risk to carry into INC-11, not a blocker for closing
BUG-008 or clearing INC-10. Nothing in `docs/` gives any reason to expect the live project predates PG14,
the syntax has been independently re-verified correct wherever it can be tested (local PG16, twice, by
two different agents), and neither file has been applied live yet — so no live object is at risk today.
However, since the fix's correctness is conditional on a fact nobody in this pipeline has actually checked
against the live project, **this must not be silently assumed true at apply time.** Flagging as an
explicit prerequisite so it cannot be forgotten:

> **INC-11 prerequisite:** before applying `sql/tunables_validate_trigger.sql` or
> `sql/holdings_currency_derivation.sql` to the live Supabase project, confirm the project's Postgres
> major version is 14 or later (e.g. `select version();` via Supabase SQL Editor/MCP). If it is not,
> both files' `create or replace trigger` statements will fail outright on first apply (a hard,
> immediately-visible error, not a silent bad state) and must fall back to a guarded form
> (`drop trigger if exists` + `create trigger`, accepting the narrower atomicity window discussed in §2)
> before proceeding.

### Regression suite

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **249 passed, 0 failed** (unchanged from
  baseline — SQL-only fix, no Python touched).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed** (79/1
  baseline going in — regex relaxed to restore the 1 failure, +2 new BUG-008 regression-guard tests).
  Both required green suites (**249 Python / 82 TypeScript, 0 failed each**) restored.
- Shippability: `SKIP_TUNABLES_FETCH=true python3 -c "import run_hourly, run_discovery, publish_prices"`
  → clean import, all three entry points unaffected (this fix touches only `sql/` and `tests/`).
  `cd admin-portal && npm run build` → succeeds, all 7 routes compile.

### Verdict — INC-10

**PASS. BUG-008 CLOSED (resolved 2026-07-30, fix-cycle-1).** INC-10 is clean: all AC1-AC8 previously
independently verified (archived run), BUG-008 was the sole open item and is now independently
re-verified fixed (not accepted on dev's account), the one test-suite casualty of the fix (the stale
regex) is repaired and strengthened rather than merely patched, and the PG14+ dependency is carried
forward as a named, explicit INC-11 prerequisite rather than a silent assumption. No new bugs filed this
pass. Reviewer is next; INC-11 and INC-12 remain after that.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — INC-10 touched
no `ai_judge.py` code. Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry
(repro: `tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_
undocumented_elsewhere`). **Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return
contract, if ever addressed).
