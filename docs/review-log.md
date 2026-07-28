# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–12 (2026-07-12 through 2026-07-28) — archived

Passes 1–12 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene
rule. Passes 1–9 were archived across Passes 6, 9 and 10 as their chains closed; Passes 10 and 11 were
archived at Pass 12's close; Pass 12 was archived 2026-07-28 at this Pass 13's close, with its per-finding
closing disposition (REV-062 through REV-070) appended there. Nothing from Passes 1–11 remains open. The
still-open items from Pass 12 and earlier are carried forward in full below and are **not** in the archive
as open work. Agents never read `docs/archive/` per `CLAUDE.md`.

---

## Pass 13 — 2026-07-28 (independent re-verification of REV-062 + INC-3 clearance decision)

**Scope.** Narrow and targeted, in the same shape as Pass 10's re-verification of the REV-023–032 chain:
confirm or deny that Pass 12's blocker REV-062 is genuinely closed, re-check every other item Pass 12 left
open, and issue a clean clearance decision for INC-3. Files read in full or in the cited region:
`sql/phase5_monitoring.sql`, `sql/fix_missing_degraded_checks.sql`, `sql/dedup_watchlist_health_check.sql`,
`sql/kill_switch.sql`, `sql/schema.sql`, `docs/runbook.md`, `docs/design/components.md`,
`docs/design/non-functional-ops.md`, `.github/workflows/hourly-watchlist.yml`,
`.github/workflows/daily-discovery.yml`.

**Method.** Every claim below is derived from the *current* content of the named file at the named line.
tech-lead's fix commit message, the headers the fix itself wrote, and any agent self-report were treated
as claims to be tested, not as evidence. Where a fix's own header asserts something about *another* file,
I opened that other file and checked (this caught REV-071 below).

**Method caveat (standing, unchanged since Pass 2):** no shell/execute tool and no live Supabase access
this session. `pytest -q` was not run by me; no `list_tables`/`pg_class` introspection was possible.
Arjun has deferred applying any SQL from this change request to the live project, so INC-3's AC1–AC5
remain unverifiable by anyone — reviewer included — until apply time (REV-070). That deferral is
respected, not worked around, and it bounds what "CLEAR" means below.

---

### 1. REV-062 — RESOLVED 2026-07-28. Verified against all six of its acceptance conditions.

**(a) Sole definition.** A repo-wide grep for `create or replace function public.check_pipeline_health`
returns exactly one live hit: `sql/phase5_monitoring.sql:123`. The only other match anywhere is the prose
of REV-062 itself in this log. The three-body conflict is gone, not relocated.

**(b) Kill-switch pause check present.** `sql/phase5_monitoring.sql:159-165` — the
`select paused, (case when not paused then updated_at end) into v_paused, v_resume_baseline` read,
followed by `if v_paused then return;`. It sits after the weekend guard and *before* every
`_raise_monitor`/`_clear_monitor` call site in the function, so FR25's "zero alerts while paused" is
structural, exactly as it was in INC-3's original edit.

**(c) Resume baseline on ALL FOUR staleness branches — the condition I was most concerned would be
partially applied.** Confirmed by grepping `GREATEST(` and checking each hit in context. Four code
occurrences, one per branch, no branch missed:

| Branch | Line | Comparison |
|---|---|---|
| Watchlist (merged ET/IST) | `:194` | `p_now - GREATEST(wl_last, v_resume_baseline) > interval '70 minutes'` |
| Discovery NA | `:221` | `GREATEST(disc_last, v_resume_baseline) < date_trunc('day', p_now) + interval '21 hours'` |
| Discovery IN | `:249` | `GREATEST(disc_in_last, v_resume_baseline) < date_trunc('day', p_now) + interval '9 hours 30 minutes'` |
| Publish-prices | `:279` | `p_now - GREATEST(pp_last, v_resume_baseline) > interval '70 minutes'` |

The remaining three `GREATEST` hits (`:26, :151, :179`) are comment text. Display text still interpolates
the raw un-adjusted timestamp (`:195` computes `mins` from `coalesce(wl_last, p_now)`, not from the
`GREATEST`), preserving the decision-vs-display separation `operational-controls.md` §13.4 requires.

