# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-15 — Tickers merge + nav defect fix + horizontal-scroll tier (FR36/FR37/FR38, amended NFR8) — 2026-08-01

**Scope.** Branch `inc-15-tickers-merge-nav-fix` (`main`@`98947f9`, commit `40eccb2`). Files touched (matches
the allow-list in `docs/design/increment-plan.md`'s INC-15 section exactly, `git diff --name-status main`):
`admin-portal/components/NavToggle.tsx`, `admin-portal/components/AuthGuard.tsx`,
`admin-portal/app/globals.css`, `admin-portal/app/layout.tsx`, new `admin-portal/app/(app)/tickers/page.tsx`,
new `admin-portal/components/TickerEditModal.tsx`, deleted `admin-portal/app/(app)/watchlist/page.tsx` +
`admin-portal/app/(app)/holdings/page.tsx`, new `sql/tickers_screen_rpc.sql`.

### 1. Structural no-regression check — reinterpreted per dev's flag, not applied literally

Dev correctly flagged that a literal "zero matches beyond 3 named exceptions" reading of the grep rule is
impossible for this design (the merged screen necessarily contains ordinary `watchlist`/`holdings` CRUD).
Verified the *substantive* bar instead: every `supabase.*`/`createClient`/`.rpc(` call site in the diff,
traced individually against `git show main:admin-portal/app/(app)/watchlist/page.tsx` and
`.../holdings/page.tsx` (the deleted originals):

- **`tickers/page.tsx` reads** — `supabase.from("watchlist").select("*").order("ticker")` (identical to old
  `watchlist/page.tsx`'s `loadRows()`), `supabase.from("holdings").select("*")` (identical table/columns to
  old `holdings/page.tsx`'s `loadAll()`, RLS-covered the same way — `.order("ticker")` dropped since the
  merge no longer needs a second independently-sorted list, a presentational simplification, not a new
  read), and `supabase.from("latest_call_per_ticker").select(...)` — a genuinely new *read* of an
  **existing** view (same one the track-record page already reads), consistent with §16.11.3's explicit
  "three parallel reads, no new policy" design.
- **`tickers/page.tsx` write** — `supabase.from("watchlist").insert([{ticker, market, type, status:
  "watch-only"}])` for "+ Add ticker": same shape as old `watchlist/page.tsx`'s `handleAdd`, narrowed to
  always send `status: "watch-only"` (matches AC12's explicit "not a new create-as-held path" requirement,
  not a functional expansion).
- **`TickerEditModal.tsx` writes** — `supabase.from("watchlist").update({market, type})` (subset of old
  `watchlist/page.tsx`'s `handleUpdate`, which also included `status` — status now exclusively routes
  through the new RPC, confirmed no code path lets a plain field-edit Save also silently flip `status` via
  the direct call: `doSave()` only ever sends `market`/`type` to `watchlist`, `status` always goes through
  `set_ticker_holding_status` when changed); `supabase.from("holdings").update({shares, cost_basis})` (same
  shape as old `holdings/page.tsx`'s `handleUpdate`, reached only when `status` is unchanged and already
  `held` — confirmed by reading `doSave()`'s `else if (form.status === "held")` branch, which is mutually
  exclusive with the `statusChanged` branch above it); `supabase.rpc("set_ticker_holding_status", ...)` (×2
  call sites: the watch-only→held Save path and the held→watch-only confirm path) and
  `supabase.rpc("delete_ticker", ...)` (×1, the Delete button) — exactly the two named new RPCs, used only
  for status transitions/deletion, never as a shortcut for a plain field edit (confirmed: no other call site
  routes a non-status-changing edit through either RPC).
- **Old `holdings/page.tsx`'s direct `insert()`/`delete()` calls have no equivalent direct call in the new
  code** — correctly absorbed into `set_ticker_holding_status`'s `insert ... on conflict` and
  `delete_ticker`'s `delete from holdings`, respectively. This is the intended consolidation (§16.11.5's own
  rationale: two independent client calls can't guarantee atomicity against the `holdings.ticker` FK with no
  cascade) — not a functional expansion, and not a change dev could have avoided while satisfying FR37.
