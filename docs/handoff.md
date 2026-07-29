# Handoff — INC-6: Admin portal tunables editor (FR30)

## Post-handoff fixes

Three fixes landed after this increment's original build (commit `b2934c1`), all already committed:

- **BUG-003** (commit `799cd35`) — `run_discovery.py`'s zero-candidates/zero-screen-errors early-return
  branch didn't consult `config.TUNABLES_DEGRADED` before writing the heartbeat status. Fixed to OR it
  in, per AC14's "all three entry points" wording — full writeup in the section below.
- **REV-086** (commit `17fa5fd`) — `tunables` table was missing the same RLS-does-not-govern-TRUNCATE
  REVOKE that INC-5's `admin_allowlist` got for REV-081; `anon`/`authenticated` otherwise retained
  Supabase's default TRUNCATE grant. Added `revoke insert, delete, truncate on public.tunables from
  public, anon, authenticated;` (deliberately omitting `update`/`select`, since `admin_write_tunables`
  legitimately grants both to `authenticated` — that's FR30's whole point).
- **RLS policy syntax fix** (commit `e46abf8`) — the orchestrator's live migration apply caught a real
  Postgres syntax error: `admin_write_tunables`'s original policy used `for select, update to
  authenticated`, but `CREATE POLICY ... FOR <command>` accepts exactly one command, never a comma
  list — invalid SQL, never caught locally since no dev/qa/reviewer had live Supabase execution access
  during the original build. Split into two valid policies: `admin_read_tunables` (`for select`) and
  `admin_write_tunables` (`for update`, with check) — same effective authorization as before (REV-044's
  select+update-only, no insert/delete), valid syntax. "Files changed" below and inline SQL comments
  reflect this current two-policy shape.

## BUG-003 fix (post-QA-pass follow-up)

Fixed per qa's finding (`docs/test-report.md` BUG-003) and AC14's literal "all three entry points"
wording: `scripts/run_discovery.py`'s zero-candidates/zero-screen-errors early-return branch (line 59)
now ORs in `config.TUNABLES_DEGRADED` before writing the heartbeat status, mirroring the later computed
`status =` line (line 115) — one-line change (`if screens_errored:` -> `if screens_errored or
config.TUNABLES_DEGRADED:`), print-message text left unchanged (matches the later block's own minimal,
not-fully-cause-descriptive message pattern).

Also updated (regressions this fix surfaced, not scope creep):
- `tests/test_tunables.py::test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded`
  — qa's own gap-locking test, inverted to assert `"partial"` per this task's explicit instruction.
- `tests/test_run_orchestration.py::test_quiet_day_all_screens_ok_reports_ok` — this pre-existing test
  asserted `"ok"` without neutralizing `config.TUNABLES_DEGRADED`, which is `True` by default under
  `tests/conftest.py`'s `SKIP_TUNABLES_FETCH=true`. Once the branch started consulting
  `TUNABLES_DEGRADED`, this test broke as a direct, necessary consequence of the correct production fix
  (not touched otherwise) — neutralized with `monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)`,
  the exact established pattern already used in this same file's
  `test_heartbeat_is_ok_when_every_ticker_processes_cleanly`/`test_heartbeat_is_partial_when_tunables_are_degraded`
  pair. `test_zero_candidates_with_screen_errors_reports_partial_not_ok` and
  `test_zero_candidates_with_all_screens_errored_is_still_partial` needed no change (already `partial`
  via `screens_errored`, message text unchanged).

Full suite: `python3 -m pytest -q --tb=short` -> **201 passed, 0 failed** (no change in count; the 2
transiently-broken tests above are fixed forward, not net-new). `docs/test-report.md`'s BUG-003 entries
(the detailed writeup and the "Open bugs" section) marked FIXED — no other text in that file touched.


Branch: `claude/admin-portal-evaluation-txaehj` (shared feature branch for this change request, per
project convention — not a per-increment branch). Depends on INC-5's `admin_allowlist`/`is_admin()`
(`sql/admin_portal_rls.sql`), already reviewer-CLEAR. INC-5's own handoff history (foundation, live
grant/policy audit, build-inlining fix) is preserved in git history (`git log -p -- docs/handoff.md`),
not restated here.

**Design:** `docs/design/admin-portal-tunables.md` §16.4 (schema/RLS/seed/portal UI),
`docs/design/tunables-fallback.md` §16.4 (`scripts/config.py`'s fetch/cache chain), and
`docs/design/tunables-workflow-writeback.md` §16.4 (workflow write-back, REV-040 mitigations).
Acceptance criteria: `docs/design/increment-plan.md` lines 189-282 (16 ACs).

## Flag for tech-lead: one design premise was stale, corrected during build

`tunables-fallback.md` (line 36-38) and `increment-plan.md`'s AC16 both assert that
`.github/workflows/hourly-watchlist.yml` **has no `permissions:` block at all today**. That premise
was true when those design sections were drafted (2026-07-27/28) but was overtaken by a same-day
commit (`920876f`, "Pass 11 audit findings", REV-050) that added a **top-level**
`permissions: { contents: read }` block to that same file — a race between two concurrent Pass-11
fix streams, confirmed via `git log -p`. By the time INC-6 build started, the file already had that
top-level block.

**Resolution applied (not left to silently diverge from the design):** I removed the stale top-level
`contents: read` block and replaced it with the job-scoped `contents: write` block INC-6's design
calls for (REV-040b) — functionally a strict tightening (no job in this file inherits write access by
default any more), and it's what AC16 actually checks for ("no top-level `permissions:` block exists
in the file"). If tech-lead wants a different resolution (e.g. re-adding a top-level `contents: read`
alongside the job-scoped `write`), that's a one-line change — the diff is isolated to the
`permissions:`/`concurrency:` header block plus the new commit step.

## Files changed

- **New `sql/admin_portal_tunables.sql`** — `tunables` table with the 10-key CHECK-constraint registry,
  `_stamp_tunable_update()` trigger (server-stamps `updated_at`/`updated_by`, never client-supplied),
  two RLS policies — `admin_read_tunables` (`for select to authenticated`) and `admin_write_tunables`
  (`for update to authenticated`, with check) — **not** `for all` (REV-044); split into two policies
  because Postgres' `CREATE POLICY ... FOR <command>` accepts exactly one command, never a comma list
  (post-handoff fix, see "Post-handoff fixes" below), and the 10-row seed migration. **Not applied to
  the live Supabase project** (no MCP/Supabase tool
  access this session, same constraint as INC-5) — orchestrator applies this after handoff, same
  process as `sql/admin_portal_rls.sql`. `ALERTS_ENABLED` is explicitly seeded `"true"` (not
  `config.py`'s bare `"false"` literal) — see the file's own comment for why (Decision #27's
  no-behavior-change-at-cutover requirement; today's actual live default is `true` via the
  `workflow_dispatch` input).
- **New `tunables_cache.json`** at the **repo root** (not `config/` — REV-046) — 10 key/value pairs,
  byte-for-byte identical to the SQL seed's `value` column, including `ALERTS_ENABLED: "true"`. Diffed
  directly against the SQL file's `insert` values (not eyeballed) — see "AC2" below.
- **New `admin-portal/app/(app)/tunables/page.tsx`** — the tunables editor screen, inside the same
  `(app)` route group as `watchlist`/`holdings` so it automatically gets `AuthGuard`'s session/allowlist
  check via `admin-portal/app/(app)/layout.tsx` (no new guard code written — reused as-is). Read/render/
  update against `public.tunables` via the same browser-side Supabase client
  (`lib/supabase-client.ts`) and RLS pattern as watchlist/holdings. No add/delete UI and no client-side
  key list — the RLS policy only grants `select, update` (REV-044), and `description`/`example` are DB
  columns now, not a static portal-side metadata array (per the design's explicit note). `updated_at`/
  `updated_by` are rendered read-only; the page only ever sends `{ value }` in its update call — the
  trigger stamps the rest server-side.
- **`admin-portal/components/AuthGuard.tsx`** — added a `Tunables` nav link (alongside Watchlist/
  Holdings) and updated its docstring. The design brief said "reuse `AuthGuard.tsx` as-is"; I read that
  as reusing the wrapping/auth mechanism unmodified (still true — zero changes to the auth/redirect
  logic), not that a real feature should ship with no way to navigate to it. INC-5's handoff explicitly
  flagged "no stub pages or nav links exist for [tunables]" as an INC-5 known limitation for INC-6 to
  close.
- **`admin-portal/lib/validation.ts`** — added `validateTunableValue()` (blank-value check only; every
  other rule — which keys exist, cast validity — is enforced server-side by the CHECK constraint and
  `scripts/config.py`'s own cast, intentionally not duplicated client-side).
- **`scripts/config.py`** — added the two-tier fallback chain per `tunables-fallback.md`
  (`TUNABLES_FETCH_TIMEOUT_MS`, `SKIP_TUNABLES_FETCH`, `_fetch_tunables()`, `_load_tunables_cache()`,
  `_tunable()`, `TUNABLES_DEGRADED`, `write_tunables_cache_if_fetched()`), replacing the bare
  `os.environ.get(...)` reads for exactly the 10 curated keys (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`,
  `ALERTS_ENABLED` → `ALERTS_ENABLED_TABLE` + the `_alerts_input` AND-gate, `DISCOVERY_GAINER_PCT`,
  `DISCOVERY_LOSER_PCT`, `DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`,
  `DISCOVERY_MIN_MARKET_CAP_INR`, `DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`). Every
  other tunable in the file (~18 non-curated keys, e.g. `AI_PROVIDER`, `GEMINI_TIMEOUT_MS`,
  `YF_PACING_SECONDS`, `DISCOVERY_MIN_PRICE`, `DISCOVERY_52W_PROXIMITY`, ...) is byte-for-byte untouched
  — confirmed via `git diff -- scripts/config.py`. Also added a `[config] tunables resolved
  (degraded=...)` startup log line printing all 10 effective values — needed for AC5's "observing the
  new value in its `[config]` startup log line" (the design's own code sketch only had per-fallback log
  lines, not a happy-path summary; added this to actually satisfy AC5's text, see verification below).
  `create_client`/`ClientOptions` import added; cross-checked `postgrest_client_timeout` against the
  installed `supabase==2.31.0`'s real `ClientOptions.__init__` signature (accepts `int | float | httpx.Timeout`,
  seconds) before trusting the design's code block verbatim.
