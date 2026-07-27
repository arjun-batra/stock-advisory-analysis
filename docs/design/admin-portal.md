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
  deploy. **As of Decision #27 (2026-07-27), no feature in this portal needs a server-only secret** —
  including the FR30 tunables editor, which now writes directly to Supabase under RLS (§16.4) — so
  Next.js's serverless API routes are used only for the standard Supabase Auth OAuth callback exchange
  (§16.8), not for any secret-holding proxy.
- **Auth:** Supabase Auth, **Google OAuth as the only enabled provider** — email/password and
  magic-link are disabled in the Supabase Auth dashboard config (an ops/config step at INC-5, not code;
  dev confirms and records it in `docs/handoff.md`). No anonymous access; every read/write from the
  portal, **including tunables** (§16.4), goes through the Supabase JS client carrying the signed-in
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

**Defense in depth (two independent layers):**
1. **RLS (the real enforcement).** Every write policy below — watchlist, holdings, **and now the FR30
   `tunables` table** (§16.4) — is gated on `is_admin()`. This holds even if the frontend has a bug; a
   malicious or buggy client can't write past it. As of Decision #27, this is the **only** authorization
   mechanism the portal needs anywhere — there is no longer a server-side proxy path with its own,
   separate re-verification step (§16.4 below no longer holds a secret at all).
2. **Portal UI check.** Immediately after Google sign-in, the frontend checks the signed-in email against
   `admin_allowlist` (via a lightweight authenticated read or an `is_admin()` RPC call) and **signs the
   user out immediately** with a visible "not authorized" message if it doesn't match — this is a UX
   improvement (a clear rejection instead of a confusing wall of failed writes), not the actual security
   boundary; RLS is.

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

### 16.4 Tunables editor (FR30) — REVISED 2026-07-27, Decision #27 (supersedes #24)

**The former design (below this note, historically) proposed a GitHub-PAT-holding Vercel proxy that
wrote directly to GitHub Actions Variables.** During design that premise was checked against the live
workflow YAML and found false for 8 of the 10 curated keys (see the superseded write-up this replaces,
preserved in git history) — only `GEMINI_MODEL`/`GEMINI_MODEL_BACKUP` were actually wired from a GitHub
Variable into a running workflow; `ALERTS_ENABLED` came from a `workflow_dispatch` input, and the seven
`DISCOVERY_*` keys weren't wired to anything. Fixing that gap required touching `scripts/config.py`
either way, which removed the entire reason to prefer GitHub Variables as the target. **Decision #27**
(requirements.md, approved by Arjun) moves the source of truth for these 10 keys to a new Supabase
`tunables` table instead — consolidating onto the control plane the system already trusts (Supabase
already holds `watchlist`, `holdings`, and the FR24 kill-switch flag), reusing the *exact* auth mechanism
already built for FR28/29 (no second authorization scheme), and eliminating the GitHub PAT / proxy route
/ third secrets store entirely. **This is a net simplification, not an addition** — no GitHub API
integration code, no server-only secret anywhere in the portal, one authorization mechanism for every
write the portal makes.

**Schema** (`tunables` table — exact columns per FR30):

```sql
create table public.tunables (
  key         text primary key,           -- e.g. 'GEMINI_MODEL'
  value       text not null,               -- stored as text; scripts/config.py casts per key
  description text not null,               -- human-readable purpose (FR30: never a bare input box)
  example     text not null,               -- an example legal value
  updated_at  timestamptz not null default now(),
  updated_by  text
);

-- actor stamped server-side on every write, same "never trust the client's
-- self-reported identity" principle as kill_switch_audit (operational-controls.md §13.3):
create or replace function public._stamp_tunable_update() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  new.updated_at := now();
  new.updated_by := coalesce(auth.jwt() ->> 'email', session_user);
  return new;
end; $$;

create trigger tunables_stamp_update
  before update on public.tunables
  for each row execute function public._stamp_tunable_update();

create policy "admin_write_tunables" on public.tunables
  for all to authenticated
  using (public.is_admin())
  with check (public.is_admin());
```

No anon/public policy — only the authenticated admin (portal) reads/writes this table; `scripts/config.py`
reads it with the existing `SUPABASE_SECRET_KEY` (service role, bypasses RLS, same posture every other
Python module already uses — no new grant needed there).

