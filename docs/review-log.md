# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–8 (2026-07-12 through 2026-07-25) — archived

Passes 1–8 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene rule
("reviewer: on clearing an increment, move RESOLVED entries to `docs/archive/review-log-archive.md`").
Passes 1–6 were archived 2026-07-25 when REV-022 (Pass 6's one remaining open item) was independently
confirmed RESOLVED. Passes 7–8 were archived the same day, at this Pass 9's close, once their combined
open items (REV-023 through REV-027) were all independently confirmed RESOLVED — see the Pass 9 entry
below for the closing verification. Nothing from Passes 1–8 remains open. Agents never read
`docs/archive/` per `CLAUDE.md`.

---

## Pass 9 — 2026-07-25 (closing verification: design.md split, README/runbook fixes, cross-reference cleanup)

**Scope:** independent verification of a chain of fixes landed since Pass 8 (2026-07-25): tech-lead's
`docs/design.md` → `docs/design/*.md` split (`ea6843f`, closing REV-024/REV-025), pm's `README.md` fix
(`43c4295`, closing REV-026), release's new `docs/runbook.md` (`1355f11`/`42afaa2`, closing REV-027), and
two follow-up rounds of cross-reference cleanup across `docs/handoff.md`, `sql/drop_shadow_tables_migration.sql`,
`docs/test-report.md`, `qa/test-plan-full-codebase.md`, `tests/test_config.py`, `tests/test_import_smoke.py`,
`tests/test_state.py`, and `docs/runbook.md`'s own citations (`5dee15e`/`ae86b0c` and a further pass
correcting residual stale `requirements.md §11` citations). Verified independently by direct read and
fresh grep — none of the above taken on the fixing sessions' summaries alone.

**Method note (unchanged from every prior pass):** no shell/execute tool available this session
(Read/Grep/Glob/Write/Edit only) — could not run `git show ea6843f` or `git diff` directly, and could not
execute `python3 -m pytest -q --tb=short` directly. Both limitations are disclosed inline below, with the
corroborating evidence used in place of direct execution.

### 1. `docs/design.md` + `docs/design/*.md` split — verified sound

Read the new `docs/design.md` index in full (148 lines) and all five module files in full:
`foundations.md` (84 lines), `components.md` (207 lines), `data-and-flow.md` (112 lines),
`non-functional-ops.md` (110 lines), `frontend.md` (52 lines). All five are comfortably under the ~400-line
`CLAUDE.md` split threshold (largest is `components.md` at 207 lines, ~52% of the limit) — **REV-024 is
genuinely resolved**, not just nominally split into still-oversized files.

