# Handoff — INC-2: Shared Wallet-Sim Evaluation Harness (FR31)

Source: `docs/design.md` §17 (Shared wallet-sim evaluation harness, FR31) + §14 increment plan (INC-2
row) + §0 load-bearing #11 (mutual isolation, read-only harness). `docs/requirements.md` §10.2 (FR31).
Read first per the task brief: `docs/handoff.md` (INC-1), `scripts/run_shadow.py`,
`scripts/run_shadow_nse.py`, `scripts/state.py`, `docs/review-log.md` (REV-015, REV-018 — both
out of INC-2 scope, noted not touched).

## Files created
- `scripts/wallet_sim.py` — pure, zero-I/O module. `walk(rows, *, mark_price=None)` is the **single
  shared** Buy->holding / Sell->flat / Hold->no-op state machine, replacing the two byte-for-byte-identical
  inline `_derive_shadow_positions` copies. Input: one ticker's history ordered oldest->newest, each row
  `{"verdict", "timestamp", "price"}`. Output: `{"position", "round_trips", "open"}` — `position` is exactly
  what the live orchestrators need (state/entry_price/entry_date); `round_trips` and `open` (marked to
  `mark_price` when supplied) are the evaluation-only additions design §17.2 asked for. No Supabase/network
  calls anywhere in the file.
- `scripts/eval_shadow.py` — thin, read-only CLI entry point (design §17.1/§17.3). `--track {us_ca,nse}`
  selects `call_log_shadow` / `call_log_shadow_nse`; `--since`/`--until` (ISO date or datetime) override the
  default `EVAL_WINDOW_DAYS`-day window; `--output PATH` optionally also writes the report as JSON
  (`sort_keys=True`, so the file itself is byte-identical across reproducible runs). Split into pure
  compute functions (`build_report`, `render_report`, `default_window`, `parse_window_bound`,
  `_verdict_counts`) and I/O functions (`fetch_shadow_rows`, `fetch_production_rows`, `main`) so qa can
  unit-test the report logic without a DB double at all, and integration-test the I/O seam with a fake
  Supabase double (same pattern as `tests/test_run_shadow_nse.py`'s `FakeShadowNseSupabase`/
  `FakeCallLogSupabase`). Per ticker and in the totals: verdict counts, closed round-trip count, wins,
  win rate, summed realized return %, and (if still open) the position marked to its latest snapshot price
  with unrealized return %. Production baseline pulled from `call_log` for the same tickers/window:
  verdict counts + `alerted` count (the verdict-change record).

## Files changed
- `scripts/run_shadow.py` / `scripts/run_shadow_nse.py` — `_derive_shadow_positions` in both files now
  builds the ordered `{"verdict", "timestamp", "price"}` row list from the same Supabase query as before
  and calls `wallet_sim.walk(walk_rows)["position"]` instead of running its own inline loop. The Supabase
  query itself, the table/column selection, and the returned `{ticker: {"state", "entry_price",
  "entry_date"}}` shape are all **unchanged** — only the state-machine body moved into `wallet_sim.walk`.
- `scripts/config.py` — added `EVAL_WINDOW_DAYS` (default `14`, env-overridable), read by
  `eval_shadow.default_window`.

## How the refactor preserves behavior (verified, not assumed)
1. **Line-by-line equivalence.** `wallet_sim.walk`'s loop is the same three-branch logic
   (`Buy and flat -> holding`, `Sell and holding -> flat`, else no-op) as the two inline versions it
   replaces, just reading `price`/`timestamp` from a flattened row instead of `data_snapshot.get("price")`/
   `r.get("timestamp")` inline — the flattening happens in the caller (`_derive_shadow_positions`) before
   the call, so the *inputs* `wallet_sim.walk` sees are identical to what the old inline loop read.
2. **Existing test suite passes unchanged.** `tests/test_run_shadow_nse.py`'s wallet-walk tests
   (`test_nse_wallet_walk_buy_flips_flat_to_holding`, `..._sell_flips_holding_to_flat`, `..._hold_is_a_no_op`,
   `..._empty_history_is_flat`, `..._covers_only_requested_tickers_independently`,
   `..._reads_only_call_log_shadow_nse_never_call_log_or_call_log_shadow`) all call
   `run_shadow_nse._derive_shadow_positions(sb, tickers)` — the public function signature and return shape
   are untouched, so these tests exercise the new `wallet_sim.walk`-backed implementation without any
   change and all pass. Full suite: **209 passed, 0 failed** (`python3 -m pytest tests/ -q`), no regressions
   vs. before the refactor.
