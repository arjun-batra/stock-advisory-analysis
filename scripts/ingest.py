"""Data ingestion via yfinance (solution design 4.2).

Returns the data the AI prompt is fed and the detail page renders, in the
`data_snapshot` shape from design 5. Carries over the Phase 0 smoke-test logic,
including newly-listed handling (4.4a / 7.5): a young IPO returns valid price
data but can't fill the 20-day window, so those fields come back as the explicit
string "n/a (newly listed)" rather than being omitted or faked.
"""

import time

import yfinance as yf

import config


def _is_rate_limit(exc: Exception) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(s in blob for s in ("ratelimit", "rate limit", "too many requests", "429"))


def _fetch_history(tk: "yf.Ticker"):
    """Fetch 3mo history, retrying ONCE after a backoff on a Yahoo rate-limit.

    Returns (dataframe_or_none, error_note_or_none, was_rate_limited).
    yfinance has no published rate limit and throttled the back-to-back ingest
    loop mid-run (issue #1), so this mirrors the AI step's backoff-retry.
    """
    for attempt in range(2):
        try:
            return tk.history(period="3mo", auto_adjust=False), None, False
        except Exception as e:
            if _is_rate_limit(e) and attempt == 0:
                time.sleep(config.YF_BACKOFF_SECONDS)
                continue
            note = f"history error: {type(e).__name__}: {str(e)[:120]}"
            return None, note, _is_rate_limit(e)
    return None, "history error: exhausted retries", True


def _get(d, *keys):
    for k in keys:
        try:
            v = d[k] if not hasattr(d, "get") else d.get(k)
        except Exception:
            v = None
        if v not in (None, "", 0):
            return v
    return None


def _fundamentals(tk: "yf.Ticker") -> dict:
    fi = {}
    try:
        fi = dict(tk.fast_info)
    except Exception:
        fi = {}
    info = {}
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    pe = _get(info, "trailingPE", "forwardPE")
    mcap = _get(fi, "market_cap", "marketCap") or _get(info, "marketCap")
    cur = _get(fi, "currency") or _get(info, "currency")
    hi = _get(fi, "year_high", "yearHigh") or _get(info, "fiftyTwoWeekHigh")
    lo = _get(fi, "year_low", "yearLow") or _get(info, "fiftyTwoWeekLow")
    rng = [round(float(lo), 2), round(float(hi), 2)] if (hi and lo) else None
    return {"pe": pe, "market_cap": mcap, "range_52w": rng, "currency": cur}


def _headlines(tk: "yf.Ticker", limit: int = 5) -> list[str]:
    try:
        items = tk.news or []
    except Exception:
        items = []
    titles = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = it.get("title") or (it.get("content") or {}).get("title")
        if title:
            titles.append(title)
    return titles[:limit]


def get_market_data(ticker: str) -> dict:
    """Fetch price/volume + fundamentals + news for one ticker.

    `has_price=False` means skip-with-log (no usable data). `is_new=True` means a
    valid young listing — judged on what's available, 20d fields marked n/a.
    `rate_limited=True` flags a skip caused by Yahoo throttling vs. genuine
    no-data (delisted/halted), so the run log and call_log can tell them apart.
    """
    market = "TSX" if ticker.upper().endswith(".TO") else "US"
    out = {
        "ticker": ticker, "market": market,
        "has_price": False, "is_new": False, "rate_limited": False,
        "price": None, "pct_change_1d": None, "pct_change_5d": None,
        "pct_change_20d": None, "volume_vs_avg": None,
        "fundamentals": {}, "headlines": [], "notes": [],
    }

    tk = yf.Ticker(ticker)
    h, err, rate_limited = _fetch_history(tk)
    if err is not None:
        out["notes"].append(err)
        out["rate_limited"] = rate_limited
        return out
    if h is None or h.empty:
        out["notes"].append("no price data (delisted/halted/bad ticker)")
        return out

    close = h["Close"].dropna()
    vol = h["Volume"].dropna()
    out["has_price"] = True
    out["price"] = round(float(close.iloc[-1]), 4)

    n = len(close)
    if n >= 2:
        out["pct_change_1d"] = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2)
    if n >= 6:
        out["pct_change_5d"] = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2)
    if n >= config.MIN_HISTORY_ROWS:
        out["pct_change_20d"] = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2)
        avg20 = vol.iloc[-21:-1].mean()
        out["volume_vs_avg"] = round(float(vol.iloc[-1] / avg20), 2) if avg20 else None
    else:
        out["is_new"] = True
        out["pct_change_20d"] = "n/a (newly listed)"
        out["volume_vs_avg"] = "n/a (newly listed)"

    out["fundamentals"] = _fundamentals(tk)
    out["headlines"] = _headlines(tk)
    return out
