"""Data ingestion via yfinance (solution design 4.2).

Returns the data the AI prompt is fed and the detail page renders, in the
`data_snapshot` shape from design 5. Carries over the Phase 0 smoke-test logic,
including newly-listed handling (4.4a / 7.5): a young IPO returns valid price
data but can't fill the 20-day window, so those fields come back as the explicit
string "n/a (newly listed)" rather than being omitted or faked.
"""

import re
import time
from datetime import datetime, timezone

import yfinance as yf

import config


def _is_rate_limit(exc: Exception) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(s in blob for s in ("ratelimit", "rate limit", "too many requests", "429"))


def _fetch_history(tk: "yf.Ticker", period: str | None = None):
    """Fetch history (default 3mo, `config.YF_HISTORY_PERIOD`), retrying ONCE
    after a backoff on a Yahoo rate-limit. `period` overrides the window
    (used by `get_price_only`'s narrower 5d fetch).

    Returns (dataframe_or_none, error_note_or_none, was_rate_limited).
    yfinance has no published rate limit and throttled the back-to-back ingest
    loop mid-run (issue #1), so this mirrors the AI step's backoff-retry.
    """
    period = period or config.YF_HISTORY_PERIOD
    for attempt in range(config.YF_HISTORY_RETRIES):
        try:
            return tk.history(period=period, auto_adjust=False), None, False
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
    # Company identity/sector so the AI isn't guessing what a ticker is from
    # its symbol alone (matters most for small caps and NSE names).
    name = _get(info, "shortName", "longName")
    sector = _get(info, "sector")
    industry = _get(info, "industry")
    return {"pe": pe, "market_cap": mcap, "range_52w": rng, "currency": cur,
            "name": name, "sector": sector, "industry": industry}


def _news_date(item: dict, content: dict) -> str | None:
    """Best-effort publish date (YYYY-MM-DD) from either yfinance news shape:
    new-style content.pubDate ISO string, or legacy providerPublishTime epoch."""
    pub = content.get("pubDate") or content.get("displayTime")
    if isinstance(pub, str) and len(pub) >= 10:
        return pub[:10]
    ts = item.get("providerPublishTime")
    if isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


# Generic corporate/name words that can't identify a company on their own.
# Kept deliberately broad ("bank" would match any bank-sector story; "india"
# any India story) — the tokens that remain must be distinctive (e.g. "hdfc",
# "exide", "unilever", "jammu"). Lowercase, alnum-only, len >= 3.
_NAME_STOPWORDS = {
    "the", "and", "for", "ltd", "limited", "inc", "incorporated", "corp",
    "corporation", "company", "companies", "plc", "group", "holdings",
    "holding", "bank", "india", "indian", "industries", "enterprises",
    "international", "services", "financial",
}


def _relevance_tokens(ticker: str, name: str | None) -> set[str]:
    """Match tokens identifying the company: the base symbol (suffix stripped,
    alnum-only — 'J&KBANK.NS' -> 'jkbank') plus the distinctive words of the
    company name. Empty when no name is available — callers must then skip
    filtering (fail-open), because the base symbol alone can't prove a headline
    is unrelated (e.g. Apple stories rarely contain 'AAPL')."""
    name_toks = {w for w in re.split(r"[^a-z0-9]+", (name or "").lower())
                 if len(w) >= 3 and w not in _NAME_STOPWORDS}
    if not name_toks:
        return set()
    base = re.sub(r"[^a-z0-9]", "", ticker.split(".")[0].lower())
    return name_toks | ({base} if base else set())


def _mentions_company(title: str, tokens: set[str]) -> bool:
    """True if the headline plausibly mentions the company. Titles are compared
    two ways: split on non-alnum (\"Reliance's\" -> 'reliance', 's') AND as
    whitespace chunks with punctuation collapsed ('L&T' -> 'lt'). Tokens of 4+
    chars also match as word prefixes ('goog' -> 'google', 'scotia' ->
    'scotiabank'); shorter ones ('tcs', 'itc', 'lt') must match exactly."""
    t = title.lower()
    words = [w for w in re.split(r"[^a-z0-9]+", t) if w]
    words += [w for w in (re.sub(r"[^a-z0-9]", "", c) for c in t.split()) if w]
    for w in words:
        for t in tokens:
            if w == t or (len(t) >= 4 and w.startswith(t)):
                return True
    return False