The module map's stated section-to-file mapping was checked against each file's actual `##` headers and
found accurate in every row: `foundations.md` opens with "Section numbers below (§1–§3)... unchanged" and
contains exactly `## 1`, `## 2`, `## 3`; `components.md` contains exactly `## 4` (with `### 4.1`–`### 4.8`
subsections matching the index's parenthetical); `data-and-flow.md` contains exactly `## 5`–`## 6`;
`non-functional-ops.md` contains exactly `## 7`–`## 9`; `frontend.md` contains exactly `## 10`–`## 12`.
`docs/design.md` itself retains `## 0` (load-bearing decisions) and `## 15` (requirement coverage map) plus
the "Retired: shadow-pilot tracks" unnumbered note, exactly matching the index's own row for "this file."
Section numbers are preserved unchanged across the split (only physical file location moved), as the
index's own note (line 31) claims — confirmed true, not just asserted.

**Content-loss check:** no shell tool was available to run `git show ea6843f` directly, so this rests on
comparing the current five module files + index against Pass 7/8's own prior direct reads of the
pre-split monolithic `docs/design.md` (both sessions quoted specific line ranges and content, e.g. Pass 8's
recorded 763-line structure and module-boundary line estimates: foundations ~135 lines/§0–3, components
~200 lines/§4, data-and-flow ~105 lines/§5–6, non-functional-ops ~100 lines/§7–9, frontend+coverage-map ~70
lines/§10–12+§15). The post-split files' actual sizes (84/207/112/110/52, +148 for the index) land within
the same order of magnitude as those estimates once one further fact is accounted for: the ~157-line
RETIRED §13/14/16/17/18 block (already recommended for deletion-or-archival by Pass 8's own finding) was
compressed into the ~27-line "Retired: shadow-pilot tracks" note that stayed in the index, rather than
carried into any module file — this is a legitimate tech-lead call Pass 8 explicitly flagged as
tech-lead's judgment call to make ("tech-lead's call whether to delete §13/14/16/17/18 outright... or
archive them"), and git history + `docs/requirements.md`'s own changelog still carry the full historical
narrative per the doc's own stated policy. No load-bearing content (the §0 decisions, the §4 component
specs, the §5 data model / §6 flow, the §7–9 ops/config surface, the §10–12 frontend/limitations, or the
§15 coverage map) is missing from the module files — every item Pass 7/8 previously quoted or referenced
was found present, in the expected module, on direct read. **Flagged as a method caveat, not silently
assumed:** without `git show`, this is corroboration by cross-session content comparison, not a byte-level
diff against the pre-split commit.

### 2. Fresh, independent repo-wide grep for stale cross-references

Grepped the whole repo (excluding `.git/`) for `design\.md.{0,10}§(1[3-8])` (old shadow-pilot/removal-plan
section numbers) and `requirements\.md.{0,15}§11`. Results:

- **`requirements\.md.{0,15}§11`:** live hits are correctly zero outside the two explicitly-allowed
  locations — `docs/review-log.md`'s own historical Pass 7/8 entries (now moved to
  `docs/archive/review-log-archive.md`, itself never read by agents) and `docs/requirements.md`'s own
  changelog describing its own history. No live doc, test, or code file cites a dangling `§11`.
- **`design\.md.{0,10}§1[3-8]`:** all live hits are inside `docs/design/components.md`/`foundations.md`/
  `data-and-flow.md` citing `docs/design.md` **§0** (the load-bearing-decisions section, which correctly
  stayed in the thin index and was never renumbered) — a false-positive match on the regex's `§1` prefix,
  not an actual §13–§18 citation. No genuine old-numbering hit found live anywhere.

**However, a broader sweep for `design\.md §<N>` (any number) and `docs/design.md §18` specifically
surfaced citations the cleanup rounds missed:**

- **`docs/handoff.md:78, 81, 92, 99`** — four instances of "design §18.4" / "per §18.4" / "design §18.5",
  a dev-owned document describing the 2026-07-16 shadow-removal handoff. `docs/design.md`'s §18 no longer
  exists as a numbered section post-split (folded into the unnumbered "Retired: shadow-pilot tracks" note)
  — these four citations are dangling. Not caught by the "dev fixed `docs/handoff.md`" cleanup round; see
  **REV-028** below.
- **`docs/test-report.md:35`** — qa's "latest run" narrative states "...marked ... RETIRED with a pointer
  to `docs/design.md` §18..." — same dangling §18 citation, in the one live (non-archived) qa document.
  See **REV-029** below.
- **`qa/test-plan-full-codebase.md:103`** (test P4-5) — still cites "`docs/design.md` §4.6", the
  pre-split numbering. This is the *same exact citation* that was correctly fixed elsewhere in the same
  file: P1-2 (line 49) now correctly reads "`docs/design/components.md` §4.6" for the identical fact (the
  retired `reminder` kind). P4-5's copy of the same citation was missed. See **REV-030** below.

No `docs/design.md §4`/`§3`/`§9`/`§10`/`§6` live citations were found that should point to a module file
instead, **other than** the P4-5 instance above — spot-checked `docs/idea-brief.md`, `README.md`,
`tests/test_config.py`, `tests/test_import_smoke.py`, `tests/test_state.py`,
`sql/drop_shadow_tables_migration.sql`: all correctly updated to either cite `docs/design.md §0` (correctly
unmoved) or the specific `docs/design/<module>.md §N` (correctly migrated), or to cite the "Retired:
shadow-pilot tracks" note by name with no number (robust to future renumbering).