- **`is_admin()`** — appears only inside `sql/tickers_screen_rpc.sql`'s two new functions (confirmed via
  `git diff main -- admin-portal/ sql/ | grep -n "is_admin"` — zero hits outside that file).
- **`set_kill_switch`/`validateTunableValue`/kill-switch or tunables validation** — zero live-code matches
  anywhere in the diff; `set_kill_switch` appears only in `sql/tickers_screen_rpc.sql`'s doc-comment prose
  citing it as the precedent pattern, not a call. `git diff --name-only main -- admin-portal/lib/
  admin-portal/app/\(app\)/tunables admin-portal/app/\(app\)/track-record` returns empty — confirmed
  untouched.
- **`validateHoldingsRow`/`validateWatchlistRow`** — both carried over unchanged from the pre-merge forms
  (same functions, same rules, imported into `TickerEditModal.tsx`/`tickers/page.tsx` instead of the deleted
  files) — no new validation rule invented.

**Verdict: clean consolidation.** Every write in the diff is either (a) the same table/columns/RLS-gated
operation the deleted pre-merge pages already performed, relocated, or (b) one of the two named RPCs used
only for status transitions/deletion. No plain field edit is routed through an RPC; no RPC does anything
beyond what §16.11.5 specifies. Dev's own self-report reached the same conclusion — independently
re-traced call-site-by-call-site against the actual deleted file contents (not just dev's characterization)
and confirm it.

### 2. `tests/admin_portal/static_source_checks.test.ts`'s 3 known-broken tests — fixed (qa's territory)

The 3 failing assertions referenced the now-deleted `holdings/page.tsx` by literal path
(`HOLDINGS_PAGE` constant). Repointed at the post-merge files, preserving the exact behavioral guarantee
each was checking (not deleted, not rubber-stamped):
- "no currency `<select>`/`<input>` in the form" → now checks both `tickers/page.tsx` (add form) and
  `TickerEditModal.tsx` (edit form) for the same absence.
- "insert()/update() payloads never send `currency`" → now extracts `insert`/`update`/`rpc` call args from
  both `tickers/page.tsx` and `TickerEditModal.tsx` (the `rpc()` calls added to the checked method set since
  `set_ticker_holding_status`/`delete_ticker` are now where the old direct `holdings.insert`/`.delete` calls'
  responsibility moved to) and asserts none carry a `currency:` key.
- "displays a read-only derived currency, not an editable field" → repointed at `TickerEditModal.tsx`;
  the approved mockup's `.field .derived` chip mechanism is unchanged (`MARKET_CURRENCY`-looked-up value +
  `(from {market})`), but the old page's literal "Derived from market — not editable." hint sentence is
  genuinely absent from the approved mockup/new modal (not a regression — the mockup never included it) so
  the assertion was changed from matching that literal sentence to asserting the same underlying guarantee:
  a `className="derived"` span (never an `<input>`/`<select>`) showing the derived value.

Result: `node --experimental-strip-types --test tests/admin_portal/static_source_checks.test.ts` →
**14 passed, 0 failed** (was 11/14 before the fix).

### 3. Real-browser Playwright verification (independent, not a re-run of dev's script)

