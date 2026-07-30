# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-10 — fix-cycle-2 re-test (REV-113 major, REV-112 minor) — 2026-07-30

**Scope.** Verification of dev's fix-cycle-2 on INC-10 at commit `649c945`, covering **REV-113** (major,
`docs/review-log.md` Pass 26) and **REV-112** (minor, same pass). Read `docs/review-log.md` Pass 26's
REV-113/REV-112 entries, `docs/handoff.md`'s INC-10 fix-cycle-2 entry, `scripts/ai_judge.py`'s
`_ticker_block`, `scripts/state.py`'s `build_position`, and the new
`sql/admin_portal_tunables_alerts_enabled_description_fix.sql`. 2 of 3 fix cycles used.

### REV-113 — mismatched-currency figures no longer reach the prompt by any route

Confirmed by direct read of `scripts/ai_judge.py:101-116`: for a held position where
`position["currency_mismatched"]` is true, `_ticker_block` now omits both `cost_basis` and `price` from
the held-position line entirely and states plainly that the two figures are not comparable and that no
gain/loss should be computed — replacing the old unlabeled `Cost basis: X CUR, Current price: Y` line
that let a model do the subtraction itself even with `pl_pct` suppressed.

**Closed the coverage gap dev flagged against itself** (`docs/handoff.md`: "no existing test exercises
`_ticker_block` with a non-`None` position at all"). Added to `tests/test_ai_judge.py`:
- `test_ticker_block_currency_mismatch_omits_cost_basis_and_states_not_comparable` — mismatch case: no
  labeled cost-basis figure, no `Unrealized P/L` line, "not comparable" instruction present, both
  currencies named, `Shares` still shown.
- `test_ticker_block_currency_mismatch_leaks_no_cost_basis_figure_by_any_route` — walks the **whole**
  rendered block (not just the held-position line) and confirms the raw cost-basis number (`50.0`/`50`)
  does not survive anywhere by another route, and that the price which legitimately remains appears
  exactly once, only in the `Price/volume` line, unambiguously labeled with the fundamentals currency.
- `test_ticker_block_currency_mismatch_fails_on_pre_fix_behavior` — locks in the specific pre-fix line
  shape (`Cost basis: 50.0 USD ... Unrealized P/L: n/a`) as absent, named so a future regression to the
  old branch is caught explicitly.
- `test_ticker_block_agreeing_currency_position_line_unchanged` — agreeing-currency case: the normal
  held-position line is byte-identical to the pre-REV-113 rendering (`Shares: 10, Cost basis: 50.0 CAD,
  Current price: 60.0, Unrealized P/L: 20.0%`), proving the fix only branches on an actual mismatch.

**Verified the mismatch tests genuinely test the fix, not incidental behavior:** reverted
`scripts/ai_judge.py` to the pre-fix content (`git show 6784d26:scripts/ai_judge.py`) in a scratch copy,
ran the four new tests — all three mismatch-case tests fail against the pre-fix code (cost basis and
unlabeled price still render on one line), the agreeing-currency test still passes (unaffected by the
fix, as expected). Restored the working tree afterward (`git diff` on `scripts/ai_judge.py` clean —
qa never edits production code).

**`build_position`'s `currency_mismatched` flag** (`scripts/state.py:164-202`) is the single source of
truth `_ticker_block` now consumes. Extended the three existing `test_state.py` currency-guard tests
(no new test files needed — same fixtures, added assertions) to assert the flag directly, not just
`pl_pct`'s side effect:
- Match (`test_build_position_computes_normally_when_currencies_agree`): `currency_mismatched is False`,
  `pl_pct` computed normally — unchanged from last pass's verification.
- Mismatch (`test_build_position_suppresses_pl_pct_on_currency_mismatch`): `currency_mismatched is True`,
  `pl_pct is None`, warning logged — unchanged from last pass's verification.
- Unknown fundamentals currency, both the no-key and empty-dict shapes
  (`test_build_position_missing_fundamentals_currency_is_unknown_not_mismatch`):
  `currency_mismatched is False` in both, `pl_pct` still computed — confirms "unknown" is correctly
  distinct from "mismatched," and `pl_pct` suppression behavior is unchanged from when this was last
  verified (Pass 26 predecessor run).

**REV-113 holds. Verified 2026-07-30 (fix-cycle-2).**

### REV-112 — corrective SQL now additive, idempotent, and genuinely re-runnable

Read the new `sql/admin_portal_tunables_alerts_enabled_description_fix.sql` (one `update` statement,
scoped to `key = 'ALERTS_ENABLED'`) and the diff to `sql/admin_portal_tunables.sql`
(`git show 649c945 -- sql/admin_portal_tunables.sql`): confirmed the diff removes only the trailing
`update` block and its comment, replacing it with a one-line pointer comment — lines 1-86 (the
already-applied `create table`/trigger/policies/seed `insert`) are byte-for-byte untouched.

Independently re-ran BUG-008's own re-runnability standard on a local Postgres 16 scratch database
(dropped after verification): applied `sql/schema.sql` + `sql/admin_portal_rls.sql` +
`sql/admin_portal_tunables.sql`, then simulated a live-seeded row still carrying the **original,
pre-DEEP-005** stale description (`git show 99e0255:sql/admin_portal_tunables.sql`'s literal seed text,
which is what a project seeded before this fix round actually has live), then:
- Applied the new fix file once → `UPDATE 1`, description corrected to the AND-gate text.
- Applied it again, verbatim → `UPDATE 1` again, no error, description unchanged (idempotent — matches
  BUG-008's established double-apply standard).

Confirms the file **genuinely corrects** `ALERTS_ENABLED`'s seed description against a database seeded
from `sql/admin_portal_tunables.sql`, is additive (touches no table/trigger/policy definition), and is
re-runnable to the same standard as the other two INC-10 SQL files. The original file's already-applied
content is otherwise untouched, confirmed by direct diff.

**REV-112 holds. Verified 2026-07-30 (fix-cycle-2).**

### Regression suite

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **253 passed, 0 failed** (baseline 249 +
  4 new `_ticker_block` tests; 3 existing `build_position` tests gained assertions, no new test files
  for those).
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **82 passed, 0 failed**
  (unchanged from baseline — this fix cycle touched no TypeScript).
- Shippability: `SKIP_TUNABLES_FETCH=true python3 -c "import run_hourly, run_discovery, publish_prices"`
  → all three entry points import cleanly (this fix cycle touches `scripts/ai_judge.py`,
  `scripts/state.py`, `sql/`; no entry-point contract change).
- No SQL applied to the live Supabase project (per instruction) — all SQL verification against a local
  scratch Postgres instance, dropped after use.

### Verdict — INC-10 fix-cycle-2

**PASS.** REV-113 (major) and REV-112 (minor) both independently verified closed, not accepted on dev's
account — REV-113's fix confirmed to actually prevent cost-basis leakage by every route in the rendered
block (not just the one line that changed), confirmed to genuinely change model-facing output (fails
against pre-fix code), and confirmed not to weaken the pre-existing agreeing-currency/unknown-currency
behavior. REV-112's file confirmed additive, idempotent, and actually effective against a realistically
stale live row. No new bugs filed this pass. **INC-10 is clean for reviewer** — no open qa-owned defect
remains against this increment (REV-114, the SQL-behavior CI gap, is a pre-existing systemic limitation
flagged for qa as future work, not a fix-cycle-2 regression, and does not block this verdict).

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — fix-cycle-2
touched no `_parse_batch` code. Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006
fix-cycle-2 entry (repro: `tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_
last_write_wins_undocumented_elsewhere`). **Owner:** tech-lead (design-level call on `_parse_batch`'s
ticker-keyed return contract, if ever addressed).
