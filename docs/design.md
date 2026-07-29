# Stock Advisory Agent — Solution Design (as-built + draft increment plan)

**Owner:** tech-lead. **Status:** DESCRIPTIVE / as-built for FR1–FR23, NFR1–NFR4 (core, live). GATE 3 was
passed by the user for the 2026-07-26 change request's plan — kill-switch (FR24–FR26), admin portal
(FR27–FR32, NFR5–6), AI provider abstraction (FR33) — covered by `docs/design/increment-plan.md`
(INC-3–INC-7) and five new module files (`operational-controls.md`, `admin-portal.md`,
`admin-portal-tunables.md`, `tunables-fallback.md`, `tunables-workflow-writeback.md`). **INC-3
(kill-switch, FR24–FR26) and INC-4 (AI provider abstraction, FR33) are IMPLEMENTED** — dev built both, qa
tested both, and reviewer cleared both with zero blockers through Pass 14 (`docs/review-log.md`); see
`operational-controls.md` §13–§14, now **IMPLEMENTED**. **INC-5 (admin portal foundation: auth, hosting,
watchlist & holdings CRUD, FR27–FR29, NFR5–6) is also IMPLEMENTED** — dev-built, live-deployed, qa-tested
with a PASS verdict; reviewer Pass 17 verdict is CLEAR — REV-081/082/083 all RESOLVED, zero blockers — see
`docs/design/increment-plan.md`'s status note and `docs/review-log.md`. **INC-6 (admin portal: tunables
editor, FR30) is also IMPLEMENTED** — dev-built, qa-tested (PASS — BUG-003 found and fixed,
`docs/test-report.md`); reviewer Pass 19 verdict is CLEAR — REV-086/087/088/089 all RESOLVED, zero
blockers — see `docs/design/increment-plan.md`'s status note and `docs/review-log.md`. **INC-7 (admin
portal: track-record view & kill-switch UI, FR31–FR32) is also IMPLEMENTED** — dev-built, qa-tested (PASS
— zero bugs, `docs/test-report.md`); reviewer Pass 20 verdict is CLEAR — zero blockers, zero majors (two
non-blocking doc-hygiene minors, REV-093/094, closed by this update; `docs/review-log.md`). Design
revised several times
since: 2026-07-27 (Decision #27, supersedes #24 — FR30's tunables editor moves
from a GitHub-PAT proxy to a Supabase table); 2026-07-27 (Decision #28, refines #27 — the failed-fetch
fallback moves from a hardcoded literal to a repo-committed cache file, and *proposes*
`hourly-watchlist.yml` as sole cache writer, for Arjun to confirm or override); 2026-07-28 (tech-lead
correction, no new Decision # — the fallback chain narrowed to two tiers only, table then cache file; a
permanent third hardcoded-literal tier added during design elaboration is removed, and a simultaneous
double-failure of both tiers now fails loud via `SystemExit` instead of guessing); and 2026-07-28 again
(reviewer REV-040 + **Decision #29**, pm — REV-040 flagged Decision #28's write-ownership proposal as a
race/privilege trade-off to re-put to Arjun, who confirmed `hourly-watchlist.yml` stays sole writer *on
condition of* REV-040's two mitigations — a shared `concurrency` group with `publish-prices.yml` and a
bounded retry around the cache-commit `git push` — both now part of this design, see
`docs/design/tunables-workflow-writeback.md` §16.4). **INC-6 and INC-7 are both reviewer-CLEAR (Pass 19
and Pass 20 respectively, `docs/review-log.md`) — INC-7 was the last increment in the approved build
order, so all seven increments (INC-3–INC-7) are now IMPLEMENTED and reviewer-clear.** **No open design
questions remain** as of Decision #29 — see
`docs/design/increment-plan.md` and `docs/design/tunables-workflow-writeback.md` §16.4.
Split into per-module files under `docs/design/` (2026-07-25, REV-024) — **this file is a thin index;
read the module file(s) your increment actually touches, not the whole tree.**

**Provenance:** Originally produced during the 2026-07-12 multi-agent-template adoption pass by condensing
the existing, code-verified solution design `requirements_docs/SD.md` (v20, ~1400 lines) into this
template's format. It is **reverse documentation of a shipped system**, not forward design work. `SD.md`
and `requirements_docs/SD-history.md` remain in the repo as the historical/rationale record; where this
doc and `SD.md` disagree, the code wins and this doc is the one to fix.

