# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-13 — Admin portal responsive & visual modernization (NFR8) — 2026-07-31

**Scope.** `docs/design/increment-plan.md`'s INC-13 (9 ACs), `docs/design/admin-portal.md` §16.10,
`docs/ux-spec.md` §7.4 (Direction G) + §7.3 (density table) + §2.3 (tunables label mapping),
`docs/ux-mockups/direction-g-compact-toggle.html` (approved visual reference). Branch
`inc-13-admin-portal-ui-modernization` (commit `ea68f5b`), dev handoff `docs/handoff.md` (bottom entry).

**Environment note (affects both dev and qa identically):** this sandbox's egress policy blocks the real
Supabase project (`ikghqdtlbwifwnooytmm.supabase.co`, confirmed via direct `curl` — `CONNECT tunnel failed,
response 403` — same `connect_rejected`/`policy denial` class as the `cdn.playwright.dev` block dev hit).
No live Google OAuth / RLS / `kill_switch_audit` round-trip is reachable from this sandbox, full stop —
this is an environment limitation, not a code defect. Chromium itself, however, **is** pre-installed
(`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) and the globally-installed `playwright` npm package
launches it successfully, so unlike dev, qa **could** run a real-browser Playwright pass — the missing
piece was a live Supabase backend, not a browser. Worked around by running the admin portal for real
(`next build && next start`) and mocking every Supabase network call (auth cookie, `rest/v1/*`, `rpc/*`)
at the Playwright network layer, so the actual compiled app (not a static mockup, not a source-reading
exercise) renders and is measured/clicked for real. This closes dev's flagged gap for every
geometry/markup/interaction-wiring AC; it does not and cannot substitute for a genuine live OAuth+RLS+
audit-row round-trip, which still needs to run once real network access exists (same residual as INC-3/
INC-4's already-deferred live checks).

### 1. Existing automated suite

- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` (repo root): **82 passed, 0
  failed** — confirms dev's claim, zero assertion changes (diffed the test files themselves: untouched).
- `python3 -m pytest -q --tb=short`: **286 passed, 1 failed** —
  `test_ingest.py::test_get_price_only_matches_get_market_data_price_fields_for_same_history`
  (`assert 14.5 == None`). Confirmed pre-existing and unrelated to INC-13: reproduces identically on a
  throwaway worktree of `8124f833` (the commit INC-13 branched from, before any of dev's edits) and
  `scripts/ingest.py` is outside INC-13's file allow-list (`git diff --name-only claude/admin-portal-ui-
  modernize-hhzgu5..inc-13-admin-portal-ui-modernization -- scripts/` is empty). Not filed as an INC-13
  bug; flagging for whoever owns `scripts/ingest.py`'s date-sensitivity next.

### 2. Structural "no functional regression" enforcement (AC5)

`git diff --name-only main..inc-13-admin-portal-ui-modernization -- admin-portal/` is **not** a meaningful
comparison in this repo (`main` doesn't contain `admin-portal/` at all yet — confirmed via `git ls-tree -d
main -- admin-portal`, empty), exactly as dev's handoff flags. Re-ran against dev's actual branch point
(`claude/admin-portal-ui-modernize-hhzgu5`, the merge-base): `git diff --name-only` shows exactly the 10
allow-listed files (no `sql/`, `scripts/`, `lib/*.ts`, or `tests/` file). The forbidden-call grep (
`supabase\.|validateHoldingsRow|validateTunableValue|is_admin|set_kill_switch|\.rpc\(|createClient`)
returns **exactly one match**, a prose doc-comment in `AuthGuard.tsx` (`// Purely cosmetic (avatar-chip
initials) — never used for authorization, which is is_admin()/RLS.`) — confirmed by inspecting the diff
line-by-line: every real call site (`createClient()`, `.rpc("set_kill_switch", ...)`,
`.from("kill_switch_state")...`, `validateTunableValue(...)`) is byte-for-byte unchanged. **AC5: PASS.**

### 3. Real-browser viewport pass (the gap dev could not close)

Playwright + pre-installed Chromium against the real running app (`next start`, port 4173), all Supabase
calls mocked at the network layer (auth cookie seeded per `@supabase/ssr`'s actual cookie codec so the
real authenticated screens render, not just the "Checking session…" skeleton). All 5 screens
(login/watchlist/holdings/tunables/track-record) + shared header/kill-switch, at 375px/768px/1280px (15
screen×width checks) plus targeted AC2/AC3/AC4/AC7/AC8 assertions and a mocked kill-switch RPC round-trip.
Screenshots taken at every screen×width for visual record.

**Result: 156 pass / 3 fail** (the 3 failures are BUG-011 below, all the same root cause).

- **AC1 (no page-level horizontal scroll):** PASS, 15/15 — `scrollWidth <= clientWidth` held for every
  screen at every width, including track-record at 375px (its 9-column table scrolls *inside*
  `.table-scroll`, never at the page level).
- **AC2 (watchlist/holdings stacked cards @375px):** PASS — real `<tr>` computed `display: block`,
  `data-label` present on every cell, Edit/Delete individually clickable with a real bounding box.
- **AC3 (nav + kill-switch reachable via collapsed control @375/768):** PASS — `.nav-toggle-btn` exists,
  fits inside the header, opening it reveals Watchlist/Holdings/Tunables/Track record/Sign out all
  visible; kill-switch toggle itself stays visible independent of the nav toggle (matches design intent:
  "reachable with zero extra clicks at any width").
- **AC4 (1280px 4-col grid):** PASS — `tbody` computed `display: grid`, `grid-template-columns` resolves
  to 4 tracks, for both watchlist and holdings.
- **AC7(b)/(c) (tunables always-visible compact cards, friendly label + demoted raw key):** PASS at all
  three widths — all 10 `.tun-card`s present, all 10 raw `SNAKE_CASE` keys still in the rendered markup,
  friendly heading ≠ raw key, value input/select + Save visible with zero clicks.
- **AC7(a) (flatter shadow/radius tokens across watchlist/holdings/track-record cards):** **FAIL** — see
  BUG-010 and BUG-011.
- **AC8 (sliding toggle-switch, not a static pill):** PASS — `.killswitch .toggle` exists, `.killswitch
  .pill` count is 0, at every screen/width. Clicking the toggle (mocked RPC): fires
  `rpc/set_kill_switch` with `{p_paused: true, p_source: "admin-portal"}`, and the toggle's visual state
  flips to `.paused` after the (mocked) success response — the click-target/visual-state half of AC8 is
  confirmed. The **persisted-row** half (a real `kill_switch_audit` row appearing) cannot be confirmed
  from this sandbox — no live Supabase reachable (see environment note above) — but AC5's structural grep
  already proves the RPC call site itself is byte-for-byte unchanged from INC-7, so INC-7's own already-
  established proof mechanism still applies unmodified; this is not a new gap INC-13 introduces.
- **Login screen:** renders correctly at all three widths (`.login-card` present, no page scroll).

### 4. Functional-regression spot check (CRUD + validation wiring survives the markup restructure)

Separate mocked-network Playwright pass, 3 widths × (watchlist Edit→Save, watchlist Delete, tunables
reject-then-accept a value): **15/15 pass**. Confirms Add/Edit/Delete and validate-then-write handlers
still fire the correct REST calls with correct payloads after INC-13's markup/CSS restructure — no wiring
regression from the responsive rework, at any breakpoint.

### 5. Manual regression checklist (auth gate, RLS, CRUD, validation, pagination, kill-switch round-trip)

**Partially blocked by the same environment gap as §3's live-Supabase note** — the auth-gate-reject,
live-RLS-write-confirmed-in-Supabase, and live kill-switch-audit-row portions of INC-13 AC6's checklist
need real network access this sandbox doesn't have, identical to dev's own stated limitation. What **was**
verified this session, without a live backend:
- CRUD/validation logic itself: covered unchanged by the untouched `tests/admin_portal/*.test.ts` (§1) and
  by §4's live-wiring spot check.
- Track-record pagination/sort/filter code: zero diff (confirmed via the AC5 grep in §2 and a manual read
  of `track-record/page.tsx` — only `className`/wrapper markup changed, `loadRows`/`toggleSort`/
  `applyFilters` bodies untouched).
- Kill-switch click → RPC → visual-state update: confirmed via §3's mocked round-trip.
**Not verified this session (real backend required):** allowlist-reject flow, live Supabase writes for
watchlist/holdings/tunables, and a live `kill_switch_audit` row appearing. Flagging for the user/release to
decide whether to accept the same residual-live-check status INC-3/INC-4/INC-11 already carry, or to
re-run this specific check once Supabase egress is available.

### 6. Dev's two flagged judgment calls (`docs/handoff.md`)

- **(a) Watchlist/holdings: real `<table>` at tablet, card grid only at desktop.** Investigated against
  AC4's literal text (only tests 1280px), `docs/design/admin-portal.md` §16.10's "what dev implements"
  narrative (says 4-col desktop/3-col tablet/2-col phone), `docs/ux-spec.md` §7.3.2's density table (same:
  "4-col desktop / 3-col tablet / 2-col phone"), and the approved mockup (`direction-g-compact-toggle.html`,
  which is a card grid at every breakpoint, 2-col even at phone). **Empirically confirmed via computed
  style at 768px: `.crud-table tr` has `background: rgba(0,0,0,0)`, `box-shadow: none`, `border-radius:
  0px` — i.e., literally zero card treatment at tablet, not just "a plainer card."** This crosses from "a
  reasonable reading of an ambiguous doc" into a violation of AC7(a)'s explicit "at all three widths…
  across watchlist, holdings… cards" text — filed as **BUG-010**.
- **(b) Track-record: kept as a real, sortable table in a card-styled scroll container, not per-row
  cards.** AC7(a) literally names "track-record cards"; `docs/ux-spec.md` §7.3.2 explicitly requires "3-col
  card grid desktop / 2-col tablet / 1-col phone" for track-record; the approved mockup implements exactly
  that (`.tr-cards`). **Empirically confirmed: zero `.tr-cards`/card elements exist for track-record at any
  of the three widths** — there is no "track-record card" for AC7(a)'s shadow/radius requirement to apply
  to. This is a real AC violation, not an accepted judgment call — filed as **BUG-011**. (Dev's stated
  reasoning — that literal per-row cards would either hide the sortable `<th>` controls or require
  reinventing sort as a non-`<th>` tap target — is a legitimate implementation concern, but the fix is
  tech-lead's/dev's call, not something qa can wave through against an explicit AC.)
- **(c) Kill-switch reuses legacy `PAUSED`/`RUNNING`/`Resume`/`Pause` strings as an accessible label
  (`title` + `.sr-only` span).** No AC violated — AC8 only requires a `.toggle` element (not `.pill`) and
  an unchanged RPC call site, both true (§3/§2). **Accepted**, no bug filed.

### Bugs filed

**BUG-010 — Watchlist/holdings rows have zero card styling at the tablet breakpoint (640–1023px),
contradicting AC7(a) and `docs/ux-spec.md` §7.3.2's density table — moderate.**
- **Increment:** INC-13. **FR/NFR:** NFR8, AC7(a) (`docs/design/increment-plan.md`).
- **Repro:** load `/watchlist` (or `/holdings`) at 768px viewport width; inspect a `<tr>` in `.crud-table
  tbody` — computed `background-color: rgba(0,0,0,0)`, `box-shadow: none`, `border-radius: 0px` (CSS at
  `admin-portal/app/globals.css`'s `@media (min-width:640px) and (max-width:1023px)` block explicitly
  zeroes these). Screenshot: `shot-watchlist-768.png` (this session's scratch dir) shows a plain flush
  table, no card boundaries.
- **Expected:** per AC7(a) ("flatter single-layer card shadows and the smaller radius-md/radius-lg tokens
  … across watchlist, holdings, and track-record cards" — applies "at all three widths") and `docs/ux-
  spec.md` §7.3.2 ("4-col desktop / 3-col tablet / 2-col phone" for watchlist/holdings), tablet width
  should show card-styled watchlist/holdings rows (a 3-col card grid per the approved mockup).
- **Actual:** a plain, unstyled real `<table>` with no card shadow/radius/background at all at 768px.
- **Owner:** dev (tech-lead may instead choose to update `docs/design/admin-portal.md` §16.10's
  contradictory mechanism paragraph and get user sign-off on "table at tablet" as an intentional deviation
  — either way, this is a decision above qa's pay grade, being handed back rather than silently accepted).

**BUG-011 — Track-record view never renders as cards at any width, contradicting AC7(a)'s literal
"track-record cards" text and `docs/ux-spec.md` §7.3.2's card-grid density table — moderate-high.**
- **Increment:** INC-13. **FR/NFR:** NFR8, AC7(a).
- **Repro:** load `/track-record` at 375px, 768px, or 1280px; `document.querySelectorAll(".tr-cards,
  [class*='tr-card']")` returns 0 at every width; only `.log-table` (a real `<table>`, class renamed from
  `crud-table`) exists, wrapped in a `.table-scroll` container. Screenshot: `shot-track-record-375.png`
  shows a flat table with columns already cut off (`Parse stat…`) requiring internal horizontal scroll to
  see the rest.
- **Expected:** per AC7(a) (names "track-record cards" as one of three card types needing the token
  treatment) and `docs/ux-spec.md` §7.3.2 ("3-col card grid desktop / 2-col tablet / 1-col phone" for
  track-record), and the approved mockup (`.tr-cards` grid at every breakpoint).
- **Actual:** no track-record card exists at any width — always a table in a card-styled scroll wrapper.
- **Note:** dev's stated concern (converting the sortable `<th>` controls to a card layout without a new
  interaction design) is real and worth tech-lead weighing against the AC — but the AC as written is not
  satisfied today.
- **Owner:** dev/tech-lead (same reconciliation choice as BUG-010: build the literal per-row card layout,
  or get design.md/AC7 explicitly revised with user sign-off for the table-in-scroll-container approach).

### Verdict

**FAIL — 2 bugs filed (BUG-010, BUG-011), both AC7(a) violations traced to dev's own flagged judgment
calls (a) and (b).** Everything else: **PASS** — existing suite 82/0 (TS) + 286/1 (Python, 1 pre-existing/
unrelated), AC5 structural enforcement clean, AC1/AC2/AC3/AC4/AC7(b)/AC7(c)/AC8 all independently confirmed
via a real-browser Playwright pass against the actual running app (the gap dev flagged as unclosed), CRUD/
validation wiring survives the restructure at all three widths, judgment call (c) accepted. Not a
regression risk to existing functionality — both bugs are visual/layout-density gaps against the approved
design, not functional breakage. Dev to fix BUG-010/BUG-011 (or get the design doc/AC revised with tech-
lead + user sign-off if the table-based approach is to be accepted instead); qa re-tests after either path.

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

**BUG-010 — see INC-13 run above.** **Owner:** dev/tech-lead.

**BUG-011 — see INC-13 run above.** **Owner:** dev/tech-lead.
