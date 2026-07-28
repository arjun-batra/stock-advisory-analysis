# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–9 (2026-07-12 through 2026-07-25) — archived

Passes 1–9 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene rule
("reviewer: on clearing an increment, move RESOLVED entries to `docs/archive/review-log-archive.md`").
Passes 1–6 were archived 2026-07-25 when REV-022 (Pass 6's one remaining open item) was independently
confirmed RESOLVED. Passes 7–8 were archived the same day, at Pass 9's close, once their combined open
items (REV-023 through REV-027) were all independently confirmed RESOLVED. Pass 9 itself was archived
2026-07-25 at this Pass 10's close, once its five open items (REV-028 through REV-032) were all
independently confirmed RESOLVED — see the Pass 10 entry below for the closing verification. Nothing from
Passes 1–9 remains open. Agents never read `docs/archive/` per `CLAUDE.md`.

---

## Pass 10 — 2026-07-25 (final closing verification: REV-023–REV-032 chain, Passes 7–9)

**Scope:** last pass in the template-conformance audit chain that started at Pass 7. Independently
re-verify REV-028 through REV-032 (Pass 9's five open minor items) against current file state, re-run a
fresh repo-wide grep for the two defect classes that recurred across this whole chain (stale
`design.md §13–18` citations, stale `requirements.md §11` citations), and do one broader sanity sweep for
any `design.md §<N>` citation this chain hasn't already checked. Relevant commits: `6b0f077` (REV-028's
four originally-flagged instances, REV-029, REV-030) and `45bb3b2` (a fifth REV-028 instance dev caught
independently, plus REV-031 and REV-032).

### 1. Independent re-verification of REV-028 through REV-032

- **REV-028 (`docs/handoff.md`, dangling `§18.4`/`§18.5` citations, owner dev).** Read `docs/handoff.md` in
  full (102 lines). Zero `§18` references remain anywhere in the file — all four originally-flagged
  citations (former lines 78, 81, 92, 99) now name the "Retired: shadow-pilot tracks" note directly, no
  number, and the fifth instance the task flagged (former line 54, inside the "New file" section) also
  reads correctly today (that line now cites "design §8," an unrelated, still-valid section, not §18) —
  confirmed the 5th-instance fix landed. **RESOLVED**, confirmed by direct read, not by commit message.
- **REV-029 (`docs/test-report.md:35`, dangling `§18`, owner qa).** Read `docs/test-report.md` in full.
  Line 35 (renumbered slightly in the current file but the same sentence) now reads "...marked 'Phase 6 —
  Shadow Pipeline' (P6-1..P6-5) RETIRED with a pointer to the 'Retired: shadow-pilot tracks' note in
  `docs/design.md`" — no stale `§18` number. **RESOLVED**, confirmed by direct read.
- **REV-030 (`qa/test-plan-full-codebase.md:103`, P4-5's stale `§4.6`, owner qa).** Read the P4-5 row
  directly: now cites "`docs/design/components.md` §4.6," matching P1-2's already-correct form for the
  identical fact exactly, as REV-030 asked for. **RESOLVED**, confirmed by direct read.
- **REV-031 (`docs/runbook.md:86`, wrong-section CORS citation, owner release).** Read the §2.3 table row
  directly: now cites "`docs/design/frontend.md` §11 and `docs/requirements.md` Decision #18" for the
  CORS/`prices.json` workaround — the correct module and section (an exact content and Decision-number
  match, as REV-031 specified). **RESOLVED**, confirmed by direct read.
- **REV-032 (`README.md`, stale handoff/runbook claim, owner pm).** Read the "How to run" note in full: it
  now correctly states `docs/runbook.md` exists, is "the dedicated deploy runbook, owned by release,
  covering general deploy procedure — not to be confused with `docs/handoff.md`, which covers only the
  shadow-tracks-removal increment." The SQL migration-order `(inferred)` marker is gone, replaced with a
  direct citation to `docs/runbook.md` §2.3 and the exact apply order. The Python-version item, which
  REV-032 said could "stay as-is or be resolved," was resolved: it now cites `python-version: "3.12"`
  directly from the three cron-triggered workflow files, explicitly noting `docs/runbook.md` itself doesn't
  state a Python version. **RESOLVED**, confirmed by direct read.

All five are logged RESOLVED with today's date and commit citations in the closure disposition appended to
the archived Pass 9 entry (`docs/archive/review-log-archive.md`).

### 2. Fresh repo-wide grep for the two recurring defect classes

Grepped the whole repo (excluding `.git/`, `docs/archive/`, `requirements_docs/`) for
`design\.md.{0,10}§(1[3-8])` and `requirements\.md.{0,15}§11`:

- **`design\.md.{0,10}§(1[3-8])`:** zero live hits. The only matches anywhere in the repo are inside
  `docs/archive/review-log-archive.md` (historical narrative, out of scope) and `docs/review-log.md`'s own
  Pass 9/10 narrative text describing the historical defect (not a live citation pointing a reader at a
  dead section).
- **`requirements\.md.{0,15}§11`:** zero live hits. The only matches are inside
  `docs/archive/review-log-archive.md`/`docs/archive/test-report-archive.md` (historical, out of scope) and
  `docs/requirements.md`'s own changelog describing its own history (an accepted exception carried since
  Pass 9). `docs/review-log.md`'s own narrative text (this file, describing the historical defect) also
  matches but is not a live citation.
- **A broader unprefixed sweep** for bare `§1[3-8]` and `§11` (not requiring a `design.md`/`requirements.md`
  prefix, to catch any citation whose wording drifted) turned up additional hits, all confirmed benign on
  inspection: `pages/dashboard.html:71,171` and `sql/dashboard_latest_call_view.sql:2,43` cite **`SD §13`**
  — the *Solution Design* document (`requirements_docs/SD.md`), a completely different, separate historical
  document that was never renumbered as part of this chain (its own §13 genuinely still exists and is
  correct); `docs/requirements.md:131` similarly cites `SD §13`, same story. `docs/requirements.md`'s own
  changelog (lines 283–284) uses bare "§11" referring to its own past self, already an accepted exception.
  `docs/design/frontend.md`, `docs/design/foundations.md`, `docs/design/non-functional-ops.md`, and
  `docs/design.md` itself all correctly cite the **new**, correct `frontend.md §11` (CORS section,
  post-split) — not stale. No genuine hit of either defect class found anywhere live.

**Zero hits outside the already-accepted exceptions. This chain is done.**

### 3. Broader sanity sweep — `design.md §<N>`, any section number

Grepped the whole repo for `design\.md §` (any number) and spot-checked four hits not already checked in
Pass 9's own sweep or in step 1/2 above:

- `CLAUDE.md:53` and `.claude/commands/spin-up-team.md:65` — both contain the identical illustrative
  example string "e.g., 'implement INC-3 per design.md §4; files: src/x.py, src/y.py'" inside the
  pipeline-template documentation itself (describing how *any* subagent brief should cite a document, in
  the abstract). Not a citation into this project's actual `docs/design.md` content and not asserting
  current section state — not a stale citation, no defect.
- `tests/test_state.py:3` — "docs/design.md §0 #1/#2" — §0 (load-bearing decisions) correctly stayed in the
  thin index post-split and was never renumbered. Correct, already independently confirmed in Pass 9's own
  read of this file (docstring/comment-only edits, no logic change since).
- `docs/design.md:24` — the module map's own row for "this file": "§0, §15" — matches the file's actual
  `## 0` and `## 15` headers exactly, already confirmed accurate in Pass 9's full read.

No further staleness found in this broader sweep.

### 4. Test suite — same standing method caveat as every prior pass

No shell/execute tool was available this session, so `python3 -m pytest -q --tb=short` could not be run
directly. No `tests/` files changed since Pass 9's last structural comparison (only `docs/`-tree files were
touched by the REV-028/029/030/031/032 fixes, confirmed by which files were read/checked above), so Pass
9's "still 144/144" conclusion stands unchanged; not re-derived independently this pass since nothing in
its evidentiary basis (`scripts/`, `tests/` file listings) could have changed. Same standing recommendation
carried since Pass 2: the orchestrator or qa should execute `pytest -q` directly for a machine-verified
confirmation.

