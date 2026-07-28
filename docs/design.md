# Stock Advisory Agent — Solution Design (as-built + draft increment plan)

**Owner:** tech-lead. **Status:** DESCRIPTIVE / as-built for FR1–FR23, NFR1–NFR4 (core, live). **DRAFT**
for the 2026-07-26 change request — kill-switch (FR24–FR26), admin portal (FR27–FR32, NFR5–6), AI
provider abstraction (FR33) — covered by the Increment Plan below (INC-3–INC-7) and three new module
files (`operational-controls.md`, `admin-portal.md`, `admin-portal-tunables.md`). Revised twice since:
2026-07-27 (Decision #27, supersedes #24 — FR30's tunables editor moves from a GitHub-PAT proxy to a
Supabase table), again 2026-07-27 (Decision #28, refines #27 — the failed-fetch fallback moves from a
hardcoded literal to a repo-committed cache file), and again 2026-07-28 (tech-lead correction, no new
Decision # — the fallback chain narrowed to two tiers only, table then cache file; a permanent third
hardcoded-literal tier added during design elaboration is removed, and a simultaneous double-failure of
both tiers now fails loud via `SystemExit` instead of guessing — see
`docs/design/admin-portal-tunables.md` §16.4). **Not yet implemented; no dev work starts before the
user approves this plan at GATE 3**, per CLAUDE.md's pipeline gates. **No open design questions remain**
as of the 2026-07-28 revision — see the increment plan below and `docs/design/admin-portal-tunables.md`
§16.4.
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
| `docs/design/foundations.md` | Purpose, confirmed architecture choices, accepted risks, high-level architecture diagram | §1–§3 |
| `docs/design/components.md` | Scheduler, data ingestion, discovery prefilter, AI judgment layer, state/persistence, alerting, detail page, reliability monitor | §4 (4.1–4.8) |
| `docs/design/data-and-flow.md` | Data model (Supabase schema, `data_snapshot` jsonb contract), core single-rule change-detection flow | §5–§6 |
| `docs/design/non-functional-ops.md` | Cost/security/concurrency/delisting design, repo structure & module boundaries, configuration surface (tunables) | §7–§9 |
| `docs/design/frontend.md` | Detail page & dashboard rendering authority, browser-CORS constraint, known limitations | §10–§12 |
| `docs/design/operational-controls.md` **(DRAFT)** | Kill-switch (dispatch-layer enforcement, audit trail, monitor pause-awareness) and AI provider abstraction (interface, LiteLLM-vs-hand-rolled decision) | §13–§14 |
| `docs/design/admin-portal.md` **(DRAFT)** | Admin portal: hosting/auth, authorization model (RLS/allowlist), watchlist/holdings CRUD, track-record view, kill-switch UI, secrets inventory | §16 (16.1–16.3, 16.5–16.9) |
| `docs/design/admin-portal-tunables.md` **(DRAFT)** | Tunables editor (FR30): Supabase `tunables` table schema, RLS (`select, update` only + key-registry CHECK, REV-044), seed data, portal UI. Split out of `admin-portal.md` 2026-07-27. | §16.4 |
| `docs/design/tunables-fallback.md` **(DRAFT)** | Tunables editor (FR30) runtime half: Decision #28 cache-file fail-safe (`tunables_cache.json` at repo root, REV-046), two-tier `config.py` fallback chain — table then cache, fails loud via `SystemExit` if both miss a key, explicit fetch timeout + offline test seam (REV-041), cache write-back validation (REV-036), `TUNABLES_DEGRADED` heartbeat signal (REV-045), `hourly-watchlist.yml` write-back, `ALERTS_ENABLED` AND-gate. Split out of `admin-portal-tunables.md` 2026-07-28 — INC-6 reads both tunables files, not the rest of §16. | §16.4 |

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

## Increment plan — 2026-07-26 change request (DRAFT, pending GATE 3)

Continues the project's increment numbering (INC-1/INC-2 were the retired shadow-pilot tracks, see
above — numbers are not reused). Sequencing follows the approved build order: kill-switch first
(self-contained, no dependency on the other two items), then the AI provider abstraction (a contained
refactor, independent of the portal), then the admin portal last, split into vertical slices so each is
independently shippable — the portal's kill-switch-UI slice (INC-7) intentionally comes last because it
depends on INC-3's backend flag/function already existing. **No increment starts before the previous one
passes QA (CLAUDE.md non-negotiable).**