**Seed migration (INC-6):** one `insert` per curated key, at the value/description/example already
documented for these keys in `requirements.md` §10 / `scripts/config.py`'s existing comments — **no
behavior change at cutover** (Decision #27's explicit requirement: seeded values equal the literals they
replace). `GEMINI_MODEL_BACKUP`'s `description` row states "leave empty to disable the fallback model" —
since the table always has a row once seeded (no more GitHub-Variable-style "unset" ambiguity), the old
proxy design's special-cased "current effective value" display logic is no longer needed: the portal
just renders whatever `value` currently holds.

**Portal UI:** no static metadata array in the portal codebase anymore (`description`/`example` are now
DB columns, seeded once) — the tunables screen is a straight read/render/write against
`public.tunables`, using the same browser-side Supabase client + RLS pattern as watchlist/holdings
(§16.3). **No Next.js API route, no server-only secret, for this feature at all.**

**`scripts/config.py` fetch-with-fallback (FR30's explicit fail-safe posture — "same posture already
used elsewhere," e.g. `ai_judge`'s fail-safe-to-Hold):**

```python
def _fetch_tunables() -> dict[str, str]:
    """Best-effort fetch of the 10 curated rows at process start. Returns {}
    on ANY failure (network, auth, missing table) so every caller falls back
    to its own hardcoded Python literal — a bad/slow fetch can only ever
    fall back to a known-good prior default, never crash the run or serve a
    garbage value. Short explicit timeout so a Supabase hiccup can't hang
    process startup."""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)   # same pattern as state.py's _client()
        rows = client.table("tunables").select("key,value").execute().data
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"  [config] tunables fetch failed ({e}); using hardcoded defaults")
        return {}

_TUNABLES = _fetch_tunables()   # one fetch, all 10 keys, at import time

def _tunable(key: str, cast, default):
    raw = _TUNABLES.get(key)
    if raw is None:
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        print(f"  [config] tunables value for {key!r} ({raw!r}) failed to cast; using default")
        return default

# example usage — replaces the plain os.environ.get(...) reads for these 10 keys only;
# every other config.py tunable (the ~18 non-curated keys) is completely untouched:
GEMINI_MODEL = _tunable("GEMINI_MODEL", str, "gemini-2.5-flash")
ALERTS_ENABLED_TABLE = _tunable("ALERTS_ENABLED", lambda v: str(v).lower() == "true", True)
```

Precedence for these 10 keys is now **table value → hardcoded Python literal** — a clean two-level
fallback, per FR30's text. No workflow-YAML env-var layer is consulted for them any more.

**`ALERTS_ENABLED` — the one key with a real second input to reconcile.** Unlike the other 9 curated
keys, `ALERTS_ENABLED` is *also* driven by the existing `workflow_dispatch` input
(`${{ inputs.alerts_enabled }}` → env var `ALERTS_ENABLED`, unchanged, no YAML touch), which is the
documented **safe forced-test pattern** (`components.md` §4.1: "for any off-hours forced run, set
`ALERTS_ENABLED=false`"). That mechanism must keep working exactly as today — a manual dry-run test
should still be able to force alerts off regardless of what the table says. The table's value, symmetric
with the kill-switch's spirit but *softer* (checks/AI calls/logging still run; only the push is muted,
same as today's dry-run behavior — this does not duplicate FR24, which explicitly rejects an
alerts-only mechanism as the kill-switch's own enforcement), should be able to **additionally suppress**
real scheduled alerts, which the input alone can never do (pg_cron dispatches carry no inputs, so the
input always resolves to the YAML default `true` on every real run today). Resolution — pure Python, no
workflow YAML change needed, since both signals are already available as of INC-6:

```python
_alerts_input = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"   # workflow_dispatch input, unchanged
ALERTS_ENABLED = _alerts_input and ALERTS_ENABLED_TABLE   # table fetch failure -> ALERTS_ENABLED_TABLE
                                                            # defaults True -> AND is a no-op -> today's
                                                            # exact behavior, unchanged, on any fetch failure
```

The portal's toggle can only ever **suppress** alerts, never force them on over an explicit manual
dry-run request. `hourly-watchlist.yml` / `daily-discovery.yml` are **not touched** by this increment —
the existing `ALERTS_ENABLED: ${{ inputs.alerts_enabled }}` line stays exactly as-is; only
`scripts/config.py` changes. (The pre-existing `${{ vars.GEMINI_MODEL || '...' }}` / `_BACKUP` Variable
wiring in `hourly-watchlist.yml` becomes a harmless, unread vestige once the table takes precedence for
those two keys — safe to leave as-is; not required to remove it for correctness, since `_tunable()`
no longer consults that env var at all. Flagging as a future cleanup opportunity, not INC-6 scope.)

The 10 keys (verbatim from FR30 / `requirements.md` §10's portal-exposure note): `GEMINI_MODEL`,
`GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`, `DISCOVERY_LOSER_PCT`,
`DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_MARKET_CAP_INR`,
`DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`. No other tunable is reachable from this UI;
the other ~18 non-curated tunables are completely unaffected — still GitHub Variables/code defaults.

**Open design gap from the prior pass is now RESOLVED, not just deferred:** the previous write-up
flagged that 8 of 10 keys weren't actually wired to anything live, and needed Arjun's sign-off on a
GitHub-YAML-touching fix before INC-6 could start. Decision #27 resolves it structurally — the table
fetch in `scripts/config.py` is now how *all 10* keys take effect, so there is no wiring gap left to
close, and (per §16.4 above) `ALERTS_ENABLED`'s manual-dry-run interaction is resolved with a pure Python
change, not a workflow-YAML one. **No open question remains for INC-6.**

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

**REVISED 2026-07-27 (Decision #27):** the portal holds **no server-only secret at all**, for any
feature, including tunables. Every write (watchlist, holdings, tunables, kill-switch) goes through the
signed-in user's own Supabase session JWT, authorized by RLS/`is_admin()` — there is no longer a
credential in this system whose blast radius is broader than "one Supabase Auth account's own session."

| Secret | Lives in | Never appears in |
|---|---|---|
| Supabase anon/publishable key | Vercel `NEXT_PUBLIC_SUPABASE_ANON_KEY` (client-side, by design — this is the low-privilege key, RLS-gated) | N/A — intentionally public, same posture as the existing dashboard/detail page |
| Supabase service/secret key | **Not used by the portal at all**, for any feature — every portal write (watchlist, holdings, tunables, kill-switch) goes through the user's own session JWT + RLS. The secret key is used only by the existing Python workflows (`scripts/config.py`'s tunables fetch, §16.4, included) — unchanged from before this feature existed | Portal codebase, client bundle |
| Google OAuth client secret | Configured in Supabase Auth dashboard (Supabase-managed), not portal code | Portal repo/env at all |

~~GitHub PAT (`actions:write`)~~ — **removed by Decision #27.** No longer needed; there is no GitHub-API
write path anywhere in the portal.

### 16.8 Repo/module boundaries — REVISED 2026-07-27 (Decision #27)

```
admin-portal/                    # new directory, deployed to Vercel (root = admin-portal/)
  app/
    login/                       # Google OAuth sign-in, allowlist check + reject UX (§16.2)
    auth/callback/                # OAuth code-exchange route (standard Supabase Auth/Next.js
                                   #   PKCE flow — anon key only, no secret; unrelated to the
                                   #   removed GitHub-PAT proxy)
    watchlist/                   # FR28 CRUD screens
    holdings/                    # FR29 CRUD screens
    tunables/                    # FR30 editor — reads/writes public.tunables directly (§16.4)
    track-record/                # FR31 read-only view
    (kill-switch toggle surfaced on a shared authenticated layout/header, not a standalone page)
  lib/supabase-client.ts         # browser client (anon key + session) — used by EVERY feature now,
                                  #   including tunables; no separate server-side data path exists
sql/
  admin_portal_rls.sql           # INC-5: admin_allowlist, is_admin(), watchlist/holdings write policies
  admin_portal_tunables.sql      # INC-6: tunables table, _stamp_tunable_update() trigger,
                                  #   admin_write_tunables policy, 10-row seed (§16.4)
  kill_switch_portal_grant.sql   # INC-7: set_kill_switch admin-check + grant, kill_switch_state SELECT policy
```

**No `app/api/` routes and no server-only secret anywhere in the portal** — every feature (watchlist,
holdings, tunables, kill-switch RPC, track-record reads) is a direct, RLS-gated browser-to-Supabase call.
This is strictly smaller than the pre-Decision-#27 design (which had one API route + two server-side
library files for the GitHub-PAT proxy alone).

### 16.9 Requirement coverage

| Requirement | Covered by |
|---|---|
| FR27 (Google OAuth via Supabase Auth, no other login path) | §16.1, §16.2 |
| FR28 (watchlist CRUD) | §16.3 |
| FR29 (holdings CRUD) | §16.3 |
| FR30 (curated tunables editor, Supabase `tunables` table source of truth, RLS-gated, no PAT) | §16.4 |
| FR31 (read-only track-record view) | §16.5 |
| FR32 (kill-switch UI) | §16.6 |
| NFR5 (portal cost) | §16.1 |
| NFR6 (auth-gated writes, RLS at the database layer for every write incl. tunables) | §16.2, §16.4, §16.7 |
