# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## C901 complexity-refactor verification — `ai_judge._parse_batch` / `run_discovery.main` — 2026-07-31

**Scope.** Commit `0a24460` ("fix: reduce cyclomatic complexity of `_parse_batch` and `run_discovery.main`
(C901)") — a pure structural refactor with no intended behaviour change, prompted by
`.github/workflows/audit.yml`'s second `ruff check --select C90 .` invocation being red on `main` (local
checks had only ever run the first, unqualified `ruff check .`). Read `docs/handoff.md`'s commit-adjacent
context, `scripts/ai_judge.py`/`scripts/run_discovery.py` as they now stand, `docs/review-log.md`'s
DEEP-003/BUG-005/BUG-006 write-ups (Pass 25, `docs/archive/review-log-archive.md` per the live file's own
archival), and `docs/test-report.md`'s prior run (now archived). `docs/archive/` otherwise not read.

**Mechanical facts taken as given (independently re-confirmed, not re-investigated in depth):** both
`ruff check --select C90 .` and `ruff check .` pass; no file under `tests/` was in the commit's diff. Full
Python suite before any qa change: **281 passed, 0 failed**.

### Behavioural-equivalence findings (the actual ask — exercising code, not reading it)

Diffed `0a24460` line-for-line first: both `_parse_batch` and `run_discovery.main` are **verbatim code
moves** — every extracted helper's body is byte-identical to the block it replaced (including comments,
control flow, and the exact `Counter`/`dict` mutation pattern), with no logic altered. That diff-level
observation was then independently checked by running the guarded behaviours directly against the current
code (not the diff, not existing tests) — five ad hoc probes against `scripts/ai_judge.py` on the current
checkout, plus the existing (untouched) `tests/test_kill_switch_boundary.py`/`tests/test_state.py` suites
re-run to confirm they still exercise the real code paths:

- **Fail-safe path (`parse_status` in `failed`/`api_error`) never advances `current_verdict`/never
  pushes.** `scripts/state.py` is **not in this commit's diff at all** — `process_ticker`'s load-bearing
  guard (state.py:333) is untouched by construction. Confirmed the guard still holds by re-running
  `tests/test_state.py::test_ai_failure_fail_safe_guard_is_untouched_by_delivery_gating` and
  `::test_ai_api_error_fail_safe_guard_is_untouched_by_delivery_gating` (both pass, unmodified files).
- **DEEP-003 misattribution rejection.** Direct probe: request `["A","B","C"]`, model replies
  `[A(labeled,ok), X(labeled 'X', wrong slot), B(labeled 'B', sitting in C's array slot)]`. Result: `A`
  resolves `ok`/Buy; `B` resolves `ok`/Hold via its own label (unaffected by the shift); `C` — no `"C"`
  label anywhere, and the positional candidate at its index is labeled `"B"`, which doesn't match or
  normalize to `"C"` — **fails safe** (`parse_status="failed"`, `verdict="Hold"`), and `B`'s rationale text
  does not appear anywhere in `C`'s result. **PASS.**
- **BUG-005 unambiguity rule.** Two sub-cases against the live `_parse_batch`: (1) genuine cross-market
  collision — requested `["ABC.TO","ABC.NS"]`, model labels one reply `"ABC"` (ambiguous, normalizes to
  both) and the other `"ABC.NS"` (exact label) — `ABC.NS` resolves `ok` via its exact label; `ABC.TO`'s
  only path is the ambiguous normalized positional candidate, which **fails safe**. (2) unambiguous case —
  single-ticker request `["ABC.TO"]`, model replies with a bare `"ABC"` label — resolves `ok`/the reply's
  verdict, since exactly one requested ticker normalizes to `"ABC"`. **Both PASS.**
- **BUG-006 guards.** (1) Duplicate requested ticker `["ABC","ABC"]` with one matching labeled reply
  resolves `ok` (not miscounted as an ambiguity collision — `_normalized_ambiguity` dedupes by distinct
  requested string before counting). (2) Duplicate ticker where the first occurrence resolves `ok` and a
  second array slot carries an unrelated ticker's label: the earlier `ok` is **not clobbered** by the
  would-be later fail-safe. **Both PASS.**
