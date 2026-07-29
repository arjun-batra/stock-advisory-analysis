# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-7 — Admin portal: track-record view & kill-switch UI (FR31, FR32) — 2026-07-29

**Scope:** `sql/kill_switch_portal_grant.sql` (new), `admin-portal/app/(app)/track-record/page.tsx` (new),
`admin-portal/components/KillSwitchToggle.tsx` (new), `admin-portal/components/AuthGuard.tsx` (nav link +
toggle wiring), `admin-portal/app/(app)/layout.tsx` (docstring only), `admin-portal/app/globals.css`
(styling only). Branch: `claude/admin-portal-evaluation-txaehj`, commit `036e334`. Design:
`docs/design/admin-portal.md` §16.5 (track-record), §16.6 (kill-switch UI); `docs/design/operational-
controls.md` §13 (INC-3 kill-switch backend, context). Acceptance criteria: `docs/design/increment-
plan.md` lines 286-300 (4 ACs). Dev's handoff: `docs/handoff.md`. This is the last increment in the
approved build order.

**Session constraint, same as every prior increment:** no live Supabase network access, no Supabase MCP /
GitHub Actions dispatch tool bound to this session. Every AC requiring a live migration apply, live
RLS/RPC round-trip, or a real dispatch suppression proof could **not** be independently reproduced this
run — reported as **deferred**, not verified. See the per-AC table below.

### SQL grammar review — `sql/kill_switch_portal_grant.sql` (the brief's specific ask, given INC-6's
### `CREATE POLICY ... FOR select, update` bug that survived dev + qa + two reviewer passes)

Read line-by-line against actual PostgreSQL `CREATE POLICY` / `CREATE OR REPLACE FUNCTION` / `GRANT` /
`REVOKE` grammar, independently (not taking dev's "syntax self-check performed" note in the handoff on
trust):

- **`create policy "admin_read_kill_switch" ... for select to authenticated using (public.is_admin());`**
  — `FOR` clause names exactly one command (`select`), not a comma list. This is precisely the class of
  bug that broke `admin_portal_tunables.sql` the first time (REV-091/REV-092) — confirmed fixed here, and
  now locked in as a permanent regression test (`tests/admin_portal/kill_switch_static.test.ts`). Clause
  order (`ON table` → `FOR command` → `TO role` → `USING (expr)`) matches Postgres grammar exactly.
- **`create or replace function public.set_kill_switch(...) ... language plpgsql security definer set
  search_path = '' as $$ ... end; $$;`** — `$$` dollar-quote delimiters are balanced (2 occurrences, one
  open/one close); `declare`/`begin`/`if ... then ... end if;`/`update`/`insert ... values (...);`/`end;`
  structure is syntactically valid; diffed the signature/language/security preamble against
  `sql/kill_switch.sql`'s already-proven-live `set_kill_switch` definition — byte-identical except for the
  new `if auth.uid() is not null and not public.is_admin() then raise exception 'not authorized'; end if;`
  block inserted after `begin`. All object references (`auth.jwt()`, `auth.uid()`, `public.kill_switch_state`,
  `public.kill_switch_audit`, `public.is_admin()`) are schema-qualified, consistent with `search_path = ''`;
  unqualified `now()`/`session_user` resolve correctly regardless (`pg_catalog` and SQL-standard keywords
  are always implicitly searched — same as the proven-live INC-3 original, unchanged in that respect).
- **`grant execute on function public.set_kill_switch(boolean, text) to authenticated;`** — valid GRANT
  grammar, correct function signature (matches the `(boolean, text)` overload).
- **`revoke insert, update, delete, truncate on public.kill_switch_state from public, anon, authenticated;`**
  and **`revoke truncate on public.kill_switch_audit from public, anon, authenticated;`** — valid REVOKE
  grammar (comma-separated privilege lists ARE allowed in `REVOKE`, unlike `CREATE POLICY`'s single-command
  `FOR` clause — dev did not conflate the two, which is exactly where a mistake could plausibly have crept
  in). `kill_switch_audit`'s REVOKE only adds the previously-missing `truncate` verb (confirmed against
  `sql/kill_switch.sql`'s baseline REVOKE, which already had insert/update/delete but not truncate — the
  gap being closed is real, not a redundant no-op). Neither REVOKE touches `SELECT` — the new policy's
  grant is unaffected.
