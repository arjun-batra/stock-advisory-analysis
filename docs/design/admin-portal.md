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

**2026-07-31 addendum (NFR8, Decision #39, INC-13 — READY, dev may start):** §16.10 below adds the
responsive/visual-modernization design for the five screens covered by §16.1–§16.6. This is a
presentation-layer-only addition — it changes no auth/RLS/schema/data-fetching content in §16.1–§16.9,
which remain as-built/IMPLEMENTED exactly as documented above and require no revision for NFR8. The
user has selected **Direction G** ("Compact Toggle") as the final visual/interaction direction — see
§16.10's updated content below for the exact reference files and details dev builds against.

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
| NFR8 (responsive & modern admin-portal UI/UX, zero functional regression) | §16.10 — **READY**, Direction G selected, INC-13 (`increment-plan.md`) |

### 16.10 Responsive & visual design system (NFR8, INC-13) — READY, Direction G selected

**Gate cleared 2026-07-31:** designer published `docs/ux-spec.md` with mockup directions covering all
five screens, and the user (Arjun) selected **Direction G — "Compact Toggle"**
(`docs/ux-mockups/direction-g-compact-toggle.html`; design detail in `docs/ux-spec.md` §7.4, built on
Direction F's density §7.3 and Direction E's toggle component §7.2). INC-13 is now **READY — dev may
start a build plan.** This section defines the **technical mechanism** (breakpoints, layout system,
structural enforcement) that Direction G is implemented through; the visual/interaction language itself
is designer's + the user's call and is specified in `docs/ux-spec.md`, not restated here.

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
- `.crud-table` (`watchlist`/`holdings` pages) — below the tablet breakpoint, switches from `<table>`
  layout to a stacked "card per row" layout via CSS only (`tr { display:block }`, `td::before { content:
  attr(data-label) }`), reading a `data-label="<column header>"` attribute added to each `<td>` in markup
  (a markup addition, not a logic change) — this satisfies "no horizontal scrolling" literally at phone
  width rather than wrapping the table in a scroll region. At tablet/desktop widths the existing `<table>`
  layout is kept.
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
