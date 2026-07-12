"""prefilter.py — discovery quality-gate and signal boundary logic (FR4).

FR4: "A candidate that trips at least one signal (and clears quality gates on
market cap, price, volume, and listing exchange) reaches the AI... Specific
thresholds for signals and quality gates are tunable at build time."

These are pure functions over a quote dict + `config` module state, so they're
cheap, high-value, boundary-focused unit tests — no network, no yfinance call.
"""

import importlib

import pytest

import config
import prefilter


@pytest.fixture(autouse=True)
def _restore_config():
    """Prevent config mutations in one test (configurability checks) leaking
    into the next; prefilter reads config.* fresh on every call, so a plain
    reload is enough to restore defaults."""
    yield
    importlib.reload(config)
    importlib.reload(prefilter)


US_PROFILE = {
    "min_mcap": config.DISCOVERY_MIN_MARKET_CAP,
    "min_price": config.DISCOVERY_MIN_PRICE,
    "exchanges": config.DISCOVERY_ALLOWED_EXCHANGES,
}


def _quote(**overrides):
    q = {
        "symbol": "ACME",
        "marketCap": config.DISCOVERY_MIN_MARKET_CAP,
        "regularMarketPrice": config.DISCOVERY_MIN_PRICE,
        "regularMarketVolume": config.DISCOVERY_MIN_VOLUME,
        "exchange": "NYSE",
        "regularMarketChangePercent": 0.0,
    }
    q.update(overrides)
    return q


# --- quality gates: market cap / price / volume / exchange (FR4) --------------

def test_quality_gate_passes_at_exact_market_cap_floor():
    q = _quote(marketCap=config.DISCOVERY_MIN_MARKET_CAP)
    assert prefilter._passes_quality(q, US_PROFILE) is True


def test_quality_gate_fails_just_below_market_cap_floor():
    q = _quote(marketCap=config.DISCOVERY_MIN_MARKET_CAP - 1)
    assert prefilter._passes_quality(q, US_PROFILE) is False


def test_quality_gate_passes_at_exact_price_floor():
    q = _quote(regularMarketPrice=config.DISCOVERY_MIN_PRICE)
    assert prefilter._passes_quality(q, US_PROFILE) is True


def test_quality_gate_fails_just_below_price_floor():
    q = _quote(regularMarketPrice=config.DISCOVERY_MIN_PRICE - 0.01)
    assert prefilter._passes_quality(q, US_PROFILE) is False


def test_quality_gate_passes_at_exact_volume_floor():
    q = _quote(regularMarketVolume=config.DISCOVERY_MIN_VOLUME)
    assert prefilter._passes_quality(q, US_PROFILE) is True


def test_quality_gate_fails_just_below_volume_floor():
    q = _quote(regularMarketVolume=config.DISCOVERY_MIN_VOLUME - 1)
    assert prefilter._passes_quality(q, US_PROFILE) is False


def test_quality_gate_fails_disallowed_exchange():
    q = _quote(exchange="OTC")
    assert prefilter._passes_quality(q, US_PROFILE) is False


def test_quality_gate_missing_fields_fail_closed_not_crash():
    # a quote with no marketCap/price/volume/exchange at all must fail the
    # gate cleanly (defaults to 0/"" via `.get(...) or 0`), never raise.
    assert prefilter._passes_quality({}, US_PROFILE) is False


# --- NSE (region=in) profile uses INR floors + NSI-only exchange allowlist ---

def test_in_profile_uses_inr_floors_and_nsi_exchange():
    profile = prefilter._profile("in")
    assert profile["min_mcap"] == config.DISCOVERY_MIN_MARKET_CAP_INR
    assert profile["min_price"] == config.DISCOVERY_MIN_PRICE_INR
    assert profile["exchanges"] == {"NSI"}


def test_in_profile_rejects_bse_dual_listing():
    profile = prefilter._profile("in")
    q = _quote(exchange="BSE", marketCap=config.DISCOVERY_MIN_MARKET_CAP_INR,
               regularMarketPrice=config.DISCOVERY_MIN_PRICE_INR)
    assert prefilter._passes_quality(q, profile) is False


def test_in_profile_accepts_nsi_listing():
    profile = prefilter._profile("in")
    q = _quote(exchange="NSI", marketCap=config.DISCOVERY_MIN_MARKET_CAP_INR,
               regularMarketPrice=config.DISCOVERY_MIN_PRICE_INR)
    assert prefilter._passes_quality(q, profile) is True


# --- signals: mover / volume / earnings / 52w (FR4's four signals) ------------

def test_mover_signal_trips_at_exact_gainer_threshold():
    q = _quote(regularMarketChangePercent=config.DISCOVERY_GAINER_PCT)
    assert "mover" in prefilter._signals(q)


def test_mover_signal_does_not_trip_just_below_gainer_threshold():
    q = _quote(regularMarketChangePercent=config.DISCOVERY_GAINER_PCT - 0.01)
    assert "mover" not in prefilter._signals(q)


