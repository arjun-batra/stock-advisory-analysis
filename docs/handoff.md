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

---

# Handoff — INC-8: Degraded-run visibility + delivery-confirmed alerting (NFR2, FR15, FR34;
DEEP-001+DEEP-002)

**Date:** 2026-07-30. Branch: `claude/big-guns-qv3kjt` (no `inc-8-<slug>` branch created — per this
session's explicit instruction, deviating from `CLAUDE.md`'s normal per-increment branching; two commit
checkpoints kept per the solo/low-stakes opt-in). Not merged to `main`, not tagged.

## Build plan (written before coding, per dev's updated workflow)

Read `docs/design/increment-plan.md`'s `### INC-8` section (Files/Depends-on/8 ACs),
`docs/design/components.md` §4.6 (alerting) + §4.8 (reliability/heartbeat), `docs/design/
data-and-flow.md` §6 (core-flow pseudocode with the new delivery-gated sequencing),
`docs/requirements.md` NFR2/FR15/FR34 + Decisions #31/#32, and `docs/review-log.md`'s DEEP-001/DEEP-002.
Design is unambiguous and self-contained — no deviation to flag. Approach: (1) `notify.py` —
`NtfyNotifier.push()` returns `True` only on a confirmed 2xx (`raise_for_status()` inside `try`), `False`
on any exception/non-2xx (new `[notify] ERROR push failed for {ticker}: ...` line, replacing the old
silent-print `[notify error]`); `DryRunNotifier.push()` returns `None` explicitly. (2) `state.py` —
`write_call_log()` gains an optional client-supplied `id` param (a `str(uuid.uuid4())` generated before
`push()`, per §4.6's ordering fix, so the same id feeds both the tap-through URL and the log row);
`process_ticker`'s change branch computes `delivered = notifier.push(...)`, writes
`alerted=(delivered is True)`, and only advances `verdict_state.current_verdict` when `delivered is not
False` (True or None/dry-run) — a real failure returns `"push-failed"` and leaves the crossing pending
for automatic retry next cycle; the pre-existing `parse_status in ("failed","api_error")` fail-safe guard
at the top of `process_ticker` (state.py, load-bearing #8) is untouched — INC-8 changes only whether
that outcome counts as degraded downstream, never the state-advance guard itself. `process_candidate`
gets the identical treatment (`"candidate-push-failed"` outcome), which automatically fixes
`recently_pushed_candidates()`'s dedup (Decision #32) since it already filters on `alerted=True` and
nothing else needed to change there. `build_position` is untouched (INC-10's file, not this one). (3)
`run_hourly.py`/`run_discovery.py` — one-line `degraded = ...` formula change each, adding
`outcomes["no-read"]` (+ `outcomes["push-failed"]` / `outcomes["candidate-push-failed"]`), exactly the
fix block components.md §4.8 specifies verbatim. (4) `pages/dashboard.html` — widened the verdict-pill
special-case from `parse_status === "no_data"` to `["no_data","failed","api_error"].includes(...)`;
`pages/detail.html` left untouched (it already special-cased `failed`/`api_error` — confirmed by reading
it, matching the design's "no change needed there" note). No SQL changes, no new config tunable (none
was needed or introduced). Contracts touched: `Notifier.push()`'s return type (documented above, both
implementations); `state.write_call_log()` gains one optional kwarg (backward-compatible — every
existing call site that doesn't pass `id` behaves identically, since Supabase's `gen_random_uuid()`
default still fires). Verify: full pytest suite + targeted scratch scripts per AC (below) + a JS-logic
extraction check for the dashboard pill, since no Python test can exercise `pages/*.html`.

## Files touched

- `scripts/notify.py` — `NtfyNotifier.push()` now returns `bool` (`raise_for_status()` inside `try`,
  distinct `[notify] ERROR push failed for {ticker}: ...` log line on failure); `DryRunNotifier.push()`
  now returns `None` explicitly (was implicit).
- `scripts/state.py` — `write_call_log()` gained an optional `id` kwarg; `process_ticker`'s change
  branch and `process_candidate`'s push branch both compute `delivered = notifier.push(...)` and gate
  `alerted`/state-advance on it (`"push-failed"` / `"candidate-push-failed"` new outcome labels). The
  `parse_status in ("failed","api_error")` fail-safe guard (state.py, the no-read branch near the top of
  `process_ticker`) is byte-for-byte unchanged. `build_position` not touched (INC-10's).
- `scripts/run_hourly.py` — `degraded` formula: `+ outcomes["no-read"] + outcomes["push-failed"]`.
- `scripts/run_discovery.py` — `degraded` formula: `+ outcomes["no-read"] +
  outcomes["candidate-push-failed"]`.
- `pages/dashboard.html` — verdict-pill special-case widened to
  `["no_data","failed","api_error"].includes(row.parse_status)`; confidence-pill guard left unchanged
  per the design's explicit note (confidence is already null on every fail-safe row).
- `pages/detail.html` — **zero changes** (confirmed via `git diff --stat`, empty output) — it already
  special-cased `failed`/`api_error` before this increment.

`git diff --name-only` against the pre-increment tree: exactly `pages/dashboard.html`,
`scripts/notify.py`, `scripts/run_discovery.py`, `scripts/run_hourly.py`, `scripts/state.py` — the five
files INC-8's design names, nothing else (AC8's diff-scope half).

## How to run / reproduce the verification

```
SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short          # full existing suite
```
Ad hoc AC verification (I do not own `tests/` — see "Test-suite impact" below for why permanent tests
weren't added here): three scratch scripts under this session's scratchpad directory (not part of the
repo, not committed) reused `tests/test_state.py`'s `FakeSupabase`/`_wl_row`/`_data`/`_ai` builders
directly against the real `state.py`/`notify.py`/`run_hourly.py`/`run_discovery.py` code:
1. A `ControllableNotifier` double whose `push()` return value is scripted per call (`False`/`True`/
   `None` in sequence) drove AC5 (fail-then-retry-succeeds), AC6 (dry-run advances state, no backlog
   dump on the following quiet check), and AC7 (undelivered/dry-run candidates excluded from
   `recently_pushed_candidates()`).
2. `notify.requests.post` monkeypatched to a 500-then-200 sequence and to a raising callable drove AC4
   (`NtfyNotifier.push()` returns `False`/`True` correctly, never raises, logs the new distinct line;
   `DryRunNotifier.push()` returns `None`).
3. `run_hourly.main()` / `run_discovery.main()` driven end-to-end (same wiring pattern as
   `tests/test_run_orchestration.py`'s `wire_main`/`wire_discovery` fixtures) with every ticker/candidate
   forced to `parse_status="failed"`/`"api_error"` drove AC1 (heartbeat `"partial"`, all-failed and
   mixed no-read+quiet batches, both entry points) — reproducing DEEP-001's exact scenario and
   confirming it would have read `"ok"` against the pre-fix formula (`git show HEAD:scripts/run_hourly.py
   | grep 'degraded ='` on the pre-fix commit shows `outcomes["skip"] + outcomes["error"]` only).
4. A standalone Node script extracted the exact widened conditional from the edited
   `pages/dashboard.html` and rendered it against `parse_status` in `{"failed","api_error","no_data",
   "ok"}`, confirming the first three render the "no data" pill and a genuine `"ok"` Hold still renders
   the real Hold pill (AC3).

## Acceptance criteria — self-verification

1. **PASS (self-verified via scratch script #3 above).** All-`no-read` batch on both `run_hourly.main()`
   and `run_discovery.main()` writes `run_heartbeat.status == "partial"`; a mixed no-read+quiet batch on
   `run_hourly` does too. **qa must add the permanent regression test** (`tests/test_run_orchestration.py`
   pattern) — this is explicitly named in the increment as a qa test, not a dev one.
2. **PASS — dev-self-verifiable by grep, done directly:**
   `grep -n 'outcomes\["no-read"\]' scripts/run_hourly.py scripts/run_discovery.py` and
   `grep -n 'outcomes\["push-failed"\]\|outcomes\["candidate-push-failed"\]' scripts/run_hourly.py
   scripts/run_discovery.py` both return a match in each file's `degraded = ...` line.
3. **PASS — dev-self-verifiable by grep + scratch script #4.** `pages/dashboard.html`'s verdict-pill
   condition is `["no_data","failed","api_error"].includes(row.parse_status)`; `pages/detail.html` has
   zero diff. The qa "manual/browser check" half of this AC (a real synthetic `call_log` row rendered in
   an actual browser) is qa's to run — I verified the exact logic in isolation (Node), not a rendered
   DOM/browser session.
4. **PASS (self-verified via scratch script #2).** `NtfyNotifier.push()` returns `True` only on a
   response where `raise_for_status()` doesn't raise; returns `False` (never raises) on any `requests`
   exception or non-2xx, logging `[notify] ERROR push failed for {ticker}: ...`.
   `DryRunNotifier.push()` returns `None` unconditionally. **qa must add the permanent test** (mock
   `requests.post` to return a 500, assert `push()` returns `False` without raising) — named explicitly
   as a qa test in the AC.
5. **PASS (self-verified via scratch script #1).** Simulated push failure: `call_log.alerted == False`,
   `verdict_state.current_verdict` unchanged (still the OLD verdict), and a second `process_ticker` call
   with the same new AI verdict fires `notifier.push` again for the same crossing, then succeeds and
   advances state. All three asserted in one flow, matching the AC's own framing.
6. **PASS (self-verified via scratch script #1).** Simulated dry run (`delivered=None`):
   `call_log.alerted == False` but `verdict_state.current_verdict` DOES advance; confirmed no backlog
   dump — the immediately-following same-verdict check comes back `"quiet"`, not a second alert.
7. **PASS (self-verified via scratch script #1).** Discovery candidate pushed via dry run
   (`delivered=None`) or a failed real push (`delivered=False`) both write `alerted=False`, and
   `state.recently_pushed_candidates()` excludes the ticker in both cases (already-correct filter,
   `alerted=True`, now fed the right value).
8. **PARTIAL — see "Test-suite impact" below.** `git diff` confirms the diff is scoped to exactly the
   five named files (verified above). The "full existing test suite passes" half is **not clean**: 8 of
   207 previously-passing tests now fail. This is not a regression from an unrelated bug — every one of
   the 8 failures is a direct, mechanical consequence of the FR34/DEEP-002 contract change these same
   tests encode the *old* (buggy) behavior of. Full accounting below.

## Test-suite impact (read before treating this as a clean handoff)

**Full suite: `199 passed, 8 failed`** (was `207 passed, 0 failed` immediately before this increment's
edits — I ran the baseline first and confirmed it). All 8 failures are in files I do not own
(`tests/test_notify.py`, `tests/test_state.py` — `CLAUDE.md`'s dev row: "never touches: requirements,
design, tests") and all 8 fail for the same reason: they assert the pre-FR34 contract this increment is
built to fix.

- **`tests/test_notify.py::test_ntfy_notifier_swallows_network_errors_without_crashing`** — asserts the
  old log-line substring `"[notify error]"`. AC4 explicitly requires the new, distinct
  `[notify] ERROR push failed for {ticker}: ...` line; the old and new strings cannot both be true. One
  line to fix (update the asserted substring).
- **`tests/test_state.py::test_any_verdict_change_fires_immediate_alert`** (6 parametrized cases) and
  **`test_discovery_buy_pushes`** — both use `FakeNotifier.push()`, which has no `return` statement
  (implicitly returns `None`). Under the *old* contract `push()`'s return value was never read, so this
  didn't matter; under the *new* contract (this increment), `None` means "dry run — deliberately not
  attempted" (§4.6), so `alerted` is correctly written `False` and these tests' `assert ... is True`
  fails. This is not a bug in my implementation — it is DEEP-002's own finding, almost verbatim: these
  specific assertions are what "`call_log.alerted = true` means we intended to push, not delivered"
  looked like as a green test. The fix is one line in the shared fixture (`FakeNotifier.push` should
  `return True` to represent a successful real send, the semantic these tests actually intend to
  exercise), not a design or behavior question.

**Why I did not fix these myself:** `CLAUDE.md`'s agent table is explicit that `tests/` is qa's owned
artifact and dev never touches it; editing `tests/test_state.py`/`tests/test_notify.py` here would be
scope creep into another agent's file, independent of how small the fix is. I flagged this rather than
silently declaring AC8 fully PASS, per dev rule #3 ("if the design is wrong or ambiguous, stop and flag
it — never silently deviate") — AC8's "full existing test suite passes" and the ownership boundary are
in tension whenever an increment changes a contract old tests encode, and I'm surfacing that tension
explicitly rather than picking a side unilaterally.

**Recommended qa fix (not applied — for qa's next pass, not a design decision needed from tech-lead):**
add a `returns` parameter to `FakeNotifier.__init__` (default `True`, matching "an ordinary successful
push" as the common case these pre-existing tests intend), and update the one `[notify error]` ->
`[notify] ERROR push failed for` substring in `test_notify.py`. Both are mechanical, no design judgment
required — the semantics of what each test is *supposed* to exercise are unchanged by this increment,
only the contract used to express "the push succeeded" changed shape.

**TypeScript suite:** unaffected — zero `admin-portal/` files touched by this increment (63 baseline
stands; not re-run since nothing in scope could affect it).

## Known limitations

- The 8 test failures above are a known, accounted-for consequence of this increment's own scope, not a
  hidden regression — see "Test-suite impact." qa's phase (b) pass for INC-8 needs to both (a) apply the
  mechanical fixture fix above so the pre-existing suite reflects the new contract, and (b) write the
  new permanent tests the increment's ACs name explicitly (AC1's all-no-read/mixed heartbeat test, AC4's
  mocked-500 `push()` test, AC5/AC6/AC7's delivery/dry-run/retry flows) — my scratch scripts (not
  committed, session-scratchpad only) demonstrate exactly what each of those should assert.
- `pages/dashboard.html`'s AC3 manual/browser check (a real synthetic `call_log` row rendered and
  visually confirmed) was not run in an actual browser this session — verified the exact JS conditional
  in isolation instead (Node). qa should do the browser pass named in the AC.
- No config-schema change, no new tunable, no SQL change — matches the design's explicit "no config
  schema change" / "no SQL changes" statements; nothing to flag there.

---

# Handoff — INC-9: Parse-attribution contract + closed-market structural check (FR17; DEEP-003+DEEP-004)

## Build plan (written before coding)

Read `docs/design/increment-plan.md`'s INC-9 section, `docs/design/components.md` §4.2 (ingestion) +
§4.4/§4.4a (parse & retry, the new positional-fallback attribution contract), `docs/design/
non-functional-ops.md` §7.5, `requirements.md` FR17 + Decisions #33/#34, and `docs/review-log.md`'s
DEEP-003/DEEP-004 entries (file:line citations). Both fixes are structural, self-contained, and scoped to
exactly two files — no config-schema change, no SQL, no new tunable, matching the increment's own "no
config-schema change" statement.

- **DEEP-003 (`scripts/ai_judge.py`, `_parse_batch`):** narrow the positional fallback so `arr[i]` is
  accepted only when its own `ticker` field is absent (legitimate — model forgot the label, request
  order preserved) or normalizes (new `_normalize_ticker` helper — case-fold, strip `.TO`/`.NS`) to the
  ticker being resolved. Anything else (a genuinely different ticker at that index — the misaligned-array
  case DEEP-003's evidence describes) falls through to `_FAIL_SAFE_PARSE`. Add the
  `positional fallback used for {t}` log line (fires only on the legitimate path) and a duplicate-ticker
  log line in the `by_ticker` dict-build loop (was a silent last-wins). Correct the module docstring's
  unqualified "can only ever MISS a signal" claim to name this mechanism.
- **DEEP-004 (`scripts/ingest.py`, `get_market_data`):** move the `_session_state()` call earlier and
  insert the stale-bar/closed-market structural check immediately after `h` is confirmed non-empty and
  before any of `close`/`price`/`pct_change_*`/`volume_vs_avg` are computed — per-market tz via
  `config.MARKET_TZ`/`config.NSE_MARKET_TZ`, compare `h.index[-1].date()` to today's market-local date;
  if the session reads live but the last bar predates today, append a note and `return out` with
  `has_price` still `False` (same skip-with-log path as any other no-data day). The later, now-redundant
  `_session_state()` call is removed — `live`/`frac` from the earlier call are reused.

**Verification plan:** run the full existing suite (structural check must not disturb the pre-existing
`_session_state`/pro-rating tests, all of which exercise wall-clock-only scenarios where the check is a
no-op); grep-verify AC2 (`positional fallback used for`) and AC5 (`last_bar_date` precedes the pro-rating
math, one function, manual read); write small scratch scripts (session-scratchpad only, not committed)
exercising both DEEP-003 scenarios (misattribution-must-fail-safe, legitimate-fallback-must-still-work)
and both DEEP-004 scenarios (stale bar during nominal live hours -> `has_price=False` + reason note;
same-day bar -> unaffected) against a monkeypatched `ingest.datetime` — the same seam a qa test would
use, since `_session_state` and the new check share the same imported `datetime` name.

No deviation from design — proceeded without flagging tech-lead.

## Files changed

- `scripts/ai_judge.py` — module docstring (names the positional-fallback mechanism instead of asserting
  an unqualified claim); new `_normalize_ticker` helper; `_parse_batch` rewritten per §4.4a's contract
  (narrowed fallback acceptance test, `used_fallback` log line, duplicate-ticker log line in the
  `by_ticker` build loop). No other function touched.
- `scripts/ingest.py` — `get_market_data` only: the stale-bar structural check inserted right after the
  empty-history guard, before any price/volume math; the later duplicate `_session_state()` call removed
  in favor of reusing the earlier result. `get_price_only`/`_session_state`/`_market_for`/everything else
  untouched.

## How to run it

`python3 -m pytest -q --tb=short` from the repo root (no new env vars, no config changes). To exercise
either fix directly: `python3 -c "import ai_judge; ai_judge._parse_batch(raw_json_str, tickers, model)"`
or `ingest.get_market_data(ticker)` with `yf.Ticker` monkeypatched (see `tests/test_ingest.py`'s
`FakeYFTickerNoInfoNoNews` pattern) — freeze `ingest.datetime` (a fake `datetime` subclass with an
overridden `now(tz)` classmethod, assigned to `ingest.datetime`) to control "today" for the stale-bar
scenario, since `get_market_data` takes no explicit clock parameter and neither does `_session_state`'s
default path.

## Acceptance-criteria self-verification

1. **PASS.** Scratch script (session-scratchpad, not committed): request `[A,B,C]`, model response
   `[A,X,B]` (drops C, hallucinates X) -> `C` resolves `parse_status="failed"` (not B's verdict/rationale
   under `"ok"`); `B` itself still resolves normally via its own direct label. Second scratch scenario: a
   same-order response where the middle object has no `ticker` label at all -> that ticker still resolves
   `parse_status="ok"` with the unlabeled object's own verdict/rationale (the legitimate fallback case).
   Both confirmed by direct assertion, not just log inspection.
2. **PASS.** `grep -n "positional fallback used for" scripts/ai_judge.py` returns the log line; the
   scratch run's captured stdout shows it fires exactly once, only for the legitimate-fallback ticker —
   zero occurrences in the misattribution scenario (correctly suppressed since that candidate fails the
   corroboration check and is never accepted).
3. **PASS.** Module docstring no longer states the MISS-only claim unqualified — it now names
   `_parse_batch`'s narrowed positional-fallback acceptance test as the mechanism that makes it true
   (manual read, top of `scripts/ai_judge.py`).
4. **PASS.** Scratch script with a monkeypatched `ingest.datetime`: history ending 3 business days before
   the frozen "today" (2026-07-27 vs. frozen 2026-07-30), frozen clock at 12:45 ET (nominal live session)
   -> `has_price=False` and a note containing "market appears closed today" naming both dates. Second
   scenario, same frozen clock, history ending on the frozen "today" itself -> unaffected: `has_price=True`,
   `session_live=True`, normal pro-rating path reached.
5. **PASS.** `grep -n "last_bar_date" scripts/ingest.py` — both occurrences (the assignment and the
   comparison) are inside `get_market_data`, positioned directly after the empty-history guard and before
   `close = h["Close"].dropna()` / any of `pct_change_1d`/`pct_change_5d`/`pct_change_20d`/`volume_vs_avg`
   — confirmed by direct read, not merely a late-added early-return guard bolted after the math.
6. **PASS.** `python3 -m pytest -q --tb=short` -> **229 passed, 0 failed** — identical to the pre-INC-9
   baseline (229 Python / 63 TypeScript, confirmed by the user at `f66d693`); TypeScript suite untouched
   (zero `admin-portal/` files in scope, not re-run — nothing in this increment's diff could affect it).
   `git diff --name-only` against the pre-INC-9 commit shows exactly `scripts/ai_judge.py` and
   `scripts/ingest.py` changed (plus tech-lead's own in-flight `docs/design.md`/
   `docs/design/increment-plan.md` status-marker edits, which are not this increment's files and were not
   touched by dev).

**No pre-existing test needed changing or broke** — unlike INC-8, no test in `tests/` encoded the old
positional-fallback or stale-bar-blind behavior as an assertion, so there is no test-suite tension to flag
here; the full suite was green before and after with zero edits to `tests/`.

## Known limitations / things the design didn't fully anticipate

- **DEEP-004's accepted edge case is unchanged and still applies**: in the first seconds/minutes after a
  genuinely open session's start, if yfinance hasn't posted today's intraday bar yet, this check could
  misfire and skip a ticker for one cycle on a normal trading day (self-corrects 30 min later next cycle).
  This is documented in `components.md` §4.2 as an accepted MISS-direction risk, not something this
  increment needed to mitigate further.
- `h.index[-1].date()` is taken at face value as "yfinance's own bar date, exchange-local" per the design
  snippet — no explicit timezone conversion is applied to the index before calling `.date()`. This matches
  every existing fixture pattern in `tests/test_ingest.py` (naive `pd.date_range` indices) and the design's
  own comment; if a live yfinance response's index were ever UTC-normalized rather than exchange-local,
  this comparison would need revisiting, but that's a pre-existing assumption this increment inherits, not
  a new one it introduces.
- One qa-facing note for the next phase: AC1's "second test" (legitimate fallback with a same-order,
  ticker-label-missing response) and AC4's "second test" (same-day bar unaffected) are both explicitly
  the *regression* half of each AC — worth qa keeping both the failure-mode and the working-mode assertion
  in the same test file so a future change to either check is caught from both directions, the same
  pattern INC-8's design called out for its own dual-assertion ACs.
- `docs/design/increment-plan.md` and `docs/design.md` currently carry uncommitted, in-flight edits from
  tech-lead (status-marker updates reflecting INC-8's Pass-24 clearance) that predate this session's INC-9
  work and are outside dev's ownership (`CLAUDE.md`'s agent table: tech-lead owns `docs/design.md`) — noted
  here only so INC-9's own commit doesn't get blamed for unrelated doc diffs already present in the tree.

---

## BUG-005 fix (fix cycle 1 of 3) — `_normalize_ticker`'s cross-market collision in `_parse_batch`

### Build plan (written before coding)

Read `docs/test-report.md`'s BUG-005 entry (repro, expected/actual, qa's suggested-not-prescribed fix),
`docs/design/components.md` §4.4a's positional-fallback contract (the exact pseudocode I implemented
against in INC-9), and `docs/review-log.md`'s DEEP-003 entry (same fabrication class, adjacent case). Root
cause: `_normalize_ticker` strips `.TO`/`.NS` before comparing, so two *different* real watchlist tickers
sharing a base symbol across markets (`ABC.TO`/`ABC.NS`) normalize identically, letting the positional
fallback's corroboration check treat an already-consumed `ABC.TO` object as if it corroborates `ABC.NS`.
**Fix shape:** a normalized-only match (candidate has an explicit `ticker` field that doesn't exactly equal
the ticker being resolved but normalizes to it) is now accepted only when that normalized form is
*unambiguous* — exactly one of the batch's requested tickers normalizes to it (`collections.Counter` over
`tickers`, computed once per `_parse_batch` call). The no-ticker-field ("model forgot the label") branch is
untouched — it never depended on normalization to identify a match, so it can't be ambiguous the same way.
Considered qa's suggested alternative (require an *exact* match whenever the candidate carries an explicit
`ticker` field, reserving normalization for the no-field case only) but rejected it: §4.4a's own contract
and this task's stated constraint both require a bare `"ABC"` reply to still resolve a request for
`"ABC.TO"` when unambiguous — qa's alternative would reject that legitimate case outright, not just the
collision. The unambiguity-guard shape preserves that legitimate normalized match while closing the
collision. **File:** `scripts/ai_judge.py` only (`_parse_batch`, `_normalize_ticker` untouched, module
docstring updated to state the refined invariant). Verify: `tests/test_ai_judge.py`'s three
`_parse_batch`-scoped tests (BUG-005's repro test, the misattribution test, the legitimate-fallback test)
plus the full suite; manual smoke of the collision repro, the no-label legitimate case, and a bare-ticker
normalized match in a single-ticker (unambiguous) batch.

### Departure from §4.4a — flagged, not silently applied

**Yes, this fix extends §4.4a's literal contract.** §4.4a's pseudocode (`components.md` lines ~236–251)
accepts a normalized match unconditionally: "its own `ticker` field is absent, OR its own ticker normalizes
... to the one we're resolving." It does not mention batch-wide ambiguity at all — that gap is exactly
BUG-005. My fix adds a new condition (`normalized_counts[t_norm] == 1`) that §4.4a's text does not specify.
This is a correctness fix to a documented gap, not a reinterpretation of what §4.4a already says — but
since it changes the accept/reject boundary of the corroboration check, tech-lead should record the
unambiguity guard in `components.md` §4.4a (same pattern the test-report's BUG-005 entry already names:
"tech-lead recording the corroboration-check decision in `components.md` §4.4a, same pattern as the
original DEEP-003 fix"). I have not edited the design doc.

### Files changed

- `scripts/ai_judge.py` — `_parse_batch`: added a `Counter` of normalized forms over the batch's requested
  `tickers`; the normalized-match branch of the positional-fallback check now also requires
  `normalized_counts[_normalize_ticker(t)] == 1`. Module docstring and `_parse_batch`'s own docstring
  updated to state the refined invariant (BUG-005 closes the residual gap DEEP-003's narrowing left open).
  No other function touched; `_normalize_ticker` itself is unchanged. New import: `from collections import
  Counter`.

### How to run it

`SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short tests/test_ai_judge.py -k parse_batch` for the
targeted 3 tests, or the full suite: `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short`.

### Full regression + smoke test

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **237 passed, 0 failed** (236 baseline + the
  1 previously-failing BUG-005 test now passing; matches the task's stated success bar exactly).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **63 passed, 0 failed**, unaffected
  (zero `admin-portal/` files in scope).
- Manual smoke via `ai_judge._parse_batch` directly, three scenarios:
  1. BUG-005 repro (`["ABC.TO", "ABC.NS"]`, response `[{no ticker, verdict/rationale A}, {"ticker":
     "ABC.TO", verdict/rationale B}]`) → `ABC.TO` resolves `parse_status="ok"`/`rationale="abc-to-reason"`
     via its own direct label; `ABC.NS` now resolves `parse_status="failed"` (fail-safe), no longer
     inherits `ABC.TO`'s rationale.
  2. Legitimate no-label fallback (INC-9's own committed scenario, `["AAPL","MSFT","TSLA"]`, MSFT's object
     unlabeled) → `MSFT` still resolves `parse_status="ok"` with its own object's verdict/rationale, log
     line still fires — unaffected by this fix, confirming the constraint against regressing it holds.
  3. Legitimate bare-ticker normalized match in an *unambiguous* single-ticker batch (`["ABC.TO"]`,
     response `[{"ticker": "ABC", ...}]`) → still resolves `parse_status="ok"` via the normalized match,
     confirming the "model answers ABC when asked about ABC.TO" case §4.4a exists to serve is preserved,
     not regressed by the new ambiguity guard.

### Known limitations

- The ambiguity check is scoped to the tickers requested *in the current batch* only, per the task's
  framing ("unambiguous within the batch being parsed"). A three-way collision (e.g. a batch somehow
  requesting the same base symbol on all three markets) is likewise caught, since `Counter` counts however
  many tickers share a normalized form, not just two.
- Not in scope for this fix cycle (unchanged): `by_ticker`'s existing duplicate-ticker log line, the
  misaligned-array (DEEP-003 original) check, and `ingest.py` (BUG-005 is `ai_judge.py`-only per the task's
  scope).

---

## BUG-006 fix (fix cycle 2 of 3) — duplicate-requested-ticker miscounted as ambiguity in `_parse_batch`

### Build plan (written before coding)

Read `docs/test-report.md`'s "Open bugs" BUG-006 entry (repro, root cause, explicit "not in scope" note on
the pre-existing overwrite semantics), `docs/design/components.md` §4.4a (now updated by tech-lead with the
BUG-005 unambiguity guard's pseudocode and stated intent — "exactly one of the tickers requested this call
normalizes to that form"), and my own fix-cycle-1 handoff entry above. Root cause per qa: `normalized_counts
= Counter(_normalize_ticker(x) for x in tickers)` counts raw occurrences of the requested `tickers` list, so
the SAME ticker string requested twice (not two distinct tickers colliding) inflates its own count to 2 and
the guard rejects it as "ambiguous" — then, because `out` is keyed by ticker string, that wrongly-rejected
fail-safe overwrites the first occurrence's already-good entry. **Fix shape:** count *distinct* requested
tickers (dedup by uppercased string) before building the `Counter`, so a duplicate request no longer counts
against itself while a genuine cross-ticker collision (`ABC.TO`/`ABC.NS`, two distinct strings) still counts
correctly. Read §4.4a's prose closely first ("exactly one of the tickers requested this call normalizes to
that form") — it reads naturally as "one of the distinct tickers", consistent with the fix; see the
departure note below for why I judged this a counting correction, not a contract change. **Also:** per the
task's explicit prompt to consider the overwrite path independently, added a narrow guard so a later
fail-safe result never overwrites an already-resolved "ok" for the same ticker key — reachable even with
correct counting whenever a duplicate request's two occurrences land on genuinely different outcomes (one
resolves, the other doesn't). Did **not** change `out`'s ticker-string keying/last-write-wins semantics more
broadly (e.g. ok-over-ok) — qa's bug report explicitly scopes that out ("not itself being re-litigated
here"), and redesigning the return shape would ripple into every caller of `_parse_batch`, well past this
bug's scope. **File:** `scripts/ai_judge.py` only (`_parse_batch`'s `Counter` construction and the
per-ticker write to `out`; `_normalize_ticker` untouched). Verify: the BUG-006 repro test (qa's, already
committed), the existing BUG-005/DEEP-003 `_parse_batch` tests (guard against regressing the collision case
the counting fix must still catch), full suite, plus manual smoke of three scenarios (BUG-006 repro,
ok-then-fail-safe duplicate, genuine cross-market collision still fails safe).

### Does this change §4.4a again? No — flagged for confirmation, not silently assumed

This is a counting-mechanism correction, not a change to what §4.4a specifies. §4.4a's stated contract is
"a normalized-only match is accepted only when it is unambiguous within the batch: exactly one of the
tickers requested this call normalizes to that form" — the *intent*, restated repeatedly in §4.4a's own "why
this is non-obvious" and BUG-005-refinement prose, is to catch **distinct, real tickers** colliding on a
shared normalized base (its own worked example is always `ABC.TO`/`ABC.NS`, two different companies). A
ticker requested twice is not a second thing to be confused with — it's the same thing asked about twice;
there is nothing to disambiguate. The literal pseudocode (`Counter(...) for x in tickers`, no dedup) simply
didn't anticipate that a batch could contain a literal duplicate string, which is exactly BUG-006's finding.
Correcting the count to operate over distinct requested tickers makes the code match the contract's own
stated purpose; it doesn't add, remove, or loosen what counts as "ambiguous" between two different real
tickers — verified with the smoke-test scenario 3 below, the genuine `ABC.TO`/`ABC.NS` collision still fails
safe unchanged. The overwrite guard (ok is never replaced by a later fail-safe for the same key) is likewise
not a §4.4a change — §4.4a governs when a normalized match is *accepted*, not what happens to `out`'s
dict-keyed storage after a result is already accepted; that's a narrower, local safety net one layer down.
**No design doc edit made or needed on my read — flagging per the task's instruction so tech-lead/orchestrator
can confirm rather than silently trusting my judgment on it.**

### Files changed

- `scripts/ai_judge.py` — `_parse_batch`:
  - `normalized_counts` now built from `{x.upper() for x in tickers}` (dedup) rather than the raw `tickers`
    list, so a ticker requested twice counts once toward its own normalized form, not twice.
  - The per-ticker write into `out` now goes through a local `result` variable; before writing, if `result`
    is a fail-safe (`parse_status == "failed"`) and `out` already holds an `"ok"` entry for that same ticker
    key, the write is skipped (logged, not silent) instead of overwriting the earlier good verdict.
    Otherwise last-write-wins is unchanged (matches qa's "not in scope" note on the pre-existing overwrite
    behavior).
  - Docstring (`_parse_batch`'s own) updated to state both refinements and why. No other function touched.

### How to run it

`SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short tests/test_ai_judge.py -k parse_batch` for the
targeted tests, or the full suite: `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short`.

### Full regression + smoke test

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **241 passed, 0 failed** (240 baseline + the
  1 previously-failing BUG-006 test now passing; matches the task's stated success bar exactly).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **63 passed, 0 failed**, unaffected
  (zero `admin-portal/`-relevant files touched).
- Manual smoke via `ai_judge._parse_batch` directly, three scenarios:
  1. BUG-006 repro (`["AAPL","ABC.TO","ABC.TO"]`, second `ABC.TO` occurrence answered with bare `"ABC"`) →
     `AAPL` resolves `ok`; `ABC.TO` resolves `ok` (both occurrences now legitimately reachable — the
     surviving entry is the second occurrence's, per unchanged last-write-wins for ok-over-ok, which is
     within scope of what this fix guarantees: qa's assertion is `parse_status == "ok"`, not which of the
     two legitimate rationales survives).
  2. Overwrite-guard scenario (`["ABC.TO","ABC.TO"]`, first occurrence resolves `ok` via the no-label
     fallback, second occurrence's candidate collides with an unrelated ticker and fails safe) → the guard
     fires (`[ai_judge] duplicate requested ticker 'ABC.TO' (index 1): keeping the earlier resolved
     verdict...`), `out["ABC.TO"]` stays the first occurrence's `ok` result, not clobbered by the later
     fail-safe.
  3. Genuine cross-market collision, unchanged (`["ABC.TO","ABC.NS"]`, one unlabeled response object) →
     both still fail safe (`parse_status="failed"` for both), confirming the counting fix didn't loosen
     BUG-005's own guard.

### Known limitations

- The overwrite guard added here only protects the specific "ok, then later fail-safe, same ticker key"
  direction. It does not change what happens when a duplicate request resolves to two different legitimate
  ("ok") answers at each occurrence — last-write-wins still applies there (scenario 1 above), unchanged
  from pre-BUG-005 behavior and explicitly out of scope per qa's bug report. If a future increment wants
  deterministic behavior for that case (e.g. always keep the first, or merge/flag both), that's a design
  decision (`out`'s ticker-keyed return shape would need to change, rippling to callers) — not addressed
  here.
- Duplicate ticker requests remain proven-unreachable for `watchlist.ticker` (DB primary key) but reachable
  in principle from discovery-candidate batches, per qa's own severity note — unchanged by this fix, which
  only changes how a reachable duplicate is handled once it occurs.

---

# Handoff — INC-10: Tunables write-time validation + holdings-currency derivation (FR30, FR11, FR29;
DEEP-005+DEEP-006)

**Date:** 2026-07-30. Branch: `claude/big-guns-qv3kjt` (continuing this session's branch per explicit
instruction — no new branch, no merge, no tag). Not merged to `main`.

## Build plan (written before coding)

Read `docs/design/increment-plan.md`'s `### INC-10` section (Files/Depends-on/8 ACs),
`docs/design/admin-portal-tunables.md` §16.4's "FIX ROUND (DEEP-005, INC-10)" subsection,
`docs/design/admin-portal.md` §16.3's "FIX ROUND (DEEP-006, INC-10)" subsection,
`docs/design/non-functional-ops.md` §7.3 (currency enforcement) and §8 (file-level tags naming the two
new SQL files), `docs/requirements.md` FR30/FR11/FR29 + Decisions #34/#35, and `docs/review-log.md`'s
DEEP-005/DEEP-006 entries (file:line evidence). Both fixes are fully specified by the design (exact
SQL/trigger blocks given verbatim in admin-portal-tunables.md/admin-portal.md) — no design ambiguity to
flag.

**Approach:**
- **DEEP-005 (tunables):** mirror `scripts/config.py`'s `_TUNABLE_CASTS` ten-key contract in two
  independent places. `admin-portal/lib/validation.ts`'s `validateTunableValue` becomes key-aware
  (`(key, value) -> string[]`, was `(value) -> string[]`) with one rule per curated key (5 float keys, 2
  int keys, `ALERTS_ENABLED` true/false-only, `GEMINI_MODEL` non-blank, `GEMINI_MODEL_BACKUP` blank
  allowed — the shipped INC-6 version incorrectly required non-blank for every key, blocking the
  documented "leave empty to disable the fallback" state). New `sql/tunables_validate_trigger.sql`
  enforces the identical contract in a `BEFORE UPDATE` trigger, so a direct SQL edit is caught the same
  way. `admin-portal/app/(app)/tunables/page.tsx`: `ALERTS_ENABLED` renders as a `true`/`false` select,
  not free text (structurally prevents the typo class, not just catches it). Effective-value visibility
  (the AND-gate compounding gap): per the design, no new portal widget — instead the `ALERTS_ENABLED`
  seed row's `description` is corrected to state the AND-gate plainly (`sql/admin_portal_tunables.sql`,
  both the INSERT text for a fresh deploy and a new idempotent `UPDATE` to sync the already-live row),
  and INC-8's `call_log.alerted` (already shipped, already visible on the INC-7 track-record view) is
  the reused live signal — no new schema/UI built for this, per the design's explicit "reuse over
  building a second indicator" call.
- **DEEP-006 (holdings currency):** new `sql/holdings_currency_derivation.sql` — a `BEFORE INSERT OR
  UPDATE` trigger on `holdings` that derives `currency` from `watchlist.market` via the existing FK and
  **unconditionally overwrites** whatever was submitted (portal, direct SQL, or any future caller
  alike). `admin-portal/lib/validation.ts`: `HoldingsInput`/`validateHoldingsRow` drop `currency`
  entirely; new `MARKET_CURRENCY` display-only map. `admin-portal/app/(app)/holdings/page.tsx`: currency
  `<select>` removed from both the add form and the edit row, replaced with a read-only derived label
  sourced from the selected ticker's `watchlist.market` (fetched alongside the ticker list); no
  `currency` field in any insert/update payload. `scripts/state.py`'s `build_position` (explicitly
  reserved for this increment when INC-8 was told to leave it alone) gets the second, independent
  defense-in-depth layer: if `holding["currency"]` disagrees with the ticker's own independently-fetched
  `data["fundamentals"]["currency"]`, `pl_pct` is suppressed (`None`) with a logged warning instead of
  computed from mismatched currencies, per FR11. A missing (not merely differing) fundamentals currency
  is treated as "unknown," not "disagrees" — `pl_pct` still computes in that case, unchanged from
  pre-INC-10 behavior (matches the two pre-existing `build_position` tests, which pass no `fundamentals`
  key at all).

**Contracts touched:** `validateTunableValue`'s signature and `HoldingsInput`/`validateHoldingsRow`'s
shape both change — see "Deviation from the Files list" below for the direct consequence on two
pre-existing test files. `build_position`'s return shape is unchanged (`shares`/`cost_basis`/`currency`/
`pl_pct`), only `pl_pct`'s computation gains a new suppression branch.

**Verify:** full Python + TypeScript suites, `npm run build`, plus (since neither SQL file can be applied
to the live project this session) a local scratch Postgres instance to exercise both new triggers'
actual behavior end-to-end — see "How I verified the SQL" below.

## What changed and why

DEEP-005: the tunables editor validated only non-emptiness. Three of the ten curated keys' `config.py`
casts can never raise (`str` for `GEMINI_MODEL`/`_BACKUP`, `lambda v: str(v).lower()=="true"` for
`ALERTS_ENABLED`), so a typo like `ALERTS_ENABLED="tru"` silently disabled all real pushes with no error,
while a typo in any of the seven numeric keys instead took down every scheduled entry point via
`SystemExit` at import time — the same form reported success either way. Fix: the same ten-key
type/domain contract is now enforced at write time, in the portal (before any write attempt) and in the
database (so a direct SQL edit can't bypass it either).

DEEP-006: `holdings.currency` was free-choice, defaulting to `USD` for every market, never reconciled
against the held ticker's own `watchlist.market` even though the FK makes the market known at write
time. A `.TO` position entered as USD 50 against a native CAD 68 showed +36% where the truth is ~0%, fed
to the AI as fact (FR11) and rendered on the detail page. Fix: currency is now derived unconditionally
from `watchlist.market` by a DB trigger (not admin-entered, not client-validated), with a second,
independent defense-in-depth check in `build_position` for the narrower residual case where
`watchlist.market` itself is wrong for the ticker's real listing.

## Files changed

- **New:** `sql/tunables_validate_trigger.sql` — `_validate_tunable_update()` + `tunables_0_validate_update`
  trigger (BEFORE UPDATE on `public.tunables`).
- **New:** `sql/holdings_currency_derivation.sql` — `_derive_holdings_currency()` +
  `holdings_derive_currency` trigger (BEFORE INSERT OR UPDATE on `public.holdings`).
- `sql/admin_portal_tunables.sql` — "seed-data correction" the increment plan calls for: `ALERTS_ENABLED`'s
  seeded `description` corrected to state the AND-gate plainly, in both the INSERT (fresh-deploy
  source of truth) and a new idempotent `UPDATE` (syncs the already-live row, since the INSERT can't
  re-run against an existing primary key). No other line in this file changed — the table, stamp
  trigger, RLS policies, and the other 9 seed rows are untouched.
- `admin-portal/lib/validation.ts` — `validateTunableValue(key, value)` (was `(value)`), ten per-key
  rules; `HoldingsInput`/`validateHoldingsRow` drop `currency`; new `MARKET_CURRENCY` map.
- `admin-portal/app/(app)/tunables/page.tsx` — `ALERTS_ENABLED` renders as a select; `handleUpdate` passes
  the row's `key` into `validateTunableValue`.
- `admin-portal/app/(app)/holdings/page.tsx` — currency input removed from add/edit; watchlist fetch now
  includes `market`; read-only derived-currency label shown in both the add form and the edit row.
- `scripts/state.py` — `build_position`: new currency-mismatch guard (see above); no other function
  touched.

### Deviation from the "Files:" list — flagged, not silently applied

`tests/admin_portal/tunables_static.test.ts` and `tests/admin_portal/validation.test.ts` were **not** in
INC-10's Files list, but implementing `validateTunableValue`'s key-aware signature and dropping
`currency` from `HoldingsInput`/`validateHoldingsRow` — both explicitly mandated by
`admin-portal-tunables.md` §16.4 / `admin-portal.md` §16.3 — breaks 6 pre-existing call sites in those
two files (3 single-arg `validateTunableValue(...)` calls; the currency-checking half of
`validateHoldingsRow`'s tests). AC8 requires both "full existing test suite passes" and "no file outside
the list above changed," which are mutually exclusive once a design-mandated signature change is
implemented. I made the minimal, mechanical adaptation (added the required `key` argument to the three
`validateTunableValue` calls against `GEMINI_MODEL`, whose rule — non-blank — matches the tests' original
intent; removed the `currency` field/assertions from `validateHoldingsRow`'s fixtures, replacing "every
declared currency is accepted" — the one test with no remaining equivalent — with nothing, a net −1
test) rather than either leaving the suite red or leaving the design's mandated contract change
unimplemented. This is the same class of adaptation as this file's own INC-9 entry above (`tests/
test_tunables.py`'s two mocks renamed from `get_market_data` to `get_price_only` after that contract
changed) — not new test authorship for new behavior, which I did not add (e.g. no new tests for
`MARKET_CURRENCY` or the other 9 tunable-key rules; that's qa's normal INC-10 pass). Flagging explicitly
per CLAUDE.md's "never silently deviate" — orchestrator/qa should confirm this is acceptable or
reassign the two test-file edits.

## How to run it

`python3 -m pytest -q --tb=short` and `node --experimental-strip-types --test tests/admin_portal/*.test.ts`
from the repo root; `npm run build` from `admin-portal/`. No new env var, no new tunable, no config
change. The two new SQL files are **not applied to the live project** (explicit instruction — release/
INC-11 territory); to exercise them locally, apply `sql/admin_portal_tunables.sql` (already-live schema,
for the `tunables` table + seed) then the two new files against any Postgres instance with `auth.jwt()`/
`auth.uid()` stubbed (Supabase-provided functions, not used by either new trigger's own logic — only
needed so the files parse without error outside Supabase).

## How I verified the SQL (no live Supabase access this session)

Spun up a local Postgres 16 instance (already installed in this environment), created a scratch
database, stubbed `auth.jwt()`/`auth.uid()`, recreated `watchlist`/`holdings`/`tunables` per
`sql/schema.sql`/`sql/admin_portal_tunables.sql`, then applied both new files verbatim (no edits) and
ran the exact scenarios below. Scratch database dropped after verification; nothing left running.

## Acceptance-criteria self-verification

1. **PASS.** `ALERTS_ENABLED` is a `<select>` (`admin-portal/app/(app)/tunables/page.tsx`, confirmed by
   direct read and by `npm run build`'s successful compile). `validateTunableValue` rejects a malformed
   value for each of the 7 numeric keys before any write is attempted — confirmed both client-side
   (function returns non-empty errors) and, per AC3 below, server-side via the DB trigger.
2. **PASS.** Local scratch DB: `update ... set value='' where key='GEMINI_MODEL_BACKUP'` → `UPDATE 1`,
   `select value from tunables where key='GEMINI_MODEL_BACKUP'` → empty string, not rejected.
   `validateTunableValue("GEMINI_MODEL_BACKUP", "")` also returns `[]` client-side.
3. **PASS.** Local scratch DB, direct SQL: `update ... set value='5%' where key='DISCOVERY_GAINER_PCT'`
   → `ERROR: tunables.value for key DISCOVERY_GAINER_PCT must be numeric (e.g. "5" or "2.0"), got 5%`.
   `update ... set value='tru' where key='ALERTS_ENABLED'` → `ERROR: ... must be exactly "true" or
   "false" (case-insensitive), got tru`. A valid edit to each of the 10 keys (verified all 10, including
   both `ALERTS_ENABLED='false'` and `'TRUE'` for case-insensitivity) succeeded — full transcript above.
4. **PASS.** `select tgname from pg_trigger where tgrelid = 'public.tunables'::regclass order by tgname`
   → `tunables_0_validate_update` then `tunables_stamp_update` (confirmed on the scratch DB). The
   rejected `DISCOVERY_GAINER_PCT='5%'` update left `updated_at`/`updated_by` unchanged (re-selected
   before/after — identical timestamp, `updated_by` still null from the original seed) — no partial side
   effect. Note: I named the new trigger `tunables_0_validate_update`, not the design doc's illustrative
   `tunables_1_validate`/`tunables_2_stamp` — see "Known limitations" below for why.
5. **PASS.** `admin-portal/app/(app)/holdings/page.tsx`'s add/edit form has no currency input (confirmed
   by direct read and `npm run build`). Local scratch DB: inserted one holding per market (`AAPL`/US,
   `SHOP.TO`/TSX, `TCS.NS`/NSE), each with `currency='USD'` explicitly submitted in the INSERT (worse
   than the portal's actual payload, which no longer sends `currency` at all) — resulting rows show
   `USD`/`CAD`/`INR` respectively, not `USD` for all three.
6. **PASS.** Local scratch DB: `update holdings set currency='USD' where ticker='SHOP.TO'` (bypassing the
   portal, explicitly trying to force USD on a TSX ticker) → row still shows `CAD` after the update —
   the trigger overrides a client that actively tries to set it, not just one that omits it.
7. **PASS.** Scratch Python script (`SKIP_TUNABLES_FETCH=true`, no live Supabase): a holding with
   `currency="USD"` against `data["fundamentals"]["currency"]="CAD"` (the residual "watchlist.market
   wrong for this ticker" case, cost basis 50 vs price 68) → `pl_pct is None`,
   `[state] WARNING holding currency mismatch for SHOP.TO: ...` logged. Matching currencies →
   `pl_pct` computed normally (20.0). Missing `fundamentals` entirely (as both pre-existing
   `test_build_position_*` fixtures already do) → unaffected, `pl_pct` still computed — confirms no
   regression on the two pre-existing tests, which is also proven by the full-suite run below (244/244,
   zero new failures, zero tests needed changing in `tests/test_state.py`).
8. **PASS.** `python3 -m pytest -q --tb=short` → **244 passed, 0 failed** (identical to the stated
   baseline — `build_position`'s new branch is a no-op for every existing fixture, none of which include
   a `fundamentals` key). `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **62
   passed, 0 failed** (baseline 63, minus the one test with no remaining equivalent — see "Deviation"
   above; zero unexpected failures). `npm run build` → succeeds, all 7 routes present including
   `/holdings` and `/tunables`. `git diff --name-only` shows exactly the 7 production files listed above
   plus the 2 new SQL files plus the 2 flagged test-file adaptations — nothing else.

## Known limitations / things the design didn't fully anticipate

- **Trigger naming departs from the design doc's illustrative names.** `admin-portal-tunables.md` §16.4
  names the ordering pair `tunables_1_validate`/`tunables_2_stamp`, which reads as if the already-live
  `tunables_stamp_update` trigger (INC-6, `sql/admin_portal_tunables.sql`) gets renamed. Given this
  round's explicit caution against redefining/dropping already-applied live objects, I instead named the
  new trigger `tunables_0_validate_update` — `'0'` sorts before `'s'` in `tgname` order, so it fires
  first without touching the existing trigger at all. This satisfies AC4's substance (validate-before-
  stamp, confirmed on the scratch DB above) via a strictly additive change. Flagging since it's a literal
  departure from the design doc's illustrative naming, though not from its behavioral requirement.
- **Pre-existing holdings rows, if any existed:** the new `holdings` trigger only fires on `INSERT`/
  `UPDATE`. A row that is never subsequently written to keeps whatever `currency` it already has —
  this migration does **not** backfill/correct existing rows (a data change, out of scope for a
  code-review-time SQL file, and explicitly not something to apply live this session). Any future
  `UPDATE` to an existing row — even one only touching `shares`/`cost_basis` — re-derives and overwrites
  `currency` as a side effect (self-healing on next write), since the trigger fires regardless of which
  columns changed. The live watchlist holds zero holdings today, so this is moot in practice right now,
  but if a bad row is ever created before this trigger is applied, it stays bad until its next write.
  Not something this file addresses — flagging for release/INC-11 to note when applying.
- Neither new SQL file has been applied to the live Supabase project, per the explicit instruction for
  this increment — both `sql/tunables_validate_trigger.sql` and `sql/holdings_currency_derivation.sql`,
  plus `sql/admin_portal_tunables.sql`'s new corrective `UPDATE`, need release/INC-11 to apply them (the
  same "not applied by dev" posture every prior admin-portal SQL file in this project has used at
  handoff time).
- `GEMINI_MODEL_BACKUP`'s "blank means disabled" contract is validated (allowed) but not itself
  regression-tested against `scripts/config.py`'s cast (`str`, which already accepts `""`) — this was
  already true before INC-10 and isn't a new gap this increment introduces, just noting it wasn't
  independently re-verified against `config.py` beyond reading the existing cast.
- `MARKET_CURRENCY` (the portal's display-only mapping) and the DB trigger's `case v_market when ...`
  mapping are two independent copies of the same US/TSX/NSE → USD/CAD/INR fact, matching the design's
  own framing ("this constant is display-only... a mismatch... can only ever produce a wrong label,
  never a wrong write"). If a fourth market is ever added, both need updating — same class of drift risk
  `requirements.md` §10's dual-baseline-table gap (REV-074/078/087) already documents for tunables; not
  new to this increment, just the same pattern recurring in a new place.

## BUG-008 fix (fix cycle 1 of 3) — neither new SQL file re-applied cleanly

**Build plan.** Both `sql/tunables_validate_trigger.sql:84-86` and
`sql/holdings_currency_derivation.sql:46-48` end in a plain `create trigger ...` with no `or replace`
and no preceding `drop ... if exists` guard, so a second apply errors `trigger "..." already exists`
(qa's repro, `docs/test-report.md` Open bugs / BUG-008). Everything else in both files (`create or
replace function`, no grants/comments in either file — checked, there are none) was already
re-runnable. Fix: make each file's `create trigger` statement idempotent, verify by applying each
file twice to a local Postgres and diffing object state, run both full suites, do not touch
`sql/admin_portal_tunables.sql`, `tests/`, or anything outside these two files.

**Mechanism chosen: `create or replace trigger` (PG14+), not `drop trigger if exists` + `create
trigger`.** I considered both. `create or replace trigger` is a single atomic DDL statement, so
(unlike drop-then-recreate, which is two separate auto-committed statements in a `psql -f` run)
there is never a window where a concurrent write to `public.tunables`/`public.holdings` could land
while the trigger is momentarily absent — on a live table other surfaces already write to, that
matters. Postgres-version doubt was resolved, not assumed away: I don't have Supabase MCP/live-
project access this session, so I can't query the live project's Postgres major version directly,
but qa's own BUG-008 repro already smoke-tested `create or replace trigger` successfully against a
local Postgres 16, and this project's local reference Postgres (used throughout dev's and qa's own
verification, including this fix's) is also 16 — consistent with Supabase's current default of
PG15+ for new/active projects, with no contrary evidence anywhere in `docs/`. Release/INC-11 should
still confirm the live project's actual version before applying, per this bug's original framing, but
I'm not aware of any basis to expect it's older than PG14.

**Files changed:** `sql/tunables_validate_trigger.sql` (line 84's `create trigger` → `create or
replace trigger`, plus a short comment explaining the fix), `sql/holdings_currency_derivation.sql`
(same change, line 46). No other lines touched in either file.

**Verified by re-applying, not just reasoning about it.** Started a local Postgres 16
(`pg_ctlcluster 16 main start`), built a scratch database with `watchlist`/`holdings` (per
`sql/schema.sql`) plus `sql/admin_portal_tunables.sql` verbatim (stubbing `auth.jwt()`/`is_admin()`,
which only exist on live Supabase), then for each of the two fixed files: applied once, recorded
`pg_trigger`/`pg_proc` state (`tgname`, `tgrelid`, `tgfoid`, `tgenabled`, function OID), applied
again verbatim, and re-checked the same state plus behavior:
  - Both files' second apply succeeded (`CREATE FUNCTION` / `CREATE TRIGGER`, no error) — the BUG-008
    repro's exact failure no longer reproduces.
  - Trigger fire order unchanged after the second apply: `select tgname from pg_trigger where
    tgrelid = 'public.tunables'::regclass and not tgisinternal order by tgname` still returns
    `tunables_0_validate_update` then `tunables_stamp_update` (validate still fires first).
  - Function OIDs identical before/after (`create or replace function` already preserved identity;
    unaffected by this fix).
  - Behavior re-confirmed live after the second apply, not just object metadata: a bad
    `DISCOVERY_GAINER_PCT` value is still rejected; inserting all-`USD` holdings for US/TSX/NSE
    tickers still derives `USD`/`CAD`/`INR`; a direct `UPDATE ... SET currency='USD'` on a TSX
    holding is still overridden back to `CAD`; a ticker absent from `watchlist` still raises
    `holdings.ticker % has no matching watchlist row`.
  - Existing row data was untouched by the mere re-apply itself (`tunables`/`holdings` row values
    identical before/after) — re-applying the DDL doesn't reset anything stateful; only a subsequent
    write re-fires either trigger, same as before this fix.
  - Scratch database dropped and the local Postgres cluster stopped after verification; nothing left
    running.

**Everything else in both files checked, not assumed, to already be re-runnable:** both
`create or replace function` statements are inherently idempotent and were unaffected; neither file
contains any `grant`, `comment on`, or other stateful statement — read both files fully to confirm
before concluding the trigger line was the only defect.

**One test-suite side effect, flagged rather than worked around.** Full TS suite:
`tests/admin_portal/tunables_static.test.ts:144-153` ("... trigger name sorts before
tunables_stamp_update ...") asserts the file's `create trigger` line against a regex,
`/create trigger (\S+)\s+before update on public\.tunables/i`, that only matches the literal
pre-fix `create trigger` syntax — it does not match `create or replace trigger`, so this one test
now fails (`error: 'new validate trigger not found'`). This is not a behavioral regression: the
trigger name, its position, and the fire-order it's testing for are all still correct (verified
directly against `pg_trigger` above); the assertion's regex itself needs `create (or replace )?
trigger` to match the fixed, correct file. I did not edit it — `tests/` is qa's per the ownership
table and I was told qa "has already re-verified" this pass. Flagging for qa's next pass rather than
silently leaving it unexplained. (A second static test at line 156-166, forbidding a literal
`drop trigger` substring anywhere in the file, was NOT broken by the chosen mechanism — it was only
briefly broken by my own draft comment prose using that literal substring, which I reworded; the
final file contains no `drop trigger` statement or comment text at all, consistent with choosing
`create or replace trigger` over drop-then-recreate.)

**Full regression suite, run quietly, both suites:**
- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **249 passed, 0 failed** — unchanged
  from baseline, as expected for an SQL-only fix.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **79 passed, 1 failed**
  (baseline 80/0) — the single failure is `tunables_static.test.ts:144-153` described above, a
  pre-fix-syntax-assuming assertion, not a regression in file behavior.

**Smoke test:** all three `scripts/` entry points still import cleanly
(`SKIP_TUNABLES_FETCH=true python3 -c "import sys; sys.path.insert(0,'scripts'); import
run_hourly, run_discovery, publish_prices"` → `OK`); the SQL fix touches only the two new files,
nothing Python/TypeScript-side changed, so this is confirmation the fix stayed scoped, not a new
check.

**Owner of the flagged test-suite item:** qa, to update
`tunables_static.test.ts:146`'s regex (`create trigger` → `create (or replace )?trigger`) to match
the fixed file on its next pass. Not blocking a re-review of the SQL fix itself, which is complete
and independently re-verified above.

## REV-112/REV-113 fix (fix cycle 2 of 3) — `_ticker_block` currency-mismatch fabrication risk + corrective-SQL packaging

### Build plan (written before coding)

Read `docs/review-log.md` Pass 26's REV-113/REV-112 entries, `docs/design/non-functional-ops.md` §7.3,
and `docs/requirements.md` FR11/FR29. **REV-113** (major, priority): `ai_judge._ticker_block`
(`:101-106`) rendered a held position's raw `cost_basis`/currency and unlabeled `price` on one line even
when `build_position` had suppressed `pl_pct` for a currency mismatch — the model could still compute
its own gain/loss from the two adjacent, differently-denominated numbers and state it as fact. §7.3
already documents the invariant (pl_pct suppression) and DEEP-006's own suggested fix ("stop a bad row
from reaching the prompt at all") is on record, so this closes that intent one layer further, not a new
design decision. **REV-112** (minor): the DEEP-005 seed-description correction lived as a trailing
`update` inside `sql/admin_portal_tunables.sql`, an already-applied (INC-6), non-re-runnable migration —
so it would never actually reach the live project. Files: `scripts/ai_judge.py` (REV-113 render fix),
`scripts/state.py` (expose the mismatch condition `build_position` already computes, so `_ticker_block`
doesn't re-derive it — CLAUDE.md's "extract on second occurrence" rule), `sql/admin_portal_tunables.sql`
(remove the trailing `update`, pointer comment only) + new `sql/admin_portal_tunables_alerts_enabled_
description_fix.sql` (the correction, as its own additive/idempotent/re-runnable file). Verify: full
pytest + node --test suites unchanged from baseline (249/0, 82/0 expected), manual `_ticker_block`
render check for both the mismatch and agreeing-currency cases, no design doc edited.

### REV-113: what `_ticker_block` now emits, and why

For a held position where `build_position` detects a currency mismatch (holding currency vs. the
independently-fetched fundamentals currency, the exact FR11 condition), `_ticker_block` now emits:

```
Shares: 10. Cost basis and current price are not shown together: the recorded holding currency (USD)
does not match this ticker's market currency (CAD), so the two figures are not comparable -- do not
compute or state an unrealized gain/loss for this position.
```

instead of the old `Shares: N, Cost basis: X CUR, Current price: Y, Unrealized P/L: n/a` line. I chose
**omission over labeling** (the reviewer's two suggested shapes): labeling both figures with their own
currencies would still put two numbers side by side that *look* subtractable/divisible, and a model
computing its own cross-currency "adjusted" ratio despite a label is the same risk class DEEP-005/006/
this finding are all about — the guard needs to hold even against a model that half-ignores an
instruction. Omitting both raw figures (not just the derived `pl_pct`) matches DEEP-006's own
already-recorded fix intent quoted in REV-113 ("stop a bad row from reaching the prompt at all") and
removes the arithmetic opportunity structurally rather than trusting an instruction to suppress it.
`Shares` is kept (not currency-denominated, no mismatch risk, still useful HELD-vs-WATCH-ONLY context).
The current price is not lost to the model — it still appears, correctly labeled with the fundamentals
currency, in the unrelated "Price/volume" line below (unchanged), which is the ticker's own real listing
price and needed for price/volume analysis regardless of any holding.

To avoid duplicating the mismatch condition (build_position's `fundamentals_currency and currency and
fundamentals_currency != currency`) a second time in `ai_judge.py`, `build_position` (`scripts/
state.py`) now also returns `currency_mismatched: bool` on the position dict it already builds and
hands to `judge_batch`/`_ticker_block` via the existing `{"data":..., "position":...}` contract —
`state.py` stays the single owner of the FR11 invariant-detection logic; `ai_judge.py` only consumes the
already-computed fact. No existing test asserts the full key-set of `build_position`'s return value
(`tests/test_state.py:307-370` all check specific keys, e.g. `pos["pl_pct"]`), so this is additive, not
breaking.

**Does this change §7.3's specified contract? No.** §7.3's text is about the currency invariant itself
("pl_pct is suppressed... rather than computed from mismatched currencies, per FR11's explicit
requirement") — it says nothing about the prompt-rendering layer's exact wording, and this fix
implements the intent §7.3/FR11 and DEEP-006 already establish (no model-facing fabrication of a
cross-currency figure), just at the one remaining layer (the raw inputs, not just the derived output)
that intent hadn't yet reached. I did not edit `non-functional-ops.md`. One adjacent doc line is *not*
fully precise anymore and is worth tech-lead's attention at the next design-doc pass (not blocking, not
edited by me): `docs/design/components.md` §4.4's one-line prompt-content summary says the per-ticker
block has "shares/cost-basis/price/P&L for held" unconditionally — true in the non-mismatch case, no
longer true in the mismatch case. Flagging, not fixing — design docs are tech-lead's per the ownership
table.

### REV-112: where the correction moved, and why

New file: `sql/admin_portal_tunables_alerts_enabled_description_fix.sql` — one `update public.tunables
... where key = 'ALERTS_ENABLED'` statement, byte-identical to the one removed from `sql/
admin_portal_tunables.sql`, with a header explaining the move and its idempotency (same shape as this
round's other two new files, `tunables_validate_trigger.sql`/`holdings_currency_derivation.sql`). Chose
"new separate file" over "apply-time note" (the reviewer's two suggested fixes) because INC-11 is about
to apply those same two new files — adding this as a third file in that same batch is a natural,
low-effort home that actually gets executed, rather than relying on a release engineer reading an extra
instruction correctly by hand. `sql/admin_portal_tunables.sql` itself: removed only the trailing
`update` block (never applied live — only the file's original `create table`/seed seeded at INC-6 is
"Deployed as part of INC-6" per `docs/runbook.md` §2.3) and replaced it with a one-line pointer comment;
lines 1-86 (the already-applied create-table/seed content) are untouched. No SQL applied to the live
project.

### Files changed

- `scripts/ai_judge.py` — `_ticker_block`'s held-position line branches on `position["currency_mismatched"]`.
- `scripts/state.py` — `build_position` returns `currency_mismatched: bool` alongside the existing keys.
- `sql/admin_portal_tunables.sql` — trailing corrective `update` removed, replaced with a pointer comment; nothing else changed.
- `sql/admin_portal_tunables_alerts_enabled_description_fix.sql` — new, the relocated correction.

### How to run it

`SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` (full suite);
`node --experimental-strip-types --test tests/admin_portal/*.test.ts` (full suite); manual render check:
`python3 -c "..."` building a mismatched-currency `data`/`holding` pair, calling
`state.build_position()` then `ai_judge._ticker_block()`, confirming `cost_basis`/`price` never appear
on the same line for that case (done below).

### Full regression + smoke test

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **249 passed, 0 failed** — matches
  baseline exactly; REV-113's change added no new duplicated-condition code and no existing test builds
  a held-position prompt through `_ticker_block` (`tests/test_ai_judge.py` only exercises `position:
  None`), so nothing broke and nothing needed a workaround.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed** —
  matches baseline exactly; no TS test reads `sql/admin_portal_tunables.sql`'s trailing lines or the
  new SQL file's content.
- Manual `_ticker_block` render check (mismatch: USD holding on a CAD-fundamentals ticker; agreement:
  CAD holding on a CAD-fundamentals ticker) — mismatch case shows the new omission line with no
  `cost_basis` figure anywhere in the block; agreement case is byte-identical to the pre-fix rendering
  (`Shares: 10, Cost basis: 50.0 CAD, Current price: 68.0, Unrealized P/L: 36.0%`) — the guard fires only
  on an actual mismatch, unchanged behavior otherwise.
- Smoke test: `SKIP_TUNABLES_FETCH=true python3 -c "import sys; sys.path.insert(0,'scripts'); import
  run_hourly, run_discovery, publish_prices"` → all three entry points import cleanly.

### Known limitations / things qa may need to update

- No existing test exercises `_ticker_block` with a non-`None` `position` at all (mismatched or
  agreeing) — qa may want to add a `test_ai_judge.py` case for both branches now that REV-113 gives the
  mismatch branch product-relevant behavior worth a permanent regression guard (mirrors how DEEP-006's
  `build_position` guard got its own three tests in `test_state.py`). Not something I added myself since
  `tests/` is qa's per the ownership table and none of the 249 pytest / 82 TS tests broke, so there's
  nothing to *fix*, only a coverage gap to flag.
- `tunables_static.test.ts:144-153`'s regex/BUG-008 flag from fix cycle 1 (still open, qa's) is
  unrelated to this fix cycle and unaffected by it.

---

# Handoff — INC-12: kill-switch in-flight boundary checks + mid-run-abort classification (FR24, FR35; DEEP-007)

## Build plan (written before coding, per dev's workflow)

Read `docs/design/increment-plan.md`'s `### INC-12` (files + literal ACs), `docs/design/
operational-controls.md` §13.6 (all five subsections), `docs/requirements.md` FR24/FR25/FR35 + Decisions
#37/#38, and `docs/design/components.md` §4.8 (INC-8's heartbeat contract). Approach: add `state.is_paused()`,
`state.KillSwitchAbort(BaseException)`, `state.write_kill_switch_abort()`, and two checkpoint-3 call sites
(`process_ticker`/`process_candidate`, each right before its own `notifier.push(...)`, before any write for
that ticker); checkpoint 1 (bare early return) in `run_hourly.main()`/`run_discovery.main()` right after
`sb`/`notifier` are constructed; checkpoint 2 (raises `KillSwitchAbort("ai_call")`) in `_process_group`
after Phase-1 ingest / in `run_discovery.main()` after its own Phase-1 ingest, both immediately before
`judge_batch(...)`; a `try/except state.KillSwitchAbort` wrapping each `main()`'s group-processing work,
writing one `kill_switch_abort_log` row and returning with **no** `run_heartbeat` write; checkpoint 4 (bare
early return) in `publish_prices.py` right before the `pages/prices.json` file write. New SQL:
`sql/kill_switch_abort_log.sql`, mirroring `kill_switch_audit`'s RLS+FORCE+REVOKE, `create table if not
exists` for genuine re-runnability (verified by double-apply against local Postgres 16, not just reasoned
about). No config-schema change. Verify: full Python+TS suites green, every literal AC in the increment
plan self-checked (grep call-site counts, `BaseException` subclass, manual trace of what each checkpoint
does/doesn't call), double-apply the new SQL file locally.


## What changed and why

DEEP-007's gap: §13.1's dispatch-layer kill switch only stopped *future* pg_cron dispatches — a run
already executing when the flag flipped ran to full completion (real Yahoo fetches, a real AI call, a
real push, a real `contents: write` commit), while the portal badge already read PAUSED. Decision #37
added four Python-layer boundary checkpoints, each immediately before an irreversible action, so an
in-flight run stops itself. Decision #38/FR35 then closes the follow-on gap: a run that aborts at
checkpoint 2/3 has already produced real logged per-ticker work, a shape distinct from both "never
started" (FR25) and "completed degraded" (NFR2) that needs its own non-alerting classification, causally
tied to the checkpoint's own flag read so a genuine crash can never be misreported as a deliberate pause.

**Checkpoint 1** (`run_hourly.main()` / `run_discovery.main()`, right after `sb`/`notifier` are
constructed): bare early return, no `run_heartbeat` row, no `kill_switch_abort_log` row.
**Checkpoint 2** (`run_hourly._process_group()` after Phase-1 ingest / `run_discovery.main()` after its
own Phase-1 ingest, both immediately before `judge_batch(...)`): raises `state.KillSwitchAbort("ai_call")`
— it sits below `main()`, so it can't just `return`.
**Checkpoint 3** (`state.process_ticker` / `state.process_candidate`, only in the branch that's about to
push, before `log_id`/`write_call_log`/`verdict_state` are touched): raises
`state.KillSwitchAbort("push")` — nothing has been written yet for that ticker, so the crossing is left
exactly as pending as if this cycle had never reached it; the next cycle's `process_ticker`/
`process_candidate` retries automatically against the still-unadvanced `verdict_state` (FR34's existing
mechanism — no new resume logic, per FR35's own text).
**Checkpoint 4** (`publish_prices.main()`, right before the `pages/prices.json` write): bare early return
— Yahoo fetches in that script aren't gated (not irreversible), only the commit-triggering write is.

`KillSwitchAbort` subclasses `BaseException`, not `Exception` — both entry points already wrap per-ticker/
per-group work in `except Exception` so one bad ticker can't take the run down; a plain `Exception`
subclass raised from inside those loops would be silently caught and miscounted as `outcomes["error"]`,
exactly the misclassification FR35 forbids. It's caught exactly once, by a `try/except
state.KillSwitchAbort` wrapping each `main()`'s group-processing work (the `for s in run_sessions` loop
in `run_hourly.py`; the checkpoint-2-check + `judge_batch(...)` + Phase-3 push loop in `run_discovery.py`).
The `except` branch computes `real_rows_this_cycle` from the `outcomes` counter accumulated so far, calls
`state.write_kill_switch_abort(...)`, prints a `[kill-switch] paused -- aborted at checkpoint=...` line,
and returns — **no** `run_heartbeat` write, mirroring checkpoint 1's existing treatment.

`kill_switch_abort_log` (new table, `sql/kill_switch_abort_log.sql`) is written **only** from
`state.write_kill_switch_abort()`, called **only** inside the `except KillSwitchAbort` branches above —
that exclusivity is what makes a row's existence proof of a deliberate pause rather than an inference from
a symptom (a short outcome count, a missing heartbeat) that a genuine crash could also produce.
`check_pipeline_health()` needed **zero** SQL changes: while `kill_switch_state.paused = true` it already
returns before any alert evaluation (§13.4), and the missing `run_heartbeat` row after an abort is exactly
the shape §13.4's existing `resume_baseline` guard already tolerates on resume — both built for
checkpoint 1's case, now covering checkpoints 2–4 for free by following the same "write nothing to
`run_heartbeat`" convention.

## Files touched

- `sql/kill_switch_abort_log.sql` — new. `kill_switch_abort_log` table (`workflow`, `checkpoint` CHECK'd
  to `'ai_call'`/`'push'`, `aborted_at`, `real_rows_this_cycle`), RLS enabled+forced, `insert/update/delete`
  revoked from `public, anon, authenticated` — same two-layer deny-all posture as `kill_switch_audit`.
  `create table if not exists` for genuine re-runnability (no trigger in this file, so BUG-008's PG14+
  `create or replace trigger` concern doesn't arise here at all — see "SQL idempotency" below).
- `scripts/state.py` — new `is_paused(sb)`, new `KillSwitchAbort(BaseException)`, new
  `write_kill_switch_abort(sb, *, workflow, checkpoint, real_rows_this_cycle)`; one checkpoint-3 call site
  each in `process_ticker` (the "change -> immediate alert" branch) and `process_candidate` (the `do_push`
  branch), both immediately before `log_id = str(uuid.uuid4())`/`notifier.push(...)`.
- `scripts/run_hourly.py` — checkpoint 1 in `main()` (after `sb`/`notifier` construction, before
  `state.get_watchlist(sb)`); checkpoint 2 in `_process_group` (after Phase-1 ingest, before
  `judge_batch(...)`); `main()`'s `for s in run_sessions: _process_group(...)` loop wrapped in
  `try/except state.KillSwitchAbort`.
- `scripts/run_discovery.py` — checkpoint 1 in `main()` (after `sb`/`notifier` construction, before
  `prefilter.find_candidates(...)`); checkpoint 2 + `judge_batch(...)` + the Phase-3 push loop wrapped in
  `try/except state.KillSwitchAbort` (checkpoint 2 raises immediately inside the `try`, right after Phase-1
  ingest completes).
- `scripts/publish_prices.py` — checkpoint 4 right before `out = {...}` / the `pages/prices.json` write.
- `docs/handoff.md` — this entry.

No config-schema change (no new tunable — matches the design's "no config-schema change" note).

## How to run it

`SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` (Python suite);
`node --experimental-strip-types --test tests/admin_portal/*.test.ts` (TypeScript suite, unaffected by
this increment — no `admin-portal/` files touched). To exercise the kill switch itself locally: seed a
`kill_switch_state` row (or point at a live Supabase project with `sql/kill_switch.sql` applied), flip
`paused` via `select set_kill_switch(true);`, then run any of `run_hourly.main()` / `run_discovery.main()`
/ `publish_prices.main()` and watch for the `[kill-switch]` log lines at the checkpoint reached.
`sql/kill_switch_abort_log.sql` is **not applied to the live Supabase project** (explicit instruction for
this session) — apply it after `sql/kill_switch.sql` (already live) whenever release/INC-11-style live
verification runs.

## Full regression + smoke test

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` -> **253 passed, 0 failed** — identical to
  the stated 253/0 baseline (no existing test exercises the new checkpoints yet; qa owns adding that
  coverage per the increment's ACs).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` -> **82 passed, 0 failed** —
  identical to baseline (nothing in `admin-portal/` touched).
- `git diff --name-only` / `git status --porcelain` -> exactly `sql/kill_switch_abort_log.sql` (new),
  `scripts/state.py`, `scripts/run_hourly.py`, `scripts/run_discovery.py`, `scripts/publish_prices.py`,
  `docs/handoff.md` — nothing outside the increment's file list.
- Import smoke test: `python3 -c "import run_hourly, run_discovery, publish_prices"` -> all three entry
  points import cleanly; confirmed `issubclass(state.KillSwitchAbort, BaseException) is True` and
  `issubclass(state.KillSwitchAbort, Exception) is False` directly in the interpreter.
- **Scripted end-to-end harness** (in-memory Supabase/notifier doubles, same shape as `tests/test_state.py`'s
  `FakeSupabase`/`FakeNotifier`, run against the real `run_hourly.py`/`run_discovery.py`/`publish_prices.py`/
  `state.py` code — not just reasoning about the diff): built a scratch script exercising every checkpoint
  end to end; scratch script and full transcript are not part of the repo (dev-only verification, per the
  "no test files" scope for this increment — qa owns `tests/`). Results, matching every literal AC below.

## Acceptance-criteria self-verification (`increment-plan.md`'s `### INC-12`)

1. **PASS.** `grep -n "def is_paused" scripts/state.py` -> one match (`state.py:22`). Scripted harness:
   mocked `kill_switch_state` select to return `paused=True` then `paused=False` in turn -> `is_paused(sb)`
   returned `True` then `False`, matching each case.
2. **PASS — call-site counts confirmed by grep, literally:**
   - `scripts/run_hourly.py`: `grep -n "is_paused(sb)"` -> exactly 2 (`state.is_paused(sb)` at checkpoint 1
     in `main()`, line 160; checkpoint 2 in `_process_group`, line 87).
   - `scripts/run_discovery.py`: `grep -n "is_paused(sb)"` -> exactly 2 (checkpoint 1 in `main()`, line 36;
     checkpoint 2, line 108).
   - `scripts/state.py`: `grep -n "^\s*if is_paused(sb)"` -> exactly 2 (checkpoint 3 in `process_candidate`,
     line 200; checkpoint 3 in `process_ticker`, line 368), each immediately before its own
     `notifier.push(...)` call.
   - `scripts/publish_prices.py`: `grep -n "is_paused(sb)"` -> exactly 1 (checkpoint 4, line 70).
   - `grep -n "class KillSwitchAbort" scripts/state.py` -> `class KillSwitchAbort(BaseException):` —
     confirmed `BaseException`, not `Exception`, both by the grep and by
     `issubclass(state.KillSwitchAbort, Exception) is False` in the interpreter.
3. **PASS.** Scripted harness: patched `ingest.get_market_data`/`prefilter.find_candidates`/
   `ai_judge.judge_batch`/`notifier.push`/`state.write_heartbeat`/`state.write_kill_switch_abort` to raise
   `AssertionError` if called at all; mocked `is_paused()` to return `True` before any ticker-level work;
   ran `run_hourly.main()`, `run_discovery.main()`, and `publish_prices.main()` — none of the six boomed
   functions fired for any of the three entry points. Confirms checkpoint 1/4's abort is a bare,
   side-effect-free early return.
4. **PASS.** Scripted harness: real `ingest.get_market_data` ingested one ticker to completion (`items`
   non-empty), `is_paused()` scripted `False` at checkpoint 1 then `True` at checkpoint 2 —
   `ai_judge.judge_batch` (patched to raise if called) never fired, `state.write_heartbeat` (patched to a
   tracking stub) was never called, `state.write_kill_switch_abort` was called exactly once with
   `checkpoint="ai_call"`, `workflow="hourly-watchlist"`, `real_rows_this_cycle=0` (zero prior rows this
   cycle — the checkpoint-2-with-zero-prior-rows sub-case §13.6.3 explicitly documents).
5. **PASS.** Scripted harness: two watchlist tickers (AAPL, MSFT) both pre-seeded with prior
   `verdict_state.current_verdict="Hold"`; the AI batch returns `Buy` for both (both are real verdict
   crossings). `is_paused()` scripted `False` through AAPL's checkpoint-3 read (AAPL pushes and its
   `verdict_state` advances to `Buy`) then `True` for MSFT's checkpoint-3 read. Result: `notifier.push`
   called exactly once (AAPL only — confirmed by the call list); MSFT got **no** `call_log` insert and
   **no** `verdict_state` upsert/update at all (its row stayed exactly `current_verdict="Hold"`, untouched —
   "the crossing stays exactly as pending"); `state.write_kill_switch_abort` called once with
   `checkpoint="push"`, `real_rows_this_cycle=1` (AAPL's `change-alert`, matching the real-outcome count so
   far this cycle); `state.write_heartbeat` never called. Separately confirmed the `BaseException`
   propagation this AC and AC7 both depend on: `_process_group`'s Phase-3 loop has its own
   `except Exception` around each ticker, and MSFT's `KillSwitchAbort` was **not** counted into
   `outcomes["error"]` (outcomes ended at `{'change-alert': 1}`, no `error` key at all) — it propagated
   straight out of the loop, out of `_process_group`, and up to `main()`'s outer `except
   state.KillSwitchAbort`.
6. **PASS.** Re-ran the harness with fresh doubles seeded from AC5's *aborted* end state (`AAPL:Buy`
   already advanced, `MSFT:Hold` still pending) and `is_paused()` returning `False` throughout: MSFT was
   pushed (`notifier.push` called with `MSFT`) and `verdict_state.current_verdict` advanced to `Buy`; a
   `run_heartbeat` row was written (a normal, non-aborted completion this time) — confirms FR35's
   "no new resume logic needed" claim with the zero additional code this design specifies.
7. **PASS** — see AC5's propagation trace above; the same scripted run proves the `except Exception` guard
   inside `_process_group`'s Phase-3 loop does not catch `KillSwitchAbort` (`BaseException`), and it
   reaches `main()`'s outer handler uncounted in `outcomes["error"]`.
8. **Live SQL item — folded into a future live-verification pass, not a merge blocker for this increment**
   (per the increment plan's own text). Not applied to the live project this session (explicit
   instruction). Verified instead against a local Postgres 16 scratch database — see "SQL idempotency"
   below for the double-apply result; the RLS/REVOKE deny-all posture (`relrowsecurity`/
   `relforcerowsecurity` both `true`, zero grants to `anon`/`authenticated`, a `set role anon` SELECT and
   INSERT both denied with `permission denied for table kill_switch_abort_log`) was confirmed on that
   scratch database, matching AC8's proof pattern; the live-project row-count/`check_pipeline_health()`
   portion of AC8 needs a real dispatched run against Supabase and is explicitly release/live-verification
   territory, not something dev can self-verify locally.
9. **PASS.** Full suite: 253/0 (Python), 82/0 (TypeScript) — see "Full regression" above. `git diff
   --name-only` confirms no file outside this increment's list changed.

## SQL idempotency — double-apply result, and the PG-version question

Started a local Postgres 16 cluster (`pg_ctlcluster 16 main start`), created a scratch database
(`inc12_scratch`; `anon`/`authenticated` roles already existed cluster-wide from a prior fix-cycle's
verification work), applied `sql/kill_switch_abort_log.sql` **twice**, verbatim, no edits between applies:

- **First apply**: `CREATE TABLE` / `ALTER TABLE` ×2 / `REVOKE`, all succeeded. Confirmed
  `relrowsecurity`/`relforcerowsecurity` both `true`; zero grants to `anon`/`authenticated`/`public`
  (`information_schema.role_table_grants`); a `postgres`-role (BYPASSRLS) insert succeeded; `set role anon`
  then a `SELECT`/`INSERT` both failed with `permission denied for table kill_switch_abort_log`.
- **Second apply**: `psql:...:35: NOTICE: relation "kill_switch_abort_log" already exists, skipping` /
  `CREATE TABLE` (no-op) / `ALTER TABLE` ×2 / `REVOKE` — **exit code 0, no error**. Re-checked afterward:
  `relrowsecurity`/`relforcerowsecurity` unchanged (still `true`/`true`); the row inserted after the first
  apply was still present, untouched; grants to `anon`/`authenticated` still zero; a second `postgres`
  insert still succeeded (2 rows total) and `anon` was still denied both `SELECT` and `INSERT`; the
  `checkpoint` CHECK constraint (`in ('ai_call','push')`) still rejected a bogus value with the same error.
  Scratch database dropped and the cluster stopped afterward; nothing left running.

**No PG14+ syntax used.** This file has no trigger at all (unlike `sql/tunables_validate_trigger.sql`/
`sql/holdings_currency_derivation.sql`, which needed `create or replace trigger`, a PG14+ construct, to
fix BUG-008) — the only re-runnability concern here was the plain `create table`, fixed with `create table
if not exists` (standard syntax on every Postgres version this project could plausibly be on).
`alter table ... enable/force row level security` and `revoke` are idempotent by nature (a harmless no-op
on re-run, not an error) on every Postgres version, so they needed no defensive rewrite. Given the user is
independently confirming the live project's Postgres major version, this file should apply cleanly
regardless of the outcome of that check.

## Known limitations / things the design didn't fully anticipate

- **`real_rows_this_cycle`'s formula is copied verbatim from the design's own snippet**
  (`("cold-start", "quiet", "change-alert", "push-failed", "no-read")` for `run_hourly.py`;
  `("candidate-logged", "candidate-pushed", "candidate-push-failed", "no-read")` for `run_discovery.py`) —
  note it deliberately excludes `outcomes["skip"]` even though a skip *does* write a `call_log` row
  (`state.log_skip`). This is the design's own choice (§13.6.2's snippet), not a deviation I introduced;
  flagging only because "real (non-skip) `call_log` row" in FR35's own text reads as if a skip should
  count, while the design's literal code sample doesn't include it. Not fixing silently — the design's
  code block is unambiguous and matches what `increment-plan.md`'s ACs test against, so I implemented it
  as written; tech-lead should confirm whether this is intentional or a design-doc gap in a future pass, no
  design deviation on my part meanwhile.
- **Live-project confirmation of `check_pipeline_health()`'s zero-SQL-change claim** (AC8's second half —
  a real dispatched run against Supabase, paused mid-run, produces exactly one row and no alert both while
  paused and after resume) needs live infrastructure and is out of scope for this session per the explicit
  instruction not to apply the new SQL live. Folded into a future live-verification pass, per the increment
  plan's own framing (not a merge blocker for INC-12).
- No test files were added or edited (`tests/` is qa's per the ownership table); every AC above was
  self-verified with a throwaway scratch harness, not committed to the repo. qa's own tests will need to
  build equivalent fakes/mocks for `kill_switch_state`/`kill_switch_abort_log` reads/writes — the shape used
  here (a `.table(name).select(...).eq(...).limit(...).execute().data` chain, matching `tests/test_state.py`'s
  existing `FakeSupabase`) should drop in directly.
- An automated environment checkpoint (`git log` commit `b09e65f`, "checkpoint dev's in-progress
  boundary-check work (UNVERIFIED)") committed this increment's working tree mid-session, before self-
  verification was complete — not a commit I made myself, and not the "dev commits after qa passes" event
  CLAUDE.md's git workflow describes. Flagging so the orchestrator doesn't mistake it for a completed
  handoff commit; no qa run or reviewer pass has happened yet for INC-12.

---

# Handoff — Evidence record: INC-11 live-verification pass (Decision #36) — Postgres version, INC-3 AC3, INC-4 AC6, INC-7 Step 0, INC-10 SQL confirmation

## Context

`docs/design/increment-plan.md`'s `### INC-11` names three checkable, separable items (INC-3 AC3, INC-4
AC6, INC-7 Step 0 + AC2/AC3), plus a Postgres-major-version doubt `docs/handoff.md`'s "BUG-008 fix (fix
cycle 1 of 3)" section explicitly carried forward as an open INC-11 prerequisite ("Release/INC-11 should
still confirm the live project's actual version before applying... I'm not aware of any basis to expect
it's older than PG14"). Subagents have no Supabase/GitHub credentials this session, so — same posture as
the INC-3/ClientOptions evidence record above — **this record was executed directly by the orchestrator**,
not by any subagent, then handed to qa to log per doc-hygiene/attribution rules. qa did not run these
checks and did not have Supabase/GitHub access this session.

### Raw evidence

**Date:** 2026-07-30. **Run by:** orchestrator, live query against the production Supabase project (user
explicitly executed these checks; the sole user, accepting the risk of live testing against production).

**1. Live DB Postgres major version.** Confirmed **PostgreSQL 17.6.1** — resolves the residual doubt
above outright: no longer an assumption, and well above the PG14+ floor `create or replace trigger`
(`sql/tunables_validate_trigger.sql`, `sql/holdings_currency_derivation.sql`) needs. No corrective action
required on either file.

**2. INC-3 AC3 (resume-baseline / no-false-alarm under a real pause/resume cycle).**
`kill_switch_state.paused` false→true at `19:12:47.594Z`. `dispatch_github_workflow('hourly-watchlist.yml',
'{}')` returned `null` and created **no** workflow run — scheduled dispatches run at :00/:30, the last real
run was `19:00:01Z`, and none fired at `19:12`. Resumed (paused true→false) at `19:12:57.378Z`.
`kill_switch_audit` gained exactly two new rows, one per toggle — this also independently reconfirms
**INC-3 AC4** (the original AC4 evidence, 2026-07-29 above, was a different pause/resume cycle; today's
exercise reproduces the same audit-trail guarantee on a fresh cycle). **Caveat, recorded deliberately:**
the actor was `postgres` (direct SQL / service-role credential), so this exercised INC-3's original
trusted-direct-SQL path, **not** the admin portal's `is_admin()`-gated RPC path — that distinct path
remains INC-7 AC2/AC3's job, still open (item 5 below).

**3. INC-4 AC6 (live Gemini smoke test).** 90 `call_log` rows in the trailing 3 hours to `19:01:42Z`,
every one `parse_status='ok'`, `model_used='gemini-2.5-flash'`, `fallback_from=null` — 90 consecutive
successful live Gemini calls in production, stronger evidence than a single one-off smoke test would have
been.

**4. INC-7 Step 0 (confirm `sql/kill_switch_portal_grant.sql` is actually live).** `admin_read_kill_switch`
policy present on `kill_switch_state` (`select`/`authenticated`/`is_admin()`); `set_kill_switch(boolean,
text)` present and its body contains the `is_admin()` authorization check. **Step 0 passes — no migration
apply needed.** `docs/design.md`'s FR31/FR32 coverage row claiming this SQL was already live and confirmed
against production is itself now independently confirmed, not merely trusted.

**5. INC-7 AC2/AC3 — explicitly NOT done, still open.** The portal RPC round-trip and live
dispatch-suppression proof both require a real authenticated admin **browser** session (the portal's own
`is_admin()`-gated path) — nobody in this session, subagent or orchestrator, had one available. Do **not**
infer this closed from item 2's service-role proof above; that exercised a materially different auth path.
Remains open pending a session with an authenticated admin portal login.

**6. INC-10 SQL objects — applied live and independently re-verified (supplementary to INC-11's three
named items, folded into the same live-verification pass).** `inc10_tunables_validate_trigger`,
`inc10_holdings_currency_derivation`, `inc10_alerts_enabled_description_fix` all confirmed live: both
triggers present and enabled on `public.tunables`/`public.holdings`; `tunables_0_validate_update` sorts
before `tunables_stamp_update` (correct validate-then-stamp fire order). **DEEP-005 proven closed live,**
not just against a local scratch database as INC-10's own qa passes did: inside a rolled-back transaction,
`update tunables set value='yes' where key='ALERTS_ENABLED'` was rejected with `tunables.value for key
ALERTS_ENABLED must be exactly "true" or "false" (case-insensitive), got yes`; the live row's `value`
remains `true` and its `description` carries the corrected AND-gate text.

### What this closes

- The PG14+ residual doubt flagged in this file's "BUG-008 fix (fix cycle 1 of 3)" section is resolved,
  not merely reasoned about further.
- INC-3 AC3 and INC-4 AC6 — both of INC-11's fully-executable named items — now have dated, attributed,
  checkable evidence; `docs/test-report.md`'s INC-11 entry flips both from "deferred" to a dated PASS.
- INC-7 Step 0 passes; INC-7 AC2/AC3 stay open, recorded as open (not silently re-deferred, not silently
  marked done) — `docs/test-report.md`'s INC-11 entry reflects this distinction explicitly.
- INC-10's three live SQL objects (already applied per a prior, uncredentialed session) are now
  independently confirmed present, enabled, and behaviorally correct against the real production database,
  not just reasoned about from a local scratch-database proxy.

---

# Handoff — INC-12 fix cycle 1: REV-116 (DEEP-007 residual) + REV-117 (SQL REVOKE gap)

## Build plan (written before coding)

Reviewer Pass 28 (`docs/review-log.md`) found two majors blocking `v0.1.0`: (1) `run_hourly.py`'s
`config.write_tunables_cache_if_fetched()` — a real `contents: write` commit path — ran unconditionally as
`main()`'s first statement, before checkpoint 1's pause read, so a paused run could still commit to `main`
(REV-116, DEEP-007 not fully closed); (2) `sql/kill_switch_abort_log.sql`'s `REVOKE` omitted `truncate`
(REV-117), the same gap class closed four times before in this codebase. Plan: (a) read
`operational-controls.md` §13.1/§13.6 and `tunables-fallback.md`'s "before the market gate... cache
refreshes on every dispatch" design property to find a fix that closes REV-116 without silently breaking
that property; (b) check `run_discovery.py`/`publish_prices.py` for the same before-checkpoint-1
irreversible-write pattern rather than assuming it's unique to `run_hourly.py`; (c) apply `admin_allowlist`'s
exact four-verb REVOKE shape to `kill_switch_abort_log.sql`, double-apply locally to confirm idempotency;
(d) run full regression + a real-code-path smoke test that doesn't rely on `SKIP_TUNABLES_FETCH` masking.
Files: `scripts/run_hourly.py`, `sql/kill_switch_abort_log.sql` only — no `tests/` edits (qa owns those),
no design-doc edits (tech-lead owns those; flagging the checkpoint-1 placement/§13.1 claim below instead).

## REV-116 — where checkpoint 1 moved, and why

**Checked `run_discovery.py` and `publish_prices.py` first, per the brief's explicit instruction not to
assume the gap is unique to `run_hourly.py`.** Confirmed via `grep -rn write_tunables_cache_if_fetched
scripts/` that only `run_hourly.py` calls it — `write_tunables_cache_if_fetched()`'s own docstring
(`config.py:165-168`) states Decision #28 made `hourly-watchlist.yml` the **sole** writer; `run_discovery.py`
and `publish_prices.py` "never call this; they remain pure read-only consumers." Read both files' `main()`
top-to-bottom directly: `run_discovery.py` goes `require_secrets()` → `client()` → `notifier` → checkpoint 1
with nothing irreversible in between; `publish_prices.py` goes `require_secrets(...)` → `client()` →
watchlist read → a Yahoo-fetch loop (not irreversible) → checkpoint 4 immediately before the file write, and
checkpoint 1 is explicitly out of scope for it per §13.6.2's own text ("FR24's text does not name this
checkpoint for `publish_prices.py`"). **No fix needed in either file** — the pattern genuinely does not
recur there.

**`run_hourly.py` fix: moved checkpoint 1 (the `is_paused()` read) to the very top of `main()`, ahead of
both the tunables-cache write and the market-gate computation, preceded only by its genuine precondition**
(`config.require_secrets("SUPABASE_URL", "SUPABASE_SECRET_KEY")` then `sb = state.client()` — the two
secrets `state.client()` itself needs; `GEMINI_API_KEY` isn't a precondition for reading the pause flag and
stays validated later, right before the AI call, via a second, narrower `require_secrets("GEMINI_API_KEY")`
call further down). Considered the simpler alternative the reviewer also named — leaving checkpoint 1 where
it was and just moving the tunables-write call to after it — but rejected it: `tunables-fallback.md:302-303`
states, as an explicit design property (not just a comment), that the write runs "before the market gate...
so the cache refreshes on every dispatch regardless of whether the market check inside `main()` goes on to
skip work." Checkpoint 1's *old* position was already after the closed-market early return, so moving only
the write (not the checkpoint) down to that position would have made the cache silently stop refreshing on
every closed-market invocation (most of the day) — a real regression of a stated design property, not a
neutral fix. Moving checkpoint 1 itself to the top preserves that property exactly (the cache still refreshes
on every dispatch that isn't paused, open market or not) while also closing REV-116 (nothing irreversible is
reachable before the pause read, full stop). Verified both properties hold by executing the real `main()`
code path directly (see "What a test can honestly prove," below) rather than trusting the property from
reading the diff alone.

**This changes what `operational-controls.md` documents and needs a design-doc correction I did not make
myself:**
- §13.6.2's checkpoint-1 placement text ("Placed immediately after `sb = state.client()` / `notifier =
  notify.get_notifier()` are constructed") is now stale — checkpoint 1 no longer waits for `notifier`, and
  now also precedes the market-gate computation and the tunables-cache write.
- §13.1's accepted-risk paragraph (`operational-controls.md:59-68`) still contains the exact sentence Pass 28
  flagged as false ("no irreversible action possible in that window") — this fix is what makes that sentence
  true again, so it needs updating to describe the corrected window, not deleting outright.
Flagging both per the brief's instruction ("if your fix changes what §13.6 specifies... say so and I will
route the design update to tech-lead") rather than editing `operational-controls.md` myself. Noted in passing:
tech-lead's in-progress edits already on this branch (uncommitted, `git diff docs/design/`) have updated
§13.6.5's REVOKE sample for REV-117 and the top-of-file/§13.6 status lines for the Pass 28 NOT CLEAR verdict,
but have not yet touched §13.1's claim or §13.6.2's checkpoint-1 placement text — both still need the
correction above.

## REV-117 — REVOKE fix + double-apply result

Added `truncate` to `sql/kill_switch_abort_log.sql`'s `REVOKE`, matching `admin_allowlist`'s exact four-verb
shape (`sql/admin_portal_rls.sql:17`, the closest precedent per the brief — no legitimate write path to this
table exists at all, same as `admin_allowlist`):
```sql
revoke insert, update, delete, truncate on public.kill_switch_abort_log from public, anon, authenticated;
```
Updated the file's own comment to name REV-117 and the four prior closures of this same gap class
(REV-081/REV-086/`kill_switch_portal_grant.sql`/REV-099), same convention the file already used.

**Double-apply result (local, not live — the orchestrator is holding this file until fix + reviewer
clearance).** No Docker or PG17 available in this sandbox (checked; Docker daemon unreachable, only
`postgresql-16` installed) — ran against a local **Postgres 16.13** cluster instead (`initdb`/`pg_ctl`
under a throwaway data dir, `anon`/`authenticated` roles created fresh). Nothing in this file is
version-sensitive (no trigger, no PG14+ construct — same conclusion the file's own header comment already
draws), so REVOKE/RLS/FORCE semantics are unchanged across 16→17.6.1 and this remains a faithful proxy, but
it is **not** a PG17.6.1-identical verification — flagging the substitution explicitly rather than silently
presenting it as equivalent.
- **First apply:** `CREATE TABLE` / `ALTER TABLE` ×2 / `REVOKE` all succeeded.
- **Second apply, verbatim, no edits:** `NOTICE: relation "kill_switch_abort_log" already exists, skipping` /
  `CREATE TABLE` (no-op) / `ALTER TABLE` ×2 / `REVOKE` — exit code 0, clean no-op.
- **Verified the actual privilege state, not just a clean exit code:** `\dp public.kill_switch_abort_log`
  shows only `postgres=arwdDxt/postgres` — no `PUBLIC` default grant remains. `set role anon; truncate
  public.kill_switch_abort_log;` and the same under `authenticated` both failed with `permission denied for
  table kill_switch_abort_log`.
- Scratch cluster stopped and its data directory removed afterward; nothing left running.

## What a test can honestly prove about REV-116, given `SKIP_TUNABLES_FETCH`

Per the brief's warning: every committed test runs with `SKIP_TUNABLES_FETCH=true` (`tests/conftest.py`),
which empties `config._TUNABLES` at import time, so `write_tunables_cache_if_fetched()`'s own `if not
_TUNABLES: return` guard makes it a silent no-op regardless of ordering — **no test in the committed suite,
old or new, can distinguish "the call happens after the pause check" from "the call never does anything at
all."** A green suite here proves the checkpoint's *call-site position* is textually correct (e.g.
`test_checkpoint_call_site_counts`) and that nothing else regressed; it does **not** prove the fix actually
prevents the commit path from firing while paused — that requires exercising the pre-fetch-populated path
the suite deliberately skips for determinism.

To actually verify REV-116 is closed, I ran `run_hourly.main()` directly (not through pytest) with
`config._TUNABLES` populated with a real pending value (bypassing the `SKIP_TUNABLES_FETCH` skip) and
`is_paused()` faked to return `True`: `write_tunables_cache_if_fetched()`'s call count was `0` — confirmed
by wrapping the function with a call-counting spy, not by reading print output. A second run with the same
populated `_TUNABLES` and `is_paused()` returning `False` (market closed, no `FORCE_RUN`) showed a call
count of `1`, confirming the "refreshes on every non-paused dispatch, including a closed-market one" property
survived the fix. Neither of these is a committed test (scratch-only, per the brief's scope: qa owns
`tests/`) — **qa should add a permanent test that populates `_TUNABLES`/`_TUNABLE_CASTS` directly (bypassing
`SKIP_TUNABLES_FETCH`) and asserts `write_tunables_cache_if_fetched` is not called when `is_paused()` returns
`True`**, since this is exactly the scenario the existing 22 boundary tests structurally cannot exercise.

## Tests that need updating (qa owns `tests/`, not edited here)

- `tests/test_kill_switch_boundary.py::test_checkpoint1_run_hourly_aborts_before_any_named_side_effect`'s
  docstring ("Checkpoint 1 is placed AFTER `sb = state.client()` / `notifier = notify.get_notifier()` are
  constructed") is now stale — checkpoint 1 no longer waits for `notifier`. The test's actual assertions
  still pass unchanged (it never required notifier construction to happen, only that six named functions are
  never called), so this is a comment-only staleness, not a failing assertion.
- `tests/test_run_orchestration.py::test_all_markets_closed_without_force_run_is_a_noop`'s comment ("main()
  returns before `state.client()` or `state.write_heartbeat()` are ever reached") is also now stale —
  `state.client()` (mocked) and `is_paused()` (against the base `FakeSupabase`, which returns `paused=False`
  by default for any unhandled table) are now both reached before the closed-market check. The test still
  passes (`wire_main.run_heartbeat == {}` is unaffected), same comment-only staleness.
- **New test recommended** (see previous section): a real-`_TUNABLES`-populated, paused-run assertion that
  `write_tunables_cache_if_fetched` is not called — the one scenario this fix cycle's own regression suite
  cannot exercise.

## Files changed

- `scripts/run_hourly.py` — `main()` restructured: checkpoint 1 (`require_secrets` for the two Supabase
  secrets, `state.client()`, `is_paused()`) moved to the top; `write_tunables_cache_if_fetched()` moved to
  right after it; the later `require_secrets()` call narrowed to `"GEMINI_API_KEY"` only (the Supabase pair
  is already validated by then). Checkpoint call-site count unchanged (still exactly 2 `if
  state.is_paused(sb):` occurrences).
- `sql/kill_switch_abort_log.sql` — `REVOKE` gains `truncate`; comment updated to name REV-117 and the prior
  precedent files.

## How to run it

`python3 -m pytest -q --tb=short` (Python suite); `node --experimental-strip-types --test
tests/admin_portal/*.test.ts` (TypeScript suite, unaffected — zero `admin-portal/` files touched this fix
cycle).

## Full regression + smoke test

**Python: 275 passed, 0 failed** (matches the stated baseline exactly — no regressions, no new tests added
by dev per scope). **TypeScript: 82 passed, 0 failed** (matches baseline; unaffected by this fix cycle's
files). Smoke test: the two scratch-harness runs described above (REV-116, real code path, paused vs.
not-paused) plus the full existing `tests/test_kill_switch_boundary.py` (22 tests) and
`tests/test_run_orchestration.py` suites re-run in isolation, all passing.

## Known limitations

- SQL double-apply verification used local Postgres 16, not the live-confirmed PG17.6.1, due to no
  Docker/PG17 availability in this sandbox — semantically equivalent for the REVOKE/RLS/FORCE constructs
  touched, but not a byte-identical version match. Flagged above, not silently substituted.
- Did not apply `sql/kill_switch_abort_log.sql` live, per explicit instruction — still queued, now with the
  REV-117 fix, pending reviewer re-clearance.
- Did not edit `docs/design/operational-controls.md` (§13.1's claim, §13.6.2's checkpoint-1 placement text) —
  flagged above for tech-lead, per scope.
- Did not edit `tests/` — flagged the two stale-comment tests and one recommended new test above for qa.
- An automated environment checkpoint (`git log` commit `3cd13b9`, "checkpoint dev's in-progress REV-116/117
  fixes (UNVERIFIED)") committed `scripts/run_hourly.py`/`sql/kill_switch_abort_log.sql` mid-session, before
  self-verification was complete — same pattern as this file's earlier `b09e65f` note, not a commit I made
  myself. Diffed the checkpoint against my final edits (`git show 3cd13b9 -- scripts/run_hourly.py
  sql/kill_switch_abort_log.sql`) and confirmed it matches the final, tested state byte-for-byte — nothing
  was lost or silently changed. Flagging so the orchestrator doesn't mistake the checkpoint's own "UNVERIFIED"
  label for this handoff's status: full regression (275/0 Python, 82/0 TypeScript) and the real-code-path
  smoke tests above were run against this exact content, after the checkpoint landed.
