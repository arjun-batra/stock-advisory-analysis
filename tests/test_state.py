"""state.py — the single-rule verdict-change state machine (FR7, FR8, FR15) and
the discovery Buy-only push gate (FR4 Decision #16). This is the load-bearing
core the whole product's alerting behavior rests on (docs/design.md §0 #1/#2,
docs/design/data-and-flow.md §6).

Supabase is faked in-memory (no network, no real client) so the state machine
is exercised exactly the way `state.process_ticker` / `state.process_candidate`
call it in production, without touching a real database.
"""

import pytest

import state


# --- a tiny in-memory double for the Supabase python client, covering only ---
# --- the exact call chains state.py issues ------------------------------------

class _Result:
    def __init__(self, data):
        self.data = data


class _Verb:
    def __init__(self, backend, table, kind, payload=None):
        self.backend = backend
        self.table = table
        self.kind = kind
        self.payload = payload
        self._filters = {}

    def select(self, *_a):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def limit(self, _n):
        return self

    def gte(self, *_a):
        return self

    def execute(self):
        return self.backend._execute(self)


class FakeTable:
    def __init__(self, backend, name):
        self.backend = backend
        self.name = name

    def select(self, *_a):
        return _Verb(self.backend, self.name, "select")

    def insert(self, row):
        return _Verb(self.backend, self.name, "insert", row)

    def upsert(self, row):
        return _Verb(self.backend, self.name, "upsert", row)

    def update(self, fields):
        return _Verb(self.backend, self.name, "update", fields)


class FakeSupabase:
    """In-memory stand-in for the pieces of the Supabase client state.py uses."""

    def __init__(self):
        self.watchlist = []
        self.holdings = []
        self.verdict_state = {}   # ticker -> dict
        self.call_log = []        # list of dict rows (insertion order)
        self.run_heartbeat = {}
        self._next_id = 1

    def table(self, name):
        return FakeTable(self, name)

    def _execute(self, verb: _Verb):
        if verb.kind == "select":
            if verb.table == "watchlist":
                return _Result(list(self.watchlist))
            if verb.table == "holdings":
                return _Result(list(self.holdings))
            if verb.table == "verdict_state":
                ticker = verb._filters.get("ticker")
                row = self.verdict_state.get(ticker)
                return _Result([row] if row else [])
            if verb.table == "call_log":
                rows = self.call_log
                for col, val in verb._filters.items():
                    rows = [r for r in rows if r.get(col) == val]
                return _Result(rows)
            return _Result([])

        if verb.kind == "insert":
            row = dict(verb.payload)
            row["id"] = f"log-{self._next_id}"
            self._next_id += 1
            self.call_log.append(row)
            return _Result([row])

        if verb.kind == "upsert":
            if verb.table == "verdict_state":
                ticker = verb.payload["ticker"]
                self.verdict_state[ticker] = dict(verb.payload)
                return _Result([verb.payload])
            if verb.table == "run_heartbeat":
                self.run_heartbeat[verb.payload["workflow_name"]] = verb.payload
                return _Result([verb.payload])
            return _Result([verb.payload])

        if verb.kind == "update":
            if verb.table == "verdict_state":
                ticker = verb._filters.get("ticker")
                self.verdict_state.setdefault(ticker, {}).update(verb.payload)
                return _Result([self.verdict_state[ticker]])
            return _Result([])

        raise AssertionError(f"unexpected verb {verb.kind}")


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def push(self, ticker, verdict, rationale, *, kind, log_id, market=None):
        self.calls.append(dict(ticker=ticker, verdict=verdict, rationale=rationale,
                                kind=kind, log_id=log_id, market=market))


# --- fixtures ------------------------------------------------------------------

@pytest.fixture
def sb():
    return FakeSupabase()


@pytest.fixture
def notifier():
    return FakeNotifier()


def _wl_row(ticker="AAPL", market="US"):
    return {"ticker": ticker, "market": market}


def _data(ticker="AAPL", market="US"):
    return {"ticker": ticker, "market": market, "price": 100.0,
            "pct_change_1d": 1.0, "pct_change_5d": 2.0, "pct_change_20d": 3.0,
            "volume_vs_avg": 1.1, "fundamentals": {}, "headlines": []}


def _ai(verdict="Buy", parse_status="ok", rationale="looks good"):
    return {"verdict": verdict, "rationale": rationale, "confidence": "high",
            "parse_status": parse_status, "raw_model_response": "{}",
            "model_used": "gemini-3.5-flash", "usage": None, "fallback_from": None,
            "retry_count": 0}


import datetime as _dt

NOW = _dt.datetime(2026, 7, 12, 14, 0, tzinfo=_dt.timezone.utc)


# --- FR15: cold start ----------------------------------------------------------

def test_cold_start_logs_but_does_not_alert(sb, notifier):
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)

    assert outcome == "cold-start"
    assert len(sb.call_log) == 1
    row = sb.call_log[0]
    assert row["alerted"] is False
    assert row["alert_type"] is None
    assert row["verdict"] == "Buy"
    assert notifier.calls == []                       # FR8/§0#2: no bootstrap alert
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"


