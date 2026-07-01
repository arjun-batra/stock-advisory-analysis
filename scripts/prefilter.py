"""Discovery prefilter (Phase 4) — reactive movers via Yahoo's screener.

Pulls the day's gainers / losers / most-active (US predefined screens + a custom
region=ca query for Canada), applies quality gates, tags each survivor with the
signal(s) it tripped (mover / volume spike / earnings proximity / 52-week extreme),
excludes watchlist names up front, ranks, and returns a shortlist for the AI.

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


def _screen(label: str, query, **kw) -> tuple[list[dict], bool]:
    """Run one screen. Returns (quotes, errored). errored=True means the call
    raised (rate-limit, endpoint/shape change, runner-IP throttling) and got
    swallowed — the caller counts these so a total screener failure can't
    masquerade as a quiet '0 candidates' day (mirrors the issue #2 heartbeat fix).
    """
    try:
        return _quotes(yf.screen(query, **kw)), False
    except Exception as e:
        print(f"  [prefilter] {label} screen error: {type(e).__name__}: {str(e)[:120]}")
        return [], True


def _EQ():
    EQ = getattr(yf, "EquityQuery", None)
    if EQ is None:
        from yfinance import EquityQuery as EQ  # noqa
    return EQ


def _region_query(region_code: str, op: str, pct: float, min_mcap: float, min_price: float):
    """Custom EquityQuery for a region (ca or in), gated on move/mcap/price."""
    EQ = _EQ()
    return EQ("and", [
        EQ(op, ["percentchange", pct]),
        EQ("eq", ["region", region_code]),
        EQ("gt", ["intradaymarketcap", min_mcap]),
        EQ("gt", ["intradayprice", min_price]),
    ])


def _profile(region: str) -> dict:
    """Per-region quality gate (Phase 6 D5). 'na' = US + Canada (the original
    behaviour). 'in' = India NSE only — region=in also returns BSE listings, so
    the allowed-exchange set is NSI-only to drop the .BO duplicates, and the
    marketCap/price floors are INR-denominated.
    """
    if region == "in":
        return {"min_mcap": config.DISCOVERY_MIN_MARKET_CAP_INR,
                "min_price": config.DISCOVERY_MIN_PRICE_INR,
                "exchanges": config.DISCOVERY_ALLOWED_EXCHANGES_IN}
    return {"min_mcap": config.DISCOVERY_MIN_MARKET_CAP,
            "min_price": config.DISCOVERY_MIN_PRICE,
            "exchanges": config.DISCOVERY_ALLOWED_EXCHANGES}


def _passes_quality(q: dict, profile: dict) -> bool:
    if (q.get("marketCap") or 0) < profile["min_mcap"]:
        return False
    if (q.get("regularMarketPrice") or 0) < profile["min_price"]:
        return False
    if (q.get("regularMarketVolume") or 0) < config.DISCOVERY_MIN_VOLUME:
        return False
    if (q.get("exchange") or "") not in profile["exchanges"]:
        return False
    return True


def _signals(q: dict) -> list[str]:
    """Which discovery signals this quote trips (mover / volume / earnings / 52w)."""
    sig = []
    chg = q.get("regularMarketChangePercent")
    if chg is not None and (chg >= config.DISCOVERY_GAINER_PCT or chg <= config.DISCOVERY_LOSER_PCT):
        sig.append("mover")
    vol = q.get("regularMarketVolume") or 0
    avg = q.get("averageDailyVolume3Month") or 0
    if avg and (vol / avg) >= config.DISCOVERY_VOL_SPIKE:
        sig.append("volume")
    # earnings proximity (FR4): the screener often carries an earnings timestamp
    # (epoch seconds). Best-effort like the 52w fields — applied only if present.
    # Tag when earnings are imminent (within the window) or just reported (<=2d ago),
    # since a same-day earnings move is exactly what discovery wants to catch.
    now = time.time()
    ets = q.get("earningsTimestampStart") or q.get("earningsTimestamp")
    if isinstance(ets, (int, float)) and ets:
        if (now - 2 * 86400) <= ets <= (now + config.DISCOVERY_EARNINGS_DAYS * 86400):
            sig.append("earnings")
    px = q.get("regularMarketPrice")
    hi = q.get("fiftyTwoWeekHigh")            # best-effort: not guaranteed present
    lo = q.get("fiftyTwoWeekLow")
    if px and hi and px >= hi * (1 - config.DISCOVERY_52W_PROXIMITY):
        sig.append("52w-high")
    if px and lo and px <= lo * (1 + config.DISCOVERY_52W_PROXIMITY):
        sig.append("52w-low")
    return sig


def _market_for(exchange: str) -> str:
    return {"Toronto": "TSX", "NSI": "NSE"}.get(exchange, "US")


def find_candidates(exclude: set[str], region: str = "na") -> tuple[list[dict], int, int, dict]:
    """Return (candidates, screens_attempted, screens_errored, funnel), ranked.

    `region` selects the market set (Phase 6 D5): "na" = US predefined movers +
    a custom region=ca query (the original behaviour); "in" = India, a custom
    region=in gainers/losers query filtered to NSE (exchange NSI) only. The
    per-region quality gate (mcap/price floors, allowed exchanges) comes from
    _profile(region).

    Each candidate: {ticker, market, signals, screen_pct}. `exclude` is the
    uppercased watchlist set — those never reach discovery (the hourly loop
    already covers them). The error count lets the caller tell a genuine quiet
    day (0 candidates, 0 errors) from a silent screener failure (0 candidates,
    N errors) — see run_discovery's heartbeat handling.

    `funnel` (issue #8) records where the day's quotes dropped off so a
    zero-candidate day is diagnosable instead of opaque:
      raw            — total quotes returned across all screens (pre-dedup)
      after_dedup    — unique symbols, minus watchlist exclusions
      passed_quality — cleared the marketCap/price/volume/exchange gates
      passed_signal  — also tripped >=1 signal (mover/volume/earnings/52w) == shortlist pool
    "screened 180, 12 passed quality, 0 tripped a signal" points straight at the
    signal thresholds; "180 raw, 0 passed quality" points at the quality gates.
    Three consecutive zero-signal days is a tuning signal, not normal (SD 4.3).
    """
    raw: list[dict] = []
    attempted = 0
    errored = 0
    profile = _profile(region)

    def _collect(label, query, **kw):
        nonlocal attempted, errored
        attempted += 1
        quotes, err = _screen(label, query, **kw)
        if err:
            errored += 1
        return quotes

    if region == "in":
        # India (NSE): region=in custom gainers/losers. No US predefined screens
        # apply. BSE duplicates are dropped later by the NSI-only quality gate.
        raw += _collect("in_gainers",
                        _region_query("in", "gt", config.DISCOVERY_GAINER_PCT,
                                      profile["min_mcap"], profile["min_price"]),
                        sortField="percentchange", sortAsc=False, size=50)
        time.sleep(1)
        raw += _collect("in_losers",
                        _region_query("in", "lt", config.DISCOVERY_LOSER_PCT,
                                      profile["min_mcap"], profile["min_price"]),
                        sortField="percentchange", sortAsc=True, size=50)
    else:
        for label in ("day_gainers", "day_losers", "most_actives"):
            raw += _collect(label, label, size=50)
            time.sleep(1)
        raw += _collect("ca_gainers",
                        _region_query("ca", "gt", config.DISCOVERY_GAINER_PCT,
                                      profile["min_mcap"], profile["min_price"]),
                        sortField="percentchange", sortAsc=False, size=50)
        time.sleep(1)
        raw += _collect("ca_losers",
                        _region_query("ca", "lt", config.DISCOVERY_LOSER_PCT,
                                      profile["min_mcap"], profile["min_price"]),
                        sortField="percentchange", sortAsc=True, size=50)

    funnel = {"raw": len(raw), "after_dedup": 0, "passed_quality": 0, "passed_signal": 0}

    seen: dict[str, dict] = {}
    for q in raw:
        sym = (q.get("symbol") or "").upper()
        if not sym or sym in exclude or sym in seen:
            continue
        seen[sym] = q   # provisional; pruned below. Counted as a unique, in-scope symbol.

    funnel["after_dedup"] = len(seen)

    kept: dict[str, dict] = {}
    for sym, q in seen.items():
        if not _passes_quality(q, profile):
            continue
        funnel["passed_quality"] += 1
        sig = _signals(q)
        if not sig:
            continue
        kept[sym] = {
            "ticker": sym,
            "market": _market_for(q.get("exchange") or ""),
            "signals": sig,
            "screen_pct": q.get("regularMarketChangePercent"),
        }

    funnel["passed_signal"] = len(kept)

    # Rank: more signals first, then larger absolute move.
    ranked = sorted(kept.values(),
                    key=lambda c: (len(c["signals"]), abs(c.get("screen_pct") or 0)),
                    reverse=True)
    return ranked[: config.DISCOVERY_SHORTLIST_MAX], attempted, errored, funnel
