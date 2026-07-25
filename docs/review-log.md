# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–6 (2026-07-12 through 2026-07-16) — archived

Passes 1–6 (baseline adoption audit, post-debt-cleanup re-audit, INC-1 NSE-shadow-pilot pre-merge audit,
INC-2 shared-eval-harness pre-merge audit, the post-Pass-4 cleanup independent re-verification, and the
shadow-pilot removal change request's diff-scoped pre-merge audit) are archived in full to
`docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene rule ("reviewer: on clearing an
increment, move RESOLVED entries to `docs/archive/review-log-archive.md`"), archived 2026-07-25 when
REV-022 — Pass 6's one remaining open item — was independently confirmed RESOLVED (pm removed the stale
shadow-pilot section from `docs/idea-brief.md` in commit `ee32d2d`, the same day). All REV-001 through
REV-022 items from that span are now RESOLVED, ACCEPTED-DEBT, or MOOT. Nothing from that span remains
open. Agents never read `docs/archive/` per `CLAUDE.md`.

---

## Pass 7 — 2026-07-25 (REV-022 closure verification + audit of 3 same-day follow-up commits)

Scope: this session closes out Pass 6's one open item and audits the three follow-up commits that landed
the same day (2026-07-16) but after Pass 6 was written, so were never themselves reviewer-audited:
- `ee32d2d` — "Remove shadow wallet pilot section from idea-brief.md (REV-022)" — pm-owned fix for REV-022.
- `8b86f81` — "docs: confirm shadow tables dropped from live Supabase project" — dev-owned `docs/handoff.md`
  edit confirming `sql/drop_shadow_tables_migration.sql` was applied to the live DB.
- `83b27de` — "Delete shadow experiment content from requirements.md outright" — pm-owned `docs/requirements.md`
  edit per a further user follow-up ("remove all traces of shadow experiment from requirements document as
  well"), deleting §10 (Experimental Tracks, all FR24–FR31/FR32–FR39 text), the three retired config
  tables, and the NFR5/NFR6 verbatim block (254 lines removed), leaving one-line changelog pointers.

**Method note (unchanged from every prior pass):** no shell/execute tool available this session
(Read/Grep/Glob/Write/Edit only) — I could not run `git show`/`git diff` on the three commits directly.
Verified their claimed effect instead by reading the current working-tree file contents directly (all
three commits are already applied to the tree) and by a fresh, independent case-insensitive repo-wide
grep for `shadow` (excluding `.git/` and `docs/archive/`), rather than taking the commit messages or
`docs/handoff.md`'s own sweep claims on trust.

### REV-022 verification

Read `docs/idea-brief.md` in full (109 lines, current). The "Experimental addition (NOT core v1 scope):
shadow wallet pilot" section Pass 6 flagged is gone outright — no `shadow` token anywhere in the file
(confirmed by direct grep, zero hits). The document now describes only the live v1 system (watchlist,
discovery, alerting, dashboard, dead-man monitor) with no mention of either retired pilot. Matches
commit `ee32d2d`'s stated effect exactly (19 lines removed, no other section altered).

**REV-022 — RESOLVED 2026-07-25.** Fixed by pm in commit `ee32d2d`, same day as Pass 6 was written.
Independently confirmed by direct read of the current file — not taken on the commit message's word.

### 8b86f81 verification — `docs/handoff.md` live-migration confirmation

Read `docs/handoff.md`'s "New file" section (the `sql/drop_shadow_tables_migration.sql` entry). It now
reads: "**Applied to the live Supabase project** by the orchestrator; confirmed via `list_tables` that
`call_log_shadow`/`call_log_shadow_nse` are gone and the remaining tables (`watchlist`, `holdings`,
`verdict_state`, `call_log`, `run_heartbeat`, `monitor_alerts`) are untouched." This supersedes Pass 6's
"documented as not-yet-applied in three independent places" finding — the migration's status has moved
from pending to applied, and the doc now says so plainly rather than leaving a stale "not yet applied"
claim in place. No Supabase MCP tool was available in this reviewer session to independently re-confirm
the live database state directly (same limitation Pass 4/5 disclosed for REV-016) — this rests on the
documented orchestrator-performed verification, not an independent reviewer re-check. Flagged as a method
caveat, not silently treated as reviewer-verified.

Noted, not a finding: `docs/handoff.md` lines 47–48 (dev's original repo-wide sweep note, unedited by
`8b86f81`) still lists `docs/idea-brief.md` alongside `README.md` as needing a pm fix. This is pre-existing
text from dev's original handoff (predates all three commits in this pass's scope, and `8b86f81` only
added the "Applied to the live Supabase project" confirmation, not a rewrite of the sweep section) — now
mildly stale since `idea-brief.md` was fixed by `ee32d2d`, but it is a working note recording what was true
at write-time, not a live status claim, and the actual action item (fix `idea-brief.md`) was correctly
acted on. Not rising to a new finding; too minor to log given the explicit "don't expect problems, this is
bookkeeping" framing of this pass.

### 83b27de verification — `docs/requirements.md` shadow-content deletion

Grepped `docs/requirements.md` case-insensitive for `shadow`: 6 hits remain, all in the Changelog table
(lines 9, 279, 281, 283–287), each a one-line historical pointer ("Retired and removed outright
2026-07-16 — see below and git history.") — no live FR/NFR section text. Grepped specifically for
`FR2[4-9]|FR3[0-9]|NFR5|NFR6`: same result, matches only inside the changelog rows, zero matches in any
requirement section body. Read the document's section headers top to bottom (`## 1.` through
`## 18.`... actually through the Changelog): §10 is now **"Configuration (tunables audit baseline)"**
(the former §11, renumbered down by one, exactly as the changelog entry describes) — the former §10
"Experimental Tracks" section is gone outright, not merely marked retired. Read the front-matter
provenance note (line 9) and NFR1 (§6, line 158–162): both are fixed exactly as the changelog claims — the
provenance note now reads "including an experimental shadow-wallet track that was added and later retired
and removed outright," and NFR1 now reads "one batched Gemini call per run per track (production
watchlist, NSE watchlist, and daily discovery)" with the former "and each shadow track" clause gone.

