# Stock Advisory Agent — Solution Design (as-built + draft increment plan)

**Owner:** tech-lead. **Status:** DESCRIPTIVE / as-built for FR1–FR23, NFR1–NFR4 (core, live). **DRAFT**
for the 2026-07-26 change request — kill-switch (FR24–FR26), admin portal (FR27–FR32, NFR5–6), AI
provider abstraction (FR33) — covered by the Increment Plan below (INC-3–INC-7) and two new module
files. **Not yet implemented; no dev work starts before the user approves this plan at GATE 3**, per
CLAUDE.md's pipeline gates. One open design gap needs Arjun's/pm's sign-off before INC-6 specifically —
see `docs/design/admin-portal.md` §16.4. Split into per-module files under `docs/design/` (2026-07-25,
REV-024) — **this file is a thin index; read the module file(s) your increment actually touches, not the
whole tree.**

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
| `docs/design/admin-portal.md` **(DRAFT)** | Admin portal: hosting/auth, authorization model (RLS/allowlist), watchlist/holdings CRUD, tunables editor, track-record view, kill-switch UI, secrets inventory | §16 |

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
passes QA (CLAUDE.md non-negotiable); INC-6 additionally has one open design question that needs
Arjun's/pm's confirmation before it starts (flagged below and in `admin-portal.md` §16.4).**

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
7. No secret (GitHub PAT or otherwise) appears in the built client bundle or any browser network request
   — trivially true this increment (no PAT usage yet) but asserted as the INC-6 baseline.

### INC-6 — Admin portal: tunables editor (FR30)
**Design:** `docs/design/admin-portal.md` §16.4. **Files:** `admin-portal/app/api/tunables/route.ts`,
`admin-portal/lib/tunables-metadata.ts`, `admin-portal/app/tunables/`; **plus**, pending the open
question below, `daily-discovery.yml`, `hourly-watchlist.yml`, `scripts/config.py`.
**⚠️ Do not start this increment until the open design gap in `admin-portal.md` §16.4 is confirmed with
Arjun via pm** — 8 of the 10 curated tunables are not actually wired to a GitHub Actions Variable in the
live workflows today, contrary to what FR30/Decision #24 assumed; a recommended resolution is written up
in §16.4 but needs an explicit nod since it touches a documented safety mechanism (`ALERTS_ENABLED`)
before dev builds against it.
**Acceptance criteria:**
1. `/api/tunables` reads the GitHub PAT only from a server-only Vercel env var; absent from any client
   bundle (grep the built output).
2. The route rejects requests without a valid authenticated admin session — direct unauthenticated
   `curl` returns 401/403.
3. The UI lists exactly the 10 FR30 keys, each with description, example, and a correct current
   effective value (including the `GEMINI_MODEL_BACKUP` "unset = fallback disabled" special case, §16.4)
   — no other tunable is editable here.
4. Editing and saving a value updates the corresponding GitHub Actions Variable (`gh variable list`
   confirms), and the next workflow run picks it up.
5. `scripts/config.py`'s existing tunables and the `${{ vars.X || 'default' }}` wiring already in
   `hourly-watchlist.yml` are unmodified by keys that were already correctly wired (`GEMINI_MODEL`/
   `_BACKUP`); the `DISCOVERY_*`/`ALERTS_ENABLED` wiring fix (if confirmed) is additive per §16.4, not a
   behavior change when the new Variables are left unset.

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
(`admin-portal.md` §16.4). No dev work starts on any of INC-3–INC-7 before the user approves this plan
at GATE 3.
