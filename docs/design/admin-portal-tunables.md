# Admin portal — tunables editor (FR30)

Split out of `docs/design/admin-portal.md` (2026-07-27, this section grew past the point where INC-6
should have to load the rest of the portal's design to build against it) — see `docs/design.md` for the
index, module map, §0 load-bearing decisions, increment plan, and requirement coverage map, and
`admin-portal.md` for the portal's auth/RLS model (§16.2, `is_admin()`/`admin_allowlist`) that this
section depends on directly. Section number (§16.4) is unchanged from before the split — it's still part
of §16 (Admin portal architecture), just in its own file now.

**Status: DRAFT** — covers FR30, refined since the 2026-07-26 CR (Decision #27, 2026-07-27, supersedes
#24; Decision #28, 2026-07-27, refines #27) and once more on 2026-07-28 (tech-lead correction, no new
Decision # — see fallback-chain section below: a permanent third fallback tier had been added during
design elaboration beyond what Decision #28 / FR30 actually specify; Arjun's review caught it and it's
removed here). Builds in **INC-6**, which depends on INC-5's `admin_allowlist`/`is_admin()` already
existing. GATE 3 was passed for the whole change request; INC-6 itself has not started.

---

### 16.4 Tunables editor (FR30) — REVISED 2026-07-27, Decisions #27 (supersedes #24) and #28 (refines
#27); fallback chain narrowed further 2026-07-28 (see below)

**The former design proposed a GitHub-PAT-holding Vercel proxy that wrote directly to GitHub Actions
Variables.** During design that premise was checked against the live workflow YAML and found false for 8
of the 10 curated keys (the superseded write-up is preserved in git history, not restated here — doc
hygiene) — only `GEMINI_MODEL`/`GEMINI_MODEL_BACKUP` were actually wired from a GitHub Variable into a
running workflow; `ALERTS_ENABLED` came from a `workflow_dispatch` input, and the seven `DISCOVERY_*`
keys weren't wired to anything. Fixing that gap required touching `scripts/config.py` either way, which
removed the entire reason to prefer GitHub Variables as the target. **Decision #27** (requirements.md,
approved by Arjun) moves the source of truth for these 10 keys to a new Supabase `tunables` table
instead — consolidating onto the control plane the system already trusts (Supabase already holds
`watchlist`, `holdings`, and the FR24 kill-switch flag), reusing the *exact* auth mechanism already built
for FR28/29 (no second authorization scheme, see `admin-portal.md` §16.2's `is_admin()`), and eliminating
the GitHub PAT / proxy route / third secrets store entirely. **This is a net simplification, not an
addition** — no GitHub API integration code, no server-only secret anywhere in the portal, one
authorization mechanism for every write the portal makes.

**Schema** (`tunables` table — exact columns per FR30):

```sql
create table public.tunables (
  key         text primary key check (key in (           -- REV-044: fixed FR30 key registry — the
    'GEMINI_MODEL', 'GEMINI_MODEL_BACKUP', 'ALERTS_ENABLED',                 -- portal can never widen
    'DISCOVERY_GAINER_PCT', 'DISCOVERY_LOSER_PCT', 'DISCOVERY_VOL_SPIKE',    -- its own reach by
    'DISCOVERY_MIN_MARKET_CAP', 'DISCOVERY_MIN_MARKET_CAP_INR',             -- inserting a row for a
    'DISCOVERY_SHORTLIST_MAX', 'DISCOVERY_PUSH_COOLDOWN_DAYS'                -- key nothing reads
  )),
  value       text not null,               -- stored as text; scripts/config.py casts per key
  description text not null,               -- human-readable purpose (FR30: never a bare input box)
  example     text not null,               -- an example legal value
  updated_at  timestamptz not null default now(),
  updated_by  text
);
alter table public.tunables enable row level security;

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

-- REV-044 fix, 2026-07-28: narrowed from `for all` to `for select, update` only.
-- FR30 needs UPDATE on the ten migration-seeded rows — nothing more. `for all`
-- (the original draft) also granted INSERT/DELETE, which nothing in the
-- portal UI uses; a stray DELETE would silently pin that key to whatever the
-- cache/hardcoded-seed-time value was forever (no error surfaces — tier 2
-- still resolves it, see the fallback chain below), and an INSERT could add a
-- row for a key `scripts/config.py` never reads. The CHECK constraint above is
-- the second half of this fix — even a same-admin UPDATE (the only op this
-- policy allows) cannot rename a row's `key` to something outside the fixed
-- 10, since `key` is the primary key and any UPDATE that changed it would
-- have to satisfy the CHECK on the new value.
create policy "admin_write_tunables" on public.tunables
  for select, update to authenticated
  using (public.is_admin())
  with check (public.is_admin());
```

`is_admin()` is defined in INC-5 (`admin-portal.md` §16.2) — this policy is a direct, literal caller of
it, not a re-implementation. **No anon/public policy exists, and no `insert`/`delete` policy exists for
any role, including `authenticated`** (REV-033/REV-044) — with RLS enabled, that means insert/delete on
this table is denied to everyone except the table owner (the seed migration below, which inserts the 10
rows as the owner, is unaffected). `scripts/config.py` reads it with the existing `SUPABASE_SECRET_KEY`
(service role, bypasses RLS, same posture every other Python module already uses — no new grant needed
there).

**Seed migration (INC-6):** one `insert` per curated key, at the value/description/example already
documented for these keys in `requirements.md` §10 / `scripts/config.py`'s existing comments — **no
behavior change at cutover** (Decision #27's explicit requirement: seeded values equal the literals they
replace). **`ALERTS_ENABLED` needs care here:** `scripts/config.py`'s own bare literal default for this
key is the conservative `"false"` (`os.environ.get("ALERTS_ENABLED", "false")` — Phase-2-era comment:
"runs the full logic but sends NO real pushes"), but the system's actual **live** default is effectively
`true` on every scheduled run today, via the `workflow_dispatch` input's own YAML default (below).
Seeding this row as `"false"` would silently break production alerting the moment the table becomes
authoritative (violates Decision #27's "no behavior change at cutover"). **The seed value for
`ALERTS_ENABLED` must be `"true"`**, matching today's actual live behavior, not `config.py`'s bare
literal. `GEMINI_MODEL_BACKUP`'s `description` row states "leave empty to disable the fallback model" —
since the table always has a row once seeded (no more GitHub-Variable-style "unset" ambiguity), the old
proxy design's special-cased "current effective value" display logic is no longer needed: the portal
just renders whatever `value` currently holds.

**Portal UI:** no static metadata array in the portal codebase anymore (`description`/`example` are now
DB columns, seeded once) — the tunables screen is a straight read/render/write against
`public.tunables`, using the same browser-side Supabase client + RLS pattern as watchlist/holdings
(`admin-portal.md` §16.3). **No Next.js API route, no server-only secret, for this feature at all.**

**Runtime fallback chain, cache file, timeout, and workflow write-back:** moved to
`docs/design/tunables-fallback.md` (2026-07-28, doc hygiene — this file plus that content together
exceeded the ~400-line module-split guidance once the Pass-11 review fixes landed, REV-033/036/041/044/
045/046). That file covers `scripts/config.py`'s two-tier fetch → cache fallback chain, the fail-loud
`SystemExit` behavior, `TUNABLES_FETCH_TIMEOUT_MS`/`SKIP_TUNABLES_FETCH`, `write_tunables_cache_if_fetched()`,
`hourly-watchlist.yml`'s new commit step, and the `ALERTS_ENABLED` AND-gate — same §16.4, second file.
**No open question remains for INC-6** (both files).
