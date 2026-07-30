# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## INC-10 — Tunables write-time validation + holdings-currency derivation (FR30, FR11, FR29;
DEEP-005+DEEP-006) — 2026-07-30

**Scope.** dev handoff at `7e29f30`. Read `docs/handoff.md`'s INC-10 section, `docs/design/
increment-plan.md` `### INC-10`, `docs/design/admin-portal.md` §16.3, `docs/design/
admin-portal-tunables.md` §16.4, `docs/design/non-functional-ops.md` §7.3/§8, `docs/requirements.md`
FR30/FR11/FR29 + Decisions #34/#35, and `docs/review-log.md`'s DEEP-005/DEEP-006/REV-109. `git diff
--name-only` against the pre-INC-10 commit confirms exactly the 10 files dev's handoff lists (7 production
+ 2 new SQL + 2 flagged test-file adaptations) changed — nothing else.

### Priority one — dev's edits to `tests/admin_portal/tunables_static.test.ts` / `validation.test.ts`

**Both files reviewed line-by-line against the diff (`git diff 7e29f30~1 7e29f30 -- tests/`).**

- **`tests/admin_portal/tunables_static.test.ts` — mechanical, no coverage loss.** The 3 adapted
  `validateTunableValue(...)` call sites now pass `"GEMINI_MODEL"` as the key; each test's original
  intent (non-blank happy path / whitespace edge case / empty-string invalid input) is unchanged and
  `GEMINI_MODEL`'s rule really is "non-blank," so the adaptation is a faithful signature update, not a
  weakened assertion. **Confirmed, not accepted on trust:** ran all three before/after — same pass/fail
  behavior against equivalent inputs.
- **`tests/admin_portal/validation.test.ts` — mechanical for 3 of 4 edits; the deletion is genuine, not a
  coverage loss, but its replacement was missing until this pass (now added).** `validateHoldingsRow`'s
  `currency` argument/assertions were removed from the happy-path, shares-boundary, and
  invalid-input tests — correct, since `HoldingsInput` no longer has a `currency` field at all (design
  §16.3: currency is now DB-derived, never client-validated) — there is no remaining client-side currency
  rule for those tests to exercise. **The deleted test, audited hardest per instruction:**
  `"validateHoldingsRow: every declared currency is accepted (configurability: CURRENCIES drives
  validation)"` asserted that `CURRENCIES` drove `validateHoldingsRow`'s acceptance — that specific
  behavior is genuinely gone (currency is no longer a `validateHoldingsRow` input), so deleting the test
  as written is correct, not silent coverage loss of that mechanism. **However**, the underlying
  market→currency fact the deleted test protected in spirit **did not simply disappear — it moved** to the
  new `MARKET_CURRENCY` display-only map (`admin-portal/lib/validation.ts`), and dev's own handoff
  confirms it added zero tests for it ("no new tests for `MARKET_CURRENCY` ... that's qa's normal INC-10
  pass"). **Found genuinely untested and fixed this pass:** added `"MARKET_CURRENCY: every market maps to
  a member of CURRENCIES..."` (`tests/admin_portal/validation.test.ts`), which restores equivalent
  configurability coverage against the mechanism that now actually governs currency, and cross-checks it
  against `sql/holdings_currency_derivation.sql`'s own `case v_market when ...` mapping by value.
  `CURRENCIES` itself is still exported/used (as `MARKET_CURRENCY`'s value type) — dropping it from the
  import list would have been the wrong call; it's correctly still imported now that a real consumer of it
  exists in the test file.
- **Net effect:** dev's edits are sound; one real gap existed (no test locks `MARKET_CURRENCY`'s
  correctness or its market-coverage completeness) — closed this pass, not merely trusted.

### Priority two — independent SQL verification (live-project-bound files)

Did not inherit dev's local-Postgres verification claim — spun up a fresh local Postgres 16 instance,
applied `sql/schema.sql`-equivalent `watchlist`/`holdings` tables, `sql/admin_portal_tunables.sql`
verbatim, then both new files verbatim, and independently re-ran every AC's scenario plus additional
idempotency/fire-order checks. Scratch database dropped after verification; nothing left running.

**Behavior — all confirmed correct, independently:**
- All 10 curated keys: a bad value is rejected with an error message naming the key (`DISCOVERY_GAINER_PCT
  = '5%'`, `DISCOVERY_SHORTLIST_MAX = '15.5'`, `ALERTS_ENABLED = 'yes'/'tru'/'True '` all rejected;
  `GEMINI_MODEL = ''` rejected); a valid edit to all 10 keys succeeds, including `ALERTS_ENABLED =
  'TRUE'`/`'false'` case-insensitively; `GEMINI_MODEL_BACKUP = ''` (blank) succeeds.
- A rejected update leaves `updated_at`/`updated_by` byte-for-byte unchanged (re-selected before/after —
  identical timestamp) — no partial side effect from a failed write.
- `select tgname from pg_trigger where tgrelid = 'public.tunables'::regclass and not tgisinternal order by
  tgname` → `tunables_0_validate_update`, then `tunables_stamp_update` — validate genuinely fires first.
- Holdings: inserting one holding per market (US/TSX/NSE) **with `currency='USD'` explicitly submitted in
  the INSERT for all three** (deliberately wrong for TSX/NSE, not merely omitted) still lands as
  `USD`/`CAD`/`INR` respectively. A direct `UPDATE holdings SET currency='USD' WHERE ticker='SHOP.TO'`
  (bypassing the portal, actively trying to force USD onto a TSX ticker) is overridden back to `CAD` —
  confirms the trigger overrides a client that actively fights it, not just one that omits the field.
  Touching only `shares` on an existing TSX row re-derives and keeps `CAD` (self-healing side effect,
  matches dev's documented note).
- Insert for a ticker absent from `watchlist` raises `holdings.ticker % has no matching watchlist row` —
  fail-loud, not a silent bad write.

**Trigger-naming judgment call — confirmed sound.** Dev named the new tunables trigger
`tunables_0_validate_update` rather than the design doc's illustrative `tunables_1_validate` (which read as
renaming the already-live `tunables_stamp_update`). `'0'` sorts before `'s'` in `tgname`, so Postgres's
same-event-BEFORE-triggers-fire-in-name-order rule puts validation first without redefining or dropping the
live `tunables_stamp_update` object at all — verified above, both via the `pg_trigger` ordering query and
via the rejected-write-leaves-timestamp-untouched behavior. This satisfies AC4's substance through a purely
additive path; the departure from the design doc's illustrative name is the right call given this round's
explicit live-object caution, not a shortcut.

**BUG-008 filed — new, moderate, both new SQL files (not the pre-existing `tunables_stamp_update`).**
Neither `sql/tunables_validate_trigger.sql` nor `sql/holdings_currency_derivation.sql` re-applies cleanly:
each file's `create trigger ...` statement (no `or replace`, no `drop ... if exists` guard) errors with
`trigger "..." for relation "..." already exists` on a second apply, while the `create or replace function`
statements in the same files are fine. Reproduced on a clean local Postgres 16: apply once (succeeds) →
apply again verbatim (function objects succeed, both `create trigger` statements fail). Confirmed Postgres
16 supports `create or replace trigger` (`select`-free smoke test: `create or replace trigger
tunables_0_validate_update before update on public.tunables for each row execute function
public._validate_tunable_update();` → `CREATE TRIGGER`, no error) — so this is a one-line-per-file fix, not
a structural problem. `docs/runbook.md:198` states migrations/corrective scripts should "be idempotent
(e.g., `DROP TABLE IF EXISTS`, `CREATE OR REPLACE FUNCTION`, etc.)" — these two new files meet that bar for
every statement except their one `CREATE TRIGGER` line each. Full detail in "Open bugs" below.

### Priority three — DEEP-005 / DEEP-006 behavioral closure

**DEEP-005 — closed at the system level, verified via the DB layer (not just `validateTunableValue`'s
return value).** The original findings were: (1) a numeric-key typo reaches `config.py` and kills all three
entry points via `SystemExit` — already independently protected against reaching a live table by the DB
trigger (Priority two above: `DISCOVERY_GAINER_PCT='5%'` is rejected before it is ever written, so it can
never reach `config.py`'s cast at all); pre-existing `test_ac9_direct_double_miss_raises_systemexit_naming_
the_key`/`test_ac12_tier1_cast_failure_fails_loud_never_reaches_cache_write` (`tests/test_tunables.py`)
independently confirm `config.py`'s own fail-loud behavior is unchanged as the second line of defense. (2)
`ALERTS_ENABLED` silently accepting `"yes"`/`"tru"`/`"True "` — confirmed rejected at both layers: the DB
trigger (Priority two) and a new permanent test,
`"validateTunableValue: ALERTS_ENABLED accepts only true/false, case-insensitively"`
(`tests/admin_portal/validation.test.ts`), which asserts DEEP-005's exact repro strings are rejected. (3)
`GEMINI_MODEL_BACKUP`'s blank value — confirmed now accepted at both layers (DB: `UPDATE ... SET
value='' WHERE key='GEMINI_MODEL_BACKUP'` succeeds; client:
`"validateTunableValue: GEMINI_MODEL_BACKUP accepts blank..."`, new test). Also newly locked down: the
`ALERTS_ENABLED` `<select>` itself (`"tunables page: ALERTS_ENABLED renders a <select> with exactly the
true/false options..."`, new static-source test) — previously only dev's self-verified manual read, no
permanent regression test existed for the UI half of AC1 until this pass.

**DEEP-006 — closed, including the "stale pre-trigger row" case explicitly asked about.** New
`tests/test_state.py` tests confirm `build_position`'s mismatch guard suppresses `pl_pct` (not a wrong
number) on a currency disagreement, logs a `WARNING` naming the ticker and both currencies, computes
normally when currencies agree, and — DEEP-006's own stated "unknown ≠ disagrees" rule — still computes
`pl_pct` when `fundamentals.currency` is missing entirely (covers both a genuine unknown-currency ticker
and a pre-existing holdings row the DB trigger hasn't re-derived, since the guard reads whatever `currency`
value it's handed at call time and has no dependency on the DB trigger's write history). Independently
confirmed wired into the real entry point, not just unit-tested in isolation: drove `run_hourly.main()`
end-to-end (scratch script, `FakeSupabase`/`FakeNotifier` doubles per `tests/test_run_orchestration.py`'s
own convention) with a `SHOP.TO` holding at `currency="USD"` against a mocked `fundamentals.currency="CAD"`
— the `[state] WARNING holding currency mismatch for SHOP.TO...` line fired from inside the real
`run_hourly.py` → `state.build_position` call site, confirming the guard is live in the shipped pipeline,
not dead code only reachable from a test file. The DB trigger's INSERT/UPDATE-only firing (a pre-existing
row keeps its old currency until next written) is accurately noted by dev as a known limitation, not a bug
— **and is exactly the case this Python-layer guard covers independently of the trigger**, confirmed above.