def test_cold_start_with_failed_parse_does_not_create_state(sb, notifier):
    """A fail-safe Hold at cold start must still log (FR15) but must NOT seed
    verdict_state with the fabricated Hold (load-bearing #8 guard)."""
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(),
                                    _ai("Hold", parse_status="api_error"), NOW)
    assert outcome == "no-read"
    assert len(sb.call_log) == 1
    assert sb.call_log[0]["alerted"] is False
    assert "AAPL" not in sb.verdict_state
    assert notifier.calls == []


# --- FR8: no-change -> silence, still logged -----------------------------------

def test_no_change_is_silent_but_logged(sb, notifier):
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)

    assert outcome == "quiet"
    assert len(sb.call_log) == 2
    assert sb.call_log[1]["alerted"] is False
    assert sb.call_log[1]["alert_type"] is None
    assert notifier.calls == []
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"


# --- FR7: any change fires an immediate alert, incl. a change TO Hold ---------

@pytest.mark.parametrize("before,after", [
    ("Buy", "Sell"),
    ("Buy", "Hold"),        # FR7 explicitly: a weakening Buy->Hold is itself a signal
    ("Hold", "Buy"),
    ("Sell", "Buy"),
    ("Sell", "Hold"),
    ("Hold", "Sell"),
])
def test_any_verdict_change_fires_immediate_alert(sb, notifier, before, after):
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai(before), NOW)   # cold start
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai(after), NOW)

    assert outcome == "change-alert"
    assert len(notifier.calls) == 1
    assert notifier.calls[0]["verdict"] == after
    assert notifier.calls[0]["kind"] == "change"
    assert sb.call_log[-1]["alerted"] is True
    assert sb.call_log[-1]["alert_type"] == "change"
    assert sb.verdict_state["AAPL"]["current_verdict"] == after


@pytest.mark.parametrize("verdict", ["Buy", "Sell", "Hold"])
def test_no_change_case_for_every_verdict_is_silent(sb, notifier, verdict):
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai(verdict), NOW)
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai(verdict), NOW)
    assert outcome == "quiet"
    assert notifier.calls == []


def test_no_frequency_cap_alerts_on_every_flip(sb, notifier):
    """§0 #1: no cooldown/debounce — a choppy sequence alerts on every crossing."""
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), NOW)
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), NOW)

    assert len(notifier.calls) == 3
    assert [c["verdict"] for c in notifier.calls] == ["Sell", "Buy", "Sell"]


# --- load-bearing #8: a fail-safe Hold can never fabricate a change alert -----

def test_failed_parse_after_established_state_does_not_alert_or_advance(sb, notifier):
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start, Buy
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(),
                                    _ai("Sell", parse_status="failed"), NOW)

    assert outcome == "no-read"
    assert notifier.calls == []                                  # no fabricated alert
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"   # state NOT advanced
    assert sb.call_log[-1]["alerted"] is False


def test_failed_parse_row_is_still_logged_for_track_record(sb, notifier):
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Hold", parse_status="api_error"), NOW)
    assert len(sb.call_log) == 2   # FR15: every check logs, including non-reads


# --- log_skip (FR15/FR17 skip-with-log) ----------------------------------------

def test_log_skip_writes_quiet_no_data_row_and_does_not_touch_state(sb):
    state.log_skip(sb, "MSFT", ["history error: timeout"])
    assert len(sb.call_log) == 1
    row = sb.call_log[0]
    assert row["alerted"] is False
    assert row["alert_type"] is None
    assert row["data_snapshot"]["parse_status"] == "no_data"
    assert "MSFT" not in sb.verdict_state


# --- build_position (FR2/FR11) --------------------------------------------------

def test_build_position_computes_pl_pct():
    holding = {"shares": 10, "cost_basis": 100.0, "currency": "USD"}
    pos = state.build_position(holding, {"price": 120.0})
    assert pos["pl_pct"] == 20.0


def test_build_position_none_for_watch_only():
    assert state.build_position(None, {"price": 120.0}) is None


def test_build_position_handles_zero_cost_basis_without_crash():
    holding = {"shares": 10, "cost_basis": 0, "currency": "USD"}
    pos = state.build_position(holding, {"price": 120.0})
    assert pos["pl_pct"] is None


# --- process_candidate (discovery, FR4 Decision #16: Buy-only push) -----------

def test_discovery_buy_pushes(sb, notifier):
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"), {"verdict": "Buy", "rationale": "breakout"},
                                       push=True)
    assert outcome == "candidate-pushed"
    assert len(notifier.calls) == 1
    assert sb.call_log[0]["alerted"] is True


@pytest.mark.parametrize("verdict", ["Hold", "Sell"])
def test_discovery_hold_and_sell_are_logged_silently(sb, notifier, verdict):
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"), {"verdict": verdict, "rationale": "meh"},
                                       push=True)
    assert outcome == "candidate-logged"
    assert notifier.calls == []
    assert sb.call_log[0]["alerted"] is False


def test_discovery_buy_within_cooldown_not_pushed(sb, notifier):
    """push=False simulates the 7-day dedup cooldown suppression (design 4.3)."""
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"), {"verdict": "Buy", "rationale": "breakout"},
                                       push=False)
    assert outcome == "candidate-logged"
    assert notifier.calls == []
    assert sb.call_log[0]["alerted"] is False


def test_discovery_failed_parse_never_pushes(sb, notifier):
    ai = {"verdict": "Buy", "rationale": "n/a", "parse_status": "failed"}
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"), ai, push=True)
    assert outcome == "no-read"
    assert notifier.calls == []
