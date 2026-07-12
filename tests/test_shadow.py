"""shadow.py / run_shadow.py -- the shadow wallet pilot (FR24-FR29; REV-005
follow-up). Gemini (via the shared `ai_judge._client` seam) and Supabase are
fully mocked -- no real network/API/DB call is ever made in this suite.

Covers:
- `shadow.judge_batch_shadow`'s control flow, reusing the same fake-Gemini
  machinery as test_ai_judge.py (it shares ai_judge._client/_generate/
  _parse_batch/_models_to_try verbatim, per shadow.py's own docstring).
- `run_shadow._derive_shadow_positions`: the wallet-walk (flat->holding on
  Buy, holding->flat on Sell, Hold is a no-op, a redundant Buy while already
  holding is a no-op).
- `run_shadow._usable_market_data`: same-data reuse returns None on a
  no-price/no_data production row.
"""

import json

from conftest import FakeGeminiResponse

import ai_judge
import run_shadow
import shadow


# --- shadow.judge_batch_shadow: control flow (shares ai_judge machinery) -----

def _shadow_item(ticker="AAPL", state="flat", entry_price=None, entry_date=None):
    return {
        "data": {
            "ticker": ticker, "market": "US", "price": 100.0,
            "pct_change_1d": 1.0, "pct_change_5d": 2.0, "pct_change_20d": 3.0,
            "volume_vs_avg": 1.1, "fundamentals": {}, "headlines": [],
            "session_live": False, "volume_pro_rated": False,
        },
        "shadow_pos": {"state": state, "entry_price": entry_price, "entry_date": entry_date},
    }


def _verdict_json(ticker="AAPL", verdict="Buy"):
    return json.dumps([{"ticker": ticker, "verdict": verdict,
                        "confidence": "high", "rationale": "position-aware call"}])


def test_judge_batch_shadow_happy_path_uses_shared_client_seam(mock_gemini):
    client = mock_gemini([FakeGeminiResponse(_verdict_json())])

    result = shadow.judge_batch_shadow([_shadow_item("AAPL")])

    assert result["AAPL"]["verdict"] == "Buy"
    assert result["AAPL"]["parse_status"] == "ok"
    # confirms shadow really goes through the same fake client ai_judge uses,
    # i.e. it shares ai_judge._client() rather than constructing its own.
    assert len(client.models.calls) == 1


def test_judge_batch_shadow_uses_shadow_system_prompt_not_production_prompt(mock_gemini, monkeypatch):
    """The prompt content itself isn't the focus (per the task brief), but the
    control-flow guarantee that the SHADOW system prompt (position-aware
    addendum) -- not production's bare prompt -- is what's actually sent."""
    captured = {}
    real_generate = ai_judge._generate

    def _spy(client, model, prompt, cfg):
        captured["system_instruction"] = cfg.system_instruction
        return real_generate(client, model, prompt, cfg)

    monkeypatch.setattr(ai_judge, "_generate", _spy)
    mock_gemini([FakeGeminiResponse(_verdict_json())])

    shadow.judge_batch_shadow([_shadow_item("AAPL")])

    assert captured["system_instruction"] == shadow.SHADOW_SYSTEM_PROMPT
    assert captured["system_instruction"] != ai_judge.BATCH_SYSTEM_PROMPT


def test_judge_batch_shadow_empty_items_returns_empty_dict():
    assert shadow.judge_batch_shadow([]) == {}


def test_judge_batch_shadow_fails_safe_to_hold_on_hard_failure(mock_gemini):
    from conftest import FakeAPIError
    mock_gemini([FakeAPIError(code=404, status="NOT_FOUND")])

    result = shadow.judge_batch_shadow([_shadow_item("AAPL")])

    assert result["AAPL"]["verdict"] == "Hold"
    assert result["AAPL"]["parse_status"] == "api_error"


