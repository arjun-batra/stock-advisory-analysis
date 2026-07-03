# Requirements/Design vs. Codebase Review — 2026-07-03

> **Status: IMPLEMENTED (same day).** All six gaps and all improvement opportunities below were
> fixed in the follow-up change set (SD v19; Requirements v5; UI-handoff v4; Supabase migrations
> `latest_call_per_ticker_view` + `monitor_nse_discovery_and_publish_prices`). This document is
> retained as the record of what was found and why each fix took the shape it did. Two follow-up
> observables remain and are tracked in SD §11: the first live close-slot run under the runtime
> grace, and live validation of the new ca/in volume screens.

**Scope:** Requirements v4, SD v18, UI-handoff v3 compared against the full codebase
(`scripts/`, `sql/`, `pages/`, `.github/workflows/`) on `main` at `553a73a`.

**Overall verdict:** the build is a close match to the documented design. The single-rule
alert machine (§6.3) including the fail-safe non-reading guard, cold-start silence, FR23
timestamps on all three surfaces, FR18 topic routing with the non-silent fallback,
discovery's Buy-only push + 7-day dedup + funnel logging, the per-market gates with
per-group batched AI calls, schema-enforced output (v18), dashboard FR19–22 behavior, and
the RLS/concurrency posture all verify against the code. The findings below are the
exceptions, ranked by severity.

---

## Gap 1 — HIGH (confirmed logic bug): the v17 close-boundary fix is incomplete; the final dispatch of every trading day is still dropped, one layer down

**What the docs say.** SD §0 item 9 / §4.1 (v17): pg_cron's sub-second jitter made the
exact-close `*/30` slot's `now()` land just past the close, silently dropping the last
dispatch of every session. Fixed by widening the SQL dispatch gates to close + 5 min
(16:05 ET in `dispatch_watchlist_if_open()`, 15:35 IST in `dispatch_watchlist_nse_if_open()`,
migration `fix_market_close_boundary_jitter`). §4.1 also states: "Python `is_market_open()`
remains as execution-time defense-in-depth — the dispatch gate and the runtime gate now
agree."

**What the code does.** The SQL gates were widened (`sql/phase5_monitoring.sql:223`,
`sql/scheduler_pgcron.sql:132`), but the Python runtime gates were not:
`config.py:133` still has `MARKET_CLOSE = time(16, 0)` and `config.py:151`
`NSE_MARKET_CLOSE = time(15, 30)`, tested with `<=` in `is_market_open()` / `is_nse_open()`.

**Why it still fails.** The exact-close slot now dispatches correctly (~16:00:00.x ET),
but the workflow then has to queue a runner, check out, set up Python, and
`pip install -r requirements.txt` before `run_hourly.main()` executes — realistically
1–3 minutes. By then it is ~16:01–16:03 ET, `is_market_open()` returns `False`,
`open_sessions` is empty, `FORCE_RUN` is false, and the run exits as a no-op
(`run_hourly.py:123`). Identically for NSE at the 15:30 IST slot. So the defect v17 was
written to fix — "silently dropped the last dispatch of every trading day" — still occurs,
just at the Python gate instead of the SQL gate. It is also invisible: a no-op run writes
no heartbeat, and the monitor's watchlist windows end at 16:00 ET / 15:30 IST, so nothing
alerts. The §4.1 sentence that the two gates "agree" is no longer true post-v17.

**Recommended fix.**
1. Mirror the slack in the runtime gates — but size it for what this layer actually
   absorbs: dispatch→execution latency of minutes, not pg_cron's sub-second jitter.
   Suggest close + 10 min (`16:10` ET / `15:40` IST), as a named config value (e.g.
   `RUNTIME_CLOSE_GRACE_MIN`, tunable per the existing threshold pattern). Keep the open
   bounds exact. The next `*/30` slot (16:30 ET / 16:00 IST) is not dispatched by the SQL
   gates at all, so a wider runtime grace admits no post-close run.
2. Update SD §0 item 9 / §4.1 to state both bounds and why they differ.
3. Verify on the next session close via the `[gate]` audit line: the ~16:00 ET dispatch
   should log `open=US/TSX` and process the group.