3. **Manual equivalence check.** Ran both the old inline logic (from git history) and the new
   `wallet_sim.walk`-backed `_derive_shadow_positions` against the same synthetic Buy/Sell/Hold histories
   (including Buy-while-holding and Sell-while-flat no-ops) and confirmed identical `{state, entry_price,
   entry_date}` output.

## How to run `eval_shadow.py`
```
GEMINI_API_KEY=... SUPABASE_URL=... SUPABASE_SECRET_KEY=... \
  python3 scripts/eval_shadow.py --track us_ca
python3 scripts/eval_shadow.py --track nse --since 2026-07-01 --until 2026-07-14
python3 scripts/eval_shadow.py --track us_ca --output report.json
```
`--track` is required (`us_ca` or `nse`); `--since`/`--until` default to the last `EVAL_WINDOW_DAYS` (14)
days ending now. Prints a deterministic report to stdout; `--output` additionally writes the same data as
sorted-keys JSON. `GEMINI_API_KEY` is required only because `config.require_secrets()` is a shared
fail-fast gate across all three secrets — this script never calls Gemini.

## Read-only guarantee (verified)
`grep -n "\.insert(\|\.update(\|\.upsert(\|\.delete(" scripts/eval_shadow.py scripts/wallet_sim.py` matches
only the docstring's own prose (`No .insert(/.update(/.upsert(/.delete( calls...`), not a real call. All
Supabase access in `eval_shadow.py` is `.select(...).eq(...).gte(...).lte(...).order(...).execute()` reads
via `state.client()`. `wallet_sim.py` makes no Supabase/network calls at all.

