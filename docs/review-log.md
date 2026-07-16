# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–5 (2026-07-12 through 2026-07-15) — archived

Passes 1–5 (baseline adoption audit, post-debt-cleanup re-audit, INC-1 NSE-shadow-pilot pre-merge audit,
INC-2 shared-eval-harness pre-merge audit, and the post-Pass-4 cleanup independent re-verification) are
archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene rule ("reviewer: on
clearing an increment, move RESOLVED entries to `docs/archive/review-log-archive.md`"), archived
2026-07-16 when Pass 6 (below) cleared with zero blockers. All REV-001 through REV-021 items from that
span are now either RESOLVED, `ACCEPTED-DEBT`, or **MOOT** (REV-015, REV-018, REV-020, REV-021 — the four
still open at the end of Pass 5 — were superseded 2026-07-16 when the shadow-pilot removal change request
deleted the files/sections they concerned; see Pass 6's "Re-check of prior open items" below). Nothing
from that span remains open. Agents never read `docs/archive/` per `CLAUDE.md`.

---

## Pass 6 — 2026-07-16 (shadow-pilot removal change request — diff-scoped pre-merge audit)

Scope: diff-scoped audit per `CLAUDE.md` Phase 3d of everything changed since the last reviewer
clearance (commit `228e8dd`), for the change request retiring FR24–FR31/NFR5 (US/TSX shadow pilot +
shared eval harness) and FR32–FR39/NFR6 (NSE shadow pilot). Branch
`claude/remove-us-tsx-nse-experiment-jb94x1` (6 commits: `42d7858`, `07c48e5`, `6233973`, `148b081`,
`4a61d29`, `4779e90`). **Method note:** no shell/execute tool available this session (Read/Grep/Glob/
Write/Edit only, consistent with every prior pass) — I could not run `git diff --name-only 228e8dd..HEAD`
or `pytest` myself. Substituted `Glob`/`Grep` over the current working tree to independently confirm file
presence/absence (deleted files verified genuinely absent via directory listing, not just taken on the
task brief's word) and to case-insensitively grep the entire repo for `shadow` (excluding `.git/`) rather
than trusting dev's/qa's own sweep claims. Read every file the task brief named in full or in relevant
part: `docs/requirements.md` (full), `docs/design.md` (header + §§13–18 in full, plus targeted greps of
§9/§16.6/§17.4's tunable tables), `scripts/config.py` (full), `.github/workflows/hourly-watchlist.yml`
(full), `sql/drop_shadow_tables_migration.sql` (full), `docs/handoff.md` (full), `docs/test-report.md`
(full), `qa/test-plan-full-codebase.md` (Phase 3/6 sections), `README.md` (full), `tests/test_import_smoke.py`
(full), `tests/conftest.py` (fixture-class grep), `scripts/run_hourly.py` (targeted grep),
`scripts/ai_judge.py` (`_generate` docstring), `requirements.txt` (full).

### Pass 1 — Traceability, requirements → code

Independently verified every retired FR/NFR ID is consistently marked retired across all three docs, not
taken on the changelog's word:
- `docs/requirements.md` §10 top-level note + §10.1/§10.2/§10.3 section headers + the NFR5/NFR6 block at
  the bottom + both "Experimental" §11 tunable-table headers all read **RETIRED (2026-07-16)**, with FR
  text kept verbatim below each notice for removal-traceability only, exactly as the 2026-07-16 changelog
  entries describe. No dangling "active"/"MAY run" framing found outside the verbatim-preserved historical
  FR clause text itself (which is correctly labeled as historical, not current).
- `docs/design.md` header (lines 3–12), §13/§14/§16/§17 (all four independently read in full) and the §15
  coverage map (line 658–660) all consistently say RETIRED, point back to `docs/requirements.md` §10.1–
  §10.3 for the verbatim FR text, and correctly distinguish the *unrelated* paid-tier/`gemini-2.5-flash`
  model-default correction (still active, §4.4/§9) from the retired shadow-specific content — this
  distinction is real and correctly drawn, not a hand-wave (confirmed `scripts/config.py:26-27`'s
  `GEMINI_MODEL`/`GEMINI_MODEL_BACKUP` defaults are untouched by the removal and still `gemini-2.5-flash`/
  `gemini-2.5-flash-lite`).
- `docs/design.md` §18 (the removal plan) maps every retired FR/NFR ID to a concrete file/config/SQL/test
  action, and I independently confirmed every one of those actions actually happened (see Pass 3 below) —
  the plan was executed, not just written.
- No traceability gap: every retired ID has a design disposition (§13/§16/§17/§18) and a code-removal
  action, and qa's regression pass (`docs/test-report.md`) confirms the resulting test suite has zero
  shadow-related collection errors. Nothing FR24–FR39/NFR5–6-shaped was left half-designed or
  half-removed.

### Pass 2 — Completeness (orphaned "shadow" references)

Grepped the entire repository, case-insensitive, for `shadow` (excluding `.git/`) myself rather than
trusting dev's/qa's own sweep claims in `docs/handoff.md`/`docs/test-report.md`. 11 files matched:

| File | Disposition |
|---|---|
| `docs/test-report.md`, `docs/archive/test-report-archive.md` | qa-owned, correctly historical/retirement-framed |
| `qa/test-plan-full-codebase.md` | correctly retired (Phase 6 struck, P3-1/P3-7 corrected) — read in full, confirmed |
| `docs/handoff.md` | dev-owned, entirely about this removal increment — correct |
| `sql/drop_shadow_tables_migration.sql` | the new migration itself — correct, see Pass 5 below |
| `docs/design.md`, `docs/requirements.md`, `docs/review-log.md` | all correctly retired/historical framing, verified above and by this log's own history |
| `docs/idea-brief.md` | **see REV-022 below — stale, flagged as a new finding** |
| `requirements_docs/stock-advisor-ui-handoff-v3-spec.md` | "no shadows" is a CSS box-shadow styling rule — unrelated, not a finding (confirmed by direct read) |
| `.gitignore` | `.shadow-pilot-session-state.md` — a Claude-Code build-session scratch-file naming convention, unrelated to the `call_log_shadow` feature — confirmed by direct read, not a finding |

`scripts/`, `sql/` (apart from the new drop migration), `.github/workflows/`, and `tests/` all returned
**zero** matches for `shadow` (case-insensitive) — independently confirmed by my own grep, not dev's or
qa's. `Glob` confirmed all six named-for-deletion files (`scripts/shadow.py`, `scripts/run_shadow.py`,
`scripts/run_shadow_nse.py`, `scripts/wallet_sim.py`, `scripts/eval_shadow.py`, and the two shadow SQL
migrations) and all five named-for-deletion test files (`tests/test_shadow.py`, `tests/test_run_shadow.py`,
`tests/test_run_shadow_nse.py`, `tests/test_wallet_sim.py`, `tests/test_eval_shadow.py`) are genuinely
absent from the working tree, not merely emptied or renamed.

**REV-022 — [BLOAT] minor (doc staleness) — `docs/idea-brief.md:110-127`.** The "Experimental addition
(NOT core v1 scope): shadow wallet pilot" section still describes both shadow tracks in present-tense,
active-feature language ("A parallel, **non-production** AI verdict track... It writes only to its own
isolated table, never alerts... gated by a kill switch that defaults ON," "A **second, independent shadow
track for NSE tickers** was added...") with no retirement notice at all — it reads as if FR24–FR30/NFR5
and FR32–FR39/NFR6 are still live requirements. `docs/handoff.md`'s own repo-wide grep sweep (line 47)
already flagged this exact file to pm ("`docs/idea-brief.md`, `README.md` — pm-owned; `README.md` still
describes the shadow pilot as a current feature... flagging to pm") — `README.md` was subsequently fixed
(confirmed no `shadow` hits remain in it, see Pass 2 table above), but `idea-brief.md` was not. This file
was not itself touched by this increment's diff, but per this pass's audit criterion #2 ("no dangling
'active' references left... anywhere in docs or code") and `CLAUDE.md`'s non-negotiable ("Docs stay in
sync with reality — a stale doc is a bug"), a live pm-owned artifact describing retired FR/NFR IDs as
current scope is a genuine finding, not pedantry — a future reader of `idea-brief.md` alone (without
cross-referencing `requirements.md`'s retirement notices) would believe both shadow pilots are still
running. **Not a blocker** — `idea-brief.md` is not the source of truth for FR/NFR status (`requirements.md`
is, and it is correctly retired there); this is a secondary-doc staleness issue, the same class and
severity as the historical REV-017/REV-021 design.md staleness findings. **Owner: pm** (`docs/idea-brief.md`
is pm-owned) — add a short retirement note (mirroring `requirements.md` §10's top-level notice) or trim the
section to a one-line historical pointer.

### Pass 3 — Correctness (production code paths FR1–FR23 untouched)

Read `scripts/config.py` in full: confirmed zero `SHADOW_*`/`EVAL_WINDOW_DAYS` names remain, and every
production tunable (`GEMINI_MODEL`/`_BACKUP`, `NSE_GEMINI_MODEL`/`_BACKUP`, `GEMINI_MAX_RETRIES`/
`_RETRY_BASE_MS`/`_TIMEOUT_MS`, `YF_*`, `HEADLINES_LIMIT`, `NOTIF_BODY_MAX`, `RATIONALE_MAX`, all
`DISCOVERY_*` gates, `MARKET_*`/`NSE_MARKET_*`, `RUNTIME_CLOSE_GRACE_MIN`) and every function
(`discovery_models`, `nse_models`, `is_market_open`, `is_nse_open`, `require_secrets`) is present,
unchanged in signature/default, and — specifically for `nse_models()` — confirmed by direct grep of
`scripts/run_hourly.py:39,48` that it is genuinely called by **production** NSE dispatch (not a shadow-only
leftover; the name-overlap concern the task brief flagged is a non-issue). Read
`.github/workflows/hourly-watchlist.yml` in full: exactly one job, one step (`Run hourly watchlist check`),
byte-for-byte the production step with only the one documented comment reword (`GEMINI_MAX_RETRIES`
comment: "shared by the production and shadow tracks" → "shared by the production track") — no shadow
step, no `SHADOW_TIMEOUT_MINUTES`/`SHADOW_ENABLED`/`SHADOW_NSE_*` env reference anywhere. Read
`scripts/ai_judge.py`'s `_generate` docstring: the shadow clause is genuinely gone ("THE shared call path:
production watchlist/discovery (judge_batch) funnels every API request through here" — no
`shadow.judge_batch_shadow` mention), confirmed no behavior change (grepped the full file for `shadow`,
zero hits, and the retry/backoff logic itself — `_is_retryable`, the exponential-jitter sleep — reads
identically to Pass 3/4's prior independently-verified description). Grepped `scripts/` for any
`import shadow`/`from shadow`/`judge_batch_shadow`/`wallet_sim`/`eval_shadow` reference: zero hits — no
orphaned import anywhere. `tests/test_import_smoke.py`'s module-discovery is glob-based
(`SCRIPTS_DIR.glob("*.py")`) and its entry-point list is now a plain 3-item list
(`run_hourly`/`run_discovery`/`publish_prices`), matching design §18.4's instruction exactly — no stale
hardcoded 4-entry-point list left behind. `tests/conftest.py` confirmed to contain no
`FakeShadowSupabase`/`FakeShadowNseSupabase` class (grepped for `class Fake`; only the pre-existing Gemini
fakes remain, which `test_ai_judge.py` still legitimately uses). **No accidental deletion of shared/
production code found; FR1–FR23 code paths are intact.**

### Pass 4 — Hardcoding audit / docs-in-sync non-negotiable

No new tunables or literals introduced by this removal (it is a pure deletion/edit, adds no new business
logic). `sql/drop_shadow_tables_migration.sql` introduces no config surface (correctly — a one-time DROP
has nothing to tune). Cross-checked `docs/requirements.md` §11's now-retired "Experimental" tunable tables
against `docs/design.md` §9/§16.6/§17.4's matching retirement notices for `SHADOW_ENABLED`,
`SHADOW_PROMPT_VARIANT`, `SHADOW_SNAPSHOT_LOOKBACK_MIN`, `SHADOW_NSE_ENABLED`, `SHADOW_NSE_PROMPT_VARIANT`,
`SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN`, `EVAL_WINDOW_DAYS`, and the REV-015 `SHADOW_TIMEOUT_MINUTES` workflow
Variable — all seven are consistently marked retired in both docs, and I confirmed by direct read of
`scripts/config.py` and `.github/workflows/hourly-watchlist.yml` (Pass 3 above) that none of the seven
exist in code anymore. No sync gap.

**Independently re-verified the "144 passed / 0 failed" claim in `docs/test-report.md` by hand-counting
test items myself** (no shell access this session, same limitation as every prior pass) rather than taking
qa's number on faith: `grep -c '^def test_'` per file gives `test_prefilter.py` 30, `test_config.py` 26,
`test_notify.py` 18, `test_ingest.py` 11, `test_ai_judge.py` 8, `test_state.py` 16 raw defs, `test_textutil.py`
12 raw defs, `test_import_smoke.py` 2 raw defs. Reading every `@pytest.mark.parametrize` decorator directly
(`test_state.py` has three: a 6-case `before,after` matrix, a 3-case and a 2-case `verdict` list;
`test_textutil.py` has one 3-case `limit` list; `test_import_smoke.py` has a 10-item `MODULE_NAMES` glob
list and a 3-item `entry_point` list) and expanding raw defs to actual collected test items:
`test_state.py` → 24, `test_textutil.py` → 14, `test_import_smoke.py` → 13. Total:
30+26+18+11+8+24+14+13 = **144**, exactly matching `docs/test-report.md`'s claimed figure. This is genuine
independent corroboration via full parametrize-expansion arithmetic, not a re-statement of qa's number —
flagging as resolved the standing "someone should run live pytest" request only insofar as this
hand-verification gives high confidence the count is real; it is still not a substitute for an actual
`pytest -q` run (same disclosed method caveat as Pass 2/4/5).

### Pass 5 — Security audit / migration correctness

Read `sql/drop_shadow_tables_migration.sql` in full:
```sql
DROP TABLE IF EXISTS call_log_shadow;
DROP TABLE IF EXISTS call_log_shadow_nse;
```
Exactly the two retired shadow tables, both with `IF EXISTS` guards (safe to run whether or not the tables
currently exist), no other statement, correctly commented with the design §18.3 pointer and the FR IDs it
covers. Confirmed **documented as not-yet-applied** in three independent places, all consistent with each
other: `docs/handoff.md` ("**Not yet applied to the live Supabase project** — that is a separate,
explicitly-authorized step for the orchestrator"), `docs/test-report.md` ("has not yet been applied to the
live Supabase project — the `call_log_shadow`/`call_log_shadow_nse` tables may still exist in the live
DB"), and `qa/test-plan-full-codebase.md` P3-1 ("as of this test-plan update it had not yet been applied to
the live project"). No doc claims it has been applied — no false "done" claim, matching the task brief's
statement that live application is a separate authorized step out of this audit's scope. No committed
secrets in any new/changed file (grepped `scripts/config.py`, `sql/drop_shadow_tables_migration.sql`,
`.github/workflows/hourly-watchlist.yml`, `docs/handoff.md`, `docs/test-report.md` for API-key/token/PAT
patterns — only the pre-existing, already-accepted `sb_secret_...` naming-convention comment in
`config.py:15`, unchanged from every prior pass). No new network/file operations, no new trust-boundary
surface introduced by a pure-deletion change.

### Re-check of prior open items

Not re-litigated in depth (out of this diff's file scope — none of `run_shadow.py`/`hourly-watchlist.yml`'s
`SHADOW_TIMEOUT_MINUTES` prose/`test-report.md` §10.1 exist to re-check anymore, since the files they lived
in are deleted or superseded by this pass's fresh `docs/test-report.md`). **REV-015, REV-018, REV-020,
REV-021** are now moot: REV-015/REV-021 concerned a workflow `timeout-minutes` literal on the now-deleted
shadow steps; REV-018 concerned `run_shadow.py::main()`'s exception handling, and that file is now deleted
outright; REV-020 concerned per-file test counts in a `test-report.md` section that has itself been
superseded (the old run archived, per doc hygiene). Marking all four **MOOT (removal supersedes)**, dated
2026-07-16 — not RESOLVED (nobody fixed the underlying code; the code they were about no longer exists) and
not silently dropped. **REV-002/REV-006/REV-016/REV-017/REV-019** were already fully resolved/disposed of
by Pass 4/5 and remain so — the FR31 harness they concerned is itself now retired and deleted, consistent
with the requirements.md changelog.

### Pass 6 summary

**New findings by tag:**
- `[BLOAT]` (doc staleness): 1 (REV-022, minor — `docs/idea-brief.md` still describes both retired shadow
  pilots as active scope; `README.md`'s equivalent staleness was already caught and fixed this same pass by
  pm, per dev's handoff sweep)
- `[REQUIREMENTS-GAP]` / `[DESIGN-GAP]` / `[CODE-GAP]` / `[TEST-GAP]` / `[SCOPE-CREEP]` / `[SECURITY]` /
  `[HARDCODED]`: 0

**Resolved this pass:** none newly resolved (nothing open from Pass 5 fell within this diff's file scope to
re-verify).

**Marked MOOT this pass (4):** REV-015, REV-018, REV-020, REV-021 — all concerned files/sections deleted or
superseded by this removal; the underlying code/doc-section they referenced no longer exists, so there is
nothing left to fix or re-check. Not counted as open or as newly resolved.

**Open blocker count: 0.**
**Open major count: 0.**
**Open minor count: 1** (REV-022, new this pass — pm-owned `docs/idea-brief.md` staleness).
**ACCEPTED-DEBT count: 0** (REV-006 was specific to the now-deleted live-infra-dependent shadow orchestration
test gap — retired alongside the code it concerned; no longer applicable).

### Verdict — shadow-pilot removal change request

**CLEAR TO MERGE. 0 blockers, 0 majors.** Every retired FR/NFR ID (FR24–FR39, NFR5–NFR6) is consistently
and correctly marked retired across `docs/requirements.md`, `docs/design.md`, `qa/test-plan-full-codebase.md`,
and `docs/test-report.md` — independently verified by direct read, not taken on trust. A full-repo,
case-insensitive grep for `shadow` (my own, not dev's/qa's sweep) confirms zero orphaned references in
`scripts/`, `sql/` (apart from the new, correct drop migration), `.github/workflows/`, or `tests/`; the two
remaining doc-level hits outside already-correctly-retired locations (`.gitignore`'s unrelated session-file
name, `requirements_docs/`'s unrelated CSS "no shadows" rule) are genuinely unrelated to the feature, not
missed cleanup. Production code paths (FR1–FR23) are confirmed untouched: `nse_models()` still exists and
is confirmed called by production NSE dispatch in `run_hourly.py`, every other `scripts/config.py` tunable
and function is present and unchanged, and the workflow YAML runs exactly one (production) step. The new
`sql/drop_shadow_tables_migration.sql` is correct — drops exactly `call_log_shadow` and
`call_log_shadow_nse`, both `IF EXISTS`-guarded, and is consistently documented in three places as not yet
applied to the live database (a separate, explicitly-authorized step, correctly out of this audit's scope
per the task brief). The claimed "144 passed / 0 failed" test result was independently corroborated by hand
via full parametrize-expansion arithmetic (144 exactly), not merely re-stated from qa's report. No hardcoded
tunables introduced (this is a pure deletion/edit); no new security surface.

**One open minor, not blocking:** **REV-022** — `docs/idea-brief.md`'s "Experimental addition... shadow
wallet pilot" section is stale (present-tense, active-feature language for both retired tracks), the one
place this sweep found that `docs/handoff.md`'s own repo-wide grep flagged to pm but which does not appear
to have been fixed yet (unlike its `README.md` sibling, which was). Route to **pm**.

**Four prior open items (REV-015, REV-018, REV-020, REV-021) are now MOOT**, not resolved and not
reopened — the files/sections they concerned were deleted or superseded by this removal itself.

**Method caveat (unchanged from every prior pass):** no shell-execution tool available this session — the
144-test claim rests on careful, fully-shown parametrize-expansion arithmetic by hand rather than an actual
`pytest -q` run. Recommend the orchestrator or qa run one live `python3 -m pytest tests/ -q` as a final
machine-verified confirmation, the same standing recommendation carried since Pass 2 and still never
executed by a reviewer session directly.
