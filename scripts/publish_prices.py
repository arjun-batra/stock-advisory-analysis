"""Publish a same-origin prices.json for the read-only dashboard (issue #18 fallback).

The #18 smoke test proved the browser cannot fetch Yahoo directly (CORS-blocked
for every market). So instead of a client-side Yahoo fetch, this runs on a GitHub
Actions runner — where Yahoo IS reachable — reads the watchlist, fetches the
current price + 1d change for each ticker via the same yfinance path the pipeline
already uses, and writes pages/prices.json. The committing workflow refreshes it
on the market cadence and the dashboard reads it same-origin (relative URL, no
CORS). Freshness is therefore "as of the last publish run" (minutes), not
tick-live — the accepted #18 fallback, and the dashboard's "prices updated Ns
ago" clock reads `generated_at` so it stays honest about the real price age.

Only SUPABASE_URL + SUPABASE_SECRET_KEY are needed (no Gemini) — this does no AI
work, it just reads the watchlist and prices it.
"""

import json
import os
import time
from datetime import datetime, timezone

import ingest
import state

OUT_PATH = "pages/prices.json"


def _num(v):
    return v if isinstance(v, (int, float)) else None


def main() -> None:
    missing = [n for n in ("SUPABASE_URL", "SUPABASE_SECRET_KEY") if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"Missing required environment secrets: {', '.join(missing)}")

    sb = state.client()
    watchlist = state.get_watchlist(sb)
    prices: dict[str, dict] = {}
    for i, row in enumerate(watchlist):
        ticker = row["ticker"]
        if i > 0:
            time.sleep(2)   # be polite to Yahoo, same posture as the ingest loop
        try:
            data = ingest.get_market_data(ticker)
            if data["has_price"]:
                prices[ticker] = {
                    "price": _num(data["price"]),
                    "chg": _num(data["pct_change_1d"]),
                    "market": data["market"],
                    "currency": (data.get("fundamentals") or {}).get("currency"),
                }
            else:
                print(f"  skip {ticker}: no price ({'; '.join(data['notes'])})")
        except Exception as e:
            print(f"  skip {ticker}: {type(e).__name__}: {e}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "prices": prices}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"Wrote {OUT_PATH} with {len(prices)}/{len(watchlist)} tickers priced "
          f"at {out['generated_at']}")


if __name__ == "__main__":
    main()
