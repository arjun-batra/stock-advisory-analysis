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
