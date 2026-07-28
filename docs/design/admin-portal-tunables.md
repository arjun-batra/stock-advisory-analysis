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

`is_admin()` is defined in INC-5 (`admin-portal.md` §16.2) — this policy is a direct, literal caller of
it, not a re-implementation. No anon/public policy — only the authenticated admin (portal) reads/writes
this table; `scripts/config.py` reads it with the existing `SUPABASE_SECRET_KEY` (service role, bypasses
RLS, same posture every other Python module already uses — no new grant needed there).

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
successfully-fetched value**, read from a **repo-committed cache file**, `config/tunables_cache.json` —
reusing the exact "commit only if changed" mechanism `.github/workflows/publish-prices.yml` already uses
for `pages/prices.json` (verified directly against that file's current content, not assumed):

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

**Seed file (`config/tunables_cache.json`, committed at INC-6 time):** must contain **exactly** the same
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

```python
_CACHE_PATH = pathlib.Path(__file__).resolve().parent.parent / "config" / "tunables_cache.json"

def _fetch_tunables() -> dict[str, str]:
    """This run's live fetch — unchanged from Decision #27. Returns {} on ANY
    failure; NEVER writes to the cache file itself (only write_tunables_cache_
    if_fetched(), called explicitly, does that — see below)."""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
        rows = client.table("tunables").select("key,value").execute().data
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"  [config] tunables fetch failed ({e}); falling back to config/tunables_cache.json")
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

def _tunable(key: str, cast):
    """Two tiers only: live Supabase fetch, then the repo-committed cache. If
    neither has a usable value for `key`, fail loud rather than guess — same
    posture as require_secrets() above for a missing required secret."""
    for source in (_TUNABLES, _TUNABLES_CACHE):    # tier 1, then tier 2
        raw = source.get(key)
        if raw is not None:
            try:
                return cast(raw)
            except (TypeError, ValueError):
                print(f"  [config] tunables value for {key!r} ({raw!r}) failed to cast; trying next tier")
                continue
    raise SystemExit(
        f"[config] tunable {key!r} unavailable: Supabase tunables fetch failed or did not "
        f"include this key, AND config/tunables_cache.json is missing, unreadable, or also "
        f"missing this key. Refusing to start with an unknown value for a portal-controlled "
        f"tunable rather than silently guessing one."
    )

def write_tunables_cache_if_fetched() -> None:
    """Serialize THIS RUN'S successful Supabase fetch to config/tunables_cache.json,
    unconditionally overwriting the file with current values — mirrors
    publish_prices.py always writing pages/prices.json fresh and letting the
    WORKFLOW's git-diff step (not this function) decide whether anything
    actually changed and needs a commit. No-ops silently if this run's fetch
    failed (_TUNABLES is empty) — a failed fetch never overwrites a good cache.

    Decision #28: hourly-watchlist.yml is the SOLE writer (runs most
    frequently, every 30 min in-hours). Called ONLY from run_hourly.py's
    entry point — run_discovery.py and publish_prices.py never call this;
    they remain pure read-only consumers of _TUNABLES_CACHE via _tunable()
    above, same as every script already reads it."""
    if not _TUNABLES:
        return
    _CACHE_PATH.write_text(json.dumps(_TUNABLES, indent=2, sort_keys=True) + "\n")

# example usage — replaces the plain os.environ.get(...) reads for these 10 keys only;
# every other config.py tunable (the ~18 non-curated keys) is completely untouched:
GEMINI_MODEL = _tunable("GEMINI_MODEL", str)
ALERTS_ENABLED_TABLE = _tunable("ALERTS_ENABLED", lambda v: str(v).lower() == "true")
```

`run_hourly.py`'s only change: one line, early in `main()` (before the market gate, so the cache
refreshes on every dispatch regardless of whether the market check inside `main()` goes on to skip
work) — `config.write_tunables_cache_if_fetched()`. Still "no logic in entry points": it's a single
delegate call to a `config.py` function, same shape as every other entry-point/module boundary in this
codebase.

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
          git add config/tunables_cache.json
          if git diff --cached --quiet; then
            echo "tunables_cache.json unchanged — nothing to commit."
          else
            git commit -m "chore: refresh tunables cache [skip ci]"
            git pull --rebase origin "${GITHUB_REF_NAME}" || true
            git push origin "HEAD:${GITHUB_REF_NAME}"
          fi
```

`daily-discovery.yml` and `publish-prices.yml` get **no** YAML changes — they already check out the full
repo (so `config/tunables_cache.json` is present on disk via `actions/checkout`), read it transparently
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
