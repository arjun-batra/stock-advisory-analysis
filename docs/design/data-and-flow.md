# Data model & core flow

Part of `docs/design.md`'s module split (2026-07-25, REV-024). See `docs/design.md` for the index, module
map, §0 load-bearing decisions, and the requirement coverage map — read that first for orientation.
Section numbers below (§5–§6) are unchanged from the pre-split monolithic `docs/design.md`.

---

## 5. Data model (Supabase / Postgres)

| Table | Key columns | Purpose / FR |
|---|---|---|
| `watchlist` | ticker, market (US/TSX/NSE), type, status (held/watch-only), date_added | Ticker list (FR1, FR3); `market` CHECK admits NSE |
| `holdings` | ticker, shares, cost_basis, currency | Position data (FR2, FR11); `currency`∈{USD,CAD,INR}; `shares>0`/`cost_basis>0` CHECK guards |
| `verdict_state` | ticker, current_verdict, last_checked_at | Change-detection for the single rule (FR7/FR8); shrunk to 3 cols when cooldown/reminder retired |
| `call_log` | id (**uuid**), ticker, verdict, rationale, timestamp (UTC), label (watchlist/new-candidate), alert_type (change/null), alerted (bool), data_snapshot (jsonb) | Track record (FR15); detail-page source (FR14) |
| `monitor_alerts` | check_name (PK), last_state, last_alerted_at, updated_at | Dead-man monitor dedup (NFR2) |
| `run_heartbeat` | workflow_name, last_run_at, status | Per-workflow heartbeat (NFR2). Keys: `hourly-watchlist` (shared across sessions), `daily-discovery` (NA), `daily-discovery-in` (NSE), `publish-prices` |

> **RETIRED (2026-07-16):** `call_log_shadow` (former US/CA shadow pilot table) and `call_log_shadow_nse`
> (former NSE shadow pilot table) are removed from this data model. Both were `DROP TABLE`d from the live
> Supabase project (not just left unwritten) — already executed and verified; see `docs/design.md`'s
> "Retired: shadow-pilot tracks" note.

**View `latest_call_per_ticker`** (`sql/dashboard_latest_call_view.sql`): most recent `call_log` row per
ticker (`DISTINCT ON (ticker) … ORDER BY ticker, timestamp DESC`), slim columns only (`id, ticker,
verdict, rationale, timestamp, label, alerted, parse_status, price, confidence`). `security_invoker=true`
so the publishable key is still governed by `call_log`'s RLS. Replaces a client-side scan that shipped
multi-MB `raw_model_response` per refresh (FR21, NFR1).