- **REVOKE-doesn't-break-anything reasoning, independently confirmed:** both tables' only legitimate write
  path is `set_kill_switch()`, which is `SECURITY DEFINER` and executes as the function/table owner — REVOKE
  from `public, anon, authenticated` never restricts the owner's own implicit privileges, so the function's
  internal `UPDATE`/`INSERT` are unaffected by this REVOKE. No other code path (application, portal, or
  design doc) claims a legitimate direct authenticated `INSERT`/`UPDATE`/`DELETE` on either table —
  confirmed by re-reading `operational-controls.md` §13.2-§13.3 and `admin-portal.md` §16.6, not inferred.
  Verdict: the REVOKE addition is correct and doesn't regress any legitimate access path.

**No grammar defect found.** All statements are individually valid, balanced, and terminated with semicolons.
This is a strong static signal but — per the same caveat that applied to INC-6's undetected bug — not a
substitute for actually applying the migration against a live Postgres instance, which this session still
cannot do.

### New tests added

- **New `tests/admin_portal/kill_switch_static.test.ts`** (21 tests) — static/source-level checks, same
  convention as `static_source_checks.test.ts`/`tunables_static.test.ts`. Covers: the SQL grammar points
  above as permanent regression tests (not just this session's manual read); AC1's hard boundary (no
  `.reduce`, no win-rate/score/trend keyword, in live code — comment-only mentions of the historical bug
  class or the `latest_call_per_ticker` design decision are excluded via a `codeOnly`-style filter so prose
  doesn't trip the check); every `CALL_LOG_SELECT` field is a raw column or a single `->>'key'` extraction;
  no `.insert(`/`.update(`/`.delete(` anywhere in `track-record/page.tsx` (true read-only); pagination via
  `.range()`, sort via `.order()`, filters via `.ilike()`/`.eq()` only; `KillSwitchToggle` reads
  `kill_switch_state.paused` via the singleton row on mount; the toggle RPC call is
  `set_kill_switch({ p_paused: !paused, p_source: "admin-portal" })` exactly; **`handleToggle` never calls
  `setPaused` directly and always re-reads via `await loadState()` after the RPC call** (locks in the
  design's explicit "not an optimistic flip" requirement, not just presence of a reload call but its
  ordering relative to the RPC); `AuthGuard` renders `<KillSwitchToggle />` and links `/track-record`.
- **Extended `tests/admin_portal/build_bundle.test.ts`** (+2 tests, reusing the existing real-`next-build`
  fixture rather than a second slow build) — `/track-record` appears in the real build's
  `routes-manifest.json` `staticRoutes`, and `server/app/track-record.html` is actually produced
  (statically prerendered), mirroring the established build-bundle pattern for INC-5/INC-6's routes.
- No production code touched by qa, per `CLAUDE.md`.

### Suite results

- **Python:** `python3 -m pytest -q --tb=short` → **201 passed, 0 failed** — identical to the pre-increment
  baseline (this increment touches no Python file; confirmed via `git diff --stat`).
- **Admin-portal JS/TS:** `node --experimental-strip-types --test tests/admin_portal/*.test.ts` →
  **63 passed, 0 failed** (40 pre-existing baseline + 21 new in `kill_switch_static.test.ts` + 2 new in
  `build_bundle.test.ts`).
- **Lint:** `cd admin-portal && npm run lint` → clean, zero errors/warnings.

### Shippability check (real entry point)

`npm run build` (real `next build`, not dev mode) with disposable `qa-test-marker-...` env values:
succeeded, all 8 routes compile (`/`, `/_not-found`, `/auth/callback`, `/holdings`, `/login`,
`/track-record`, `/tunables`, `/watchlist`), TypeScript check passes, `/track-record` statically
prerendered. `next start -p 3313` + `curl`, independently re-run (not reused from dev's handoff claim):
- `GET /track-record` (no session) → 200, renders `AuthGuard`'s "Checking session…" shell — same
  client-side-redirect-after-hydration pattern as every other gated route (`/watchlist`, `/holdings`,
  `/tunables`); RLS is the real server-side gate regardless of what the pre-hydration shell renders.
- `GET /` → 200.
- No server errors in the `next start` log; `.next/` build artifact cleaned up afterward.

### Acceptance criteria — per-AC verdict (`docs/design/increment-plan.md` lines 286-300)

| AC | Verdict | Evidence |
|---|---|---|
| 1. Read-only, paginated `call_log` presentation, no new aggregation/scoring | **PASS — independently re-verified** | `kill_switch_static.test.ts`'s field-shape and no-write-call tests confirm every rendered field is a raw column or single `->>'key'` extraction (matching `latest_call_per_ticker`'s already-proven three-field extraction), no `.reduce`/win-rate/score/trend computation in live code, no `.insert`/`.update`/`.delete` calls. `npm run build` + `next start` confirm the route compiles, statically prerenders, and serves 200. |
| 2. Toggle shows live `paused` on load; flip calls `set_kill_switch(..., p_source:='admin-portal')`, produces `kill_switch_audit` row with `source='admin-portal'`/`actor`=admin email | **Statically verified (independently re-derived, not taken on dev's claim); live RPC/audit round-trip DEFERRED** | `KillSwitchToggle.tsx`'s RPC call body confirmed to pass exactly `{ p_paused: !paused, p_source: "admin-portal" }`; confirmed it re-reads state via `await loadState()` after the RPC rather than optimistically flipping (`setPaused` is never called directly inside `handleToggle`, and the reload happens strictly after the RPC call in source order). `set_kill_switch`'s body (SQL grammar-reviewed above) stamps `actor` from `auth.jwt()->>'email'`. **Cannot verify the live INSERT/UPDATE actually happens** without the migration applied + a real authenticated session (no Supabase MCP access this session). |
| 3. Pause via portal → subsequent dispatch makes no `pg_net` call | **DEFERRED, needs live Supabase** | Confirmed via `git diff --stat` that `sql/scheduler_pgcron.sql` (where `dispatch_github_workflow`'s pause-check lives, per `operational-controls.md` §13.1) is untouched by this commit — this increment only adds a second caller to the same `kill_switch_state.paused` flag, no new dispatch-suppression logic to verify beyond AC2's live-write gap above. |
| 4. Full INC-5/INC-6 regression holds | **PASS** | See Suite results above: 201/201 Python (0 regressions, no Python file touched), 63/63 admin-portal JS/TS (40 pre-existing baseline all still pass unmodified + 23 new). `static_source_checks.test.ts`'s AC6/AC7 checks (no secret-looking string, no dynamic `process.env[...]`, `admin_allowlist` zero-policy shape, `is_admin()` shape) and `tunables_static.test.ts` (INC-6) all still pass unchanged. |

### SQL/code review beyond the ACs (per the brief's explicit ask)

- **`sql/kill_switch_portal_grant.sql` grammar:** no defect found — see dedicated section above. This is
  the strongest available signal this session; live application remains the final confirmation step
  (orchestrator's job, same as every prior increment's SQL).
- **REVOKE correctness (TRUNCATE-grant gap closure):** confirmed correct — see reasoning above. Does not
  remove any legitimate access path; matches the `admin_allowlist` (REV-081) precedent exactly.
- **`admin-portal/app/(app)/track-record/page.tsx` AC1 hard boundary:** confirmed via both manual read and
  a new permanent regression test — no derived-analytics code exists.
- **`KillSwitchToggle.tsx`/`AuthGuard.tsx`/`layout.tsx`/`globals.css`:** all match the design/handoff
  description exactly (`git diff 7f0a18c 036e334` read in full) — nav link, toggle wiring inside
  `AuthGuard`'s shared header (not `layout.tsx`, matching the design's "shared header, not a standalone
  page" text and INC-6's own precedent for the same reasoning), CSS additions scoped to the two new badge
  classes plus one new `--ok` variable in both light/dark `:root` blocks.

**No functional bugs found.** No production code modified by qa.

### Verdict

**PASS.** Python: 201/201 passed (0 regressions, no Python file touched by this increment). Admin-portal
JS/TS: 63/63 passed (40 pre-existing baseline unchanged + 23 new: 21 in `kill_switch_static.test.ts`, 2 in
`build_bundle.test.ts`). Shippability: real `next build` + `next start` serves `/track-record` and every
other route correctly, zero server errors. SQL grammar reviewed line-by-line against actual PostgreSQL
`CREATE POLICY`/`CREATE OR REPLACE FUNCTION`/`GRANT`/`REVOKE` syntax — no defect found, and the specific
class of bug that broke INC-6 (`FOR select, update` comma list) is now a permanent regression test. AC1,
AC4 fully independently re-verified this session; AC2 statically verified (RPC call shape, re-read-not-
optimistic-flip ordering) with the live round-trip deferred; AC3 confirmed via diff-scope (no dispatch
logic touched) with the live suppression proof deferred. All AC2/AC3 live-verification gaps require
Supabase MCP/live-session access this environment does not provide — same constraint as every prior
increment this delivery. This is the last increment in the approved build order; qa's remaining work is
the closure end-to-end pass once `sql/kill_switch_portal_grant.sql` is applied live.

---

## Open bugs

None open. (BUG-003, filed and fixed during INC-6, is archived with that run — see
`docs/archive/test-report-archive.md`.)
