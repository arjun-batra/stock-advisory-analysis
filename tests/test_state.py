"""state.py — the single-rule verdict-change state machine (FR7, FR8, FR15) and
the discovery Buy-only push gate (FR4 Decision #16). This is the load-bearing
core the whole product's alerting behavior rests on (docs/design.md §0 #1/#2,
docs/design/data-and-flow.md §6).

Supabase is faked in-memory (no network, no real client) so the state machine
is exercised exactly the way `state.process_ticker` / `state.process_candidate`
call it in production, without touching a real database.
"""

import datetime as _dt

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
            return self._execute_select(verb)
        if verb.kind == "insert":
            return self._execute_insert(verb)
        if verb.kind == "upsert":
            return self._execute_upsert(verb)
        if verb.kind == "update":
            return self._execute_update(verb)
        raise AssertionError(f"unexpected verb {verb.kind}")

    def _execute_select(self, verb: _Verb):
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

    def _execute_insert(self, verb: _Verb):
        row = dict(verb.payload)
        row["id"] = f"log-{self._next_id}"
        self._next_id += 1
        self.call_log.append(row)
        return _Result([row])

    def _execute_upsert(self, verb: _Verb):
        if verb.table == "verdict_state":
            ticker = verb.payload["ticker"]
            self.verdict_state[ticker] = dict(verb.payload)
            return _Result([verb.payload])
        if verb.table == "run_heartbeat":
            self.run_heartbeat[verb.payload["workflow_name"]] = verb.payload
            return _Result([verb.payload])
        return _Result([verb.payload])

    def _execute_update(self, verb: _Verb):
        if verb.table == "verdict_state":
            ticker = verb._filters.get("ticker")
            self.verdict_state.setdefault(ticker, {}).update(verb.payload)
            return _Result([self.verdict_state[ticker]])
        return _Result([])


class FakeNotifier:
    """Delivery-aware double for the FR34/DEEP-002 contract (components.md
    §4.6): push() must report True/False/None, not just "was called".

    `returns` is what a bare `FakeNotifier()` gives back on every push (default
    True -- an ordinary successful send, which is what most of this suite's
    pre-existing tests actually intend to exercise; a plain "was push() called"
    test never cared about the return value before FR34 existed). `queue`, if
    given, overrides `returns` and is consumed one value per call (for tests
    that need a scripted fail-then-succeed sequence, e.g. AC5's retry flow) --
    once exhausted, falls back to `returns`.
    """

    def __init__(self, returns=True, queue=None):
        self.calls = []
        self.returns = returns
        self.queue = list(queue) if queue is not None else None

    def push(self, ticker, verdict, rationale, *, kind, log_id, market=None):
        self.calls.append(dict(ticker=ticker, verdict=verdict, rationale=rationale,
                                kind=kind, log_id=log_id, market=market))
        if self.queue:
            return self.queue.pop(0)
        return self.returns


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


# --- build_position currency-mismatch guard (FR11/FR29, DEEP-006, INC-10) -------
# sql/holdings_currency_derivation.sql guarantees holdings.currency agrees with
# watchlist.market, but not that watchlist.market is itself correct for the ticker's
# real listing. This is the second, independent Python-layer defense for that residual
# case -- it operates purely on whatever currency value it is handed at call time, so
# it also protects a pre-existing holdings row the DB trigger has not yet re-derived
# (the trigger only fires on INSERT/UPDATE; a row nobody writes to keeps its old value
# until its next write) -- there is nothing DB-trigger-specific this guard depends on.

def test_build_position_suppresses_pl_pct_on_currency_mismatch(capsys):
    """A .TO holding whose currency disagrees with the independently-fetched
    fundamentals currency (the DEEP-006 repro: watchlist.market wrong for this
    ticker, or a stale pre-trigger row) must not compute a wrong pl_pct."""
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "USD"}
    data = {"ticker": "SHOP.TO", "price": 68.0, "fundamentals": {"currency": "CAD"}}
    pos = state.build_position(holding, data)
    assert pos["pl_pct"] is None
    assert pos["currency"] == "USD"  # holding's stored currency is still reported as-is
    log = capsys.readouterr().out
    assert "WARNING" in log
    assert "SHOP.TO" in log
    assert "USD" in log and "CAD" in log


def test_build_position_computes_normally_when_currencies_agree(capsys):
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "CAD"}
    data = {"ticker": "SHOP.TO", "price": 60.0, "fundamentals": {"currency": "CAD"}}
    pos = state.build_position(holding, data)
    assert pos["pl_pct"] == 20.0
    assert "WARNING" not in capsys.readouterr().out


