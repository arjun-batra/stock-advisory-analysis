# Admin portal

Part of `docs/design.md`'s module split. See `docs/design.md` for the index, module map, §0
load-bearing decisions, increment plan, and requirement coverage map — read that first for
orientation. Section number below (§16) continues the pre-split numbering; §15 (coverage map) stays in
`docs/design.md` itself.

**Status: DRAFT** — covers the 2026-07-26 change request (FR27–FR32, NFR5, NFR6). Not yet implemented;
increments INC-5, INC-6, INC-7 build this (see `docs/design.md`'s increment plan). Pending GATE 3.

**New trust boundary — read this file in full before changing any of it.** Every other surface in this
system is either read-only-and-public (dashboard, detail page) or has no human-authenticated caller at
all (the workflows use the Supabase secret key server-side). This is the **first** write-capable,
human-authenticated surface. NFR6 asks for this explicitly: design the auth/RLS/secrets handling
carefully, not by analogy to the read-only surfaces.

---

## 16. Admin portal architecture (FR27–FR32, NFR5, NFR6)

### 16.1 Hosting & stack (Decision #23)

- **Frontend + backend:** Next.js (App Router) app in a new `admin-portal/` directory in this same
  repo, deployed to **Vercel** with the project root set to `admin-portal/`. Same repo as the rest of
  the system (not a separate repo) — consistent with the existing "public repo, $0 hosting" posture; no
  secrets live in the portal's client-side code (NFR6), so a public repo is not a new exposure.
  Next.js gives both the static/SSR frontend and serverless **API routes** (Vercel Functions) in one
  deploy — the API routes are the only place the GitHub PAT is ever used (§16.4).
- **Auth:** Supabase Auth, **Google OAuth as the only enabled provider** — email/password and
  magic-link are disabled in the Supabase Auth dashboard config (an ops/config step at INC-5, not code;
  dev confirms and records it in `docs/handoff.md`). No anonymous access; every read/write from the
  portal (except the tunables proxy, see §16.4) goes through the Supabase JS client carrying the signed-in
  user's session JWT.
- **Cost (NFR5):** Vercel Hobby tier (free) and Supabase Auth (free, included in the existing free-tier
  Supabase project) are expected to cover single-user traffic with no new recurring spend; any overage
  still falls under NFR1's $0–15/mo cap, not a separate budget — no new tier commitment needed at design
  time.

### 16.2 Authorization model — who is "the admin"

Google OAuth by itself only proves *a* Google account signed in — it does **not** restrict *which*
Google account can. Since this is explicitly a single-user system (Arjun only), authorization is a
second, independent gate on top of authentication:

```sql
-- INC-5: first migration that needs a Supabase Auth identity to check against.
create table public.admin_allowlist (
  email text primary key
);
-- Seeded once, manually, with Arjun's Google account email (an ops step at INC-5
-- rollout — the email itself isn't a secret, but it's not a literal baked into
-- migration SQL either; insert it via the SQL editor at deploy time).

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(auth.jwt() ->> 'email', '') in (select email from public.admin_allowlist);
$$;
```

`is_admin()` is the **single source of truth** for "is this caller allowed to write" — every RLS policy
below and the kill-switch function (INC-7, `operational-controls.md` §13.3) call it, so there is exactly
one place to audit or change who's authorized.

**Defense in depth (three independent layers, not just one):**
1. **RLS (the real enforcement).** Every write policy below is gated on `is_admin()`. This holds even if
   the frontend has a bug — a malicious or buggy client can't write past it.
2. **Portal UI check.** Immediately after Google sign-in, the frontend checks the signed-in email against
   `admin_allowlist` (via a lightweight authenticated read or an `is_admin()` RPC call) and **signs the
   user out immediately** with a visible "not authorized" message if it doesn't match — this is a UX
   improvement (a clear rejection instead of a confusing wall of failed writes), not the actual security
   boundary; RLS is.
3. **Server-side re-verification for the tunables proxy** (§16.4) — the one path that touches a secret
   (the GitHub PAT) never trusts the client's "I'm an admin" claim; it re-checks server-side against
   Supabase using the request's own session token before doing anything.

### 16.3 Watchlist & holdings CRUD (FR28, FR29)

No new backend needed — the portal's browser-side Supabase client (anon/publishable key + the user's
session JWT) talks to `watchlist` and `holdings` directly; RLS is the authorization boundary.