Real `next build && next start` (port 4173, `NEXT_PUBLIC_SUPABASE_URL`/`ANON_KEY` set to disposable marker
values so the mocked network layer's hostname match works and the build statically inlines them), Supabase
REST + RPC mocked at `context.route()` with an in-memory fixture store, a pre-seeded `@supabase/ssr`-shaped
auth cookie so `AuthGuard`'s `checkAuthorization()` resolves without a live project, pre-installed Chromium
(`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, no `playwright install` run), globally-installed
`playwright@1.56.1` driver.

- **Re-ran dev's own 54-assertion script independently, unmodified apart from the executable path** — **54
  passed, 0 failed** — corroborates AC1–AC12, AC7/AC8's exact write-timing/RPC-argument claims, and the "+
  Add ticker"/search-no-network behavior, all against the real build, not taken on trust.
- **Supplementary qa-authored script (31 additional independent checks)**, covering ground dev's own script
  didn't exercise:
  - FR38 (2 checks): `<title>` and `.app-header-brand` both read "Sentinel Portal".
  - AC14's regression half — tunables/track-record at 375/768/1280px (18 checks): correct nav mechanism per
    tier (burger <640px, `.nav-strip` ≥640px) on **every** authenticated route, not just `/tickers`; zero
    page-level horizontal scroll/clipping; kill-switch toggle still present; tunables' friendly-label
    rendering and track-record's verdict-pill rendering both still functioning (INC-13/14 regression
    checklist re-run, automated rather than dev's manual spot-check).
  - Login page unaffected (1 check).
  - Edge case — empty watchlist (2 checks): zero cards render without crashing, empty-state message shown.
  - Invalid-input case — negative shares + non-numeric price on a watch-only→held transition (2 checks):
    Save stays blocked, no RPC fires.
  - Sign-out button is functional, not just visible (2 checks): exactly one control in `.app-header-right`,
    clicking it actually navigates to `/login`.
  - 4 remaining checks distributed across the above groupings.
  All **31 passed, 0 failed**.
- **Exact-breakpoint boundary spot-check (not in either script above):** burger visible at 639px, hidden at
  640px — confirms §16.11.2's breakpoint is the literal pixel value, not "approximately 640."

**Total independent real-browser verification: 85/85 checks passed** (54 re-run + 31 new), across
375/768/1280px plus a 639/640px boundary pair.

### 4. Automated suites

- `python -m pytest -q --tb=short` → **287 passed, 0 failed.**
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` (all 6 files) → **82 passed, 0
  failed** (5 + 6 + 21 + 14 + 20 + 16 — includes the 14/14 from the fixed `static_source_checks.test.ts`
  above).

### 5. Regression checklist — auth, RLS, kill-switch, tunables

- **Auth:** `admin_guard.test.ts` (5/5) unaffected; login page loads and still offers only Google OAuth
  (confirmed live in the browser pass above, §3).
- **RLS:** `static_source_checks.test.ts`'s `admin_write_watchlist`/`admin_write_holdings`/`admin_allowlist`/
  `is_admin()` shape checks (3 tests) pass unchanged — `sql/admin_portal_rls.sql` itself is untouched by this
  diff (`git diff --name-only main -- sql/` shows only the new `tickers_screen_rpc.sql`).
  `sql/tickers_screen_rpc.sql`'s two new functions are correctly `is_admin()`-gated and `grant execute ... to
  authenticated` only (no anon grant), read directly from the file (§16.11.5's copied-verbatim SQL, matches
  `set_kill_switch`'s established shape).
- **Kill-switch:** zero drift — `kill_switch_static.test.ts` (21/21) unaffected;
  `KillSwitchToggle.tsx`/`kill_switch.sql`/`kill_switch_portal_grant.sql` untouched by this diff (not in
  `git diff --name-only`); browser pass confirms the toggle still renders in `.app-header-right` on every
  route.
- **Tunables:** zero drift — `tunables_static.test.ts` (20/20) unaffected; `tunables/page.tsx`,
  `lib/validation.ts`'s `validateTunableValue`, `sql/admin_portal_tunables.sql`,
  `sql/tunables_validate_trigger.sql` all untouched (not in `git diff --name-only`); browser pass confirms
  the tunables screen still renders/functions (friendly labels present) at all 3 widths.

### 6. `sql/tickers_screen_rpc.sql` — not applied live (same constraint as every prior `sql/*.sql` file)

No live Supabase/MCP credentials available in this session — the RPC contract is exercised only against the
mock fixture (§3), matching the exact function signatures/behavior in the file, not a real Postgres function.
Release must apply this file before the modal's watch-only↔held/delete actions work against real data (same
pattern every prior `sql/` file in this project has followed).

### Verdict — INC-15

**PASS.** 287/0 Python, 82/0 TypeScript (3 previously-known-broken tests fixed by qa, same suite now fully
green), 85/85 independent real-browser checks (54 re-run from dev's own script + 31 new qa-authored checks +
a breakpoint boundary spot-check) across 375/768/1280px, structural no-regression check reinterpreted
per dev's flag and independently traced call-site-by-call-site against the deleted originals (clean
consolidation confirmed, not rubber-stamped), zero drift on auth/RLS/kill-switch/tunables. Zero new bugs
filed.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — nothing in this
increment touched `ai_judge.py`. Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006
fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
