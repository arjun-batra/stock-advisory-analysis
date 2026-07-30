# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs. INC-9's BUG-005 fix-cycle-1 re-test is archived there; this
entry covers BUG-006's fix-cycle-2 re-test (final cycle used before escalation would apply).

---

## INC-9 — BUG-006 fix-cycle-2 re-test (`_parse_batch`'s counting fix + overwrite guard) — 2026-07-30

**Scope.** `scripts/ai_judge.py` (`_parse_batch` only). `git diff --stat 3693948..HEAD -- scripts/ tests/`
confirmed empty before this run — working tree matched dev's fix-cycle-2 handoff commit (`11f2b96` code,
`3693948` handoff) exactly, zero drift. Read against dev's fix-cycle-2 handoff entry (`docs/handoff.md`,
"BUG-006 fix (fix cycle 2 of 3)"), the current `_parse_batch` code and docstring, `docs/test-report.md`'s
own prior BUG-006 entry (now archived), and `docs/design/components.md` §4.4a.

### 1. §4.4a no-change claim — agree with dev, but flag a doc-drift item

Dev's fix has two parts: (a) `normalized_counts` now built from `{x.upper() for x in tickers}` (dedup)
instead of raw `tickers` occurrences, and (b) a new guard skipping a fail-safe write into `out` when an
`"ok"` entry for that ticker key already exists. Dev asserts neither changes §4.4a's contract.

**Agree, on the merits.** §4.4a's own prose (`docs/design/components.md` lines 266–330) — the "why this is
non-obvious" section, the worked examples, the "second-order judgment" discussion of FR20/cross-market
watchlists — is consistently and exclusively about *distinct, real* tickers colliding on a shared
normalized base (`ABC.TO`/`ABC.NS`, two different companies). It never once contemplates the same ticker
string appearing twice in one `tickers` request list; that is a different failure mode (a duplicate
request, not a second thing to disambiguate) that the contract's prose simply didn't anticipate. Correcting
the count to operate over distinct requested tickers doesn't loosen what counts as ambiguous between two
different real tickers — confirmed independently in §2 below, not taken on dev's word. Part (b), the
overwrite guard, operates one layer below §4.4a entirely: §4.4a governs when a normalized match is
*accepted*; the guard governs what happens to `out`'s dict-keyed storage after acceptance, a `_parse_batch`
implementation detail outside what §4.4a specifies either way.

