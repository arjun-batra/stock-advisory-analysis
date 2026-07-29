# Code map — one-page mental model

**Owner:** tech-lead. Backfilled 2026-07-29 (new CLAUDE.md requirement; project predates it). This is a
map for "does the code still match this" — for rationale read `docs/design.md` / `docs/design/*.md`.
Refresh whenever a merged increment changes structure.

## Modules

**`scripts/`** (Python pipeline; control plane = Supabase, execution = GitHub Actions)
- `config.py` — single tunables-resolution seam: env/secrets + FR30 curated fetch (Supabase `tunables`
  table → `tunables_cache.json` fallback, fail-loud on double-miss). All other modules import from here.
- `ingest.py` — yfinance wrapper (price/volume/headlines). `prefilter.py` — Yahoo screener + discovery
  gates. `ai_provider.py` — `AIProvider`/`GeminiProvider`, sole owner of the Gemini SDK. `ai_judge.py` —
  provider-neutral `judge_batch()`, talks only to `ai_provider`'s interface. `state.py` — Supabase
  read/write + verdict-change state machine. `notify.py` — ntfy push. `textutil.py` — shared helpers.
- `run_hourly.py`, `run_discovery.py`, `publish_prices.py` — thin entry points, no business logic;
  `run_hourly.py` is the only one that writes the tunables cache back.

**`admin-portal/`** (Next.js/Vercel; the one write-capable, human-authenticated surface)
- `app/` — `login/`, `auth/callback/` (only server route, no secret), `(app)/watchlist|holdings|
  tunables|track-record/`. `components/` — `AuthGuard.tsx`, `KillSwitchToggle.tsx`.
- `lib/supabase-client.ts` — the only Supabase client (browser, anon key + session), used by every
  feature. `lib/admin-guard.ts` — UI-layer allowlist check (UX only, not the security boundary).
  `lib/validation.ts` — form validation mirroring `sql/schema.sql` CHECKs, no new rules invented.
- **Boundary:** real authorization is Postgres RLS + `is_admin()` (`sql/admin_portal_rls.sql`); the
  portal has no server-only secret and no `app/api/` proxy anywhere (Decision #27).

**`sql/`** (one concern per file) — `schema.sql` (core tables + RLS), `scheduler_pgcron.sql` (pg_cron +
`dispatch_github_workflow()`), `phase5_monitoring.sql`/`enable_monitor_alerts_rls.sql` (dead-man's-switch
monitor), `dashboard_latest_call_view.sql` (dashboard read view), `kill_switch.sql` (FR24–26),
`admin_portal_rls.sql` (`admin_allowlist`, `is_admin()` — hard dependency for later admin migrations),
`admin_portal_tunables.sql` (`tunables` table + policy + seed), `kill_switch_portal_grant.sql` (portal
admin-check on kill-switch). Three files are historical/superseded/**not applied**, kept as markers only
(see each header): `drop_shadow_tables_migration.sql`, `dedup_watchlist_health_check.sql`,
`fix_missing_degraded_checks.sql`.

**`tests/`** — top-level `test_*.py` cover `scripts/`; `tests/admin_portal/*.test.ts` cover
`admin-portal/` (static/build/validation, no live Supabase in CI).

**`pages/`** — public read-only dashboard + detail page + `prices.json` (GitHub Pages); distinct from
`admin-portal/`, no write path, auth is client-side obfuscation only.

## End-to-end data flow

Supabase pg_cron → `dispatch_github_workflow()` → GitHub Actions (execution-only) → `scripts/` entry
points → yfinance + Gemini → `state.py` writes `call_log`/`verdict_state` → `notify.py` → ntfy →
dashboard/detail pages read Postgres (anon key, RLS) + `prices.json`. Separately, `admin-portal/`
reads/writes `watchlist`/`holdings`/`tunables`/`kill_switch_state` directly via browser Supabase client
+ RLS — no path through the Python pipeline or GitHub Actions.

## Where config lives

Application/business tunables: `scripts/config.py` (env vars + two-tier `tunables` fetch/cache chain).
Workflow-engine knobs: GitHub Actions repo Variables with literal fallback in the `.yml` files. Full
schema: `docs/design/non-functional-ops.md` §9.

## Extension points

New AI provider → implement `AIProvider` in `ai_provider.py`, no `ai_judge.py` change. New tunable →
add to `config.py` (+ `admin_portal_tunables.sql`'s key registry if portal-curated), never hardcode.
New portal feature → `app/` route + RLS policy on `is_admin()`, never a server-only secret or API proxy.

## Dependency rules

- `scripts/*.py` and `admin-portal/` never import each other — share only the Supabase database.
- `admin-portal/` holds no server-only secret; every write goes through the user's session JWT + RLS.
- `ai_judge.py` depends only on `ai_provider.py`'s interface, never the Gemini SDK directly.
- `config.py` is the sole tunables seam; nothing else reads `os.environ` or `tunables` directly.
- Entry points (`run_*.py`, `publish_prices.py`, every `admin-portal/app/` page) hold no business
  logic — they call importable modules so those can be substituted in tests.
- RLS/`is_admin()` is the actual authorization boundary for every write, both server-side (secret key,
  `scripts/`) and client-side (anon key, `admin-portal/`).
