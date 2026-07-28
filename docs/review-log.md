# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–11 (2026-07-12 through 2026-07-28) — archived

Passes 1–11 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene
rule. Passes 1–9 were archived across Passes 6, 9 and 10 as their chains closed; Passes 10 and 11 were
archived 2026-07-28 at this Pass 12's close, with Pass 11's per-finding closing disposition (REV-033
through REV-061) appended there. Nothing from Passes 1–10 remains open. Pass 11's five still-open items
are carried forward in full below and are **not** in the archive as open work. Agents never read
`docs/archive/` per `CLAUDE.md`.

---

## Pass 12 — 2026-07-28 (combined: Pass-11 closing verification + INC-3 diff-scoped clearance)

**Scope.** Diff-scoped to the 42 files changed since Pass 10's clearance (`d8e3988..HEAD`), covering two
jobs at once:

1. **Part 1 — independent re-verification of REV-033 through REV-061** (Pass 11's 29 findings) against
   current file content. Same standard Pass 10 used to close the REV-023–032 chain: read the actual
   current state of every cited location; a commit message or an agent's self-report is not evidence.
2. **Part 2 — INC-3 (kill-switch, FR24/FR25/FR26/NFR2) diff-scoped clearance.** Design:
   `docs/design/increment-plan.md` "### INC-3 — Kill-switch" (6 ACs) and
   `docs/design/operational-controls.md` §13. Files under audit: new `sql/kill_switch.sql`, edits to
   `sql/scheduler_pgcron.sql` and `sql/phase5_monitoring.sql`. qa's own pass:
   `docs/test-report.md` (PASS conditional, BUG-002 filed and fixed).

**Method caveat (standing, unchanged since Pass 2, and the same constraint qa worked under):** no
shell/execute tool and no live Supabase access this session. `pytest -q` was not run by me; no
`list_tables`/`pg_class` introspection was possible. Every finding is derived from direct file reads,
cited by `file:line`. Arjun has explicitly deferred applying any SQL from this change request to the live
project, so INC-3's AC1–AC5 are unverifiable by anyone — reviewer included — until apply time. That
deferral is respected, not worked around.

---

### 1. Part 1 — REV-033 through REV-061: verification results

**22 of 29 confirmed fully RESOLVED. 2 resolved-with-dependency. 5 still open.** Per-finding disposition
is recorded in `docs/archive/review-log-archive.md` alongside the archived Pass 11 entry. The two the
task singled out for extra scrutiny:

- **REV-033 (blocker, `[SECURITY]`) — RESOLVED 2026-07-28, verified by direct read of all five tables.**
  - `kill_switch_state`: `alter table public.kill_switch_state enable row level security;`
    (`sql/kill_switch.sql:33`, mirrored at `docs/design/operational-controls.md:65`), zero policies.
  - `kill_switch_audit`: `enable row level security` (`:54`) **and** `force row level security` (`:55`)
    **and** `revoke insert, update, delete on public.kill_switch_audit from public, anon, authenticated;`
    (`:56`) — all three of REV-033's asks present, with the BYPASSRLS interaction and its
    verify-at-apply-time caveat written into the file (`:57-82`).
  - `admin_allowlist`: `alter table public.admin_allowlist enable row level security;`
    (`docs/design/admin-portal.md:54`), zero policies, stated explicitly.
  - `tunables`: `alter table public.tunables enable row level security;`
    (`docs/design/admin-portal-tunables.md:53`).
  - `monitor_alerts`: new `sql/enable_monitor_alerts_rls.sql:24`, with its apply-order position and
    idempotency documented.
  - **Zero anon policies exist anywhere on the new tables.** I re-derived this rather than trusting the
    comments: a repo-wide grep of `sql/` and `docs/design/` for `create policy` returns exactly five
    live policies — `anon_read_watchlist` and `anon_read_call_log` (`sql/schema.sql:59,112`, both
    pre-existing production behaviour backing the public dashboard/detail page, correctly captured by
    REV-035's extraction, not new), and `admin_write_watchlist` / `admin_write_holdings` /
    `admin_write_tunables` / `admin_read_kill_switch` (all `to authenticated` **and** gated by
    `using (public.is_admin())`). No new table grants `anon` anything.

- **REV-037 (major, `[DESIGN-GAP]`) — RESOLVED 2026-07-28 at all four cited locations; one residual
  logged separately as REV-068.** All four originally-flagged statements now read two-tier + fail-loud:
  `docs/design/non-functional-ops.md:59-60`, `:112-113` (the one that previously specified the *opposite*
  of the decided behaviour — it now states the fail-loud `SystemExit` posture and defers the mechanism to
  `tunables-fallback.md` rather than restating it), `:178-179` ("**no third, hardcoded-literal tier**"),
  and `docs/design/admin-portal.md:123-124`. I then swept the whole repo for `3-tier|three-tier|third
  tier|third-tier|hardcoded literal|tier 3` and checked **every** live hit by reading it in context:
  each surviving occurrence is a *negation* of the third tier (`tunables-fallback.md:76,84,87,93`
  explaining why it was removed; `tunables-workflow-writeback.md:165` "not the permanent third tier";
  `admin-portal.md:128` "to a stale '3-tier' description once already, REV-037";
  `increment-plan.md:30,149-150`; `requirements.md:387` "not a fixed hardcoded literal"), never an
  assertion of it. One near-miss checked and cleared: `non-functional-ops.md:176` says the table is a
  "**third tunables surface**" — that is surfaces (config.py env / workflow `vars` / Supabase table),
  not fallback tiers, and is correct. Zero surviving stale third-tier references in design.
  `docs/requirements.md` is the one document the correction never reached at all — REV-068.

**Module-split guideline — RESOLVED.** Every file under `docs/design/` is now comfortably under the ~400
line guidance: `increment-plan.md` 279 (was flagged at 450), `tunables-fallback.md` 295,
`operational-controls.md` 365, `components.md` 255, `admin-portal.md` 235, `design.md` 190,
`non-functional-ops.md` 189, `tunables-workflow-writeback.md` 178, `data-and-flow.md` 119,
`admin-portal-tunables.md` 120, `foundations.md` 87, `frontend.md` 51. Nothing over. No finding logged.
(`docs/runbook.md` 429 and `docs/requirements.md` 414 are over 400 but the CLAUDE.md guidance names
`design.md` specifically, and both are single-owner reference documents with no module structure to
split into — not flagged.)

---

### 2. Part 2 — INC-3 diff-scoped audit

**Traceability, requirements → code (pass 1).** FR24 → `operational-controls.md` §13.1/§13.2 → the pause
guard at `sql/scheduler_pgcron.sql:52-58`, placed correctly *before* the Vault PAT lookup and the
`net.http_post` call, so no HTTP request is constructed while paused. I independently re-derived qa's
five-dispatch-path claim rather than accepting it: `dispatch_watchlist_if_open()`
(`phase5_monitoring.sql:288-308`), `dispatch_watchlist_nse_if_open()` (`scheduler_pgcron.sql:135-154`),
`discovery-dispatch` (`:113-117`), `discovery-dispatch-nse` (`:166-167`) and `publish-prices`
(`:171-172`) all reach GitHub only via `dispatch_github_workflow`, and the only other `net.http_post`
call site in the repo is `send_ntfy` (`phase5_monitoring.sql:40`), which is not a dispatch path. qa's
claim holds. FR25 → §13.4 → `phase5_monitoring.sql:136-142`, early `return` before any
`_raise_monitor`/`_clear_monitor`, and `send_ntfy` is only ever reached from inside those two, so zero
alerts while paused is structural, not incidental. FR26 → §13.2/§13.3 → `sql/kill_switch.sql:47-53`
(audit table) and `:94-108` (`set_kill_switch`, exactly one update + one insert per call). NFR2
(extended) → §13.4 → `GREATEST(..., v_resume_baseline)` at `phase5_monitoring.sql:155, 183, 209, 231,
255` — all four staleness checks plus the second watchlist-session branch, decision-only, with alert
message text still interpolating the raw un-adjusted timestamp exactly as §13.4 requires.

**BUG-002 — confirmed genuinely fixed.** `sql/kill_switch.sql:8-13` now reads "Apply order: this file
FIRST, before sql/scheduler_pgcron.sql and sql/phase5_monitoring.sql", which agrees with
`sql/scheduler_pgcron.sql:16-18`, `sql/phase5_monitoring.sql:15-17` and `docs/handoff.md:43-44`. All
four sources now state the same order. Read directly, not taken from the fix report.

**Traceability, code → requirements (pass 2) — clean.** Nothing in INC-3's SQL does anything outside
FR24–FR26/NFR2. `p_source` supports FR26's "actor/source"; the INC-7 forward-reference comments describe
future work without implementing it. No `[SCOPE-CREEP]`.

**Hardcoding (pass 3) — clean for this increment.** `ruff.toml` now exists so `audit.yml`'s lint gate is
live (REV-049a). INC-3 introduces no tunable literals: the `70 minutes` threshold and session bounds are
pre-existing and already tracked by REV-048's linked table.

**Leanness (pass 4) — clean for this increment.** The comment volume in `sql/kill_switch.sql` is high
(~50 of 129 lines) but every block is load-bearing rationale — the BYPASSRLS interaction, the
verify-at-apply-time instruction, the INC-7 forward contract. Not narration, not dead code, no
commented-out SQL. Not flagged.

**Security (pass 5) — clean for this increment.** No committed secret anywhere in the changed file set
(re-swept independently). `set_kill_switch` is `SECURITY DEFINER` with `set search_path = ''`, fully
qualifies every reference, and revokes `execute` from `public, anon, authenticated`
(`sql/kill_switch.sql:110`) — consistent with every other definer function in the codebase. One
behaviour worth recording, not a defect: `select paused into v_paused ... where id = true` leaves
`v_paused` NULL if the row is absent, so `dispatch_github_workflow` **fails open** (dispatches) when
`kill_switch_state` is missing. That matches the design as written and is the safer default for a
trading pipeline; noted here so it is a recorded decision rather than an accident.

**What qa's static-only review missed — see REV-062 below.** qa scoped its review to the three files the
increment touched and did not consider that two *other* committed migrations redefine the same function.
That is the one real defect this pass found.

---

### BLOCKER

**REV-062 — `[CODE-GAP]` / `[DESIGN-GAP]` — blocker — `check_pipeline_health()` now has three mutually
exclusive definitions committed to the repo, and no apply order produces a correct one; the runbook's own
instruction silently reverts FR25 and NFR2.**

Location: `sql/phase5_monitoring.sql:104-267`; `sql/fix_missing_degraded_checks.sql:39-…`;
`sql/dedup_watchlist_health_check.sql:35-166`; `docs/runbook.md:81`.

Description: three files each contain a full `create or replace function public.check_pipeline_health`.
Each is missing what the others have:

- `sql/phase5_monitoring.sql` (INC-3's edit) **has** the kill-switch pause check (`:136-142`) and the
  resume-baseline `GREATEST` on all four staleness comparisons, and **lacks** REV-042's degraded branches
  (`disc_status` is still selected at `:206` and never read — the exact dead read REV-042 was filed
  about) and REV-047's dedup.
- `sql/dedup_watchlist_health_check.sql` **has** REV-042's three degraded branches (`:106, :129, :154`)
  and REV-047's single parameterised watchlist branch, and **lacks** the kill switch entirely: no
  `v_paused` declaration, no `select paused ... from public.kill_switch_state`, no
  `if v_paused then return`, and all four staleness checks use the raw `wl_last`/`disc_last`/
  `disc_in_last`/`pp_last` with **no** `GREATEST(..., v_resume_baseline)` (`:73, :100, :123, :148`).
  Confirmed by reading the file in full and by grepping it for `v_paused|resume_baseline|kill_switch` —
  zero matches.
- `sql/fix_missing_degraded_checks.sql` — same omission; the same grep returns zero matches there too.

The sharpest evidence that this was never reconciled is in the dedup file's own header
(`:9-12`), which cites *INC-3's `GREATEST(last_run_at, resume_baseline)` change* as the motivating
example of why the duplication is dangerous — and then ships a function body that does not contain it.
Its header also claims it is "a complete, correct final state, not a partial diff that would regress"
(`:21-28`); that claim is true against `fix_missing_degraded_checks.sql` and false against
`phase5_monitoring.sql`.

Impact, and why it is a blocker rather than a major:
- `docs/runbook.md:81` actively instructs release to "apply **`dedup_watchlist_health_check.sql` alone**
  when release schedules this." Following that instruction after INC-3's SQL is applied **silently
  reverts FR25** (the monitor resumes firing stale/degraded alerts during a deliberate pause, which is
  precisely the false-page FR25 exists to prevent) **and NFR2's resume-baseline fix** (which
  `operational-controls.md:179` calls "load-bearing, not optional"). Nothing errors; the pause simply
  stops being respected by the monitor half of the kill switch, while the dispatch half keeps working —
  the hardest possible failure to notice.
- The reverse order loses REV-042's degraded alerting and REV-047's dedup instead. **There is no apply
  order that yields a correct final function.** The repo cannot currently produce a correct
  `check_pipeline_health` at all.
- It is latent rather than live only because Arjun has deferred all SQL application. That deferral is
  what keeps it out of production today; it is not a mitigation, since the whole point of these files is
  to be applied.

Suggested fix: produce **one** authoritative `check_pipeline_health` containing all four changes (INC-3's
pause check + resume baseline, REV-042's three degraded branches, REV-047's dedup), delete or clearly
mark the superseded files as historical-only, and correct `docs/runbook.md:81` to name the single file to
apply. Note the merge is not mechanical: REV-047's dedup collapses the two watchlist branches that INC-3
edited, so the `GREATEST(wl_last, v_resume_baseline)` has to land inside the merged branch exactly once.
Owner: **tech-lead** (reconcile the three bodies into one), then **release** (runbook §2.3 and the
line-81 note). qa should re-test the merged function's four staleness paths against both AC3 and REV-042.

---

### MAJOR

**REV-063 — `[DESIGN-GAP]` — major — the runbook's fresh-deploy apply order never mentions
`sql/kill_switch.sql`, and apply-order authority is now split across three files that don't reference
each other.**
Location: `docs/runbook.md:70-81`; `sql/kill_switch.sql:8-13`; `sql/schema.sql:32-37`.
Description: `docs/runbook.md` §2.3 is the documented authority for apply order ("Apply SQL migrations in
this exact order"), and it lists five files — `scheduler_pgcron.sql`, `schema.sql`,
`phase5_monitoring.sql`, `dashboard_latest_call_view.sql`, `enable_monitor_alerts_rls.sql`. A repo-wide
grep of `docs/runbook.md` for `kill_switch` returns **zero hits**: INC-3's SQL appears nowhere in the
deploy procedure, not even in the line-81 "not yet part of this apply order" note that does cover
`fix_missing_degraded_checks.sql` and `dedup_watchlist_health_check.sql`. Meanwhile
`sql/kill_switch.sql:8` (as corrected by BUG-002) states it must be applied **first, before
`scheduler_pgcron.sql`** — which is step 1 of the runbook's order — and `sql/schema.sql:32-37` states a
third, independent version of the order that omits `kill_switch.sql` too. Three files each assert an
apply order; none cites the others; the one an operator is told to follow is missing a file that another
says must come first. This is the same defect class as BUG-002 (which qa caught and dev fixed at the
three-file level) reappearing one level up, at the runbook level.
Suggested fix: state the apply order **once**, in `docs/runbook.md` §2.3, including `sql/kill_switch.sql`
at its correct position and its not-yet-applied status; have `sql/kill_switch.sql` and `sql/schema.sql`
headers point at §2.3 instead of restating an order each (`CLAUDE.md`: "state anything once, reference by
ID elsewhere" — restating it in three places is what let them diverge).
Owner: **release** (runbook §2.3), then **dev** (the two SQL headers).

**REV-064 — `[HARDCODED]` — major — the REV-039 fix removed all model wiring from both workflow YAMLs but
the runbook still tells the operator to create six GitHub Variables that are now completely dead.**
Location: `docs/runbook.md:44-51` vs `.github/workflows/hourly-watchlist.yml:50-59` and
`.github/workflows/daily-discovery.yml:47-55`.
Description: the REV-038/REV-039 fix (correct, and confirmed resolved on the code side) deleted every
model `env:` line from both workflows, making `scripts/config.py` the single source of truth. But
`docs/runbook.md` §2.2 still instructs the operator to create `GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`,
`NSE_GEMINI_MODEL`, `NSE_GEMINI_MODEL_BACKUP`, `DISCOVERY_GEMINI_MODEL` and `DISCOVERY_GEMINI_MODEL_BACKUP`
as "Optional, User-Tunable" repo Variables with documented defaults. None of the six is read by anything
any more. This is REV-039's own stated harm — "a control surface that still looks live in the GitHub UI
and in `docs/runbook.md:44-51`, where an operator who edits the Variable will see no effect and get no
warning" — and it is now strictly worse than when REV-039 was filed: previously four of the six were at
least wired. REV-039's suggested fix explicitly included "update `runbook.md` §2.2"; the code half landed
and the doc half did not. (The three rows immediately below, `GEMINI_MAX_RETRIES` /
`GEMINI_RETRY_BASE_MS` / `GEMINI_TIMEOUT_MS`, **are** still wired in both workflows and are correct — do
not remove those.)
Suggested fix: delete the six model rows from `docs/runbook.md` §2.2 and replace them with a one-line
pointer to `scripts/config.py` as the source of truth (and to the FR30 tunables table once INC-6 ships).
Owner: **release**.

**REV-039 (carried from Pass 11) — `[HARDCODED]` — major — partially resolved.** Code side RESOLVED
(verified: zero model literals remain in either workflow YAML; `scripts/config.py:26-27,109-110,123-124`
is the sole home, with the reason recorded inline at `hourly-watchlist.yml:50-59`). Doc side OPEN — see
REV-064. Owner: **release**.

**REV-043 (carried from Pass 11) — `[BLOAT]` — major (efficiency) — design done, code not written.**
tech-lead made the design call (`docs/design/components.md:86-95`: add
`ingest.get_price_only(ticker) -> dict`, `period='5d'` history + `fast_info`, no `info`, no news) and
recorded the file-level impact in `non-functional-ops.md:65-66,80-81`. But `scripts/ingest.py` contains
no `get_price_only` (grepped) and `scripts/publish_prices.py:45` still calls
`ingest.get_market_data(ticker)`. The ~1000 avoidable Yahoo requests/day are still being made. Owner:
**dev** (implement per `components.md` §4.2).

---

### MINOR

**REV-065 — `[DESIGN-GAP]` — minor — `non-functional-ops.md` §9 now describes a workflow-Variable
convention the REV-038/039 fix deliberately abandoned, and documents wiring that no longer exists.**
Location: `docs/design/non-functional-ops.md:155-163` and `:186-189`. (a) `:159-161` states "This repo's
established convention for workflow knobs an operator may need to change **without a commit** is a repo
**Variable with a literal fallback** — `${{ vars.X || '<default>' }}` — used throughout
`hourly-watchlist.yml` (`GEMINI_MODEL`, `GEMINI_MAX_RETRIES`, …)". Neither half is true today: the
`GEMINI_MODEL` wiring was deleted outright, and the surviving `GEMINI_MAX_RETRIES`/`RETRY_BASE_MS`/
`TIMEOUT_MS` lines use plain `${{ vars.X }}` with **no** literal fallback, on purpose and with the
rationale written into the YAML (`hourly-watchlist.yml:60-66`). (b) `:186-189` says "The pre-existing
`${{ vars.GEMINI_MODEL || '...' }}` / `_BACKUP` Variable wiring **already in** `hourly-watchlist.yml`
becomes a harmless, unread vestige … safe to leave, not required to remove" — that wiring is already
gone, so the paragraph documents non-existent code and gives INC-6 a stale instruction. Owner:
**tech-lead**.

**REV-066 — `[HARDCODED]` — minor — `NTFY_BASE_URL` and `NTFY_TIMEOUT_SECONDS` exist in code but not in
the config audit baseline, against that baseline's own rule.** Location: `scripts/config.py:113-114` vs
`docs/design/non-functional-ops.md:127-146` and `docs/requirements.md` §10. REV-052's code half is
RESOLVED — `notify.py:98,100` now reads both from config, and the SQL-side duplicate at
`phase5_monitoring.sql:41` is inherent to the SQL layer, not a new defect. But REV-052 routed the
config-surface half to tech-lead and it did not land: a grep of the whole `docs/` tree for
`NTFY_BASE_URL|NTFY_TIMEOUT_SECONDS` returns **zero hits**. `non-functional-ops.md:146` states the rule
these two now violate: "**no tunable may live only in code**." Owner: **tech-lead** (§9 baseline),
**pm** (`requirements.md` §10 baseline).

**REV-067 — `[DESIGN-GAP]` — minor — every SQL citation in the new REV-048 constants table is wrong, in a
table whose entire purpose is making drift trackable.** Location: `docs/design/components.md:50-56`. The
table is a good addition and closes REV-048's design half, but: rows 1–2 cite
`scheduler_pgcron.sql:279` for `dispatch_watchlist_if_open()` — that file is 184 lines long and the
function is defined in `phase5_monitoring.sql:288-308` (wrong file *and* a nonexistent line); rows 3–4
cite `scheduler_pgcron.sql:132` where the actual bounds are at `:151`; rows 5–6 cite
`phase5_monitoring.sql:125` and `:153` where the actual guards are at `:151` and `:179`; row 7 cites
`:129,157,229` where the three `interval '70 minutes'` copies are at `:155,183,255`. The monitor
citations are all short by ~26 lines — the exact number INC-3 added to that file — so they were written
against the pre-INC-3 file and never re-checked. Owner: **tech-lead**.

**REV-068 — `[REQUIREMENTS-GAP]` — minor — the 2026-07-28 two-tier/fail-loud decision never reached
`docs/requirements.md` at all, and the cache path there is stale.** Location:
`docs/requirements.md:306` (Decision #27), `:307` (Decision #28), `:385-388` (§10 FR30 note).
(a) A grep of `docs/requirements.md` for `two-tier|fail loud|fail-loud|SystemExit` returns **zero hits**.
The decision that the pipeline now hard-exits when a curated tunable cannot be resolved from either tier
is a real behavioural change to FR30's fail-safe semantics, and it exists only in the design modules —
no Decision entry, no changelog row, no §10 update. Decision #27's own text still says `config.py`
"fetches them at run start with a **fallback to hardcoded Python defaults** if the fetch fails", the one
surviving assertion of the removed tier anywhere outside a negation; Decision #24 got an explicit
"SUPERSEDED" marker for a comparable reversal, #27's clause got none. (b) `:307` and `:386` both still
name `config/tunables_cache.json`, the path REV-046 moved to the repo root — `increment-plan.md:146-147`
and `non-functional-ops.md:178` correctly say repo-root. Owner: **pm**.

**REV-069 — `[DESIGN-GAP]` — minor — `docs/runbook.md` §5 says "the four migrations" and lists four,
where §2.3 lists five.** Location: `docs/runbook.md:346-347` vs `:70-77`. REV-035's fix correctly added
`sql/schema.sql` and `sql/enable_monitor_alerts_rls.sql` to §2.3 (which now says "These five migrations"
at `:77`), but §5's parallel statement — "The four migrations in `sql/` (`scheduler_pgcron.sql`,
`schema.sql`, `phase5_monitoring.sql`, `dashboard_latest_call_view.sql` — §2.3's apply order) define the
complete control-plane schema and logic. **No other DDL is needed**" — omits
`enable_monitor_alerts_rls.sql` and asserts completeness. Same "state it once" issue as REV-063; §5
should reference §2.3 rather than re-enumerate. Owner: **release**.

**REV-070 — `[TEST-GAP]` — minor — FR24, FR25 and FR26 have design coverage and implementation but zero
verification of any kind, and the record of that should not depend on this log.** Location:
`docs/test-report.md:25-74` (AC1–AC5 all "pending live verification"); `tests/` (no SQL-targeting file).
This is not a criticism of qa — the deferral is Arjun's explicit call, qa correctly refused to fake or
simulate the live checks, and its static review was genuine and independently re-derived correct by me
above. It is logged so the gap is a tracked item rather than a footnote: at Phase-4 closure, three FRs
and one NFR extension will otherwise be marked delivered on the strength of a code read alone. The
INC-3 ACs already specify exactly what to run; they simply have not been run. Owner: **qa** (execute
AC1–AC5 at apply time), **release** (schedule the apply window; AC2/AC3 need a live pg_cron project, so
a low-traffic window per `docs/handoff.md:70-72`).

**REV-048 (carried from Pass 11) — `[HARDCODED]` — minor — design half done, test half not.** The linked
constants table now exists (`components.md:48-57`, closing the design ask, though see REV-067 for its
citations). The drift test is explicitly deferred — `components.md:59` "Suggested (not built in this
pass, qa's to schedule)". Owner: **qa**.

**REV-049 (carried from Pass 11) — `[BLOAT]` — minor — (a) and (c) resolved, (b) still open.** (a)
`ruff.toml` now exists (`line-length = 100`, `target-version = "py312"`, `select = ["E","F","W"]`), so
`audit.yml:42-47`'s gate actually runs `ruff check .` instead of logging "No ruff config found" — the
lint half of this review process's tooling-first posture is live for the first time. (c) `audit.yml:37`
is pinned to `'3.12'`, matching all three production workflows. (b) OPEN: the ESLint/Node branches
(`:60-84`) are still dead config, and the detector at `:29-31` still looks for `package.json` at the
**repo root**, so `admin-portal/package.json` at INC-5 will still be skipped and the portal will ship
with no lint or test coverage in CI. Nothing in `increment-plan.md`'s INC-5 acceptance criteria covers
portal CI. Owner: **release** (decide the portal CI story before INC-5 starts, per REV-049's original
suggestion).

**REV-052 (carried from Pass 11) — `[HARDCODED]` — minor — code half resolved, config-baseline half
open.** See REV-066. `pages/detail.html`'s `.slice(0,5)` is gone (`:109-111` now notes headlines are
already capped at `config.HEADLINES_LIMIT` upstream; the remaining `.slice(0,8)` at `:172` is UUID
display truncation, not a tunable), and `scripts/textutil.py:1-7` no longer states 280/150. Owner:
**tech-lead**, **pm**.

---

### Carried forward — the five Pass-11 items still open

REV-039 (major, release — see REV-064), REV-043 (major, dev), REV-048 (minor, qa), REV-049(b) (minor,
release), REV-052 (minor, tech-lead + pm — see REV-066). Full current text is in the MAJOR/MINOR sections
above; none is carried as a bare ID.

REV-042 and REV-047 are recorded as **resolved-with-dependency**: the corrective SQL is written and, read
on its own terms, correct — but it is not deployable until REV-062 is closed, because applying it as the
runbook currently instructs would revert INC-3. They are not counted as open findings and not counted as
clean either.

---

### What is in good shape (calibration)

- **The REV-033 remediation is better than the minimum asked for.** Two independent layers on
  `kill_switch_audit` (REVOKE *and* enable+force RLS), with an explicit written statement of which one
  covers which threat, and an honest "dev must confirm at apply time whether `postgres` carries
  BYPASSRLS" instead of an assumption presented as fact. That is the right way to write a security fix
  that cannot be tested yet.
- **BUG-002's fix propagated to all four sources**, not just the one qa named. Checked directly.
- **qa's INC-3 static review holds up under independent re-derivation.** Every substantive claim I
  re-checked — the five dispatch paths, the pre-PAT-lookup guard placement, the `send_ntfy`-only-inside-
  the-helpers argument, the `GREATEST`-NULL degradation, decision-vs-display-text separation — is
  correct. Its one gap was scope (the two sibling migration files), not rigour.
- **`tests/test_run_orchestration.py` (REV-055) covers all five named gaps**, not a subset: `_sessions()`
  model selection, the `FORCE_RUN`-with-everything-closed branch, the both-sessions-open warning, the
  `partial`-vs-`ok` heartbeat rule (three cases including mid-run error), and discovery's
  quiet-day-vs-screener-failure distinction. 13 tests, each traceable to a specific past production
  defect.
- **`pages/common.js` (REV-053) resolved the harder half properly** — the currency map is now genuinely
  one shape (`CUR` by ISO code plus `MKT_CUR_CODE`, with `curSymByCode`/`curSymByMarket` accessors),
  not two representations moved into one file.
- **`sql/schema.sql` (REV-035) is honest about its own limits** — its header states plainly that it was
  not re-verified against the live project this session and that dev/release must confirm
  column-for-column before treating it as authoritative. That caveat is worth more than the file.

---

### Pass 12 summary

**New findings by tag:** `[CODE-GAP]`/`[DESIGN-GAP]` 1 blocker (REV-062); `[DESIGN-GAP]` 1 major
(REV-063) + 3 minor (REV-065, 067, 069); `[HARDCODED]` 1 major (REV-064) + 1 minor (REV-066);
`[REQUIREMENTS-GAP]` 1 minor (REV-068); `[TEST-GAP]` 1 minor (REV-070). No `[SCOPE-CREEP]`, no
`[SECURITY]`, no committed secrets — pass 2 and pass 5 both came back clean across the whole diff.

**Resolved this pass:** 22 of Pass 11's 29 findings independently confirmed RESOLVED by direct read
(REV-033, 034, 035, 036, 037, 038, 040, 041, 044, 045, 046, 050, 051, 053, 054, 055, 056, 057, 058, 059,
060, 061), plus BUG-002. 2 resolved-with-dependency (REV-042, 047). 5 remain open (REV-039, 043, 048,
049, 052). The module-split guideline concern is resolved — no design file exceeds ~400 lines.

**Open blocker count: 1** (REV-062).
**Open major count: 4** (REV-063, 064, 039, 043).
**Open minor count: 9** (REV-065, 066, 067, 068, 069, 070, 048, 049, 052).

### Verdict — INC-3

**NOT CLEAR — one blocker (REV-062).** INC-3's own three files are correct: the SQL traces cleanly to
FR24/FR25/FR26/NFR2, BUG-002 is genuinely fixed, qa's static review holds up under independent
re-derivation, and passes 2–5 are clean across the increment. But INC-3 delivered FR25 and NFR2's
resume-baseline into a repo that already contains two other committed, runbook-endorsed migrations which
redefine the same function without them. As the repo stands, applying the documented sequence undoes what
this increment was built to guarantee, and no alternative order is correct either. That is a defect in
INC-3's delivered state, not merely an adjacent one, so it blocks clearance. REV-062 is the only thing
standing between INC-3 and a clear verdict, and it is a single-file reconciliation.

### Verdict — Pass 12

**NOT CLEAR — one blocker.** Route REV-062 to tech-lead (reconcile the three `check_pipeline_health`
bodies into one) and then release (runbook §2.3 + line 81) before INC-4 starts, per `CLAUDE.md`'s
"blockers halt the pipeline" rule. REV-063 and REV-064 should be batched into the same release-side pass
since all three touch the runbook's SQL/Variables sections. The remaining majors and minors are
schedulable and none requires halting anything currently running — noting again that nothing from this
change request is applied to the live project, so the live system's behaviour is unchanged by everything
above.

**Routing:** REV-062 → **tech-lead**, then **release**, then **qa** (re-test). REV-063, 064, 069,
049(b) → **release**. REV-065, 066, 067, 052 → **tech-lead**. REV-068, 066 (§10 half) → **pm**. REV-043 →
**dev**. REV-048, 070 → **qa**.
