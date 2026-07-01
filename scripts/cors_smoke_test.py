#!/usr/bin/env python3
"""
Issue #18 - Browser -> Yahoo CORS feasibility smoke test.

SD §13 / UI-handoff v3 (Deliverable 3, freshness signal #1) assume the read-only
dashboard fetches the *live current price* client-side, straight from Yahoo's HTTP
endpoints in the browser. The static page can't run the Python yfinance wrapper,
and the anon/publishable key carries no price data (RLS-scoped to call_log +
watchlist per #16), so the browser has to hit Yahoo itself.

This has never been proven. Yahoo's API is unofficial with no published CORS
policy. If Yahoo's endpoints don't return Access-Control-Allow-Origin for a
foreign origin, a browser cross-origin fetch is blocked and the "live price"
freshness signal fails -- which would force a design change to SD §13 (a
server-side relay, or reusing call_log's last-known price with a staleness note).

This test runs on a GitHub-hosted runner (which CAN reach Yahoo -- the container
this was authored in has Yahoo egress-blocked by org policy, so the test must run
here). It does a *real* headless-Chromium fetch from a plain static page served
over http://127.0.0.1 (a foreign, non-null origin, standing in for the GitHub
Pages origin), against the v8/finance/chart price endpoint for one ticker per
market: AAPL (US), RY.TO (TSX), RELIANCE.NS (NSE).

The runner-side curl header inspection in the workflow is the authoritative
determinant (does Yahoo send Access-Control-Allow-Origin?); this browser test is
the end-to-end confirmation the issue's acceptance criteria ask for.

Exit code 0 = at least one market's live-price fetch succeeded in-browser
(direct fetch viable). Exit code 2 = every market CORS-blocked in-browser
(direct fetch NOT viable -> #18 blocked -> SD §13 needs a fallback).
"""

import http.server
import os
import socketserver
import sys
import tempfile
import threading

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Missing dependency. Run:  pip install playwright && playwright install chromium")

# One ticker per market. chart endpoint returns the live price in
# result.meta.regularMarketPrice and needs no crumb/cookie (unlike v7 quote /
# v10 quoteSummary), so it is the endpoint the dashboard live-price read would use.
TICKERS = [
    ("US", "AAPL"),
    ("TSX", "RY.TO"),
    ("NSE", "RELIANCE.NS"),
]

# The real deployment origin (GitHub Pages). Recorded for context; the browser's
# actual Origin below is http://127.0.0.1:<port>. Yahoo's CORS response is not
# origin-specific (it either sends ACAO:* or nothing), so a localhost origin is a
# faithful stand-in -- and the workflow's curl step probes this exact origin.
PROD_ORIGIN = "https://arjun-batra.github.io"

FETCH_JS = """
async (url) => {
  try {
    const r = await fetch(url, { method: 'GET' });
    const t = await r.text();
    let price = null;
    try { price = JSON.parse(t)?.chart?.result?.[0]?.meta?.regularMarketPrice ?? null; } catch (e) {}
    return { ok: true, status: r.status, price, sample: t.slice(0, 80) };
  } catch (e) {
    // A CORS block surfaces here as "TypeError: Failed to fetch".
    return { ok: false, error: String(e) };
  }
}
"""


def _serve(dirpath):
    os.chdir(dirpath)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def main():
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "index.html"), "w") as f:
        f.write("<!doctype html><meta charset=utf-8><title>CORS test</title><h1>cors probe</h1>")
    httpd, port = _serve(tmp)
    origin = f"http://127.0.0.1:{port}"
    print(f"Issue #18 browser->Yahoo CORS smoke test")
    print(f"Serving static page from {origin}  (stand-in for {PROD_ORIGIN})\n")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errs = []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.goto(f"{origin}/index.html")
        for market, sym in TICKERS:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=1m"
            res = page.evaluate(FETCH_JS, url)
            results.append((market, sym, res))
            if res.get("ok"):
                print(f"[FETCH OK ] {market:4} {sym:14} status={res.get('status')} "
                      f"price={res.get('price')}")
            else:
                print(f"[BLOCKED  ] {market:4} {sym:14} {res.get('error')}")
        browser.close()

    print("\n" + "=" * 64)
    ok = [r for r in results if r[2].get("ok")]
    blocked = [r for r in results if not r[2].get("ok")]
    print(f"  in-browser fetch:  {len(ok)} OK   {len(blocked)} BLOCKED   (of {len(results)})")
    print("=" * 64)
    if not ok:
        print("\n  VERDICT: browser->Yahoo direct fetch is CORS-BLOCKED for every market.")
        print("  #18 is BLOCKED. SD §13 live-price read cannot be a direct browser fetch;")
        print("  a fallback is required (server-side relay, or call_log last-known price).")
        return 2
    if blocked:
        print("\n  VERDICT: partial -- some markets fetched, some blocked. Investigate per-market.")
        return 0
    print("\n  VERDICT: browser->Yahoo direct fetch WORKS for all markets. SD §13 stands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
