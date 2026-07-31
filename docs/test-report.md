# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-13 fix cycle 1 retest — BUG-010/BUG-011 (NFR8) — 2026-07-31

**Scope.** Re-test of `docs/design/increment-plan.md`'s INC-13 (9 ACs) after dev's fix-cycle-1 commits
`3d1cdb3` (fix) + `e515093` (handoff) on `inc-13-admin-portal-ui-modernization`, per dev's account in
`docs/handoff.md`'s "INC-13 fix cycle 1" entry. Supersedes the prior INC-13 run (2026-07-31, FAIL, both
bugs below filed) — see `docs/archive/test-report-archive.md` for that entry.

**Method.** Dev's own fix-verification used a static HTML harness (real compiled CSS, hand-copied markup
shape) rather than a live-mocked Playwright render of the actual React app, and explicitly flagged this
gap and asked qa to re-run the higher-fidelity method. Repeated the same real-browser method as the
original INC-13 pass: `next build && next start` (fresh server process — the port had a stale server left
over from an earlier session serving pre-fix code; killed it and confirmed the new process's `cwd`/build
before testing, to avoid silently re-validating against stale code) on port 4173, Playwright + the
pre-installed Chromium (`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) driving the actual compiled
app, with every Supabase network call (`auth/v1/*`, `rest/v1/*`, `rest/v1/rpc/*`) mocked at the network
layer. Auth: seeded the `sb-ikghqdtlbwifwnooytmm-auth-token` cookie with the exact `@supabase/ssr`
base64url+chunking codec (verified by driving the real installed `@supabase/ssr` chunker/base64url
modules directly, not a guessed format), so `AuthGuard`'s `checkAuthorization()` resolves a real
authenticated/admin session with zero network round-trip needed for session bootstrap — the same
higher-fidelity approach the original INC-13 pass used, now re-run against the fix's own diff. 49
harness assertions across BUG-010/BUG-011 verification, full AC1–AC4/AC7(b)(c)/AC8 regression, functional
sort testing, and CRUD/validation spot checks; scripts/screenshots are session-scratchpad only, not
committed (matches this project's LLM/browser-test fixture posture — this is a deterministic-shell
UI/wiring check, no generated-text property assertions needed).

### 1. BUG-010 retest — watchlist/holdings tablet card styling

Computed styles measured directly (not read from source) at 768px:
- `.crud-table-wrap` (watchlist): `background-color` non-transparent (`rgb(255, 255, 255)`), `box-shadow`
  a real shadow (not `none`), `border-radius` non-zero (`8px`, matches `--radius-md`). **PASS** — was
  `rgba(0, 0, 0, 0)` / `none` / `0px` before the fix.
- `.crud-table-wrap` (holdings): same non-transparent background confirmed. **PASS.**
- Confirmed no phone/desktop regression: same computed-style checks were exercised as part of AC2 (375px,
  row-level card styling on `.crud-table tbody tr` still present) and AC4 (1280px, 4-column grid still
  present) below — both still green.

**BUG-010: RESOLVED.**

### 2. BUG-011 retest — track-record cards at all three widths

At 375px/768px/1280px: `document.querySelectorAll("table")` on `/track-record` returns **0** at every
width (previously always 1 — a real `<table class="log-table">`); `.tr-card` count is **> 0** at every
width; `.tr-cards`'s computed `grid-template-columns` resolves to **1 column at 375px, 2 at 768px, 3 at
1280px** — matching AC7(a)/`docs/ux-spec.md` §7.3.2's 1/2/3-tier density requirement exactly. No
page-level horizontal scroll at any width (AC1 held simultaneously).

**Functional sort check (not just visual):**
- Default load (timestamp descending): first rendered card is the newest row (`AAPL`, 2026-07-30).
- Selecting "Ticker" via the new `.sort-controls select` (`changeSortColumn`) changes the row order
  (first card is no longer `AAPL`) and lands on `TD.TO` first — confirming `changeSortColumn`'s
  documented reset-to-descending semantics hold through the real `.order()`-driven `loadRows()` query
  against the new control surface.
- Clicking the direction-toggle button (`toggleSortDirection`) reverses the order again (`AAPL` first,
  ascending ticker) — confirms the direction flip is wired to a real re-fetch, not a client-side no-op.

**BUG-011: RESOLVED.**

### 3. Full regression — AC1–AC4, AC7(b)/(c), AC8 (no regression from the fix)

All re-confirmed via the same real-browser pass, not assumed from dev's diff-touches-nothing-else claim:
- **AC1** (no page-level horizontal scroll): held at all widths on track-record and watchlist (spot-checked
  alongside the BUG-010/BUG-011 assertions above).
- **AC2** (watchlist stacked cards @375px): `<tr>` computed `display: block`, `data-label` present on
  cells. **PASS.**
- **AC3** (nav + kill-switch reachable via collapsed control @375px): `.nav-toggle-btn` exists; kill-switch
  toggle has a non-zero bounding box independent of the nav toggle. **PASS.**
- **AC4** (1280px 4-col desktop grid): watchlist `tbody` computed `display: grid` resolving to 4 columns.
  **PASS.**
- **AC7(b)/(c)** (tunables always-visible compact cards): all 10 `.tun-card`s present; all 10 raw
  `SNAKE_CASE` keys still rendered; friendly heading text differs from the raw key. **PASS.**
- **AC8** (sliding toggle, RPC round-trip): `.killswitch .pill` count is 0; clicking `.killswitch .toggle`
  fires `rpc/set_kill_switch` with `{p_paused: true, p_source: "admin-portal"}` (mocked), and the toggle's
  class flips to `.paused` on the (mocked) success response. **PASS** — same residual as the original
  pass: the persisted `kill_switch_audit` row itself needs live Supabase, unreachable from this sandbox;
  AC5's structural grep (below) confirms the RPC call site is unchanged.
- **AC9** (best-effort accessibility, non-blocking): keyboard-Tab reaches every interactive control
  (nav toggle, kill-switch toggle, nav links, form inputs/selects, Save) in DOM order at all three widths,
  no dead ends observed; a quick contrast spot-check (`h1` text `rgb(31,36,48)` on body background
  `rgb(244,245,247)`) is comfortably high-contrast. Recorded per NFR8's "not a pass/fail gate" framing —
  unaffected by this fix cycle (outside its file scope) and unchanged from before.

### 4. Structural "no functional regression" enforcement (AC5)

`git diff --name-only main..inc-13-admin-portal-ui-modernization -- admin-portal/` is still not a
meaningful comparison (`main` contains no `admin-portal/` directory at all — confirmed again via
`git ls-tree -d main -- admin-portal`, empty), same environment note as the original INC-13 run. Re-ran
against the branch's actual merge-base (`claude/admin-portal-ui-modernize-hhzgu5`), covering the full
branch diff including this fix cycle: `git diff --name-only` shows exactly the 10 allow-listed files
(`globals.css`, `watchlist/page.tsx`, `holdings/page.tsx`, `track-record/page.tsx`, `tunables/page.tsx`,
`layout.tsx`, `login/page.tsx`, `AuthGuard.tsx`, `KillSwitchToggle.tsx`, `NavToggle.tsx` — no `sql/`,
`scripts/`, `lib/*.ts`, or `tests/` file). The forbidden-call grep (`supabase\.|validateHoldingsRow|
validateTunableValue|is_admin|set_kill_switch|\.rpc\(|createClient`), run with zero diff context
(`git diff -U0`) to avoid false positives from unrelated unchanged context lines, returns **exactly one
match** — the same prose doc-comment in `AuthGuard.tsx` qa's original pass already found
(`// Purely cosmetic (avatar-chip initials) — never used for authorization, which is is_admin()/RLS.`).
**AC5: PASS**, clean across the full branch, not just this fix commit.

### 5. Existing automated suite

- `node --experimental-strip-types --test tests/admin_portal/*.test.ts`: **82 passed, 0 failed** — zero
  assertion changes (matches dev's claim).
- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short`: **286 passed, 1 failed** —
  `test_ingest.py::test_get_price_only_matches_get_market_data_price_fields_for_same_history`, the same
  pre-existing/unrelated date-sensitive failure flagged in the original INC-13 run (outside INC-13's file
  allow-list, reproduces identically on the pre-INC-13 commit). Not an INC-13 regression.
- `cd admin-portal && npm run build`: compiles cleanly, all 8 routes present, TypeScript check passes.
- `cd admin-portal && npm run lint`: zero errors/warnings.

### 6. CRUD/validation regression spot check (fix cycle's markup change didn't collaterally break anything)

Re-ran at 375px/768px/1280px: watchlist Edit→Save fires a `PATCH` with the edited payload and the row
re-renders correctly after the sort-control/table-wrap CSS changes; watchlist Delete fires a `DELETE` and
the row disappears; tunables rejects a non-numeric value for `DISCOVERY_GAINER_PCT` before any write
(`validateTunableValue`'s `must be numeric` error shown, zero `PATCH` request), then accepts a valid value
and fires the `PATCH`. All 15 checks (3 widths × 5 assertions) **pass** — no wiring regression from
BUG-010/BUG-011's fix.

### Verdict

**PASS — 0 bugs open for INC-13.** BUG-010 and BUG-011 both independently confirmed RESOLVED via computed
styles/DOM structure measured on the real running app (not dev's static harness, not source-reading).
Full regression clean: AC1–AC5, AC7(a)/(b)/(c), AC8, AC9 all hold; existing suite 82/0 (TypeScript) + 286/1
(Python, 1 pre-existing/unrelated); structural grep clean across the full branch diff; CRUD/validation
wiring unaffected at all three widths. **This is a full PASS with zero open INC-13 bugs — ready for
reviewer.**

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — INC-13 touches
only `admin-portal/`, nowhere near `ai_judge.py`. Full detail: `docs/archive/test-report-archive.md`'s
INC-9 BUG-006 fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