**(d) Degraded branches present — the previously dead reads are now read.** `disc_status` at `:227`,
`disc_in_status` at `:255`, `pp_status` at `:285`, each an `elsif ... is not null and ... <> 'ok'` raising
a `degraded` alert. All three variables are now declared *and* consumed (`:132-134`). REV-042's exact
defect — selected and never read — is gone.

**(e) ET/IST dedup landed, with the resume-baseline fix inside it exactly once.** `:182-188` computes
`v_session_active` / `v_session_label` once; `:190-214` is a single evaluation branch. The
`GREATEST(wl_last, v_resume_baseline)` appears **once** at `:194` — not duplicated across two surviving
branches, and not dropped in the collapse. The only thing that genuinely differed between the old ET and
IST blocks (the message suffix) is parameterized at `:201` as
`case when v_session_label = 'IST' then ' during the NSE session' else '' end`. This was the part of the
merge I flagged as "not mechanical" in REV-062's suggested fix; it was done correctly.

**(f) NULL semantics preserved for a never-paused system.** With no `kill_switch_state` row, both
`v_paused` and `v_resume_baseline` are NULL; `if v_paused then` is not taken (NULL is not true) and
Postgres's `GREATEST` ignores NULL operands, so every comparison falls back to the real `last_run_at`.
The comment at `:155-158` states this and it is correct as written.

**(g) The two superseded files can no longer be applied.** Both are now comment-only files — zero
executable statements, so pasting either into a SQL editor is a no-op rather than a silent revert:
- `sql/fix_missing_degraded_checks.sql` (29 lines) and `sql/dedup_watchlist_health_check.sql` (36 lines)
  both open with `-- SUPERSEDED — DO NOT APPLY` as the literal first content line, state what they
  originally shipped, cite REV-062, say where the reconciled function now lives, and point at
  `docs/runbook.md` §2.3 and `git log -p` for the original bodies.
