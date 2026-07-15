"""run_shadow.py -- the US/CA shadow wallet pilot's `_derive_shadow_positions`
(FR31 refactor target, design.md §17.2, INC-2).

Mirrors tests/test_run_shadow_nse.py's wallet-walk coverage for the NSE track,
retargeted to the US/CA `_derive_shadow_positions` (previously untested
directly per the INC-2 handoff's "Known limitations"). Confirms the refactor
that delegates to the shared `wallet_sim.walk` produces the same
{state, entry_price, entry_date} shape and behavior as the pre-refactor inline
loop (Buy/Sell/Hold/no-op rules, empty history, per-ticker independence, and
strict call_log_shadow-only reads).
"""

import run_shadow


class FakeShadowQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def in_(self, *_a, **_kw):
        return self

    def gte(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def execute(self):
        class R:
            data = self._data
        return R()


class FakeShadowSupabase:
    """Table-keyed double; a read from an unexpected table raises, proving the
    walk only ever reads call_log_shadow (never call_log_shadow_nse or the
    live call_log)."""

    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        if name not in self._tables:
            raise AssertionError(f"unexpected read/write to table {name!r}")
        return FakeShadowQuery(self._tables[name])


def _row(ticker, verdict, timestamp, price=None):
    return {"ticker": ticker, "verdict": verdict, "timestamp": timestamp,
            "data_snapshot": {"price": price} if price is not None else {}}


def test_wallet_walk_buy_flips_flat_to_holding():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=100.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["AAPL"]["entry_price"] == 100.0
    assert positions["AAPL"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_wallet_walk_sell_flips_holding_to_flat():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=100.0),
        _row("AAPL", "Sell", "2026-07-11T09:00:00Z", price=110.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "flat"
    assert positions["AAPL"]["entry_price"] is None
    assert positions["AAPL"]["entry_date"] is None


def test_wallet_walk_hold_is_a_no_op():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=100.0),
        _row("AAPL", "Hold", "2026-07-11T09:00:00Z", price=105.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["AAPL"]["entry_price"] == 100.0
    assert positions["AAPL"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_wallet_walk_buy_while_holding_is_a_no_op():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=100.0),
        _row("AAPL", "Buy", "2026-07-11T09:00:00Z", price=999.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["entry_price"] == 100.0   # unchanged by the second Buy


def test_wallet_walk_sell_while_flat_is_a_no_op():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Sell", "2026-07-10T09:00:00Z", price=100.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"] == {"state": "flat", "entry_price": None, "entry_date": None}


def test_wallet_walk_empty_history_is_flat():
    sb = FakeShadowSupabase({"call_log_shadow": []})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"] == {"state": "flat", "entry_price": None, "entry_date": None}


def test_wallet_walk_reads_only_call_log_shadow_never_call_log_or_call_log_shadow_nse():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=100.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])
    assert positions["AAPL"]["state"] == "holding"


def test_wallet_walk_covers_only_requested_tickers_independently():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=100.0),
        _row("MSFT", "Sell", "2026-07-10T09:00:00Z", price=300.0),   # Sell-while-flat: no-op
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL", "MSFT"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["MSFT"]["state"] == "flat"


def test_run_shadow_source_never_writes_to_call_log_or_call_log_shadow_nse():
    import inspect
    src = inspect.getsource(run_shadow)
    assert 'sb.table("call_log_shadow_nse")' not in src
    assert 'sb.table("call_log").insert' not in src