- **`scripts/run_hourly.py`** — one line added early in `main()`, before the market gate:
  `config.write_tunables_cache_if_fetched()`. Also the REV-045 heartbeat-status change:
  `status = "partial" if (degraded or config.TUNABLES_DEGRADED) else "ok"`.
- **`scripts/run_discovery.py`, `scripts/publish_prices.py`** — REV-045 heartbeat-status change only,
  at each file's single existing computed-`status` line. Neither calls
  `write_tunables_cache_if_fetched` (`grep -c` = 0 in both files, confirmed below) — they remain
  read-only tunables-cache consumers, Decision #28/#29. Note: `run_discovery.py`'s early-return
  "zero candidates" branch (two hardcoded `"partial"`/`"ok"` literals, not a computed `status =` line)
  was **not** touched — the brief and design both describe changing "the existing status-computation
  line" (singular), which is the later computed line at the bottom of `main()`. Flagged in Known
  Limitations below.
- **`.github/workflows/hourly-watchlist.yml`** — `concurrency.group` renamed `hourly-watchlist` ->
  `repo-commit` (REV-040a); top-level `permissions: contents: read` replaced with a job-scoped
  `permissions: contents: write` under `jobs.watchlist` (REV-040b, see the stale-premise flag above);
  new "Commit tunables cache if changed" step with the bounded 3-attempt push retry, added after "Run
  hourly watchlist check", per `tunables-workflow-writeback.md` lines 92-117.
