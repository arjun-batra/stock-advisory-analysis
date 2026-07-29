# Handoff — Live-system fix: `ingest.get_price_only()` (REV-043, carried since Pass 15)

## Build plan (written before coding, per dev's updated workflow)

Read `docs/review-log.md` REV-043 + `docs/design/components.md` §4.2's design call +
`docs/design/non-functional-ops.md`'s repo-structure DRAFT note for `ingest.py`/`publish_prices.py`, and
`docs/code-map.md`. Design fixes the contract: `ingest.get_price_only(ticker) -> dict` — `period='5d'`
history (enough for `price`/`pct_change_1d`) plus `tk.fast_info` for currency, **no** `tk.info` scrape,
**no** `tk.news` call; `publish_prices.py` switches its one call site from `get_market_data()` to
`get_price_only()`; `get_market_data()` stays untouched (still the only path `run_hourly.py`/
`run_discovery.py` use). Files: `scripts/ingest.py` (new function + `_fetch_history` gains an optional
`period` param, default unchanged), `scripts/config.py` (new `YF_PRICE_ONLY_PERIOD` tunable, "5d" default
— same pattern as `YF_HISTORY_PERIOD`, no hardcoded fetch window per CLAUDE.md), `scripts/publish_prices.py`
(one-line call switch + docstring update), `tests/test_ingest.py` (new coverage),
`tests/test_tunables.py` (two existing mocks of `publish_prices.ingest.get_market_data` renamed to
`get_price_only` — they'd otherwise silently stop exercising the real call path). No design deviation;
scope stays inside REV-043 as written. Verify: full suite green, direct smoke-run of `publish_prices.main()`
with a mocked `get_price_only`, confirm `pages/prices.json` output values match what the old full fetch
would have produced for the same close data.

## What changed and why

`publish_prices.py` was pulling a full `get_market_data()` per ticker (3mo history + `tk.fast_info` +
`tk.info` + `tk.news`, ~4 Yahoo requests) but only ever reads `price`/`pct_change_1d`/`market`/
`fundamentals.currency`. `get_price_only()` fetches a 5d history window (still enough for `price` and
`pct_change_1d` — both only ever look at the last 1-2 closes) and `tk.fast_info` for currency, skipping the
`tk.info` scrape and `tk.news` fetch entirely. This is a pure efficiency fix: same published price values,
cheaper fetch. `get_market_data()` and its callers (`run_hourly.py`, `run_discovery.py`) are unchanged.

## Files touched

- `scripts/ingest.py` — added `get_price_only(ticker) -> dict`; `_fetch_history` gained an optional
  `period` param (defaults to `config.YF_HISTORY_PERIOD`, so `get_market_data`'s behavior is unchanged).
- `scripts/config.py` — added `YF_PRICE_ONLY_PERIOD` (default `"5d"`), same tunable pattern as
  `YF_HISTORY_PERIOD`/`YF_HISTORY_RETRIES`.
- `scripts/publish_prices.py` — call site switched `ingest.get_market_data(ticker)` ->
  `ingest.get_price_only(ticker)`; no other logic changed (same dict field names read: `has_price`,
  `price`, `pct_change_1d`, `market`, `fundamentals.currency`, `notes`).
- `tests/test_ingest.py` — three new tests: `get_price_only` returns correct price/1d-change fields and
  never touches `tk.info`/`tk.news` (raises if it does); its price/pct_change_1d values match
  `get_market_data`'s for the same underlying closes (no behavior change); empty-history skip-with-log path.
- `tests/test_tunables.py` — two existing `publish_prices` heartbeat tests updated to mock
  `ingest.get_price_only` instead of the now-unused-by-`publish_prices` `ingest.get_market_data` (the old
  mocks would have gone stale silently — `publish_prices.main()` no longer calls `get_market_data` at all).

## How to run

`python3 -m pytest tests/test_ingest.py tests/test_tunables.py -q` for the targeted coverage, or the full
suite: `python3 -m pytest -q --tb=short` (207 passed, 0 failed — no regressions). Manual smoke test: mock
`state.client`/`state.get_watchlist`/`ingest.get_price_only`/`state.write_heartbeat` and call
`publish_prices.main()` in a tmp cwd — confirmed it writes `pages/prices.json` with the expected
price/chg/market/currency shape and an `ok` heartbeat.

## Known limitations / follow-ups

- `docs/design/non-functional-ops.md` §9's tunables list does not yet mention `YF_PRICE_ONLY_PERIOD` —
  that file is tech-lead-owned (dev doesn't touch design docs per CLAUDE.md); flagging for tech-lead to add
  a one-line entry alongside `YF_HISTORY_PERIOD`'s.
- REV-043's "related, not addressed here" note (`publish_prices.py` has no market-open gate in
  `sql/scheduler_pgcron.sql`) is explicitly out of scope for this fix and unchanged — still a pm question
  per the design doc.

---

# Handoff — REV-096 fix: relocate `BATCH_SYSTEM_PROMPT` out of `ai_judge.py` into `prompts/`

## Build plan (written before coding, per dev's updated workflow)

- **Read first:** `docs/code-map.md` (`ai_judge.py` = provider-neutral judge, no other module reads
  `BATCH_SYSTEM_PROMPT`), `docs/design/components.md:157-183` and
  `docs/design/operational-controls.md:328-335` (tech-lead had already pre-updated both to say the
  prompt "lives in `prompts/batch_system_prompt.txt`, loaded at import time by `ai_judge.py`" — no
  design ambiguity to flag; pm's decision + tech-lead's design edit were both already on disk before
  I started).
- **Scope:** pm-decided, code-hygiene-only relocation (REV-096) — move the literal text verbatim,
  keep the resulting formatted `BATCH_SYSTEM_PROMPT` value byte-identical. No prompt wording change,
  no new config tunable (the path itself isn't a runtime-configurable value — same posture as
  `config._CACHE_PATH`, a structural file location, not a tunable).
- **Files:** new `prompts/batch_system_prompt.txt` (the relocated text, with the one
  `{RATIONALE_MAX}` interpolation point kept as a literal `{RATIONALE_MAX}` placeholder);
  `scripts/ai_judge.py` (delete the inline constant, read the file at import time, resolve the
  placeholder via `str.replace` — not `str.format`, since the prompt's own JSON-example text
  contains literal `{`/`}` that `str.format` would otherwise require escaping).
- **Contracts touched:** none — `BATCH_SYSTEM_PROMPT` stays a module-level `str` in `ai_judge.py`,
  same two call sites (`judge_batch`, lines ~300/318), same value.
- **Verification:** built a throwaway script that `exec()`'d the pre-edit inline constant with
  `RATIONALE_MAX=280` bound to capture the exact ground-truth string, then compared it byte-for-byte
  against `ai_judge.BATCH_SYSTEM_PROMPT` after the edit (`==` True, same length, 1821 chars) — plus
  the full test suite and a fresh import smoke test.

## Files touched

- `prompts/batch_system_prompt.txt` — new. The relocated prompt text, `{RATIONALE_MAX}` left as a
  literal placeholder resolved at import time.
- `scripts/ai_judge.py` — removed the inline `BATCH_SYSTEM_PROMPT` string constant; added
  `import pathlib`, `_PROMPT_PATH` (resolved the same way `config._CACHE_PATH` is — repo root via
  `pathlib.Path(__file__).resolve().parent.parent`, since `scripts/` is a flat, non-package
  directory), and a `.read_text().replace("{RATIONALE_MAX}", str(RATIONALE_MAX))` load with a
  fail-loud `SystemExit` if the file is missing/unreadable (matches this codebase's established
  fail-loud posture for required config, e.g. `config.require_secrets`/`config._tunable`).

## How to run

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` from repo root — 207 passed (no test
  asserted the prompt's literal content, so none needed changes).
- Smoke test: `python3 -c "import sys; sys.path.insert(0,'scripts'); import
  ai_judge; print(len(ai_judge.BATCH_SYSTEM_PROMPT))"` with `SKIP_TUNABLES_FETCH=true` set — imports
  cleanly, prints `1821` (same length as before the move).

## Known limitations

- None functional — this is a pure relocation. `docs/design/components.md` and
  `docs/design/operational-controls.md` already describe the post-fix state (tech-lead pre-updated
  them alongside the pm decision), so no design-doc follow-up is owed by this change.
- Unrelated in-flight changes were present in the working tree before this session started
  (`scripts/config.py`, `scripts/ingest.py`, `scripts/publish_prices.py`, `sql/kill_switch.sql`,
  `tests/test_ingest.py`, `tests/test_tunables.py`, plus a new untracked
  `sql/schema_truncate_grant_closure.sql`) — not touched or reviewed here; this handoff's diff is
  scoped strictly to `prompts/batch_system_prompt.txt` and `scripts/ai_judge.py`.

---

# Handoff — Evidence record: INC-3 kill-switch live test (AC2/AC4/AC5) + ClientOptions hotfix live confirmation

## Context

`docs/test-report.md`'s Phase-4 whole-system end-to-end entry correctly declined to mark INC-3's
AC2/AC4/AC5 as independently verified: it checked `docs/review-log.md` (Pass 21's "Open items" still
lists REV-070 open) and `docs/handoff.md` in full, found no dated evidence block for a live kill-switch
pause/resume test anywhere in the repo (unlike REV-083's precedent for INC-5's AC8), and correctly left
REV-070/INC-3's status as still deferred rather than take an unrecorded claim on faith. That was the
right call — no code or doc change from dev was warranted on the strength of an unwritten claim. This
entry supplies the missing evidence, in the same dated/attributed/checkable format REV-083 established,
so qa can independently corroborate it and update `docs/test-report.md` accordingly (qa's file, not
touched here — see the handoff note in this session's final summary).

### AC2/AC4/AC5 / REV-070 live kill-switch pause/resume audit — raw evidence

**Date:** 2026-07-29. **Run by:** orchestrator, live query via Supabase MCP `execute_sql` against
project `ikghqdtlbwifwnooytmm` (user explicitly authorized live testing against production for this
session, being the sole user and accepting the risk).

```
-- Baseline before test
select max(id) as max_id_before from net._http_response;
=> max_id_before = 1362

-- Pause
select public.set_kill_switch(true, 'e2e-test-orchestrator');
=> (void, no error)

-- Attempt dispatch while paused (AC2)
select public.dispatch_github_workflow('hourly-watchlist.yml') as result;
=> result = null   (function's own source: returns null immediately when
   kill_switch_state.paused=true, before ever reaching net.http_post --
   confirmed by reading pg_get_functiondef(oid) for dispatch_github_workflow
   before running this test)

-- Confirm zero new pg_net requests (AC2)
select max(id) as max_id_after_paused_dispatch from net._http_response;
=> max_id_after_paused_dispatch = 1362   (unchanged -- zero new HTTP requests
   were made while paused)

-- Resume
select public.set_kill_switch(false, 'e2e-test-orchestrator');
=> (void, no error)

-- Audit trail (AC4)
select * from public.kill_switch_audit order by changed_at asc;
=> [
     {id: d9f6b308-..., action: pause,  actor: postgres, source: e2e-test-orchestrator, changed_at: 2026-07-29 17:45:58.972166+00},
     {id: e57f7053-..., action: resume, actor: postgres, source: e2e-test-orchestrator, changed_at: 2026-07-29 17:46:03.68885+00}
   ]
   -- exactly 2 rows, correct action values, non-null actor, source correctly
   -- attributed, ~5 seconds apart (pause then resume)

-- Final state confirmed restored to normal
select * from public.kill_switch_state;
=> {id: true, paused: false, updated_at: 2026-07-29 17:46:03.68885+00, updated_by: postgres}

-- RLS check (AC5)
select relname, relrowsecurity, relforcerowsecurity from pg_class
where relname in ('kill_switch_state','kill_switch_audit');
=> [
     {kill_switch_audit, rls_enabled: true, rls_forced: true},
     {kill_switch_state, rls_enabled: true, rls_forced: false}
   ]
```

This closes `docs/test-report.md`'s open evidence gap for INC-3's **AC2** (pausing suppresses dispatch
before any `pg_net` call — `dispatch_github_workflow` returned `null` and `net._http_response`'s max id
was unchanged across the paused-dispatch attempt, confirming zero HTTP requests were made while paused),
**AC4** (audit trail — exactly 2 rows, correct `action` values, non-null `actor`, `source` correctly
attributed to the caller, pause/resume ~5 seconds apart), and **AC5** (RLS enabled on both
`kill_switch_state` and `kill_switch_audit`, matching `sql/kill_switch.sql`'s design). AC1 (objects
exist) was already covered by INC-3's original build. **AC3 (resume-baseline / no-false-alarm test under
synthetic staleness) is a separate test this evidence does not cover and remains deferred** — do not
mark it verified from this record.

### ClientOptions hotfix — live production confirmation (separate, later run)

**Date:** 2026-07-29. **Run by:** orchestrator, live query via Supabase MCP `execute_sql` against
project `ikghqdtlbwifwnooytmm`, after the hotfix (main commit `79cea50`) was picked up by the next real
scheduled run.

```
-- Before fix (run at 17:31:41 UTC, pre-fix commit): status='partial' for both hourly-watchlist and publish-prices

-- After fix merged (main commit 79cea50) and picked up by the 18:00:01 UTC scheduled run:
select workflow_name, last_run_at, status from public.run_heartbeat order by workflow_name;
=> hourly-watchlist:  last_run_at=2026-07-29 18:01:49, status=ok
   publish-prices:    last_run_at=2026-07-29 18:03:32, status=ok
```

Confirms the `ClientOptions` hotfix (this file's "Production bug fix" section immediately below)
resolved the live tunables-fetch failure in production, not just in local reproduction — both scheduled
workflows moved from `status=partial` (pre-fix) to `status=ok` (post-fix) on the very next real run.

---

# Handoff — Production bug fix: `ClientOptions` incompatibility broke live tunables fetch

## Build plan (written before coding, per dev's updated workflow)

- **What broke:** `scripts/config.py`'s `_fetch_tunables()` called
  `create_client(SUPABASE_URL, SUPABASE_SECRET_KEY, options=ClientOptions(postgrest_client_timeout=...))`.
  The installed `supabase-py==2.31.0`'s `create_client()`/`Client.__init__` only sets
  `options.storage` on its OWN internally default-constructed `ClientOptions` (the
  `if options is None:` branch) — the importable `supabase.lib.client_options.ClientOptions`
  dataclass has no `storage` field at all (confirmed via `inspect.getsource`/`dataclasses.fields`
  against the exact installed version). Passing a caller-built instance skipped that branch and
  crashed with `AttributeError: 'ClientOptions' object has no attribute 'storage'` on every call
  since INC-6 merged, degrading `hourly-watchlist`/`publish-prices` to `partial` (real push
  notifications) on every scheduled run — the tunables editor never functionally reached
  production; every run silently used the tier-2 cache.
- **Fix:** don't construct `ClientOptions` at all — `create_client(SUPABASE_URL,
  SUPABASE_SECRET_KEY)` (no `options=`), then `client.postgrest.session.timeout =
  httpx.Timeout(TUNABLES_FETCH_TIMEOUT_MS / 1000)` on the already-built client. Removed the
  now-unused `from supabase.lib.client_options import ClientOptions` import; added `import
  httpx` (already a pinned transitive dependency via `requirements.txt`, no new dependency).
- **Files:** `scripts/config.py` (the fix); `docs/design/tunables-fallback.md` (REV-095 — synced
  the as-built code block + added an incident/resolution note, since this is the same file's
  contract the code implements, same precedent as REV-092); `tests/test_tunables.py` (updated
  `_FakeSupabaseClient`/`mock_tunables_fetch` to model `.postgrest.session.timeout` instead of a
  `create_client(options=...)` kwarg, and rewrote `test_ac13_timeout_is_actually_passed_into_client_options`
  to match); new `tests/test_fetch_tunables_real_client_construction.py` — regression tests that
  go through the REAL (unmocked) `supabase.create_client()` construction path, which is exactly
  the seam the old mock-the-whole-function test pattern never exercised and let this ship
  undetected.
- **Contracts touched:** none outside `scripts/config.py`'s internal `_fetch_tunables()` — the
  function's return contract (`dict[str, str]` on success, `{}` on any failure) is unchanged;
  every caller (`_TUNABLES = _fetch_tunables()` at import time) is untouched.
- **Verification:** full existing suite (204 tests, all pass) + 3 new regression tests; manual
  reproduction of both the old crash (`AttributeError: 'ClientOptions' object has no attribute
  'storage'`, confirmed against the real installed `supabase-py==2.31.0`) and the fixed path
  (fails with a real network/proxy error caught by `except Exception`, not the AttributeError) via
  local `python3` against `https://example.invalid.supabase.co` (RFC 2606 never-resolves host,
  no live credentials needed); all three entry points (`run_hourly.py`, `run_discovery.py`,
  `publish_prices.py`) import cleanly end to end with `SKIP_TUNABLES_FETCH=true` and separately
  with `SKIP_TUNABLES_FETCH=false` against the fake host (falls back to tier-2 cache exactly as
  designed, `TUNABLES_DEGRADED=True`, no crash).

## Files touched

- `scripts/config.py` — the fix (`_fetch_tunables()`, imports).
- `docs/design/tunables-fallback.md` — REV-095: as-built code block sync + incident note.
- `tests/test_tunables.py` — fixture/test update to match the new client-construction shape.
- `tests/test_fetch_tunables_real_client_construction.py` — new, real (unmocked) construction-path
  regression coverage.

## How to run

- `python3 -m pytest -q --tb=short` from repo root (204 passed).
- Manual repro/verify (no live credentials needed):
  `SKIP_TUNABLES_FETCH=false SUPABASE_URL=https://example.invalid.supabase.co
  SUPABASE_SECRET_KEY=fake GEMINI_API_KEY=fake python3 -c "import sys;
  sys.path.insert(0,'scripts'); import config"` — should log a `403`/network-class failure and
  `TUNABLES_DEGRADED=True`, never an `AttributeError`.

## Known limitations

- No live Supabase project available this session — the fix's construction-path correctness is
  verified against the real installed library (no `AttributeError`), but a genuine tier-1 fetch
  success (real rows returned) was not re-verified live; that path's shape (`.table().select()
  .execute().data`) is unchanged from before this fix and was already covered by INC-6's
  mocked-fetch tests.
- Design-doc sync (`docs/design/tunables-fallback.md`) done by dev per this project's REV-092
  precedent for a fix this tightly coupled to one code block; if tech-lead wants a second pass
  over the wording, flag it — no structural/contract change was made, only the code block and an
  incident note.

---

# Handoff — INC-7: Admin portal track-record view & kill-switch UI (FR31, FR32)

## Build plan (written before coding, per dev's updated workflow)

- **Design read:** `docs/design/admin-portal.md` §16.5 (track-record, read-only/no-new-aggregation
  hard boundary) + §16.6 (kill-switch UI, exact SQL block to copy verbatim) + §16.8 (module
  boundaries: `app/track-record/`, toggle "surfaced on a shared authenticated layout/header, not a
  standalone page", `sql/kill_switch_portal_grant.sql`); `operational-controls.md` §13 for INC-3
  context; `data-and-flow.md` §5 for `call_log`/`latest_call_per_ticker` schema.
- **Files:** new `sql/kill_switch_portal_grant.sql` (copy design's function/grant/policy block
  verbatim + close a TRUNCATE-grant gap on `kill_switch_state`/`kill_switch_audit`, same class as
  REV-081/REV-086); new `admin-portal/app/(app)/track-record/page.tsx` (paginated/sortable/filterable
  `call_log` read, no view needed — see below); new `admin-portal/components/KillSwitchToggle.tsx`
  (isolated component, single responsibility); `AuthGuard.tsx` gets the toggle + a `/track-record` nav
  link (it's the file that actually renders the shared header every authenticated route sees —
  `layout.tsx` is a one-line `<AuthGuard>{children}</AuthGuard>` pass-through, same reasoning INC-6
  used when it put the Tunables nav link in `AuthGuard.tsx` rather than `layout.tsx`); small
  `globals.css` additions for the toggle's paused/running badge.
- **Contracts touched:** `set_kill_switch(boolean, text)` (INC-3, extended not replaced),
  `kill_switch_state`/`kill_switch_audit` grants (INC-3), `call_log`'s existing
  `anon_read_call_log` SELECT policy (read-only consumer, zero SQL change). No new RLS for
  track-record — reuses the policy the public dashboard already relies on.
- **`call_log` vs `latest_call_per_ticker` decision:** FR31/FR15 frame this as the full auditable
  log ("the full log is what makes §2's success criterion auditable"), and the view is
  DISTINCT-ON'd to one row per ticker (a handful of rows — nothing to paginate). AC1's "paginated
  presentation" only makes sense against the full `call_log` history, so the page queries `call_log`
  directly with `.range()`/`.order()`, selecting the same slim column set the view already proved
  safe (`parse_status`, `price`, `confidence` extracted via `->>'key'` from `data_snapshot`, never
  shipping `raw_model_response`) — same technique as `sql/dashboard_latest_call_view.sql`, applied
  inline via PostgREST's query-string JSON-operator syntax instead of a stored view. This is the one
  piece flagged for live verification below (my own client library doesn't validate the string; only
  Supabase's live PostgREST does).
- **Verification plan:** full existing suite (pytest + node --test + npm build/lint) before and after;
  AC1 self-check is a grep-for-aggregation-logic code review (no `reduce`/win-rate/scoring math
  anywhere in the new page) since there's no live DB to exercise it against; AC2/AC3 need live
  Supabase/dispatch access I don't have this session — flagged explicitly below, same posture as
  every prior increment's handoff.

---

## Files changed

- **New `sql/kill_switch_portal_grant.sql`** — copies `docs/design/admin-portal.md` §16.6's exact
  block verbatim: `create or replace function public.set_kill_switch(...)` (adds the
  `auth.uid() is not null and not public.is_admin()` authorization check — an authenticated portal
  caller must pass `is_admin()`; a null-`auth.uid()` direct-SQL/service-role caller is unaffected,
  preserving INC-3's original trusted-direct-SQL path), `grant execute on function
  public.set_kill_switch(boolean, text) to authenticated;`, and `create policy
  "admin_read_kill_switch" on public.kill_switch_state for select to authenticated using
  (public.is_admin());`.

  **Also closes a TRUNCATE-grant gap this increment is the right place to close** (per the brief's
  explicit ask to check): `sql/kill_switch.sql` (INC-3) enabled RLS on `kill_switch_state` with zero
  policies and revoked `insert, update, delete` on `kill_switch_audit` — but **neither table's REVOKE
  ever included `truncate`**, unlike `admin_allowlist` (REV-081) and `tunables` (REV-086), which both
  got the full `insert, delete, truncate` (or `insert, update, delete, truncate`) treatment once this
  exact class of gap was found. RLS does not govern `TRUNCATE` at all in Postgres — it's gated purely
  by the `TRUNCATE` table privilege, which Supabase's default public-schema grants otherwise leave
  live for `anon`/`authenticated` regardless of RLS being enabled. This file adds:
  ```sql
  revoke insert, update, delete, truncate on public.kill_switch_state from public, anon, authenticated;
  revoke truncate on public.kill_switch_audit from public, anon, authenticated;
  ```
  `kill_switch_state` gets all four verbs revoked (RLS with zero policies already denied
  SELECT/INSERT/UPDATE/DELETE via PostgREST, but not TRUNCATE — REVOKE is the belt-and-suspenders
  fix, matching `admin_allowlist`'s pattern exactly since there's no legitimate direct-write path here
  either, only `set_kill_switch()`). `admin_read_kill_switch`'s new SELECT policy for `authenticated`
  is unaffected — REVOKE never touched SELECT. `kill_switch_audit` only needs the missing `truncate`
  verb added (insert/update/delete were already revoked by `sql/kill_switch.sql`); repeating
  already-revoked verbs would be harmless but redundant, so this file states only the one gap that's
  actually new. Both REVOKEs are placed first in the file (independent of the function/grant/policy
  block that follows), matching `admin_portal_rls.sql`/`admin_portal_tunables.sql`'s convention of
  revoking before or alongside the policy that legitimizes the narrower access that remains.

  **Syntax self-check performed** (per the brief's explicit warning about the INC-6
  `CREATE POLICY ... FOR select, update` comma-list bug, which no dev/qa/reviewer pass caught until
  live application): the new `admin_read_kill_switch` policy names exactly one command (`select`), not
  a comma list — same shape as the now-fixed `admin_read_tunables`/`admin_write_tunables` pair. The
  `create or replace function` block's grammar (`declare`/`begin`/`if ... then ... end if;`/`update`/
  `insert`/`end;`) was diffed line-by-line against `sql/kill_switch.sql`'s already-proven-live
  `set_kill_switch` body — identical `language plpgsql security definer set search_path = ''`
  preamble and closing `$$;`, with only the new `if` block and `v_actor` declaration added inside.
  **Not applied live by dev** (no Supabase MCP access this session) — orchestrator applies this after
  handoff, same process as `sql/admin_portal_rls.sql`/`sql/admin_portal_tunables.sql`.

- **New `admin-portal/app/(app)/track-record/page.tsx`** — read-only, paginated, sortable, filterable
  presentation of `public.call_log`, inside the `(app)` route group so it inherits `AuthGuard`'s
  session/allowlist check automatically (no new guard code). Query: `.from("call_log").select(
  "id,ticker,verdict,rationale,timestamp,label,alerted,parse_status:data_snapshot->>parse_status,
  price:data_snapshot->>price,confidence:data_snapshot->>confidence", { count: "exact" })` with
  `.range()` (25 rows/page, a local `PAGE_SIZE` UI constant — not a business tunable, no config-file
  entry per design's tunables scope) and `.order()`. Filters: ticker (`ilike`, substring), label
  (`watchlist`/`new-candidate`, matches `data-and-flow.md` §5), verdict (`Buy`/`Sell`/`Hold`, matches
  `pages/common.js`'s `VERDICT` map) — applied via an explicit "Apply filters"/"Clear" button pair
  (not live-as-you-type), matching the rest of the portal's explicit-action convention. Sort: ticker,
  verdict, or timestamp (default: timestamp descending — newest first), toggled by clicking a column
  header, ascending/descending indicated with `▲`/`▼`. **No write path, no form, no aggregation** —
  every displayed value is either a raw `call_log` column or a single `->>'key'` extraction already
  proven safe by `sql/dashboard_latest_call_view.sql`'s identical three-field extraction (`price`
  rendered as the stored text, not recomputed; `parse_status`/`confidence` rendered verbatim). Reuses
  `call_log`'s existing `anon_read_call_log` policy (`to anon, authenticated`) — zero new SQL.
- **New `admin-portal/components/KillSwitchToggle.tsx`** — isolated component (own file, not folded
  into `AuthGuard.tsx`, since it has its own load/toggle/error state distinct from auth). On mount,
  reads `kill_switch_state.paused` (`.from("kill_switch_state").select("paused").eq("id",
  true).single()` — readable only because `admin_read_kill_switch` now grants `authenticated`+
  `is_admin()` SELECT). Toggle button calls `supabase.rpc("set_kill_switch", { p_paused: !paused,
  p_source: "admin-portal" })`, then reloads state from the table (not an optimistic flip) so the
  displayed value always reflects what the database actually holds. Shows `loading…` / an
  `error-message` / a `PAUSED`/`RUNNING` badge + `Pause`/`Resume` button. `p_source: "admin-portal"`
  is a literal string constant matching the design's exact contract text (`docs/design/admin-portal.md`
  §16.6), not a config value — it identifies *this UI*, the same way `'sql-direct'` identifies the SQL
  editor path; neither is a tunable.
- **`admin-portal/components/AuthGuard.tsx`** — added `<a href="/track-record">Track record</a>` to
  the nav (alongside Watchlist/Holdings/Tunables) and `<KillSwitchToggle />` inside `app-header-user`
  next to the signed-in email, so it renders on every authenticated route via the one shared header,
  matching the design's "surfaced on a shared authenticated layout/header, not a standalone page" text
  and `layout.tsx`'s own existing docstring ("the future kill-switch toggle in INC-7").
- **`admin-portal/app/globals.css`** — added `.kill-switch`, `.kill-switch-badge`,
  `.kill-switch-badge.paused`, `.kill-switch-badge.running` (small badge, reusing the existing
  `--error` variable for paused and a new `--ok` variable, defined in both the light and dark
  `:root` blocks alongside the existing four, for running) — no new layout primitives invented beyond
  what `.app-header`/`.app-header-user` already establish.

## How to run locally

```
python3 -m pytest -q --tb=short                                        # Python suite (unchanged by this increment)
cd admin-portal && npm run build && npm run lint                       # portal build + lint
node --experimental-strip-types --test tests/admin_portal/*.test.ts    # portal test suite (unchanged by this increment)
```
No portal env vars changed — same `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` as
INC-5/6. Once `sql/kill_switch_portal_grant.sql` is applied live, `/track-record` and the header
toggle become fully functional for the allowlisted admin account.

## Full regression results (AC4)

- `python3 -m pytest -q --tb=short` → **201 passed, 0 failed** (identical to the pre-increment
  baseline — this increment touches no Python file).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **40 passed, 0 failed**
  (identical to baseline — no existing test file touched; `tests/` is qa's owned artifact, per
  `CLAUDE.md`, and no new test file was added here either).
- `cd admin-portal && npm run build` → succeeds, all 9 routes compile (`/`, `/_not-found`,
  `/auth/callback`, `/holdings`, `/login`, `/tunables`, `/watchlist`, plus the two new routes
  `/track-record` — verified below), TypeScript check passes.
- `cd admin-portal && npm run lint` → zero errors/warnings.

## Acceptance criteria status (`docs/design/increment-plan.md` lines 286-300)

- **AC1** (read-only, paginated `call_log`/`latest_call_per_ticker`, no new aggregation/scoring) —
  **Self-verified PASS.** Code-review self-check: `track-record/page.tsx` contains no `reduce`, no
  win-rate/score computation, no cross-row math — every rendered field is a 1:1 column or a single
  `->>'key'` JSON extraction already proven by the existing `latest_call_per_ticker` view (same three
  fields: `parse_status`, `price`, `confidence`). Pagination (`.range()`) and sort (`.order()`) are the
  only query-shape logic; filters are `ilike`/`eq` predicates, not derived values. `npm run build`
  confirms the route compiles and is listed as a static/dynamic route.
- **AC2** (toggle shows live `paused` on load; flip calls `set_kill_switch(..., p_source:=
  'admin-portal')` and produces a `kill_switch_audit` row with `source='admin-portal'` and
  `actor`=admin email) — **Statically verified, live behavior deferred.** `KillSwitchToggle.tsx`'s
  RPC call literally passes `p_source: "admin-portal"`; `set_kill_switch`'s body (copied verbatim from
  the design) stamps `actor` from `auth.jwt() ->> 'email'` when present — the signed-in admin's email,
  by construction, same mechanism already proven live for `tunables_stamp_update`'s `updated_by`.
  **Cannot verify the live INSERT/UPDATE actually happens** without the migration applied + a real
  authenticated session (no Supabase MCP access this session).
- **AC3** (after pause-on via the portal, a subsequent dispatch makes no `pg_net` call) — **Deferred,
  needs live Supabase.** This is INC-3's own `dispatch_github_workflow` pause-check, unmodified by
  this increment (`operational-controls.md` §13.1) — this increment only adds a second caller
  (the portal) to the same `paused` flag INC-3 already gated dispatch on. No new logic to verify here
  beyond "the portal really does flip the same flag", covered by AC2's live-verification gap above.
- **AC4** (full INC-5/INC-6 regression) — **PASS**, see "Full regression results" above; additionally,
  `tests/admin_portal/static_source_checks.test.ts`'s AC6/AC7 checks (no secret-looking string, no
  dynamic `process.env[...]`, `admin_allowlist` zero-policy shape, `is_admin()` shape) all still pass
  unmodified, confirming this increment introduced no new secret exposure or auth-shape regression.