**`data_snapshot` (jsonb) contract — the load-bearing consumer contract:**
```json
{
  "market": "US | TSX | NSE",
  "price": 0.0, "pct_change_1d": 0.0, "pct_change_5d": 0.0, "pct_change_20d": 0.0,
  "volume_vs_avg": 0.0, "session_live": false, "volume_pro_rated": false,
  "fundamentals": { "pe": 0, "market_cap": 0, "range_52w": [0,0], "currency": "USD",
                    "name": "...", "sector": "...", "industry": "..." },
  "headlines": ["[2026-06-30] ...", "..."],
  "raw_model_response": "<verbatim>",
  "confidence": "high | medium | low | null",
  "parse_status": "ok | failed | api_error | no_data",
  "model_used": "<gemini model string>",
  "tokens": { "prompt": 0, "output": 0, "thoughts": 0, "total": 0 },
  "fallback_from": "<null | '<model>: <ExcType>: <message[:200]>' | '<model1>: ...; <model2>: ...' | ...>",
  "discovery_signals": ["mover", "volume", "52w-high"],
  "rate_limited": false,
  "position": { "shares": 0, "cost_basis": 0.0, "currency": "USD", "pl_pct": 0.0 }
}
```
- `tokens` is a **per-batch total replicated across every row — dedup per run, never sum per row**
  (`docs/design.md` §0, load-bearing #6).
- `discovery_signals` present only on discovery rows; `position` present only on held tickers; `market`
  written on both write paths by `state._snapshot()`.
- `confidence` is `null` on any fail-safe path, never a guessed default; not yet read by any consumer
  (`frontend.md` §12).
- **REV-057 fix, 2026-07-28:** this contract previously listed `parse_status` values `ok | retried |
  failed | api_error | no_data` and a short `fallback_from` token set (`timeout | 503 | 429-rpd | parse`);
  neither matched what the code actually writes. `retried` is written by nothing — the retry path
  (`components.md` §4.4's "parse & retry") returns `ok` on a successful retry, so `retried` is removed
  from the documented set (reserved/unused, not a live value). `fallback_from` is a full string,
  `"; ".join(f"{model}: {detail}" for each attempted model)`, assembled in `ai_judge.judge_batch` from the
  per-attempt `detail` string (`f"{type(exc).__name__}: {str(exc)[:200]}"`) that
  `ai_provider.GeminiProvider.generate` raises inside its `ProviderError` since INC-4 (pre-INC-4 this was
  all built in `ai_judge._generate`) — corrected above to match. Any future query/analytics view against
  this jsonb shape should match the writer, not the previously-stale contract.

**Timestamps stored in UTC; rendering per-surface (FR23):** notifications = one market timezone
(server); detail page + dashboard = device primary + IST secondary (client); relative time computed
client-side at render from `call_log.timestamp` (never stored). Market-hour gating computed in ET/IST,
never fixed UTC offsets.

**Supabase objects.** Functions: `dispatch_github_workflow`, `dispatch_watchlist_if_open`,
`dispatch_watchlist_nse_if_open`, `send_ntfy`, `_raise_monitor`, `_clear_monitor`,
`check_pipeline_health`. View: `latest_call_per_ticker`. Extensions: `pg_cron`, `pg_net`. Vault secrets:
`github_workflow_pat`, `ntfy_topic`. RLS is on for every table; publishable key has SELECT policies on
`call_log` and `watchlist` only. (The former shadow tables' RLS/no-anon-grant posture no longer applies —
both tables are dropped; see `docs/design.md`'s "Retired: shadow-pilot tracks" note.)

---

## 6. Core flow — single-rule change detection (FR6, FR7, FR8, FR15)

Cadence is **every 30 minutes** during market hours (the workflow is legacy-named `hourly-watchlist.yml`
and heartbeat `hourly-watchlist`, which do **not** mean 60 minutes). Each wake-up filters the watchlist to
whichever session is open (US/TSX via ET, NSE via IST — sessions never overlap, verified) and runs that
group through its own batched AI call.

The single alerting rule (`docs/design.md` §0, load-bearing #1/#2), implemented in `state.py`:

```
for each ticker in (watchlist filtered to the currently-open market):
    new_verdict = ai_judge(...)                 # JSON-validated, fails safe to Hold
    state = get_verdict_state(ticker)

    if state is None:                           # cold start: baseline, no alert (avoids go-live dump)
        create_verdict_state(ticker, new_verdict, now)
        write_call_log(ticker, new_verdict, alert_type=NULL, alerted=False)   # FR15
        continue

    if new_verdict == state.current_verdict:    # no change -> silence, still logged (FR15/FR8)
        state.last_checked_at = now
        write_call_log(ticker, new_verdict, alert_type=NULL, alerted=False)
        continue

    # change -> immediate alert, no cooldown (FR7)
    write_call_log(ticker, new_verdict, alert_type="change", alerted=True)
    send_push(ticker, new_verdict, rationale, kind="change")   # "Changed to X", topic per market
    state.current_verdict = new_verdict
    state.last_checked_at = now
```

Consequences (stated plainly): a change **to Hold** still alerts (a weakening Buy is a signal); there is
**no frequency cap** (choppy day pushes every flip — accepted, `foundations.md` §2 item 4); **every check
logs** (FR15), including no-change and cold-start rows with `alerted=false`. A standing actionable verdict
at cold start is **silent until it crosses** (`docs/design.md` §0, load-bearing #2) — this is why NSE
go-live did not dump 10 alerts.

Daily discovery (`run_discovery.py`) runs the sourcing/prefilter (`components.md` §4.3) → one batched AI
call → logs every candidate as `label='new-candidate'`, `alert_type=null`, pushing only `Buy` not flagged
within 7 days. Ingest skips are logged the same way (FR15).