### REV-109 — closed

Added `tests/test_prefilter.py::test_find_candidates_returns_no_duplicate_tickers_even_with_overlapping_
screens` (the `region="na"` path, maximal cross-screen symbol overlap) and
`test_find_candidates_dedup_also_holds_for_india_region` (the separate `region="in"` branch). Both assert
`find_candidates()`'s returned candidate list has no duplicate `ticker`, confirm `funnel["after_dedup"]`
reflects unique-symbol count (not raw overlap count), and confirm real overlap was actually exercised
(`funnel["raw"] > funnel["after_dedup"]`, `attempted > 1`) so the test can't pass vacuously. This is the
regression lock BUG-006/BUG-007's deferral rested on with nothing protecting it before this pass.

### Regression suite

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **249 passed, 0 failed** (244 baseline + 5
  new: 3 `build_position` currency-guard tests, 2 `find_candidates` dedup tests). Zero regressions.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **80 passed, 0 failed** (62
  baseline after dev's flagged deletion + 18 new: 8 in `validation.test.ts` — `MARKET_CURRENCY` mapping
  plus 7 `validateTunableValue` per-key rule tests — 5 in `tunables_static.test.ts` — ALERTS_ENABLED-is-a-
  select, handleUpdate-passes-key, and 3 `tunables_validate_trigger.sql` static checks — and 5 in
  `static_source_checks.test.ts` — holdings-page currency-removal/derivation static checks). Zero
  regressions; confirms dev's reported 62 was correct and that the one deletion's gap is now closed.
