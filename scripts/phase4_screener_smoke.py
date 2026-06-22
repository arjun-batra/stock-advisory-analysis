"""Phase 4 screener smoke test (mirrors the Phase 0 yfinance smoke test).

Discovery (reactive movers) is built on Yahoo's screener via yfinance's
`yf.screen()`. That endpoint is unofficial, so before building the prefilter on
top of it we confirm: it returns, which predefined queries exist, what fields
come back (so we know what to quality-gate on), and whether Canada/TSX coverage
works via a custom region=ca query or whether v1 is US-only.

Run it where Yahoo is reachable (locally or a one-off Actions run), NOT in the
locked dev sandbox:
    pip install -U yfinance
    python phase4_screener_smoke.py

The screener needs a reasonably recent yfinance (>=~0.2.50). The version is
printed first; if `yf.screen` is missing, upgrade.
"""

import yfinance as yf

NEED_FIELDS = ["symbol", "regularMarketChangePercent", "marketCap",
               "regularMarketPrice", "regularMarketVolume"]

results = {}   # label -> ("PASS"|"PARTIAL"|"FAIL", note)


def _quotes(res):
    if isinstance(res, dict):
        return res.get("quotes") or res.get("records") or [], list(res.keys())
    if isinstance(res, list):
        return res, ["<list>"]
    return [], [f"<{type(res).__name__}>"]


def run(label, query, **kw):
    try:
        res = yf.screen(query, **kw)
    except Exception as e:
        print(f"[{label}] ERROR: {type(e).__name__}: {str(e)[:160]}")
        results[label] = ("FAIL", f"{type(e).__name__}")
        return
    quotes, topkeys = _quotes(res)
    print(f"[{label}] top-level keys: {topkeys}  | count: {len(quotes)}")
    if not quotes:
        results[label] = ("FAIL", "no quotes returned")
        return
    q0 = quotes[0]
    have = [f for f in NEED_FIELDS if f in q0]
    missing = [f for f in NEED_FIELDS if f not in q0]
    print(f"[{label}] sample field keys: {sorted(q0.keys())[:25]}")
    if missing:
        print(f"[{label}] MISSING needed fields: {missing}")
    print(f"[{label}] top 5:")
    for q in quotes[:5]:
        print(f"    {str(q.get('symbol')):10} "
              f"chg={q.get('regularMarketChangePercent')}  "
              f"mcap={q.get('marketCap')}  "
              f"px={q.get('regularMarketPrice')}  "
              f"vol={q.get('regularMarketVolume')}  "
              f"exch={q.get('fullExchangeName') or q.get('exchange')}")
    results[label] = ("PASS" if not missing else "PARTIAL",
                      f"{len(quotes)} quotes, missing={missing or 'none'}")


print("yfinance version:", getattr(yf, "__version__", "?"))
print("has yf.screen:", hasattr(yf, "screen"))
print("-" * 70)

# 1) what predefined screens exist on this version
try:
    predefined = list(yf.PREDEFINED_SCREENER_QUERIES.keys())
    print("PREDEFINED screens available:", predefined)
except Exception as e:
    print("PREDEFINED_SCREENER_QUERIES error:", type(e).__name__, e)
print("-" * 70)

# 2) the three US predefined movers screens we plan to use
for s in ("day_gainers", "day_losers", "most_actives"):
    run(s, s, size=50)
    print("-" * 70)

# 3) custom CANADA query — does region=ca work? (decides US-only vs US+CA for v1)
try:
    EQ = getattr(yf, "EquityQuery", None)
    if EQ is None:
        from yfinance import EquityQuery as EQ  # noqa
    ca = EQ("and", [
        EQ("gt", ["percentchange", 3]),
        EQ("eq", ["region", "ca"]),
        EQ("gt", ["intradaymarketcap", 1_000_000_000]),
        EQ("gt", ["intradayprice", 5]),
    ])
    run("custom_ca_gainers", ca, sortField="percentchange", sortAsc=False, size=50)
except Exception as e:
    print(f"[custom_ca_gainers] SETUP ERROR: {type(e).__name__}: {str(e)[:160]}")
    results["custom_ca_gainers"] = ("FAIL", f"setup: {type(e).__name__}")
print("-" * 70)

# summary
print("SUMMARY")
for label, (verdict, note) in results.items():
    print(f"  {verdict:8} {label:20} {note}")
us_ok = all(results.get(s, ("FAIL",))[0] in ("PASS", "PARTIAL")
            for s in ("day_gainers", "day_losers", "most_actives"))
ca_ok = results.get("custom_ca_gainers", ("FAIL",))[0] in ("PASS", "PARTIAL")
print("-" * 70)
print(f"US movers usable:    {'YES' if us_ok else 'NO'}")
print(f"Canada usable:       {'YES' if ca_ok else 'NO (v1 would be US-only)'}")