- **`.github/workflows/publish-prices.yml`** — exactly one line changed: `concurrency.group`
  `publish-prices` -> `repo-commit`. Nothing else.
- **`.github/workflows/daily-discovery.yml`** — zero changes (`git diff` is empty, confirmed below).
- **`tests/conftest.py`** — added `os.environ.setdefault("SKIP_TUNABLES_FETCH", "true")` alongside the
  existing fake-secrets block, per the design's explicitly-flagged INC-6 follow-up.

## How to run locally

```
python3 -m pytest -q --tb=short                          # Python suite (repo root or scripts/ on path)
cd admin-portal && npm run build && npm run lint          # portal build + lint
node --experimental-strip-types --test tests/admin_portal/*.test.ts   # portal test suite
```

A curated tunable's effective value is visible in any script's stdout at import time:
`[config] tunables resolved (degraded=...): GEMINI_MODEL=... ...`.

## Acceptance criteria status

**Self-verified now (scripted/local, no live Supabase needed):**

- **AC2** — PASS. `tunables_cache.json`'s 10 pairs diffed directly against `sql/admin_portal_tunables.sql`'s
  `insert` values — identical, including `ALERTS_ENABLED: "true"` in both.
- **AC5** (import-time pickup, not hot-reloaded) — PASS, verified with a scripted fake `supabase.create_client`
  that returns an edited `GEMINI_MODEL` row: a fresh process import resolves `config.GEMINI_MODEL` to the
  edited value and prints it in the new `[config] tunables resolved ...` startup line;
  `config.TUNABLES_DEGRADED` is `False` when tier 1 fully succeeds.