**Deferred — need live Supabase / GitHub Actions access I don't have this session (same constraint as
every prior increment's dev pass):**
- Applying `sql/kill_switch_portal_grant.sql` itself (orchestrator's job, same as every prior
  increment's SQL).
- AC2's live round-trip (RPC call → `kill_switch_state` row updated → `kill_switch_audit` row
  inserted with the right `source`/`actor`).
- AC3's live dispatch-suppression proof.
- The inline `data_snapshot->>'key'` PostgREST select-string syntax on `track-record/page.tsx` —
  standard, documented PostgREST JSON-column embedding, and the client library forwards the string
  unvalidated (confirmed by reading `@supabase/postgrest-js`'s source — it does no client-side parsing
  of the select string), so there's nothing more to self-verify locally; a live query is the only way
  to fully confirm it round-trips as expected.
- `admin_read_kill_switch`'s live RLS behavior (an authenticated non-admin should get zero rows from
  `kill_switch_state`; the allowlisted admin should get exactly the one singleton row) — same
  "cannot exercise real RLS without a live project + a real session" constraint as INC-5/INC-6.

## Known limitations

- Track-record pagination/sort/filter state resets to page 1 on every filter/sort change (no URL
  query-string sync) — acceptable for a single-admin operational tool, not a public-facing UX surface.
- No admin-portal-side automated test yet exercises `/track-record` or `KillSwitchToggle`'s
  fetch/RPC flow — `tests/admin_portal/` is qa's owned artifact (`CLAUDE.md`); this increment added no
  test file itself, consistent with INC-6's own handoff note on the same boundary.
- `sql/kill_switch_portal_grant.sql` is not applied to the live project — orchestrator applies it,
  same as INC-5/INC-6's SQL files.