```sql
create policy "admin_write_watchlist" on public.watchlist
  for all to authenticated
  using (public.is_admin())
  with check (public.is_admin());

create policy "admin_write_holdings" on public.holdings
  for all to authenticated
  using (public.is_admin())
  with check (public.is_admin());
```

(`watchlist` keeps its existing anon-SELECT policy from `data-and-flow.md` §5, untouched — this is an
**additional** `authenticated`-role policy, not a replacement. `holdings` currently has RLS enabled with
**no** policies at all, i.e. zero anon/authenticated access — this is the first policy it gets.)

**Fields (from `data-and-flow.md` §5):** `watchlist` — ticker, market (US/TSX/NSE), type
(held/watch-only), status; `holdings` — ticker, shares (>0), cost_basis (>0), currency
(USD/CAD/INR — matches the ticker's market). The portal's forms mirror these columns and their existing
CHECK constraints 1:1; no new validation rules invented beyond what the DB already enforces.

### 16.4 Tunables editor (FR30)

**Source of truth stays GitHub Actions Variables (Decision #24)** — the portal is a write-through client,
never a second config store. The only server-side secret in this whole feature is a GitHub PAT with
`actions:write` scope on this repo, held in a Vercel **server-only** environment variable (not
`NEXT_PUBLIC_*`), used exclusively inside one Next.js API route:

```
GET  /api/tunables         -> for each of the 10 curated keys, read the live GitHub Actions Variable
                               value (GitHub REST: GET /repos/{owner}/{repo}/actions/variables/{name})
                               and pair it with static metadata (description, example, workflow-YAML
                               fallback default) shipped in the portal codebase.
POST /api/tunables         -> { key, value } -> re-verify the caller is an authenticated admin
                               (server-side: validate the Supabase session token against
                               admin_allowlist using the Supabase SERVICE/secret key from the server
                               route — never the client's anon key/session alone), reject with 401/403
                               otherwise; then PATCH the corresponding GitHub Actions Variable
                               (PATCH /repos/{owner}/{repo}/actions/variables/{name}) using the PAT.
```

**Curated field metadata** (FR30 — description + example + current value per field, never a bare input
box) is a small static array in the portal codebase, one entry per key:

```ts
type TunableField = {
  key: string;              // GitHub Actions Variable name
  description: string;      // human-readable purpose
  example: string;          // an example legal value
  workflowDefault: string;  // the literal fallback baked into the workflow YAML when the Variable
                             // is unset — shown as "(using default)" so "current effective value"
                             // is never blank just because no one has ever touched this key
  kind: "string" | "number" | "boolean";
};
```

The 10 keys (verbatim from FR30 / `requirements.md` §10's portal-exposure note): `GEMINI_MODEL`,
`GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`, `DISCOVERY_LOSER_PCT`,
`DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_MARKET_CAP_INR`,
`DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`. No other tunable is reachable from this UI.

**`GEMINI_MODEL_BACKUP` special case:** unlike the other keys, an *unset* `GEMINI_MODEL_BACKUP` Variable
does not fall back to a literal model string — it **disables the fallback model entirely** (empty env →
`config.py`'s `if m` filter drops it; `components.md` §4.4, `hourly-watchlist.yml` comment). This key's
`workflowDefault` metadata must say "unset = fallback disabled," not a model name, or the portal would
display a misleading "current effective value."

> ### ⚠️ OPEN DESIGN GAP — found while designing this increment, needs Arjun's/pm's sign-off before INC-6 starts
>
> FR30 and Decision #24 both assume "the portal edits [GitHub Actions Variables] the system already
> reads at runtime." **That's only true for 2 of the 10 curated keys today.** Verified against the live
> workflow YAML (`.github/workflows/hourly-watchlist.yml`, `daily-discovery.yml`):
> - `GEMINI_MODEL` / `GEMINI_MODEL_BACKUP` — ✅ already wired as `${{ vars.X }}` in
>   `hourly-watchlist.yml`. The portal editing these Just Works with no other change.
> - `ALERTS_ENABLED` — ❌ currently wired to the `workflow_dispatch` **input**
>   `${{ inputs.alerts_enabled }}` in **both** workflows, not a Variable. A scheduled (pg_cron,
>   no-inputs) dispatch always gets the YAML input default (`true`); there is no GitHub Actions
>   Variable named `ALERTS_ENABLED` today. Writing one via the portal would have **zero effect** on any
>   real scheduled run.
> - The seven `DISCOVERY_*` keys — ❌ not present in `daily-discovery.yml`'s `env:` block at all. They
>   are pure `os.environ.get(name, <literal default>)` reads in `scripts/config.py` that always resolve
>   to the Python literal today, because the workflow never passes them through as env vars. Setting a
>   GitHub Actions Variable for any of these today would also have **zero effect**.
>
> **My recommended resolution (concrete enough for dev to build against, but flagging for explicit
> confirmation since it touches production workflow YAML and one documented safety mechanism):**
> 1. **The seven `DISCOVERY_*` keys** — mechanical, zero behavioral risk: add
>    `${{ vars.KEY || '<existing literal default>' }}` env lines to `daily-discovery.yml`'s `env:`
>    block, exactly mirroring the already-working `GEMINI_MODEL` pattern. Unset Variable → identical
>    behavior to today (same literal falls through). I'm confident recommending this outright; it's the
>    same pattern already used four times in this codebase.
> 2. **`ALERTS_ENABLED`** — this one is a genuine judgment call, because `inputs.alerts_enabled` is the
>    documented **safe forced-test pattern** (`components.md` §4.1: "for any off-hours forced run, set
>    `ALERTS_ENABLED=false`") and I don't want the portal's toggle to silently weaken it. Recommended
>    design: keep the *input* wiring exactly as-is (unchanged manual-dry-run behavior), and **AND-gate**
>    it with a new, independent `vars.ALERTS_ENABLED` Variable that the portal controls:
>    ```yaml
>    ALERTS_ENABLED: ${{ inputs.alerts_enabled }}        # unchanged — manual dry-run override
>    ALERTS_ENABLED_VAR: ${{ vars.ALERTS_ENABLED || 'true' }}   # new — portal-controlled global mute
>    ```
>    ```python
>    # scripts/config.py — additive, one new line, fully backward compatible when the new
>    # Variable is unset (defaults to "true", so the AND is a no-op and behavior is unchanged):
>    _alerts_input = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"
>    _alerts_var = os.environ.get("ALERTS_ENABLED_VAR", "true").lower() == "true"
>    ALERTS_ENABLED = _alerts_input and _alerts_var
>    ```
>    Effect: the portal's `ALERTS_ENABLED` toggle can only ever **suppress** alerts (never force them on
>    over an explicit manual dry-run request), and every existing scheduled/manual run keeps its exact
>    current behavior until an operator actually touches the new Variable. This is *not* a duplicate of
>    the kill-switch (FR24 explicitly rejects "alerts-only suppression" as the kill-switch's mechanism;
>    this is the softer, already-intended-by-FR30 sibling control — checks/AI calls/logging still run,
>    only the push is muted, same as today's dry-run behavior).
>
> **Why this is flagged rather than just built:** it means INC-6's file scope is not "the portal
> codebase alone" — it also touches `daily-discovery.yml`, `hourly-watchlist.yml`, and
> `scripts/config.py` (production dispatch/safety-toggle files), which is bigger than "build a portal
> that edits variables the system already reads." Routing to pm/Arjun per the no-inference rule before
> INC-6 starts, not guessing silently on a change to a documented safety mechanism. If Arjun prefers a
> different resolution (e.g., trim FR30's curated list to only the 2 keys that already work, deferring
> the rest), that's a requirements.md change pm would take back through the CR process — either answer
> is buildable from here once confirmed.

### 16.5 Track-record view (FR31)

Read-only. Reuses the existing `latest_call_per_ticker` view / direct `call_log` reads
(`data-and-flow.md` §5) via the same anon/publishable-key pattern the dashboard already uses — no new
RLS needed (the anon SELECT policy on `call_log` already covers it), no new backend route. "Cleaner
presentation" (FR31) means pagination/sorting/filtering in the UI only — **no new aggregation, scoring,
or trend computation** beyond what `call_log` already stores; this is a hard boundary per FR31's text and
the requirement coverage map should be checked against it at review time (a portal that starts computing
win-rate-since-alert or similar would be scope creep back into the analytics layer FR16 explicitly kept
out of v1).

### 16.6 Kill-switch UI (FR32)

Depends on `operational-controls.md` §13 (INC-3) already existing. Two additive changes to that
increment's objects, made in INC-7:

```sql
-- extend set_kill_switch (INC-3) with admin authorization once callers can be authenticated:
create or replace function public.set_kill_switch(
  p_paused boolean, p_source text default 'sql-direct'
) returns void
language plpgsql security definer set search_path = '' as $$
declare v_actor text := coalesce(auth.jwt() ->> 'email', session_user);
begin
  if auth.uid() is not null and not public.is_admin() then
    raise exception 'not authorized';
  end if;
  update public.kill_switch_state
     set paused = p_paused, updated_at = now(), updated_by = v_actor where id = true;
  insert into public.kill_switch_audit(action, actor, source)
  values (case when p_paused then 'pause' else 'resume' end, v_actor, p_source);
end; $$;

grant execute on function public.set_kill_switch(boolean, text) to authenticated;

create policy "admin_read_kill_switch" on public.kill_switch_state
  for select to authenticated using (public.is_admin());
```

`auth.uid() is null` (no Supabase Auth session — i.e. called via the SQL editor or a service-role
connection) still bypasses the admin check entirely, preserving INC-3's original "trusted direct SQL
access" path unchanged. An `authenticated`-role caller (the portal) is now required to pass `is_admin()`.
Portal UI: reads `kill_switch_state.paused` on load to show current state, calls
`supabase.rpc('set_kill_switch', { p_paused: !current, p_source: 'admin-portal' })` on toggle. Because
this operates on the exact same flag/function as FR24's backend, FR25's monitor pause-awareness and
FR26's audit logging apply automatically — no new logic needed here, only the UI wiring and the two
grants above.

### 16.7 Secrets inventory (NFR6 traceability)

| Secret | Lives in | Never appears in |
|---|---|---|
| GitHub PAT (`actions:write`) | Vercel server-only env var (e.g. `GITHUB_ACTIONS_PAT`), read only inside `/api/tunables` | Client bundle, `NEXT_PUBLIC_*` vars, git history, browser network responses |
| Supabase anon/publishable key | Vercel `NEXT_PUBLIC_SUPABASE_ANON_KEY` (client-side, by design — this is the low-privilege key, RLS-gated) | N/A — intentionally public, same posture as the existing dashboard/detail page |
| Supabase service/secret key | **Not used by the portal at all** for watchlist/holdings/kill-switch (those go through the user's own session JWT + RLS); used *only* server-side inside the tunables route's admin re-verification step (§16.4), from a Vercel server-only env var | Client bundle |
| Google OAuth client secret | Configured in Supabase Auth dashboard (Supabase-managed), not portal code | Portal repo/env at all |

### 16.8 Repo/module boundaries

```
admin-portal/                    # new directory, deployed to Vercel (root = admin-portal/)
  app/
    login/                       # Google OAuth sign-in, allowlist check + reject UX (§16.2)
    watchlist/                   # FR28 CRUD screens
    holdings/                    # FR29 CRUD screens
    tunables/                    # FR30 editor (calls /api/tunables)
    track-record/                # FR31 read-only view
    (kill-switch toggle surfaced on a shared authenticated layout/header, not a standalone page)
  app/api/tunables/route.ts      # FR30 server-side GitHub-PAT proxy (§16.4) — the ONLY route touching the PAT
  lib/supabase-client.ts         # browser client (anon key + session)
  lib/supabase-server.ts         # server-side client for admin re-verification (§16.4/§16.2 layer 3)
  lib/tunables-metadata.ts       # the static TunableField[] array (§16.4)
sql/
  admin_portal_rls.sql           # INC-5: admin_allowlist, is_admin(), watchlist/holdings write policies
  kill_switch_portal_grant.sql   # INC-7: set_kill_switch admin-check + grant, kill_switch_state SELECT policy
```

### 16.9 Requirement coverage

| Requirement | Covered by |
|---|---|
| FR27 (Google OAuth via Supabase Auth, no other login path) | §16.1, §16.2 |
| FR28 (watchlist CRUD) | §16.3 |
| FR29 (holdings CRUD) | §16.3 |
| FR30 (curated tunables editor, GH-Variables source of truth, PAT server-side only) | §16.4 |
| FR31 (read-only track-record view) | §16.5 |
| FR32 (kill-switch UI) | §16.6 |
| NFR5 (portal cost) | §16.1 |
| NFR6 (auth-gated writes, server-side-only secrets) | §16.2, §16.4, §16.7 |