### 3. `README.md`'s three REV-026 fixes — verified accurate, but one new staleness found

- **Paid-tier wording (line 42):** "Gemini Flash (Google's paid tier; cost is held by keeping call volume
  low... rather than a free-tier daily cap)" — matches `docs/requirements.md` NFR1 (§6, line 158) exactly:
  "Gemini now runs on Google's **paid tier**... cost held by low call volume, not a free-tier daily request
  cap." Accurate.
- **Citation (line 71 area):** the tunable-surface sentence now reads "...documented in the Configuration
  section of `docs/requirements.md` and defined in `scripts/config.py`" — the specific `§11`/`§10` number
  was dropped entirely rather than just corrected, which is a more robust fix (no longer vulnerable to a
  future renumbering). Accurate and resolves cleanly.
- **Handoff-doc claim (lines 49–53):** now reads "`docs/handoff.md` exists but covers only the
  shadow-tracks-removal increment, not general deploy procedure, so steps marked *(inferred)* below are not
  yet confirmed against a dedicated deploy handoff/runbook..." — accurate **as of when pm wrote it**
  (`43c4295`, before `docs/runbook.md` existed). **Now stale as a side effect of release's later REV-027
  fix:** `docs/runbook.md` exists today and its §2.3 gives the exact SQL migration apply order
  (`sql/scheduler_pgcron.sql` → `phase5_monitoring.sql` → `dashboard_latest_call_view.sql` →
  `drop_shadow_tables_migration.sql`) — directly resolving the first `(inferred)` marker at
  `README.md:59–60` ("exact apply order... confirm against a handoff"). The blanket claim "not yet
  confirmed against a dedicated deploy handoff/runbook" is therefore no longer true. The second
  `(inferred)` marker (`README.md:66–67`, Python version) genuinely remains unconfirmed — grepped
  `docs/runbook.md` for `3.12`/"Python version": zero hits, so that one is still accurately flagged. See
  **REV-032** below — a new finding, not a re-open of REV-026 (REV-026 itself is correctly resolved as
  originally scoped; this is churn introduced by the *subsequent* REV-027 fix landing after README.md's
  own fix).

### 4. `docs/runbook.md` — coherent, citations spot-checked, one mis-citation found

Read `docs/runbook.md` in full (409 lines). Spot-checked citations against their target module files:
- §1 "issues documented in `docs/design/components.md` §4.1" (scheduler unreliability) — confirmed:
  `components.md` §4.1 discusses GitHub's shared scheduler dropping ticks. Correct.
- §1 "`docs/design/components.md` §4.8" (dead-man monitor) — confirmed: §4.8 is exactly the reliability
  monitor section. Correct.
- §1 "`docs/design/frontend.md` §10" (password gate) — confirmed: §10 states "client-side SHA-256 passcode
  gate." Correct.
- §2.1 "`docs/design/components.md` §4.4" (paid-tier Gemini model) — confirmed: §4.4 is the AI judgment
  layer, states "Gemini Flash on Google's paid tier." Correct.
- §2.2 "`docs/design/components.md` §4.4" (retries, corrected timeout) — confirmed, both present in §4.4.
  Correct.
- §2.3 "`docs/design/components.md` §4.1" (native cron scheduler dropped ticks) — confirmed. Correct.
- §5 "`docs/requirements.md` §6, NFR1" — confirmed: NFR1 lives at `## 6. Non-Functional Requirements`,
  line 156–158. Correct.
- §7 "`docs/requirements.md` §10 (Configuration audit baseline)" — confirmed: `## 10. Configuration
  (tunables audit baseline)` at line 211, matching the post-renumbering current state. Correct.
