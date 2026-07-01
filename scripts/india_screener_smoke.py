"""India (NSE) screener smoke test — Phase 6 D5 prep (mirrors phase4_screener_smoke).

SD §12 D5 says NSE discovery reuses the prefilter pipeline with a `region=in`
EquityQuery "mirroring the existing region=ca". But only US + region=ca were ever
smoke-tested (phase4_screener_smoke). Before wiring India into prefilter we must
confirm, on a runner where Yahoo is reachable:
  1. does a region=in gainers/losers EquityQuery return at all;
  2. what `marketCap` magnitudes come back — they're in INR, so the USD $2B
     DISCOVERY_MIN_MARKET_CAP gate is meaningless as-is and needs recalibrating;
  3. what `exchange` / `fullExchangeName` tag NSE listings carry (for the
     allow-list + _market_for mapping);
  4. that price/volume/change fields the quality gate + signals need are present.

Run on a GitHub-hosted runner (Yahoo is egress-blocked in the dev container):
    pip install -U yfinance
    python scripts/india_screener_smoke.py
"""

import yfinance as yf

NEED_FIELDS = ["symbol", "regularMarketChangePercent", "marketCap",
               "regularMarketPrice", "regularMarketVolume"]

# INR reference points to make the marketCap magnitudes legible in the log.
# ~83 INR/USD at time of writing: $2B ≈ ₹1.66e11; ₹1e11 = ₹10,000 crore.
USDINR = 83.0


def _quotes(res):
    if isinstance(res, dict):
        return res.get("quotes") or res.get("records") or [], list(res.keys())
    if isinstance(res, list):
        return res, ["<list>"]
    return [], [f"<{type(res).__name__}>"]


def _in_query(op: str, pct: float):
    EQ = getattr(yf, "EquityQuery", None)
    if EQ is None:
        from yfinance import EquityQuery as EQ  # noqa
    return EQ("and", [
        EQ(op, ["percentchange", pct]),
        EQ("eq", ["region", "in"]),
        EQ("gt", ["intradaymarketcap", 10_000_000_000]),   # ₹1,000 cr floor just for the probe
        EQ("gt", ["intradayprice", 50]),                   # ₹50 floor just for the probe
    ])


def run(label, query, **kw):
    try:
        res = yf.screen(query, **kw)
    except Exception as e:
        print(f"[{label}] ERROR: {type(e).__name__}: {str(e)[:160]}")
        return None
    quotes, topkeys = _quotes(res)
    print(f"[{label}] top-level keys: {topkeys}  | count: {len(quotes)}")
    if not quotes:
        print(f"[{label}] no quotes returned")
        return quotes
    q0 = quotes[0]
    missing = [f for f in NEED_FIELDS if f not in q0]
    print(f"[{label}] sample field keys: {sorted(q0.keys())[:30]}")
    if missing:
        print(f"[{label}] MISSING needed fields: {missing}")
    print(f"[{label}] top 8 (marketCap shown in INR and ≈ USD):")
    for q in quotes[:8]:
        mc = q.get("marketCap")
        mc_usd = f"${mc/USDINR/1e9:.1f}B" if isinstance(mc, (int, float)) else "—"
        print(f"    {str(q.get('symbol')):16} "
              f"chg={q.get('regularMarketChangePercent')}  "
              f"mcap={mc} (≈{mc_usd})  "
              f"px={q.get('regularMarketPrice')} {q.get('currency')}  "
              f"vol={q.get('regularMarketVolume')}  "
              f"exch={q.get('exchange')} / {q.get('fullExchangeName')}")
    return quotes


print("yfinance version:", getattr(yf, "__version__", "?"))
print("has yf.screen:", hasattr(yf, "screen"))
print("-" * 78)

g = run("in_gainers", _in_query("gt", 3), sortField="percentchange", sortAsc=False, size=50)
print("-" * 78)
l = run("in_losers", _in_query("lt", -3), sortField="percentchange", sortAsc=True, size=50)
print("-" * 78)

# Exchange-tag census: which exchange strings show up, so we know what to allow.
allq = (g or []) + (l or [])
if allq:
    exch = {}
    for q in allq:
        k = f"{q.get('exchange')} / {q.get('fullExchangeName')}"
        exch[k] = exch.get(k, 0) + 1
    print("Exchange tags seen (NSE listings expected):")
    for k, n in sorted(exch.items(), key=lambda x: -x[1]):
        print(f"    {n:3}x  {k}")
    caps = [q.get("marketCap") for q in allq if isinstance(q.get("marketCap"), (int, float))]
    if caps:
        caps.sort()
        print(f"marketCap (INR) range across {len(caps)} quotes: "
              f"min={caps[0]:.3e}  median={caps[len(caps)//2]:.3e}  max={caps[-1]:.3e}")
        print(f"  → USD-equiv: min≈${caps[0]/USDINR/1e9:.2f}B  "
              f"median≈${caps[len(caps)//2]/USDINR/1e9:.2f}B  max≈${caps[-1]/USDINR/1e9:.2f}B")
    print("\nDECISION INPUTS for SD §12 D5:")
    print("  - region=in screener usable:", "YES" if allq else "NO")
    print("  - Recalibrate DISCOVERY_MIN_MARKET_CAP for INR (per-market cap), and add the")
    print("    NSE exchange tag(s) above to DISCOVERY_ALLOWED_EXCHANGES + _market_for.")
else:
    print("region=in returned nothing from either screen — SD §12 D5 'mirrors region=ca' is")
    print("NOT confirmed; report back before wiring India into prefilter.")