- **AC8** (read-only workflows never write) — PASS (static). `grep -c write_tunables_cache_if_fetched
  scripts/run_discovery.py scripts/publish_prices.py` = 0/0; `scripts/run_hourly.py` has exactly one real
  call site. The fallback-to-cache behavior itself (part a of AC8) is exercised by AC9's/AC13's scripted
  checks below, which cover the same `_fetch_tunables`-failure code path these two entry points share via
  `config.py`.
- **AC9** (double-failure fails loud) — PASS, verified with a real subprocess: `tunables_cache.json`
  temporarily moved aside + `SUPABASE_URL` set to an unparseable value (fails fast, no network hang) ->
  `import config` raises `SystemExit` naming `GEMINI_MODEL` (the first curated key resolved) and exits
  non-zero (`EXIT=1`). Cache file restored immediately after (untracked-diff-clean, confirmed via
  `git status`).
- **AC12** (REV-036, validate + never-shrink) — PASS, verified with a scratch cache file (not the real
  repo file): a simulated 9/10-key fetch that also includes one value which fails its cast
  (`DISCOVERY_LOSER_PCT = 'not-a-number'`) leaves the untouched 10th key's cached value intact, updates
  only the successfully-fetched-and-cast key, and drops the bad-cast value rather than persisting it.
  Separately verified the tier-1-cast-failure fail-loud path directly: a value Supabase "returned" that
  fails its cast (`DISCOVERY_GAINER_PCT = '5%'`) raises `SystemExit` naming the key and does **not** fall
  through to the cache tier.
- **AC13** (REV-041, timeout tunable + offline seam) — PASS. `TUNABLES_FETCH_TIMEOUT_MS` reads from the
  environment (default `5000`) and is passed into `ClientOptions(postgrest_client_timeout=...)`.
  `SKIP_TUNABLES_FETCH=true` verified to make **zero** network calls at import time (monkeypatched
  `socket.socket.connect` to raise if invoked — no exception raised, confirming zero calls) and every
  curated key resolves from `tunables_cache.json`.