def test_build_position_missing_fundamentals_currency_is_unknown_not_mismatch(capsys):
    """A missing (not merely differing) fundamentals currency is "unknown", not
    "disagrees" -- pl_pct must still compute, matching pre-INC-10 behavior (also
    covers a pre-existing holdings row the currency-derivation trigger has not
    reprocessed, and any caller that omits `fundamentals` entirely)."""
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "USD"}
    data = {"ticker": "AAPL", "price": 60.0}  # no "fundamentals" key at all
    pos = state.build_position(holding, data)
    assert pos["pl_pct"] == 20.0
    assert "WARNING" not in capsys.readouterr().out

    data_empty_fundamentals = {"ticker": "AAPL", "price": 60.0, "fundamentals": {}}
    pos2 = state.build_position(holding, data_empty_fundamentals)
    assert pos2["pl_pct"] == 20.0


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


# --- INC-8 / FR34 / DEEP-002: delivery-confirmed alerting ----------------------
# components.md §4.6, increment-plan.md INC-8 AC5/AC6/AC7.

def test_ai_failure_fail_safe_guard_is_untouched_by_delivery_gating(sb):
    """Highest-stakes assertion in this increment (per qa brief): an AI/Gemini
    failure (parse_status in failed/api_error) must still leave current_verdict
    UNCHANGED and fire NO alert at all, regardless of anything push() would
    have returned -- state.py:256's pre-existing fail-safe guard (load-bearing
    #8) is untouched by INC-8. Proven by BEHAVIOR: a notifier that would
    deliver successfully (returns=True) is wired in, and the guard must still
    never call it. A regression here would fabricate advice."""
    notifier = FakeNotifier(returns=True)
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start, Buy
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(),
                                    _ai("Sell", parse_status="failed"), NOW)

    assert outcome == "no-read"
    assert notifier.calls == []                                   # push() never even called
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"    # state NOT advanced
    assert sb.call_log[-1]["alerted"] is False


def test_ai_api_error_fail_safe_guard_is_untouched_by_delivery_gating(sb):
    """Same guard, the other fail-safe parse_status value (api_error)."""
    notifier = FakeNotifier(returns=True)
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Hold"), NOW)  # cold start, Hold
    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(),
                                    _ai("Buy", parse_status="api_error"), NOW)

    assert outcome == "no-read"
    assert notifier.calls == []
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Hold"
    assert sb.call_log[-1]["alerted"] is False


def test_failed_push_leaves_state_pending_then_retries_and_succeeds(sb):
    """AC5, exact flow named in increment-plan.md: fail once, retry on the next
    cycle with the SAME new verdict, succeed, and only then does state advance.
    All three assertions belong in one flow per the AC's own framing."""
    notifier = FakeNotifier(queue=[False, True])   # first change-push fails, retry succeeds
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start (no push call)

    # First attempt at the crossing: push fails.
    outcome1 = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), NOW)
    assert outcome1 == "push-failed"
    assert sb.call_log[-1]["alerted"] is False
    assert sb.call_log[-1]["alert_type"] == "change"                # attempted, not silently dropped
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"      # OLD verdict, unchanged
    assert len(notifier.calls) == 1

    # Next cycle: same new AI verdict (Sell) is re-evaluated against the still-
    # unadvanced prior verdict (Buy) -- push is retried automatically.
    later = NOW + _dt.timedelta(minutes=30)
    outcome2 = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), later)
    assert outcome2 == "change-alert"
    assert len(notifier.calls) == 2                                  # push() fired again for the SAME crossing
    assert notifier.calls[1]["verdict"] == "Sell"
    assert sb.call_log[-1]["alerted"] is True
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Sell"      # now advances


def test_ai_failure_while_a_push_failed_crossing_is_pending_does_not_alert_or_advance(sb):
    """Interaction of both DEEP-001/DEEP-002 fixes: a crossing already left
    pending by a failed push must NOT be disturbed by a subsequent AI-call
    failure -- the fail-safe guard fires first, no push is attempted, and the
    still-unadvanced OLD verdict is untouched, so the genuine retry is not
    lost or corrupted by an unrelated bad AI cycle in between."""
    notifier = FakeNotifier(returns=False)   # every real push attempt fails
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start, Buy

    outcome1 = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), NOW)
    assert outcome1 == "push-failed"
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"
    calls_after_first = len(notifier.calls)

    # Next cycle: the AI call itself fails (unrelated transient outage).
    later = NOW + _dt.timedelta(minutes=30)
    outcome2 = state.process_ticker(sb, notifier, _wl_row(), _data(),
                                     _ai("Sell", parse_status="api_error"), later)
    assert outcome2 == "no-read"
    assert len(notifier.calls) == calls_after_first   # no push attempted this cycle
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"   # still the old, unadvanced verdict
    assert sb.call_log[-1]["alerted"] is False