**Requirement IDs** referenced throughout map to `docs/requirements.md` (FR1–FR23 / NFR1–NFR4, core and
live). FR24–FR31/NFR5 (US/CA shadow pilot + shared evaluation method) and FR32–FR39/NFR6 (NSE shadow
pilot) are **retired** — kept in `docs/requirements.md`'s changelog for historical traceability only, no
longer implemented or design-active. See "Retired: shadow-pilot tracks" below.

---

## Module map

| File | Covers | Sections |
|---|---|---|
| `docs/design.md` (this file) | Load-bearing decisions, retired-work pointer, requirement coverage map | §0, §15 |
| `docs/design/increment-plan.md` **(INC-3–INC-7 all IMPLEMENTED; INC-6 reviewer-CLEAR Pass 19, INC-7 reviewer-CLEAR Pass 20)** | The project plan: INC-3 through INC-7, design pointers, file lists, dev-self-verifiable acceptance criteria. Split out of `design.md` 2026-07-28. | n/a (project plan, not a numbered design section) |
| `docs/design/foundations.md` | Purpose, confirmed architecture choices, accepted risks, high-level architecture diagram | §1–§3 |
| `docs/design/components.md` | Scheduler, data ingestion, discovery prefilter, AI judgment layer, state/persistence, alerting, detail page, reliability monitor | §4 (4.1–4.8) |
| `docs/design/data-and-flow.md` | Data model (Supabase schema, `data_snapshot` jsonb contract), core single-rule change-detection flow | §5–§6 |
| `docs/design/non-functional-ops.md` | Cost/security/concurrency/delisting design, repo structure & module boundaries, configuration surface (tunables) | §7–§9 |
| `docs/design/frontend.md` | Detail page & dashboard rendering authority, browser-CORS constraint, known limitations | §10–§12 |
| `docs/design/operational-controls.md` **(IMPLEMENTED, INC-3/INC-4)** | Kill-switch (dispatch-layer enforcement, audit trail, monitor pause-awareness) and AI provider abstraction (interface, LiteLLM-vs-hand-rolled decision) | §13–§14 |
| `docs/design/admin-portal.md` **(INC-5 sections IMPLEMENTED, reviewer-CLEAR Pass 17; INC-7 sections IMPLEMENTED, reviewer-CLEAR Pass 20)** | Admin portal: hosting/auth, authorization model (RLS/allowlist), watchlist/holdings CRUD, track-record view, kill-switch UI, secrets inventory | §16 (16.1–16.3, 16.5–16.9) |
| `docs/design/admin-portal-tunables.md` **(IMPLEMENTED, INC-6 reviewer-CLEAR Pass 19)** | Tunables editor (FR30): Supabase `tunables` table schema, RLS (`select, update` only + key-registry CHECK, REV-044), seed data, portal UI. Split out of `admin-portal.md` 2026-07-27. | §16.4 |
| `docs/design/tunables-fallback.md` **(IMPLEMENTED, INC-6 reviewer-CLEAR Pass 19)** | Tunables editor (FR30) `scripts/config.py` half: Decision #28 cache-file fail-safe (`tunables_cache.json` at repo root, REV-046), two-tier fallback chain — table then cache, fails loud via `SystemExit` if both miss a key or a tier-1 value fails to cast (REV-036), explicit fetch timeout + offline test seam (REV-041), validated/merged cache write-back, `TUNABLES_DEGRADED` heartbeat signal (REV-045). Split out of `admin-portal-tunables.md` 2026-07-28. | §16.4 |
| `docs/design/tunables-workflow-writeback.md` **(IMPLEMENTED, INC-6 reviewer-CLEAR Pass 19)** | Tunables editor (FR30) workflow-YAML half: which workflow commits `tunables_cache.json` back to git, and REV-040/Decision #29's race + privilege mitigations (shared `concurrency` group with `publish-prices.yml`, job-scoped `permissions`, bounded push retry), `ALERTS_ENABLED` AND-gate. Split out of `tunables-fallback.md` 2026-07-28 — INC-6 reads all three tunables files, not the rest of §16. | §16.4 |

