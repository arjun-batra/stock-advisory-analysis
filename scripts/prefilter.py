"""Discovery prefilter (Phase 4) — reactive movers via Yahoo's screener.

Pulls the day's gainers / losers / most-active (US predefined screens + a custom
region=ca query for Canada), applies quality gates, tags each survivor with the
signal(s) it tripped (mover / volume spike / 52-week extreme), excludes watchlist
names up front, ranks, and returns a shortlist for the AI.

Screener shape was verified by scripts/phase4_screener_smoke.py: US gainers/
losers/most-active and a custom region=ca query all return, with marketCap,
regularMarketPrice, regularMarketChangePercent, regularMarketVolume,
averageDailyVolume3Month, and exchange populated; Canadian symbols come back
already suffixed (e.g. SHOP.TO) and exchange tags market cleanly (Toronto vs
NYSE/Nasdaq). The 52-week fields are used best-effort — applied only if present.

The screener is unofficial Yahoo, so every screen call is wrapped: one failing
screen degrades the day's coverage rather than killing discovery.
"""

import time

import yfinance as yf

import config


def _quotes(res) -> list[dict]:
    if isinstance(res, dict):
        return res.get("quotes") or res.get("records") or []
    return res or []


def _screen(label: str, query, **kw) -> list[dict]:
    try:
        return _quotes(yf.screen(query, **kw))
    except Exception as e:
        print(f"  [prefilter] {label} screen error: {type(e).__name__}: {str(e)[:120]}")
        return []


def _ca_query(op: str, pct: float):
    EQ = getattr(yf, "EquityQuery", None)
    if EQ is None:
        from yfinance import EquityQuery as EQ  # noqa
    return EQ("and", [
        EQ(op, ["percentchange", pct]),
        EQ("eq", ["region", "ca"]),
        EQ("gt", ["intradaymarketcap", config.DISCOVERY_MIN_MARKET_CAP]),
        EQ("gt", ["intradayprice", config.DISCOVERY_MIN_PRICE]),
    ])


def _passes_quality(q: dict) -> bool:
    if (q.get("marketCap") or 0) < config.DISCOVERY_MIN_MARKET_CAP:
        return False
    if (q.get("regularMarketPrice") or 0) < config.DISCOVERY_MIN_PRICE:
        return False
    if (q.get("regularMarketVolume") or 0) < config.DISCOVERY_MIN_VOLUME:
        return False
    if (q.get("exchange") or "") not in config.DISCOVERY_ALLOWED_EXCHANGES:
        return False
    return True


def _signals(q: dict) -> list[str]:
    """Which discovery signals this quote trips (mover / volume / 52w-high|low)."""
    sig = []
    chg = q.get("regularMarketChangePercent")
    if chg is not None and (chg >= config.DISCOVERY_GAINER_PCT or chg <= config.DISCOVERY_LOSER_PCT):
        sig.append("mover")
    vol = q.get("regularMarketVolume") or 0
    avg = q.get("averageDailyVolume3Month") or 0
    if avg and (vol / avg) >= config.DISCOVERY_VOL_SPIKE:
        sig.append("volume")
    px = q.get("regularMarketPrice")
    hi = q.get("fiftyTwoWeekHigh")            # best-effort: not guaranteed present
    lo = q.get("fiftyTwoWeekLow")
    if px and hi and px >= hi * (1 - config.DISCOVERY_52W_PROXIMITY):
        sig.append("52w-high")
    if px and lo and px <= lo * (1 + config.DISCOVERY_52W_PROXIMITY):
        sig.append("52w-low")
    return sig


def _market_for(exchange: str) -> str:
    return "TSX" if exchange == "Toronto" else "US"


def find_candidates(exclude: set[str]) -> list[dict]:
    """Return up to DISCOVERY_SHORTLIST_MAX candidates, ranked.

    Each candidate: {ticker, market, signals, screen_pct}. `exclude` is the
    uppercased watchlist set — those never reach discovery (the hourly loop
    already covers them).
    """
    raw: list[dict] = []
    for label in ("day_gainers", "day_losers", "most_actives"):
        raw += _screen(label, label, size=50)
        time.sleep(1)
    raw += _screen("ca_gainers", _ca_query("gt", config.DISCOVERY_GAINER_PCT),
                   sortField="percentchange", sortAsc=False, size=50)
    time.sleep(1)
    raw += _screen("ca_losers", _ca_query("lt", config.DISCOVERY_LOSER_PCT),
                   sortField="percentchange", sortAsc=True, size=50)

    seen: dict[str, dict] = {}
    for q in raw:
        sym = (q.get("symbol") or "").upper()
        if not sym or sym in exclude or sym in seen:
            continue
        if not _passes_quality(q):
            continue
        sig = _signals(q)
        if not sig:
            continue
        seen[sym] = {
            "ticker": sym,
            "market": _market_for(q.get("exchange") or ""),
            "signals": sig,
            "screen_pct": q.get("regularMarketChangePercent"),
        }

    # Rank: more signals first, then larger absolute move.
    ranked = sorted(seen.values(),
                    key=lambda c: (len(c["signals"]), abs(c.get("screen_pct") or 0)),
                    reverse=True)
    return ranked[: config.DISCOVERY_SHORTLIST_MAX]