- This is the "clearly marked, not silently emptied" outcome the task asked me to distinguish. An operator
  or agent opening either file learns *why* it is inert. I specifically checked the dedup file's old
  self-contradicting header (which cited INC-3's `GREATEST` change as motivation while omitting it) — it
  has been replaced and the contradiction is now written down as history at `:8-12`.

**(h) Nothing else in the repo still points at them as appliable.** Grepped both filenames repo-wide
(excluding `docs/archive/`): the only live references are the two files' own headers,
`sql/phase5_monitoring.sql:21-35`, `docs/runbook.md:74,82`, and `docs/design/non-functional-ops.md:89-96`
— every one of which marks them superseded. The design module was updated too, which REV-062 did not
explicitly ask for; that is a genuine improvement, not a gap.

**Consequence: REV-042 and REV-047 are now fully RESOLVED**, promoted from Pass 12's
"resolved-with-dependency" holding state. Their corrective logic is live in the single reconciled function
and there is no longer an apply path that reverts it.

---

### 2. Runbook re-check — REV-063 and REV-069

**REV-063 — PARTIALLY RESOLVED. Runbook half closed; SQL-header half still open, downgraded to minor.**
- **Closed:** `docs/runbook.md:71` now lists `sql/kill_switch.sql` as **step 1** of §2.3's apply order,
  with the "must be applied first" rationale (both `dispatch_github_workflow()` and
  `check_pipeline_health()` read `kill_switch_state`) and an explicit note that it was previously missing.
  `:78` correctly reads "These six migrations" (was five). The operator-facing defect — the documented
  authority omitting a file another file said must come first — is gone.
- **Also closed by the same edit:** `docs/runbook.md:82` replaces the old line-81 instruction with a
  **"Superseded — do not apply"** paragraph naming both files and explaining the REV-062 history. The
  instruction to apply the dedup file alone, which would have reverted FR25/NFR2, no longer exists
  anywhere in the runbook. This was the sharpest edge of REV-062 and it is properly gone.
- **Still open (now minor, owner dev):** REV-063's second half was "have `sql/kill_switch.sql` and
  `sql/schema.sql` headers point at §2.3 instead of restating an order each." Neither did.
  `sql/kill_switch.sql:8-17` still restates the order inline and contains **no reference to
  `docs/runbook.md` at all** (grepped `runbook` across `sql/` — `kill_switch.sql` returns zero hits).
  `sql/schema.sql:32-37` still enumerates a five-file order and — the part that matters — **omits
  `sql/kill_switch.sql` entirely**, i.e. it still names `sql/scheduler_pgcron.sql` as the first file to
  apply, which is precisely what the runbook fix just established is wrong. It does now add "See
  `docs/runbook.md` §2.3 for the full, corrected order" at `:37`, which is why this is a minor and not a
  major: a reader who follows that pointer gets the right answer. But the stale enumeration is still sat
  directly above the pointer, and "state anything once" is still violated in three places.

**REV-069 — RESOLVED 2026-07-28, as a side effect of the same runbook edit.** `docs/runbook.md:347-350`
no longer says "The four migrations"; it now enumerates all six (`kill_switch.sql`, `scheduler_pgcron.sql`,
`schema.sql`, `phase5_monitoring.sql`, `dashboard_latest_call_view.sql`, `enable_monitor_alerts_rls.sql`)
and references "§2.3's apply order". The count/content mismatch and the false "No other DDL is needed"
completeness claim are both fixed. §5's list is still an enumeration rather than a pure cross-reference,
but it is now a *correct* one, so the finding is closed rather than carried.

---

### 3. Re-check of the rest of Pass 12 — what the fix did NOT touch

**REV-064 — STILL OPEN, and broader than originally logged. Major.** The runbook edit touched §2.3 and §5;
it did not touch §2.2. `docs/runbook.md:46-51` still instructs the operator to create all six model
Variables (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `NSE_GEMINI_MODEL`, `NSE_GEMINI_MODEL_BACKUP`,
`DISCOVERY_GEMINI_MODEL`, `DISCOVERY_GEMINI_MODEL_BACKUP`) with documented defaults. I re-confirmed none
is read: grepping both workflow YAMLs for those names returns only *comment* lines
(`hourly-watchlist.yml:51-52`, `daily-discovery.yml:48-49`) explaining that `scripts/config.py` is now the
source of truth — zero `${{ vars.* }}` wiring. Two additional stale locations this pass found that Pass 12
did not cite, and which should be fixed in the same edit:
- `docs/runbook.md:339` (§7 Configuration Reference) re-lists all nine Variables including the six dead
  ones, as "Variables (all optional, defaults applied if unset)".
- `docs/runbook.md:390` (§8 Configuration Tuning) still says "**Via Variables (recommended for model
  swaps):** Update the Variable in GitHub Actions Settings; the next workflow dispatch will pick up the
  new value." That is now false for exactly the case it recommends — a model swap.

The three surviving retry Variables (`GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BASE_MS`, `GEMINI_TIMEOUT_MS`)
**are** still wired (`hourly-watchlist.yml:67`, `daily-discovery.yml:61`) and must not be removed.
Owner: **release**.

**REV-067 — STILL OPEN and now materially worse. Minor.** The reconciliation shifted
`phase5_monitoring.sql` line numbers and changed one of the facts the table asserts, and
`docs/design/components.md:50-56` was not updated:
- Rows 5–6 cite `phase5_monitoring.sql:125` and `:153` for the monitor grace windows; they are now at
  `:182` and `:185`.
- Row 7 says `interval '70 minutes'`, "**three copies**" at `:129,157,229`. After REV-047's dedup there
  are now **two** copies, at `:194` and `:279`. The count is wrong, not just the line numbers — and the
  count is the thing that table exists to track.
- Rows 1–4 remain wrong in the way Pass 12 described: `scheduler_pgcron.sql:279` in a 184-line file, and
  `dispatch_watchlist_if_open()` is actually in `phase5_monitoring.sql` (now `:318-338`).
Owner: **tech-lead**.