Section numbers are unchanged from the pre-split monolithic file — only the physical file location moved.
Read §0 (below) and this index regardless of which module your increment touches; §0 is the "why it is
this way" context every change should be checked against.

---

## 0. Load-bearing decisions (read before changing anything)

These are the "why it is this way" calls that are cheap to reverse without realizing the cost. Full
provenance is in `requirements_docs/SD-history.md`; the load-bearing short version, preserved verbatim in
intent from `SD.md §0`:

1. **Single-rule alerting (FR7, FR8; `data-and-flow.md` §6).** Any verdict change → immediate alert; no
   change → silence. No cooldown, no debounce, no 7-day reminder (the old FR7 reminder is retired). The
   removed cooldown/reminder added state that wasn't earning its keep on a single-user push tool. Accepted
   cost: alert bursts on a choppy day. **Don't re-add a cooldown/debounce without a real, observed volume
   problem.**
2. **Signal on crossings, not standing states (FR8; `data-and-flow.md` §6).** A standing Buy/Sell that
   never changes is silent by design — there is no bootstrap re-announce. A logged change is one threshold
   crossing, not proof of a durable signal; read the track record that way.
3. **Gemini fallbacks were never quota/RPD (`components.md` §4.4).** The real cause was a client-side
   timeout firing on slow-but-valid (already token-billed) responses, plus occasional 503s — fixed with
   `GEMINI_TIMEOUT_MS=180s`. The real reason is logged per call in `data_snapshot.fallback_from`;
   **don't call fallbacks "rate-limiting."**
4. **Supabase pg_cron is the clock, not GitHub cron (`components.md` §4.1).** GitHub's shared scheduler
   silently dropped most ticks. The **runtime market gate, not the schedule, is the authority** on whether
   work happens — the schedule fires loosely and the market gate trims it. Never trust the schedule to
   mean "market open." (NFR2.)
5. **Reliability is an active dead-man monitor (`components.md` §4.8, NFR2).** It must surface a run that
   *never triggers*, not only one that runs and fails. Known limit: it lives in the same pg_cron it
   watches (single point of failure, `foundations.md` §2 item 6); an out-of-band ping is the unbuilt
   mitigation.
6. **One batched AI call per run, not per ticker (`components.md` §4.4).** Gemini runs on **Google's paid
   tier** system-wide (production watchlist, NSE watchlist, discovery); there is no free-tier daily
   request cap. Batching is still load-bearing for cost: one batched call per run per market group is what
   keeps paid-tier spend inside NFR1's unchanged $0–15/mo cap (cost is held by low call volume, not a free
   quota). `data_snapshot.tokens` is a **per-batch total replicated on every row** — dedup per run, never
   sum per row. (Prior to 2026-07-16 this also covered the now-retired shadow tracks' calls — see
   "Retired: shadow-pilot tracks" below.)
7. **Discovery uses Yahoo's live screener, not a maintained universe (`components.md` §4.3).** The
   `candidate_universe` table was vestigial and has been dropped; there is no seed/quarterly-refresh
   ownership burden. Don't reintroduce one.
8. **AI fails safe to Hold (`components.md` §4.4, FR9).** A parse/API failure logs a fail-safe Hold, and
   the change detector's cold-start/no-change guard stops it from being read as a real change — so a bug
   can only ever *miss* a signal, never *fabricate* one. Keep that guard.
9. **Market-close dispatch boundary is close + 5 min (SQL) / close + `RUNTIME_CLOSE_GRACE_MIN` (Python),
   not exact close (`components.md` §4.1).** The two layers carry different close bounds **on purpose** —
   the SQL gate (16:05 ET / 15:35 IST) absorbs pg_cron sub-second jitter; the Python gate (16:00 +
   `RUNTIME_CLOSE_GRACE_MIN`, default 10 min) absorbs dispatch-to-execution latency (runner queue +
   checkout + pip install). Both bugs were confirmed and fixed. **Don't tighten either bound to the exact
   close, and don't "simplify" the two numbers into one** — they protect against different failure modes.
   Neither admits the following post-close `*/30` slot.
10. **RETIRED (2026-07-16).** Formerly: "US/CA shadow pilot is triple-isolated and fail-open by policy."
    Removed along with the shadow track — see "Retired: shadow-pilot tracks" below for what was removed
    and why. Kept as a numbered placeholder only so older cross-references elsewhere don't dangle.
