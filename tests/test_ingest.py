"""ingest.py — the yfinance data-ingestion wrapper (supports FR9, FR17; REV-004
follow-up). `yfinance.Ticker` is fully mocked; no real network call is ever
made in this suite.

Covers: the headline relevance filter (`_mentions_company`/`_headlines`) --
an unrelated same-acronym-company headline gets dropped, and the filter
fails OPEN (keeps everything) when no company name is available to match
against -- and the session-aware pricing/volume pro-rating boundary logic
(`_session_state`) at three key points: well into the session, just after
open, and after the session has closed.
"""

import datetime as dt

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
