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
existing. Pending GATE 3.

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

**Fail-safe on a failed fetch — REVISED 2026-07-27, Decision #28 (refines #27, does not change the
table above):** a fixed hardcoded Python literal as the *only* fallback would silently freeze at
whatever value happened to be in the code the last time that line was edited, drifting stale from
whatever's actually been curated via the portal in day-to-day use — defeating the point of a
portal-editable source of truth. Instead, `scripts/config.py` falls back to the **last
successfully-fetched value**, read from a **repo-committed cache file**, `tunables_cache.json` at the
**repo root** (REV-046, see naming note below) — reusing the exact "commit only if changed" mechanism
`.github/workflows/publish-prices.yml` already uses for `pages/prices.json` (verified directly against
that file's current content, not assumed):

```
git add pages/prices.json
if git diff --cached --quiet; then
  echo "prices.json unchanged — nothing to commit."
else
  git commit -m "chore: refresh dashboard prices.json [skip ci]"
  git pull --rebase origin "${GITHUB_REF_NAME}" || true
  git push origin "HEAD:${GITHUB_REF_NAME}"
fi
```

That workflow also declares `permissions: contents: write` at the top level — required because the
default `GITHUB_TOKEN` is otherwise read-only for repo contents. **`hourly-watchlist.yml` has no
`permissions:` block at all today** (confirmed by reading the file directly) — INC-6 must add the same
`permissions: contents: write` block to it, or the new commit step will fail with a 403 on push.

**Naming/location — REV-046 fix, 2026-07-28:** the cache file is `tunables_cache.json` at the **repo
root**, not inside a `config/` subdirectory as an earlier draft of this section had it. `scripts/` is a
flat, non-package directory placed directly on `sys.path` (no `__init__.py`), so `import config` resolves
`scripts/config.py` by path order; a repo-root `config/` directory with no `__init__.py` is a valid
implicit Python namespace package that would **shadow `scripts/config.py`** whenever the repo root
precedes `scripts/` on `sys.path` — a real risk for a bare `python -c "import config"` from the repo root,
or any future tooling change, and one that costs nothing to avoid before the file exists. Repo-root
placement (alongside `README.md`, `requirements.txt`) is not importable as a package and cannot collide
with the `config` module name.

**Seed file (`tunables_cache.json`, committed at INC-6 time):** must contain **exactly** the same
10 key/value pairs as the `tunables` table's seed migration above — including `ALERTS_ENABLED: "true"`,
not `config.py`'s bare `"false"` literal, for the same cutover-safety reason. Any mismatch between the
two seeds would show up as a spurious "changed" commit the moment the first real Supabase fetch
succeeds and gets compared… except comparison happens file-vs-file inside git, not against the table, so
a mismatched seed wouldn't actually *fail* anything — it would just mean day one's cache disagreed with
day one's table for no operator-visible reason, which is exactly the kind of drift this mechanism exists
to prevent. Keep them identical.

```json
{
  "GEMINI_MODEL": "gemini-2.5-flash",
  "GEMINI_MODEL_BACKUP": "gemini-2.5-flash-lite",
  "ALERTS_ENABLED": "true",
  "DISCOVERY_GAINER_PCT": "5",
  "DISCOVERY_LOSER_PCT": "-5",
  "DISCOVERY_VOL_SPIKE": "2.0",
  "DISCOVERY_MIN_MARKET_CAP": "2000000000",
  "DISCOVERY_MIN_MARKET_CAP_INR": "50000000000",
  "DISCOVERY_SHORTLIST_MAX": "15",
  "DISCOVERY_PUSH_COOLDOWN_DAYS": "7"
}
```

**`scripts/config.py` — two-tier fallback chain, REVISED 2026-07-28** (this run's live Supabase fetch →
repo-committed cache; **no third tier**). The prior draft of this section added a permanent hardcoded
Python literal as a third, last-resort floor baked directly into each `_tunable()` call site. Arjun
objected during review and asked that it be re-checked against what was actually specified. Re-reading
`requirements.md` FR30 directly: *"`scripts/config.py` fetches them from this table at run start, falling
back to the last successfully-fetched value, cached in a repo-committed file, itself seeded from an
initial hardcoded default on first run, if the fetch fails."* That sentence describes exactly two runtime
tiers — table, then cache file — plus a one-time **seed-time** default used to populate the cache file's
initial content at INC-6 build time (already covered above, "Seed file" section). It does not describe a
third tier consulted at every run. **The permanent third tier was tech-lead's own design elaboration, not
a requirement** — confirmed by this re-read, not asserted from Arjun's summary alone.

Arjun's substantive objection also holds independent of the text-matching question: a third tier means the
same default value lives in three places that must be kept in sync (the SQL seed migration, the committed
cache JSON, and a Python literal per key) — the exact failure class as the `ALERTS_ENABLED` seed-value bug
caught earlier in this same design pass (§ "Seed migration" above), except permanent and load-bearing
instead of a one-time seed mistake. Removed.

**Failure mode when both tiers miss a key — decided here, not deferred:** with no third tier, if the live
Supabase fetch fails or omits a key *and* the cache file is missing, unreadable, or also missing that key,
there is no default left to silently return. `_tunable()` now **fails loud**: it raises `SystemExit` naming
the key and both failed sources, rather than inventing or guessing a value. This mirrors
`scripts/config.py`'s own existing `require_secrets()`, which already fails fast with a clear message on a
missing required secret instead of limping along on an unset/empty value — same posture, same module,
applied consistently to another class of "config this program cannot safely start without." The
alternative (silently picking *some* value — e.g. `None`, `0`, or re-adding a hidden literal) reintroduces
exactly the drift risk Arjun flagged, just moved one layer down; failing loud makes the double-failure
visible immediately (a crashed scheduled workflow run, alerting via NFR2's dead-man monitor) instead of
running the trading logic on a silently wrong tunable, which is strictly worse for a system whose output
drives real alerts. This is a **deliberately rare** failure path — the cache file is repo-committed (not
volatile), and Supabase's own base URL/secret-key resolution already goes through `require_secrets()`
before any of this runs — but "rare" is exactly why it must fail loud rather than fail silent: nobody is
watching for a quiet, wrong default on a path nobody expects to exercise.

**REV-041 fix, 2026-07-28 — timeout + a deterministic offline path.** The sketch above (and every version
of this section before this fix) called `create_client(...).table(...).execute()` with no timeout
argument. `supabase-py`'s default PostgREST timeout is not short, and `config.py` is imported by *every*
module and every entry point — a hung or slow Supabase connection would stall the start of every scheduled
run, on a module that had never made a network call before this increment. Two additions, both below:
(a) an explicit, non-curated timeout tunable (`TUNABLES_FETCH_TIMEOUT_MS`) passed into the client — it
cannot itself live in the `tunables` table, since resolving it is a precondition for fetching that table
at all; (b) an explicit `SKIP_TUNABLES_FETCH` offline switch so tests and local runs deterministically use
tier 2 (the cache) instead of making a real network call — needed because `tests/conftest.py` points
`SUPABASE_URL` at a fake host and `config` is reloaded roughly fifteen times per suite run (`test_config.py`'s
`reload_config` fixture); without this, INC-6 would turn every test run into ~15 live connection attempts
against that fake host. `_fetch_tunables()` is the **single patchable seam** for both — qa mocks this one
function, the same pattern `ai_judge._client` already establishes as this codebase's convention for an
external-call boundary.

```python
TUNABLES_FETCH_TIMEOUT_MS = int(os.environ.get("TUNABLES_FETCH_TIMEOUT_MS", "5000"))   # non-curated;
    # bootstraps the fetch below, so it cannot itself be sourced from the `tunables` table

_CACHE_PATH = pathlib.Path(__file__).resolve().parent.parent / "tunables_cache.json"   # repo root,
    # REV-046 — NOT inside a `config/` subdirectory (see the naming note above the JSON seed block)

_TUNABLE_CASTS: dict[str, "Callable[[str], object]"] = {}   # populated by every _tunable() call below;
    # write_tunables_cache_if_fetched() reuses this exact registry to validate before persisting (REV-036)
    # rather than re-deriving cast rules in a second place.

def _fetch_tunables() -> dict[str, str]:
    """This run's live fetch. Returns {} on ANY failure, or when explicitly
    skipped (REV-041's offline path, below) — NEVER writes to the cache file
    itself (only write_tunables_cache_if_fetched(), called explicitly, does
    that — see below). This is the ONE function qa patches to test every
    fallback-tier path deterministically, mirroring ai_judge._client."""
    if os.environ.get("SKIP_TUNABLES_FETCH", "false").lower() == "true":
        print("  [config] SKIP_TUNABLES_FETCH set; using tunables_cache.json only "
              "(no live Supabase call made) — deterministic for tests/local runs")
        return {}
    try:
        client = create_client(
            SUPABASE_URL, SUPABASE_SECRET_KEY,
            options=ClientOptions(postgrest_client_timeout=TUNABLES_FETCH_TIMEOUT_MS / 1000),
            # exact kwarg/unit to confirm against the installed supabase-py version at INC-6 build time
        )
        rows = client.table("tunables").select("key,value").execute().data
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"  [config] tunables fetch failed ({e}); falling back to tunables_cache.json")
        return {}

def _load_tunables_cache() -> dict[str, str]:
    """Repo-committed last-known-good values, read once at import time. A
    missing/corrupted file returns {} — every key lookup then falls through
    to _tunable()'s fail-loud SystemExit below if the live fetch also missed
    it. No hardcoded floor exists past this point."""
    try:
        return json.loads(_CACHE_PATH.read_text())
    except Exception as e:
        print(f"  [config] tunables cache read failed ({e}); no fallback tier left for these keys")
        return {}

_TUNABLES = _fetch_tunables()               # tier 1: this run's live Supabase fetch
_TUNABLES_CACHE = _load_tunables_cache()    # tier 2: last-known-good, repo-committed
TUNABLES_DEGRADED = False    # REV-045: set True the first time any curated key resolves from tier 2
                              # instead of tier 1 this run — read by every entry point's heartbeat write
                              # (below) so a persistently-stale tunables state is monitor-visible, not silent.

def _tunable(key: str, cast):
    """Two tiers only: live Supabase fetch, then the repo-committed cache.

    REV-036 fix: a tier-1 value that FAILS TO CAST now fails loud immediately
    (SystemExit) instead of silently falling through to tier 2. A cast failure
    on a value Supabase actually returned is an operator-caused data error
    (e.g. a bad portal edit — `5%` typed into a numeric field), not a fetch
    failure; silently falling through let that bad value later get persisted
    into the cache by write_tunables_cache_if_fetched() (see below), turning
    one typo into a permanently corrupted last-known-good. Only a MISSING key
    (source.get(key) is None) falls through to the next tier — a genuinely
    absent value, not a malformed one.
    """
    global TUNABLES_DEGRADED
    raw1 = _TUNABLES.get(key)
    if raw1 is not None:
        try:
            return cast(raw1)
        except (TypeError, ValueError):
            raise SystemExit(
                f"[config] tunable {key!r} was fetched from Supabase as {raw1!r} but failed to "
                f"cast. This is an operator-entered value error, not a fetch failure — refusing "
                f"to fall through to the cache tier and risk persisting it as the new "
                f"last-known-good. Fix the value in the tunables table (portal or SQL editor)."
            )
    raw2 = _TUNABLES_CACHE.get(key)
    if raw2 is not None:
        try:
            value = cast(raw2)
        except (TypeError, ValueError):
            raise SystemExit(
                f"[config] tunable {key!r} unavailable: Supabase tunables fetch did not include "
                f"this key, AND the cached value {raw2!r} in tunables_cache.json failed to cast. "
                f"Refusing to start with an unknown value for a portal-controlled tunable."
            )
        TUNABLES_DEGRADED = True
        print(f"  [config] tunable {key!r} resolved from tunables_cache.json (tier 2) — "
              f"live Supabase fetch did not include it this run")
        return value
    raise SystemExit(
        f"[config] tunable {key!r} unavailable: Supabase tunables fetch failed or did not "
        f"include this key, AND tunables_cache.json is missing, unreadable, or also "
        f"missing this key. Refusing to start with an unknown value for a portal-controlled "
        f"tunable rather than silently guessing one."
    )

def write_tunables_cache_if_fetched() -> None:
    """Validate and merge THIS RUN'S successful Supabase fetch into the
    existing cache, then write the result to tunables_cache.json. No-ops
    silently if this run's fetch failed entirely (_TUNABLES is empty) — a
    failed fetch never touches a good cache.

    REV-036 fix (three changes from the original draft, which serialized
    `_TUNABLES` verbatim and unconditionally):
      1. VALIDATE before writing: a fetched value is only persisted if it
         still casts cleanly under `_TUNABLE_CASTS[key]` (populated by every
         `_tunable()` call above). In practice a tier-1 cast failure now
         raises SystemExit during import (see `_tunable()` above) before this
         function is ever reached, so this re-check is redundant with that
         invariant today — kept anyway as an independent safety net, since
         trusting a single enforcement point for "never persist a bad value"
         is exactly the kind of assumption that's cheap to double up on.
      2. MERGE, never overwrite: start from the existing cache and only
         update keys this run's fetch actually returned. The original draft
         wrote `_TUNABLES` directly, so a fetch that legitimately omitted a
         key (e.g. a transient partial response) silently DELETED that key's
         last-known-good from the file — the exact opposite of what
         "last-known-good" promises. The merged file can never be smaller
         than the cache already on disk.
      3. No-op cleanly when nothing changed, so the workflow's git-diff step
         (not this function) still decides whether a commit is needed —
         unchanged behavior from the original draft, preserved here.

    Decision #28: hourly-watchlist.yml is the SOLE writer (runs most
    frequently, every 30 min in-hours). Called ONLY from run_hourly.py's
    entry point — run_discovery.py and publish_prices.py never call this;
    they remain pure read-only consumers of _TUNABLES_CACHE via _tunable()
    above, same as every script already reads it."""
    if not _TUNABLES:
        return
    merged = dict(_TUNABLES_CACHE)
    for key, raw in _TUNABLES.items():
        cast = _TUNABLE_CASTS.get(key)
        if cast is None:
            continue   # a key this run never read via _tunable(); leave the cache's value untouched
        try:
            cast(raw)   # validate only — the cache stores the raw string, same shape as today
        except (TypeError, ValueError):
            print(f"  [config] tunables cache write-back: {key!r}={raw!r} failed to validate; "
                  f"keeping the existing cached value for this key")
            continue
        merged[key] = raw
    if merged == _TUNABLES_CACHE:
        return
    _CACHE_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")

# example usage — replaces the plain os.environ.get(...) reads for these 10 keys only;
# every other config.py tunable (the ~18 non-curated keys) is completely untouched:
GEMINI_MODEL = _tunable("GEMINI_MODEL", str)
ALERTS_ENABLED_TABLE = _tunable("ALERTS_ENABLED", lambda v: str(v).lower() == "true")
```

`run_hourly.py`'s change: one line, early in `main()` (before the market gate, so the cache refreshes on
every dispatch regardless of whether the market check inside `main()` goes on to skip work) —
`config.write_tunables_cache_if_fetched()`. Still "no logic in entry points": it's a single delegate call
to a `config.py` function, same shape as every other entry-point/module boundary in this codebase.
**REV-045 fix — a second, smaller addition to all three entry points** (`run_hourly.py`,
`run_discovery.py`, `publish_prices.py`): each already computes a `degraded` boolean/count before writing
its `run_heartbeat` status (`components.md` §4.8, issue #2's `partial`-vs-`ok` rule). Each of those three
existing expressions gains `or config.TUNABLES_DEGRADED` — e.g. `run_hourly.py:155` becomes `status =
"partial" if (degraded or config.TUNABLES_DEGRADED) else "ok"` — so a run that silently fell back to the
tunables cache is monitor-visible via NFR2's existing dead-man/degraded-alert path (REV-042's fix, below in
`components.md`, is what makes the SQL side of "degraded" actually alert for discovery/publish-prices; this
is the Python side setting the status correctly for tunables specifically). No new mechanism — reusing the
status-computation seam that already exists at all three sites.

**Workflow step, `hourly-watchlist.yml` only** (added directly after "Run hourly watchlist check",
mirroring `publish-prices.yml`'s "Commit prices.json if changed" step exactly — same bot identity, same
`[skip ci]` convention, same `git pull --rebase` race guard):

```yaml
permissions:
  contents: write   # NEW — this workflow has no permissions block today; required for the push below

# ...unchanged steps above...

      - name: Commit tunables cache if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add tunables_cache.json
          if git diff --cached --quiet; then
            echo "tunables_cache.json unchanged — nothing to commit."
          else
            git commit -m "chore: refresh tunables cache [skip ci]"
            git pull --rebase origin "${GITHUB_REF_NAME}" || true
            git push origin "HEAD:${GITHUB_REF_NAME}"
          fi
```

`daily-discovery.yml` and `publish-prices.yml` get **no** YAML changes — they already check out the full
repo (so `tunables_cache.json` is present on disk via `actions/checkout`), read it transparently
through `_tunable()`'s tier-2 fallback exactly like every other script, and never call
`write_tunables_cache_if_fetched()`. No new permission needed on either — reading a checked-out file
requires no special token scope.

**`ALERTS_ENABLED` — the one key with a real second input to reconcile.** Unchanged reasoning from the
prior pass, restated against the new fallback chain: `ALERTS_ENABLED` is *also* driven by the existing
`workflow_dispatch` input (`${{ inputs.alerts_enabled }}` → env var `ALERTS_ENABLED`, still untouched, no
YAML change), the documented **safe forced-test pattern** (`components.md` §4.1: "for any off-hours
forced run, set `ALERTS_ENABLED=false`"). That must keep working exactly as today. Resolution — pure
Python, unchanged in shape from the prior pass, just now backed by the two-tier `_tunable()` chain instead
of a flat table-or-literal one:

```python
_alerts_input = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"   # workflow_dispatch input, unchanged
ALERTS_ENABLED = _alerts_input and ALERTS_ENABLED_TABLE   # ALERTS_ENABLED_TABLE resolves through
                                                            # table -> cache; if BOTH miss, _tunable()
                                                            # has already raised SystemExit above — this
                                                            # line never runs on an unresolved value
```

The portal's toggle can only ever **suppress** alerts, never force them on over an explicit manual
dry-run request. (The pre-existing `${{ vars.GEMINI_MODEL || '...' }}` / `_BACKUP` Variable wiring
already in `hourly-watchlist.yml` remains a harmless, unread vestige — `_tunable()` never consults that
env var; optional future cleanup, not INC-6 scope.)

The 10 keys (verbatim from FR30 / `requirements.md` §10's portal-exposure note): `GEMINI_MODEL`,
`GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`, `DISCOVERY_LOSER_PCT`,
`DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_MARKET_CAP_INR`,
`DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`. No other tunable is reachable from this UI;
the other ~18 non-curated tunables are completely unaffected — still GitHub Variables/code defaults.

**Status: all open questions from earlier passes are now resolved, not deferred.** Decision #27 closed
the GitHub-Variables wiring gap (table is now how all 10 keys take effect). Decision #28 closes the
failed-fetch fallback question (cache file, not a frozen literal) **and** the write-ownership question
(`hourly-watchlist.yml` sole writer, confirmed by Arjun — not a proposal any more). The 2026-07-28 pass
closes one more, raised by Arjun on review: the fallback chain is two tiers only (table, then cache
file) — the permanent third hardcoded-literal tier was tech-lead's own design elaboration beyond FR30 /
Decision #28's actual text, not a requirement, and has been removed; a simultaneous double-failure
(Supabase fetch fails or misses a key, and the cache file is also missing/unreadable/missing that key)
now fails loud via `SystemExit`, matching `require_secrets()`'s existing fail-fast posture for missing
critical config rather than inventing a silent guess. **No open question remains for INC-6.**

**Pass 11 review fixes (2026-07-28, reviewer REV-033/036/041/044/045/046):** RLS enabled on `tunables`
with zero anon policies and the write policy narrowed to `select, update` plus a key-registry `check`
(REV-033/044); the cache write-back now validates before persisting, merges instead of overwriting, and a
tier-1 cast failure fails loud instead of silently degrading (REV-036); the Supabase fetch gained an
explicit timeout tunable and a deterministic offline test seam (REV-041); a tier-2 fallback now sets
`config.TUNABLES_DEGRADED`, surfaced through all three entry points' existing heartbeat status computation
(REV-045); the cache file moved to `tunables_cache.json` at the repo root, out of a `config/` subdirectory
that would have collided with the `config` module name (REV-046). **Follow-up needed at INC-6 build time,
not a design gap:** `tests/conftest.py` needs a corresponding `os.environ.setdefault("SKIP_TUNABLES_FETCH",
"true")` alongside its existing fake-secrets block, so the test suite exercises the offline path by
default — this is qa's file, noted here for INC-6's dev/qa handoff, not implemented in this design pass.