def test_mover_signal_trips_at_exact_loser_threshold():
    q = _quote(regularMarketChangePercent=config.DISCOVERY_LOSER_PCT)
    assert "mover" in prefilter._signals(q)


def test_mover_signal_does_not_trip_just_above_loser_threshold():
    q = _quote(regularMarketChangePercent=config.DISCOVERY_LOSER_PCT + 0.01)
    assert "mover" not in prefilter._signals(q)


def test_volume_signal_trips_at_exact_spike_multiple():
    q = _quote(regularMarketVolume=1_000_000, averageDailyVolume3Month=1_000_000 / config.DISCOVERY_VOL_SPIKE)
    assert "volume" in prefilter._signals(q)


def test_volume_signal_does_not_trip_just_below_spike_multiple():
    avg = 1_000_000 / config.DISCOVERY_VOL_SPIKE
    q = _quote(regularMarketVolume=1_000_000 - 1, averageDailyVolume3Month=avg)
    assert "volume" not in prefilter._signals(q)


def test_volume_signal_absent_when_average_missing():
    q = _quote(regularMarketVolume=10_000_000, averageDailyVolume3Month=0)
    assert "volume" not in prefilter._signals(q)


def test_52w_high_signal_trips_at_exact_proximity():
    hi = 100.0
    px = hi * (1 - config.DISCOVERY_52W_PROXIMITY)
    q = _quote(regularMarketPrice=px, fiftyTwoWeekHigh=hi)
    assert "52w-high" in prefilter._signals(q)


def test_52w_high_signal_does_not_trip_outside_proximity():
    hi = 100.0
    px = hi * (1 - config.DISCOVERY_52W_PROXIMITY) - 1.0
    q = _quote(regularMarketPrice=px, fiftyTwoWeekHigh=hi)
    assert "52w-high" not in prefilter._signals(q)


def test_52w_low_signal_trips_at_exact_proximity():
    lo = 50.0
    px = lo * (1 + config.DISCOVERY_52W_PROXIMITY)
    q = _quote(regularMarketPrice=px, fiftyTwoWeekLow=lo)
    assert "52w-low" in prefilter._signals(q)


def test_52w_signal_best_effort_absent_when_fields_missing():
    q = _quote()   # no fiftyTwoWeekHigh/Low at all
    assert "52w-high" not in prefilter._signals(q)
    assert "52w-low" not in prefilter._signals(q)


def test_earnings_signal_trips_within_window():
    import time as _time
    ets = _time.time() + (config.DISCOVERY_EARNINGS_DAYS - 1) * 86400
    q = _quote(earningsTimestampStart=ets)
    assert "earnings" in prefilter._signals(q)


def test_earnings_signal_does_not_trip_outside_window():
    import time as _time
    ets = _time.time() + (config.DISCOVERY_EARNINGS_DAYS + 5) * 86400
    q = _quote(earningsTimestampStart=ets)
    assert "earnings" not in prefilter._signals(q)


def test_quote_tripping_zero_signals_is_excluded_from_shortlist():
    q = _quote()   # exactly at quality floors, no move/volume/earnings/52w signal
    assert prefilter._signals(q) == []


# --- market label mapping (feeds discovery's US/TSX/NSE grouping, FR20) -------

def test_market_from_exchange_toronto_is_tsx():
    assert prefilter._market_from_exchange("Toronto") == "TSX"


def test_market_from_exchange_nsi_is_nse():
    assert prefilter._market_from_exchange("NSI") == "NSE"


def test_market_from_exchange_unknown_defaults_to_us():
    assert prefilter._market_from_exchange("NYSE") == "US"
    assert prefilter._market_from_exchange("SomethingElse") == "US"


# --- configurability: thresholds are tunables, not hardcoded (FR4, design §9) -

def test_gainer_threshold_is_config_driven_not_hardcoded(monkeypatch):
    """Changing DISCOVERY_GAINER_PCT must change mover-signal behavior — proof
    the threshold isn't hardcoded inside _signals()."""
    monkeypatch.setattr(config, "DISCOVERY_GAINER_PCT", 50.0)
    q = _quote(regularMarketChangePercent=10.0)   # would have tripped at the default (5%)
    assert "mover" not in prefilter._signals(q)

    monkeypatch.setattr(config, "DISCOVERY_GAINER_PCT", 5.0)
    assert "mover" in prefilter._signals(q)


def test_min_market_cap_is_config_driven_not_hardcoded(monkeypatch):
    monkeypatch.setattr(config, "DISCOVERY_MIN_MARKET_CAP", 10_000_000_000.0)
    q = _quote(marketCap=3_000_000_000.0)   # would have passed at the $2B default
    profile = {"min_mcap": config.DISCOVERY_MIN_MARKET_CAP,
               "min_price": config.DISCOVERY_MIN_PRICE,
               "exchanges": config.DISCOVERY_ALLOWED_EXCHANGES}
    assert prefilter._passes_quality(q, profile) is False