11. **RETIRED (2026-07-16).** Formerly: "Two mutually-isolated shadow tracks." Same disposition as #10 —
    see "Retired: shadow-pilot tracks" below.

---

## Retired: shadow-pilot tracks (2026-07-16)

Two experimental "shadow verdict" tracks (US/CA and NSE) plus a shared wallet-sim evaluation harness were
built (formerly INC-1/INC-2, shipped 2026-07-13/14/15), covering FR24–FR31/NFR5 (US/CA shadow + shared
eval method) and FR32–FR39/NFR6 (NSE shadow). On 2026-07-16 the user requested "End both US/TSX and NSE
experiment (shadow) and remove the codebase for it" — a clean-deletion change request, nothing preserved
for revival.

**Removal executed and independently verified** (dev's `docs/handoff.md`, qa's `docs/test-report.md`,
both 2026-07-16; reviewer Pass 6/7 re-confirmed no regression):
- **Code:** `scripts/shadow.py`, `run_shadow.py`, `run_shadow_nse.py`, `wallet_sim.py`, `eval_shadow.py`,
  both shadow SQL migrations, and the two shadow steps in `hourly-watchlist.yml` deleted outright.
- **Config:** `SHADOW_*` and `EVAL_WINDOW_DAYS` tunables removed from `scripts/config.py`; the
  `SHADOW_TIMEOUT_MINUTES` workflow Variable and its binding removed.
- **Database:** `call_log_shadow` / `call_log_shadow_nse` dropped from the **live** Supabase project via
  `sql/drop_shadow_tables_migration.sql`, confirmed via `list_tables`.
- **Tests:** shadow-specific test files/fixtures removed; full regression passed with 0 open bugs.

This note intentionally replaces what was previously ~157 lines across five sections (prompt spec,
orchestration, wallet-walk, isolation belts, storage schema, config, and a mechanical removal checklist)
— that work is finished and verified, not open design, so the blow-by-blow doesn't need to stay live.
**Full historical narrative is in git history** (this file, pre-2026-07-25) and in `docs/requirements.md`'s
own changelog / git history for the deleted FR text (the former Experimental Tracks section was deleted
outright from `docs/requirements.md`, not kept in a live numbered section). FR24–FR31/NFR5 and
FR32–FR39/NFR6 remain listed in `docs/requirements.md`'s changelog for traceability only; no live design
content backs them anymore.

---

## Increment plan — 2026-07-26 change request (GATE 3 approved; INC-3–INC-7 all IMPLEMENTED, reviewer-CLEAR through Pass 20)