## Gap 2 — MEDIUM (NFR2): the NSE discovery run is unmonitored

`run_discovery.py:105` writes the same `daily-discovery` heartbeat for both regions, and
`check_pipeline_health()` (`sql/phase5_monitoring.sql:169-184`) only evaluates discovery
after 23:00 UTC against "ran after 21:00 UTC today" — i.e., it validates only the 22:00 UTC
US/TSX run. If the 10:00 UTC `discovery-dispatch-nse` silently stops (the exact
dropped-dispatch failure mode NFR2 exists for), nothing ever alerts; worse, an NSE
heartbeat written at ~10:05 UTC is overwritten by the NA run the same day, so the evidence
disappears. SD §4.8/D4 added an IST window for the *watchlist* only; the requirement (NFR2:
"a run that never triggers must surface as loudly as one that runs and fails") covers
discovery too.

**Recommended fix.** Write a region-suffixed heartbeat (`daily-discovery-in`) when
`region == "in"`, add a second discovery window to `check_pipeline_health()` (e.g. at
`t >= 11:00 UTC`, require `daily-discovery-in` after 09:30 UTC today, weekdays), and widen
the `health-monitor` cron hours from `4-10` to `4-11` so the new window is actually
evaluated. Keep the `daily-discovery` key for NA so existing monitoring is untouched.

## Gap 3 — MEDIUM (NFR1 cost + FR21 edge): the dashboard's call_log read is heavy and its latest-row window can expire

`dashboard.html:173` fetches `call_log?select=*&order=timestamp.desc&limit=1000` on every
60-second refresh. `select=*` drags the full `data_snapshot` — including
`raw_model_response`, which is the *entire batch* raw JSON replicated onto every row of a
run (SD §4.4a), plus tokens/headlines. That is easily several MB per refresh; an open
dashboard tab polls it every minute and can burn a meaningful share of Supabase free-tier
egress (NFR1) to render a handful of fields.

There is also a correctness edge: "latest row per ticker" is computed client-side from a
fixed 1000-row window (~3–4 days at current volume). FR21/Decision #13 say the last-run
block persists once a ticker has ≥1 check; after a long closure (holiday bridge + weekend)
one market's rows can age out of the window and its cards silently lose their verdict
block.

**Recommended fix.** Select only what renders:
`select=id,ticker,verdict,rationale,timestamp,label,data_snapshot->price` (an order of
magnitude smaller). Better: create a `latest_call_per_ticker` view
(`SELECT DISTINCT ON (ticker) ...` ordered by `ticker, timestamp DESC`) with a SELECT RLS
policy mirroring `call_log`'s, and have the dashboard read that — constant-size, no window
expiry, one row per ticker.

## Gap 4 — MEDIUM (doc integrity): Requirements and UI-handoff were never amended for the issue-#18 prices rework

- **Requirements FR21** still specifies current price "live-pulled on each refresh cycle"
  (and §3 scope says "live price"). As built — and as deliberately accepted in SD §13 —
  price is "as of the last `publish-prices` run" (~30-min cadence) read from
  `pages/prices.json`. The accepted downgrade is documented only on the SD side; the
  source-of-truth doc still promises the old behavior.
- **UI-handoff v3** — the declared *rendering authority*, whose own precedence rule says it
  wins over the SD — still says "Browser fetches Yahoo directly (anon key has no price
  data)" (Deliverable 3, freshness signal 1). That describes the design issue #18 proved
  infeasible. Taken at face value, the governing doc currently mandates an impossible
  implementation.

**Recommended fix.** Requirements v5 change note amending FR21 (publish-cadence price,
`generated_at`-honest freshness indicator); UI-handoff v4 note replacing the direct-fetch
sentence with the same-origin `prices.json` read. While in there: the handoff's "Headlines
— titles only" predates v18's `[YYYY-MM-DD]` prefixes now stored and rendered, and the SD
§5 `discovery_signals` examples (`volume-spike`, `52w-extreme`) don't match the code's
actual tags (`volume`, `52w-high`/`52w-low`, `prefilter.py:_signals`) — align the docs to
the code.