def _headlines(tk: "yf.Ticker", limit: int = config.HEADLINES_LIMIT, name: str | None = None) -> tuple[list[str], int]:
    """Headline titles prefixed with their publish date when available, so the
    AI (and the detail page) can tell a this-morning story from a stale one.

    Relevance filter (2026-07-03 hourly-run review, finding 3): Yahoo's
    per-ticker feed mixes in stories about unrelated companies — SBIN.NS
    carried SBI Holdings (Japan) crypto stories, and the model's rationale
    visibly absorbed them ("the parent company's crypto-related activities").
    Titles that mention neither the company name nor the ticker are dropped
    BEFORE the limit is applied, so junk can't crowd out relevant stories.
    Fail-open: with no company name to match against, nothing is dropped.
    Returns (titles, dropped_count) — the count goes into data notes.
    """
    try:
        items = tk.news or []
    except Exception:
        items = []
    tokens = _relevance_tokens(getattr(tk, "ticker", "") or "", name)
    titles, dropped = [], 0
    for it in items:
        if not isinstance(it, dict):
            continue
        content = it.get("content") or {}
        title = it.get("title") or content.get("title")
        if not title:
            continue
        if tokens and not _mentions_company(title, tokens):
            dropped += 1
            continue
        date_s = _news_date(it, content)
        titles.append(f"[{date_s}] {title}" if date_s else title)
    return titles[:limit], dropped


def _session_state(market: str, now: datetime | None = None) -> tuple[bool, float]:
    """(session_live, fraction_of_session_elapsed) for a market right now.

    Drives the intraday handling (2026-07-03 hourly-run review, finding 4):
    mid-session, yfinance's last daily bar is a LIVE, partial bar — the "close"
    is the live price and the day's volume is incomplete. US and TSX share the
    ET session; NSE uses the IST session. The fraction is wall-clock over the
    session span (clamped 0..1) — intraday volume isn't uniform (U-shaped), so
    pro-rating by it is an estimate, clearly labeled as such downstream.
    """
    if market == "NSE":
        tz, open_t, close_t = config.NSE_MARKET_TZ, config.NSE_MARKET_OPEN, config.NSE_MARKET_CLOSE
    else:   # US and TSX share the 9:30-16:00 ET session
        tz, open_t, close_t = config.MARKET_TZ, config.MARKET_OPEN, config.MARKET_CLOSE
    # STRICT session bounds on purpose — not is_market_open/is_nse_open, whose
    # RUNTIME_CLOSE_GRACE_MIN exists to keep the final dispatch of the day from
    # being no-op'd. A run inside that grace window is judging the settled
    # close, so it must NOT be labeled a live session.
    now = now or datetime.now(tz)
    if now.weekday() >= 5 or not (open_t <= now.time() <= close_t):
        return False, 1.0
    elapsed = ((now.hour - open_t.hour) * 3600 + (now.minute - open_t.minute) * 60
               + now.second - open_t.second)
    total = ((close_t.hour - open_t.hour) * 3600 + (close_t.minute - open_t.minute) * 60)
    if not total:
        return True, 1.0
    return True, max(0.0, min(1.0, elapsed / total))


def _market_for(ticker: str) -> str:
    """Map a ticker suffix to its market (design §12 D6).

    `.NS` -> NSE (India), `.TO` -> TSX (Canada), otherwise US. This is the same
    suffix convention yfinance uses; the Phase-0 smoke test confirmed `.NS`
    tickers report exchange='NSI' and carry currency='INR', which flows through
    `_fundamentals` into data_snapshot.fundamentals.currency untouched (no FX).
    """
    t = ticker.upper()
    if t.endswith(".NS"):
        return "NSE"
    if t.endswith(".TO"):
        return "TSX"
    return "US"


