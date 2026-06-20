"""Hourly watchlist orchestrator (solution design 6.1).

Wakes up, checks the market is actually open (ET), then walks the watchlist:
ingest -> AI verdict -> change/cooldown/reminder logic -> log. One bad ticker is
skipped-with-log and never takes down the run for the others. Writes a heartbeat
at the end so a missed run is visible (NFR2). Phase 2: no real pushes.
"""

import time
from datetime import datetime, timezone

import config
import ingest
import ai_judge
import state
import notify


def main() -> None:
    now_et = datetime.now(config.MARKET_TZ)
    if not config.is_market_open(now_et):
        print(f"Market closed at {now_et:%Y-%m-%d %H:%M %Z} - no-op, exit.")
        return

    config.require_secrets()
    sb = state.client()
    notifier = notify.get_notifier()

    watchlist = state.get_watchlist(sb)
    holdings = state.get_holdings_map(sb)
    now = datetime.now(timezone.utc)
    print(f"Hourly run: {len(watchlist)} tickers, alerts={'ON' if config.ALERTS_ENABLED else 'DRY-RUN'}")

    outcomes = {}
    for row in watchlist:
        ticker = row["ticker"]
        try:
            data = ingest.get_market_data(ticker)
            if not data["has_price"]:
                print(f"  skip {ticker}: {'; '.join(data['notes'])}")  # skip-with-log (7.5)
                outcomes["skip"] = outcomes.get("skip", 0) + 1
                continue

            position = state.build_position(holdings.get(ticker), data)
            ai = ai_judge.judge(data, position)
            result = state.process_ticker(sb, notifier, row, data, ai, now)

            tag = "NEW" if data["is_new"] else ""
            print(f"  {ticker:9} {ai['verdict']:4} -> {result} "
                  f"[{ai['parse_status']}] {tag}")
            outcomes[result] = outcomes.get(result, 0) + 1
        except Exception as e:
            # one ticker must never kill the run for the rest
            print(f"  ERROR {ticker}: {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1

        time.sleep(config.GEMINI_PACING_SECONDS)

    state.write_heartbeat(sb, "hourly-watchlist", "ok")
    print(f"Done. {dict(outcomes)}")


if __name__ == "__main__":
    main()
