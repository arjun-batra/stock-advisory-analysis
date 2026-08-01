# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-14 — Admin portal visual fidelity fix (NFR8 conformance, corrects INC-13) — 2026-08-01

**Scope.** Branch `inc-14-admin-portal-visual-fidelity-fix` (`main`@`da50ed8` + commits `5882026`,
`3ffe56f`). Files touched: `admin-portal/app/globals.css`, `admin-portal/app/(app)/watchlist/page.tsx`,
`admin-portal/app/(app)/holdings/page.tsx` (+ `docs/handoff.md`). Verified independently against
`docs/design/increment-plan.md`'s INC-14 AC1–AC6 — did not take dev's reported 60/60 count on trust; ran a
fresh, independently-authored real-browser Playwright pass (mocked Supabase network, real
`next build && next start` on port 4174, pre-installed Chromium `/opt/pw-browsers/chromium-1194`, a
globally-installed `playwright` driver — no `playwright install` run).

### 1. Real-browser verification (independent of dev's script)

Two independent Playwright scripts (session scratchpad, not committed — same posture as prior admin-portal
browser checks), covering watchlist + holdings at 375/768/1280px, and a supplementary regression pass
across all 4 authenticated routes (watchlist/holdings/tunables/track-record):

- **Pill/badge markup (AC1), watchlist:** exactly 3 `.pill.type`, 1 `.pill.held`, 2 `.pill.watch` rendered
  (matching 3 mocked rows — 1 held, 2 watch-only) at all 3 widths; market renders in `.mkt` (not a pill,
  confirmed `background-color: rgba(0,0,0,0)`) — zero raw `data-label="Market"` `<td>` remains. Exact color
  match to the mockup: `.pill.held` computed `background-color: rgb(220, 252, 231)` (`--color-success-bg`),
  `.pill.type` computed `rgb(219, 234, 254)` (`--color-info-bg`) — confirmed distinct from each other.
- **Card elevation (AC3), all 3 widths, both pages:** `.ticker-card` computed `box-shadow` is non-`none`
  (`rgba(20, 20, 43, 0.08) 0px 1px 2px 0px`) and `background-color: rgb(255, 255, 255)` differs from
  `document.body`'s `rgb(244, 245, 247)` at 375px, 768px, **and 1280px** — the specific gap INC-13 AC6 left
  unmeasured (it only re-ran functional checks at all 3 widths, never this computed-style assertion at
  desktop width). Confirmed measured directly, not assumed.
- **Modal open/close via real interaction (AC2), both pages, all 3 widths:** clicking the toolbar
  "+ Add ticker"/"+ Add holding" button (768/1280px) or the `.fab` (375px) opens `.modal-overlay`/
  `.form-modal` with `role="dialog"`/`aria-modal="true"` and the correct "Add …" heading; clicking
  `button.secondary` ("Cancel") or clicking the scrim (outside `.form-modal`, verified via a real
  `page.mouse.click` at a scrim corner, not a CSS-class assertion) closes it without adding a row (row
  count confirmed unchanged via a post-close DOM read); clicking an edit icon opens the same modal
  pre-filled (watchlist ticker input = `"AAPL"`; holdings shares input = `"10"`) with an "Edit …" heading.
  111 checks in the primary script, all passed.
- **Supplementary regression (INC-13 AC1–AC3 re-check, AC5's explicit instruction):** zero horizontal
  scroll and zero console errors on all 4 authenticated routes at all 3 widths (12 combinations); 4-item nav
  reachable at every width; `.card-grid` `grid-template-columns` resolves to 2/3/4 tracks at 375/768/1280px
  on both watchlist and holdings; `.fab`/`.toolbar-add-btn` visibility is mutually exclusive per band on
  both pages. 51 checks, all passed.
- **Total independent browser verification: 162/162 checks passed** (111 + 51), corroborating dev's
  60/60 claim with a separately-authored script and a fresh session, not a re-run of dev's own script.

### 2. Automated suites

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **287 passed, 0 failed.**
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed**
  (after a qa-owned hardening of `static_source_checks.test.ts`, see §3 below — same pass count as before
  hardening, no assertion intent changed).
- `cd admin-portal && npm run build && npm run lint` → builds clean, 8 routes, zero lint
  errors/warnings.

### 3. `static_source_checks.test.ts`'s flagged regex — investigated, not waved through

Dev flagged the `insert()`/`update()`-payload-shape regex
(`/\.(insert|update)\(\s*\{?\[?\{?([\s\S]*?)\}\]?\)/g`) as "fragile to unrelated function ordering." Traced
this directly rather than trusting the characterization:

- **Root cause confirmed:** the regex's suffix is `\}\]?\)` — a **mandatory** literal `}` (only the `]` is
  optional), which must appear with **zero intervening characters** before the closing `)`. The
  `insert([{...},])` call's own object literal closes as `},\n    ])` (comma + whitespace between `}` and
  `]`), which never satisfies that suffix — so the lazy capture skips straight past it and keeps scanning
  until it finds the next place in the file where a literal `}` is immediately followed by (optional `]`
  then) `)`. That happens to be `setEditForm({...})` inside `openEditModal` (a `})`-shaped call with no gap)
  — an unrelated function dev deliberately kept positioned between `handleAdd`/`handleUpdate` specifically
  to keep this incidental match shape intact (documented in dev's own code comment and handoff).
- **Empirically confirmed fragile, not currently broken:** removing `openEditModal` from between the two
  write calls in a scratch copy of the file (simulating a future, purely-presentational refactor with zero
  behavioral change) drops the regex's match count from 2 to 1, which would fail the
  `assert.ok(writeCalls.length >= 2, ...)` line — even though nothing about the currency-payload contract
  changed. **Confirmed with dev's actual shipped code (not the scratch copy): the test passes today (14/14
  in that file)** — INC-14 did not break it; dev's positioning of `openEditModal` (unchanged in intent,
  preserved from pre-INC-14) keeps the incidental match shape alive.