**Matches commit `83b27de`'s claimed effect exactly** — §10 (Experimental Tracks) deleted, three retired
config tables deleted, NFR5/NFR6 verbatim block deleted, dangling references in the front-matter and NFR1
fixed, changelog rows trimmed to one-line pointers (not deleted, correctly preserved as the audit trail
per the commit's own stated rationale). Core FR1–FR23/NFR1–NFR4 and the Decisions Log (§8) confirmed
untouched by spot-read.

### Full-repo regression grep

Case-insensitive `shadow` grep across the whole repo (excluding `.git/` and `docs/archive/`) confirms no
new regression:
- `.gitignore` — `.shadow-pilot-session-state.md`, the same pre-existing, already-accepted Claude-Code
  session-file naming convention Pass 6 confirmed unrelated to the feature. Unchanged, not a finding.
- `docs/requirements.md` — 6 changelog-only historical pointers, verified above. Correct.
- `docs/test-report.md` — qa-owned, retirement-framed historical run entries (the "Shadow tracks
  retirement — removal regression pass — 2026-07-16" section Pass 6 already reviewed). Unchanged, correct.
- `docs/design.md` — still contains extensive `shadow` text, but every occurrence checked is explicitly
  labeled **RETIRED (2026-07-16)** (§§0, 4, 7, 9, 13, 15, 16, 17, 18) — unchanged since Pass 6's own
  verification of this file, not touched by any of the three commits in this pass's scope. See REV-023
  below for one specific staleness this pass found within that retired framing.
- `qa/test-plan-full-codebase.md` — correctly retired framing (P3-1, P3-7, Phase 6 banner), unchanged since
  Pass 6.
- `scripts/`, `tests/`, `sql/` (apart from the already-reviewed drop migration), `.github/workflows/` —
  zero hits, confirmed by direct grep. No regression.

No new orphaned/regressed `shadow` reference found anywhere in the repo as a result of these three
commits.

### New finding

**REV-023 — [BLOAT] minor (doc staleness, cross-reference) — `docs/design.md` lines 8, 76, 81, 617, 658,
659, 660, 674, 684, 691, 694.** `83b27de` deleted `docs/requirements.md`'s former §10 (Experimental
Tracks, including §10.1/§10.2/§10.3) and renumbered the old §11 (Configuration) down to the new §10 — but
`docs/design.md` (not itself touched by any of the three commits, so this is a side effect, not a direct
edit) still points to the now-nonexistent old section numbers in at least nine places:
- Lines 658–660 (the §15 requirements-coverage map): "FR24–FR30, NFR5 | RETIRED 2026-07-16 — ... see
  `docs/requirements.md` §10.1", "FR31 | RETIRED ... §10.2", "FR32–FR39, NFR6 | RETIRED ... §10.3" — all
  three point at sections that no longer exist; `docs/requirements.md` §10 is now the Configuration
  section, not the (deleted) Experimental Tracks section.
- Lines 8, 76, 81, 617, 674, 684 similarly cite `docs/requirements.md` §10.1/§10.2/§10.3 as where "the
  requirement text itself is preserved verbatim... for traceability" — this is now factually **wrong**,
  not just a stale pointer: `83b27de`'s own changelog entry states the FR text was "Deleted... rather than
  leaving it marked retired" and is preserved only "in git history," not in the live document. Design.md
  is telling a future reader to look in a document location that both (a) doesn't have that section number
  anymore and (b) never held the text this way even before renumbering — the text was deleted outright, not
  kept "verbatim" in a numbered subsection.
- Lines 691, 694 cite "`docs/requirements.md` §10 (2026-07-16 changelog entries)" / "requirements.md §10
  changelog" — also wrong: the Changelog is now an unnumbered section at the bottom of the document, not
  §10 (§10 is Configuration).

This is the same staleness class as the already-resolved REV-017/REV-021 (design.md text lagging a change
made in a sibling document), not a new category. **Not a blocker, not a major** — purely a traceability
cross-reference and a "where is this preserved" claim, not a change to any prescriptive/requirement
content; no reader would be misled about what to build, only about where to find retired FR text if they
went looking for it. **Owner: tech-lead** (`docs/design.md` is tech-lead-owned) — update the nine citations
to either drop the specific-subsection pointer (since it no longer resolves) or point to git history
directly (matching `docs/requirements.md`'s own front-matter framing: "full FR/NFR text is preserved in
git history if ever needed").

### Pass 7 summary

**New findings by tag:**
- `[BLOAT]` (doc staleness): 1 (REV-023, minor — `docs/design.md`'s cross-references to `docs/requirements.md`
  §10.1/§10.2/§10.3/§10-changelog, all deleted/renumbered by `83b27de`)
- `[REQUIREMENTS-GAP]` / `[DESIGN-GAP]` / `[CODE-GAP]` / `[TEST-GAP]` / `[SCOPE-CREEP]` / `[SECURITY]` /
  `[HARDCODED]`: 0

**Resolved this pass:** REV-022 (`docs/idea-brief.md` shadow-pilot staleness — fixed by pm in `ee32d2d`,
independently confirmed by direct read).

**Open blocker count: 0.**
**Open major count: 0.**
**Open minor count: 1** (REV-023, new this pass — tech-lead-owned `docs/design.md` cross-reference
staleness following `docs/requirements.md`'s §10 deletion/renumbering).

### Verdict — REV-022 closure + 3 follow-up commits

**CLEAR. 0 blockers, 0 majors.** REV-022 is genuinely resolved, independently confirmed by direct read of
the current `docs/idea-brief.md` (zero `shadow` hits, not just taken on the commit message's word). All
three follow-up commits (`ee32d2d`, `8b86f81`, `83b27de`) do exactly what they claim: `idea-brief.md`'s
stale section is gone; `docs/handoff.md` now correctly documents the shadow-tables DROP migration as
applied to the live Supabase project (resting on the orchestrator's stated verification, not an
independent reviewer re-check — no Supabase MCP tool available this session); `docs/requirements.md`'s
shadow-experiment content is deleted outright per the user's explicit follow-up instruction, with the
audit trail correctly preserved as one-line changelog pointers rather than silently vanishing. A fresh,
independent full-repo grep for `shadow` found no new regression anywhere in `scripts/`, `tests/`, `sql/`,
or `.github/workflows/`.

**One new open minor, not blocking: REV-023** — `docs/design.md`'s traceability cross-references to
`docs/requirements.md`'s now-deleted/renumbered §10.1/§10.2/§10.3 subsections (and one "§10 changelog"
reference) are stale, a side effect of `83b27de`'s requirements.md edit that was never propagated to
design.md's own citations of it. Route to **tech-lead**.

**Method caveats (disclosed, not silently assumed away):** (a) no shell-execution tool available this
session — verification of the three commits' effect rests on reading the current working-tree state and a
fresh independent grep, not on `git show`/`git diff` output; (b) no Supabase MCP tool available this
session — the live-migration-applied claim in `docs/handoff.md` rests on the orchestrator's documented
verification, not an independent reviewer re-check.

---

## Pass 8 — 2026-07-25 (full-repo template/process-conformance audit)

**Scope:** requested as a comprehensive audit of the whole repo against `CLAUDE.md`'s delivery-team-template
conventions specifically (process/hygiene conformance), not a normal diff-scoped increment pass — treated
like the Phase 4 "full 5-pass audit over the whole codebase" in spirit, but focused on template adherence.
Runs concurrently with a tech-lead session independently fixing REV-023 (`docs/design.md`'s stale
`docs/requirements.md` §10.1/§10.2/§10.3 citations) — that fix is verified below, not duplicated.

The `.claude/` scaffolding, `CLAUDE.md`, `.claudeignore`, and `.github/workflows/audit.yml` were already
diffed byte-for-byte against upstream `arjun-batra/delivery-team-template` by the orchestrator and found
identical — not re-verified here (out of scope: reviewer audits the product repo's own conformance to the
rules, not the rules file itself). Everything else below is this pass's own direct verification, not taken
on the orchestrator's brief.

**Method note (unchanged):** no shell/execute tool available this session (Read/Grep/Glob/Write/Edit only)
— no `git log`/`git diff`/`git blame` this pass either; all findings rest on direct reads of current
working-tree file contents and repo-wide greps, disclosed inline where it matters (e.g., "release agent
ever engaged" is assessed from documentary evidence only, not commit history).

### REV-023 verification (concurrent tech-lead fix — independently confirmed, not assumed)

Read `docs/design.md`'s current lines 1–27, 70–82, 611–699 in full and grepped the whole file for
`§10\.[123]` and `requirements\.md.{0,3}§10 \(`: **zero hits**. Every citation Pass 7 flagged (lines 8, 76,
81, 617, 658–660, 674, 684, 691, 694) now reads "preserved in git history only" / "deleted outright from
`docs/requirements.md`" instead of pointing at the now-nonexistent §10.1/§10.2/§10.3 subsections — matches
the fix REV-023 called for exactly. **REV-023 — RESOLVED 2026-07-25**, independently confirmed by direct
read and fresh grep, not taken on the concurrent session's word.

### New finding: one additional instance of the same staleness class, missed by REV-023's enumeration

**REV-025 — [BLOAT] minor (doc staleness, same class as REV-023) — `docs/design.md:524`.**
`docs/requirements.md`'s Configuration section was renumbered from the old §11 down to §10 when
`83b27de` deleted the former §10 (Experimental Tracks) outright (confirmed: `docs/requirements.md`'s current
`## ` headers run 1 → 10, with "## 10. Configuration (tunables audit baseline)" at line 211 — verified by
direct grep of both files). `docs/design.md:524` ("This mirrors `docs/requirements.md §11` (the reviewer's
audit baseline)") still cites the pre-renumbering §11 — the same dangling-cross-reference defect REV-023
was just fixed for, at a line REV-023's own line list (8, 76, 81, 617, 658–660, 674, 684, 691, 694) did not
include. Not a blocker, not a major — one stale section-number pointer, same low-stakes profile as
REV-023. **Owner: tech-lead** — update to §10, ideally while REV-023's fix is still fresh context, to avoid
a second round-trip.

### New finding: `docs/design.md` line-count exceeds the doc-hygiene split threshold

**REV-024 — [BLOAT] major (doc hygiene, `CLAUDE.md` "Document hygiene" rule) — `docs/design.md`, whole
file.** Read the file's full section structure (`## 0` through `## 18`, confirmed via grep) and its true
length: **763 lines** (641 non-blank lines confirmed by count, ~763 total confirmed by reading to EOF at
line 766–768). `CLAUDE.md` states plainly: "tech-lead: once design.md exceeds ~400 lines, split per module
into `docs/design/<module>.md` with a thin index; agents read only the modules their increment touches."
This file is roughly **1.9x** the threshold and has been for some time — it was already well over 400 lines
by Pass 3 (2026-07-14, INC-1 pre-merge), which itself added new content (§16) without triggering a split,
and it has never been flagged as a hygiene violation by any of Passes 1–7. This is a genuine, currently-true
violation, not a historical one already fixed.

**Assessed module boundaries, for tech-lead's judgment (reviewer does not choose, only observes and
recommends per the read-only mandate):**
- The file's own header (lines 3–4) already states the natural fault line: "§§0–12, 15 cover Phases 0–7"
  (the live, active design — core system) vs. **§13, §14, §16, §17, §18 (~157 lines, lines 611–768) are
  RETIRED shadow-pilot content**, including §18's mechanical removal checklist. Per `docs/handoff.md` (dev,
  2026-07-16) and Pass 7's independent confirmation, that removal has **already been executed** — code
  deleted, tests cleaned, and the two Supabase tables **already dropped from the live project**
  (`docs/handoff.md`: "Applied to the live Supabase project... confirmed via `list_tables`"). A completed,
  historical removal checklist for tables that no longer exist is arguably itself leanness debt at this
  point (git history + `docs/requirements.md`'s own changelog already carry the audit trail) rather than
  live design content that needs to stay in the active document — tech-lead's call whether to delete §13/14/
  16/17/18 outright (git history preserves them, matching this doc's own stated policy for retired FR text)
  or archive them to `docs/archive/design-retired-sections.md`. Either move alone would bring the live file
  from ~763 lines to ~610 — still over 400, but a large single step.
- For the remaining ~610 lines of live content, natural module boundaries along the file's own existing
  section grouping: **foundations** (§0 load-bearing decisions, §1 purpose, §2 accepted risks, §3
  architecture — lines 29–162, ~135 lines), **components** (§4, lines 163–360, ~200 lines — scheduler,
  ingestion, prefilter, AI judgment, persistence, alerting, detail page, monitor; this is the single
  largest section and the most likely one an increment actually touches in isolation), **data & core flow**
  (§5 data model + §6 core flow, lines 360–464, ~105 lines), **non-functional & ops** (§7 NFR design, §8
  repo structure, §9 configuration surface, lines 464–563, ~100 lines), **frontend & requirement map** (§10
  detail/dashboard rendering, §11 CORS, §12 known limitations, §15 requirement coverage map, ~70 lines
  combined). A thin `docs/design.md` index (pointers + the load-bearing-decisions summary, which every
  increment should see regardless of module) plus `docs/design/<module>.md` files matching the above would
  let a dev implementing e.g. a discovery-prefilter change read only the components + data-flow modules,
  not all 763 lines, exactly matching the rule's stated purpose. **Owner: tech-lead** — this is a design.md
  restructure, squarely tech-lead's file; reviewer logs the violation and the boundary analysis, does not
  perform the split.

### New finding: `docs/runbook.md` absent despite the project deploying live

**REV-027 — [GAP] major — repo-wide (`docs/runbook.md` does not exist; `release` agent shows no evidence of
ever being engaged).** Confirmed via `Glob docs/**`: the only files in `docs/` are `archive/`, `design.md`,
`handoff.md`, `idea-brief.md`, `requirements.md`, `review-log.md`, `test-report.md` — no `runbook.md`, no
`docs/archive/runbook-archive.md`. Grepped all of `docs/*.md` for `runbook`/`release agent`/`CI/CD`:
zero substantive hits (one incidental match inside `docs/archive/test-report-archive.md`, unrelated
prose). `CLAUDE.md` is explicit: **"release (only if the project deploys) owns docs/runbook.md and CI/CD
config... If the project deploys, release sets up docs/runbook.md and CI before INC-1."** This project
unambiguously deploys: four live, currently-running GitHub Actions workflows
(`audit.yml`, `daily-discovery.yml`, `hourly-watchlist.yml`, `publish-prices.yml`), the last of which
produces hundreds of automated `chore: refresh dashboard prices.json` commits to `pages/prices.json` — this
is not a dormant CI config, it is an actively-deploying production system.

**Assessment (both possible dispositions considered, per the task's instruction not to leave this
silent):** `docs/idea-brief.md`'s own front matter frames the whole adoption as retroactive — "This is a
*retroactive* brief for a system that is already live (Phases 0–7 in production for weeks)," ported during
"the multi-agent-template adoption pass" on 2026-07-12 — which is a plausible reason CI/deploy tooling
predates the multi-agent workflow and wasn't set up "before INC-1" in the literal sense (there was no
INC-1 at adoption time; the system was already running). **But** that framing, on its own, only explains
why a runbook wasn't written *before* adoption — it does not explain why one was never **backfilled**
during or after the 2026-07-12 adoption pass, across seven subsequent reviewer passes, two shipped-then-
retired increments (INC-1 NSE pilot, the shared-eval-harness work), and one full removal increment, none of
which routed this to a release agent or recorded an explicit accepted-debt rationale anywhere in `docs/`.
Unlike `docs/requirements.md`'s and `docs/idea-brief.md`'s explicit "historical record, left untouched"
framing for `requirements_docs/`, there is **no comparable explicit acceptance note anywhere in the repo**
for the runbook gap — it is simply absent, undiscussed. Given four workflows deploy automatically to a live
system with real external side effects (ntfy pushes, a public dashboard, a live Supabase project) and zero
documented rollback/incident-response/deploy-verification procedure exists anywhere, this is a genuine
operational gap, not a paperwork nicety — rated **major**, not blocker (the system has run stably for weeks
without one, so it is not actively broken, but the absence is a real risk the team has never explicitly
chosen to accept). **Owner: release** — engage the release agent for the first time to author
`docs/runbook.md` documenting the four workflows' deploy/rollback/monitoring procedures per `CLAUDE.md`'s
ownership table; alternatively, if the team decides this is acceptable debt for a single-user solo system,
that decision belongs to the user via pm, recorded explicitly (not left implicit) per `CLAUDE.md`'s
"trade-offs go to them via pm, never decided silently" rule.

### New finding: `README.md` doc-sync staleness (three items, one file, pm-owned)

**REV-026 — [BLOAT] minor (doc staleness, "docs stay in sync with reality" non-negotiable) —
`README.md:42`, `README.md:48–51`, `README.md:71`.**
- **Line 42:** "**Gemini Flash** (free tier) generates verdicts..." — stale. The 2026-07-13 changelog entry
  in `docs/requirements.md` (line 282) and `docs/idea-brief.md`'s Constraints section both record, as
  user-confirmed fact, that Gemini "is no longer on the free tier — it now runs on Google's **paid tier**,
  system-wide." `README.md` never received this correction; a reader would be told the wrong billing tier.
- **Lines 48–51:** "**Note:** ... A dev/release handoff doc has not yet been produced in this pipeline run,
  so steps marked *(inferred)* should be confirmed against a handoff before being relied on." This is now
  false as literally written — `docs/handoff.md` exists (dev's 2026-07-16 shadow-tracks-removal handoff).
  It does not fully resolve the underlying *(inferred)* uncertainty (that handoff covers a deletion
  increment, not general deploy/SQL-apply-order/Python-version guidance — see REV-027 above, the actual gap
  is the missing runbook, not the absence of any handoff doc at all), but the note's literal claim ("has not
  yet been produced") is factually wrong and should at minimum be reworded to reflect that a handoff exists
  but doesn't cover general deploy procedure.
- **Line 71:** "...documented in `docs/requirements.md` §11 and defined in `scripts/config.py`." Same
  renumbering-staleness class as REV-023/REV-025, but in a **pm-owned** document (`README.md`), not
  tech-lead's `design.md` — `docs/requirements.md`'s Configuration section is now §10, not §11.

Not a blocker, not a major — none of the three misleads a reader about what the system does, only about
tier/billing detail, handoff-doc provenance, and one section-number pointer. **Owner: pm** (`README.md` is
pm-owned per `CLAUDE.md`).

### Checked, not a finding: `docs/requirements.md` changelog cap

Counted the Changelog table (`docs/requirements.md` lines 274–288): **exactly 10 dated rows** (lines
278–287). `CLAUDE.md`'s rule is "cap requirements changelog at **10 most recent** entries; archive the
rest" — at exactly 10, the cap is not yet exceeded, so this is **not currently a violation**. Noted for
forward visibility only: unlike `docs/review-log.md` (`docs/archive/review-log-archive.md` exists) and
`docs/test-report.md` (`docs/archive/test-report-archive.md` exists), there is **no**
`docs/archive/requirements-changelog-archive.md` yet — the next changelog entry (entry #11) will require pm
to create one and archive the oldest row(s) to stay at the cap. Not logging this as a REV item since there
is nothing currently out of compliance to fix; flagging so it isn't missed the next time `requirements.md`
changes.

### Checked, not a finding: document-hygiene rules elsewhere

- **Reviewer's own archiving (self-check):** `docs/review-log.md` currently holds only Pass 7 + this Pass 8
  (Passes 1–6 correctly archived to `docs/archive/review-log-archive.md`, confirmed by reading both files'
  headers and content) — the reviewer's own hygiene rule is being followed correctly. RESOLVED items in
  this pass (REV-023) will move to the archive file at the next natural clearance point per the established
  pattern, alongside REV-022's prior move.
- **qa's `docs/test-report.md` hygiene:** confirmed only the latest run (2026-07-16 shadow-retirement
  regression pass) plus an "Open bugs: None" section live in the file; older runs (baseline, INC-1, INC-2)
  correctly live in `docs/archive/test-report-archive.md`. Compliant.
- **"State anything once, reference by ID elsewhere" (no restated FR/bug text across docs):** re-checked
  `docs/design.md`'s requirement-coverage map (§15), `docs/test-report.md`, and this log — all reference
  FR/NFR/BUG/REV IDs and short pointers, not verbatim requirement or bug text. The one prior violation of
  this pattern (shadow-experiment FR text duplicated verbatim across `docs/requirements.md` and
  `docs/design.md`) was the thing the 2026-07-16 change request explicitly had removed; confirmed gone by
  Pass 7 and re-confirmed here. Compliant.
- **"Agents never read `docs/archive/`":** a process rule, not directly machine-checkable, but grepped every
  live doc for the word "archive" — all five hits (`docs/review-log.md`, `docs/handoff.md`,
  `docs/test-report.md`, and self-references inside the two archive files) are pointer/housekeeping notes
  ("moved to X per doc-hygiene rule"), none imply an agent consulted archived content to make a decision.
  No violation found.
- **Repo structure / `requirements_docs/` and `qa/test-plan-full-codebase.md` legacy framing:** confirmed
  `docs/requirements.md`'s front matter and `docs/idea-brief.md`'s front matter both still accurately
  describe `requirements_docs/` as the untouched pre-adoption historical record (spot-read
  `requirements_docs/stock-advisory-agent-requirements.md`'s own v5 header — still describes itself as
  "Owner: Arjun (solo build reference)," consistent with "left untouched"). No file has been added to
  `requirements_docs/` since adoption (`Glob` shows the same 5 files repeated across every pass). No recent
  work misplaced there. `qa/test-plan-full-codebase.md`'s own front-matter staleness-correction note
  (2026-07-12) remains accurate and current; the file's `§10`/`§18` cross-references are correctly current
  (confirmed at line 125), and its P1-6 body still says "§11" but that's inside a per-test pass-criteria
  line the file's own header explicitly disclaims as an un-rewritten historical snapshot ("only the items
  below explicitly flagged as factually wrong were corrected... those per-test references were not
  individually rewritten") — correctly excluded, not a new finding, consistent with how Passes 1–7 treated
  this same file's other SD-v15-era body text.
- **Code-layer re-audit:** `scripts/` (10 modules) and `tests/` (9 files, matching the 144-test count in
  `docs/test-report.md`) are byte-identical in file listing to what Pass 7 last saw — no source changed
  since Pass 7's clearance, so the full 5-pass code-level audit already closed out through Pass 7 (0
  blockers, 0 majors, all minors resolved/accepted-debt) remains valid and was not re-run from scratch this
  pass. Spot-checked `scripts/config.py` against `docs/design.md` §9 and `docs/requirements.md` §10 (the
  hardcoding-audit baseline, post-renumbering): every tunable in code has a matching entry in both docs'
  tables, defaults match exactly (spot-checked `YF_HISTORY_RETRIES=2`, `NOTIF_BODY_MAX=150`,
  `DISCOVERY_MIN_MARKET_CAP_INR=50000000000`, `RUNTIME_CLOSE_GRACE_MIN=10`) — no drift, no new
  `[HARDCODED]` findings.

### Pass 8 summary

**New findings by tag:**
- `[BLOAT]` (doc hygiene / staleness): 3 (REV-024 major — `docs/design.md` line-count exceeds the 400-line
  split threshold; REV-025 minor — one more stale §10.1-class citation at `docs/design.md:524`, missed by
  REV-023; REV-026 minor — three `README.md` doc-sync staleness items)
- `[GAP]`: 1 (REV-027 major — `docs/runbook.md` absent despite four live production-deploying workflows,
  release agent never evidenced as engaged)
- `[REQUIREMENTS-GAP]` / `[DESIGN-GAP]` / `[CODE-GAP]` / `[TEST-GAP]` / `[SCOPE-CREEP]` / `[SECURITY]` /
  `[HARDCODED]`: 0 new (code layer unchanged since Pass 7; re-spot-checked, no drift)

**Resolved this pass:** REV-023 (`docs/design.md`'s stale §10.1/§10.2/§10.3 citations — fixed by the
concurrent tech-lead session, independently confirmed by direct read and fresh grep, not taken on trust).

**Checked and found compliant, not findings:** reviewer's own archive hygiene, qa's test-report hygiene,
no-restated-FR-text rule, agents-never-read-archive rule, `requirements_docs/`/qa-test-plan legacy framing,
requirements.md changelog cap (at the cap, not yet over it).

**Open blocker count: 0.**
**Open major count: 2** (REV-024 — `docs/design.md` exceeds the doc-hygiene split threshold, owner
tech-lead; REV-027 — `docs/runbook.md` gap for a live-deploying project, owner release).
**Open minor count: 2** (REV-025 — one missed `docs/design.md` citation, owner tech-lead; REV-026 — three
`README.md` staleness items, owner pm).

### Verdict — Pass 8 (full-repo template-conformance audit)

**Not clear to treat as a routine clearance: 2 open majors, both process/documentation gaps rather than
code defects — nothing here blocks the increment pipeline from continuing, but both should be routed before
the next Phase 4 closure.** REV-023 is genuinely resolved (independently re-verified, not assumed from the
concurrent session's claim). The code layer is unchanged and remains clean per Pass 7's closed-out audit.
The two new majors are both structural/process conformance gaps the task specifically asked to be surfaced
rather than left implicit: `docs/design.md`'s length has silently exceeded the split threshold for multiple
passes without ever being flagged, and `docs/runbook.md` has never existed despite the project actively
deploying to production via four live workflows, with no explicit accepted-debt note anywhere recording
that as a deliberate choice. Route REV-024 to tech-lead, REV-027 to release (engaging that agent for the
first time), REV-025 to tech-lead (bundle with REV-024's restructure), and REV-026 to pm.