**2026-07-27 revision (Decision #27, supersedes #24):** INC-6 (tunables editor) originally carried an
open design gap and a wider file footprint (a GitHub-PAT-holding Vercel proxy, plus edits to two
production workflow YAML files). Design-time investigation found Decision #24's premise false — only 2
of the 10 curated keys were actually wired from a GitHub Variable into the live workflows — and Arjun
approved moving the tunables source of truth to a new Supabase `tunables` table instead, reusing INC-5's
`is_admin()`/RLS mechanism directly rather than a separate GitHub-API code path. **INC-6 is now smaller
than originally planned, not larger: no GitHub API integration, no server-only secret, and the original
open design gap is resolved (not just deferred).** INC-6 now also has a **direct, literal dependency on
INC-5's `is_admin()`/`admin_allowlist` objects** (not just a shared pattern it happens to reuse) — the
`tunables` table's write policy calls the exact same function INC-5 creates for watchlist/holdings, so
INC-6 cannot be built or even meaningfully designed against a stub.

**2026-07-27 revision, second pass (Decision #28, refines #27):** the failed-Supabase-fetch fallback for
these 10 keys is no longer a fixed hardcoded Python literal — it's a repo-committed cache file
(`tunables_cache.json`) holding the last successfully-fetched value per key, reusing
`publish-prices.yml`'s already-proven commit-on-change mechanism. Arjun confirmed the write-ownership
shape tech-lead proposed: `hourly-watchlist.yml` (runs most frequently) is the **sole** writer;
`daily-discovery.yml` and `publish-prices.yml` remain read-only consumers, as they already are for the
Supabase table itself. **This does add one small workflow-YAML change** — `hourly-watchlist.yml` gains a
`permissions: contents: write` block (absent today) and one new commit-on-change step — but it's a
direct copy of a pattern already live and working in this exact repo, not new risk surface. See
`docs/design/tunables-fallback.md` (§16.4, split 2026-07-28) for the full mechanism.

### INC-3 — Kill-switch (FR24, FR25, FR26, NFR2)
**Design:** `docs/design/operational-controls.md` §13. **Files:** new `sql/kill_switch.sql`
(`kill_switch_state`, `kill_switch_audit`, `set_kill_switch()`); edits to `dispatch_github_workflow` and
`check_pipeline_health` in `sql/scheduler_pgcron.sql` / `sql/phase5_monitoring.sql`. **No Python changes**
— enforcement is entirely at the SQL/pg_cron dispatch layer, per FR24.
**Acceptance criteria (dev self-verifiable):**
1. `kill_switch_state` (singleton), `kill_switch_audit`, and `set_kill_switch(p_paused, p_source)` exist
   in the live Supabase project (confirm via `list_tables` / `list_functions`).
2. With `select set_kill_switch(true);`, manually invoking any of the 5 dispatch paths (both watchlist
   gates, both discovery calls, publish-prices) during their normal trigger window makes **no** `pg_net`
   HTTP request (no new `net._http_response` row) and writes **no** `run_heartbeat` row. With
   `select set_kill_switch(false);`, the same calls dispatch normally (a `pg_net` request row appears).
3. `select check_pipeline_health();` with `paused=true` and a synthetically stale heartbeat produces
   **no** `monitor_alerts` change and **no** `send_ntfy` call. After `set_kill_switch(false, ...)`,
   re-running immediately (heartbeat still stale purely from the pause duration) still produces **no**
   false "stale" alert — confirms the resume-baseline fix (§13.4).
4. Each `set_kill_switch` call inserts exactly one `kill_switch_audit` row with the correct `action`
   (`pause`/`resume`), a non-null `actor`, and `changed_at` — verified across ≥2 toggles.
5. Full existing test suite passes unmodified; no `scripts/*.py` file is touched by this increment (grep
   confirms zero diff outside `sql/`).

### INC-4 — AI provider abstraction (FR33)
**Design:** `docs/design/operational-controls.md` §14. **Files:** new `scripts/ai_provider.py`; refactor
`scripts/ai_judge.py`. No other file changes — `run_hourly.py`/`run_discovery.py` are untouched.
**Acceptance criteria:**
1. `scripts/ai_provider.py` defines `AIProvider` (ABC), `ProviderResult`, `TokenUsage`, `ErrorClass`,
   `ProviderError`, `BatchVerdictSchema`, `GeminiProvider`, `get_provider()`, per §14.2.
2. `grep -n "genai\|types\." scripts/ai_judge.py` returns **zero** matches — all Gemini-SDK-specific
   imports/calls now live only in `ai_provider.py`.
3. `judge_batch()`'s public signature/return contract is unchanged (`{ticker: {verdict, confidence,
   rationale, raw_model_response, parse_status, model_used, usage, fallback_from, retry_count}}`);
   `git diff` shows **zero** changes to `run_hourly.py` and `run_discovery.py`.
4. Full existing test suite passes with no assertion changes (import-path updates only) — proves
   behavior parity, not a rewrite. `config.GEMINI_TIMEOUT_MS` / `GEMINI_MAX_RETRIES` /
   `GEMINI_RETRY_BASE_MS` still govern retry/backoff identically (same log lines, same jitter formula).
5. `config.AI_PROVIDER` (default `"gemini"`) added to `scripts/config.py` and the config audit baseline
   (`non-functional-ops.md` §9); `get_provider("bogus")` raises `SystemExit` with a clear message.
6. A real smoke-test batched call against live Gemini still returns valid verdicts through the new path.

### INC-5 — Admin portal: auth, hosting, watchlist & holdings CRUD (FR27, FR28, FR29, NFR5, NFR6)
**Design:** `docs/design/admin-portal.md` §16.1–§16.3, §16.7–§16.8. **Files:** new `admin-portal/`
Next.js app (Vercel); new `sql/admin_portal_rls.sql` (`admin_allowlist`, `is_admin()`, watchlist/holdings
write policies).
**Note:** `admin_allowlist`/`is_admin()` built here are a **hard, literal dependency for INC-6** as of
Decision #27 — the tunables table's write policy calls this exact function, not just a shared pattern.
Keep the migration's function signature stable once INC-6 is built against it.
**Acceptance criteria:**
1. Portal deployed on Vercel at a stable URL; logged-out visits redirect to Google sign-in; no
   email/password or magic-link UI exists anywhere in the app (confirm both in the Supabase Auth
   provider config and the login page markup).
2. Signing in with a non-allowlisted Google account is signed out immediately with a visible
   "not authorized" message; devtools network tab shows no successful watchlist/holdings query for that
   session.
3. Signing in with the allowlisted admin account reaches the authenticated app.
4. Admin can add/edit/delete a `watchlist` row and a `holdings` row from the portal; each change is
   confirmed by querying Supabase directly.
5. The same writes attempted via a direct REST call with the anon key and **no** authenticated admin
   session are rejected by RLS (`curl` returns a permissions error) — proves NFR6's "no unauthenticated
   write path."
6. `admin_allowlist`/`is_admin()` exist and are used by both new RLS policies (grep the migration).
7. No secret of any kind (there is none in this design — no GitHub PAT, no server-only credential) appears
   in the built client bundle or any browser network request; the portal's only "credential" is the
   signed-in user's own Supabase session, which is expected and RLS-gated.

### INC-6 — Admin portal: tunables editor (FR30) — REVISED 2026-07-27, Decisions #27 (supersedes #24) and #28 (refines #27)
**Design:** `docs/design/admin-portal-tunables.md` §16.4. **Files:** new `sql/admin_portal_tunables.sql`
(`tunables` table, `_stamp_tunable_update()` trigger, `admin_write_tunables` RLS policy, 10-row seed);
new `tunables_cache.json` (10-key seed file, identical values to the SQL seed); new
`admin-portal/app/tunables/` (portal UI); additions to `scripts/config.py` (two-tier fallback chain —
Supabase table → `tunables_cache.json`, no third hardcoded-literal tier; fails loud via
`SystemExit` if both tiers miss a key, see `admin-portal-tunables.md` §16.4's 2026-07-28 revision — plus
`write_tunables_cache_if_fetched()` and the `ALERTS_ENABLED` AND-gate, §16.4); one line added to
`run_hourly.py`'s entry point; **`.github/workflows/hourly-watchlist.yml`** gains a `permissions:
contents: write` block (it has none today) and a new "Commit tunables cache if changed" step mirroring
`publish-prices.yml`'s existing commit-on-change step. `daily-discovery.yml` and `publish-prices.yml` are
**not** touched (read-only cache consumers, same as every script). **Depends on INC-5's
`admin_allowlist`/`is_admin()` already existing.**
**Simplification note (still holds after Decision #28):** this increment remains **smaller** than the
original GitHub-PAT-proxy plan — no GitHub API integration, no PAT, no Vercel API route/proxy. Decision
#28 adds exactly one small, well-precedented workflow change (the tunables-cache commit step, copied
from a pattern already live and proven in `publish-prices.yml`), not a new category of risk. Both open
questions from earlier passes — the GitHub-Variable wiring gap, and now the failed-fetch fallback +
write-ownership question — are resolved structurally, not deferred.
**Acceptance criteria:**
1. `tunables` table exists, seeded with exactly the 10 FR30 keys at their current default
   value/description/example (matches `requirements.md` §10's per-key defaults — no behavior change at
   cutover, confirmed by diffing a fresh run's `data_snapshot`/discovery output against the pre-INC-6
   baseline for an unedited row). **`ALERTS_ENABLED`'s seed value is `"true"`** (today's actual live
   default via the `workflow_dispatch` input), not `config.py`'s bare `"false"` literal — verify this
   specific row explicitly, since seeding it wrong would silently break production alerting.
2. `tunables_cache.json` is committed with **exactly** the same 10 key/value pairs as the SQL
   seed above (byte-for-byte value match per key, including `ALERTS_ENABLED: "true"`) — diff the two
   seed sources directly, don't just eyeball them.
3. Writing to `tunables` with the anon key and **no** authenticated admin session is rejected by RLS
   (`curl` returns a permissions error) — same proof pattern as INC-5 item 5.
4. Updating a row via the portal stamps `updated_at`/`updated_by` correctly (server-side, via the
   trigger — not client-supplied) and is visible on next read; `select * from tunables` after an edit
   confirms the new `value` and the signed-in admin's email in `updated_by`.
5. `scripts/config.py`'s `_tunable()`-derived values (e.g. `GEMINI_MODEL`, `DISCOVERY_GAINER_PCT`) pick
   up a table edit on the **next process start** (import-time fetch — not live/hot-reloaded mid-run,
   confirmed by editing a row, then re-running a script and observing the new value in its `[config]`
   startup log line).
6. **Cache write-back, unchanged case:** running `hourly-watchlist.yml` (or `run_hourly.py` locally
   against a live Supabase connection) when no `tunables` row has changed since the last run produces
   **zero** git commits — `git log` before/after shows no new commit touching
   `tunables_cache.json`.
7. **Cache write-back, changed case:** editing one `tunables` row via the portal, then triggering
   `hourly-watchlist.yml`, produces **exactly one** new commit authored by `github-actions[bot]`, message
   `chore: refresh tunables cache [skip ci]`, touching only `tunables_cache.json`, containing the
   new value and nothing else changed.
8. **Read-only workflows never write:** simulating a Supabase fetch failure (e.g. temporarily wrong
   `SUPABASE_URL`/blocked network) during a `daily-discovery.yml` or `publish-prices.yml` run — (a) the
   run falls back to `tunables_cache.json`'s values correctly (confirmed via the `[config]`
   startup log line naming the fallback tier used) and completes normally; (b) `git status`/`git log`
   shows **no** attempt to write or commit `tunables_cache.json` from either workflow — grep
   `run_discovery.py` and `publish_prices.py` for `write_tunables_cache_if_fetched` and confirm zero
   matches.
9. **Double-failure fails loud, not silent.** With the Supabase project unreachable (or the fetch
   returning no rows) **and** `tunables_cache.json` deleted or corrupted in a scratch test,
   importing `scripts/config.py` (and therefore any entry point that imports it —
   `run_hourly.py`/`run_discovery.py`/`publish_prices.py`) raises `SystemExit` naming the first
   unresolvable tunable key and both failed sources, and the process exits non-zero — it must **not**
   proceed with any value for that key (no hardcoded-literal floor exists to fall back to as of the
   2026-07-28 revision). A qa test performs exactly this: delete/corrupt the cache file, force the
   Supabase fetch to fail (bad URL or mocked exception), invoke the entry point, and assert non-zero
   exit + the `SystemExit` message naming the affected key.
10. `ALERTS_ENABLED`: with the `tunables` row set to `false`, a scheduled (no-`inputs`) run sends no real
    push even though the `workflow_dispatch` input defaults to `true` (table/cache suppresses). With the
    row `true` and a manual dry-run (`inputs.alerts_enabled=false`), no real push is sent either (input
    still wins as a floor) — proves the AND-gate direction is correct, not just "some interaction exists."
11. `git diff` shows **zero** changes to `daily-discovery.yml` / `publish-prices.yml` for this increment;
    `hourly-watchlist.yml`'s diff is limited to the new `permissions:` block and the one new commit step.

### INC-7 — Admin portal: track-record view & kill-switch UI (FR31, FR32)
**Design:** `docs/design/admin-portal.md` §16.5–§16.6, `operational-controls.md` §13.3 (forward
reference). **Files:** `admin-portal/app/track-record/`; kill-switch toggle on the shared authenticated
layout; new `sql/kill_switch_portal_grant.sql` (extends `set_kill_switch`, adds
`kill_switch_state` SELECT policy). **Depends on INC-3.**
**Acceptance criteria:**
1. Read-only, paginated presentation of `call_log`/`latest_call_per_ticker` — no new aggregation/scoring
   beyond what's already logged (review confirms no derived-analytics code was added).
2. Kill-switch toggle shows the live `kill_switch_state.paused` value on load; flipping it calls
   `set_kill_switch(..., p_source:='admin-portal')` and produces a new `kill_switch_audit` row with
   `source='admin-portal'` and `actor` = the signed-in admin's email.
3. After toggling pause on via the portal, a subsequent dispatch call makes no `pg_net` request (reuses
   INC-3's verification method) — proves the UI is wired to the real flag.
4. All INC-5/INC-6 acceptance criteria still hold (full portal regression: auth gate, allowlist, RLS,
   no client-exposed secrets).

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
| NFR3 | `components.md` §4.6, §4.7; `non-functional-ops.md` §7.2 |
| NFR4 | `components.md` §4.1 cadence; `frontend.md` §11 freshness posture |
| FR24–FR30 (2026-07-12 US/CA shadow pilot), NFR5 (old) | **RETIRED 2026-07-16** — formerly the US/CA shadow pilot; see "Retired: shadow-pilot tracks" above. FR text preserved only in git history (deleted outright from `docs/requirements.md`). Note: `docs/requirements.md`'s retirement pass freed these IDs, and the 2026-07-26 CR below reassigns FR24–FR33/NFR5–6 to entirely new, unrelated requirements (kill-switch/portal/AI-abstraction) — same numbers, no relation to the retired content; not a collision. |
| FR31 (old, shared wallet-sim harness) | **RETIRED 2026-07-16** — see "Retired: shadow-pilot tracks" above. FR text preserved only in git history. |
| FR32–FR39 (old), NFR6 (old) | **RETIRED 2026-07-16** — formerly the NSE shadow pilot; see "Retired: shadow-pilot tracks" above. FR text preserved only in git history. |
| FR24, FR25, FR26 (kill-switch, 2026-07-26 CR) | **DRAFT** — `operational-controls.md` §13. INC-3. |
| FR27, FR28, FR29, FR30, FR31, FR32 (admin portal, 2026-07-26 CR), NFR5, NFR6 | **DRAFT** — `admin-portal.md` §16. INC-5/INC-6/INC-7. |
| FR33 (AI provider abstraction, 2026-07-26 CR) | **DRAFT** — `operational-controls.md` §14. INC-4. |

**Coverage:** FR1–FR23 and NFR1–NFR4 (core, live) are covered as-built across the module files above.
**FR24–FR31/NFR5 and FR32–FR39/NFR6 (old numbering) are retired (2026-07-16)** — the requirement IDs
remain in `docs/requirements.md` for historical traceability only. **FR24–FR33 and NFR5–NFR6 (current,
2026-07-26 CR) are DRAFT design**, covered by the Increment Plan above (INC-3–INC-7) and the two new
module files; not yet implemented, and INC-6 has one open design gap pending confirmation
(`admin-portal-tunables.md` §16.4). No dev work starts on any of INC-3–INC-7 before the user approves this plan
at GATE 3.