- **INC-12 in `run_discovery`** — `state.py`'s `KillSwitchAbort(BaseException)` declaration is outside
  this commit's diff (confirmed unchanged); `run_discovery.py`'s two `if state.is_paused(sb):` call sites
  (checkpoint 1 in `main()`, checkpoint 2 now inside the extracted `_judge_and_process`) are unchanged in
  count and placement relative to the pre-refactor code, confirmed via
  `tests/test_kill_switch_boundary.py::test_checkpoint_call_site_counts` (still asserts exactly 2, still
  passes) — the regex is indentation/function-agnostic, so it validates the count survived the extraction
  into a helper, not just the presence of the literal call. Re-ran (unmodified)
  `test_checkpoint2_run_discovery_ai_call_abort` and `test_checkpoint3_process_candidate_abort_leaves_
  nothing_logged`: exactly one `kill_switch_abort_log` row, correct `checkpoint`
  (`"ai_call"`/`"push"`), correct `real_rows_this_cycle` (0 in both, the existing zero-prior-outcome
  cases), and `run_heartbeat == {}` (heartbeat write suppressed) in both. **Added new coverage** (below)
  for the previously-untested nonzero-`real_rows_this_cycle` case on discovery's own path, since only
  `run_hourly.py` had that scenario covered pre-refactor.