**Moved to `docs/design/increment-plan.md`** (2026-07-28, doc hygiene — `design.md` exceeded the
~400-line module-split guidance once the Pass-11 review fixes and Decision #29/REV-040 landed). That file
has the full history (Decisions #27/#28/#29, REV-040's race/privilege mitigations) and the complete INC-3
through INC-7 plan: design pointers, file lists, and every dev-self-verifiable acceptance criterion,
including the REV-033/034/036/040/041/044/045/046 fixes layered on since the original 2026-07-26 CR.
**INC-3 (kill-switch) and INC-4 (AI provider abstraction) have shipped** — dev-implemented, qa-tested, and
reviewer-cleared with zero blockers through Pass 14 (`docs/review-log.md`). **INC-5 (admin portal
foundation: auth, hosting, watchlist & holdings CRUD) has also shipped** — dev-implemented, live-deployed,
qa-tested with a PASS verdict; reviewer Pass 17 verdict is CLEAR — REV-081/082/083 all RESOLVED, zero
blockers (`docs/review-log.md`). **INC-6 (admin portal: tunables editor, FR30) has also shipped** —
dev-implemented, qa-tested with a PASS verdict (BUG-003 found and fixed, `docs/test-report.md`); reviewer
Pass 19 verdict is CLEAR — REV-086/087/088/089 all RESOLVED, zero blockers (`docs/review-log.md`). **INC-7
(admin portal: track-record view & kill-switch UI, FR31/FR32) has also shipped** — dev-implemented,
qa-tested with a PASS verdict (zero bugs, `docs/test-report.md`); reviewer Pass 20 verdict is CLEAR — zero
blockers, zero majors (two non-blocking doc-hygiene minors, REV-093/094, closed by this update;
`docs/review-log.md`). **INC-7 was the last increment in the approved build order — all seven increments
(INC-3–INC-7) are now IMPLEMENTED and reviewer-clear. No open design questions remain for any of
INC-3–INC-7.**

---

## 15. Requirement coverage map

| Requirement | Where satisfied |
|---|---|
| FR1, FR3 | `components.md` §4.2, `data-and-flow.md` §5 `watchlist` |
| FR2, FR11 | `components.md` §4.4 (prompt, held block), §4.7 (detail position block); `data-and-flow.md` §5 `holdings`/`position` |
| FR4, FR5 | `components.md` §4.3 prefilter + signals + Buy-only push; `data-and-flow.md` §6 discovery flow |
| FR6 | `components.md` §4.1 scheduler; `data-and-flow.md` §6 30-min cadence |
| FR7, FR8 | §0 #1/#2 (this file); `data-and-flow.md` §6 single-rule change detector |
| FR9, FR10 | `components.md` §4.4 AI judgment (no fixed rules/style); §0 #8 fail-safe (this file) |
| FR12, FR13, FR14 | `components.md` §4.6 ntfy, §4.7 detail page |
| FR15, FR16 | `data-and-flow.md` §5 `call_log`, §6 (every check logged, incl. no-change/cold-start/skip) |
| FR17 | `components.md` §4.1 gates; `non-functional-ops.md` §7.5 skip-with-log |
| FR18 | `components.md` §4.6 per-market topic routing |
| FR19–FR22 | `frontend.md` §10 dashboard, §11 CORS/prices.json |
| FR23 | `components.md` §4.6 (notifications), §4.7 (detail page); `frontend.md` §10 (dashboard, client dual-tz); `data-and-flow.md` §5 UTC contract |
| NFR1 | `components.md` §4.4 batched call; `non-functional-ops.md` §7.1 cost |
| NFR2 | `components.md` §4.1 gate authority, §4.8 dead-man monitor |
| NFR3 (Disclaimer) | `components.md` §4.7 (Decision #17, "informational data is the accepted rationale") |
| NFR4 | `components.md` §4.1 cadence; `frontend.md` §11 freshness posture |
| NFR7 (Core security posture — added by pm 2026-07-28, REV-058) | `non-functional-ops.md` §7.2 (retitled "Security (NFR7)"); `data-and-flow.md` §5 (RLS on every table); `components.md` §4.7 (UUID-only detail-page URLs) |
| FR24–FR30 (2026-07-12 US/CA shadow pilot), NFR5 (old) | **RETIRED 2026-07-16** — formerly the US/CA shadow pilot; see "Retired: shadow-pilot tracks" above. FR text preserved only in git history (deleted outright from `docs/requirements.md`). Note: `docs/requirements.md`'s retirement pass freed these IDs, and the 2026-07-26 CR below reassigns FR24–FR33/NFR5–6 to entirely new, unrelated requirements (kill-switch/portal/AI-abstraction) — same numbers, no relation to the retired content; not a collision. |
| FR31 (old, shared wallet-sim harness) | **RETIRED 2026-07-16** — see "Retired: shadow-pilot tracks" above. FR text preserved only in git history. |
| FR32–FR39 (old), NFR6 (old) | **RETIRED 2026-07-16** — formerly the NSE shadow pilot; see "Retired: shadow-pilot tracks" above. FR text preserved only in git history. |
| FR24, FR25, FR26 (kill-switch, 2026-07-26 CR) | **IMPLEMENTED** — `operational-controls.md` §13. INC-3: dev-built, qa-tested, reviewer-cleared zero blockers through Pass 14. `sql/kill_switch.sql` is applied and live in the Supabase project. AC1 (objects exist), AC2 (pause suppresses dispatch before any `pg_net` call), AC4 (audit trail), and AC5 (RLS enabled on both tables) are independently verified via a dated live-evidence run (`docs/handoff.md`), corroborated by qa (`docs/test-report.md` §7) and reviewer (Pass 22/23, review-log.md REV-070). Only **AC3** (resume-baseline / no-false-alarm test under synthetic staleness) remains deferred — owner qa+release, to be run as a follow-up live pass. |
| FR27, FR28, FR29 (admin portal foundation, 2026-07-26 CR), NFR5, NFR6 | **IMPLEMENTED** — `admin-portal.md` §16.1–§16.3, §16.7–§16.8. INC-5: dev-built, live-deployed, qa-tested with a PASS verdict. Reviewer Pass 17 verdict is CLEAR — REV-081/082/083 all RESOLVED, zero blockers (`docs/review-log.md`); FR27–FR29/NFR5–6 are reviewer-clear. |
| FR30 (admin portal — tunables editor, 2026-07-26 CR) | **IMPLEMENTED** — `admin-portal-tunables.md`, `tunables-fallback.md`, `tunables-workflow-writeback.md` (§16.4). INC-6: dev-built, qa-tested (PASS — BUG-003 found and fixed), reviewer Pass 19 verdict CLEAR — REV-086/087/088/089 all RESOLVED, zero blockers (`docs/review-log.md`). |
| FR31, FR32 (admin portal — track-record view & kill-switch UI, 2026-07-26 CR) | **IMPLEMENTED** — `admin-portal.md` §16.5–§16.6. INC-7: dev-built, qa-tested (PASS — zero bugs, `docs/test-report.md`), reviewer Pass 20 verdict CLEAR — zero blockers, zero majors (`docs/review-log.md`). `sql/kill_switch_portal_grant.sql` is applied and live in the Supabase project (`admin_read_kill_switch` policy and the `is_admin()`-gated `set_kill_switch()` confirmed against production). What remains deferred is INC-7's own live round-trip — a portal-triggered toggle producing a `kill_switch_audit` row with `source='admin-portal'` and suppressing dispatch (AC2/AC3 per the Increment Plan's INC-7 criteria) — no dated live-evidence block for this specific path exists yet (`docs/test-report.md`'s Phase-4 pass). |
| FR33 (AI provider abstraction, 2026-07-26 CR) | **IMPLEMENTED** — `operational-controls.md` §14. INC-4: dev-built, qa-tested (5 of 6 AC), reviewer-cleared zero blockers through Pass 14. AC6 (live-Gemini smoke test) is deferred, not failed — no `GEMINI_API_KEY` was available in the build environment; needs a follow-up run with real credentials before AC6 is marked PASS (`docs/handoff.md`). |

**Coverage:** FR1–FR23, NFR1–NFR4, and NFR7 (core, live) are covered as-built across the module files
above — NFR7 added 2026-07-28 (pm, REV-058) to give the system's pre-existing security posture its own
ID, previously mis-cited as NFR3 (Disclaimer). **FR24–FR31/NFR5 and FR32–FR39/NFR6 (old numbering) are
retired (2026-07-16)** — the requirement IDs remain in `docs/requirements.md` for historical traceability
only. **FR24–FR26 and FR33 (current, 2026-07-26 CR) are IMPLEMENTED** — INC-3 and INC-4 shipped, per the
table above; the module files (`operational-controls.md` §13–§14) are as-built documentation for these,
not draft design. **FR27–FR29 and NFR5–NFR6 (current, 2026-07-26 CR) are also IMPLEMENTED** — INC-5
shipped (dev-built, live-deployed, qa-tested PASS; reviewer Pass 17 CLEAR — REV-081/082/083 all
RESOLVED), per the table above; `admin-portal.md` §16.1–§16.3, §16.7–§16.8 are as-built
documentation for these, not draft design. **FR30 (current, 2026-07-26 CR) is also IMPLEMENTED** — INC-6
shipped (dev-built, qa-tested PASS with BUG-003 found and fixed; reviewer Pass 19 CLEAR — REV-086/087/
088/089 all RESOLVED, zero blockers), per the table above; `admin-portal-tunables.md`,
`tunables-fallback.md`, and `tunables-workflow-writeback.md` are as-built documentation for this, not draft
design. **FR31–FR32 (current, 2026-07-26 CR) are also IMPLEMENTED** — INC-7 shipped (dev-built, qa-tested
PASS with zero bugs; reviewer Pass 20 CLEAR — zero blockers, zero majors), per the table above; the
Increment Plan (INC-7) and `admin-portal.md` §16.5–§16.6 are as-built documentation for this, not draft
design. **No open design questions remain for any of INC-3–INC-7.** All seven increments in the approved
build order (INC-3–INC-7) are now IMPLEMENTED and reviewer-clear.
