# Admin portal

Part of `docs/design.md`'s module split. See `docs/design.md` for the index, module map, §0
load-bearing decisions, increment plan, and requirement coverage map — read that first for
orientation. Section number below (§16) continues the pre-split numbering; §15 (coverage map) stays in
`docs/design.md` itself.

**Status:** covers the 2026-07-26 change request (FR27–FR32, NFR5, NFR6). GATE 3 was passed by the user for
the whole change request (see `docs/design.md`). **INC-5 sections (§16.1–§16.3, §16.7–§16.8: hosting/auth,
authorization model, watchlist/holdings CRUD) are IMPLEMENTED** — dev-built, qa-tested, reviewer Pass 17
verdict CLEAR — REV-081/082/083 all RESOLVED, zero blockers (`docs/design/increment-plan.md`'s status
note, `docs/review-log.md`). **INC-6's design content lives in `admin-portal-tunables.md`,
`tunables-fallback.md`, and `tunables-workflow-writeback.md` (all IMPLEMENTED, reviewer-CLEAR Pass 19)** —
the `§16.4` pointer below is a cross-reference only, not a status claim about this file. **INC-7
(§16.5–§16.6) sections are also IMPLEMENTED** — dev-built, qa-tested (PASS — zero bugs,
`docs/test-report.md`), reviewer Pass 20 verdict CLEAR — zero blockers, zero majors (see
`docs/design.md`'s increment plan and coverage map, `docs/review-log.md`).

**2026-07-30 addendum:** §16.3's "holdings-currency derivation" content below was new design for **INC-10**
(DEEP-006, `docs/design/increment-plan.md`) — **now IMPLEMENTED**, dev-built across two fix cycles
(REV-112/REV-113 found and fixed), qa-tested (PASS), reviewer Pass 27 verdict CLEAR, zero blockers/majors
(`docs/review-log.md`). The rest of this page (INC-5/INC-7) was already shipped; all of §16.1–§16.3,
§16.5–§16.8 now describe live, reviewer-cleared behavior.

**New trust boundary — read this file in full before changing any of it.** Every other surface in this
system is either read-only-and-public (dashboard, detail page) or has no human-authenticated caller at
all (the workflows use the Supabase secret key server-side). This is the **first** write-capable,
human-authenticated surface. NFR6 asks for this explicitly: design the auth/RLS/secrets handling
carefully, not by analogy to the read-only surfaces.

**2026-07-31 addendum (NFR8, Decision #39, INC-13 — IMPLEMENTED, merged to `main`):** §16.10 below adds the
responsive/visual-modernization design for the five screens covered by §16.1–§16.6. This is a
presentation-layer-only addition — it changes no auth/RLS/schema/data-fetching content in §16.1–§16.9,
which remain as-built/IMPLEMENTED exactly as documented above and require no revision for NFR8. The
user has selected **Direction G** ("Compact Toggle") as the final visual/interaction direction — see
§16.10's updated content below for the exact reference files and details dev builds against.

**2026-08-01 addendum (FR36–FR38, amended NFR8, Decision #40) — §16.11 added, INC-15 READY.**
Arjun's admin-portal redesign change request: merge the watchlist+holdings screens into one "Tickers"
screen (FR36), a mandatory-field workflow gate on the watch-only↔held status transition (FR37), a
branding rename (FR38, no design content needed), and a real defect in the already-approved nav design
(desktop nav rendering vertically stacked instead of horizontal) plus new design intent for a
horizontally-scrollable nav tier (amended NFR8). §16.11 below has the full root-cause diagnosis, the nav
mechanism fix, and the merged Tickers screen's architecture (data model, modal, FR37's transactional
status-transition RPC). **2026-08-01 update — gate cleared:** Arjun approved the mockup
`docs/ux-mockups/direction-g-tickers-merge.html` (designer marking it SELECTED/APPROVED in
`docs/ux-spec.md` in parallel) — **INC-15 is now READY in `increment-plan.md`; dev may begin a build
plan.** §16.11's acceptance criteria below have been reviewed against this mockup and finalized (several
corrected — see §16.11.3/§16.11.4's revision notes). §16.1–§16.10 are unaffected by this addendum except
where §16.11 explicitly says otherwise (the tablet nav band's *mechanism*, and the watchlist/holdings
screens' eventual replacement).

---

## 16. Admin portal architecture (FR27–FR32, NFR5, NFR6)

### 16.1 Hosting & stack (Decision #23)

- **Frontend + backend:** Next.js (App Router) app in a new `admin-portal/` directory in this same
  repo, deployed to **Vercel** with the project root set to `admin-portal/`. Same repo as the rest of
  the system (not a separate repo) — consistent with the existing "public repo, $0 hosting" posture; no
  secrets live in the portal's client-side code (NFR6), so a public repo is not a new exposure. **As of Decision #27 (2026-07-27), no feature in this portal needs a server-only secret** —
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
alter table public.admin_allowlist enable row level security;
-- REV-033 fix, 2026-07-28: no policy is created for this table. With RLS
-- enabled and zero policies, anon/authenticated get zero rows via PostgREST —
-- correct, since nothing outside this table's own migration/ops-seed step and
-- is_admin() (below, a SECURITY DEFINER function that reads it as the table
-- owner, exempt from RLS the same way every other SECURITY DEFINER function
-- in this codebase already is) should ever read or write it. Without this,
-- Supabase's default public-schema grants would let ANY signed-in Google
-- account (or even anon) read the allowlist and, worse, INSERT their own
-- email into it — which would make them "the admin" and defeat is_admin()
-- for every RLS policy in INC-5/6/7 at once, since it is their single source
-- of truth (see the paragraph below).

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

**Fields (from `data-and-flow.md` §5, corrected 2026-07-28 — the values below were previously swapped):**
`watchlist` — ticker, market (US/TSX/NSE), type (`stock`/`ETF`, default `stock`), status
(`held`/`watch-only`); `holdings` — ticker, shares (>0), cost_basis (>0), currency
(USD/CAD/INR — matches the ticker's market). The portal's forms mirror these columns and their existing
CHECK constraints 1:1 (see `sql/schema.sql`, REV-035, for the exact constraints); no new validation rules
invented beyond what the DB already enforces.

**FIX ROUND (DEEP-006, INC-10) — `holdings.currency` is derived, not admin-entered (FR11/FR29, Decision
#35).** As shipped, the holdings add/edit form offered a free-choice `currency` select (default `USD` for
every market, `admin-portal/lib/validation.ts`'s `validateHoldingsRow`), never reconciled against the held
ticker's own `watchlist.market` (reachable via the existing FK) — a TSX/NSE position entered at its natural
default silently produced a wrong unrealized P&L, fed to the AI as fact (FR11) and rendered on the detail
page (latent only because the live watchlist holds zero positions today). **Fix, same-currency by
construction, not by admin cooperation:**
- **UI:** the holdings form drops the `currency` input entirely; it instead shows a **read-only** derived
  label next to the ticker/market picker (e.g. "Currency: CAD (from TSX)"), sourced from the selected
  ticker's `watchlist.market` — not submitted in the write payload at all.
- **`validation.ts`:** `HoldingsInput` drops `currency`; `validateHoldingsRow` no longer checks it (nothing
  left for the client to validate — the server derives it unconditionally, see below).
- **`sql/holdings_currency_derivation.sql` (new file):** a `BEFORE INSERT OR UPDATE` trigger on `holdings`
  that looks up `watchlist.market` for `new.ticker` (guaranteed to exist by the pre-existing FK) and sets
  `new.currency` to the mapped value (US⇒USD, TSX⇒CAD, NSE⇒INR) — **unconditionally overwriting whatever
  was submitted**, so this holds for the portal, a direct SQL edit, and any future write path alike, not
  just the one UI that currently exists:
  ```sql
  create or replace function public._derive_holdings_currency() returns trigger
  language plpgsql security definer set search_path = '' as $$
  declare v_market text; v_currency text;
  begin
    select market into v_market from public.watchlist where ticker = new.ticker;
    if v_market is null then
      raise exception 'holdings.ticker % has no matching watchlist row', new.ticker;
    end if;
    v_currency := case v_market when 'US' then 'USD' when 'TSX' then 'CAD' when 'NSE' then 'INR' end;
    if v_currency is null then
      raise exception 'watchlist.market % for ticker % has no known currency mapping', v_market, new.ticker;
    end if;
    new.currency := v_currency;
    return new;
  end; $$;

  create trigger holdings_derive_currency
    before insert or update on public.holdings
    for each row execute function public._derive_holdings_currency();
  ```
- **Defense-in-depth, `scripts/state.build_position` (`components.md` §4.5 consumer):** the trigger above
  guarantees `holdings.currency` always agrees with `watchlist.market` — but not that `watchlist.market`
  itself is correct for the ticker's actual listing (a separate, narrower residual risk, out of DEEP-006's
  scope). As a second, independent layer reusing data already fetched, `build_position` now compares
  `holding["currency"]` to the ticker's own `data["fundamentals"]["currency"]` (Yahoo's independently-
  fetched value) and returns `pl_pct=None` with a logged warning on a mismatch, rather than computing a
  gain/loss figure from currencies that disagree (FR11's explicit requirement) — see `non-functional-ops.md`
  §7.3.
- **No RLS change needed:** the existing `admin_write_holdings` policy (`for all to authenticated using
  (is_admin())`) is unaffected — the trigger runs regardless of who or what wrote the row, same as
  `_stamp_tunable_update()` already does for `tunables`.

### 16.4 Tunables editor (FR30)

**Moved to `docs/design/admin-portal-tunables.md`** (2026-07-27 — this subsection grew past the point
where INC-6 should have to load the rest of the portal's design to build against it; doc hygiene, see
`docs/design.md`'s split threshold). Covers: the `tunables` table schema, `is_admin()`-gated RLS policy
(narrowed to `select`/`update` only, REV-044), seed migration (including the `ALERTS_ENABLED` seed-value
correctness note), the Decision #28 cache-file fail-safe mechanism (`tunables_cache.json`, the **two-tier**
`scripts/config.py` fallback chain — table then cache, fails loud via `SystemExit` if both tiers miss a
key — `hourly-watchlist.yml`'s new write-back step), and the `ALERTS_ENABLED` AND-gate logic. The exact
fallback-chain mechanism is stated once, in `admin-portal-tunables.md` §16.4 — this stub intentionally
doesn't restate it (CLAUDE.md's "state anything once" rule; restating it is what let this exact stub drift
to a stale "3-tier" description once already, REV-037). INC-6 reads that file; INC-5 and INC-7 don't need
to.

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
revoke insert, update, delete, truncate on public.kill_switch_state from public, anon, authenticated;
-- Same TRUNCATE-grant gap class as REV-081 (admin_allowlist) and REV-086 (tunables): RLS never governs
-- TRUNCATE in Postgres, so Supabase's default grants otherwise leave it open regardless of RLS.
-- kill_switch_state gets all four verbs revoked, not just TRUNCATE: there is no legitimate anon/
-- authenticated write path to this table at all — every write happens through set_kill_switch(),
-- which runs as the table owner (SECURITY DEFINER) and is therefore unaffected by this REVOKE.

revoke truncate on public.kill_switch_audit from public, anon, authenticated;
-- kill_switch_audit already had insert/update/delete revoked by sql/kill_switch.sql (INC-3) — only the
-- missing TRUNCATE verb is added here, closing the same gap class one increment later than REV-081/086
-- caught it on the other two tables.

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
| NFR7 (RLS scopes access to what each surface needs — extended here to `admin_allowlist`, RLS-enabled with zero anon/authenticated policies, REV-033) | §16.2 |
| NFR8 (responsive & modern admin-portal UI/UX, zero functional regression) | §16.10 — Direction G, INC-13 (`increment-plan.md`) merged/reviewer-CLEAR Pass 35, **but a post-merge visual-fidelity gap (pill markup, Add/Edit modal, desktop elevation) is open — fix tracked as INC-14**, not yet qa/reviewer-cleared. **Navigation-mechanism bullet (amended 2026-08-01, Decision #40): §16.11.1 (defect root cause/fix)/§16.11.2 (new tablet horizontal-scroll mechanism) — tracked as INC-15, READY** (mockup gate cleared 2026-08-01 — Arjun approved `docs/ux-mockups/direction-g-tickers-merge.html`; dev may start). |
| FR36 (merged Tickers screen: one-card-per-row, card content, click-to-modal) | §16.11.3/§16.11.4 — tracked as **INC-15, READY**, built against `docs/ux-mockups/direction-g-tickers-merge.html` (approved 2026-08-01) |
| FR37 (mandatory shares/price-per-share on watch-only→held; delete-with-confirmation on held→watch-only) | §16.11.4 (workflow/validation)/§16.11.5 (transactional RPC) — tracked as **INC-15, READY** |
| FR38 (branding rename "Admin Portal"→"Sentinel Portal") | UI string change only — no design content needed, dev/designer implement directly |

### 16.10 Responsive & visual design system (NFR8, INC-13) — IMPLEMENTED, reviewer-CLEAR Pass 35, merged to `main`; **known post-merge gap, fix tracked as INC-14**

**Gate cleared 2026-07-31:** designer published `docs/ux-spec.md` with mockup directions covering all
five screens, and the user (Arjun) selected **Direction G — "Compact Toggle"**
(`docs/ux-mockups/direction-g-compact-toggle.html`; design detail in `docs/ux-spec.md` §7.4, built on
Direction F's density §7.3 and Direction E's toggle component §7.2). INC-13 is now **IMPLEMENTED and
merged to `main`** (commit `da50ed8`, PR #46; reviewer Pass 35 CLEAR, zero blockers/majors). This section defines the **technical mechanism** (breakpoints, layout system,
structural enforcement) that Direction G is implemented through; the visual/interaction language itself
is designer's + the user's call and is specified in `docs/ux-spec.md`, not restated here.

**2026-08-01 — known gap, do not treat this section as describing what's actually live.** A post-merge
production defect (Arjun, reported against `sentinel-admin.arjunbatra.xyz`) found the live watchlist/
holdings screens still render market/type/status as raw text (zero `.pill`/`.ticker-card` classes in the
built `admin-portal/app/globals.css`) and still render Add/Edit ticker as a permanently-visible inline
form section (zero `.form-modal`/`.fab` classes) — neither matches the mockup this section and §16.10's
prose below describe. INC-13's own acceptance criteria (`docs/design/increment-plan.md`) never explicitly
named these two components, so dev satisfied what was literally written without building them; this was a
gap in the AC list, not a design error — the mechanism/prose below was and remains correct. **The fix is
tracked as INC-14** (`docs/design/increment-plan.md`, "2026-08-01 — post-merge production defect on
INC-13"), which tightens the AC list against this exact gap; no content in this section changes as a
result. Desktop-width (1280px) card elevation is also unverified in production pending INC-14's AC3.
Treat §16.10's description below as the **design intent**, confirmed live again only once INC-14 is
qa-tested and reviewer-cleared.

**Direction G — what dev implements (reference files, not restated in full — read the sources):**
- **Visual baseline — Direction F's compact density** (`docs/ux-spec.md` §7.3, mockup
  `docs/ux-mockups/direction-f-compact-cards.html`, since Direction G reuses F's tokens/layout verbatim
  except the kill-switch control): flatter single-layer card shadow (`shadow-card` per §7.3.1, not C's
  layered shadow), smaller corner radii (`radius-md` 8px / `radius-lg` 14px vs. C's 12px/20px), tighter
  spacing scale (`space-1`…`space-8`: 4/6/10/14/18/24/36/48px), smaller type scale (11/13/15/17/22/28px),
  and higher grid density at each breakpoint: watchlist/holdings **4-col** card grid desktop / 3-col
  tablet / 2-col phone; tunables editor renders all 10 keys as **always-visible compact cards** (no
  accordion/expand-collapse — value input and Save visible without a tap, `docs/ux-spec.md` §7.3.2);
  track-record **3-col** card grid desktop / 2-col tablet / 1-col phone. Accent color emerald
  (`color-accent` `#059669`).
- **Kill-switch control — Direction E's sliding toggle-switch** (`docs/ux-spec.md` §7.4.2, component
  structure from §7.2's `.killswitch`/`.toggle` markup in `docs/ux-mockups/direction-e-hybrid.html`,
  resized to Direction G's compact scale — track 30×17px, thumb 13px circle): markup is a label
  (`<span>System: Running</span>` / `"System: Paused"`, no emoji) plus a separate `.toggle` element
  (track + thumb), **not** Direction F's static `<span class="pill">` badge. Running: track
  `background: var(--color-accent)`, thumb slid right (`::after{ right:2px }`). Paused: `.toggle.paused`
  — track `background: var(--color-border)` (grey), thumb slid left (`::after{ right:auto; left:2px }`).
  **Interaction (no new backend logic — purely a visual-control swap):** clicking/tapping the toggle
  element calls the exact same `set_kill_switch(..., p_source:='admin-portal')` Supabase RPC that INC-7's
  `components/KillSwitchToggle.tsx` already calls (§16.6) — dev changes only the rendered markup/CSS and
  the click target (the toggle div instead of the pill span), not the `onClick` handler's body or the RPC
  call itself. Loading/in-flight/error/success states are governed unchanged by the shared UX contract
  (`docs/ux-spec.md` §2.5): loading = toggle muted/disabled; in-flight = toggle disabled, label
  "Pausing…"/"Resuming…"; error = toggle snaps back to prior position + inline message; success = toggle
  position updates immediately, label/sub-label update to the new `updated_at`/`updated_by`.
- **Tunables friendly labels — all 10 keys** (`docs/ux-spec.md` §2.3's mapping table is authoritative):
  each tunable card's primary heading is the friendly label (e.g. "Primary AI model", "Alerts on/off
  switch") with the raw `SNAKE_CASE` key demoted to a small monospace subtitle directly beneath it (never
  dropped — Arjun still needs to map a field back to `scripts/config.py`). This is a label-only change:
  no change to validation, storage, or which key maps to which input type (`ALERTS_ENABLED` still a
  true/false select, etc. — INC-10's validation, §16.3/`admin-portal-tunables.md` §16.4, untouched).

**Scope boundary (structural, not just stated intent):** every change in INC-13 is presentation-layer —
CSS, JSX/TSX markup, className/data-attribute additions, and purely-presentational local component state
(e.g. a nav-open/closed boolean). **Nothing in §16.1–§16.9 above changes.** No `supabase.*` call, no
`lib/validation.ts` exported function's logic, no `lib/admin-guard.ts`/`lib/supabase-client.ts` content,
no `sql/*`, no `scripts/*`, and no event-handler's *business* logic (a button may be restyled/repositioned;
what its `onClick` calls may not change) may be touched. This is enforced structurally (see acceptance
criteria in `increment-plan.md`'s INC-13, not just reviewed by eye): a `git diff` grep for
`supabase\.|validateHoldingsRow|validateTunableValue|is_admin|set_kill_switch|\.rpc\(|createClient` across
every file INC-13 touches must return zero matches.

**Breakpoints (tech-lead decision, per NFR8's explicit delegation — mobile-first CSS):**
- **Phone:** up to 639px (base/default styles, no media query needed).
- **Tablet:** `@media (min-width: 640px)`.
- **Desktop:** `@media (min-width: 1024px)`.

These three bands are what "phone/tablet/desktop" in NFR8 map to; qa tests at 375px, 768px, and 1280px as
concrete representative widths (common devtools/Playwright presets, one comfortably inside each band).

**Layout mechanism per current file (`code-map.md`'s `admin-portal/` inventory — no new files required,
one small presentational component permitted):**
- `app/globals.css` — the current fixed `main { max-width: 900px }` becomes fluid with breakpoint-scaled
  padding; `.app-header`'s flex nav row (today unconditional) collapses to a stacked/menu form below the
  tablet breakpoint via CSS (a small presentational `NavToggle` local-state component is permitted in
  `components/` if a JS-driven open/closed toggle is needed — no data implications, no new prop touches
  any Supabase call).
- `.crud-table` (`watchlist`/`holdings` pages) — the underlying `<table>`/`<tr>`/`<td>` DOM structure and
  markup are unchanged at every width; only CSS `display` overrides and one added markup attribute vary
  by breakpoint (three bands, BUG-010 fix folded in):
  - **Phone (base, <640px):** stacked "card per row" via CSS only (`tbody{display:block}`,
    `tr{display:block}` with its own card shadow/radius/background, `td{display:flex}`,
    `td::before{content:attr(data-label)}`), reading a `data-label="<column header>"` attribute added to
    each `<td>` in markup (a markup addition, not a logic change) — satisfies "no horizontal scrolling"
    literally at phone width rather than wrapping the table in a scroll region.
  - **Tablet (640–1023px):** the `<table>` layout is kept literally (`display:table-row-group`/
    `table-row`/`table-cell`, header row shown, `data-label` suppressed) — no `<div>`-based card grid and
    no `data-label`/`attr()` trick at this width. The one addition is `.crud-table-wrap`, a wrapper `<div>`
    around the `<table>` that supplies Direction G's card *styling* (surface background, `radius-md`,
    `shadow-card`) at this band only, since a real `display:table-row` element can't reliably paint its
    own box-shadow. `.crud-table-wrap` stays transparent at phone/desktop, where each `<tr>` (phone) or
    grid cell (desktop) already carries its own card treatment.
  - **Desktop (>=1024px):** `tbody{display:grid; grid-template-columns:repeat(4,1fr)}` turns the table
    into Direction G's 4-column compact card grid — each `<tr>` becomes a grid cell/card (own
    shadow/radius/background), `data-label` still suppressed. This is a CSS-only transformation of the
    same `<table>` markup, not a separate card-grid component.
- **Track-record page** — converted from a real sortable `<table>` (BUG-011 fix) to a `.tr-cards` CSS
  grid (3-col desktop / 2-col tablet / 1-col phone, same three-tier density pattern as the tunables
  grid), with each record rendered as a `.tr-card`. Because a card layout has no column-header row for
  sort affordances to live in, the old clickable `<th>` sort handlers are replaced by a `.sort-controls`
  bar (a field `<select>` plus a direction-toggle button) driving the same underlying `.order()` query/
  state — sort reachability (FR31) is preserved, only the control's markup changed.
- `form.crud-form` — already single-column (fits phone as-is); gains an optional two-column
  `grid-template-columns` at the desktop breakpoint only, if the chosen mockup direction calls for it.
- Kill-switch toggle (`components/KillSwitchToggle.tsx`) and login screen — CSS/markup sizing only; no
  change to the toggle's `set_kill_switch` RPC call or the login screen's OAuth redirect.

**Files INC-13 may touch (allow-list, see `increment-plan.md` for the exact grep-checkable rule):**
`admin-portal/app/globals.css`, `admin-portal/app/layout.tsx`, `admin-portal/app/(app)/layout.tsx`,
`admin-portal/app/login/page.tsx`, `admin-portal/app/(app)/watchlist/page.tsx`, `admin-portal/app/(app)/
holdings/page.tsx`, `admin-portal/app/(app)/tunables/page.tsx`, `admin-portal/app/(app)/track-record/
page.tsx`, `admin-portal/components/AuthGuard.tsx`, `admin-portal/components/KillSwitchToggle.tsx`, and at
most one new presentational component file under `admin-portal/components/` (e.g. `NavToggle.tsx`) if a
collapsible-nav toggle needs local state. No other file, in any directory, is in scope.

**Accessibility:** best-effort only per NFR8's explicit text — keyboard reachability and legible contrast
are checked and recorded, not a pass/fail gate; no WCAG target.

**2026-08-01 note — nav defect diagnosis moved to §16.11.** The desktop-vertical-stacking nav defect
Arjun reported (routed via Decision #40, NFR8's amended navigation-mechanism bullet) is **not** a gap in
this section's design intent — the breakpoint/mechanism described above (burger below desktop, forced
horizontal row at ≥1024px) is what was *supposed* to render. §16.11 below documents the actual root cause
(a DOM/CSS structural mismatch, not a wrong breakpoint value) and the fix + new nav-mechanism design
(Decision #40's horizontal-scroll carve-out). This section's breakpoint values (639/640/1023/1024) are
unchanged and remain correct as the phone/tablet/desktop band definitions; §16.11 revises which mechanism
applies to the tablet band specifically.

---

## 16.11 Nav defect fix + horizontal-scroll tier, and the merged Tickers screen (FR36–FR38, NFR8 amendment, Decision #40) — INC-15, **READY**

**Status: READY — gate cleared 2026-08-01.** Arjun approved the mockup
`docs/ux-mockups/direction-g-tickers-merge.html` (designer records SELECTED/APPROVED in `docs/ux-spec.md`
in parallel). Dev builds directly against that mockup's exact markup/class names and interaction states —
it is now the authoritative visual/interaction reference for this increment, superseding this section's
earlier illustrative class names where the two differ (noted inline below, §16.11.1/§16.11.3/§16.11.4).
The root cause, mechanism, and data/API design below remain unchanged design intent; only the acceptance
criteria and a handful of presentation details have been corrected against the approved mockup.

### 16.11.1 Nav defect — root cause (diagnosed against the live merged code, `da50ed8`/INC-14)

**The bug is a DOM/CSS structural mismatch, not a wrong breakpoint or a wrong CSS value.**

`admin-portal/components/NavToggle.tsx` renders:
```tsx
<div className={`nav-panel${open ? " open" : ""}`}>{children}</div>
```
`admin-portal/components/AuthGuard.tsx` calls it as:
```tsx
<NavToggle>
  <nav>
    <a href="/watchlist">Watchlist</a>
    <a href="/holdings">Holdings</a>
    <a href="/tunables">Tunables</a>
    <a href="/track-record">Track record</a>
    <SignOutButton />
  </nav>
</NavToggle>
```
So the actual DOM is `.nav-panel > nav > (a, a, a, a, button.link)` — **one extra level of nesting**
between the flex container and the links. `app/globals.css`'s `.nav-panel` rules apply `display:flex` and
toggle `flex-direction` (`column` when `.open`, forced `row` at `@media (min-width: 1024px)`) — but those
rules govern `.nav-panel`'s *direct* children, which is a single `<nav>` box, not the five links. A
flexbox `flex-direction` on a container with exactly one flex item has no visible effect (there is nothing
to arrange into a row vs. a column). The actual vertical stacking is produced by a completely different,
unrelated rule: `.nav-panel a, .nav-panel button.link { display: block; width: 100%; }` (a *descendant*
selector, so it does reach through the extra `<nav>` wrapper) — each anchor becomes a full-width block
inside `<nav>`'s own default (non-flex) block formatting context, so the links stack one per line
**regardless of `.nav-panel`'s flex-direction, and regardless of viewport width.** This is why the defect
reproduces identically at every width where `.nav-panel` is visible: at phone/tablet with the menu toggled
open, vertical stacking happens to be the *intended* look (a dropdown menu), so nobody noticed; at
desktop, where CSS forces `.nav-panel` open with `flex-direction: row`, the same underlying vertical
stacking is now visibly wrong, which is exactly what Arjun's screenshot shows.

**Fix approach (dev's implementation choice at build time, either is acceptable — recorded here so dev
doesn't have to re-diagnose):**
- **Option A (preferred — flattens the DOM to match the CSS's assumption):** remove the redundant `<nav>`
  wrapper in `AuthGuard.tsx`; pass the `<a>`/`SignOutButton` elements directly as `NavToggle`'s children,
  and have `NavToggle` render its own wrapper element as `<nav className="nav-panel ...">` (semantic nav
  landmark) instead of a bare `<div>`. This makes `.nav-panel`'s direct children the actual links, so the
  existing `flex-direction`/`display:flex` rules apply to them directly, with zero other CSS change needed
  beyond §16.11.2's breakpoint/mechanism update below.
- **Option B (CSS-only, if the JSX nesting must stay for another reason):** retarget the flex rules from
  `.nav-panel` to `.nav-panel > nav` (the element that is actually the links' direct parent), and drop
  `display:flex` from `.nav-panel` itself (it becomes a positioning/dropdown-box wrapper only, unchanged
  for its mobile `.open` absolute-position styling).
Either option is a **presentation-layer-only** fix — no `supabase.*` call, no `is_admin()`/RLS/validation
logic anywhere near this file, consistent with §16.10's own scope-boundary rule.

**2026-08-01 note — approved mockup names the actual markup, superseding this subsection's illustrative
class names.** `docs/ux-mockups/direction-g-tickers-merge.html` restructures the header as
`.app-header > (.app-header-brand, .nav-strip-wrap > .nav-strip > a×3, .nav-toggle-btn,
.nav-panel-mobile, .app-header-right)` — the nav links are direct flex children of `.nav-strip` (no
intervening `<nav>` wrapper), which is the same root-cause fix as Option A above, just under new class
names. Dev follows the mockup's exact class names, not the illustrative `.nav-panel`/`NavToggle` naming
above — the diagnosis (remove the extra DOM nesting level between the flex container and the links) stays
correct and is what the mockup's structure already does. **`SignOutButton` is not one of the 3
`.nav-strip`/`.nav-panel-mobile` links** — the mockup places it in `.app-header-right` alongside the
kill-switch toggle and user chip, persistently visible at every viewport (not hidden behind the phone
burger). This is the only self-consistent reading of the mockup (which shows no sign-out affordance inside
either nav list) and does not change requirements — sign-out remains present and functional everywhere, it
simply isn't counted among the "3 nav items."

### 16.11.2 Nav mechanism — breakpoints (Decision #40's NFR8 amendment)

**Kept:** the same three bands already established in §16.10 — phone ≤639px, tablet 640–1023px, desktop
≥1024px. No new breakpoint tier is introduced; **the tablet band's *mechanism* changes**, not its pixel
boundary, which is why this counts as staying consistent with the existing bands rather than deviating
from them.

- **Phone (≤639px): burger menu, unchanged.** `NavToggle`'s hamburger button + toggle-open dropdown panel
  behavior is not affected by this fix — it was never the site of the reported defect (a vertical dropdown
  list is the *correct* look at phone width).
- **Tablet (640–1023px) — changed from burger to a literal horizontal row with a scroll safety net.**
  The burger toggle (`.nav-toggle-btn`) is now hidden starting at 640px (not 1024px), and `.nav-panel`
  (or `.nav-panel > nav`, per whichever fix option dev picks in §16.11.1) renders
  `display: flex; flex-direction: row; flex-wrap: nowrap; overflow-x: auto;` starting at the same
  640px breakpoint. This single rule satisfies NFR8's amended carve-out directly: with FR36 shrinking the
  nav from five items (Watchlist/Holdings/Tunables/Track record/Sign out) to four (Tickers/Tunables/
  Track record/Sign out), the row is expected to fit without visibly scrolling in the common case — but
  `overflow-x: auto` means if it ever doesn't (a long future item label, a narrow real-device tablet), the
  nav scrolls horizontally instead of wrapping to a second line or clipping, which is exactly the behavior
  NFR8's narrow carve-out permits, scoped to the nav container only. No JS is added for this — it is a
  pure CSS behavior that is a no-op (no visible scrollbar) whenever content already fits.
- **Desktop (≥1024px): unchanged mechanism, now actually working.** Same `display:flex; flex-direction:
  row` (`overflow-x: auto` is harmless here too — it only activates if content overflows, which it will
  not at this width with four items) — this is the band the original defect was reported against; §16.11.1
  is the fix that makes this band's already-correct CSS intent actually reach the links.

**Rationale for reusing 640px rather than picking a separate "mid-width tier":** NFR8's carve-out text
asks for a horizontally-scrollable nav "at some tech-lead-determined mid-width tier ... as an alternative
to the burger control" — the tablet band **is** that tier (it is the band that used to hide behind the
burger); moving its mechanism from burger to scroll-safe horizontal row is the literal, minimal way to
satisfy the requirement without inventing a fourth band. No deviation from the phone/tablet/desktop
three-band model is needed or taken.

### 16.11.3 Tickers screen — merged data model (FR36)

**No schema change (Decision #40, explicit).** The Tickers screen reads/writes the same two tables,
`watchlist` and `holdings`, joined client-side by `ticker` — no new table, no new column, no view change
beyond what already exists.

- **Read (page load):** three parallel Supabase reads, same RLS-authorized pattern already used by the
  existing watchlist/holdings/track-record pages — no new policy needed for reads:
  1. `select * from watchlist order by ticker` (existing `anon_read_watchlist` policy already covers this
     for the signed-in admin, same as today's watchlist page).
  2. `select * from holdings` (existing `admin_write_holdings` policy's `using (is_admin())` clause also
     covers `select` — `for all` includes read — same access the existing holdings page already relies on;
     no new policy).
  3. `select * from latest_call_per_ticker` (or equivalent — the same view/read the track-record page and
     dashboard already use, `data-and-flow.md` §5) for each ticker's latest verdict/timestamp/rationale/
     confidence.
  These three result sets are merged client-side into one view-model per row:
  ```ts
  type TickerRow = {
    ticker: string;
    market: "US" | "TSX" | "NSE";
    type: "stock" | "ETF";
    status: "held" | "watch-only";
    holding: { shares: number; cost_basis: number; currency: "USD" | "CAD" | "INR" } | null; // null iff watch-only
    latestCall: {
      verdict: "Buy" | "Sell" | "Hold";
      timestamp: string;       // ISO, rendered per FR23's dual-timezone rule (unchanged, reused from the
                                // existing detail-page/dashboard formatting helper — no new logic)
      confidence: "high" | "medium" | "low";
      rationale: string;
    } | null; // null iff no check has run yet for this ticker (same "hidden, not placeholder" rule as FR21)
  };
  ```
  `confidence` is **not new data** — it is `call_log.data_snapshot.confidence`, already produced by
  `ai_judge.py` and already surfaced on the public dashboard/detail page (FR21/FR14, `components.md`
  §4.7); this is a new *display surface* only, per FR36's own text and Decision #40's impact assessment.

- **Card layout — one card per row, all three breakpoints (supersedes INC-13/14's 4/3/2-col density for
  this screen only):** `.card-grid`'s `grid-template-columns` for the Tickers screen becomes a single
  column (`1fr`) unconditionally — no per-breakpoint override, unlike the tunables/track-record grids
  which keep their existing 3/2/1-col and 3-col/2-col/1-col density respectively (§16.10, unaffected). This
  is a new CSS class (e.g. `.ticker-list`, to avoid changing `.card-grid`'s shared definition used
  elsewhere) rather than a modification to the existing `.card-grid` rule.

- **Card content (FR36, exact list, corrected 2026-08-01 against the approved mockup's `.ticker-row-card`
  markup):** (1) a header row: ticker symbol, a plain-text market label (`.mkt`, e.g. "US"/"TSX"/"NSE" —
  not a pill), a type pill (`.pill.type`, "Stock"/"ETF"), and a status pill (`.pill.held`/`.pill.watch`,
  reused verbatim from INC-14's existing pill classes — no new CSS token); (2) if held, a shares/
  price-per-share line (`.holding-line`, a UI label only — the existing `holdings.cost_basis` value, not a
  new field); omitted entirely (no empty row) if watch-only; (3) the latest verdict as a `.verdict-pill`
  (reused from the track-record card, §16.10) plus its timestamp (reuse the existing dual-timezone
  formatting helper) plus a confidence label — **resolved by the approved mockup as plain inline text**
  ("Confidence: {high|medium|low}"), not a distinct badge/pill (the "exact visual TBD" note from the prior
  draft is now closed); binds to `latestCall.confidence`, no new data; (4) the rationale text (reuse
  `.tr-card .rationale` styling). If `latestCall` is null, the whole verdict/timestamp/confidence/rationale
  block is omitted — **the mockup shows a short italic explanatory note in its place** (e.g. "No checks
  logged yet for this ticker — results will appear here after the next run.") rather than rendering
  nothing at all; this is consistent with FR21's "hidden, not a placeholder" rule (no fabricated
  verdict/confidence data is shown), not a contradiction of it — the note names the absence, it does not
  simulate a result.

### 16.11.4 Click-to-modal + combined edit form (FR36, FR37)

The entire card is the click target (a `<button>`-semantics wrapper around the card's content, not just an
icon) opening `TickerEditModal` — reuses the `.modal-overlay`/`.form-modal` mechanism INC-14 already built
for the Add/Edit ticker modal (centered panel tablet/desktop, bottom sheet phone), generalized to this
screen instead of two separate per-table modals.

- **Modal contents, top to bottom (corrected 2026-08-01 against the approved mockup's `.modal-static`
  markup):** (a) read-only identifying header — ticker (as heading) and a `market · type` subhead line;
  **status is not repeated as separate read-only text** — it is represented by the pre-filled `status`
  select in the form below (b), which is sufficient for FR36's "full identifying info" since the value is
  immediately visible there, not hidden behind an extra interaction. **The prior draft's "card content
  restated (verdict/timestamp/confidence/rationale, read-only)" display block does not appear in the
  approved mockup and is dropped from this design** — the card itself already shows that information, and
  the modal does not repeat it; (b) one combined edit form with fields for `market` (select), `type`
  (select), `status` (select: held/watch-only), a read-only derived-currency chip (carried over unchanged
  from INC-10's existing "no currency input, derived label" behavior, §16.3), and, conditionally,
  `shares`/`price per share` (number inputs) — the same fields the separate watchlist/holdings edit forms
  already validate against (`lib/validation.ts`'s existing `validateWatchlistRow`/`validateHoldingsRow`,
  unchanged rules, now called from one form instead of two); (c) a delete action.
- **Conditional shares/price-per-share fields (FR37):** hidden when the form's current `status` value is
  `watch-only` and the ticker has no existing `holding`; shown, pre-filled from `holding`, when `status` is
  (or becomes) `held`. **New client-side validation logic, genuinely new per FR37 (this is the one
  legitimate new-logic surface this increment adds, not banned by the "no functional regression" rule):**
  when the form's `status` value transitions from `held` (or the ticker's existing status) to a *new*
  value of `held` starting from `watch-only`, the form must not allow submit until both `shares > 0` and
  `cost_basis > 0` validate (reusing the existing numeric CHECK-mirroring rules in `validateHoldingsRow`,
  not a new validation rule — only the *trigger point* — "on this specific transition" — is new).
- **Held→watch-only confirmation (FR37):** the form's `status` select can be changed to `watch-only` freely
  (Save stays enabled — this differs from the watch-only→held direction above, where Save is blocked until
  validation passes). **Clicking Save** when `status` has changed from `held` to `watch-only` replaces the
  form with a confirmation panel, in the same modal (per the approved mockup's `.confirm-panel` — not a
  separate dialog/prompt), naming the ticker and the exact shares/price-per-share values about to be
  discarded (read from the ticker's current `holding` before the delete) — e.g. "Switch AAPL to
  watch-only? This deletes the recorded 10 sh @ $150.00 USD holding — this can't be undone." The write
  (`set_ticker_holding_status`) fires only on confirming, never on the Save click itself. Cancelling
  returns to the still-open, still-unsaved form with the original `held` data untouched.
- **Delete action:** removes the ticker entirely (both its `watchlist` row and, if present, its `holdings`
  row) — see §16.11.5 for why this needs a new RPC rather than two independent client calls. Also gated
  behind its own confirmation prompt naming the ticker (existing pattern, both current watchlist/holdings
  delete buttons already confirm before deleting — unchanged UX, just one merged action instead of two;
  distinct from the held→watch-only confirmation above, which fires on a *status change*, not on the
  Delete button).

- **"+ Add ticker" (toolbar button, per the approved mockup — pre-existing capability, not new logic):**
  opens the existing add-to-watchlist form (INC-5's FR27 CRUD, unchanged validation), which creates a new
  ticker with `status='watch-only'` and no `holdings` row — consistent with the RPC design in §16.11.5,
  whose `set_ticker_holding_status` only `update`s an existing `watchlist` row (it has no `insert` path) —
  a ticker must exist watch-only before it can be promoted to held via the FR37-gated transition. This is
  not a new create-as-held path; none is needed or requested.

- **Toolbar search input (per the approved mockup):** client-side-only filter by ticker text, no backend
  call, no new data. **Flagged to pm (non-blocking):** neither FR36 nor FR37's text mentions search — this
  appears to be a designer addition within the approved mockup. It is low-risk (no RPC/schema/data-model
  touch) and does not block INC-15's READY status, but pm may want a one-line FR36 amendment for
  traceability. Tech-lead includes it in scope here since dev must build against the approved mockup
  as-is.

### 16.11.5 New backend surface — exactly two RPCs, nothing else (scoping the grep rule)

**Why a plain client-side two-step write is not good enough here.** `holdings.ticker` is a foreign key to
`watchlist.ticker` with no `ON DELETE CASCADE` (`sql/schema.sql` — Decision #40 forbids a schema change, so
this FK stays exactly as-is). Two structural facts follow directly from that: (1) a watch-only→held
transition must create `holdings` and flip `watchlist.status` together — if only one write lands (network
drop, tab close, RLS reject), the ticker ends up in a state FR37 explicitly says must never exist (`held`
with no `holdings` row, or `watch-only` with an orphaned `holdings` row); (2) deleting a ticker with an
existing `holdings` row must delete `holdings` before `watchlist`, or the FK rejects the second delete
outright. Two independent sequential `supabase.from(...).update()/.insert()/.delete()` calls from the
browser cannot guarantee this ordering survives a partial failure — the same class of problem this
codebase already treats as first-class elsewhere (`set_kill_switch`'s single-transaction RPC;
`design.md` §0 load-bearing decision #13's "checkpoint ordering must be exact, not best-effort"). The fix
is the same pattern already established for `set_kill_switch`: **wrap both writes in one
`SECURITY DEFINER` Postgres function**, so partial failure is structurally impossible (a Postgres function
body is one transaction).

**New file: `sql/tickers_screen_rpc.sql`** — the *only* new SQL this increment introduces:

```sql
create or replace function public.set_ticker_holding_status(
  p_ticker text, p_status text, p_shares numeric default null, p_cost_basis numeric default null
) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then
    raise exception 'not authorized';
  end if;
  if p_status = 'held' then
    if p_shares is null or p_shares <= 0 or p_cost_basis is null or p_cost_basis <= 0 then
      raise exception 'shares and cost_basis must both be > 0 to mark a ticker held';
    end if;
    insert into public.holdings (ticker, shares, cost_basis, currency)
      values (p_ticker, p_shares, p_cost_basis, 'USD') -- currency is overwritten unconditionally by the
                                                        -- existing holdings_derive_currency trigger (§16.3)
    on conflict (ticker) do update set shares = excluded.shares, cost_basis = excluded.cost_basis;
    update public.watchlist set status = 'held' where ticker = p_ticker;
  elsif p_status = 'watch-only' then
    delete from public.holdings where ticker = p_ticker;
    update public.watchlist set status = 'watch-only' where ticker = p_ticker;
  else
    raise exception 'unknown status %', p_status;
  end if;
end; $$;

grant execute on function public.set_ticker_holding_status(text, text, numeric, numeric) to authenticated;

create or replace function public.delete_ticker(p_ticker text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then
    raise exception 'not authorized';
  end if;
  delete from public.holdings where ticker = p_ticker;   -- no-op if none exists
  delete from public.watchlist where ticker = p_ticker;
end; $$;

grant execute on function public.delete_ticker(text) to authenticated;
```

Both mirror `set_kill_switch`'s exact shape (`operational-controls.md` §13, `admin-portal.md` §16.6):
`SECURITY DEFINER`, `is_admin()`-gated, `grant execute ... to authenticated` only (no anon grant). **Plain
field edits that do not change `status`** (e.g. editing `market`/`type` on an already-watch-only ticker, or
editing `shares`/`cost_basis` on an already-held ticker without flipping status) are **not** routed through
these RPCs — they remain direct `supabase.from("watchlist").update(...)` / `.from("holdings").update(...)`
calls under the existing `admin_write_watchlist`/`admin_write_holdings` policies, exactly as today. The new
RPCs exist only for the two operations that must be transactional: a status flip, and a full-ticker delete.

**Structural enforcement (mirrors §16.10/INC-14's rule, scoped to name these two new exceptions
explicitly):** a `git diff` grep across every file INC-15 touches for
`supabase\.|validateHoldingsRow|validateTunableValue|is_admin|set_kill_switch|\.rpc\(|createClient` is
expected to show matches **only** for: (a) `.rpc('set_ticker_holding_status', ...)` / `.rpc('delete_ticker',
...)` call sites (the two new RPCs this section defines), (b) `validateHoldingsRow`/`validateWatchlistRow`
calls carried over unchanged from the pre-merge forms, and (c) `is_admin()` appearing inside
`sql/tickers_screen_rpc.sql` itself. Any other match is out of scope and a blocker.

**Known pre-existing gap, explicitly out of scope for this increment:** editing a held ticker's `market`
(e.g. US→TSX) through the merged form does not re-run `holdings_derive_currency` (that trigger fires only
on writes *to* `holdings`, not on `watchlist.market` changing) — this gap pre-dates INC-15 and is not
introduced or worsened by it (the separate pre-merge watchlist/holdings screens had the identical gap).
Not fixed here; flagged for a future increment if Arjun wants it closed.

### 16.11.6 Nav item count, files, requirement coverage

- **Nav goes from four items to three (plus sign-out):** `AuthGuard.tsx`'s nav renders `Tickers` (replaces
  `Watchlist`), `Tunables`, `Track record`, `Sign out` — the `Holdings` link is removed entirely, matching
  FR36's explicit "4→3" text.
- **Routes:** new `admin-portal/app/(app)/tickers/page.tsx` replaces both `admin-portal/app/(app)/
  watchlist/page.tsx` and `admin-portal/app/(app)/holdings/page.tsx` (both deleted). No redirect needed —
  single-user tool, no external links to the old routes to preserve.
- **Files INC-15 may touch (allow-list):** `admin-portal/components/NavToggle.tsx`,
  `admin-portal/components/AuthGuard.tsx`, `admin-portal/app/globals.css`, `admin-portal/app/(app)/
  tickers/page.tsx` (new), and one new modal component (e.g. `admin-portal/components/
  TickerEditModal.tsx`) if the combined form needs local state beyond what the page file can hold cleanly;
  deletions of `admin-portal/app/(app)/watchlist/page.tsx` and `admin-portal/app/(app)/holdings/page.tsx`;
  `sql/tickers_screen_rpc.sql` (new, §16.11.5). No other file, in any directory, is in scope — `app/
  (app)/tunables/page.tsx`, `app/(app)/track-record/page.tsx`, `components/KillSwitchToggle.tsx`, and every
  `scripts/*.py`/`lib/*.ts` file outside the two RPC call sites are untouched.
- **Requirement coverage:** FR36 → §16.11.3/§16.11.4; FR37 → §16.11.4/§16.11.5; FR38 (branding rename) →
  dev/designer directly, no design content needed (trivial string change, per the orchestrator's brief);
  NFR8's navigation-mechanism bullet → §16.11.1 (defect fix)/§16.11.2 (new mechanism).