def test_failed_push_then_verdict_changes_again_retries_current_not_stale_verdict(sb):
    """Not named by any single AC, but follows directly from FR34's "leave the
    crossing unadvanced" contract: if a failed push leaves current_verdict at
    the OLD value, and the AI's verdict has changed AGAIN by the next cycle,
    the retry must push the NEW (current) verdict, not replay the stale one
    that failed to send. Getting this backwards would mean a real 500 on a
    Buy->Sell crossing, followed by the AI flipping to Hold before the retry,
    silently sends a Sell alert for a company the AI no longer rates Sell --
    the difference between a useful retry and misleading advice."""
    notifier = FakeNotifier(queue=[False, True])   # Buy->Sell push fails; the retry (with Hold) succeeds
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start, Buy

    outcome1 = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), NOW)  # Buy->Sell fails
    assert outcome1 == "push-failed"
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"

    # AI's verdict has moved on to Hold by the next cycle -- NOT a replay of
    # the stale failed "Sell" push.
    later = NOW + _dt.timedelta(minutes=30)
    outcome2 = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Hold"), later)
    assert outcome2 == "change-alert"
    assert notifier.calls[-1]["verdict"] == "Hold"          # pushes the CURRENT verdict
    assert sb.call_log[-1]["verdict"] == "Hold"
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Hold"


def test_dry_run_push_logs_undelivered_but_still_advances_state_no_backlog(sb):
    """AC6, both halves asserted in one block per the AC's own reasoning: a dry
    run (delivered=None) writes alerted=False (honest -- nothing was sent) but
    DOES advance verdict_state (no backlog buildup), and the immediately-
    following identical-verdict check comes back 'quiet', not a second alert
    (confirms no backlog dump)."""
    notifier = FakeNotifier(returns=None)   # DryRunNotifier-equivalent: always None
    state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Buy"), NOW)   # cold start, Buy

    outcome = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), NOW)
    assert outcome == "change-alert"
    assert sb.call_log[-1]["alerted"] is False                        # honest: nothing was sent
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Sell"       # advances, no backlog

    # Next cycle, same (now current) verdict -> genuinely quiet, not a re-push.
    later = NOW + _dt.timedelta(minutes=30)
    outcome2 = state.process_ticker(sb, notifier, _wl_row(), _data(), _ai("Sell"), later)
    assert outcome2 == "quiet"
    assert len(notifier.calls) == 1   # no second push fired


def test_discovery_candidate_dry_run_excluded_from_recent_pushed_dedup(sb):
    """AC7: a candidate pushed via a dry run (delivered=None) has alerted=False,
    and recently_pushed_candidates() -- Decision #32's 7-day cooldown, keyed on
    alerted=True -- does NOT include it, so it naturally resurfaces next scan."""
    notifier = FakeNotifier(returns=None)
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"),
                                       {"verdict": "Buy", "rationale": "breakout"}, push=True)
    assert outcome == "candidate-pushed"
    assert sb.call_log[0]["alerted"] is False
    assert "NEWCO" not in state.recently_pushed_candidates(sb, days=7)


def test_discovery_candidate_failed_push_excluded_from_recent_pushed_dedup(sb):
    """AC7, the other half: a candidate whose real push FAILED also has
    alerted=False and is not falsely deduped for the cooldown window."""
    notifier = FakeNotifier(returns=False)
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"),
                                       {"verdict": "Buy", "rationale": "breakout"}, push=True)
    assert outcome == "candidate-push-failed"
    assert sb.call_log[0]["alerted"] is False
    assert "NEWCO" not in state.recently_pushed_candidates(sb, days=7)


def test_discovery_candidate_successful_push_is_deduped(sb):
    """Counterpart/regression guard: a genuinely delivered candidate push IS
    included in the dedup set -- proves the exclusion above is about delivery
    status, not a broken filter that excludes everything."""
    notifier = FakeNotifier(returns=True)
    outcome = state.process_candidate(sb, notifier, _data("NEWCO"),
                                       {"verdict": "Buy", "rationale": "breakout"}, push=True)
    assert outcome == "candidate-pushed"
    assert sb.call_log[0]["alerted"] is True
    assert "NEWCO" in state.recently_pushed_candidates(sb, days=7)