### Chain closure

**REV-023 through REV-032 — the entire template-conformance audit chain spanning Passes 7, 8, and 9 — is
now fully resolved. Zero open items remain from this chain.** Pass 9 (with the REV-028–032 closure
disposition appended) is archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s
doc-hygiene rule, alongside Passes 1–8 already archived there.

### Pass 10 summary

**New findings by tag:** none. Zero new `[BLOCKER]`/`[MAJOR]`/`[MINOR]` findings of any tag surfaced during
this closing verification — the fresh sweep for both recurring defect classes and the broader sanity sweep
both came back clean.

**Resolved this pass:** REV-028 (dev, `6b0f077`+`45bb3b2`), REV-029 (qa, `6b0f077`), REV-030 (qa,
`6b0f077`), REV-031 (release, `45bb3b2`), REV-032 (pm, `45bb3b2`) — all five independently re-confirmed by
direct read of current file state, not taken on commit messages alone.

**Open blocker count: 0.**
**Open major count: 0.**
**Open minor count: 0.**

### Verdict — Pass 10

**CLEAR. The REV-023–REV-032 chain (Passes 7 through 9) is genuinely, fully closed — 0 blockers, 0 majors,
0 minors open from this chain or from any prior pass.** Nothing from before Pass 7 remains open either
(confirmed by the archive's own header note, itself independently re-checked this pass by reading
`docs/archive/review-log-archive.md`'s front matter). The review log (`docs/review-log.md`) currently holds
only this Pass 10 entry, with zero open items — the pipeline is clear to continue with no reviewer-side
blockers pending anywhere in the codebase.

---

## Pass 11 — 2026-07-28 (proactive whole-system architecture & efficiency audit)

**Requested by:** Arjun, via the orchestrator. **Nature:** deliberately broader than both the per-increment
diff-scoped pass and the standard Phase-4 closure audit. In addition to the five standard passes, this one
hunts for *inefficiencies, redundancies, over-engineering, silent-failure modes, and duplicated state that
must be manually kept in sync* — the failure class Arjun caught personally during the 2026-07-27/28
tunables design pass (a default value living in three places at once).

**Scope read in full this pass:** every file under `scripts/` (8 modules), `sql/` (4 files), `tests/` (9
files), `pages/` (3 files), `.github/workflows/` (4 files), `requirements.txt`, `.gitignore`, `README.md`;
`docs/design.md` + all 8 modules under `docs/design/` (including the three DRAFT modules for INC-3–INC-7);
`docs/requirements.md`, `docs/idea-brief.md`, `docs/runbook.md`, `docs/handoff.md`, `docs/test-report.md`.

**Deliberately NOT re-flagged** (already found and fixed 2026-07-28, or already documented as an accepted
risk): the `ALERTS_ENABLED` seed-value bug (`admin-portal-tunables.md` §16.4 "Seed migration"); the removed
third hardcoded-literal fallback tier; idea-brief accepted risks #1–#8 as such (the Supabase SPOF, the
client-side dashboard gate, holiday calendars, no spam control, the CORS/`prices.json` posture, Decision
#17's ungated detail page). Where an accepted risk has a genuinely *new* dimension, that dimension is
logged and the accepted part is explicitly excluded.

**Method caveat (standing, unchanged since Pass 2):** no shell/execute tool this session, so `pytest -q`
was not run and no live Supabase introspection (`list_tables`, `get_advisors`) was possible. Every finding
below is derived from direct file reads, cited by `file:line`. Findings REV-033 and REV-034 in particular
should be **confirmed against the live project** before or alongside remediation — the repo alone cannot
prove the live RLS posture, which is itself REV-035.

---

### BLOCKER

**REV-033 — `[SECURITY]` — blocker — every new table in the DRAFT increments creates RLS policies without
ever enabling RLS.**
Location: `docs/design/operational-controls.md:56-73` (`kill_switch_state`, `kill_switch_audit`);
`docs/design/admin-portal.md:49-59` (`admin_allowlist`); `docs/design/admin-portal-tunables.md:40-67`
(`tunables`). Live instance: `sql/phase5_monitoring.sql:17` (`monitor_alerts`).
Description: none of the four new tables' DDL contains `alter table … enable row level security`. In
Postgres a `create policy` is **inert** until RLS is enabled on the table, and Supabase's default grants
expose every `public`-schema table to the `anon` and `authenticated` roles through PostgREST. The anon
publishable key is published in this repo (`pages/dashboard.html:102`, `pages/detail.html:51`), so as
drafted:
- anyone could `update public.kill_switch_state set paused = true` and **silently pause the entire
  pipeline** — FR25 then correctly suppresses the dead-man monitor, so the outage is invisible;
- anyone could `insert into public.admin_allowlist` their own email and become "the admin", defeating
  `is_admin()` and therefore **every** RLS policy in INC-5/6/7 at once (§16.2 calls `is_admin()` "the single
  source of truth for who is allowed to write" — it is only as strong as the table it reads);
- anyone could rewrite `public.tunables` (including `GEMINI_MODEL` and `ALERTS_ENABLED`);
- `kill_switch_audit`'s "append-only, never updated/deleted" property (§13.2) is asserted in a comment and
  enforced by nothing.
The live `monitor_alerts` table has the same omission in its committed DDL, which contradicts
`docs/design/data-and-flow.md:66` ("RLS is on for every table") — that claim cannot be verified from the
repo (see REV-035) and should be checked against the live project.
Note this is *not* a lapse of convention — the same files revoke `execute` from `public, anon,
authenticated` on every `SECURITY DEFINER` function, correctly and consistently. The table-level equivalent
was simply never written down.
Suggested fix: for each new table, add `alter table … enable row level security;` (plus `force row level
security` for the audit table), explicitly state that no `anon` policy exists, and `revoke insert, update,
delete on public.kill_switch_audit from public, anon, authenticated` so the append-only claim is real.
Owner: **tech-lead** (design), then dev at INC-3/5/6/7 build time; the live `monitor_alerts` check is
tech-lead + orchestrator.

---

### MAJOR

**REV-034 — `[SECURITY]` — major — INC-5 turns `authenticated` into an internet-reachable principal for the
first time, with no audit of what that role can already reach.**
Location: `docs/design/admin-portal.md:31-35` (Google OAuth, §16.1), `:41-76` (§16.2);
`sql/dashboard_latest_call_view.sql:45`.
Description: enabling Google OAuth means *any* Google account can obtain a valid `authenticated` JWT
against this Supabase project. §16.2's UI-side rejection is explicitly "a UX improvement, not the security
boundary" — correct, and correctly stated — but the design never checks what the `authenticated` role can
*already* do today. That role is currently unused, so nothing has ever had to be safe against it:
`latest_call_per_ticker` is granted to `anon, authenticated`, and the existing RLS policies on `call_log` /
`watchlist` / `holdings` / `verdict_state` / `run_heartbeat` / `monitor_alerts` are not in version control
(REV-035), so their role targeting cannot be reviewed. Any existing policy written `to authenticated` or
`to public` with a permissive `using (true)` becomes world-reachable the moment INC-5 ships.
Suggested fix: add an INC-5 acceptance criterion that enumerates every existing table/view grant and policy
by role and proves an authenticated-but-not-allowlisted session can read/write nothing beyond what `anon`
already could; and consider restricting sign-ups at the Auth layer as defence in depth, so an unauthorized
JWT is never minted in the first place.
Owner: **tech-lead** (design), with the live-grant enumeration to be executed at INC-5.

**REV-035 — `[DESIGN-GAP]` — major — the core schema and all RLS policies are not in version control, and
the runbook states the opposite.**
Location: `sql/` (contains DDL for exactly one table, `phase5_monitoring.sql:17`, plus one view);
`docs/runbook.md:70-76` and `:333-345`; `README.md:58-62`.
Description: `watchlist`, `holdings`, `verdict_state`, `call_log`, `run_heartbeat` and every RLS policy in
the system exist only inside the live Supabase project. `docs/runbook.md:335` claims "The four migrations
in `sql/` define the complete control-plane schema and logic. No other DDL is needed"; §2.3 and README step
1 present the same four files as a complete fresh-deploy procedure. Following that procedure produces a
project with no tables for the pipeline to write to. This is the *identical* defect class the repo already
fixed once for the scheduler — `sql/scheduler_pgcron.sql:4-10` exists precisely because "the DDL lived ONLY
inside Supabase and was never committed" — left unfixed for the data plane. It also blocks review of
REV-033/REV-034: the RLS posture asserted in `data-and-flow.md:66` cannot be checked against anything.
Suggested fix: extract the live DDL (tables, CHECK constraints, `enable row level security`, every policy,
every grant) into `sql/schema.sql` the same way the scheduler was captured, and correct the runbook/README
apply order.
Owner: **tech-lead** (extraction/design), **release** (runbook + fresh-deploy order).

**REV-036 — `[DESIGN-GAP]` — major — INC-6's tunables cache write-back is unvalidated and unconditional, so
one bad portal edit destroys the "last-known-good" it exists to preserve.**
Location: `docs/design/admin-portal-tunables.md:206-223` (`_tunable`), `:225-240`
(`write_tunables_cache_if_fetched`).
Description: `_tunable()` on a cast failure only prints and falls through to the next tier, while
`write_tunables_cache_if_fetched()` serialises `_TUNABLES` — this run's raw fetch — verbatim, including the
value that just failed to cast, and unconditionally overwrites the whole file. Concrete sequence: Arjun
types `5%` into `DISCOVERY_GAINER_PCT`; the portal accepts it (no validation anywhere — no CHECK
constraint, no per-key type in the schema, no portal-side check); run 1 casts it, fails, silently uses the
cached `5`, then **writes `5%` into the cache**, destroying the last-known-good; every later run repeats
this silently; the first Supabase blip after that finds tier 1 empty and tier 2 uncastable, and the new
fail-loud `SystemExit` takes the entire pipeline down — from a typo made weeks earlier. The same call also
shrinks the file if the fetch returned a partial key set (e.g. a row was deleted, see REV-044), silently
discarding good values for the missing keys. The file's own docstring calls the mechanism "last
successfully-fetched value" / "last-known-good", which is exactly what it fails to guarantee.
Suggested fix: cast/validate every fetched value *before* persisting; write back only keys that validate;
never write a key set smaller than the current cache; and make a tier-1 cast failure loud (it is a real,
operator-caused error) rather than a silent fall-through — consistent with the fail-loud posture just
adopted for the double-miss case.
Owner: **tech-lead**.

**REV-037 — `[DESIGN-GAP]` — major — the 2026-07-28 "two tiers, fail loud" correction is only half
propagated; three surviving statements still specify the removed third tier, one of them contradicting the
new behaviour outright.**
Location: `docs/design/non-functional-ops.md:57-59` ("gains the 3-tier tunables fallback chain (Supabase
table -> config/tunables_cache.json -> hardcoded literal)"), `:87-90` ("falls back to the existing hardcoded
literals rather than hanging or **crashing process startup**"), `:157-158` ("a hardcoded Python literal is
now only the third-tier floor"); `docs/design/admin-portal.md:106-112` ("the 3-tier `scripts/config.py`
fallback chain").
Description: the correction landed in `docs/design.md` and `admin-portal-tunables.md` §16.4 but not in the
repo-structure/config-surface module or the §16.4 pointer stub. `non-functional-ops.md` §8 is precisely the
file a dev opens to learn which files an increment touches, so INC-6 would plausibly be built with the
third tier reinstated — re-creating the three-places-to-sync problem this correction was made to remove.
`:87-90` is worse than stale: it states the design goal as *not* crashing process startup, which is the
exact opposite of the decided `SystemExit` behaviour, so the two modules now specify contradictory
requirements for the same function.
Suggested fix: propagate the two-tier + fail-loud wording to all four locations; state the fallback chain
once (in §16.4) and have the others reference it rather than restate it, per CLAUDE.md's "state anything
once" rule — restating it in four places is what allowed three of them to drift in a single day.
Owner: **tech-lead**.

**REV-038 — `[HARDCODED]` — major — INC-6 silently breaks the documented NSE model inheritance, because the
workflow's own literal fallback chain always wins.**
Location: `.github/workflows/hourly-watchlist.yml:68-69`; `scripts/config.py:34-35`;
`docs/requirements.md:315`; `docs/runbook.md:48-49`.
Description: the YAML sets `NSE_GEMINI_MODEL: ${{ vars.NSE_GEMINI_MODEL || vars.GEMINI_MODEL ||
'gemini-2.5-flash' }}` — a three-tier chain that can never produce an empty string. `config.py:34`'s
`os.environ.get("NSE_GEMINI_MODEL", GEMINI_MODEL)` default therefore never fires today (dead code), and
after INC-6 makes `GEMINI_MODEL` table-driven the consequences become behavioural: editing `GEMINI_MODEL`
in the admin portal changes the US/TSX watchlist model while the **NSE watchlist stays pinned to the YAML
literal**, with no warning. `requirements.md:315` and `runbook.md:48` both promise "inherit US/TSX pair".
Note the asymmetry that makes this easy to miss: `NSE_GEMINI_MODEL_BACKUP` (line 69) has *no* literal tail,
so the backup keeps inheriting correctly while the primary stops — the pair silently splits across two
sources of truth.
Suggested fix: drop the literal tail (and ideally the whole `vars.` chain, see REV-039) so the Python-level
inheritance is the single mechanism; add an INC-6 acceptance criterion that edits `GEMINI_MODEL` in the
table and asserts the NSE group's `model_used` follows.
Owner: **tech-lead** (design), dev at INC-6.

**REV-039 — `[HARDCODED]` — major — model-name defaults are duplicated across `config.py` and two workflow
files today, and this exact duplication has already drifted once in production.**
Location: `scripts/config.py:26-27` and `:109-110`; `.github/workflows/hourly-watchlist.yml:60,68`;
`.github/workflows/daily-discovery.yml:48-49`. Related: `docs/design/admin-portal-tunables.md:301-303`.
Description: `'gemini-2.5-flash'` / `'gemini-2.5-flash-lite'` are written as literals in five places across
three files, each of which must be edited together. The repo's own comments record the drift event:
`hourly-watchlist.yml:56-59` explains that the 3.5→2.5 correction had to be applied to the YAML literal
*as well as* `config.py`, and `requirements.md:337-343` documents the period when code and live operation
disagreed. INC-6 adds two more copies (the SQL seed and `config/tunables_cache.json`) — which its own
acceptance criteria #1/#2 have to guard with a byte-for-byte diff, itself evidence of the cost.
Compounding it, `admin-portal-tunables.md:301-303` decides to *leave* the now-unread `${{ vars.GEMINI_MODEL
|| '…' }}` wiring in place as "a harmless, unread vestige". It is not harmless: it is a control surface
that still looks live in the GitHub UI and in `docs/runbook.md:44-51`, where an operator who edits the
Variable will see no effect and get no warning.
Suggested fix: pick one home per key. For the two keys moving to the table, delete the `vars.`/literal
wiring from `hourly-watchlist.yml` inside INC-6 (a four-line diff, strictly smaller than leaving it) and
update `runbook.md` §2.2; for `DISCOVERY_GEMINI_MODEL*`, drop the YAML literals and keep `config.py` as the
single default. Where a literal must exist twice (SQL seed vs cache seed), keep the existing byte-diff
acceptance criterion — that one is genuinely unavoidable.
Owner: **tech-lead** (design), dev at INC-6, **release** (runbook table).

**REV-040 — `[DESIGN-GAP]` / `[SECURITY]` — major — INC-6 creates a second workflow that pushes to `main` on
an overlapping cadence, and grants repo-write to the workflow with the largest blast radius.**
Location: `docs/design/admin-portal-tunables.md:254-276`; `.github/workflows/publish-prices.yml:17-18,43-54`;
`.github/workflows/hourly-watchlist.yml` (no `permissions:` block today).
Description: two issues, one mechanism.
(a) **Race.** `publish-prices.yml` already commits and pushes to `main` on `*/30 3-10,13-21` — the same
cadence window `hourly-watchlist.yml` runs on. The two have *different* `concurrency` groups, so they run
concurrently, and the copied step guards only the rebase (`git pull --rebase … || true`) — the `git push`
itself is unguarded, so a lost race fails the step and red-Xs the **trading** workflow after its real work
has already completed (alarming, and it trains the operator to ignore failures on the most important
workflow). The tunables cache changes rarely, so this is intermittent — the worst kind to debug.
(b) **Privilege.** `hourly-watchlist.yml` is the workflow that holds every production secret and processes
third-party input (Yahoo headlines, model output). Giving its `GITHUB_TOKEN` `contents: write` is the
largest privilege increase in the whole change request.
Worth weighing: `publish-prices.yml` **already** has `contents: write`, already has the commit-on-change
step, already runs `*/30` across both sessions, and is already a read-only tunables consumer that fetches
the same table — making it the sole cache writer would mean zero new permissions, zero new commit steps,
and one committer instead of two. Decision #28 recorded `hourly-watchlist.yml` as a *proposal* for Arjun to
"confirm or override" (`requirements.md:296`) and he confirmed it, so this is flagged as a trade-off to
re-put to him via pm, not as a defect in the decision.
Suggested fix (whichever writer is chosen): share one `concurrency` group between the two committing
workflows, or add a bounded retry around the push; and scope the new permission to the job, not the file,
if the writer stays in `hourly-watchlist.yml`.
Owner: **pm** (to re-put the trade-off to Arjun), then **tech-lead**.

**REV-041 — `[DESIGN-GAP]` — major — INC-6 adds an unbounded network call at `config.py` import time; the
design's own claim that it is short-timeout is not met by the design's own code.**
Location: `docs/design/admin-portal-tunables.md:180-204`; `docs/design/non-functional-ops.md:87-90` ("…
short-timeout and exception-wrapped so a Supabase hiccup falls back … rather than hanging").
Description: the sketched `_fetch_tunables()` calls `create_client(...)` and `.select().execute()` with no
timeout argument; supabase-py's default PostgREST timeout is not short. `config.py` is imported by every
module and every entry point, so a hung or slow Supabase connection stalls the start of every scheduled
run, on the module the design explicitly notes has never made a network call before. Secondary and
immediate: `tests/test_config.py:24-46`'s `reload_config` fixture reloads `config` roughly fifteen times
per suite run, so INC-6 turns the unit-test suite into ~15 live connection attempts against
`https://example.invalid.supabase.co` (`tests/conftest.py:24`), with stdout noise on each — slower CI,
new flakiness, and a fetch path with no test seam.
Suggested fix: pass an explicit `ClientOptions(postgrest_client_timeout=…)` (and make it a tunable of the
non-curated kind); provide an explicit offline/skip path so tests and local runs deterministically use tier
2; expose the fetch behind a patchable seam (`_fetch_tunables`) and say so in the INC-6 acceptance criteria
so qa can mock it, mirroring how `ai_judge._client` is already the single patched seam.
Owner: **tech-lead**.

**REV-042 — `[CODE-GAP]` — major — the dead-man monitor never alerts on a *degraded* discovery or
publish-prices run, although both compute a degraded status and the runbook documents the alert.**
Location: `sql/phase5_monitoring.sql:180-193` (`disc_status` selected, never read), `:201-216`, `:224-240`;
`scripts/run_discovery.py:59-66,114-118`; `scripts/publish_prices.py:71-72`; `docs/runbook.md:149-155`.
Description: only the two watchlist branches implement the `status <> 'ok'` degraded check. The discovery
branch **selects** `disc_status` into a variable and then never uses it — a dead read that reads as if the
check existed. So the deliberate work `run_discovery.py` does to distinguish "quiet day" from "screener
failure" (`status='partial'` when `screens_errored`, the issue #2 principle applied to discovery) and
`publish_prices.py`'s `partial` status both terminate in a table nobody watches. `docs/runbook.md:153-155`
promises exactly these alerts ("Degraded alert: when `run_heartbeat.workflow_name='daily-discovery'` shows
`status != 'ok'`"), so the operator believes coverage exists. NFR2 requires alerting on a run that
"completes degraded", without limiting it to the watchlist.
Suggested fix: add the `elsif … status <> 'ok'` branch to the discovery-NA, discovery-IN and publish-prices
checks (each is ~6 lines, mirroring the watchlist branch), or correct the runbook — but the requirement
says alert, so the SQL is the side to change.
Owner: **tech-lead** (SQL design), **release** (runbook table once fixed).

**REV-043 — `[BLOAT]` — major (efficiency) — `publish_prices.py` runs the full ingest pipeline every 30
minutes to publish four fields.**
Location: `scripts/publish_prices.py:47-54`; `scripts/ingest.py:217-288`.
Description: `ingest.get_market_data()` fetches three months of price history, `tk.fast_info`, the full
`tk.info` scrape, and `tk.news`, then runs headline relevance filtering and the session-aware
volume pro-rating — and `publish_prices` uses `price`, `pct_change_1d`, `market`, and
`fundamentals.currency`. That is roughly four Yahoo requests per ticker where one would do, on ~32 dispatch
slots per weekday across both sessions (`sql/scheduler_pgcron.sql:152`) — on the order of a thousand
avoidable requests a day against an unofficial API that has already rate-limited this pipeline in
production (issue #1), degrading the *watchlist* runs that share it and the `YF_PACING_SECONDS` budget.
It is reuse in the right spirit (one ingest wrapper, `components.md` §4.2) applied at the wrong grain.
Suggested fix: add a narrow `ingest.get_price_only(ticker)` (history `period='5d'` + `fast_info`, no
`info`, no news) and have `publish_prices` call it; keep `get_market_data` untouched for the AI paths. Also
worth confirming with pm whether `publish-prices` needs a market-open gate at all — it is the only
dispatch path with none, so it currently also fires through the 11:00–13:00 UTC gap between sessions.
Owner: **tech-lead** (design call), then dev.

---

### MINOR

**REV-044 — `[SECURITY]` — minor — the `tunables` write policy is broader than FR30 needs, and the stamping
trigger doesn't cover what the policy allows.** Location: `docs/design/admin-portal-tunables.md:59-66`. The
policy is `for all` (insert/update/delete) while the trigger is `before update` only. FR30 needs UPDATE on
ten migration-seeded rows — nothing more. A stray DELETE from the portal silently pins that key to the
cache value forever (no error is possible: tier 2 still resolves it), and an INSERT creates an unstamped
row no code reads. Suggest `for select, update` only, plus a `check (key in (…))` or FK to a key registry.
Owner: **tech-lead**.

**REV-045 — `[DESIGN-GAP]` — minor — a persistently failing tunables fetch degrades silently, against this
project's own established precedent.** Location: `docs/design/admin-portal-tunables.md:188-190,199-201`. A
failed fetch prints one line into a run log nobody reads and continues on cache values indefinitely; the
NFR2 monitor sees healthy runs. The codebase already decided this question twice in the other direction —
issue #35 made the FR18 topic fallback operator-visible (`scripts/notify.py:63-68`), and issue #2 made a
degraded run write `status='partial'` so the monitor surfaces it. Suggest the same: when tier 2 is used,
write the heartbeat as `partial` (or an equivalent monitor-visible signal), so weeks of frozen tunables
cannot pass unnoticed. Owner: **tech-lead**.

**REV-046 — `[BLOAT]` — minor — the new repo-root `config/` directory collides with the `config` module
name every script imports.** Location: `docs/design/admin-portal-tunables.md:178`;
`docs/design/non-functional-ops.md:49-53`; `tests/conftest.py:15-17`. `scripts/` is a flat, non-package
directory placed on `sys.path`, so `import config` resolves by path order; a repo-root `config/` directory
with no `__init__.py` is a valid implicit namespace package that shadows `scripts/config.py` whenever the
repo root precedes `scripts/` on `sys.path` (e.g. a bare `python -c "import config"` from the root, or any
future tooling change). Free to avoid before the file exists: name it `tunables_cache.json` at the repo
root, or put it under an existing non-importable directory. Owner: **tech-lead**.

**REV-047 — `[BLOAT]` — minor — `check_pipeline_health`'s ET and IST watchlist branches are ~25 duplicated
lines differing only in one message string.** Location: `sql/phase5_monitoring.sql:118-176`. Identical
threshold, identical priorities, identical cooldowns, identical recovery text; a future change to the
staleness rule (e.g. REV-042's degraded branch, or INC-3's `GREATEST(last_run_at, resume_baseline)` change,
which `operational-controls.md:146` already says must touch all four checks) must be made twice, correctly,
in both. Suggest one branch parameterised by a `session_label` variable. Owner: **tech-lead**.

**REV-048 — `[HARDCODED]` — minor — market-session constants are duplicated across the Python and SQL
layers with nothing detecting drift.** Location: `scripts/config.py:164-166,201-203`;
`sql/scheduler_pgcron.sql:132`; `sql/phase5_monitoring.sql:125,153,224-225,279`. The open bounds (09:30 /
09:15), the base close bounds (16:00 / 15:30), the monitor's grace windows (10:15 / 10:00) and the
`70 minutes` staleness threshold (three copies) exist independently in both layers. To be explicit: this is
**not** a request to merge the two close bounds — `docs/design.md` §0 #9 deliberately keeps SQL at close+5
and Python at close+`RUNTIME_CLOSE_GRACE_MIN`, and that decision is sound and well documented. The gap is
that changing `MARKET_OPEN`/`MARKET_CLOSE` in `config.py` (a documented tunable, `requirements.md:333-334`)
would leave five SQL sites silently disagreeing. Suggest documenting the set as one linked table in
`components.md` §4.1, and a cheap test that reads the SQL files and asserts the documented relationship
(the suite already parses workflow YAML in `docs/handoff.md`'s verify block, so the pattern exists).
Owner: **tech-lead** (design), **qa** (the drift test).

**REV-049 — `[BLOAT]` — minor — `audit.yml`'s lint gate never actually runs, its Node half is dead today
and breaks at INC-5, and it tests on a different Python than production.** Location:
`.github/workflows/audit.yml:34,36-44,57-81`. (a) `ruff check` runs only if a ruff config exists; none does
(no `ruff.toml`, no `pyproject.toml`), so every push logs "No ruff config found, skipping lint" — the
project's automated hardcoding/leanness gate, which this review process is supposed to consult first, is a
no-op. (b) The ESLint/Node branches are dead config in a Python-only repo — and become an active hazard at
INC-5, when `admin-portal/package.json` appears: the detector looks for `package.json` at the **repo root**,
so it will still skip, meaning the portal ships with no lint or test coverage in CI at all. (c) `3.x` here
vs the pinned `3.12` in all three production workflows means CI never exercises the production interpreter.
Suggest: add a minimal `ruff.toml`, pin `3.12`, and decide the portal's CI story as part of INC-5 rather
than discovering it after. Owner: **release**.

**REV-050 — `[SECURITY]` — minor — three of four workflows declare no `permissions:` block.** Location:
`.github/workflows/hourly-watchlist.yml`, `daily-discovery.yml`, `audit.yml` (cf. `publish-prices.yml:17-18`,
which does it correctly). They inherit the repository default `GITHUB_TOKEN` scope, which on older repo
settings is write-all. None of the three needs any repo write today. Suggest `permissions: contents: read`
on each (and the minimum gitleaks needs on `audit.yml`) — which also makes REV-040's new grant an explicit,
reviewable delta rather than an invisible one. Owner: **release**.

**REV-051 — `[BLOAT]` — minor — `publish_prices.py` re-implements the required-secrets check instead of
reusing `config.require_secrets()`.** Location: `scripts/publish_prices.py:34-36`; `scripts/config.py:214-222`.
Two implementations of one concern with the same error string, because `require_secrets()` hardcodes a
three-secret list including `GEMINI_API_KEY`, which this entry point doesn't need. Suggest
`require_secrets(*names)` defaulting to the current three. Owner: **dev** (after tech-lead confirms the
signature change is in scope). 

**REV-052 — `[HARDCODED]` — minor — declared tunables are restated as literals outside `config.py`.**
Location: `pages/detail.html:142` (`.slice(0,5)` duplicates `HEADLINES_LIMIT`, `config.py:96`);
`scripts/textutil.py:4-6` (docstring states "280" and "150" for `RATIONALE_MAX`/`NOTIF_BODY_MAX`, both now
env-tunable, `config.py:101-102`); `scripts/notify.py:98` (`https://ntfy.sh/` base URL and `timeout=10`,
neither in the `requirements.md` §10 baseline; the same base URL is hardcoded again in
`sql/phase5_monitoring.sql:37`). Raising `HEADLINES_LIMIT` today changes what the AI sees but not what the
detail page shows, silently. Per `docs/design/non-functional-ops.md:123`, "no tunable may live only in
code". Owner: **dev** (page + notify), **tech-lead** (adding the ntfy endpoint/timeout to the config
surface).

**REV-053 — `[BLOAT]` — minor — the two static pages duplicate their config, helpers and styles, in two
different shapes.** Location: `pages/dashboard.html:101-102,118-155` vs `pages/detail.html:50-57,91-123`.
Duplicated: the Supabase URL, the publishable key, `esc()`, the `VERDICT` colour map, `_TZSHORT`/`tzLabel`/
`clockIn`, and the entire CSS `:root` block. Worse than plain duplication: the currency mapping exists in
two *different* representations — `CUR` keyed by **market** in the dashboard (`{US:"$"}`) and `CUR` keyed by
**currency code** plus `MKT_CUR_CODE` in the detail page (`{USD:"$"}`) — so adding a fourth market means
two edits in two shapes, and a key rotation means two edits with no test to catch a miss. Suggest a shared
`pages/common.js` + `pages/common.css`; both pages are same-origin so this costs nothing. Owner: **dev**
(with tech-lead confirming the frontend module boundary, `frontend.md` §10).

**REV-054 — `[BLOAT]` — minor — `httpx` is a direct import but an undeclared dependency.** Location:
`scripts/ai_judge.py:13`; `requirements.txt`. It resolves today only transitively via `google-genai` /
`supabase`. A transitive bump that drops or majors it breaks `_is_retryable`'s client-timeout
classification (`ai_judge.py:204`) — the exact path that fixed load-bearing decision #3 — or breaks import
outright, in an environment where every other dependency is pinned. Suggest pinning `httpx` explicitly.
Owner: **dev**.

**REV-055 — `[TEST-GAP]` — minor — no automated coverage for the orchestrators' own decision logic.**
Location: `tests/test_import_smoke.py:34-42` is the only coverage of `run_hourly.py`, `run_discovery.py`,
`publish_prices.py`, and it asserts only that they import and expose `main()`. Untested: `_sessions()` /
which market group runs (`run_hourly.py:34-49`), the `FORCE_RUN`-with-everything-closed branch
(`:130-134`), the both-sessions-open warning (`:113-117`), the `partial`-vs-`ok` heartbeat rule
(`:154-156`), and `run_discovery`'s quiet-day-vs-screener-failure distinction (`:55-66`). Every one of
those exists because of a specific past production defect (issues #2, #7, #8) — precisely the logic that
should have a regression net. The pure modules underneath are well covered; this is the seam that isn't.
Owner: **qa**.

**REV-056 — `[BLOAT]` — minor — leftover scraps from the retired shadow-pilot track.** Location:
`.gitignore:4-6` (`.shadow-pilot-session-state.md`, flagged as ambiguous-ownership in `docs/handoff.md:57-59`
on 2026-07-16 and never actioned since); `sql/drop_shadow_tables_migration.sql`, which is a one-time,
already-applied migration still listed as a required step of the **fresh-deploy** procedure in
`docs/runbook.md:74` and `README.md:62` — a fresh project never had those tables. Suggest deleting the
`.gitignore` entry and moving the drop migration out of the fresh-deploy apply order (it can stay in the
repo as history). Otherwise the retirement is genuinely clean: no `shadow` references remain anywhere in
`scripts/`, `sql/` (beyond that file), `.github/workflows/`, or `pages/` — independently re-confirmed by
repo-wide grep this pass. Owner: **release** (runbook/apply order), **pm** (README), **dev** (`.gitignore`).

**REV-057 — `[DESIGN-GAP]` — minor — the `data_snapshot` contract documents values the code never
produces.** Location: `docs/design/data-and-flow.md:42,45` vs `scripts/ai_judge.py:294,297,386` and
`scripts/state.py:86`. `parse_status` is documented as `ok | retried | failed | api_error | no_data`, but
`retried` is written by nothing (the retry path returns `ok`). `fallback_from` is documented as a short
token set (`timeout | 503 | 429-rpd | parse`) while the code writes a full
`"<model>: <ExcType>: <message[:200]>"` string — anyone writing a query or a future analytics view against
the documented shape gets nothing back. This is the load-bearing consumer contract, so it should match the
writer exactly. Owner: **tech-lead**.

**REV-058 — `[REQUIREMENTS-GAP]` — minor — NFR3 is cited as the security NFR in the design, but
`requirements.md` defines it as the disclaimer NFR.** Location: `docs/requirements.md:240-241` (NFR3 =
Disclaimer) and `:251` (NFR6 citing "NFR3's 'secrets never in code' posture") vs
`docs/design/non-functional-ops.md:18-20` (§7.2 titled "Security (NFR3)") and `docs/design.md:338` (the
coverage map's NFR3 row). There is in fact no core security NFR — the security posture (RLS, Vault, no
brokerage credentials, UUID detail-page URLs) is real and well implemented, but traces to a requirement ID
that says something else. Either add a security NFR or fix the three citations; with NFR6 now introducing a
real security requirement, the ambiguity gets more expensive, not less. Owner: **pm** (ID decision), then
**tech-lead** (citations).

**REV-059 — `[DESIGN-GAP]` — minor — three self-consistency defects in the CR documents.** Location:
(a) `docs/design.md:351-352` still says "INC-6 has one open design gap pending confirmation", contradicting
the same file's header at `:14-16` ("No open design questions remain") and `admin-portal-tunables.md:320`
("No open question remains for INC-6") — *owner: tech-lead*; (b) `docs/requirements.md:377-378` still
records the cache write-ownership as "a design-level call left to tech-lead", though Decision #28's proposed
shape was confirmed by Arjun and is now stated as settled in `design.md:159-167` — *owner: pm*;
(c) `docs/design/admin-portal.md:26-27` carries a stray sentence fragment ("…is not a new exposure.
deploy.") left from an edit — *owner: tech-lead*. Each is small; together they make it hard for a reader to
tell which statement in the CR is current, which is the same condition that produced REV-037.

**REV-060 — `[DESIGN-GAP]` — minor — the runbook's fresh-deploy dispatch smoke test cannot fail, and points
at a workflow that cannot be dispatched.** Location: `docs/runbook.md:267-271`. `SELECT
public.dispatch_github_workflow('audit.yml')` targets the one workflow with no `workflow_dispatch` trigger
(`.github/workflows/audit.yml:3-5`), so GitHub rejects it; and `pg_net.http_post` returns a request id
immediately regardless of the eventual HTTP status, so the documented pass criterion ("should return a
request ID (a bigint)") is satisfied even with an expired or wrong PAT — exactly the failure this check
exists to catch (and the top suspect in the runbook's own §4 stale-alert triage list). Suggest targeting a
dispatchable workflow and asserting on the matching `net._http_response` row. Two smaller inaccuracies in
the same document: `:286` tells the operator to find the dashboard passcode in `pages/index.html`, which
does not exist (the dashboard is `pages/dashboard.html`), and `:142` describes the monitor as running ":20
and :50 past each hour" when the schedule is `20,50 4-11,14-23`. Owner: **release**.

**REV-061 — `[DESIGN-GAP]` — minor — two documents still describe Gemini as free-tier after the 2026-07-13
paid-tier correction.** Location: `docs/idea-brief.md:95` ("Gemini free tier may train on submitted
prompts") and `:98` ("Free-tier quotas move"); `docs/runbook.md:214` ("Free-tier models may train…").
The correction was applied to NFR1, `foundations.md` §2 items 1/3, `README.md`, and the idea-brief's own
Constraints section — the Open-risks list at the bottom of the idea-brief was missed. Since the accepted
risk is about *data handling terms*, the tier statement is load-bearing for the risk, not cosmetic.
Owner: **pm** (idea-brief), **release** (runbook).

---

### What is genuinely in good shape (calibration)

Reported deliberately, so the findings above are read at the right weight — this is not a codebase in
trouble, and several parts of it are better than the norm:

- **The alerting core.** The single-rule state machine (`scripts/state.py:208-267`) and its fail-safe
  guards are clean, and `tests/test_state.py` covers the load-bearing cases directly, including the one
  that matters most (a fail-safe Hold can never fabricate a change alert). The "a bug can only miss a
  signal, never fabricate one" property holds on inspection of every path.
- **Observability discipline.** The discovery funnel counters, the `partial`-vs-`ok` heartbeat rule, the
  `[gate]` audit line, the `[FR18 fallback]` line, and `fallback_from`/`retry_count` in the snapshot are a
  coherent, deliberate posture — degradations are made visible rather than swallowed. REV-042 and REV-045
  are gaps *in* that posture, not exceptions to it.
- **SQL function security.** Every `SECURITY DEFINER` function sets `search_path = ''`, qualifies its
  references, reads secrets from Vault, and revokes `execute` from `public, anon, authenticated`. That
  discipline is consistent and correct; REV-033 is the table-level counterpart that was simply never
  written, not a contradiction of it.
- **Secrets.** No committed secret found anywhere in the repo. The two client-side keys are the publishable
  anon key, correctly identified as public-by-design and RLS-scoped; the `latest_call_per_ticker` view's
  `security_invoker = true` (and its column narrowing away from `raw_model_response`) is exactly right.
- **The INC-4 LiteLLM-vs-hand-rolled analysis** (`operational-controls.md` §14.1) is the strongest piece of
  design writing in the set: five specific, falsifiable reasons grounded in this system's own incident
  history, plus an explicit revisit condition. No changes suggested.
- **INC-3's kill-switch** correctly identifies the single dispatch choke point instead of patching five
  callers, and the resume-baseline refinement (§13.4) catches a false-alarm mode most designs would ship
  into production and discover the hard way.
- **INC-6's move to a Supabase table** is a genuine net simplification (one fewer secret store, one fewer
  code path, one authorization mechanism), correctly justified by falsifying Decision #24's premise. The
  concerns above are about its edges, not its direction.
- **Doc-to-code fidelity is high overall.** The pre-existing modules (`foundations.md`, `data-and-flow.md`,
  `components.md`, `non-functional-ops.md`) were checked line-by-line against the live code and are
  accurate; REV-057 is the only content drift found in them.

---

### Pass 11 summary

**New findings by tag:** `[SECURITY]` 5 (REV-033, 034, 040 shared, 044, 050); `[DESIGN-GAP]` 11 (REV-035,
036, 037, 040, 041, 045, 046, 057, 059, 060, 061); `[CODE-GAP]` 1 (REV-042); `[HARDCODED]` 4 (REV-038, 039,
048, 052); `[BLOAT]` 7 (REV-043, 047, 049, 051, 053, 054, 056); `[TEST-GAP]` 1 (REV-055);
`[REQUIREMENTS-GAP]` 1 (REV-058). No `[SCOPE-CREEP]` found — pass 2 (code → requirements) came back clean:
every live behaviour traces to an FR/NFR or a numbered Decision, and the DRAFT increments stay inside
FR24–FR33.

**Resolved this pass:** none logged — Passes 1–10 had zero open items on entry, independently re-confirmed.

**Open blocker count: 1** (REV-033).
**Open major count: 10** (REV-034 through REV-043).
**Open minor count: 18** (REV-044 through REV-061).

**Distribution note:** 21 of the 29 findings are in DRAFT design for INC-3–INC-7 and cost nothing but an
edit to fix now, before GATE 3. Only 8 touch live production code or docs, and none of those is a
correctness defect in the alerting path.

### Verdict — Pass 11

**NOT CLEAR — one blocker.** REV-033 (RLS never enabled on the four new tables) must be resolved in design
before INC-3 or INC-5 starts; as drafted it would put a world-writable pause switch and a world-writable
admin allowlist into a financial-adjacent system, and it invalidates the authorization model that INC-5,
INC-6 and INC-7 all rest on. It is a one-line-per-table fix at this stage.

The nine other majors are all pre-build or non-urgent: REV-034/035 should be closed alongside REV-033 as a
single "database security posture" work item; REV-036/037/038/039/040/041 are INC-6 design corrections to
land before GATE 3; REV-042 and REV-043 are live-system improvements that can be scheduled independently of
the change request. No finding requires halting anything currently running.

**Routing:** REV-033–042, 044–048, 057, 059(a/c) → tech-lead. REV-040 (write-ownership trade-off), 058,
059(b), 061 (idea-brief) → pm. REV-043, 051, 052, 053, 054, 056 (`.gitignore`) → dev. REV-049, 050, 056
(runbook), 060, 061 (runbook) → release. REV-055 → qa.