**Unchanged and still open, re-confirmed this pass by direct read:** REV-065 (minor, tech-lead —
`non-functional-ops.md:155-163,186-189` still describes the abandoned `vars.X || 'default'` convention and
wiring that no longer exists), REV-066 (minor, tech-lead + pm — `NTFY_BASE_URL`/`NTFY_TIMEOUT_SECONDS`
still absent from every config baseline; repo-wide grep of `docs/` still returns zero hits), REV-068
(minor, pm — `requirements.md` still has zero `two-tier|fail-loud|SystemExit` hits and still names the
stale `config/tunables_cache.json` path), REV-070 (minor, qa + release — AC1–AC5 still unexecuted; this is
the deferral, not a defect), REV-039 doc half (major, release — folded into REV-064), REV-043 (major, dev
— `get_price_only` still absent from `scripts/ingest.py`), REV-048 (minor, qa — drift test still not
built), REV-049(b) (minor, release — portal CI story still undecided), REV-052 (minor, tech-lead + pm —
see REV-066).

---

### NEW FINDINGS — Pass 13

**REV-071 — `[DESIGN-GAP]` — minor — the runbook's new apply-order note asserts a cross-reference state
that does not exist in either file it names.**
Location: `docs/runbook.md:70` vs `sql/kill_switch.sql:8-17` and `sql/schema.sql:32-37`.
Description: the corrected §2.3 opens "This list is the single authority for apply order —
`sql/kill_switch.sql` and `sql/schema.sql`'s own header comments point back here rather than restating
it." Neither half is true today. `sql/kill_switch.sql` contains no reference to `docs/runbook.md`
whatsoever and still restates the order at `:8-17`. `sql/schema.sql` does point back (`:37`) but *also*
still restates a five-file order at `:32-37` that omits `kill_switch.sql`. This is a new defect introduced
by the REV-063 fix, not a pre-existing one: the runbook now documents a consistency that was planned but
not executed, which is worse than documenting nothing, because it tells a future reader not to bother
checking the other two files. Closing REV-063's dev half also closes this; they should be fixed together.
Owner: **dev** (the two SQL headers), then **release** (only if the dev half is declined, in which case
`:70`'s claim must be softened to match reality).

**REV-072 — `[BLOAT]` — minor — the publish-prices block re-derives the session predicate the merged
watchlist branch already computed, doubling the number of places the session bounds must stay in sync.**
Location: `sql/phase5_monitoring.sql:274-275` vs `:182-188`.
Description: REV-047's dedup introduced `v_session_active`, set true at `:182-188` iff
`(et >= '10:15' and et <= '16:00')` or `(ist >= '10:00' and ist <= '15:30')`. The publish-prices block at
`:274-275` then spells out that identical disjunction inline instead of testing `v_session_active`. The
two predicates are exactly equivalent today, so this is not a correctness bug — it is the same duplication
REV-047 was filed to remove, surviving one block further down, and it means the four session-bound
literals now appear twice each in one function. That directly undercuts REV-048's constants table (and is
part of why REV-067's "three copies" count drifted). Suggested fix: replace `:274-275` with
`if v_session_active then`. Small, but it is the difference between the dedup being done and half-done.
Owner: **tech-lead**.

---

### Open items after Pass 13

**Blockers: 0.**

**Majors: 3 IDs / 2 pieces of work** — REV-064 and REV-039 (both **release**, and both closed by the same
§2.2/§7/§8 edit — one piece of work carrying two IDs), and REV-043 (**dev**).

**Minors: 11** — REV-063 residual (dev), REV-065 (tech-lead), REV-066 (tech-lead + pm), REV-067
(tech-lead), REV-068 (pm), REV-070 (qa + release), REV-071 (dev), REV-072 (tech-lead), plus carryovers
REV-048 (qa), REV-049(b) (release), REV-052 (tech-lead + pm).

**Routing:** REV-064 + REV-039 → **release** (one §2.2/§7/§8 edit). REV-063 residual + REV-071 → **dev**
(one edit to the two SQL headers). REV-065, 066, 067, 072, 052 → **tech-lead**. REV-068 → **pm**.
REV-043 → **dev**. REV-048, 070 → **qa**. REV-049(b) → **release**, before INC-5 starts.

---

### What is in good shape (calibration)

- **The REV-062 fix is a genuine reconciliation, not a merge that dropped a side.** The condition I
  expected to fail — the resume-baseline surviving the ET/IST collapse exactly once — is the one the fix
  handled most carefully. All four staleness branches, all three degraded branches, and the pause check
  are simultaneously present in one body for the first time.
- **The superseded files were handled the right way.** Reducing them to explicit non-applyable markers
  with their history written down is strictly better than deleting them (which would have left the runbook
  and design references dangling) or emptying them silently (which was the failure mode I called out).
- **The fix propagated past the files it was asked to touch** — `docs/design/non-functional-ops.md:89-96`
  was updated to mark both files superseded, which REV-062 did not require. The one place it over-reached
  is `runbook.md:70`, where it claimed a cross-reference cleanup it had not performed (REV-071). That is
  the correct thing for me to catch and the reason this pass read the referenced files rather than the
  referencing one.
- **REV-062 was a scope failure, not a rigour failure, and it stayed one.** qa's INC-3 static review was
  sound within its three-file scope; the fix did not disturb any of the INC-3 logic qa validated.

---

### Pass 13 summary

**New findings by tag:** `[DESIGN-GAP]` 1 minor (REV-071); `[BLOAT]` 1 minor (REV-072). No new blockers,
no new majors. Pass 2 (code → requirements) clean — the reconciled function does nothing outside
FR24–FR26/NFR2 and REV-042/REV-047's already-approved scope; no `[SCOPE-CREEP]`. Pass 5 clean — no
committed secrets in the changed files, `check_pipeline_health` remains `security definer` with
`set search_path = ''`, fully schema-qualified, and `revoke execute ... from public, anon, authenticated`
(`:303`) is intact through the rewrite.

**Resolved this pass:** REV-062 (blocker), REV-069 (minor), REV-042 and REV-047 (promoted from
resolved-with-dependency to fully resolved). REV-063 partially resolved — runbook half closed, dev half
carried as a minor.

**Open blocker count: 0.**

### Verdict — INC-3

**CLEAR.** This is the reviewer's INC-3 pass signal Arjun is waiting on. REV-062 was the only thing
standing between INC-3 and clearance at Pass 12, and it is genuinely closed on independent inspection of
the actual file contents. INC-3's traceability holds: FR24 → `sql/scheduler_pgcron.sql:52-58` (pause guard
before the Vault PAT lookup and the `net.http_post`), FR25 → `sql/phase5_monitoring.sql:163-165`, FR26 →
`sql/kill_switch.sql:47-53` and `:94-108`, NFR2 extended → the four `GREATEST` sites above. Passes 2–5 are
clean across the increment. No open finding is INC-3-scoped: the three remaining majors are the runbook's
model Variables and the `get_price_only` efficiency work, both pre-dating and independent of INC-3.

**What CLEAR does and does not mean here.** It means the increment is correct as committed and nothing in
the repo now reverts it. It does **not** mean INC-3 has been executed — AC1–AC5 remain unrun against a
live project per Arjun's explicit deferral, tracked as REV-070. Reviewer clearance and qa's PASS are both
static-basis; the live verification is owed at apply time, and Phase-4 closure should not treat
FR24/FR25/FR26 as verified until it happens. That caveat is a scheduling obligation, not a blocker, and it
does not gate the merge-to-main decision, which is Arjun's to make.

### Verdict — Pass 13

**CLEAR — zero blockers.** Per `CLAUDE.md`'s git workflow, INC-3 has now passed both qa and reviewer with
zero blockers, so the merge-to-main gate is satisfied from the review side. The remaining 3 majors and 9
minors are all schedulable, none halts the pipeline, and none needs to land before INC-4 starts — though
REV-064 + REV-063-residual + REV-071 are three small edits across two owners (release, dev) that would
close cleanly as one batched pass and are worth doing before the next increment adds more runbook surface.
Nothing from this change request is applied to the live project, so live behaviour is unchanged by
everything above.
