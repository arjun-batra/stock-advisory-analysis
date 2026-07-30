# Components

Part of `docs/design.md`'s module split (2026-07-25, REV-024). See `docs/design.md` for the index, module
map, §0 load-bearing decisions, and the requirement coverage map — read that first for orientation.
Section numbers below (§4, subsections 4.1–4.8) are unchanged from the pre-split monolithic `docs/design.md`.

---

## 4. Components

### 4.1 Scheduler — Supabase pg_cron → GitHub `workflow_dispatch` (FR6, FR17, NFR2)

- Both workflows are **`workflow_dispatch`-only** (native `schedule:` removed — GitHub's shared
  scheduler dropped ~13 of ~16 daily ticks, silently, the worst failure mode for a don't-miss-things
  system).
- `pg_cron` holds the schedule and calls a `SECURITY DEFINER` function
  `dispatch_github_workflow(workflow_file, inputs)` that reads a GitHub PAT from **Supabase Vault** and
  POSTs the dispatch via **`pg_net`**.
- **Load-bearing safety principle (`docs/design.md` §0, load-bearing #4):** the schedule fires more often
  than needed; the **runtime market gate is the real authority** on whether work happens.
- **ET/IST-aware, DST-correct gating.** `dispatch_watchlist_if_open()` gates US/TSX on
  `(now() at time zone 'America/New_York')::time between '09:30' and '16:05'` + weekday;
  `dispatch_watchlist_nse_if_open()` gates NSE on the IST session `09:15`–`15:35`. The wide
  `*/30 13-21 UTC` (US/TSX) and `*/30 3-10 UTC` (NSE) crons are DST supersets trimmed by the gates.
  The **16:05 / 15:35 upper bounds are close + 5 min** — deliberate jitter slack (`docs/design.md` §0,
  load-bearing #9).
- **Python execution-time defense-in-depth.** `config.is_market_open()` / `is_nse_open()` recompute the
  gate in ET/IST; their close bound is **16:00 / 15:30 + `RUNTIME_CLOSE_GRACE_MIN` (default 10 min)** —
  wider than the SQL slack because it absorbs dispatch-to-execution latency (load-bearing #9). Open bound
  stays exact.
- `daily-discovery.yml` is dispatched post-close: 22:00 UTC (`region=na`) and 10:00 UTC (`region=in`);
  discovery is not intraday-gated (§4.3, FR4 Decision #4).
- **Safe forced-test pattern.** `FORCE_RUN=true` bypasses the market gate; if `ALERTS_ENABLED=true` at
  the same time it fires **real** pushes off-hours. `run_hourly` prints a `[gate]` audit line every run.
  Documented safe pattern: for any off-hours forced run, set `ALERTS_ENABLED=false`.

SQL lives at `sql/scheduler_pgcron.sql` (dispatch fns + all cron jobs, matches live cron).

**REV-048, 2026-07-28 — market-session constants duplication, made visible (not merged).** The open
bounds, base close bounds, monitor grace windows, and the staleness threshold each exist independently in
both the Python and SQL layers. **This is not a request to merge the two close bounds** — load-bearing
decision #9 (`docs/design.md` §0) deliberately keeps SQL at close+5 and Python at close+
`RUNTIME_CLOSE_GRACE_MIN`, and that split is sound and stays as-is. The gap REV-048 flags is narrower:
changing `MARKET_OPEN`/`MARKET_CLOSE` in `scripts/config.py` (a documented tunable, `requirements.md` §10)
would leave the SQL sites below silently disagreeing, since nothing currently reads `config.py`'s value
into SQL or vice versa. Documented here as one linked table so the duplication is trackable, not merged:

| Constant | Python (`scripts/config.py`) | SQL |
|---|---|---|
| US/TSX open | `MARKET_OPEN` (09:30 ET) | `dispatch_watchlist_if_open()`, `t >= '09:30'` (`scheduler_pgcron.sql:279`) |
| US/TSX base close | `MARKET_CLOSE` (16:00 ET) | `dispatch_watchlist_if_open()`, `t <= '16:05'` — close+5 (`scheduler_pgcron.sql:279`) |
| NSE open | `NSE_MARKET_OPEN` (09:15 IST) | `dispatch_watchlist_nse_if_open()`, `t >= '09:15'` (`scheduler_pgcron.sql:132`) |
| NSE base close | `NSE_MARKET_CLOSE` (15:30 IST) | `dispatch_watchlist_nse_if_open()`, `t <= '15:35'` — close+5 (`scheduler_pgcron.sql:132`) |
| Monitor grace after US/TSX open | n/a (Python has no monitor) | `check_pipeline_health()`, `et >= '10:15'` (`phase5_monitoring.sql:125`) |
| Monitor grace after NSE open | n/a | `check_pipeline_health()`, `ist >= '10:00'` (`phase5_monitoring.sql:153`) |
| Monitor watchlist/publish-prices staleness threshold | n/a | `interval '70 minutes'`, three copies (`phase5_monitoring.sql:129,157,229`) |
| Runtime close grace (execution-time defense-in-depth) | `RUNTIME_CLOSE_GRACE_MIN` (10 min), added to `MARKET_CLOSE`/`NSE_MARKET_CLOSE` in `is_market_open()`/`is_nse_open()` | n/a (SQL's own +5 jitter slack is separate, load-bearing #9) |

Suggested (not built in this pass, qa's to schedule): a cheap test that reads `sql/scheduler_pgcron.sql`
and `sql/phase5_monitoring.sql` as text and asserts their literal time constants match `config.py`'s
`MARKET_OPEN`/`NSE_MARKET_OPEN` (open bounds only — the close-bound split is intentional and the test
should not flag it) — the suite already parses workflow YAML in `docs/handoff.md`'s verify block, so the
pattern exists.

### 4.2 Data ingestion — `yfinance` (FR1, FR9, non-functional-ops.md §7 data sources)

Single wrapper module (`ingest.py`) used by all workflows. Pulls price/volume, basic fundamentals
(`tk.info`), and built-in news (`Ticker.news`) — one data dependency, no separate news vendor. US tickers
are bare, TSX use `.TO`, NSE use `.NS`. **Market-agnostic:** keys off the ticker suffix and the yfinance
`exchange` field, so adding a market is a config concern, not an ingestion rewrite. `ingest._market_for`
resolves per-ticker market, carried on the `data` dict and persisted (`data-and-flow.md` §5).

Two data-quality behaviors (v18/v20, feed the prompt correctly):
- **Headline relevance filter** — `_headlines()` drops titles mentioning neither the company name
  (distinctive tokens; generic words stop-listed) nor the ticker, before the 5-title cap; **fail-open**
  when no company name is available. Dropped counts go to `notes`.
- **Session-aware price/volume** — `_session_state()` (strict session bounds, *not* the
  grace-extended dispatch gates) flags `session_live` and pro-rates `volume_vs_avg` by elapsed session
  fraction (`n/a` in the first 10%). Prompt renders "live price (session in progress)"/"today so far"
  vs "last close"/"1d" accordingly. Both flags persist to `data_snapshot`.

**Skip-with-log:** a ticker returning no usable data is skipped, never fatal (FR17, `non-functional-ops.md`
§7.5). New listings (<~20 sessions) are *not* skipped — compute what history supports, mark 20d fields
`n/a (newly listed)`.

**FIX ROUND (DEEP-004, INC-9) — stale-bar / closed-market structural check (FR17, Decision #33).**
`_session_state()` above decides "is this market live right now" from weekday + wall-clock alone; it has
no way to know the last bar `get_market_data()` actually received is *today's*. On an undetected holiday
(no maintained calendar exists, Decision #8) this let a genuinely-stale prior-close bar be judged as a
live, in-progress session — `session_live=True` fed straight to the prompt, and `volume_vs_avg` pro-rated
by the elapsed session fraction into a fabricated spike (`non-functional-ops.md` §7.5 for the full defect
history). **Fix, in `get_market_data()`, immediately after `h` is confirmed non-empty and before anything
else is computed:**
```
live, frac = _session_state(market)              # moved earlier — computed once, reused below
last_bar_date = h.index[-1].date()                # yfinance's own bar date, exchange-local
today_market = datetime.now(<market's tz>).date()  # config.MARKET_TZ / config.NSE_MARKET_TZ
if live and last_bar_date < today_market:
    out["notes"].append(
        f"market appears closed today ({today_market}) — latest available bar is from "
        f"{last_bar_date}; treating as no usable data (FR17/Decision #33)")
    return out   # has_price stays False: same skip-with-log path as any other no-data day
```
This is a single, self-contained check in one function — it fires *before* `price`/`pct_change`/
`volume_vs_avg` are computed, so the pro-rating math and the prompt's `session_live` labelling never see a
stale bar at all; **no separate fix is needed in `ai_judge.py`'s prompt-rendering or the pro-rating
math** — both are downstream of this gate and simply never execute for a stale-bar ticker. FR17's sharpened
text is explicit that this case takes "the skip-with-log path exactly as it does for any other detected
non-trading day" — not merely a labelled-live-but-flagged-stale reading — so `has_price` stays `False`,
the ticker never reaches the AI, and no verdict (real or fail-safe) is produced for it that cycle.
**Accepted edge case, not mitigated further:** in the first seconds/minutes after a *genuinely* open
session's start, yfinance's live intraday bar for today may not have posted yet, so this check could
misfire and skip a ticker for one cycle on a normal trading day. The failure direction is the safe one —
a missed check (self-corrects next cycle, 30 min later) is a MISS, not a fabrication, consistent with
`docs/design.md` §0 load-bearing #8 — so no additional open-side grace window is added (mirrors the
existing `frac < 0.1` "too early" treatment for volume pro-rating, same accepted-risk class).

**REV-043 design call, 2026-07-28 — a narrow price-only path for `publish_prices.py`.**
`publish_prices.py` (the */30 dashboard-snapshot publisher, `non-functional-ops.md` §8) currently calls
the same `get_market_data()` every AI-judgment path uses, but only reads four fields
(`price`/`pct_change_1d`/`market`/`fundamentals.currency`) — `get_market_data()` still does the full
3-month history fetch, `tk.fast_info`, the full `tk.info` scrape, and `tk.news` + headline filtering for
every one of those calls, roughly four Yahoo requests per ticker where one would do, on ~32 dispatch slots
a weekday across both sessions (`sql/scheduler_pgcron.sql`'s `publish-prices` cron). That's avoidable load
against an unofficial API this pipeline has already been rate-limited by (issue #1), and it shares the
`YF_PACING_SECONDS` budget with the watchlist runs that actually need the AI-facing data.
**Decision: add `ingest.get_price_only(ticker) -> dict`** — `period='5d'` history (enough for `price` and
`pct_change_1d`) plus `tk.fast_info` for `market`/currency context, **no `tk.info` scrape, no `tk.news`
call**. `publish_prices.py` switches to this function; `get_market_data()` is **untouched** and remains
the only path the AI-judgment code (`run_hourly.py`/`run_discovery.py`) uses — this is reuse at the wrong
grain being narrowed, not a second ingestion module. Implementation (the actual function body, field
mapping, and yfinance call shape) is dev's at INC-time; this is a design decision, not code. Not gated
behind any of INC-3–INC-7 — an independent live-system fix `pm`/`release` can schedule separately.

**Related, not addressed here (pm question, not a design gap):** `publish_prices.py` is currently the only
dispatch path with no market-open gate (`sql/scheduler_pgcron.sql:152`'s `publish-prices` cron fires
`*/30 3-10,13-21` with no `dispatch_..._if_open()` gate wrapping it), so it also fires through the
11:00–13:00 UTC gap between the NSE and US/TSX sessions. Worth confirming with pm whether that's
intentional; not changed by this fix.

### 4.3 Candidate sourcing & prefilter — discovery only (FR4, FR5, Decisions #4/#9/#14/#16)

`prefilter.py` sources candidates from **Yahoo's live server-side screener** (not a maintained universe —
`docs/design.md` §0, load-bearing #7) and applies quality gates + signals locally:
- **Sourcing:** daily pull of `day_gainers` / `day_losers` / `most_actives` (US) plus custom
  EquityQueries for Canada (`region=ca`) and NSE (`region=in`), each including a day-volume-sorted
  most-actives-style query (`_volume_query`, floored at `DISCOVERY_MIN_VOLUME`) so a pure volume-spike
  candidate is reachable in all regions.
- **Quality gates (all tunable, per-region):** min market cap (`DISCOVERY_MIN_MARKET_CAP` ~$2B US/CA;
  `DISCOVERY_MIN_MARKET_CAP_INR` ₹5e10 NSE), min price (`DISCOVERY_MIN_PRICE` $5; `_INR` ₹50), min daily
  volume (`DISCOVERY_MIN_VOLUME` 500k), and an allow-list of primary exchanges
  (`DISCOVERY_ALLOWED_EXCHANGES` NYSE/Nasdaq/Toronto; `DISCOVERY_ALLOWED_EXCHANGES_IN` = `{NSI}` only,
  dropping BSE dual-listings).
- **Signals — a survivor must trip ≥1** (FR4's four criteria, code tag values in `prefilter._signals`):
  (1) `mover` — abs % change past `DISCOVERY_GAINER_PCT`/`DISCOVERY_LOSER_PCT`;
  (2) `volume` — today's volume ≥ `DISCOVERY_VOL_SPIKE` × 3-month avg;
  (3) `earnings` — earnings within `DISCOVERY_EARNINGS_DAYS` (best-effort, when the screener carries an
  earnings timestamp);
  (4) `52w-high` / `52w-low` — price within `DISCOVERY_52W_PROXIMITY` of the 52-week extreme.
- **Shortlist** ranked and capped at `DISCOVERY_SHORTLIST_MAX` (~15/day) — the **only** thing sent to
  the AI.
- **Dedup:** watchlist tickers excluded up front; a candidate pushed within `DISCOVERY_PUSH_COOLDOWN_DAYS`
  (7d) is logged but not re-pushed ("log always, push conditionally").
- **Push policy — Buys only (FR4 Decision #16):** discovery pushes only `Buy`; `Sell`/`Hold` are logged
  silently.
- **Funnel observability:** `find_candidates()` returns `raw → after_dedup → passed_quality →
  passed_signal` plus `screens_errored`, logged stage-by-stage so a silent screener failure can't
  masquerade as a quiet day.

### 4.4 AI judgment layer (FR9, FR10, FR11, NFR1)

- **Model:** Gemini Flash on Google's **paid tier**. Real operation runs the **`gemini-2.5-flash` family
  across the board** (`gemini-3.5-flash`/`gemini-3.1-flash-lite` showed stability issues). **Model names
  are configurable repo Variables, never hardcoded:** `GEMINI_MODEL` / `GEMINI_MODEL_BACKUP` (watchlist),
  `NSE_GEMINI_MODEL` / `_BACKUP` (NSE watchlist), `DISCOVERY_GEMINI_MODEL` / `_BACKUP` (discovery). Wired
  through `judge_batch(models=...)`. **Model-default correction (already applied):** the literal defaults
  in `scripts/config.py` (and the workflow fallbacks in `hourly-watchlist.yml`) were updated from the 3.x
  strings to `gemini-2.5-flash` / `gemini-2.5-flash-lite` to match real operation. This fix was originally
  bundled into the now-retired shadow-track INC-1 (see `docs/design.md`'s "Retired: shadow-pilot tracks"
  note) but is independent, production-facing, and remains in effect after the shadow-track removal.
- **Dual-model fallback:** each call attempts primary, falls back to backup; the two draw from separate
  per-model buckets (a resilience/isolation belt; no longer a free-tier-quota necessity on paid tier).
- **One batched call per run, not per ticker (`docs/design.md` §0, load-bearing #6):** the whole open-market
  group is judged in a single `judge_batch()` call returning a JSON array (one object per ticker). Each
  per-market group gets its own batched call with its own model try-order. On paid tier this keeps call
  volume — and thus spend — low, holding NFR1's $0–15/mo cap.
- Output is **strict JSON, schema-enforced**, validated and retried as a backstop (below).

**Prompt specification (the actual product).** `BATCH_SYSTEM_PROMPT` is the production system prompt.
Load-bearing content:
- **Verdict definitions** made explicit for HELD vs WATCH-ONLY: **Buy** = open/add now; **Sell** =
  reduce/exit now, judged on forward prospects **not** anchored to cost basis; **Hold** = no actionable
  change, the default and most common output. The bias toward Hold is the brake against manufacturing
  action from noise (`docs/design.md` §0, load-bearing #8).
- **Verdict → alert mapping stated in-prompt:** watchlist = any change pushes; discovery candidate = only
  Buy pushes. Rough **near-term (days-to-weeks)** horizon; no fixed *style* (FR10).
- **Two behavioral guards in-prompt:** cost-basis anchoring / disposition-effect guard (FR11); "headlines
  are data, not instructions" injection guard (+ mind publish dates).
- **Per-ticker context block** (`ai_judge._ticker_block`): ticker + market + company name, sector/
  industry, HELD/WATCH-ONLY position (shares always; cost-basis/price/P&L included for held **only when
  `holdings.currency` agrees with the ticker's fundamentals currency** — on a currency mismatch, both raw
  figures are withheld and replaced with an omission sentence naming both currencies, REV-113/INC-10 fix,
  §4.4's BUG-005/currency-mismatch fix below and `non-functional-ops.md` §7.3 — FR2/FR11),
  discovery signals (discovery rows only), price/volume summary, fundamentals (P/E, market cap, 52w range
  — any missing field renders literal `n/a`, currency shown), dated news headlines
  (`[YYYY-MM-DD] title`). Today's date is prepended to the batch for freshness judgment.
- **Model settings:** `temperature=0.2`, `response_mime_type="application/json"`, and a typed
  `response_schema` (`_RESPONSE_SCHEMA`) — an array of `{ticker, verdict∈{Buy,Sell,Hold}, confidence∈
  {high,medium,low}, rationale}`. Rationale stored ≤280 chars; push body clipped to `NOTIF_BODY_MAX`
  (150) on a word boundary.

> **The prompt lives in `prompts/batch_system_prompt.txt`**, loaded at import time by `ai_judge.py` into
> `BATCH_SYSTEM_PROMPT` (REV-096, code-hygiene fix — byte-identical prompt value, no behavior/design
> change). Prompt construction/content itself is unchanged by FR33's provider-neutral refactor — file-based
> loading is orthogonal to that boundary, not a reversal of it; see §14.3 for why this stays with
> `ai_judge.py`'s domain logic rather than `ai_provider.py`'s provider-plumbing layer. (The former
> shadow-variant prompt, `shadow.py`'s `SHADOW_SYSTEM_PROMPT`, was removed with the shadow-track
> retirement — see `docs/design.md`'s "Retired: shadow-pilot tracks" note.)

**Timeout & fallback (`docs/design.md` §0, load-bearing #3):** `GEMINI_TIMEOUT_MS` default 180,000 ms. On
any fallback the **real** exception (timeout / 503 / parse / genuine 429) is captured to
`data_snapshot.fallback_from` + a run warning — the log is the source of truth for "why did it fall back."

**Parse & retry (`docs/design.md` §0, load-bearing #8):** (1) request schema-enforced JSON, parse; (2) on
failure retry once with a terse "reply with ONLY the JSON array"; (3) on second failure **log, treat
verdict as `Hold` (no alert), move on** — a fail-safe Hold carries `confidence: null`, never fabricated.
(4) every raw response (incl. failures) is written to `data_snapshot`.

**FIX ROUND (DEEP-003, INC-9) — positional-fallback attribution contract, `_parse_batch` (§4.4a).** When a
requested ticker is absent from `by_ticker` (the model's response didn't label an object with that
ticker), `_parse_batch` falls back to the array object at the same index as the request — legitimate only
when the model followed request order but the object's own `ticker` field is missing/blank (it forgot the
label, not a different company). As shipped, the fallback accepted **any** dict at that index regardless
of its own `ticker` field, so a dropped-then-shifted response (`[A,B,C]` requested, model returns
`[A,X,B]`) could attribute `B`'s verdict/rationale/confidence to `C` and stamp it `parse_status: "ok"` —
the one path that could **fabricate**, not merely miss, a signal (violating `docs/design.md` §0 #8, which
this fix restores). **Fix — the positional object is accepted only when it corroborates the ticker being
resolved:**
```
o = by_ticker.get(t.upper())
used_fallback = False
if o is None and len(arr) == len(tickers) and isinstance(arr[i], dict):
    cand = arr[i]
    cand_ticker = cand.get("ticker")
    # Legitimate case: object has no ticker label at all, OR its own ticker
    # normalizes (case-fold, strip .TO/.NS) to the one we're resolving. A
    # DIFFERENT normalized ticker at this index means the array is
    # misaligned — accepting it would misattribute another company's verdict.
    if not cand_ticker or _normalize_ticker(str(cand_ticker)) == _normalize_ticker(t):
        o, used_fallback = cand, True
if used_fallback:
    print(f"  [ai_judge] positional fallback used for {t} (array index {i} had no "
          f"matching 'ticker' label)")
```
Anything that fails this narrowed check falls through to `_FAIL_SAFE_PARSE` (`parse_status: "failed"`) —
same fail-safe-to-Hold posture as every other parse failure, so it is caught by `state.py`'s existing
`parse_status in ("failed","api_error")` guard and can never fire a fabricated alert. `_normalize_ticker`
is a small helper (`.upper()`, strip a trailing `.TO`/`.NS`) — the same normalization `_market_for`
(`ingest.py`) already applies, not a new convention.
**Secondary, same fix commit:** `by_ticker`'s dict comprehension keeps the *last* of any duplicate ticker
label in the model's response, silently. Log (not reject) a duplicate when building `by_ticker` — a
one-line print, no behavior change — so a model repeating a ticker is visible in the run log rather than a
silent data-quality issue.
**Module docstring correction (dev, same commit):** `ai_judge.py`'s header docstring currently states "a
malformed response can only ever MISS a signal, never fabricate one" as an unqualified claim; update it to
name the positional-fallback narrowing above as the mechanism that makes the claim true, rather than
leaving it as an assertion the code didn't fully honor.

**BUG-005 refinement (INC-9 fix-cycle-1) — unambiguous-normalization guard.** The DEEP-003 fix above
legitimizes a normalized-only match ("its own `ticker` field is absent, OR its own ticker normalizes ...
to the one we're resolving") without qualification. That is itself a hole: `_normalize_ticker` strips a
trailing `.TO`/`.NS` suffix, so two *different*, real companies cross-listed on two markets — e.g.
`ABC.TO` and `ABC.NS` — normalize to the identical string `"ABC"`. If a batch requests both and the
model's response labels one of them (say `ABC.TO`) but not the other, the unqualified corroboration check
lets `ABC.NS`'s positional fallback accept `ABC.TO`'s own already-consumed labeled object as
"corroboration": one real company silently inherits a different real company's verdict/rationale under
`parse_status: "ok"` — the exact DEEP-003 fabrication class (§0 #8), reopened by the mechanism DEEP-003's
own fix introduced to close it.

**Why this is non-obvious, worth stating explicitly so it isn't optimized away later:** the corroboration
check reads as safe in isolation — it only accepts a candidate whose own ticker field "agrees with" the
one being resolved. But "agrees with" is doing normalization-strength work, and normalization is lossy by
design; that lossiness is the entire point (it's what lets a bare `"ABC"` reply legitimately resolve a
request for `"ABC.TO"`, §4.4a's own worked case). A future reader who trusts the check's *name*
("corroborates") rather than its *lossiness* could plausibly conclude the ambiguity guard below is
redundant belt-and-suspenders and simplify it back out — it is not; it is the only thing standing between
this branch and a cross-market fabrication.

**Fix — a normalized-only match is accepted only when it is unambiguous within the batch: exactly one of
the DISTINCT tickers requested this call normalizes to that form.**
```
distinct_requested = {x.upper() for x in tickers}                          # dedup requested tickers
normalized_counts = Counter(_normalize_ticker(x) for x in distinct_requested)  # first -- a ticker
                                                                             # requested twice in one
                                                                             # batch is a duplicate
                                                                             # REQUEST, not a second,
                                                                             # distinct ticker colliding,
                                                                             # and must not count against
                                                                             # itself (BUG-006)
...
o = by_ticker.get(t.upper())
used_fallback = False
if o is None and len(arr) == len(tickers) and isinstance(arr[i], dict):
    cand = arr[i]
    cand_ticker = cand.get("ticker")
    t_norm = _normalize_ticker(t)
    unambiguous_normalized_match = (
        cand_ticker and _normalize_ticker(str(cand_ticker)) == t_norm
        and normalized_counts[t_norm] == 1
    )
    if not cand_ticker or unambiguous_normalized_match:
        o, used_fallback = cand, True
```
*(Pseudocode-currency note: this block mirrors the shipped `_parse_batch` and has twice run a fix cycle
behind it — first the ambiguity guard itself, then this dedup — because the fix landed in code before this
doc was updated. `scripts/ai_judge.py`'s `_parse_batch` function and its own docstring are the source of
truth if the two ever appear to disagree; this block is refreshed at each fix cycle's close, not guaranteed
byte-current mid-cycle.)*

Two or more requested DISTINCT tickers colliding on the same normalized base symbol means a normalized-only match
can't tell which one the candidate actually belongs to, so every one of them must fail safe rather than
guess — same "never fabricate, only miss" posture as the original misaligned-array case, applied one
level deeper. The no-`ticker`-field branch is untouched by this guard: it never depended on normalization
to identify a match in the first place (there is no foreign label to compare against), so it cannot become
ambiguous the same way.

**Alternative considered and rejected: require an exact (non-normalized) match whenever the candidate
carries an explicit `ticker` field, reserving normalization for the no-field case only.** Narrower, and it
would also close the collision — but it breaks the legitimate case §4.4a exists to serve: a model that
replies with a bare `"ABC"` when asked about `"ABC.TO"` (a label is present, just not exchange-qualified)
would fail safe under an exact-match rule even in a single-ticker batch with nothing else to collide
against. The unambiguity guard keeps that legitimate normalized match working whenever it is actually
safe (nothing else in the batch could be confused for it) and refuses to guess only when it is genuinely
ambiguous — it targets the failure condition (ambiguity) rather than the mechanism (normalization) that
only sometimes produces it.

**Second-order judgment, recorded per this fix (not itself a design change; INC-9 stays mid-cycle
code-only).** Per-batch unambiguity is the right *contract* to specify at the `_parse_batch` boundary — it
is cheap, local, and correctly scopes the corroboration check to exactly the cases where "normalizes to"
is trustworthy. But it treats the symptom, not the root cause: `_normalize_ticker`'s suffix-stripping is a
lossy primitive being reused for identity comparison, and per-batch unambiguity only holds because
*today's* watchlists don't happen to carry the same base symbol on two markets at once. FR20 groups
tickers by market but nothing in the requirements prevents a user from watching both `ABC.TO` and `ABC.NS`
simultaneously (the realistic trigger BUG-005 itself names) — if that ever happens, the guard's designed
behavior is "both fail safe," which is correct (no fabrication) but is a live MISS on a watchlist entry
the user genuinely holds, for as long as the collision persists in that batch.
- **Exchange-qualified matching** (exact match first, suffix-stripped normalization only as fallback) was
  considered and doesn't structurally close this — it still needs a lossy fallback path for the legitimate
  bare-`"ABC"` case, and that fallback path is exactly where the ambiguity re-enters. It shrinks the
  surface (only same-batch, cross-market, one-side-bare replies) without removing it.
- **Prompt-level fix — require the model to always echo back the caller's exact, exchange-qualified
  ticker string, never a bare base symbol** is the structurally cleaner option: if `BATCH_SYSTEM_PROMPT`
  guaranteed that, the entire normalized-match branch (and the ambiguity it creates) becomes dead code —
  only the no-label positional fallback would remain, and that branch is unaffected by any of this. Not
  proposed as a change here: it needs a verification pass on how reliably a real model actually honors an
  echo-back instruction under load before being trusted as the sole guard, not an assumption swapped in for
  the current defense-in-depth.

**Verdict: closed for the current watchlist shape (no live cross-market same-base-symbol collision on
today's US/TSX/NSE watchlists), patched rather than structurally closed for the general case.** Keep the
per-batch unambiguity guard regardless of any future prompt change — defense in depth costs nothing here.
If a future increment allows or encourages watching the same company across two markets simultaneously,
revisit the prompt-level echo-back fix rather than trying to harden `_normalize_ticker` further: the
parser-side primitive has little room left to give without becoming exact-match, which reintroduces the
exact case the positional-fallback mechanism exists to handle.

**BUG-006 fix (INC-9 fix-cycle-2) — duplicate-requested-ticker overwrite guard, and its accepted residual
(BUG-007).** `out` is keyed by ticker string. If the same ticker string is requested twice in one
`_parse_batch` call (distinct from the BUG-005 cross-market collision above — this is one ticker appearing
twice in `tickers`, not two different tickers colliding on a normalized form), the two occurrences resolve
independently and both write into `out[ticker]`; the later write always wins. Two overwrite directions
follow, guarded asymmetrically and deliberately:
- **`failed`-over-`ok` (guarded).** A later fail-safe must never silently discard an earlier real verdict —
  that would destroy an available, legitimate answer for no reason. Guarded explicitly: `if
  result["parse_status"]=="failed" and out.get(t,{}).get("parse_status")=="ok": continue` (skip the write,
  log it as keeping the earlier resolved verdict).
- **`ok`-over-`ok` (unguarded — accepted limitation, BUG-007, qa's test-report.md).** If both occurrences
  resolve legitimately but to *different* verdicts (e.g. Buy then Sell), the guard above does not fire —
  both are `"ok"` — so the later write silently overwrites the earlier with no log trace distinguishing it
  from an ordinary single resolution (only the two routine "positional fallback used" lines appear).
  **Accepted for now, not fixed:** both outcomes are equally legitimate AI resolutions, not a fabrication
  and not a fail-safe miss — this is a determinism/observability gap, not a violation of the "never
  fabricate, only miss" invariant (`docs/design.md` §0 #8). A real fix means changing `_parse_batch`'s
  ticker-keyed return contract (`{ticker: result}`, which cannot hold two results for one requested ticker)
  to something positional or request-index-keyed, rippling through `judge_batch`'s `_enrich` and every
  caller's per-ticker lookup (`run_hourly.py`/`run_discovery.py`'s `verdicts.get(ticker)`, `state.py`'s
  downstream consumption) — a design-level contract change, not a bug-cycle patch, and disproportionate to
  a minor, narrow defect. Regression-locked:
  `tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`.

**Why only one overwrite direction is guarded (the asymmetry is intentional, not an oversight).** The
guarded direction prevents a strictly worse outcome — a real verdict silently replaced by a placeholder
that carries no information (a Hold with `confidence: null` and a fail-safe rationale). The unguarded
`ok`-over-`ok` direction has no such asymmetry: both candidates are genuine AI verdicts, so there is no
principled way to prefer one over the other without the contract change described above — guarding it
would require solving BUG-007 properly, not adding a second special case.

**Tech-lead recommendation on the root cause — record for the next person, not adopted this cycle.**
Verified against the current call paths (`scripts/prefilter.py::find_candidates`, `scripts/run_discovery.py`,
`scripts/run_hourly.py`) rather than asserted: **`_parse_batch`'s ticker-keyed return contract should stay
as-is; the right fix, if this is ever pursued, is guaranteeing duplicate-free input at the boundary that
builds a batch, not restructuring the parser's return shape.** Reasoning:
- The ticker-keyed contract (`{ticker: result}`) is the right shape for the overwhelmingly common case —
  every caller (`run_hourly.py`/`run_discovery.py`'s `verdicts.get(ticker)`, `_enrich`'s per-value stamping)
  does a simple keyed lookup; moving to positional/request-index keys would ripple through every one of
  those call sites and every test fixture that mocks `judge_batch`, to defend against an input shape
  (`tickers` containing a duplicate) that a well-formed caller should never produce in the first place.
- **`watchlist.ticker` cannot produce a duplicate** — it is a DB primary key (confirmed, `data-and-flow.md`
  §5), so `run_hourly.py`'s batches are structurally duplicate-free.
- **Discovery's candidate batches are also duplicate-free today, but incidentally rather than by a stated
  contract.** `prefilter.find_candidates()` builds its shortlist through a `seen: dict[str, dict]` keyed on
  the uppercased symbol (`prefilter.py` lines 223-228), deduplicating across every screener query (gainers/
  losers/actives/regional) within that one call, before quality gates, signals, or ranking ever run; and
  `run_discovery.py` calls `find_candidates()` exactly once per region per run and feeds its output straight
  into one `judge_batch()` call. So today's only duplicate-prone source is, in practice, already
  duplicate-free by construction. It is not, however, an *enforced* invariant — nothing tests or asserts at
  the `find_candidates()`/`judge_batch()` boundary that the returned list is duplicate-free, so a future
  change to candidate sourcing (e.g. a new query added outside the `seen` loop, or a second `find_candidates`
  call merged into one batch) could silently reintroduce the precondition BUG-006/BUG-007 guard against,
  with no test to catch the regression.
- **Verdict: this is a closed non-issue for the live call paths today, and a cheap, narrow action item — not
  the parser contract — closes the remaining gap.** Recommend a lightweight regression test (qa's, not a
  design change) asserting `find_candidates()`'s returned candidate list never contains a duplicate ticker,
  making the currently-incidental guarantee an explicit, tested contract of the sourcing boundary. `out`'s
  ticker-keyed shape and BUG-006's guard/BUG-007's documented gap stand as defense-in-depth for a
  precondition violation that should never reach `_parse_batch` in the first place, same posture as
  `_parse_batch`'s other fail-safe branches — not evidence the contract itself needs to change.

**Confidence (persisted, not yet consumed):** the model's self-rated `high`/`medium`/`low` is validated,
persisted in `data_snapshot.confidence`, surfaced on the cards, but **read by no gating logic today**
(known limitation, `frontend.md` §12).

**Token accounting (`docs/design.md` §0, load-bearing #6):** `data_snapshot.tokens {prompt, output,
thoughts, total}` is a **per-batch total replicated onto every row** — dedup per run, never sum per row.

### 4.5 State & persistence — Supabase (FR14, FR15)

All durable state in Postgres (schema `data-and-flow.md` §5). Chosen over a flat file because the detail
page (FR14) queries a specific log row directly. Supabase also hosts the scheduler and watchdog (§4.1,
§4.8, above).

### 4.6 Alerting — ntfy.sh (FR12, FR13, FR14, FR18, FR23, NFR3)

Free, no account, topic-based push, `click` field for tap-through. `notify.py` is provider-agnostic
(Pushover is a drop-in). One watchlist alert kind — `change` ("Changed to Buy"); the `reminder` kind is
retired (FR7). Discovery pushes are labeled `new-candidate`. Health-monitor pushes come from Supabase
directly via `send_ntfy`.

- **Notification timestamp (FR23):** formatted server-side, so **one** market-matched timezone, no
  secondary — US/TSX → ET (`10:30 AM ET`), NSE → IST (`8:00 PM IST`). `notify._market_timestamp(market)`;
  `_compose_body` prefixes it within `NOTIF_BODY_MAX=150`. Unknown market → ET.
- **Separate NSE topic (FR18):** `notify._topic_for(market)` routes NSE → `NSE_NTFY_TOPIC`, US/TSX →
  `NTFY_TOPIC`, **falling back to the default topic if `NSE_NTFY_TOPIC` is unset** (never drops an alert)
  and emitting an operator-visible `[FR18 fallback]` run-log line if it does.
- Notification copy (titles/body) is owned by the UI handoff (`requirements_docs/
  stock-advisor-ui-handoff-v3-spec.md`, v4) — build to the handoff.

**FIX ROUND (DEEP-002, INC-8) — delivery-confirmed contract (FR34, FR15's `alerted` definition).**
`Notifier.push()`'s contract is revised so callers can tell attempted from delivered — previously `push()`
returned nothing, swallowed all exceptions, and never checked the HTTP status, so a failed send was
indistinguishable from a success at the call site. **New return contract, both implementations:**
- `NtfyNotifier.push(...) -> bool` — `True` only on a confirmed 2xx (`resp.raise_for_status()` inside the
  `try`); `False` on any `requests` exception or non-2xx status, logged distinctly
  (`[notify] ERROR push failed for {ticker}: ...`) rather than the old print-and-swallow.
- `DryRunNotifier.push(...) -> None` — `None` is a third, explicit state: "deliberately not attempted"
  (`ALERTS_ENABLED=false` or no topic configured), distinct from both `True` and a real `False` failure.
  Never conflate `None` with a failure — a dry run is an operator choice, not an outage.

**`state.py` call-site contract (both `process_ticker` and `process_candidate`):** a `log_id` is generated
client-side (`str(uuid.uuid4())`, `call_log.id` is already `uuid`) **before** `push()` is called, so it can
be passed into both `push()` (for the tap-through URL) and the subsequent `write_call_log(id=log_id, ...)`
— this removes the previous ordering assumption that the log row had to exist before the push, which is
what let `alerted` get written before the outcome was known.
- `delivered = notifier.push(...)` — `True` / `False` / `None`.
- `alerted = (delivered is True)` — written to `call_log.alerted`; **only a confirmed 2xx counts** (FR15's
  redefinition). A dry run writes `alerted=False` — it is honest that nothing was sent, not a claim of
  delivery it can't back up.
- **State/cooldown advance:** `delivered is False` (a real, failed attempt) does **not** advance
  `verdict_state.current_verdict` (watchlist) — the next cycle re-evaluates the same crossing against the
  still-unadvanced prior verdict and retries automatically (FR34's literal retry contract). `delivered is
  True` **or** `None` (dry run) *does* advance state — a dry run is a deliberate, expected non-send, not a
  failure to recover from; **not** advancing on a dry run would let a verdict backlog build up silently
  while `ALERTS_ENABLED=false` and dump all at once the moment it flips back on, which is worse than the
  status quo and not what FR34 is for. Discovery has no `verdict_state`/cooldown lifecycle to advance
  either way, but its 7-day re-push dedup (`recently_pushed_candidates`, keyed on `alerted=True`) is a
  direct consumer of this same fix: a failed or dry-run candidate push is no longer falsely deduped for a
  week (Decision #32) — it naturally resurfaces next scan since `alerted` stays `False`.
- New outcome label for the run log / heartbeat outcomes `Counter`: `"push-failed"` (watchlist) /
  `"candidate-push-failed"` (discovery) when `delivered is False` — folded into the degraded count, see
  §4.8 below.

### 4.7 Detail page — GitHub Pages (FR14, FR2, FR11, FR23, NFR3, Decision #17)

Static page; reads `log_id` from the query string and fetches that `call_log` row via a read-only
Supabase **publishable key** (RLS-scoped to read `call_log`). The workflows use the **secret key**
(bypasses RLS), never shipped to the page. Security is the **unguessable URL**, which holds only because
`call_log.id` is a **UUID, not a serial**. **No auth gate** (Decision #17 — FR19's access control scopes
to the dashboard only; NFR3 informational data is the accepted rationale).

- **Held-position block:** rendered only when `data_snapshot.position` is present (held tickers) —
  shares, cost basis, current price, unrealized P/L (FR2/FR11). Currently dormant (live watchlist has 0
  held tickers); ruled working-as-intended.
- **Market badge / currency:** derived from `data_snapshot.market` (`$` / `CA$` / `₹`); suppressed on
  `new-candidate` rows (no authoritative market). `.NS`-suffix + fundamentals-currency fallbacks remain
  only for legacy rows.
- **Timestamp (FR23):** client-rendered, device timezone primary + IST secondary in brackets, deduped if
  the device is IST. `call_log.timestamp` is UTC; conversion is client-side.
- **No-data rows:** a `parse_status=='no_data'` row shows a "skipped, no verdict made" note.
- Layout/variants owned by the UI handoff (v4).

### 4.8 Reliability — active dead-man monitor (NFR2)

A passive heartbeat no one reads is not a monitor (`docs/design.md` §0, load-bearing #5). Design:
- A third pg_cron job, **`health-monitor`**, runs **`check_pipeline_health()`** independently of the two
  workflows.
- It actively raises an **ntfy alert** (via `send_ntfy`) when: the watchlist heartbeat is **stale during
  market hours** (ET window `10:15`–`16:00`, plus a second IST window for NSE), a **discovery run didn't
  fire** (per-region: `daily-discovery` NA checked after 23:00 UTC, `daily-discovery-in` NSE checked
  after 11:00 UTC), the **dashboard price snapshot stops refreshing** (`publish-prices` heartbeat >70 min
  old during a session), or a run **completed degraded**.
- **`monitor_alerts`** (state table) dedups: alert on state change into a bad state, re-alert per
  cooldown while bad, one recovery notice when it clears. Helpers `_raise_monitor` / `_clear_monitor`.
- The `health-monitor` cron window is `4-11,14-23` UTC (covers both sessions + both discovery checks).
- DDL: `sql/phase5_monitoring.sql`.

**Known limit (`foundations.md` §2 item 6):** the monitor lives in the same Supabase pg_cron it watches —
it cannot catch a total Supabase/pg_cron outage. An out-of-band uptime ping is the documented, unbuilt
mitigation.

**FIX ROUND (DEEP-001, INC-8) — heartbeat status must reflect "completes degraded" as NFR2 now defines
it.** `run_hourly.py`/`run_discovery.py` compute `status` from an `outcomes` `Counter` keyed by what
happened to each ticker (`skip`, `error`, `no-read`, `cold-start`, `quiet`, `change-alert`, `push-failed`,
...) and write it to `run_heartbeat.status`; `check_pipeline_health()` (`sql/phase5_monitoring.sql`)
already alerts on any `status <> 'ok'` — so the SQL side needs **no change**, the bug is entirely in which
Python outcomes count as "not ok." **As shipped, `degraded = outcomes["skip"] + outcomes["error"]`
omitted `outcomes["no-read"]`** — every fail-safe Hold from a parse/API failure (`state.py`'s
`parse_status in ("failed","api_error")` guard) — so a run where **every** ticker's AI call failed (expired
key, provider outage, bad model string) still wrote `status="ok"`. This is precisely NFR2's sharpened
"completes degraded" case (`requirements.md` NFR2, Decision #31): "any run in which one or more requested
tickers failed to produce a valid AI verdict for any reason ... regardless of internal bucket naming."
**Fix — both entry points, the only line that changes:**
```
degraded = outcomes["skip"] + outcomes["error"] + outcomes["no-read"] + outcomes["push-failed"]
status = "partial" if (degraded or config.TUNABLES_DEGRADED) else "ok"
```
(`run_discovery.py`'s equivalent line already includes `screens_errored`; add `outcomes["no-read"]` and
`outcomes["candidate-push-failed"]` to it the same way.) `outcomes["push-failed"]`/`"candidate-push-failed"`
are the new DEEP-002 outcome labels (above) — folded in here rather than as a separate change, since both
fixes touch the same formula in the same two files; this is why INC-8 bundles DEEP-001+DEEP-002. No new
status tier is introduced: an all-`no-read` run already gets the same `"partial"` value — and therefore
the same `check_pipeline_health()` alert branch — that a partially-skipped/errored run already gets today,
which satisfies NFR2's "at least the same urgency as a fully skipped/errored run" bar without a new SQL
branch. **Dashboard/detail-page rendering (`pages/dashboard.html`, `pages/detail.html`):** the detail page
already special-cases `parse_status in ("failed","api_error")` with a "fail-safe Hold" note
(`detail.html`'s `failNote`) — no change needed there. `dashboard.html`'s per-row verdict pill only
special-cased `parse_status === "no_data"` ("no data" pill); a `failed`/`api_error` row rendered a normal
`Hold` pill, indistinguishable from a real verdict. **Fix:** widen the same check to
`["no_data","failed","api_error"].includes(row.parse_status)` → render the existing "no reading" pill
style for all three (label can stay "no data" or become a shared "no reading" string — dev's call, no
behavior difference); the confidence-pill guard (`row.confidence && ...`) needs no change since
`confidence` is already `null` on every fail-safe row.
