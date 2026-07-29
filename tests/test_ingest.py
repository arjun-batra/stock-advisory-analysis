"""ingest.py — the yfinance data-ingestion wrapper (supports FR9, FR17; REV-004
follow-up). `yfinance.Ticker` is fully mocked; no real network call is ever
made in this suite.

Covers: the headline relevance filter (`_mentions_company`/`_headlines`) --
an unrelated same-acronym-company headline gets dropped, and the filter
fails OPEN (keeps everything) when no company name is available to match
against -- and the session-aware pricing/volume pro-rating boundary logic
(`_session_state`) at three key points: well into the session, just after
open, and after the session has closed. Also covers `get_price_only`
(REV-043, `components.md` §4.2): it must return the same `price`/
`pct_change_1d` values `get_market_data` would for the same underlying
history, using a narrower fetch, and must never touch `tk.info`/`tk.news`.
"""

import datetime as dt

import pandas as pd

import config
import ingest


# --- headline relevance filter (2026-07-03 hourly-run review, finding 3) -----

class FakeTicker:
    """Minimal stand-in for yfinance.Ticker: only the `.ticker` attribute and
    `.news` property that `_headlines`/`_relevance_tokens` actually read."""

    def __init__(self, ticker, news):
        self.ticker = ticker
        self.news = news


def _news_item(title, pub_date="2026-07-01"):
    return {"title": title, "content": {"pubDate": f"{pub_date}T00:00:00Z"}}


def test_unrelated_same_acronym_headline_is_dropped():
    """The exact real-world case from the code's own comment: SBIN.NS (State
    Bank of India) carried an unrelated 'SBI Holdings' (Japan) crypto story.
    Neither the company-name tokens ('state') nor the base symbol ('sbin')
    plausibly appear in that unrelated headline, so it must be dropped."""
    tk = FakeTicker("SBIN.NS", news=[
        _news_item("SBI Holdings launches new crypto fund in Japan"),
        _news_item("State Bank of India posts record quarterly profit"),
    ])
    titles, dropped = ingest._headlines(tk, name="State Bank of India")

    assert dropped == 1
    assert len(titles) == 1
    assert "State Bank of India posts record quarterly profit" in titles[0]


def test_headline_filter_fails_open_when_no_company_name_available():
    """No company name to match against -> nothing is dropped (fail-open, per
    _relevance_tokens' own docstring: the base symbol alone can't prove a
    headline is unrelated)."""
    tk = FakeTicker("AAPL", news=[
        _news_item("Completely unrelated headline about something else entirely"),
        _news_item("Another unrelated headline"),
    ])
    titles, dropped = ingest._headlines(tk, name=None)

    assert dropped == 0
    assert len(titles) == 2


def test_headline_mentioning_company_name_is_kept():
    tk = FakeTicker("AAPL", news=[_news_item("Apple unveils new iPhone lineup")])
    titles, dropped = ingest._headlines(tk, name="Apple Inc")
    assert dropped == 0
    assert len(titles) == 1


def test_headlines_respects_limit_after_filtering():
    tk = FakeTicker("AAPL", news=[_news_item(f"Apple headline {i}") for i in range(10)])
    titles, dropped = ingest._headlines(tk, limit=3, name="Apple Inc")
    assert len(titles) == 3
    assert dropped == 0


def test_headlines_handles_news_fetch_error_gracefully():
    class BrokenTicker:
        ticker = "AAPL"

        @property
        def news(self):
            raise RuntimeError("yfinance blew up")

    titles, dropped = ingest._headlines(BrokenTicker(), name="Apple Inc")
    assert titles == []
    assert dropped == 0


# --- session-aware pricing/volume pro-rating boundary logic (_session_state) -

def _et(hour, minute, weekday_date=dt.date(2026, 7, 13)):
    """2026-07-13 is a Monday."""
    return dt.datetime.combine(weekday_date, dt.time(hour, minute), tzinfo=config.MARKET_TZ)


def test_session_state_well_into_session_is_live_with_midway_fraction():
    # US session is 9:30-16:00 ET (390 minutes). 12:45 is 195 minutes in -> ~0.5.
    live, frac = ingest._session_state("US", now=_et(12, 45))
    assert live is True
    assert 0.45 < frac < 0.55


def test_session_state_just_after_open_is_live_with_small_fraction():
    # 5 minutes after the 9:30 open -> live, small (pre-10%) fraction.
    live, frac = ingest._session_state("US", now=_et(9, 35))
    assert live is True
    assert 0.0 < frac < 0.1