def get_market_data(ticker: str) -> dict:
    """Fetch price/volume + fundamentals + news for one ticker.

    `has_price=False` means skip-with-log (no usable data). `is_new=True` means a
    valid young listing — judged on what's available, 20d fields marked n/a.
    `rate_limited=True` flags a skip caused by Yahoo throttling vs. genuine
    no-data (delisted/halted), so the run log and call_log can tell them apart.
    """
    market = _market_for(ticker)
    out = {
        "ticker": ticker, "market": market,
        "has_price": False, "is_new": False, "rate_limited": False,
        "price": None, "pct_change_1d": None, "pct_change_5d": None,
        "pct_change_20d": None, "volume_vs_avg": None,
        # session_live: the market is mid-session, so `price` is a LIVE price
        # (not a settled close) and the 1d change is today-so-far.
        # volume_pro_rated: volume_vs_avg was scaled up for the elapsed portion
        # of the live session (an estimate — labeled in the prompt and UI).
        "session_live": False, "volume_pro_rated": False,
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

    # FR17/Decision #33 stale-bar structural check (INC-9, DEEP-004 fix): must
    # run before ANY price/volume math below. _session_state() only knows
    # weekday+wall-clock, not whether today is a holiday (no maintained
    # calendar exists, Decision #8), so on a closed-market day yfinance still
    # returns the prior session's bar and _session_state alone would call it
    # live. Comparing the bar's own date to today's market-local date catches
    # that here, structurally, before session_live/volume pro-rating can ever
    # see a stale bar.
    live, frac = _session_state(market)
    tz = config.NSE_MARKET_TZ if market == "NSE" else config.MARKET_TZ
    last_bar_date = h.index[-1].date()            # yfinance's own bar date, exchange-local
    today_market = datetime.now(tz).date()
    if live and last_bar_date < today_market:
        out["notes"].append(
            f"market appears closed today ({today_market}) — latest available bar is from "
            f"{last_bar_date}; treating as no usable data (FR17/Decision #33)")
        return out   # has_price stays False: same skip-with-log path as any other no-data day

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

    # Mid-session correction (2026-07-03 hourly-run review, finding 4): the last
    # bar is live and partial, so a raw volume ratio reads absurdly low early in
    # the day (observed 0.07-0.30 across the whole NSE watchlist 45 min after
    # the open — the prompt was effectively told "volume is dead" every morning).
    # Pro-rate by the elapsed session fraction; too early (<10%), the estimate
    # is dominated by the open auction/U-shape, so mark it n/a instead.
    # live/frac were already computed above (stale-bar check reuses the same
    # call rather than calling _session_state twice).
    out["session_live"] = live
    if live and isinstance(out["volume_vs_avg"], (int, float)):
        if frac < 0.1:
            out["volume_vs_avg"] = "n/a (too early in session)"
        else:
            out["volume_vs_avg"] = round(out["volume_vs_avg"] / frac, 2)
            out["volume_pro_rated"] = True

    out["fundamentals"] = _fundamentals(tk)
    heads, dropped = _headlines(tk, name=out["fundamentals"].get("name"))
    out["headlines"] = heads
    if dropped:
        out["notes"].append(f"{dropped} headline(s) dropped as likely unrelated to the company")
    return out


def get_price_only(ticker: str) -> dict:
    """Lightweight price/1d-change fetch for `publish_prices.py` (REV-043,
    `components.md` §4.2 design call). `get_market_data()` above does a full
    3mo history fetch plus `tk.fast_info`, `tk.info`, and `tk.news` — four
    Yahoo requests — but `publish_prices.py` only reads `price`/
    `pct_change_1d`/`market`/`fundamentals.currency`. This fetches a short
    `config.YF_PRICE_ONLY_PERIOD` history window (enough for those two price
    fields) and `tk.fast_info` for currency context only — no `tk.info`
    scrape, no `tk.news` call. `get_market_data()` is untouched and remains
    the only path the AI-judgment code (`run_hourly.py`/`run_discovery.py`)
    uses.
    """
    market = _market_for(ticker)
    out = {
        "ticker": ticker, "market": market,
        "has_price": False, "rate_limited": False,
        "price": None, "pct_change_1d": None,
        "fundamentals": {}, "notes": [],
    }

    tk = yf.Ticker(ticker)
    h, err, rate_limited = _fetch_history(tk, period=config.YF_PRICE_ONLY_PERIOD)
    if err is not None:
        out["notes"].append(err)
        out["rate_limited"] = rate_limited
        return out
    if h is None or h.empty:
        out["notes"].append("no price data (delisted/halted/bad ticker)")
        return out

    close = h["Close"].dropna()
    out["has_price"] = True
    out["price"] = round(float(close.iloc[-1]), 4)
    if len(close) >= 2:
        out["pct_change_1d"] = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2)

    try:
        fi = dict(tk.fast_info)
    except Exception:
        fi = {}
    out["fundamentals"] = {"currency": _get(fi, "currency")}
    return out
