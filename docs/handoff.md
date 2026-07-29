# Handoff — INC-5: Admin portal foundation (FR27, FR28, FR29, NFR5, NFR6)

## Post-handoff fixes (2026-07-29): reviewer Pass 16 REV-081 / REV-083

Reviewer's Pass 16 (`docs/review-log.md`) held INC-5 NOT CLEAR on two findings. Both fixed in this
pass; **the SQL fix (REV-081) is applied to the repo file only — it still needs to be applied live to
production separately (see below).**

**REV-081 [SECURITY, minor] — `admin_allowlist` TRUNCATE grant not covered by RLS.** RLS governs
SELECT/INSERT/UPDATE/DELETE, not TRUNCATE, so Supabase's default full-table grant left
`anon`/`authenticated` with a live (if not currently PostgREST-exploitable) TRUNCATE privilege on
`admin_allowlist`, despite RLS-enabled-zero-policies. Fixed in `sql/admin_portal_rls.sql` by adding,
immediately after `alter table public.admin_allowlist enable row level security;`:

```sql
revoke insert, update, delete, truncate on public.admin_allowlist from public, anon, authenticated;
```

matching the existing REVOKE pattern already used for `kill_switch_audit` in `sql/kill_switch.sql`.
Also tightened the file's adjacent comment so it no longer overclaims that RLS-zero-policies alone
blocks all access (it doesn't cover TRUNCATE) and notes the REVOKE closes that specific gap.

**File edit is done. Production is NOT yet patched** — `sql/admin_portal_rls.sql` was already applied
live to project `ikghqdtlbwifwnooytmm` as part of INC-5's original rollout, before this fix existed, so
this REVOKE statement must be run against the live project separately by whoever has Supabase
write/SQL-editor access. Dev does not have that access in this session.

**REV-083 [evidence-trail, minor] — AC8 live audit result was never recorded in a repo artifact.**
`docs/test-report.md`'s GAP-001 flagged that the orchestrator's live `execute_sql` verification of
AC8 (the REV-034 grant/policy audit) existed only as tribal knowledge, not a durable artifact. Recorded
below.

### AC8 / REV-034 live grant-and-policy audit — raw evidence

**Date:** 2026-07-29. **Run by:** orchestrator, live query via Supabase MCP `execute_sql` against
project `ikghqdtlbwifwnooytmm`.

```
-- RLS enabled check
select relname, relrowsecurity, relforcerowsecurity from pg_class
where relname in ('admin_allowlist','watchlist','holdings');
=>
 admin_allowlist | rls_enabled=true | rls_forced=false
 holdings        | rls_enabled=true | rls_forced=false
 watchlist       | rls_enabled=true | rls_forced=false

-- policies
select tablename, policyname, cmd, roles, qual, with_check from pg_policies
where tablename in ('admin_allowlist','watchlist','holdings');
=>
 admin_allowlist: (zero rows — no policies, as designed)
 holdings.admin_write_holdings: ALL, {authenticated}, qual=is_admin(), with_check=is_admin()
 watchlist.admin_write_watchlist: ALL, {authenticated}, qual=is_admin(), with_check=is_admin()
 watchlist."anon read watchlist": SELECT, {anon}, qual=true, with_check=null  (pre-existing, unrelated to INC-5)

-- is_admin() shape
select proname, prosecdef, pg_get_function_result(oid) from pg_proc
where proname='is_admin';
=>
 is_admin | security_definer=true | returns=boolean

-- grants on admin_allowlist (this is what surfaced REV-081)
select grantee, privilege_type from information_schema.role_table_grants
where table_name='admin_allowlist';
=>
 anon and authenticated both held full default grants (SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER)
 before the REV-081 fix; RLS blocked the four DML verbs but not TRUNCATE. See REV-081.
```

This closes `docs/test-report.md`'s GAP-001 (AC8 now has a reviewable evidence trail) and is the raw
result underlying AC6/AC8's independently-confirmed status in that file's per-AC table.

## Post-handoff bug fix (2026-07-29): production build never inlined the Supabase env vars

**Symptom:** every production build on Vercel threw `Missing required environment variable
NEXT_PUBLIC_SUPABASE_URL` at runtime in the browser, even with both `NEXT_PUBLIC_*` vars correctly
set in Vercel project settings. Extensive Vercel-side debugging (var names, environment scoping, root
directory, redeploys, custom domain caching) found nothing wrong, because the bug was never on that
side.

**Root cause:** `lib/supabase-client.ts`'s `requiredEnv(name)` read the var via `process.env[name]` —
a *dynamic/computed* property access (bracket notation with a variable). Next.js/webpack's
`NEXT_PUBLIC_*` build-time inlining only recognizes a *literal, static* `process.env.EXACT_NAME`
expression written in source; it cannot statically resolve that `name` would be
`"NEXT_PUBLIC_SUPABASE_URL"` at runtime, so the reference was never replaced, and the dynamic lookup
returned `undefined` in the browser on every production build, regardless of what was set in the
deploy environment.

Searched the rest of `admin-portal/` for the same anti-pattern (`grep -rn "process\.env\[" admin-portal`
excluding `node_modules`/`.next`) — the only match was this one call site. `app/auth/callback/route.ts`
already reads the same two vars via literal `process.env.NEXT_PUBLIC_SUPABASE_URL!` /
`process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!` (static, correct) — that file was not affected.

**Why the original `next dev` smoke test (recorded above) didn't catch it:** `next dev` resolves
`process.env` more permissively than an optimized production build and doesn't rely on the same
static-replacement/dead-code-elimination pass — this bug is production-build-specific. Smoke-testing
only via `next dev` is not sufficient evidence for any code path that touches `NEXT_PUBLIC_*` inlining.

**Fix — `admin-portal/lib/supabase-client.ts`:** `requiredEnv` now takes the already-resolved value as
a second parameter instead of doing the lookup itself; each call site passes it via a literal
`process.env.NEXT_PUBLIC_SUPABASE_URL` / `process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY` expression, so
webpack/Turbopack can find and statically replace each one at build time:

```ts
function requiredEnv(name: string, value: string | undefined): string { ... }

export function createClient() {
  return createBrowserClient(
    requiredEnv("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
    requiredEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)
  );
}
```

**Verification (corrected method — production build + built-output inspection, not `next dev`):**
1. `NEXT_PUBLIC_SUPABASE_URL=<real url> NEXT_PUBLIC_SUPABASE_ANON_KEY=<real anon key> npm run build`
   (Next.js 16.2.12, Turbopack) — compiles and generates all 6 routes with zero errors.
2. Inspected the built client chunk directly rather than inferring from absence of an error:
   `grep -o '.\{40\}ikghqdtlbwifwnooytmm[^"]*"' .next/static/chunks/*.js` found
   `s_("NEXT_PUBLIC_SUPABASE_URL","https://ikghqdtlbwifwnooytmm.supabase.co"` and the equivalent for
   `NEXT_PUBLIC_SUPABASE_ANON_KEY` — the real values are baked into the minified JS as literals, proving
   the static replacement happened at build time.
3. Negative control: rebuilt with **no** env vars set. The same chunk instead contained the unresolved
   expression `w.default.env.NEXT_PUBLIC_SUPABASE_URL` (no literal value baked in) — confirms the check
   is real (reflects actual build-time env) and not a false-positive pass.
4. `npm run start` (production server, not `next dev`) with the real vars set — `/login` returns 200
   and renders correctly, no thrown error, clean server log.
5. `python3 -m pytest -q --tb=short` — 171 passed, 0 failures (no-op as expected; change is scoped to
   `admin-portal/` TypeScript only). Note bare `pytest` on PATH resolves to an isolated `uv tool`
   install missing `supabase`/`yfinance` — use `python3 -m pytest`, per the note already in this file.

**Lesson for future increments touching `NEXT_PUBLIC_*` vars:** a `next dev` smoke test is not
sufficient evidence that env-var inlining works. Verify with an actual `npm run build` + inspection of
the built `.next/static/chunks/*.js` output for the literal value (not just absence of a runtime
error), before handoff.

**Files touched:** `admin-portal/lib/supabase-client.ts` only.


Branch: `claude/admin-portal-evaluation-txaehj` (same batching note as INC-3/INC-4 — no new `inc-N`
branch cut).

**Design:** `docs/design/admin-portal.md` §16.1–§16.3, §16.7–§16.8. **Plan/AC:**
`docs/design/increment-plan.md` "### INC-5 — Admin portal: auth, hosting, watchlist & holdings CRUD".
Traces to `docs/requirements.md` FR27–FR29, NFR5, NFR6.

## Files changed

- **New `admin-portal/`** — Next.js 16 (App Router, TypeScript) app, project root for Vercel deployment.
  Scaffolded via `create-next-app`, then trimmed to exactly the design's file list (§16.8) plus small
  supporting helpers:
  - `lib/supabase-client.ts` — the browser Supabase client (`@supabase/ssr`'s `createBrowserClient`,
    anon key + session). Used by every feature; no server-side data path.
  - `lib/admin-guard.ts` — `checkAuthorization()`, the pure-ish allowlist-check helper (session ->
    `is_admin()` RPC -> sign-out-and-reject if false). Kept out of the React component so the
    authorization decision logic is isolated from rendering.
  - `lib/validation.ts` — pure validation functions (`validateWatchlistRow`, `validateHoldingsRow`)
    mirroring `sql/schema.sql`'s CHECK constraints 1:1, no invented rules.
  - `components/AuthGuard.tsx` — client component wrapping every authenticated route; redirects to
    `/login` (no session) or `/login?error=not_authorized` (signed-in but not on the allowlist, after
    signing the user out). Renders the shared nav/header for authorized sessions.
  - `app/login/page.tsx` — Google OAuth sign-in button only. No email/password or magic-link UI
    anywhere in this file or any other file (`grep -rniE "password|magic.?link" admin-portal/app
    admin-portal/lib admin-portal/components` returns zero matches).
  - `app/auth/callback/route.ts` — standard Supabase Auth/Next.js PKCE code-exchange route
    (`@supabase/ssr`'s `createServerClient`, cookies from `next/headers`). Anon key only, no secret;
    the only server-side code in the portal.
  - `app/(app)/layout.tsx`, `app/(app)/watchlist/page.tsx`, `app/(app)/holdings/page.tsx` — the
    shared authenticated layout (a route group; the parens don't affect the URL, so these still serve
    at `/watchlist` and `/holdings` per the design's file list) wrapping the FR28/FR29 CRUD screens.
    Both screens: list + inline edit + delete + add form, client-side Supabase calls, DB error
    messages surfaced verbatim on failure (so an RLS rejection is visible, not swallowed).
  - `app/page.tsx` — root route, pure redirect target (`/` -> `/watchlist` if authorized, else
    `/login` or `/login?error=not_authorized`).
  - `app/layout.tsx`, `app/globals.css` — minimal shared shell/styling, no external font fetch.
  - `.env.example` — documents the two `NEXT_PUBLIC_*` vars (see "How to deploy" below). `.gitignore`
    (create-next-app default) ignores `.env*` with `!.env.example` added so the example stays tracked
    while `.env.local` never is.
  - Removed create-next-app boilerplate not needed here: default `CLAUDE.md`/`AGENTS.md` stubs, sample
    SVGs, the default landing page content.
- **New `sql/admin_portal_rls.sql`** — `admin_allowlist` (RLS enabled, zero policies — REV-033),
  `is_admin()` (`returns boolean`, no arguments, `SECURITY DEFINER`, exact signature from
  `admin-portal.md` §16.2 —**not changed from the design doc's block**, since INC-6 has a hard,
  literal dependency on this signature), and the `admin_write_watchlist` / `admin_write_holdings`
  policies (`for all to authenticated using (is_admin()) with check (is_admin())`), copied verbatim
  from §16.2/§16.3.

**Not touched:** no `scripts/*.py` file (`git diff --stat -- scripts/` is empty), no other `sql/*.sql`
file, no `.github/workflows/*` file.

## Acceptance criteria status

**Self-verifiable now (done):**
- **AC6** — PASS. `grep -n "admin_allowlist\|is_admin()" sql/admin_portal_rls.sql` shows both new write
  policies (`admin_write_watchlist`, `admin_write_holdings`) call `public.is_admin()` in both `using`
  and `with check`; `admin_allowlist` has `enable row level security` and zero `create policy`
  statements for it anywhere in the file (matches REV-033's fix).
- **AC7** — PASS. `grep -rniE "service_role|SUPABASE_SERVICE|GEMINI_API_KEY|GITHUB_TOKEN|_PAT\b|
  client_secret" admin-portal/app admin-portal/lib admin-portal/components sql/admin_portal_rls.sql`
  returns zero matches. Only two env vars are referenced anywhere in the portal's source
  (`grep -rn "process\.env" admin-portal/app admin-portal/lib`):
  `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Ran a real production build with
  those two vars set and inspected the built `.next` output directly: the anon/publishable key appears
  (expected — it's the intentionally-public client key, same posture as `pages/common.js`'s hardcoded
  key), and the only `service_role`/`sb_secret_` string matches anywhere in the build output are
  `@supabase/ssr`'s/`supabase-js`'s own bundled JSDoc comments warning callers never to expose a
  service_role key in the browser — library documentation text, not an embedded credential; this
  portal's code never imports or calls any `supabase.auth.admin.*` API.
- **Build** — PASS. `npm run build` (Next.js 16.2.12, Turbopack) compiles, typechecks
  (`tsc` via the build), and generates all 6 routes (`/`, `/login`, `/auth/callback`, `/watchlist`,
  `/holdings`, `/_not-found`) with zero errors. `npm run lint` (eslint) is clean, zero errors/warnings.
- **Smoke test** — PASS. Ran `next dev` locally against the real (already-public) Supabase URL/anon
  key from `pages/common.js`. All 5 routes return the expected status (`/login` 200 with a rendered
  "Sign in with Google" button and no password/magic-link text, `/` 200, `/watchlist` 200 rendering
  the `AuthGuard`'s "Checking session…" shell before the client-side redirect fires, `/holdings` 200
  same shell, `/auth/callback` with no `code` param 307-redirects to `/login?error=auth_failed`). No
  server errors in the dev log. Could not smoke-test an actual authenticated round-trip (Google OAuth
  consent screen requires a real browser + Arjun's allowlisted account) — that's AC1–AC3.
- **Full Python regression** — PASS both before and after this increment: `python3 -m pytest -q
  --tb=short` -> 171 passed (baseline was also 171; this increment adds zero Python files, confirmed
  via `git diff --stat -- scripts/` being empty). Note: `pytest` on PATH resolves to an isolated `uv
  tool` install without `supabase`/`google-genai` installed — use `python3 -m pytest` (repo-root
  `dist-packages` has the real deps), not bare `pytest`.
- **AC8** — PASS. See "AC8 / REV-034 live grant-and-policy audit — raw evidence" above (the
  post-handoff fixes section, REV-083) for the raw live query results and how they resolve REV-034.

**Deferred — need live deployment/live Supabase, per your instruction not to fake these (I don't have
Vercel or write access to the live Supabase project in this session):**
- **AC1–AC3** (deployed URL, redirect-to-Google, non-allowlisted reject, allowlisted admin reaches the
  app) — need a real Vercel URL + `admin_portal_rls.sql` applied + Google OAuth actually configured
  (Arjun's already done the OAuth/dashboard side per your note).
- **AC4–AC5** (CRUD writes confirmed via direct Supabase query; anon-key-no-session REST write rejected
  by RLS) — need the migration applied to the live project.

## How to run locally

```
cd admin-portal
cp .env.example .env.local   # fill in the two NEXT_PUBLIC_* values
npm install
npm run dev                  # http://localhost:3000
```

## How to deploy (for Arjun — exact steps)

1. **Apply the migration first.** Run `sql/admin_portal_rls.sql` against the live Supabase project (SQL
   editor or migration tool), then manually seed your admin email:
   `insert into public.admin_allowlist (email) values ('<your-google-account-email>');`
   (not baked into the migration on purpose — see the file's comments).
2. **Vercel project settings:**
   - **Root Directory:** `admin-portal`
   - **Framework Preset:** Next.js (auto-detected)
   - **Build Command:** `npm run build` (default — no override needed)
   - **Output Directory:** `.next` (default — no override needed)
   - **Install Command:** `npm install` (default)
3. **Environment variables** (Project Settings -> Environment Variables, all environments):
   - `NEXT_PUBLIC_SUPABASE_URL` = your Supabase project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = your Supabase anon/publishable key
   - No other variable is needed or used — do not add a service-role key or any other secret; the
     portal has no server-only credential anywhere (§16.7).
4. **Supabase Auth dashboard:** confirm Google is the only enabled provider (you've said this is
   already done) and that the OAuth redirect URL allow-list includes
   `https://<your-vercel-domain>/auth/callback`.
5. Deploy. Visiting the root URL logged-out should redirect to `/login`.

## Known limitations

- No `app/api/` routes beyond the auth callback, no server-only secret, exactly per §16.8 — confirmed
  by design, not just by omission.
- `app/tunables/`, `app/track-record/`, and the kill-switch UI are intentionally **not** built — out of
  scope for INC-5 (INC-6/INC-7). No stub pages or nav links exist for them; the shared header only
  links to Watchlist/Holdings.
- The holdings "add" form only lets you pick a ticker that already exists in `watchlist` (a dropdown,
  not free text) — this mirrors the FK constraint (`holdings.ticker references watchlist(ticker)`)
  rather than relying solely on the DB to reject an invalid ticker after the fact.
- `npm audit` reports 12 high-severity advisories, all in **dev-only** tooling transitively pulled in
  by `eslint-config-next`/`postcss` (not runtime/production dependencies) — `npm audit fix --force`
  would force a breaking `eslint` major-version bump; left alone for this increment since it doesn't
  affect the deployed app. Worth a follow-up `npm audit fix --force` + lint re-check in a later
  increment if Arjun wants it addressed.