- **AC14** (REV-045, degraded signal reaches heartbeat) — PASS by direct consequence: with the test
  suite's now-default `SKIP_TUNABLES_FETCH=true`, `config.TUNABLES_DEGRADED` is `True` on every import
  (every curated key legitimately falls to tier 2), and the pre-existing
  `test_heartbeat_is_ok_when_every_ticker_processes_cleanly` test now asserts `status == "partial"`
  is required, not `"ok"` — see "Expected test-suite impact" below; this failure **is** the proof AC14's
  wiring works, not a bug.
- **AC10 (partial)** — the AND-gate direction is unit-provable from the formula
  (`ALERTS_ENABLED = _alerts_input and ALERTS_ENABLED_TABLE`) and is exercised by the pre-existing,
  still-passing `test_alerts_enabled_is_off_by_default`/`test_alerts_enabled_true_override` tests (both
  pass unchanged because the seeded/cached table value is `"true"`, so the env-var input alone still
  determines the outcome in both of those specific cases — consistent with, not just coincidentally
  matching, the AND-gate). I did **not** independently verify the "table=`false` + scheduled run
  (`inputs` default `true`)" half of AC10, since that requires either live Supabase or a qa-authored
  `_fetch_tunables` mock returning `ALERTS_ENABLED="false"` — flagged below as deferred.
- **AC11** — PASS (static diff review). `git diff` confirms: `daily-discovery.yml` is byte-identical
  (empty diff); `publish-prices.yml`'s diff is exactly the one-line `concurrency.group` rename;
  `hourly-watchlist.yml`'s diff is the `concurrency.group` rename + the `permissions:` header change
  (see the stale-premise flag above for why this isn't a pure addition) + the one new step.

**Static-only (file/shape checks, not a live dispatch):**

- **AC1, AC3, AC4** — SQL/RLS shape matches the design's exact block (table, CHECK, trigger, policy
  scoped to `select, update`, seed values). **Cannot verify the live behavior** (actual RLS rejection via
  `curl`, actual `updated_by` stamping on a real authenticated write) without the migration applied to
  the live project — same constraint as INC-5's AC4/AC5.
- **AC16** — the job-scoped `permissions: contents: write` block and the absence of a top-level
  `permissions:` block are both confirmed via direct file read / `yaml.safe_load` structural check.

**Deferred — need live Supabase / a real workflow dispatch (I don't have Supabase MCP or GitHub Actions
dispatch access this session):**

- **AC1, AC3 (live), AC4 (live)** — apply `sql/admin_portal_tunables.sql`, then: `curl` with the anon key
  and no session against `tunables` (expect a permissions error); a signed-in admin `insert`/`delete`
  attempt (expect rejection, RLS is `select, update` only); a CHECK-constraint violation on a bogus
  `key`; a portal edit round-tripped through `select * from tunables` to confirm `updated_at`/
  `updated_by` really are server-stamped (not just that the trigger *reads* right locally).
- **AC6** — cache write-back, unchanged case: needs a real `hourly-watchlist.yml` dispatch against a
  live, unmodified `tunables` table; confirm zero new commits.
- **AC7** — cache write-back, changed case: edit one row via the portal (needs the migration applied +
  a deployed portal), dispatch `hourly-watchlist.yml`, confirm exactly one `github-actions[bot]` commit
  touching only `tunables_cache.json`.