**Doc-drift flag (not a blocker, not routed to tech-lead as a contract dispute):** §4.4a's own pseudocode
block (`docs/design/components.md` line 289, `Counter(_normalize_ticker(x) for x in tickers)`) still shows
the pre-BUG-006 raw-occurrence count, not dev's dedup fix. This is the second fix cycle running ahead of
the pseudocode (the fix-cycle-1 entry noted the same staleness for the guard itself, since resolved). Since
§4.4a's *prose* already supports dev's reading and no behavioral dispute exists, this is ordinary doc
hygiene (tech-lead's `components.md` line 134/889-ref action item, already on record in the handoff) rather
than a finding requiring escalation.

### 2. Counting fix — genuine cross-market collision still fails safe (highest-stakes assertion)

Verified independently, not accepted on dev's smoke-test word. New
`test_parse_batch_duplicate_alongside_genuine_collision_still_fails_safe` (`tests/test_ai_judge.py`):
batch requests `ABC.TO` twice (duplicate) **plus** `ABC.NS` once (a genuinely distinct ticker colliding on
the same normalized base — BUG-005's own scenario), all in the same call. `distinct_requested = {ABC.TO,
ABC.NS}` so `normalized_counts["ABC"] == 2` for a real reason (two distinct tickers), not an artifact of
the duplicate. Confirmed the second `ABC.TO` occurrence's bare-`"ABC"` candidate still correctly fails safe
as ambiguous — dedup did not over-correct into merging a genuine collision away. Also re-ran the
pre-existing `test_parse_batch_normalize_ticker_suffix_stripping_must_not_collide_cross_market` and
`test_parse_batch_three_way_base_symbol_collision_normalized_candidate_fails_safe` (both BUG-005-era,
unmodified) against the current code — both still pass. **BUG-005's fabrication path remains closed.**

### 3. Overwrite guard — reachability independently confirmed, not dead code

Dev's claim: the guard is independently reachable even with correct counting, when a duplicate ticker's two
occurrences land on different outcomes (one resolves, the other legitimately fails safe). Confirmed via new
`test_parse_batch_overwrite_guard_reachable_independent_of_counting_fix`, using the same batch as §2 above
(a genuine collision, not the fixed counting-bug mechanism, is what makes the second occurrence fail safe)
— `out["ABC.TO"]` correctly retains the first occurrence's `"ok"` result, the log line
(`"keeping the earlier resolved verdict, discarding a later fail-safe"`) fires, and manual `_parse_batch`
probing outside pytest reproduced the identical result. The guard is reachable through a mechanism entirely
separate from the bug it was added to guard alongside — **not dead code.**

### 4. `ok`-over-`ok` scoping decision — agree it's out of this cycle's scope, disagree it should stay unwritten

Dev deliberately left the broader "duplicate ticker resolves to two different legitimate verdicts, later
silently wins" behavior unfixed, citing (a) qa's own BUG-006 report scoped it out as pre-existing, and (b) a
real fix means changing `_parse_batch`'s ticker-keyed return contract, rippling to every caller.

**Agree with the scoping call for this fix cycle** — both reasons hold: the original bug report is explicit
("not itself being re-litigated here"), and a contract change of that shape is a design-level decision, not
a bug-cycle patch. **Disagree that it should stay undocumented.** Reproduced directly: a batch requesting
`ABC.TO` twice, both occurrences resolving `"ok"` via the no-ticker-field fallback with divergent verdicts
(`Buy` then `Sell`) — the second silently wins, with **no log line distinguishing this from an ordinary
single resolution** (only the two routine "positional fallback used" lines; the overwrite guard's log only
fires on the failed-over-ok path, not this one). Locked in as a permanent regression-lock test,
`test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`. Filing as
**BUG-007** below — deferred, not a required fix, but per the task brief's instruction, silent
last-write-wins on divergent verdicts should exist in writing rather than only in code behavior nobody
flagged.

### 5. Regression suite

- `SKIP_TUNABLES_FETCH=true python3 -m pytest -q --tb=short` → **244 passed, 0 failed** (241 baseline + 3
  new tests: cross-market-collision-alongside-duplicate, overwrite-guard-reachability,
  ok-over-ok-lock-in). Zero regressions.
- `node --experimental-strip-types --test tests/admin_portal/*.test.ts` → **63 passed, 0 failed**, matching
  baseline exactly (zero `admin-portal/` files touched by this fix cycle).
- DEEP-004 stale-bar tests (`ingest.py`'s `get_market_data`/`_session_state` work, earlier in INC-9) spot-run
  in isolation (`-k "stale_bar or DEEP004 or deep_004 or session_state"`) → 8 passed, confirming untouched;
  `git show --stat 11f2b96` confirms the fix commit touched only `scripts/ai_judge.py`.
- Shippability: entry-point-adjacent tests (`-k "run_hourly or entry_point or e2e"`) → 6 passed. A full live
  `run_hourly.main()` run is not repeated at this fix-cycle scope (already covered at INC-9's original ACs
  and the DEEP-003 shippability check, archived); full end-to-end re-confirmation is due at closure per the
  pipeline, not per fix cycle.

### Verdict — INC-9 BUG-006 fix-cycle-2 re-test

**PASS. BUG-006 is CLOSED. New finding filed for the record: BUG-007 (deferred, not a blocker).**

- **BUG-006 — RESOLVED 2026-07-30.** Both fix parts verified independently: the counting fix correctly
  narrows to distinct requested tickers without weakening BUG-005's cross-market guard (§2), and the
  overwrite guard is confirmed reachable through a mechanism independent of the counting fix, not dead
  code (§3). Dev's §4.4a no-change claim holds on the merits (§1); a minor pseudocode-staleness item is
  flagged for tech-lead's ordinary doc hygiene, not a contract dispute.
- **BUG-007 filed (new, minor, deferred by design this increment)** — see "Open bugs" below.
- Python suite: 244 passed / 0 failed. TypeScript suite: 63 passed / 0 failed. Zero regressions; DEEP-004
  untouched.
- Fix-cycle count: BUG-006 closed at 2 of 3 cycles used (1 clean re-test cycle, no third cycle needed).

**INC-9 is now clean — no open bugs blocking it. Ready for reviewer.**

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record per explicit instruction, not currently blocking.**

**Where:** `scripts/ai_judge.py`, `_parse_batch`'s `out[t] = result` (final write), specifically the
overwrite guard added in BUG-006's fix only protects the `failed`-over-`ok` direction
(`if result["parse_status"] == "failed" and out.get(t, {}).get("parse_status") == "ok": continue`) — the
`ok`-over-`ok` direction is unguarded and was pre-existing before BUG-005/006 both.

**Repro (`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`):**
request `["ABC.TO", "ABC.TO"]`; model response has two unlabeled objects (no `ticker` field on either, so
neither depends on the ambiguity guard at all) with divergent verdicts — index 0 `Buy`, index 1 `Sell`.
Both occurrences legitimately resolve via the no-ticker-field positional fallback (`parse_status="ok"`
each). The second occurrence's write silently overwrites the first's in `out["ABC.TO"]` — final result is
`Sell`, discarding the `Buy` resolution with no trace beyond the two routine "positional fallback used"
log lines (no divergence-specific warning, unlike the guarded failed-over-ok path which does log).

**Expected:** not prescribed here (a real fix changes `_parse_batch`'s ticker-keyed return contract, a
design-level decision per dev's own scoping note) — flagging only that this silent behavior exists and
should be visible in writing, per the task brief's explicit instruction.

**Actual:** later-occurrence-wins with zero indication in logs or return value that a divergent, equally
legitimate verdict was discarded.

**Severity/direction note:** both verdicts are legitimately resolved (not a fabrication or a fail-safe
miss) — this is a determinism/observability gap, not a correctness violation of the "never fabricate, only
miss" invariant. Lower severity than BUG-006. Reachability is the same narrow-but-not-provably-zero
condition BUG-006 already established (discovery-candidate batches not proven duplicate-free;
`watchlist.ticker` itself is DB-deduplicated).

**Not in scope for a fix this increment** — qa agrees with dev's scoping call to defer (BUG-006's own bug
report explicitly scoped this direction out; a proper fix ripples to every `_parse_batch`/`judge_batch`
caller). Filed so the deferral is on record, not silent.

**Owner:** tech-lead (design-level call on whether/how to change `_parse_batch`'s ticker-keyed return
contract, if ever addressed) — not a dev-fix-cycle bug.