- **§2.3, line 86 — mis-citation found:** "Fetches live prices via yfinance and commits `pages/prices.json`
  if prices changed (issue #18 CORS workaround; see `docs/design/components.md` §4.7 and
  `docs/requirements.md` Decision #18)." `docs/design/components.md` §4.7 is the **Detail page** section
  (FR14, FR2, FR11, FR23, NFR3, Decision #17) — it contains no CORS content at all. The CORS/prices.json
  workaround is actually documented in `docs/design/frontend.md` **§11**, "Browser-CORS constraint
  (Decision #18)" — an exact content and Decision-number match. This citation points a reader to the wrong
  module and section. See **REV-031** below.

### 5. Test suite — could not execute directly; corroborated by two independent methods

No shell/execute tool was available this session, so `python3 -m pytest -q --tb=short` could not be run
directly (same limitation disclosed by every prior pass since Pass 2). Two independent, non-execution
corroborations instead:

1. **Structural unchanged-ness:** `Glob scripts/*.py` (10 files) and `Glob tests/*.py` (9 files, incl.
   `conftest.py`) are byte-identical in file listing to Pass 7/8's last-confirmed state. The only
   `tests/` edits this chain made (`test_config.py`, `test_import_smoke.py`, `test_state.py`) were read in
   full and confirmed **docstring/comment-only** — no test function added, removed, or logically changed
   (all `def test_...` and `@pytest.mark.parametrize` lines are untouched; only citation text inside
   triple-quoted docstrings/comments changed).
2. **Fresh parametrize-expansion hand-count**, replicating Pass 4's archived method: `grep -c '^def
   test_'` per file gives identical raw counts to Pass 4's own hand-count (`test_prefilter.py` 30,
   `test_config.py` 26, `test_notify.py` 18, `test_ingest.py` 11, `test_ai_judge.py` 8, `test_state.py` 16,
   `test_textutil.py` 12, `test_import_smoke.py` 2), and identical `@pytest.mark.parametrize` decorator
   counts per file (`test_textutil.py` 1, `test_import_smoke.py` 2, `test_state.py` 3) — exactly matching
   Pass 4's figures, confirming no parametrize case list changed. Expanding by the same case-counts Pass 4
   verified (`test_state.py`→24, `test_textutil.py`→14, `test_import_smoke.py`→13 collected items) gives
   the same total: 30+26+18+11+8+24+14+13 = **144**, matching `docs/test-report.md`'s claimed
   "144 passed / 0 failed."

**Verdict: still 144/144, no count change** — high-confidence via structural comparison and independent
hand-count arithmetic, but **not a substitute for an actual `pytest -q` run**; recommend the orchestrator
or qa execute one, the same standing recommendation carried since Pass 2 and still never executed by a
reviewer session directly.

### New findings

**REV-028 — [BLOAT] minor (doc staleness, dangling cross-reference) — `docs/handoff.md:78, 81, 92, 99`.**
Four citations to "design §18.4" / "design §18.5" — `docs/design.md`'s §18 no longer exists as a numbered
section (folded into the unnumbered "Retired: shadow-pilot tracks" note by the `ea6843f` split). A reader
following these pointers today finds nothing at §18. Same staleness class as the already-resolved
REV-023/025. Not a blocker, not a major — informational-only doc pointers, no prescriptive content at
risk. **Owner: dev** (`docs/handoff.md` is dev-owned) — reword the four citations to name the "Retired:
shadow-pilot tracks" note directly (no number), matching how `sql/drop_shadow_tables_migration.sql`'s own
comment already does it correctly.

**REV-029 — [BLOAT] minor (doc staleness, dangling cross-reference) — `docs/test-report.md:35`.** qa's
live "latest run" narrative cites "a pointer to `docs/design.md` §18" — same dangling-§18 defect as
REV-028, in the one qa-owned live document (not the archive). **Owner: qa** — reword to name the "Retired:
shadow-pilot tracks" note directly, or drop the section-number claim.

**REV-030 — [BLOAT] minor (doc staleness, dangling cross-reference, inconsistent fix) —
`qa/test-plan-full-codebase.md:103` (test P4-5).** Still cites "`docs/design.md` §4.6" (pre-split
numbering). The identical citation, for the identical fact (the retired `notify.py` `reminder` kind), was
correctly updated at P1-2 (line 49) to "`docs/design/components.md` §4.6" — P4-5's copy of the same
citation was missed by the same cleanup pass that fixed P1-2. Not covered by this file's own front-matter
disclaimer (which explicitly scopes the "not individually rewritten" exemption to **SD v15** references
in named tests P1-3/P2-3/P2-6/P3-1–4/P3-8/P6-4 — P4-5 is not in that list, and this is a `docs/design.md`
citation, not an SD v15 one). **Owner: qa** — update P4-5's citation to `docs/design/components.md` §4.6,
matching P1-2's already-correct form.

**REV-031 — [BLOAT] minor (doc accuracy, wrong-section citation) — `docs/runbook.md:86`.** Cites
"`docs/design/components.md` §4.7" for the CORS/`prices.json` workaround; §4.7 is the Detail Page section
and contains no CORS content. The correct citation is `docs/design/frontend.md` §11 ("Browser-CORS
constraint (Decision #18)"), which is an exact content match (same Decision #18, same topic). Unlike
REV-028/029/030 (a number that no longer resolves at all), this citation *does* resolve — just to the
wrong content, which is arguably a more misleading failure mode (a reader lands on a real section that
doesn't answer their question, rather than getting an obvious dead pointer). Not a blocker, not a major —
no prescriptive/deploy-procedure content is wrong, only the pointer. **Owner: release** — correct the
citation to `docs/design/frontend.md` §11.

**REV-032 — [BLOAT] minor (doc staleness, introduced by REV-027's later fix) — `README.md:49–53, 59–60`.**
The "How to run" note's claim that steps are "not yet confirmed against a dedicated deploy handoff/runbook"
is now false — `docs/runbook.md` exists (`1355f11`/`42afaa2`, landed after pm's README fix `43c4295`) and
its §2.3 explicitly resolves the first `(inferred)` marker at lines 59–60 (exact SQL migration apply
order). The second `(inferred)` marker (lines 66–67, Python version) remains genuinely unconfirmed —
`docs/runbook.md` does not state the Python version either (confirmed absent by direct grep); that one can
stay as-is or be resolved by pointing at `.github/workflows/*.yml`'s `python-version: "3.12"` (present
verbatim in all three cron-triggered workflows). Not a blocker, not a major — this is inter-agent doc-sync
churn (REV-027's fix landing after REV-026's, in a document REV-026 doesn't own), not a new defect
introduced by either fix in isolation. **Owner: pm** (`README.md` is pm-owned) — update the note to
reflect that `docs/runbook.md` now exists and covers general deploy procedure; narrow or drop the
migration-order `(inferred)` marker; keep or resolve the Python-version one.

### REV-024/025/026/027 — closure disposition

**REV-024 — RESOLVED 2026-07-25.** Fixed by tech-lead in `ea6843f` (design.md split into thin index +
5 module files). Independently confirmed: all module files read in full, all under ~400 lines (max 207).

**REV-025 — RESOLVED 2026-07-25.** Fixed by tech-lead in `ea6843f` (the split subsumed the citation fix —
`docs/design.md:524`'s old content, "This mirrors `docs/requirements.md §11`", now reads correctly in
`docs/design/non-functional-ops.md` §9: "This mirrors the Configuration section of `docs/requirements.md`"
with no stale number). Independently confirmed by fresh repo-wide grep: zero live `requirements\.md
§11` hits outside the two explicitly-allowed historical locations.

**REV-026 — RESOLVED 2026-07-25.** Fixed by pm in `43c4295` (`README.md` paid-tier wording, handoff-doc
claim, and §11→no-number citation). Independently confirmed accurate against `docs/requirements.md` NFR1
and the Configuration section. (Note: the handoff-doc claim has since gone stale again for a different
reason — REV-027's later fix — logged as new finding REV-032 above, not a reopening of REV-026 itself.)

**REV-027 — RESOLVED 2026-07-25.** Fixed by release in `1355f11`/`42afaa2` (new `docs/runbook.md`, 409
lines, first-time engagement of the release agent). Independently confirmed coherent and mostly
accurately cited (7 of 8 spot-checked citations correct; one mis-citation logged as REV-031 above).

### Pass 9 summary

**New findings by tag:**
- `[BLOAT]` (doc staleness / cross-reference / accuracy): 5 (REV-028 minor — `docs/handoff.md` dangling
  §18.4/§18.5 citations, owner dev; REV-029 minor — `docs/test-report.md` dangling §18 citation, owner qa;
  REV-030 minor — `qa/test-plan-full-codebase.md` P4-5's dangling §4.6 citation, inconsistently missed
  versus P1-2's identical already-fixed citation, owner qa; REV-031 minor — `docs/runbook.md` wrong-section
  citation for the CORS workaround, owner release; REV-032 minor — `README.md`'s handoff/runbook claim gone
  stale as a side effect of REV-027's later fix, owner pm)
- `[REQUIREMENTS-GAP]` / `[DESIGN-GAP]` / `[CODE-GAP]` / `[TEST-GAP]` / `[SCOPE-CREEP]` / `[SECURITY]` /
  `[HARDCODED]` / `[GAP]`: 0 new

**Resolved this pass:** REV-024 (`docs/design.md` split, tech-lead, `ea6843f`), REV-025 (citation fix
subsumed by the split, tech-lead, `ea6843f`), REV-026 (`README.md` staleness, pm, `43c4295`), REV-027
(`docs/runbook.md` created, release, `1355f11`/`42afaa2`) — all four independently confirmed by direct
read and fresh grep, not taken on the fixing sessions' summaries.

**Open blocker count: 0.**
**Open major count: 0.**
**Open minor count: 5** (REV-028 dev, REV-029 qa, REV-030 qa, REV-031 release, REV-032 pm — all doc
cross-reference/citation staleness, none affecting prescriptive/build content, none blocking the pipeline).

### Verdict — Pass 9

**CLEAR to continue the pipeline: 0 blockers, 0 majors.** The full chain (REV-024 through REV-027) is
genuinely resolved, independently verified rather than rubber-stamped: the `docs/design.md` split is sound
(all module files well under the 400-line threshold, module map accurate, no content found missing),
`README.md`'s three REV-026 items are accurate, and `docs/runbook.md` is coherent with correctly-resolving
citations in 7 of 8 spot-checks. Passes 7 and 8 are fully closed out (nothing open from either span) and
archived to `docs/archive/review-log-archive.md` per doc-hygiene.

**This pass is not a rubber stamp, however: five new minor findings** (REV-028 through REV-032) surfaced
during independent verification, all in the same low-stakes "stale cross-reference/citation" class as the
already-resolved REV-023/025/026, and all a byproduct of the same churn (the design.md split plus two
follow-up cleanup rounds missed a handful of instances; the runbook's later arrival than README's fix
introduced one further staleness). None are blockers or majors, none mislead a reader about what to build,
and none require re-opening REV-024/025/026/027 themselves — routed to their respective owners (dev, qa
×2, release, pm) for the next convenient pass.

**Method caveats (disclosed, not silently assumed away):** (a) no shell-execution tool available this
session — the `docs/design.md` split's content-completeness was verified by cross-session comparison
against Pass 7/8's own prior direct reads, not a byte-level `git show ea6843f` diff; (b) the test suite
could not be executed directly — the "still 144/144" conclusion rests on structural file-listing
comparison plus an independent parametrize-expansion hand-count matching Pass 4's own archived arithmetic
exactly, not a live `pytest -q` run. Recommend the orchestrator or qa execute one directly as final
machine-verified confirmation, the same standing recommendation carried since Pass 2.