def test_session_state_at_exact_open_is_live_with_zero_fraction():
    live, frac = ingest._session_state("US", now=_et(9, 30))
    assert live is True
    assert frac == 0.0


def test_session_state_after_close_is_not_live():
    live, frac = ingest._session_state("US", now=_et(16, 1))
    assert live is False
    assert frac == 1.0


def test_session_state_on_weekend_is_not_live():
    saturday = dt.date(2026, 7, 11)
    live, frac = ingest._session_state("US", now=_et(12, 0, weekday_date=saturday))
    assert live is False


def test_session_state_nse_market_uses_ist_session():
    ist = dt.datetime.combine(dt.date(2026, 7, 13), dt.time(9, 20),
                               tzinfo=config.NSE_MARKET_TZ)
    live, frac = ingest._session_state("NSE", now=ist)
    assert live is True
    assert 0.0 < frac < 0.1


# --- get_price_only (REV-043, components.md §4.2 — publish_prices.py's -------
# lightweight price-only fetch)

def _history_df(closes):
    idx = pd.date_range("2026-07-01", periods=len(closes), freq="D")
    return pd.DataFrame({"Close": closes, "Volume": [1_000] * len(closes)}, index=idx)


class FakeYFTickerNoInfoNoNews:
    """Fake `yf.Ticker`: `.history()` and `.fast_info` are the only members
    `get_price_only` may read. `.info`/`.news` raise if ever touched, so any
    accidental full-fetch call fails the test loudly rather than silently
    doing extra network work."""

    def __init__(self, ticker, closes, currency="USD", expected_period=None):
        self.ticker = ticker
        self._closes = closes
        self.fast_info = {"currency": currency}
        self._expected_period = expected_period

    def history(self, period=None, auto_adjust=False):
        if self._expected_period is not None:
            assert period == self._expected_period
        return _history_df(self._closes)

    @property
    def info(self):
        raise AssertionError("get_price_only must not touch tk.info (full scrape)")

    @property
    def news(self):
        raise AssertionError("get_price_only must not touch tk.news")


def test_get_price_only_returns_price_and_1d_change_without_full_scrape(monkeypatch):
    closes = [10.0, 11.0, 12.0, 13.0, 14.5]
    monkeypatch.setattr(
        ingest.yf, "Ticker",
        lambda ticker: FakeYFTickerNoInfoNoNews(ticker, closes, currency="USD",
                                                 expected_period=config.YF_PRICE_ONLY_PERIOD))

    data = ingest.get_price_only("AAPL")

    assert data["has_price"] is True
    assert data["price"] == 14.5
    assert data["pct_change_1d"] == round((14.5 / 13.0 - 1) * 100, 2)
    assert data["market"] == "US"
    assert data["fundamentals"]["currency"] == "USD"


def test_get_price_only_matches_get_market_data_price_fields_for_same_history(monkeypatch):
    """Not a behavior change: given the same underlying closes, the narrower
    fetch must produce the exact same price/pct_change_1d get_market_data
    would (only the *data volume* fetched differs, not the values)."""
    # get_market_data needs >= config.MIN_HISTORY_ROWS rows to compute the 20d
    # fields, but price/pct_change_1d only ever look at the last two closes.
    long_closes = [10.0 + i * 0.1 for i in range(30)]
    long_closes[-1] = 14.5
    long_closes[-2] = 13.0
    short_closes = [13.0, 14.5]

    class FullFakeTicker(FakeYFTickerNoInfoNoNews):
        def __init__(self, ticker):
            super().__init__(ticker, long_closes, currency="USD")

        @property
        def info(self):
            return {}

        @property
        def news(self):
            return []

    monkeypatch.setattr(ingest.yf, "Ticker", FullFakeTicker)
    full = ingest.get_market_data("AAPL")

    monkeypatch.setattr(
        ingest.yf, "Ticker",
        lambda ticker: FakeYFTickerNoInfoNoNews(ticker, short_closes, currency="USD"))
    narrow = ingest.get_price_only("AAPL")

    assert narrow["price"] == full["price"] == 14.5
    assert narrow["pct_change_1d"] == full["pct_change_1d"]


def test_get_price_only_no_price_data_is_skip_not_fatal(monkeypatch):
    class EmptyHistoryTicker(FakeYFTickerNoInfoNoNews):
        def history(self, period=None, auto_adjust=False):
            return pd.DataFrame({"Close": [], "Volume": []})

    monkeypatch.setattr(ingest.yf, "Ticker", lambda ticker: EmptyHistoryTicker(ticker, []))

    data = ingest.get_price_only("DELISTED")

    assert data["has_price"] is False
    assert data["notes"]