- **AC10 (the other half)** — table=`false` + scheduled (no-`inputs`) dispatch really does suppress a
  real push; table=`true` + a manual `alerts_enabled=false` dry run also suppresses. Needs either a live
  table or a qa-authored `config._fetch_tunables` mock (the seam this design built specifically so this
  doesn't need live Supabase — qa can do this one without a real dispatch).
- **AC15** — two near-simultaneous `workflow_dispatch` calls against `hourly-watchlist.yml` and
  `publish-prices.yml`, confirmed via the Actions run queue to serialize rather than run concurrently;
  and confirm two overlapping `hourly-watchlist.yml` dispatches still serialize (unchanged regression).
- **AC16 (the retry-firing half)** — simulating a real lost race (push a throwaway commit between the
  step's `pull --rebase` and `push`, or stub `git push` to fail its first attempts) and confirming the
  retry log line + eventual success, or a clean non-zero exit after 3 failed attempts. The static shape
  (job-scoped permissions, retry loop present, `::error::` message) is confirmed; the *runtime* behavior
  needs a real workflow run.

## Expected test-suite impact — 3 pre-existing tests now fail, by design, not a regression I introduced

`python3 -m pytest -q --tb=short` -> **168 passed, 3 failed** (baseline before this increment: 171
passed, 0 failed). All three failures are the direct, intended consequence of Decision #27 (these 10
keys move OFF env-var control) and REV-045 (tier-2 resolution must be heartbeat-visible) — not bugs in
this increment's code:

1. `tests/test_config.py::test_nse_model_pair_inherits_watchlist_pair_by_default` — sets `GEMINI_MODEL`
   via env var and expects it to propagate. `GEMINI_MODEL` is now a curated tunable sourced only from
   the table/cache chain (that's the entire point of FR30/Decision #27) — an env var no longer has any
   effect on it. Needs qa to rewrite this test against `config._fetch_tunables` mocking instead of an
   env var, per the seam AC13 already calls out.
2. `tests/test_config.py::test_discovery_min_market_cap_override_propagates` — same root cause,
   `DISCOVERY_MIN_MARKET_CAP` is also curated.
3. `tests/test_run_orchestration.py::test_heartbeat_is_ok_when_every_ticker_processes_cleanly` — asserts
   `status == "ok"` for an all-clean run. With `tests/conftest.py`'s new `SKIP_TUNABLES_FETCH=true`
   default (this increment's own required addition, `tunables-workflow-writeback.md`'s explicit
   follow-up), every curated key legitimately resolves from tier 2 in the test environment, so
   `config.TUNABLES_DEGRADED` is `True` for the whole suite and the heartbeat correctly reports
   `"partial"` — this is AC14 working as designed, not a bug. Needs qa to either monkeypatch
   `config.TUNABLES_DEGRADED = False` for this specific test's clean-run assertion, or restructure it to
   assert on `degraded` alone with `TUNABLES_DEGRADED` neutralized.

I did not modify these three tests myself — `tests/` is qa's owned artifact per `CLAUDE.md`, and the
brief's file list for this increment named only `tests/conftest.py`.

## Known limitations

- ~~`run_discovery.py`'s zero-candidates early-return branch ... does not consult
  `config.TUNABLES_DEGRADED`~~ — **FIXED (BUG-003).** Per qa's finding and AC14's literal "all three
  entry points" wording, the early-return branch (`run_discovery.py:59`) now also ORs in
  `config.TUNABLES_DEGRADED` before writing the heartbeat status, same pattern as the later computed
  `status =` line. `tests/test_tunables.py::test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded`
  updated to assert `"partial"`.
- AC10's "table=`false`" half and AC6/AC7 (cache write-back) and AC1/AC3/AC4 (live RLS) are unverified
  without live Supabase/GitHub Actions access, as detailed above.
- No admin-portal-side test yet exercises the new `/tunables` page's read/update flow (qa's
  `tests/admin_portal/` suite currently only covers watchlist/holdings-era files structurally — the
  `static_source_checks.test.ts`/`build_bundle.test.ts` suites still pass unmodified since they check
  portal-wide invariants, not per-page behavior).
- `sql/admin_portal_tunables.sql` is not applied to the live project — orchestrator applies it, same as
  INC-5's `sql/admin_portal_rls.sql`.