- `cd admin-portal && npm run build` → succeeds, all 7 routes compile (`/`, `/_not-found`, `/auth/callback`,
  `/holdings`, `/login`, `/track-record`, `/tunables`, `/watchlist`).
- `cd admin-portal && npm run lint` → zero errors/warnings.
- Shippability: both Python entry points (`run_hourly.py`, `run_discovery.py`, `publish_prices.py`) import
  cleanly end-to-end (`SKIP_TUNABLES_FETCH=true`); `run_hourly.main()` driven live against the real
  `state.build_position` call site (Priority three, DEEP-006) confirms the fix is reachable from the real
  pipeline entry point, not just from a unit test.

### Verdict — INC-10

**PASS, with one bug filed (BUG-008, moderate, not a merge blocker — see rationale below).**

- AC1–AC8 (`docs/design/increment-plan.md` `### INC-10`) all independently re-verified true, not accepted
  on dev's account: AC1 (select UI + per-key client rejection, now permanently tested), AC2
  (`GEMINI_MODEL_BACKUP` blank accepted, both layers), AC3 (DB trigger rejects all 10 keys' bad values,
  naming the key), AC4 (validate-before-stamp firing order + no partial side effect on rejection), AC5/AC6
  (holdings currency derived per market, overridden even against an actively-wrong direct-SQL currency),
  AC7 (`build_position` mismatch guard, `pl_pct is None` + logged warning), AC8 (full suite green, `git
  diff` scope confirmed as exactly the files dev's handoff lists).
- DEEP-005 and DEEP-006 are both **behaviourally closed** — see Priority three above; not merely "code
  changed," the system-level consequences (typo can't reach a live tunable; `.TO`/`.NS` holdings can't
  carry a wrong currency, including the pre-existing-row edge case) are independently verified and now
  permanently regression-tested.