## Gap 5 — MINOR (UX/honesty): no-data skip rows render as real Hold verdicts

`state.log_skip()` writes `verdict="Hold"`, `parse_status="no_data"`. The dashboard's
last-run block and the detail page render that as an ordinary Hold pill with the skip note
as its rationale; `detail.html:134` shows the fail-safe callout only for
`failed`/`api_error`. A skipped cycle therefore reads as a genuine model judgment, which
contradicts the system's own "a fail-safe Hold is a placeholder, not a verdict" posture.

**Recommended fix.** In `detail.html`, add a distinct note for `parse_status === "no_data"`
("No usable market data this cycle — no verdict was made."). Optionally have the dashboard
prefer the most recent row with a real reading (falling back to the skip row) or badge
skip rows, so a transient Yahoo throttle doesn't visually overwrite the last real verdict.

## Gap 6 — MINOR (FR15): discovery ingest skips leave no call_log trace

`run_hourly` logs ingest skips via `state.log_skip` (issue #1 fix); `run_discovery.py:74`
only prints and counts them. A candidate that passed the screen but failed ingest vanishes
from the track record — inconsistent with FR15's "every check writes a log row" posture
and with the funnel-observability principle (#8). **Fix:** a `label="new-candidate"`
variant of `log_skip` (discovery already never touches `verdict_state`, so nothing else
changes).

---

## Improvement opportunities (not spec violations)

1. **`publish-prices` has no heartbeat and no monitor.** The same PAT/pg_cron failure
   modes that motivated NFR2 apply to it; if it stops, the dashboard just shows an
   ever-growing "prices updated Nh ago" that only helps if someone is looking. Cheap:
   write a `publish-prices` heartbeat row and add a staleness window to
   `check_pipeline_health()` (or at minimum a visual stale-warning threshold in the
   dashboard header when `generated_at` exceeds, say, 2 hours during market hours).
2. **NSE/CA discovery sourcing is narrower than FR4 reads.** For `region=in` (and `ca`)
   only gainers/losers screens are pulled, so the volume-spike/earnings/52w signals can
   only fire on names *already* moving ±5% — a pure volume-spike NSE candidate is
   unreachable, while the US path catches those via `most_actives`. This matches the
   shipped design (and Canada parity), but if FR4's "trips at least one of four signals"
   intent is taken literally, add a day-volume-sorted `region=in`/`region=ca` EquityQuery
   (one extra screener call each; funnel logging already handles the extra volume).
3. **Runtime gate grace as config** (see Gap 1's fix): keep the open/close bounds and the
   grace in `config.py` as named tunables so the gate semantics stay testable and the SQL
   and Python layers can be compared at a glance.
4. **Requirements FR6 vs. §5's "Regular intraday checks"**: FR6 now plainly says "every
   30 minutes"; fine — just noting the v2 change-note softening ("currently hourly") no
   longer matches FR6's wording. Cosmetic.

## Verified-as-matching (spot-checked, no action)

- Single rule §6.3 incl. the non-reading guard and cold-start silence (`state.process_ticker`).
- FR23 on all three surfaces (`notify._market_timestamp`, `detail.html fmtTs`, `dashboard fmtAbs`), incl. IST dedup.
- FR18 routing + issue-#35 operator-visible fallback (`notify._topic_for`).
- Discovery Buy-only push, 7-day dedup, funnel logging (#8), region profiles (D5).
- Per-market sessions, one batched AI call per open group, per-market model pairs (D2/D3).
- v18 prompt pass: discovery signals in-prompt, `n/a` rendering, dated headlines, schema-enforced output, null-confidence fail-safes.
- Dashboard FR19–22: SHA-256 gate, group labels, held/watching badges (text+icon), conditional `tc-bot`, configurable refresh, two distinct freshness clocks keyed off `generated_at`.
- Scheduler/monitor SQL matches SD §4.1/§4.8 (incl. ET/IST windows and the 16:05/15:35 SQL bounds), `SECURITY DEFINER` + revokes, Vault-only PAT.
- Workflows: `workflow_dispatch`-only, concurrency groups, model Variables, correct boolean-input handling.
