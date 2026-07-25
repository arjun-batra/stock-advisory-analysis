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
