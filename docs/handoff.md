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
