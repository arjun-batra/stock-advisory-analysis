# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs. INC-9's original run (initial ACs 1-6 + BUG-005 filing) is
archived there; this entry covers BUG-005's fix-cycle-1 re-test only.

---

## INC-9 — BUG-005 fix-cycle-1 re-test (`_parse_batch`'s unambiguity guard) — 2026-07-30

**Scope.** `scripts/ai_judge.py` (`_parse_batch` only — `git diff --stat 14faba9..HEAD -- scripts/ tests/`
confirms zero diff; working tree matches the fix commit exactly). Read against dev's fix-cycle-1 handoff
entry (`docs/handoff.md`, "BUG-005 fix (fix cycle 1 of 3)"), the current `_parse_batch` code, this file's
own prior BUG-005 entry (now archived), and `docs/design/components.md` §4.4a — noting §4.4a's pseudocode
still shows the unconditional (pre-guard) normalized match and has not yet been updated by tech-lead to
reflect dev's unambiguity-guard departure; not treated as authoritative where it conflicts with the fix,
not edited here.

### 1. Dev's rejection of qa's suggested alternative — evaluated on the merits, dev is correct

Dev rejected qa's originally-suggested fix ("require an exact match whenever the candidate carries an
explicit `ticker` field, reserving normalization for the no-field case only") on the grounds that it would
reject the legitimate bare-`"ABC"`-answers-`"ABC.TO"` case §4.4a exists to serve, not just the collision.
Verified independently with a concrete case: single-ticker batch requesting `["ABC.TO"]`, model replies
`[{"ticker": "ABC", ...}]` — the candidate DOES carry an explicit `ticker` field (`"ABC"`, just without the
suffix), so qa's alternative's "require exact match whenever a `ticker` field is present" test would compare
`"ABC" != "ABC.TO"` and reject it, sending a legitimate, unambiguous answer to fail-safe. Confirmed by
running `_parse_batch` directly (see `test_parse_batch_single_ticker_batch_bare_normalized_match_still_resolves`)
that the shipped fix correctly resolves this case, which qa's alternative would have broken. **Dev's
reasoning holds; the rejection was correct, not a rationalization.**

### 2. BUG-005's own test — verified by behaviour, not just green

