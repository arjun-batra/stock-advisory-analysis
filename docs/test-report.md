# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-15 fix cycle 1 — REV-151/REV-152 re-verification — 2026-08-01

**Scope.** Branch `inc-15-tickers-merge-nav-fix`, dev's fix commit `d9702aa` (on top of reviewer's Pass 37
tip `d6e6ad7`). Files touched this cycle: `sql/tickers_screen_rpc.sql`,
`admin-portal/components/TickerEditModal.tsx`, `tests/admin_portal/static_source_checks.test.ts` (2 new
regression tests, dev-authored per the orchestrator's explicit instruction).

### REV-151 (SQL missing revoke-execute) — RESOLVED, independently re-verified

Read `sql/tickers_screen_rpc.sql` directly (not taken on dev's word) and diffed the pattern against
`sql/kill_switch.sql:115` byte-for-byte. Both new functions now read:
```
revoke execute on function public.set_ticker_holding_status(text, text, numeric, numeric) from public, anon, authenticated;
grant execute on function public.set_ticker_holding_status(text, text, numeric, numeric) to authenticated;
```
and the equivalent pair for `delete_ticker(text)` — identical statement order, identical three-role list
(`public, anon, authenticated`), no blank line inserted, matching `kill_switch.sql:115`'s established shape
exactly. **RESOLVED.**

### REV-152 (silent data loss on combined edit+status-switch) — RESOLVED, independently re-verified

Read `TickerEditModal.tsx` directly: `applyMarketTypeEdit()` is now a shared helper called from both
`doSave()` and `confirmSwitchToWatchOnly()`, in that order (edit write, then the
`set_ticker_holding_status` RPC) — matches dev's account in `docs/handoff.md`'s fix-cycle entry.

Wrote an independent real-browser Playwright script from scratch (not a re-run of dev's script) —
`next build && next start` (port 4174/4175), Supabase REST+RPC mocked at `context.route()` with an
in-memory fixture store, a `@supabase/ssr`-shaped auth cookie built via the real installed
`stringToBase64URL` codec, pre-installed Chromium (`/opt/pw-browsers/chromium-1194`), no `playwright
install` run. Three scenarios, 24 checks, all passed:
- **Scenario A (combined edit — the exact reported bug)**: AAPL held, changed Market US→TSX, Type
  Stock→ETF, Status Held→Watch-only, Save, Confirm. 12/12 checks passed: exactly one `watchlist` PATCH
  fired carrying the EDITED values (`market: "TSX"`, `type: "ETF"`), fired strictly before the single
  `set_ticker_holding_status` RPC (`p_status: "watch-only"`), no error, modal closed cleanly, and the
  in-memory store reflects the edited market/type/status plus holdings row removed.
- **Scenario B (plain-edit-only, status unchanged, held)**: changed Market only, left Status as `held`.
  6/6 checks passed: exactly one `watchlist` PATCH with the edited value, **zero** RPC calls (confirms the
  fix didn't introduce an RPC call on the no-status-change path), holdings untouched.
- **Scenario C (pure-status-switch-only, no field edit, held→watch-only)**: 6/6 checks passed: RPC fires
  once with `p_status: "watch-only"`, no error, store reflects unchanged market/type (proving no field
  corruption) and the status flip. Noted (informational, not a failure) that `applyMarketTypeEdit()` now
  fires unconditionally on this path too, writing back unchanged values — harmless by design, mirrors
  `doSave()`'s own unconditional pattern, not a functional regression.

**Discriminating-power sanity check (own test, not dev's):** re-ran Scenario A's script against the
pre-fix `TickerEditModal.tsx` (`git show d6e6ad7:...`, temporarily swapped in, rebuilt) — **6/12 checks
failed** exactly as expected (zero `watchlist` PATCH fired, edited market/type never reached the store),
confirming the script actually exercises the reported defect rather than trivially passing. Restored the
fixed file afterward (confirmed byte-identical to the committed version via diff).

**RESOLVED.**

### New regression tests in `tests/admin_portal/static_source_checks.test.ts` — meaningful, verified independently

Confirmed both of dev's 2 new tests are genuine regression guards, not tautologies, by checking them against
`d6e6ad7` (pre-fix) content directly:
- `tickers_screen_rpc.sql: both RPCs have revoke execute ... (REV-151)` — regex requires the revoke line
  immediately before each grant line; against `d6e6ad7`'s SQL (no revoke lines at all) this fails.
- `edit modal: held->watch-only confirm path applies any pending market/type edit ... (REV-152)` — extracts
  `confirmSwitchToWatchOnly()`'s body and asserts `applyMarketTypeEdit()` appears at a lower index than the
  RPC call; against `d6e6ad7`'s version (no `applyMarketTypeEdit()` call exists in that function at all)
  this fails on the `assert.ok(editCallIdx >= 0, ...)` line.

Both tests fail against the exact pre-fix code they guard against and pass against the fix — meaningful.

### Automated suites — full re-run

```
SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short                 # 287 passed, 0 failed
node --experimental-strip-types --test tests/admin_portal/*.test.ts      # 84 passed, 0 failed (was 82; +2 new)
cd admin-portal && npm run build && npm run lint                          # 7 routes, clean build, zero lint errors/warnings
```
Both counts match the expected baseline exactly (287 Python, 84 TypeScript = 82 + 2 new).

### Structural no-regression check — re-run against the FULL branch diff (`main..inc-15-tickers-merge-nav-fix`)

`git diff --name-status main..inc-15-tickers-merge-nav-fix` shows the same file set as qa's original INC-15
pass (no new files snuck in this fix cycle beyond the 2 named + the test file + docs). Re-ran the
call-site-tracing content grep (`supabase\.|validateHoldingsRow|validateTunableValue|validateWatchlistRow|
is_admin|set_kill_switch|\.rpc\(|createClient|revoke execute|grant execute`, `-U0`, full diff not just the
fix commit) — same matches as qa's original pass (§1 of the archived original entry) plus the two new
`revoke execute`/`grant execute` line pairs. No new call site, no new RPC, no new validation logic —
confirms nothing beyond what's already accounted for.

### Spot-check of original 14 ACs + original 31 supplementary checks — quick re-run (only 2 files changed)

Since only `sql/tickers_screen_rpc.sql` and `TickerEditModal.tsx` changed this cycle, re-ran only the AC
paths that share the changed file rather than a full from-scratch redo:
- **AC7 (watch-only→held)** — 2/2 checks passed: exactly one `set_ticker_holding_status` RPC fires with
  the correct `p_shares`/`p_cost_basis`, holdings row created, status flips to `held`.
- **AC9 (delete)** — 2/2 checks passed: exactly one `delete_ticker` RPC fires, both `watchlist` and
  `holdings` rows removed.
- **AC8 (held→watch-only) and AC10 (plain field edit, zero RPC calls)** — re-covered directly by Scenarios A
  and B above (same assertions, stronger since they also probe the combined-edit case AC8's original text
  never tested).
- Nav/breakpoint/card-layout/AC1–6/11–14 checks are untouched by this fix cycle's diff (no nav, CSS, or
  `tickers/page.tsx` changes) — not re-run from scratch; confirmed via `git diff --name-only d6e6ad7..HEAD`
  that neither file is in this cycle's changed set.

### Verdict — INC-15 fix cycle 1

**PASS.** REV-151 and REV-152 both confirmed fixed by independent re-verification (not re-running dev's own
checks): REV-151 by direct SQL diff against the established pattern, REV-152 by an independently-authored
24-check Playwright script (plus a discriminating-power sanity check proving the script would have caught
the original bug) covering the reported combined-edit case and both edge cases (plain-edit-only,
pure-status-switch-only) — neither edge case broke. Both of dev's new regression tests verified meaningful.
287/0 Python, 84/0 TypeScript (matches expected 287 + 82+2 exactly). Structural diff re-check against the
full branch (not just the fix commit) shows nothing new beyond what's already accounted for. Zero new bugs
filed. **This clears qa's side — recommend routing back to reviewer next**, per the pipeline (reviewer's
Pass 37 was the source of REV-151/152/153; REV-153 was tech-lead's doc-only fix, out of qa's scope to
re-verify beyond confirming it doesn't touch `tests/` — not re-checked here).

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