# --- run_shadow._derive_shadow_positions: the wallet-walk (FR25) -------------

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
    """Table-keyed in-memory double: `tables={"call_log_shadow": [...]}` is
    returned verbatim regardless of filters -- tests pre-shape the rows to
    exactly what the real filtered/ordered query would have returned."""

    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return FakeShadowQuery(self._tables.get(name, []))


def _shadow_row(ticker, verdict, timestamp, price=None):
    return {"ticker": ticker, "verdict": verdict, "timestamp": timestamp,
            "data_snapshot": {"price": price} if price is not None else {}}


def test_wallet_walk_buy_flips_flat_to_holding():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _shadow_row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=150.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["AAPL"]["entry_price"] == 150.0
    assert positions["AAPL"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_wallet_walk_sell_flips_holding_to_flat():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _shadow_row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=150.0),
        _shadow_row("AAPL", "Sell", "2026-07-11T09:00:00Z", price=160.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "flat"
    assert positions["AAPL"]["entry_price"] is None
    assert positions["AAPL"]["entry_date"] is None


def test_wallet_walk_hold_is_a_no_op():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _shadow_row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=150.0),
        _shadow_row("AAPL", "Hold", "2026-07-11T09:00:00Z", price=155.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["AAPL"]["entry_price"] == 150.0    # unchanged by the Hold row
    assert positions["AAPL"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_wallet_walk_redundant_buy_while_holding_is_a_no_op():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _shadow_row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=150.0),
        _shadow_row("AAPL", "Buy", "2026-07-11T09:00:00Z", price=170.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["AAPL"]["entry_price"] == 150.0    # the SECOND Buy is a no-op
    assert positions["AAPL"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_wallet_walk_empty_history_is_flat():
    sb = FakeShadowSupabase({"call_log_shadow": []})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"] == {"state": "flat", "entry_price": None, "entry_date": None}


def test_wallet_walk_full_cycle_buy_sell_buy():
    """flat -> holding (Buy) -> flat (Sell) -> holding (Buy) again, with the
    entry re-set to the SECOND Buy's price/date since the position had gone
    flat in between (not treated as redundant)."""
    sb = FakeShadowSupabase({"call_log_shadow": [
        _shadow_row("AAPL", "Buy", "2026-07-08T09:00:00Z", price=140.0),
        _shadow_row("AAPL", "Sell", "2026-07-09T09:00:00Z", price=145.0),
        _shadow_row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=150.0),
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["AAPL"]["entry_price"] == 150.0
    assert positions["AAPL"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_wallet_walk_covers_only_requested_tickers_independently():
    sb = FakeShadowSupabase({"call_log_shadow": [
        _shadow_row("AAPL", "Buy", "2026-07-10T09:00:00Z", price=150.0),
        _shadow_row("MSFT", "Sell", "2026-07-10T09:00:00Z", price=300.0),   # Sell-while-flat: no-op
    ]})
    positions = run_shadow._derive_shadow_positions(sb, ["AAPL", "MSFT"])

    assert positions["AAPL"]["state"] == "holding"
    assert positions["MSFT"]["state"] == "flat"


# --- run_shadow._usable_market_data: same-data reuse (FR26) -------------------

def test_usable_market_data_returns_none_when_no_price():
    row = {"ticker": "AAPL", "data_snapshot": {"parse_status": "no_data", "price": None}}
    assert run_shadow._usable_market_data(row) is None


def test_usable_market_data_returns_none_when_snapshot_missing_entirely():
    row = {"ticker": "AAPL", "data_snapshot": None}
    assert run_shadow._usable_market_data(row) is None


def test_usable_market_data_returns_merged_dict_when_price_present():
    row = {"ticker": "AAPL", "data_snapshot": {"price": 150.0, "pct_change_1d": 1.0}}
    data = run_shadow._usable_market_data(row)

    assert data is not None
    assert data["ticker"] == "AAPL"
    assert data["price"] == 150.0
    assert data["pct_change_1d"] == 1.0