- REV-109 **closed** — `find_candidates()`'s duplicate-free guarantee is now locked by a permanent test in
  both region branches.
- **BUG-008 is not treated as a merge blocker for INC-10**: it is a re-apply-time defect (the file has
  never been applied to the live project yet — dev's handoff and this run both confirm that — so no live
  object has ever been created by a first, successful apply that a second apply could conflict with) with
  a trivial fix, not a behavioral defect in either trigger's logic (every behavioral AC above passed on a
  clean, single apply). Routed back to dev per the normal bug-fix-cycle process rather than blocking
  reviewer/merge, since release/INC-11 has not yet applied either file live.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — INC-10 touched
no `ai_judge.py` code. Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry
(repro: `tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_
undocumented_elsewhere`). **Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return
contract, if ever addressed).

**BUG-008 — `sql/tunables_validate_trigger.sql` and `sql/holdings_currency_derivation.sql` do not re-apply
cleanly (not idempotent) — moderate — INC-10, filed this pass.**

**Where:** both new files' final statement — `sql/tunables_validate_trigger.sql:84-86` (`create trigger
tunables_0_validate_update before update on public.tunables ...`) and
`sql/holdings_currency_derivation.sql:46-48` (`create trigger holdings_derive_currency before insert or
update on public.holdings ...`). Both use plain `create trigger` (no `or replace`, no preceding `drop
trigger if exists`); the `create or replace function` statements earlier in the same files are fine.

**Repro:** on a clean local Postgres 16 with `sql/admin_portal_tunables.sql` (and an equivalent
`watchlist`/`holdings` schema) already applied, apply either new file once (succeeds), then apply the exact
same file again, verbatim:
```
psql -f sql/tunables_validate_trigger.sql
-- 1st run: CREATE FUNCTION / CREATE TRIGGER
-- 2nd run: CREATE FUNCTION / ERROR: trigger "tunables_0_validate_update" for relation "tunables" already exists
```
Same failure mode for `sql/holdings_currency_derivation.sql`'s `holdings_derive_currency` trigger.

**Expected:** per `docs/runbook.md:198` ("Ensure the corrective script is idempotent (e.g., `DROP TABLE IF
EXISTS`, `CREATE OR REPLACE FUNCTION`, etc.)") and this round's explicit live-SQL-safety framing, a
migration file going into a live project should tolerate a re-apply without erroring.

**Actual:** a second apply of either file errors out on its `CREATE TRIGGER` statement (transaction/session
aborts at that point in a multi-statement `-f` run).

**Suggested fix (not prescribed, dev's/tech-lead's call):** `create or replace trigger ...` — confirmed
supported by Postgres 16 (`create or replace trigger tunables_0_validate_update before update on
public.tunables for each row execute function public._validate_tunable_update();` → `CREATE TRIGGER`, no
error, on the same scratch instance used for this bug's repro) — a one-line change per file, no behavioral
impact (verified: every AC-level scenario in this run's Priority two section was re-confirmed passing after
manually re-testing with `create or replace trigger` substituted in).

**Severity/why not a merge blocker:** moderate, not blocking — see "Verdict" above. Neither file has been
applied to the live project yet (both are still pending release/INC-11's first apply per dev's handoff), so
there is no live re-apply scenario this defect could trigger today; it would surface only if release ever
needs to re-run either file (e.g. a troubleshooting re-apply, or a future `supabase db push`-style
mechanism that replays all migration files). Does not affect any of INC-10's behavioral ACs, all of which
were independently verified on a single clean apply (Priority two above).

**Owner:** dev.
