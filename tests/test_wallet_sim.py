"""wallet_sim.py — the single shared Buy/Sell/Hold state machine (design.md
§17.2, FR31). Pure, zero-I/O module: no DB double needed, just plain dicts.

Covers: state-machine correctness (happy path + every no-op edge case),
return_pct math (incl. the None/zero-entry-price divide-by-zero guard),
mark_price open-position marking, multi-round-trip sequencing, and the
read-only/no-I/O non-negotiable (module never imports state/supabase/requests).
"""

import inspect

import wallet_sim


def _row(verdict, timestamp, price=None):
    return {"verdict": verdict, "timestamp": timestamp, "price": price}


# --- core state machine ------------------------------------------------------

def test_buy_flips_flat_to_holding():
    result = wallet_sim.walk([_row("Buy", "t1", 100.0)])
    assert result["position"] == {"state": "holding", "entry_price": 100.0, "entry_date": "t1"}
    assert result["round_trips"] == []


def test_sell_flips_holding_to_flat_and_records_round_trip():
    rows = [_row("Buy", "t1", 100.0), _row("Sell", "t2", 110.0)]
    result = wallet_sim.walk(rows)
    assert result["position"] == {"state": "flat", "entry_price": None, "entry_date": None}
    assert result["round_trips"] == [{
        "entry_price": 100.0, "entry_date": "t1",
        "exit_price": 110.0, "exit_date": "t2",
        "return_pct": 10.0,
    }]


def test_hold_is_a_no_op_while_holding():
    rows = [_row("Buy", "t1", 100.0), _row("Hold", "t2", 105.0)]
    result = wallet_sim.walk(rows)
    assert result["position"] == {"state": "holding", "entry_price": 100.0, "entry_date": "t1"}
    assert result["round_trips"] == []


def test_hold_is_a_no_op_while_flat():
    result = wallet_sim.walk([_row("Hold", "t1", 100.0)])
    assert result["position"] == {"state": "flat", "entry_price": None, "entry_date": None}


def test_buy_while_holding_is_a_no_op_entry_price_unchanged():
    rows = [_row("Buy", "t1", 100.0), _row("Buy", "t2", 999.0)]
    result = wallet_sim.walk(rows)
    assert result["position"] == {"state": "holding", "entry_price": 100.0, "entry_date": "t1"}


def test_sell_while_flat_is_a_no_op():
    result = wallet_sim.walk([_row("Sell", "t1", 100.0)])
    assert result["position"] == {"state": "flat", "entry_price": None, "entry_date": None}
    assert result["round_trips"] == []


def test_empty_input_is_flat_with_no_round_trips_and_no_open_position():
    result = wallet_sim.walk([])
    assert result == {
        "position": {"state": "flat", "entry_price": None, "entry_date": None},
        "round_trips": [],
        "open": None,
    }


def test_multiple_round_trips_in_sequence():
    rows = [
        _row("Buy", "t1", 100.0), _row("Sell", "t2", 110.0),   # +10%
        _row("Buy", "t3", 200.0), _row("Sell", "t4", 180.0),   # -10%
        _row("Buy", "t5", 50.0),                                 # still open
    ]
    result = wallet_sim.walk(rows, mark_price=55.0)
    assert len(result["round_trips"]) == 2
    assert result["round_trips"][0]["return_pct"] == 10.0
    assert result["round_trips"][1]["return_pct"] == -10.0
    assert result["position"] == {"state": "holding", "entry_price": 50.0, "entry_date": "t5"}
    assert result["open"] == {
        "entry_price": 50.0, "entry_date": "t5",
        "mark_price": 55.0, "unrealized_return_pct": 10.0,
    }


# --- return_pct math ----------------------------------------------------------

def test_return_pct_formula():
    # (exit/entry - 1) * 100, rounded to 4 dp
    assert wallet_sim._return_pct(100.0, 110.0) == 10.0
    assert wallet_sim._return_pct(3500.0, 3600.0) == round((3600 / 3500 - 1) * 100, 4)


def test_return_pct_rounds_to_four_decimal_places():
    assert wallet_sim._return_pct(3.0, 3.1) == round((3.1 / 3.0 - 1) * 100, 4)


def test_return_pct_none_when_entry_price_is_none():
    assert wallet_sim._return_pct(None, 110.0) is None


def test_return_pct_none_when_exit_price_is_none():
    assert wallet_sim._return_pct(100.0, None) is None


def test_return_pct_none_when_entry_price_is_zero_no_division_by_zero():
    # entry_price in (None, 0) guard — must not raise ZeroDivisionError
    assert wallet_sim._return_pct(0, 110.0) is None


def test_return_pct_none_when_both_none():
    assert wallet_sim._return_pct(None, None) is None


def test_sell_with_no_price_yields_return_pct_none_not_a_crash():
    rows = [_row("Buy", "t1", 100.0), _row("Sell", "t2", None)]
    result = wallet_sim.walk(rows)
    assert result["round_trips"][0]["return_pct"] is None
    assert result["round_trips"][0]["exit_price"] is None


# --- mark_price open-position marking ------------------------------------------

def test_mark_price_marks_open_position():
    result = wallet_sim.walk([_row("Buy", "t1", 100.0)], mark_price=120.0)
    assert result["open"] == {
        "entry_price": 100.0, "entry_date": "t1",
        "mark_price": 120.0, "unrealized_return_pct": 20.0,
    }


def test_no_mark_price_still_reports_open_position_with_none_unrealized():
    result = wallet_sim.walk([_row("Buy", "t1", 100.0)])
    assert result["open"] == {
        "entry_price": 100.0, "entry_date": "t1",
        "mark_price": None, "unrealized_return_pct": None,
    }


def test_mark_price_ignored_when_flat_no_open_position():
    result = wallet_sim.walk([_row("Buy", "t1", 100.0), _row("Sell", "t2", 110.0)], mark_price=999.0)
    assert result["open"] is None


# --- non-negotiable: zero I/O --------------------------------------------------

def test_wallet_sim_module_has_zero_io_imports():
    src = inspect.getsource(wallet_sim)
    for forbidden in ("import state", "import supabase", "import requests", "state.client"):
        assert forbidden not in src, f"wallet_sim.py must have zero I/O — found {forbidden!r}"


def test_wallet_sim_module_has_no_insert_update_upsert_delete_calls():
    src = inspect.getsource(wallet_sim)
    import re
    # Exclude the module's own docstring (its prose literally names these calls).
    doc = wallet_sim.__doc__ or ""
    code_only = src.replace(doc, "")
    for pattern in (r"\.insert\(", r"\.update\(", r"\.upsert\(", r"\.delete\("):
        assert not re.search(pattern, code_only), f"wallet_sim.py must never write — found {pattern}"