- **Outcome tallies/ordering (NFR2's degraded formula) unchanged.** `_ingest_candidates` and
  `_judge_and_process` both take `outcomes: Counter` and mutate it in place exactly as the pre-refactor
  inline loop did (confirmed by the verbatim-diff read, then independently by the new mixed-outcome test
  below, which exercises both extracted functions against the same `Counter` instance across a 4-candidate
  batch and asserts the exact resulting tally).

### New test coverage added this pass

- **`tests/test_ai_judge.py`** — five new direct unit tests against `ai_judge._positional_candidate`
  (`test_positional_candidate_rejects_length_mismatch`,
  `test_positional_candidate_accepts_unlabeled_object_in_request_order`,
  `test_positional_candidate_rejects_a_different_labeled_ticker_at_the_same_index`,
  `test_positional_candidate_accepts_unambiguous_normalized_match`,
  `test_positional_candidate_rejects_ambiguous_normalized_match`). This helper is where DEEP-003 and
  BUG-005 both live entirely; it was previously only reachable indirectly through `_parse_batch`'s full
  body. Pins the rule's exact boundary independent of the surrounding array/dict-building plumbing.
- **`tests/test_kill_switch_boundary.py`** —
  `test_checkpoint3_discovery_mixed_outcomes_before_abort_real_rows_counts_and_orders_correctly`: four
  discovery candidates (an ingest-skip, an AI fail-safe/`no-read`, an ordinary `candidate-logged`, then a
  Buy that aborts at its own checkpoint 3) in one `run_discovery.main()` call. Asserts `real_rows_this_
  cycle == 2` (the skip doesn't count, the no-read and logged outcomes do — matching the same causal-tie
  boundary `run_hourly.py`'s equivalent test already covered), exactly one abort row with
  `checkpoint="push"`, no heartbeat row, and the right three `call_log` rows present (skip-with-log still
  fires per FR15; the aborted candidate leaves nothing). Closes the one real coverage gap the refactor's
  own diff surfaced: discovery's extracted `_ingest_candidates`/`_judge_and_process` pair sharing one
  `Counter` across two function calls had no test with more than one real outcome before an abort;
  `run_hourly.py` had that case, discovery didn't.

### Decomposition judgment — genuine seams, not linter-shuffling

Both extractions are **verbatim code moves**, confirmed by reading `git show 0a24460` in full: every line
inside each new helper is character-identical to the block it replaced, including every existing comment.
Nothing was reordered, merged, or short-circuited to dodge the counter.

- **`ai_judge._parse_batch` → `_extract_array`, `_index_by_ticker`, `_normalized_ambiguity`,
  `_positional_candidate`, `_build_result`, `_store_result`.** Each has one concern with a name that
  matches it: JSON-shape tolerance, label-indexing (with the duplicate-label log line staying attached to
  its own step), ambiguity counting, the DEEP-003/BUG-005 corroboration gate, result construction, and the
  BUG-006 clobber guard. `_positional_candidate` in particular is now independently testable with a
  four-line fixture instead of needing a full fabricated model reply and requested-ticker list threaded
  through `_parse_batch`'s entire body — the five new direct tests above took minutes to write specifically
  because the seam is real. **Genuine.**
- **`run_discovery.main` → `_resolve_region`, `_report_empty_candidates`, `_ingest_candidates`,
  `_judge_and_process`, `_handle_kill_switch_abort`.** Each is a distinct phase of the pipeline (region
  resolution, the empty-candidate branch, the ingest phase, the judge+per-candidate-process phase carrying
  its own checkpoint, the abort handler) — the same shape `run_hourly.py`'s pre-existing
  `_process_group`/`_sessions` split already established, so this brings `run_discovery.py` in line with a
  pattern the codebase already uses elsewhere, not a one-off. The `outcomes: Counter` passed by reference
  through two of the five helpers is the one place a mechanical extraction could have silently changed
  aliasing/ordering; the new mixed-outcome test above exercises exactly that seam end-to-end and found no
  drift. **Genuine.**

Neither decomposition merely relocated an `if` to a different stack frame to make ruff's counter happy —
both reduce the caller's own complexity while keeping each extracted piece's complexity low and its name
descriptive of the one rule it encodes. "Passes C901" was a side effect of doing this correctly, not the
target being gamed.

### `ai_judge.py`'s 466-line length (dev-flagged, out of scope, noted for the record)

Dev flagged this outside the C901 fix's scope rather than making an unauthorized module split. Not
qa's call to make (owner: tech-lead, per `CLAUDE.md`'s file-ownership table) — noted here only so it isn't
lost, not actioned.

### Full regression (after qa's own additions)

- `python3 -m pytest -q --tb=short` → **287 passed, 0 failed** (281 baseline + 6 new: 5 in
  `tests/test_ai_judge.py`, 1 in `tests/test_kill_switch_boundary.py`).
- `ruff check --select C90 .` → clean. `ruff check .` → clean. (Both independently re-run this pass, not
  merely taken on the brief's word.)
- TypeScript suite unaffected (no `admin-portal/` file in this commit's diff) — not re-run, per the
  brief's explicit "already confirmed" instruction (82/0 stands from the prior run).

### Shippability

No entry-point contract changed (`_parse_batch`/`main`'s external signatures and return values are
unchanged — only their internals were decomposed), so the prior run's shippability evidence (real
`run_hourly.main()`/`run_discovery.main()` end-to-end exercise via `tests/test_phase4_closure_e2e.py`,
still in the suite and still passing) continues to hold. This pass's own new tests additionally drive the
real `run_discovery.main()` entry point (not internal helpers) for the mixed-outcome scenario.

### Verdict

**PASS.** 287/0 Python (281 baseline + 6 new), both `ruff` invocations clean, no file under `tests/`
touched by the commit under review. Every guard named in the brief (fail-safe non-advance, DEEP-003
misattribution rejection, BUG-005 unambiguity in both directions, BUG-006 dedup/overwrite, INC-12's
`KillSwitchAbort` propagation/single-abort-row/checkpoint/`real_rows_this_cycle`/heartbeat-suppression, and
outcome-tally/ordering preservation) was independently exercised against the current code, not inferred
from the diff or from dev's claim. No bugs filed. Decomposition judged genuine on both sides. No production
code modified by qa this pass.

---

## Open bugs

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — the C901
refactor is a verbatim move and does not touch this residual's last-write-wins behavior in `_store_result`.
Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
