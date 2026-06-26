"""Hourly watchlist orchestrator (solution design 6.1).

Wakes up, checks the market is actually open (ET), ingests every watchlist
ticker, then makes ONE batched AI call for the whole list (was one call per
ticker — cut to stay well under the Gemini free-tier daily request cap), and
walks the results through the single-rule change logic (design 6.3). One bad
ticker is skipped-with-log and never takes down the run for the others. Writes a
heartbeat at the end so a missed run is visible (NFR2).
"""

from datetime import datetime, timezone
import time

import config
import ingest
import ai_judge
import state
import notify


def main() -> None:
    now_et = datetime.now(config.MARKET_TZ)
    now = datetime.now(timezone.utc)
    market_open = config.is_market_open(now_et)

    # Gate-decision audit line (issue #7). Makes every run self-explaining in the
    # Actions log: was this an in-hours run or a FORCE_RUN, what did the gate see,
    # and are alerts live. A FORCE_RUN with ALERTS_ENABLED=true fires REAL ntfy
    # pushes regardless of market hours — this line is the trail that tells a
    # deliberate off-hours test push apart from a gate defect (the #7 confusion).
    print(f"[gate] market_open={market_open} force_run={config.FORCE_RUN} "
          f"alerts={'ON' if config.ALERTS_ENABLED else 'DRY-RUN'} "
          f"| {now:%Y-%m-%d %H:%M:%S} UTC / {now_et:%H:%M:%S %Z}")

    if not market_open and not config.FORCE_RUN:
        print(f"Market closed at {now_et:%Y-%m-%d %H:%M %Z} - no-op, exit. "
              f"(workflow_dispatch with force_run=true overrides)")
        return
    if not market_open:
        print("FORCE_RUN: market closed, running anyway against last close (test/backfill). "
              "NOTE: with ALERTS_ENABLED=true this sends REAL pushes — set it false for a silent test.")

    config.require_secrets()
    sb = state.client()
    notifier = notify.get_notifier()

    watchlist = state.get_watchlist(sb)
    holdings = state.get_holdings_map(sb)
    print(f"Hourly run: {len(watchlist)} tickers, alerts={'ON' if config.ALERTS_ENABLED else 'DRY-RUN'}")

    outcomes = {}

    # --- Phase 1: ingest everything (yfinance only, no AI/quota cost) ---
    # Paced apart + backoff-retried inside ingest to avoid Yahoo rate-limiting
    # the back-to-back loop (issue #1).
    items = []   # list of (wl_row, data, position)
    for i, row in enumerate(watchlist):
        ticker = row["ticker"]
        if i > 0:
            time.sleep(config.YF_PACING_SECONDS)
        try:
            data = ingest.get_market_data(ticker)
            if not data["has_price"]:
                reason = "rate-limited" if data.get("rate_limited") else "no data"
                print(f"  skip {ticker} ({reason}): {'; '.join(data['notes'])}")  # skip-with-log (7.5)
                state.log_skip(sb, ticker, data["notes"], rate_limited=data.get("rate_limited", False))
                outcomes["skip"] = outcomes.get("skip", 0) + 1
                continue
            position = state.build_position(holdings.get(ticker), data)
            items.append((row, data, position))
        except Exception as e:
            print(f"  ERROR {ticker} (ingest): {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1

    # --- Phase 2: ONE batched AI call for all tickers ---
    verdicts = ai_judge.judge_batch([{"data": d, "position": p} for (_, d, p) in items])

    # --- Phase 3: per-ticker single-rule change detection + logging ---
    for row, data, position in items:
        ticker = row["ticker"]
        try:
            ai = verdicts.get(ticker) or {
                "verdict": "Hold",
                "rationale": "No verdict returned for this ticker; fail-safe Hold.",
                "raw_model_response": "", "parse_status": "failed",
            }
            result = state.process_ticker(sb, notifier, row, data, ai, now)
            tag = "NEW" if data["is_new"] else ""
            print(f"  {ticker:9} {ai['verdict']:4} -> {result} "
                  f"[{ai['parse_status']}/{ai.get('model_used', '?')}] {tag}")
            outcomes[result] = outcomes.get(result, 0) + 1
        except Exception as e:
            print(f"  ERROR {ticker}: {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1

    # Heartbeat reflects whether the run was fully clean (issue #2): "partial"
    # when any ticker was skipped or errored, "ok" only when all succeeded.
    degraded = outcomes.get("skip", 0) + outcomes.get("error", 0)
    status = "partial" if degraded else "ok"
    state.write_heartbeat(sb, "hourly-watchlist", status)
    print(f"Done [{status}]. {dict(outcomes)}")


if __name__ == "__main__":
    main()