## What qa should focus on
- **Reproducibility (FR31's acceptance bar):** two `build_report(...)` calls over the same shadow/production
  row lists produce byte-identical dicts (verified manually — see smoke tests below — but qa should own the
  committed test). `render_report`/JSON output must not depend on dict/set iteration order (verdict counts
  use a fixed `("Buy","Sell","Hold")` tuple; tickers/per_ticker keys are sorted).
- **`wallet_sim.walk` unit tests**: Buy/Sell/Hold no-op rules, empty input, Buy-while-holding and
  Sell-while-flat no-ops, `None` prices (a Sell with no price yields `return_pct: None`, not a crash), the
  `mark_price` open-position marking path, division-by-zero guard when `entry_price` is `0`, and the
  round-trip list's `entry_price`/`entry_date`/`exit_price`/`exit_date`/`return_pct` shape.
- **`eval_shadow.py`'s read-only guarantee** — worth a standing regression test grepping for
  insert/update/upsert/delete, since this is the hard design requirement (§17.3).
- **CLI argument parsing**: `--since`/`--until` accepting bare dates vs. full ISO datetimes;
  `--track` rejecting values outside `{us_ca, nse}` (argparse `choices` already enforces this — confirm the
  error path).
- The refactored `_derive_shadow_positions` in both `run_shadow.py`/`run_shadow_nse.py` — confirm no
  behavior change against the pre-refactor tests (already covered by the existing NSE suite; consider
  adding an equivalent test file for `run_shadow.py` if none exists — `tests/test_run_shadow_nse.py`'s
  `test_run_shadow_main_us_ca_track_has_the_same_systemexit_gap` test currently imports `run_shadow` but
  there's no dedicated `tests/test_run_shadow.py`).

## Deviations from design.md §17 (and why)
- **Row/price shape for `wallet_sim.walk`.** Design describes the function's *intent*
  ("`wallet_sim.walk(rows)` operating on ordered rows") but not a literal signature. I chose plain
  `{"verdict", "timestamp", "price"}` dicts (price already extracted from `data_snapshot`) rather than
  passing raw `call_log`/`call_log_shadow` rows with nested `data_snapshot`, so `wallet_sim.py` stays
  schema-agnostic and doesn't need to know about `data_snapshot`'s shape at all — the callers (both
  orchestrators and `eval_shadow.py`) do that one-line flattening themselves. This is a design *choice*
  within the stated intent, not a deviation from a hard requirement.
- **A versioned SQL view (§17.1, "MAY additionally be committed").** Not built — explicitly optional in
  the design ("the Python harness is the source of truth"), and the Python harness alone satisfies FR31.
  Flagging so it isn't mistaken for an oversight.
- **No committed CSV/JSON output by default.** `--output` is opt-in per the task brief's "use your
  judgement" on this being optional; default behavior is stdout-only, matching §17.3's baseline requirement.

## Smoke tests performed
- Installed `requirements.txt` + `pytest` + `pyyaml` in a clean venv; `wallet_sim`, `eval_shadow`,
  `run_shadow`, `run_shadow_nse`, `config`, `state`, `shadow` all import cleanly.
- `grep` confirmed no `.insert(`/`.update(`/`.upsert(`/`.delete(` calls in `eval_shadow.py` or
  `wallet_sim.py` (only the docstring's own prose mentions the strings).
- Built a fake Supabase double (same shape as `tests/test_run_shadow_nse.py`'s fakes) with synthetic
  `call_log_shadow` + `call_log` rows spanning a Buy->Hold->Sell round trip (AAPL) and an open Buy (MSFT);
  called `fetch_shadow_rows`/`fetch_production_rows`/`build_report`/`render_report` directly and confirmed
  correct round-trip P&L, win rate, and open-position marking, and that two `build_report` calls on the
  same input produce an identical dict (`report1 == report2`).
- Ran `eval_shadow.main()` end-to-end with `state.client` monkeypatched to a fake Supabase double serving
  NSE data via `--track nse --output ...` and confirmed a correct printed report plus a valid, deterministic
  sorted-keys JSON file.
- `python3 -m pytest tests/ -q` from repo root: **209 passed, 0 failed** — full regression suite,
  confirming the `run_shadow.py`/`run_shadow_nse.py` wallet-walk refactor changed no observable behavior.

## Known limitations
- No dedicated `tests/test_run_shadow.py` exists yet (only `tests/test_run_shadow_nse.py`, which also
  imports and exercises a couple of `run_shadow` behaviors) — qa's call whether to add one, e.g. to unit-test
  `run_shadow._derive_shadow_positions` directly the way the NSE suite does for its counterpart.
- `eval_shadow.py`'s production-baseline query scopes `call_log` to exactly the tickers present in the
  shadow-table rows for the window (not the full watchlist) — a ticker with shadow rows but zero production
  rows in the window (e.g. a cycle gap) will show `checks=0` on the production side for that ticker; this is
  intentional (comparing like-for-like), not a bug, but worth qa calling out explicitly if it's surprising.
- REV-015 (hardcoded `timeout-minutes` on the shadow workflow steps) and REV-018 (the pre-existing
  `run_shadow.py` `except Exception` / `SystemExit` gap) are unrelated to INC-2 and were not touched — both
  remain open items routed to tech-lead per the prior handoff.

## Addendum: REV-018 fix (2026-07-15)

- **File changed:** `scripts/run_shadow.py` only.
- **Fix:** widened `main()`'s `except Exception` to `except (Exception, SystemExit)` (with the same
  explanatory comment already present in `run_shadow_nse.py`'s `main()`), so a `SystemExit` raised by
  `config.require_secrets()` on a missing secret is now caught and swallowed instead of propagating out of
  `main()` — restoring the "main() always exits 0" isolation guarantee for the US/CA shadow track, matching
  the fix already applied to `run_shadow_nse.py` during INC-1. Resolves **REV-018**.
- **Verification:** `python3 -m pytest tests/ -q` — 273 passed, 1 failed. The 1 failure is
  `tests/test_run_shadow_nse.py::test_run_shadow_main_us_ca_track_has_the_same_systemexit_gap`, which was
  written to *confirm the bug's existence* (`pytest.raises(SystemExit)` around `run_shadow.main()`); now that
  the bug is fixed, that assertion is stale/inverted by design — the test's own docstring says it documents a
  bug that was "out of INC-1 scope to fix." No other test touches this path. Not fixed here since `tests/` is
  qa's territory, not dev's — flagging for qa to retire or invert this test now that REV-018 is resolved.
