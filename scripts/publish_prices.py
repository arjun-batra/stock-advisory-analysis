"""Publish a same-origin prices.json for the read-only dashboard (issue #18 fallback).

The #18 smoke test proved the browser cannot fetch Yahoo directly (CORS-blocked
for every market). So instead of a client-side Yahoo fetch, this runs on a GitHub
Actions runner — where Yahoo IS reachable — reads the watchlist, fetches the
current price + 1d change for each ticker via `ingest.get_price_only()` (REV-043,
a narrower fetch than the AI-judgment path's `get_market_data()` — this script
doesn't need history/fundamentals/news, just price context), and writes
pages/prices.json. The committing workflow refreshes it on the market cadence and
the dashboard reads it same-origin (relative URL, no CORS). Freshness is therefore
"as of the last publish run" (minutes), not tick-live — the accepted #18
fallback, and the dashboard's "prices updated Ns ago" clock reads `generated_at`
so it stays honest about the real price age.

Only SUPABASE_URL + SUPABASE_SECRET_KEY are needed (no Gemini) — this does no AI
work, it just reads the watchlist and prices it.
"""

import json
import os
import time
from datetime import datetime, timezone

import config
import ingest
import state

OUT_PATH = "pages/prices.json"


def _num(v):
    return v if isinstance(v, (int, float)) else None


def main() -> None:
    config.require_secrets("SUPABASE_URL", "SUPABASE_SECRET_KEY")

    sb = state.client()
    watchlist = state.get_watchlist(sb)
    prices: dict[str, dict] = {}
    skipped = 0
    for i, row in enumerate(watchlist):
        ticker = row["ticker"]
        if i > 0:
            time.sleep(config.YF_PACING_SECONDS)   # be polite to Yahoo, same pacing as the ingest loops
        try:
            data = ingest.get_price_only(ticker)
            if data["has_price"]:
                prices[ticker] = {
                    "price": _num(data["price"]),
                    "chg": _num(data["pct_change_1d"]),
                    "market": data["market"],
                    "currency": (data.get("fundamentals") or {}).get("currency"),
                }
            else:
                print(f"  skip {ticker}: no price ({'; '.join(data['notes'])})")
                skipped += 1
        except Exception as e:
            print(f"  skip {ticker}: {type(e).__name__}: {e}")
            skipped += 1

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "prices": prices}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    # Heartbeat (NFR2; 2026-07-03 review). Without it a silently-dead
    # publish-prices pipeline only showed as an ever-growing "prices updated Nh
    # ago" on the dashboard — visible if someone happened to look, alerting no
    # one. check_pipeline_health() now watches this key during either session.
    status = "partial" if (skipped or config.TUNABLES_DEGRADED) else "ok"
    state.write_heartbeat(sb, "publish-prices", status)
    print(f"Wrote {OUT_PATH} with {len(prices)}/{len(watchlist)} tickers priced "
          f"at {out['generated_at']} [{status}]")


if __name__ == "__main__":
    main()