- **Verdict: fragile-but-passing, not a failure caused by INC-14.** No bug filed against dev — this is a
  test-quality issue in a file qa owns. Fixed directly (permitted — qa may fix its own tests): replaced the
  regex with a paren/bracket/brace-depth-counting extractor
  (`extractCallArgs`) that finds each call's true matching closing paren regardless of what other code
  exists elsewhere in the file. Re-ran: 14/14 still passing in `static_source_checks.test.ts`, same
  assertions, same currency-absence property enforced — now structurally robust to future unrelated
  refactors instead of accidentally-correct.

### 4. Structural no-regression grep (AC4)

```
git diff -U0 main..inc-14-admin-portal-visual-fidelity-fix -- admin-portal/ \
  | grep -E "supabase\.|validateHoldingsRow|validateTunableValue|is_admin|set_kill_switch|\.rpc\(|createClient"
```
**Zero matches** (exit 1) — confirmed independently. Note: a default-context (`-U0` omitted) grep pass
first turned up one apparent hit (`const supabase = createClient();`), but that line carries a leading
space in the diff — i.e. unmodified **context**, not an added/removed line. Re-running with `-U0` (zero
context, the exact form the brief specifies and dev used) returns genuinely zero matches. `git diff
--name-only main..inc-14-admin-portal-visual-fidelity-fix` shows only `admin-portal/app/globals.css`,
`admin-portal/app/(app)/watchlist/page.tsx`, `admin-portal/app/(app)/holdings/page.tsx`, and
`docs/handoff.md` — matches the increment's allow-list exactly.

### 5. Scope boundary (AC6)

`git diff --name-only main..inc-14-admin-portal-visual-fidelity-fix -- 'admin-portal/app/(app)/tunables/*'
'admin-portal/app/(app)/track-record/*'` returns **empty** — confirmed tunables and track-record are
untouched by this diff. Supplementary browser pass (§1) also directly re-confirmed both those screens still
render with no regression (no horizontal scroll, 4-item nav, zero console errors) at all 3 widths, even
though INC-14's own scope never claims to have changed them.

### 6. Open finding — flagged for tech-lead, not filed as a bug against dev

**AC1's literal wording vs. the holdings entity's actual data model.** AC1 says "**Watchlist and holdings**
cards render... (b) the type value... inside `<span class="pill type">`... (c) the status value... inside
`<span class="pill held">`/`<span class="pill watch">`." Independently confirmed: the **holdings** page
renders `.mkt` correctly but renders **zero** `.pill.type`/`.pill.held`/`.pill.watch` elements — only the
**watchlist** page shows those three pill classes. Investigated before flagging:
- The `holdings` table (`sql/schema.sql`) has no `type` or `status` column — only `ticker`/`shares`/
  `cost_basis`/`currency`. Those two fields exist only on `watchlist`.
- The two-page split (`/watchlist` showing type+status, `/holdings` showing shares+cost+currency) predates
  INC-13/INC-14 entirely — confirmed via `git log` that `holdings/page.tsx`'s `HoldingsRow` interface
  (no type/status fields) is unchanged back through the INC-10 fix round.
- `docs/ux-spec.md` §2.2 ("Shared UX contract," describing behavior identical across all directions,
  claimed unchanged from the functional design) describes "**one combined screen**: a table of watchlist
  entries; holdings fields... appear inline for rows where `status = held`" — this does **not** match the
  actual, longstanding two-table/two-page architecture, and appears to be stale/aspirational wording in the
  designer's spec rather than a description of what INC-5 actually built or what INC-13/14 were ever asked
  to change (both are explicitly presentation-layer-only, no functional/data-model change permitted).
- Given the "no functional change" boundary NFR8/INC-13/INC-14 all state explicitly, and that "status" is
  trivially always "held" for every row that exists in the `holdings` table at all (a status pill there
  would be redundant, not missing information), dev's interpretation (pills only where the underlying
  entity has that data) is a defensible reading of a genuinely ambiguous AC — **not** waved through
  silently, but also not filed as a BUG against dev, since resolving it either way is a
  tech-lead/documentation call (fix the stale `ux-spec.md` §2.2 wording, or clarify AC1's intent), not a
  code defect qa can adjudicate unilaterally. Routed to tech-lead for a decision; not blocking this
  increment's sign-off given the schema/architecture constraints above.

### Verdict — INC-14

**PASS.** 287/0 Python, 82/0 TypeScript (one test hardened by qa, same pass count, more robust), admin-portal
build/lint clean, 162/162 independent real-browser checks (watchlist + holdings + full 4-screen regression)
at 375/768/1280px, structural no-regression grep zero matches, scope boundary (tunables/track-record)
confirmed untouched. Zero new bugs filed. One documentation-ambiguity finding routed to tech-lead (§6, not
blocking).

**Is the live mismatch Arjun reported genuinely fixed?** Yes, based on this independent verification, not
just dev's self-report: pill/badge markup for type/status now renders with the exact mockup colors
(confirmed via `getComputedStyle`, not source-reading), market renders as the mockup's plain `.mkt` label
(not over-built into a pill), the Add/Edit interaction is now a real modal verified via actual clicks
(open/close/cancel/scrim/pre-fill, not CSS-class presence), and desktop-width (1280px) card elevation is
directly measured and visually distinct from the page background — the exact three gaps the orchestrator's
diagnosis named as missing from the merged INC-13 code are now independently confirmed present and working.

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
