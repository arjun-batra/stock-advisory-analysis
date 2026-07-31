# Retrospective — Stock Advisory Agent, through `v0.1.0`

**Scope:** delivery process, not features. Mined from `docs/review-log.md` (+ archive),
`docs/test-report.md` (+ archive), `docs/handoff.md`, `docs/requirements.md` and `git log`.
Five findings, ordered by evidence weight.

---

## F1 — Increment status is restated in prose across 5+ files, and goes stale every single time

**Evidence.** 31 distinct review findings across the project's life are status-marker staleness:
REV-017, 021, 022, 023, 025, 026, 028, 029, 030, 032, 065, 079, 082, 084, 085, 087, 088, 089, 090,
093, 103, 106, 108, 110, 111, 116, 117, 118, 121, 122, 125. That is the single largest recurring
category in the log — larger than any code-defect class. In the `/big-guns` round alone it produced
REV-108, 110, 111, 115, 121, 122, 125, and needed four separate tech-lead passes to clear.

**Root cause.** `docs/design.md`'s banner and module map, each `docs/design/*.md`'s own status line,
`docs/design/increment-plan.md`'s per-increment heading, `docs/code-map.md`, and inline repo-map
comments each restate an increment's status *in their own words*. Nothing owns the fact, so every
reviewer pass invalidates 5-8 independently-phrased copies. `CLAUDE.md` already states the correct
rule — "state anything once, reference by ID elsewhere" — but never applies it to status, which is
the most volatile fact in the project.

**PROPOSED TEMPLATE EDIT** — `CLAUDE.md` (Document hygiene section) and `.claude/agents/tech-lead.md`:

> Increment status (built / qa verdict / reviewer pass + verdict) is recorded in **exactly one place**:
> `docs/design/increment-plan.md`'s `### INC-N` heading. Every other document — `design.md`'s banner and
> module map, module files, `code-map.md` — references the increment by ID and must not restate its
> status in its own words. A status sentence outside `increment-plan.md` is a bug.

---

## F2 — Local verification ran a strictly weaker check than CI, and nobody noticed for a whole round

**Evidence.** `.github/workflows/audit.yml` runs two ruff invocations: `ruff check .` **and**
`ruff check --select C90 .`. Every agent ran only the first. dev, qa and release each reported "lint
passes" — release explicitly recorded "Python linting (Ruff): All checks pass" — while `main` was red
on every push for the entire round. Bisect: clean at `087f5dd` and `f66d693`; `_parse_batch` hit
complexity 16 at `f2fdb1e`; `run_discovery.main` hit 12 at `530c687`. Caught only when the user
forwarded a GitHub failure notification, *after* Phase 4 closure had passed with three agents
reporting clean. Logged as REV-140, still open.

**Root cause.** `.claude/agents/dev.md` rule 5 says "run the FULL existing test suite". It says nothing
about running *what CI runs*. A project can add a gate to CI that no agent ever executes locally, and
every pipeline verification will still report green.

**PROPOSED TEMPLATE EDIT** — `.claude/agents/dev.md` rule 5, and the matching rule in
`.claude/agents/qa.md`:

> Before EVERY handoff: run the full test suite **and every other check the project's CI runs** — read
> the CI config (e.g. `.github/workflows/`) and execute each check command it invokes, not a
> subset you assume is equivalent. If a CI check cannot run locally, say so explicitly in the handoff
> rather than reporting the suite as clean.

---

## F3 — Artifacts that only execute in a live environment were cleared by reading, then failed on apply

**Evidence.** Three separate live-only defects, all in SQL, all after review clearance:
1. `CREATE POLICY ... FOR select, update` — invalid Postgres, reviewer-cleared at Pass 19, discovered
   only when applied live; required a Pass 19 addendum.
2. **BUG-008** — neither new INC-10 file re-applied cleanly (`create trigger` lacks `or replace`).
   Found by qa standing up its own Postgres and applying twice, *after* dev had already verified them.
3. **REV-117** — `kill_switch_abort_log.sql`'s REVOKE omitted `truncate`. Found at Pass 28, while the
   file was queued for a live apply that would have shipped an open TRUNCATE grant to production.

**Root cause.** No rule requires that an executable artifact actually be executed before it is cleared.
Reading SQL, IaC or migrations is not verification of them.

**PROPOSED TEMPLATE EDIT** — `.claude/agents/qa.md` and `.claude/agents/reviewer.md`:

> An artifact that executes somewhere other than the test suite — SQL migration, IaC, deploy script —
> is not verified by reading it. Before it can be cleared, it must be **executed** against a local or
> scratch instance of the same technology, and where re-runnability matters, applied **twice**. Record
> what was executed and observed, not that it was inspected.

---

## F4 — The same security-posture gap recurred five times because each new object was written from scratch

**Evidence.** The "RLS never governs TRUNCATE in Postgres" gap was found and fixed independently on
five objects: `admin_allowlist` (REV-081), `tunables` (REV-086), `kill_switch_state`/`kill_switch_audit`
(`kill_switch_portal_grant.sql`), six further tables (REV-099, rated **major**), and
`kill_switch_abort_log` (REV-117, also major). Each fix was correct; none prevented the next. tech-lead
eventually generalised it to `design.md` §0 rule #12 — after the fifth occurrence.

**Root cause.** Each new table's security block was written fresh from the design's code sample rather
than derived from an existing sibling that had already absorbed prior findings — and the design's own
sample carried the defect forward.

**PROPOSED TEMPLATE EDIT** — `.claude/agents/dev.md`:

> When adding a new object of a kind that already exists in the project (a table, endpoint, job,
> migration), open the most recently reviewed sibling and mirror its established posture — grants,
> auth, error handling — rather than writing from the design's illustrative sample. Design samples lag
> behind review findings. If your new object differs from the sibling, say why in the handoff.

---

## F5 — `reviewer` is required to maintain an archive it is forbidden to read

**Evidence.** `.claude/agents/reviewer.md` line 24 requires moving RESOLVED entries to
`docs/archive/review-log-archive.md`; `CLAUDE.md` states "Agents never read `docs/archive/`". The
contradiction produced REV-127 — four still-open findings (REV-097, 100, 101, 102) had their full text
moved into the archive while still open, making them invisible to anyone reading the live log — and
REV-136, reviewer's own report that it structurally cannot perform the move. Repair required the
orchestrator granting a scoped one-time exception mid-closure.

**Root cause.** An agent cannot safely edit a file it may not read, so archive moves are either skipped
or done blind.

**PROPOSED TEMPLATE EDIT** — `.claude/agents/reviewer.md` and `CLAUDE.md`:

> The archive-read ban does not apply to an artifact's own owner performing hygiene on it. `reviewer`
> may read `docs/archive/review-log-archive.md` solely to move entries or verify what was moved, and
> must never move an entry that is not marked RESOLVED. The same exemption applies to `qa` for
> `test-report-archive.md` and `pm` for the requirements changelog archive.

---

## Not proposed as template changes

- **Fix-cycle count** (INC-9: 2, INC-10: 2, INC-12: 1) is *not* evidence of weak acceptance criteria.
  In every case the extra cycle came from a test or audit deliberately pushed **beyond** the stated
  ACs — BUG-005, BUG-006, BUG-008 and REV-113 were all found that way. The template should not
  discourage this; it is the round's most valuable behaviour.
- **The deferred live checks** (INC-3 AC3, INC-4 AC6, INC-7 AC2/AC3) resolved correctly once
  Decision #36 forced them onto the closure path. Project-specific, no template change.
- **`ai_judge.py` at 467 lines** vs the ~300 guideline — project-specific, tracked as REV-137.
