"""NSE shadow verdict pilot orchestrator (NSE, non-production, design §16).

A second, fully independent shadow track from scripts/run_shadow.py (US/CA):
same position-aware prompt variant, same wallet-walk shape, but scoped to NSE
watchlist tickers only, writing to its own table (call_log_shadow_nse), gated
by its own kill switch (config.SHADOW_NSE_ENABLED) and NSE market hours
(config.is_nse_open), and drawing from NSE's own model bucket
(config.nse_models()) instead of the US/TSX watchlist pair.

Deliberately NOT factored into a shared run_shadow.py helper for INC-1 (dev
call, design §16.3): this module duplicates run_shadow.py's cycle shape ---
consistent with how this codebase already keeps US/TSX and NSE as separate-ish
code paths (run_hourly.py._sessions) rather than a heavy shared abstraction.
The wallet-walk state machine is the one piece design §17.2 requires to become
a single shared function (wallet_sim.walk) -- that refactor (and the shared
evaluation harness) is INC-2 scope, not this increment.

Runs as its OWN process, in its OWN GitHub Actions step, STRICTLY AFTER both
the production step and the US/CA shadow step (see
.github/workflows/hourly-watchlist.yml) -- so a hang/exception here has no code
path back to either of them. main() wraps everything in a top-level try/except
and always exits 0, and the workflow step is `continue-on-error` with a
`timeout-minutes` bound, so an NSE shadow failure can never block, delay, or
fail the production dispatch or the US/CA shadow track under any failure mode
(FR37, NFR6, load-bearing #11).

What it does each cycle (all-or-nothing per cycle):
  1. Kill switch (config.SHADOW_NSE_ENABLED) + the SAME NSE market-open gate
     production uses (config.is_nse_open), or config.FORCE_RUN. Closed and not
     forced -> no-op.
  2. Reuse THIS cycle's production NSE market-data snapshot: read the call_log
     rows production just wrote for the NSE watchlist tickers (latest per
     ticker within a sub-cadence window) and rebuild each ticker's market data
     from them. Same data as production => the pilot isolates the
     position-awareness variable (FR34).
  3. Derive each ticker's shadow position ONLY from call_log_shadow_nse's own
     history via the wallet-walk (Buy: flat->holding; Sell: holding->flat;
     Hold: no-op) -- never call_log, never call_log_shadow (FR33).
  4. ONE position-aware batch Gemini call for all NSE tickers
     (shadow.judge_batch_shadow(items, models=config.nse_models())).
  5. Write every ticker's shadow row for the cycle in ONE atomic insert into
     call_log_shadow_nse (never a partial batch).

No alerts ever: this module does not import or call notify at all (FR36).
Position state is derived fresh from the DB every cycle, so an interrupted/
missed cycle needs no recovery -- the next cycle just reads the last
successfully written rows. Missed cycles are logged gaps, never backfilled.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

import config
import state
import shadow
import wallet_sim

NSE_MARKETS = {"NSE"}


def _usable_market_data(row: dict) -> dict | None:
    """Rebuild the market-data dict for the shadow prompt from a production
    call_log row's data_snapshot, or None if the row has no usable price
    (a no_data skip row, or anything missing a price). The snapshot already
    carries every field shadow._shadow_ticker_block needs except the ticker."""
    snap = row.get("data_snapshot") or {}
    if snap.get("price") is None:
        return None
    return {**snap, "ticker": row["ticker"]}


def _latest_production_snapshots(sb, tickers: list[str], since_iso: str) -> dict:
    """Latest production watchlist call_log row per ticker within the window
    (i.e. the rows production wrote THIS cycle). Returns {ticker: row}."""
    rows = (sb.table("call_log").select("ticker,timestamp,data_snapshot")
            .eq("label", "watchlist").in_("ticker", tickers)
            .gte("timestamp", since_iso)
            .order("timestamp", desc=True).execute().data or [])
    latest: dict = {}
    for r in rows:                      # rows are newest-first; keep the first seen per ticker
        latest.setdefault(r["ticker"], r)
    return latest


def _derive_shadow_positions(sb, tickers: list[str]) -> dict:
    """Today's position per ticker, from call_log_shadow_nse's own history only.

    Derived solely from call_log_shadow_nse -- never from real call_log or
    call_log_shadow. Empty history => flat. The Buy/Sell/Hold state machine
    itself lives in wallet_sim.walk (design.md §17.2) so this orchestrator and
    eval_shadow.py's harness can never silently diverge.
    Returns {ticker: {"state": "holding"|"flat", "entry_price", "entry_date"}}.
    """
    rows = (sb.table("call_log_shadow_nse")
            .select("ticker,verdict,timestamp,data_snapshot")
            .eq("label", "watchlist").in_("ticker", tickers)
            .order("timestamp", desc=False).execute().data or [])

    hist: dict = {t: [] for t in tickers}
    for r in rows:
        if r["ticker"] in hist:
            hist[r["ticker"]].append(r)

    positions: dict = {}
    for t in tickers:
        walk_rows = [
            {"verdict": r.get("verdict"), "timestamp": r.get("timestamp"),
             "price": (r.get("data_snapshot") or {}).get("price")}
            for r in hist[t]
        ]
        positions[t] = wallet_sim.walk(walk_rows)["position"]
    return positions


def _run_cycle() -> None:
    now = datetime.now(timezone.utc)
    now_ist = datetime.now(config.NSE_MARKET_TZ)

    # Kill switch (defensive; the workflow `if:` also gates the whole step).
    if not config.SHADOW_NSE_ENABLED:
        print("[shadow-nse] SHADOW_NSE_ENABLED=false — NSE shadow track disabled, no-op.")
        return

    # SAME NSE market-open gate production uses. Closed and not forced -> no-op,
    # exactly like production's NSE group (FR39).
    if not (config.is_nse_open(now_ist) or config.FORCE_RUN):
        print(f"[shadow-nse] NSE closed (force_run={config.FORCE_RUN}) — no-op. "
              f"{now:%Y-%m-%d %H:%M:%S} UTC / {now_ist:%H:%M %Z}")
        return

    config.require_secrets()
    sb = state.client()

    tickers = sorted(
        r["ticker"] for r in state.get_watchlist(sb)
        if (r.get("market") or "US") in NSE_MARKETS
    )
    if not tickers:
        print("[shadow-nse] no NSE watchlist tickers — nothing to do.")
        return

    # Reuse THIS cycle's production NSE snapshot (same underlying market data, FR34).
    since_iso = (now - timedelta(minutes=config.SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN)).isoformat()
    prod = _latest_production_snapshots(sb, tickers, since_iso)
    positions = _derive_shadow_positions(sb, tickers)

    items, skipped = [], []
    for t in tickers:
        row = prod.get(t)
        data = _usable_market_data(row) if row else None
        if data is None:
            # In-window production row exists but is unusable (no price / no_data),
            # or production wrote nothing for this ticker this cycle. Record a
            # queryable skip trace (a Hold -> no-op in the walk); never silent.
            reason = ("no usable market data in production snapshot"
                      if row else "no production snapshot in window (cycle gap)")
            skipped.append((t, reason))
            continue
        items.append({"data": data, "shadow_pos": positions[t]})

    if not items:
        # No production data at all this cycle -> a gap. Do NOT fabricate a shadow
        # call or backfill; log it and move on (self-healing next cycle).
        print(f"[shadow-nse] no usable production snapshot for any NSE ticker in the last "
              f"{config.SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN} min — cycle gap, skipping. "
              f"({len(skipped)} tickers unavailable)")
        return

    print(f"[shadow-nse] NSE {len(items)} tickers judged, {len(skipped)} skipped "
          f"(variant={config.SHADOW_NSE_PROMPT_VARIANT}, model_order via NSE_GEMINI_MODEL)")

    # ONE position-aware batch call, NSE's own model bucket (§16.2).
    verdicts = shadow.judge_batch_shadow(items, models=config.nse_models())

    # Assemble every ticker's row, then write the whole cycle in ONE atomic insert.
    out_rows, outcomes = [], Counter()
    for it in items:
        t = it["data"]["ticker"]
        ai = verdicts.get(t) or {"verdict": "Hold", "confidence": None,
                                 "rationale": f"No verdict returned for {t}; fail-safe Hold.",
                                 "raw_model_response": "", "parse_status": "failed",
                                 "model_used": None, "usage": None, "fallback_from": None}
        pos = it["shadow_pos"]
        out_rows.append({
            "ticker": t,
            "verdict": ai["verdict"],
            "rationale": ai.get("rationale"),
            "label": "watchlist",
            "alert_type": None,      # shadow never alerts
            "alerted": False,
            "data_snapshot": state._snapshot(it["data"], ai),
            "prompt_variant": config.SHADOW_NSE_PROMPT_VARIANT,
            "shadow_position_state": pos,
        })
        outcomes[ai.get("parse_status") or "?"] += 1
        print(f"  {t:9} {ai['verdict']:4} ({ai.get('confidence') or '-'}) "
              f"[{ai.get('parse_status')}/{ai.get('model_used', '?')}] "
              f"pos={pos['state']}"
              + (f"@{pos['entry_price']}" if pos["state"] == "holding" else ""))

    for t, reason in skipped:
        pos = positions[t]
        out_rows.append({
            "ticker": t, "verdict": "Hold",
            "rationale": f"Shadow skip: {reason}.",
            "label": "watchlist", "alert_type": None, "alerted": False,
            "data_snapshot": {"parse_status": "no_data", "notes": [reason]},
            "prompt_variant": config.SHADOW_NSE_PROMPT_VARIANT,
            "shadow_position_state": pos,
        })
        print(f"  {t:9} SKIP ({reason})")

    # Atomic per-cycle write: one INSERT for all rows -> fully recorded or not at
    # all, so a mid-write death can never leave a partial batch that would corrupt
    # the derived position state for some tickers but not others.
    sb.table("call_log_shadow_nse").insert(out_rows).execute()
    print(f"[shadow-nse] wrote {len(out_rows)} rows atomically "
          f"(judged={len(items)}, skipped={len(skipped)}). verdicts={dict(outcomes)}")


def main() -> None:
    # Hard isolation belt: NOTHING in the NSE shadow track may propagate out. Any
    # failure is logged explicitly (no silent failures) and swallowed; the process
    # exits cleanly so it can never affect production or the US/CA shadow track.
    # Catches SystemExit too (not just Exception): config.require_secrets() raises
    # SystemExit on a missing secret, which `except Exception` alone would miss
    # (SystemExit is a BaseException) — a real gap, verified by smoke test, in
    # the always-exits-0 guarantee this function exists to provide.
    try:
        _run_cycle()
    except (Exception, SystemExit) as e:
        print(f"[shadow-nse] ERROR (cycle skipped, production/US-CA-shadow unaffected): "
              f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