`tests/test_ai_judge.py::test_parse_batch_normalize_ticker_suffix_stripping_must_not_collide_cross_market`
passes on the current code. Independently confirmed this is a genuine fix, not the test being made to pass:
swapped `scripts/ai_judge.py` for the pre-fix `d006eb2` content (`git show d006eb2:scripts/ai_judge.py`),
reran the same test — **fails** with the exact BUG-005 symptom (`ABC.NS` resolves `parse_status="ok"` by
borrowing `ABC.TO`'s rationale, `AssertionError: ... assert 'ok' == 'failed'`), then restored the working
tree (confirmed clean via `git diff --stat`). The fix discriminates old-vs-new behavior correctly.

### 3. Legitimate paths independently confirmed

- No-label positional fallback (dev's claim, INC-9's own original scenario) —
  `test_parse_batch_legitimate_fallback_missing_ticker_label_still_resolves` (pre-existing) still passes;
  independently re-verified via direct `_parse_batch` call, unaffected by the new guard.
- Unambiguous bare-ticker normalized match, single-ticker batch (dev's claim) — new
  `test_parse_batch_single_ticker_batch_bare_normalized_match_still_resolves`: `["ABC.TO"]` answered with
  bare `"ABC"` resolves `parse_status="ok"`, fallback log line fires. **Confirmed independently, not taken
  on dev's word.**

### 4. Edge probes on the guard's own new behavior

Four scenarios probed per the brief, each written as a permanent test in `tests/test_ai_judge.py`:

| Probe | Result | Verdict |
|---|---|---|
| Well-formed response, ambiguous pair (`ABC.TO`/`ABC.NS`) present but both objects fully labeled — fallback never needed | Both resolve via direct label, zero fallback log lines fire | **Correct** — guard does not misfire on a case that never needed rescuing (`test_parse_batch_wellformed_response_with_ambiguous_pair_present_is_unaffected`) |
| Single-ticker batch, unambiguous bare match | Resolves correctly (§3 above) | **Correct** |
| 3+ symbols sharing a base (`ABC.TO`/`ABC.NS`/`ABC`), genuine collision — one candidate carries an explicit normalizing-not-exact `ticker` field | The two direct-labeled tickers (`ABC.TO`, `ABC`) resolve correctly; `ABC.NS` (no object of its own, ambiguous normalized candidate, `normalized_counts["ABC"]==3`) correctly fails safe | **Correct** (`test_parse_batch_three_way_base_symbol_collision_normalized_candidate_fails_safe`) |
| **Same ticker requested twice in one batch** (`["AAPL","ABC.TO","ABC.TO"]`) | The second occurrence's legitimate bare-`"ABC"` normalized match is wrongly rejected as "ambiguous" (`normalized_counts["ABC"]==2`, counting the SAME requested ticker's own duplicate, not a distinct colliding ticker) — and because `out` is keyed by ticker string, this rejection **overwrites** the first occurrence's already-correctly-resolved entry, so the final `out["ABC.TO"]` is a fail-safe Hold despite two independently legitimate answers being available | **Misbehaves — filed as BUG-006, new, not a variation of BUG-005** (`test_parse_batch_duplicate_ticker_in_requested_batch_drops_legitimate_second_match`, currently failing, documenting the defect) |

### 5. Regression suite

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **240 passed, 1 failed** (237 baseline + 4
  new tests: 3 pass [well-formed-unaffected, single-ticker-bare-match, three-way-collision], 1 fails
  documenting BUG-006). Zero regressions — the 237 baseline tests all still pass unchanged.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **63 passed, 0 failed**, matching
  the recorded baseline exactly (zero `admin-portal/` files touched by this fix cycle).
- `git diff --stat 14faba9..HEAD -- scripts/` → empty (dev's fix commit is the exact current state, no
  further code drift since qa's baseline).

### Verdict — INC-9 BUG-005 fix-cycle-1 re-test

**Bugs filed: BUG-006 (new). BUG-005 is CLOSED.**

- **BUG-005 — RESOLVED 2026-07-30.** The `_normalize_ticker` cross-market collision is genuinely fixed:
  the repro test passes on current code and is independently confirmed to fail on pre-fix code (§2); the
  fix's unambiguity guard does not regress either legitimate path dev claimed (§3, independently verified);
  dev's rejection of qa's suggested alternative fix is correct on the merits (§1).
- **BUG-006 filed (new, minor-to-moderate — miss-direction, not fabrication-direction)** — see "Open bugs"
  below.
- Python suite: 240 passed / 1 failed (BUG-006's own documenting test; zero regressions against the 237
  baseline). TypeScript suite: 63 passed / 0 failed, unaffected.
- Fix-cycle count: **1 of 3 used** for BUG-005 (now closed, so no further cycles needed on it). BUG-006 is
  a fresh bug, its own fix-cycle count starts at 0.

---

## Open bugs

**BUG-006 — `_parse_batch`'s BUG-005 unambiguity guard conflates a duplicated ticker *request* with a
genuine cross-ticker collision, dropping a legitimate second-occurrence match — minor/moderate — INC-9,
BUG-005 fix-cycle-1 residual, found via edge-probe, not a variation of BUG-005 itself.**

**Where:** `scripts/ai_judge.py`, `_parse_batch`'s `normalized_counts = Counter(_normalize_ticker(x) for x
in tickers)` (the guard added in BUG-005's fix) plus the pre-existing `out[t] = ...` dict-keyed-by-ticker
assignment.

**Repro (`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_in_requested_batch_drops_legitimate_second_match`):**
request `["AAPL", "ABC.TO", "ABC.TO"]` (the SAME ticker requested twice — not two different tickers sharing
a base); model response: `AAPL` directly labeled, index 1 unlabeled (`{"verdict":"Sell", "rationale":
"first-ABC.TO-unlabeled", ...}`), index 2 labeled `{"ticker":"ABC", "rationale":
"second-ABC.TO-bare-answer", ...}`. `AAPL` resolves normally. The first `ABC.TO` occurrence (index 1)
legitimately resolves via the no-ticker-field fallback (`parse_status="ok"`, `rationale="first-ABC.TO-unlabeled"`).
The second `ABC.TO` occurrence (index 2) tries the fallback too: its candidate carries an explicit
`ticker="ABC"` field that normalizes to `"ABC"`, matching what's being resolved — but `normalized_counts["ABC"]`
is `2`, purely because `"ABC.TO"` appears twice in the *requested* `tickers` list (not because two distinct
tickers collide), so the guard's `== 1` unambiguity test fails and this candidate is rejected as
"ambiguous." Because `out` is a plain dict keyed by ticker string, the second occurrence's fail-safe result
**overwrites** the first occurrence's already-correct entry.

**Expected:** a ticker requested twice in the same batch is not a cross-ticker collision — the guard's
ambiguity concept should only apply across *distinct* normalized forms, not an artifact of the same ticker
appearing more than once in the request list. At minimum, neither occurrence should regress relative to
what a single request for that ticker would have resolved to.

**Actual:** the final `out["ABC.TO"]` is a fail-safe Hold (`parse_status="failed"`), discarding a
legitimately resolvable answer that was available at index 1.

**Severity/direction note:** this is a MISS, not a fabrication — no wrong verdict is attributed, the ticker
just fails safe to Hold when a real answer existed. Lower severity than BUG-005 (which was a fabrication
risk), filed as minor/moderate rather than major. Production reachability is narrow but not provably zero:
`scripts/sql/schema.sql`'s `watchlist.ticker` is a `text primary key` (duplicate watchlist entries are
DB-impossible), but `_parse_batch`'s `tickers` argument is whatever `judge_batch` is called with, and
discovery-candidate batches (`prefilter.py`'s screener results) are not proven duplicate-free by any
constraint checked this session — flagging as a real, if narrow, edge case worth closing rather than a
theoretical one.

**Not in scope for this bug:** the underlying "duplicate ticker in a batch overwrites in `out`" dict-keying
behavior predates BUG-005's guard and is not itself being re-litigated here — only the guard's
new interaction with it (turning a previously-any-answer-survives overwrite into a fail-safe-survives
overwrite) is what's newly reported.

**Owner:** dev (with tech-lead recording any resulting `components.md` §4.4a wording update alongside the
BUG-005 guard note it's already carrying).
