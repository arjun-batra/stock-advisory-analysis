"""Phase-4 whole-system closure — cross-increment interaction tests.

Not diff-scoped to one increment. `state.py` was modified by INC-8 (delivery-
confirmed alerting, FR34), INC-10 (currency-mismatch guard, `build_position`)
and INC-12 (`is_paused`/`KillSwitchAbort`, FR24/FR35); `run_hourly.py`/
`run_discovery.py` by INC-8 and INC-12; `ingest.py` by INC-9 (stale-bar
structural check, FR17). Each increment's own diff-scoped suite
(`tests/test_kill_switch_boundary.py`, `tests/test_state.py`,
`tests/test_ingest.py`, `tests/test_ai_judge.py`, `tests/test_run_orchestration.py`)
already proves each fix in isolation, against the real `run_hourly.main()`/
`run_discovery.main()`/`state.py` code, not mocked outcomes. This file drives
the SAME real code with two or more of those fixes triggered in the same run
or across consecutive runs of the same fixture data — the class of bug no
single increment's own diff-scoped pass could see.
"""

import datetime as dt

import pandas as pd

import config
import ingest
import run_discovery
import run_hourly
import state

from test_kill_switch_boundary import (
    FakeNotifier,
    _ai,
    _data,
    _sequenced_is_paused,
    _wl_row,
    sb,
    wire_discovery,
    wire_main,
)


# =============================================================================
# Combo 1 — INC-12's pause abort interacting with INC-8's delivery-confirmed
# alerting: a crossing left pending by a failed push, then a pause before the
# automatic retry.
# =============================================================================

def test_failed_push_then_paused_before_retry_leaves_crossing_pending_with_correct_abort_accounting(
        monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})

    # --- Cycle 1: not paused, but the real push itself fails (INC-8). ------
    failing_notifier = FakeNotifier(returns=False)
    monkeypatch.setattr(run_hourly.notify, "get_notifier", lambda: failing_notifier)
    monkeypatch.setattr(state, "is_paused", lambda sb: False)

    run_hourly.main()

    assert len(sb.call_log) == 1
    assert sb.call_log[0]["alerted"] is False
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Hold"   # unchanged -- still pending
    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"   # push-failed counts as degraded
    assert sb.abort_log == []   # no pause involved this cycle
    heartbeat_after_cycle1 = dict(sb.run_heartbeat["hourly-watchlist"])

    # --- Cycle 2: the SAME still-pending crossing is retried (FR34) -- but
    #     the operator pauses the kill switch right before the retry's own
    #     checkpoint-3 push attempt. -----------------------------------------
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    retry_notifier = FakeNotifier(returns=True)   # would succeed if it were ever reached
    monkeypatch.setattr(run_hourly.notify, "get_notifier", lambda: retry_notifier)
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, True))

    run_hourly.main()

    assert retry_notifier.calls == []   # the retry attempt itself never reached notifier.push
    assert len(sb.call_log) == 1        # no second call_log row written -- still only cycle 1's
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Hold"   # still exactly as pending
    assert sb.run_heartbeat["hourly-watchlist"] == heartbeat_after_cycle1   # untouched by the abort
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"
    assert sb.abort_log[0]["workflow"] == "hourly-watchlist"
    # AAPL is the only ticker and it aborted at its OWN checkpoint 3, the
    # first (and only) ticker touched this cycle -- outcomes is a fresh
    # Counter() per main() call, so cycle 1's push-failed does not leak into
    # cycle 2's real_rows_this_cycle.
    assert sb.abort_log[0]["real_rows_this_cycle"] == 0

    # --- Cycle 3: resume. The retry now genuinely fires and the crossing
    #     finally advances -- FR34/FR35's combined "no new resume logic
    #     needed" claim, proven across a push-failure AND a pause on the SAME
    #     crossing's history, not just one or the other in isolation. --------
    monkeypatch.setattr(state, "is_paused", lambda sb: False)
    final_notifier = FakeNotifier(returns=True)
    monkeypatch.setattr(run_hourly.notify, "get_notifier", lambda: final_notifier)

    run_hourly.main()

    assert len(final_notifier.calls) == 1
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"
    assert len(sb.call_log) == 2
    assert sb.call_log[1]["alerted"] is True
    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "ok"


# =============================================================================
# Combo 2 — a currency-mismatched holding (INC-10) whose ticker also hits the
# stale-bar path (INC-9), across two consecutive cycles, through the REAL
# ingest.py + state.py + run_hourly.py code (not mocked at the outcome level).
# =============================================================================

class _FrozenDatetimeBase(dt.datetime):
    """Same technique as tests/test_ingest.py's own stale-bar tests: freeze
    `ingest.datetime.now(tz)` so the stale-bar comparison is deterministic."""
    _instant = None

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._instant
        return cls._instant.astimezone(tz)


def _freeze(monkeypatch, instant):
    frozen = type("FrozenDatetime", (_FrozenDatetimeBase,), {"_instant": instant})
    monkeypatch.setattr(ingest, "datetime", frozen)


class _StaleBarTicker:
    """A yf.Ticker double whose only bar predates 'today' -- INC-9/DEEP-004's
    stale-bar shape. get_market_data returns before fundamentals/news are
    ever touched on this path (proved by test_ingest.py's own equivalent
    test), so they don't need to be realistic here."""

    def __init__(self, ticker, closes, index):
        self.ticker = ticker
        self._closes = closes
        self._index = index

    def history(self, period=None, auto_adjust=False):
        return pd.DataFrame({"Close": self._closes, "Volume": [1_000] * len(self._closes)},
                             index=self._index)

    @property
    def fast_info(self):
        return {}

    @property
    def info(self):
        return {}

    @property
    def news(self):
        return []


class _LiveMismatchedCurrencyTicker:
    """A genuinely live (non-stale, last bar dated today) read whose
    fundamentals.currency is CAD -- triggers INC-10's build_position
    mismatch guard against a holding recorded in USD."""

    def __init__(self, ticker, closes, index):
        self.ticker = ticker
        self._closes = closes
        self._index = index
        self.fast_info = {"currency": "CAD"}

    def history(self, period=None, auto_adjust=False):
        return pd.DataFrame({"Close": self._closes, "Volume": [1_000] * len(self._closes)},
                             index=self._index)

    @property
    def info(self):
        return {}

    @property
    def news(self):
        return []


def test_currency_mismatched_holding_whose_ticker_also_hits_the_stale_bar_path(
        monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("SHOP.TO", "TSX")]
    sb.holdings = [{"ticker": "SHOP.TO", "shares": 10, "cost_basis": 100.0, "currency": "USD"}]
    monkeypatch.setattr(state, "is_paused", lambda sb: False)
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"SHOP.TO": _ai("Buy")})

    build_position_calls = []
    real_build_position = state.build_position

    def _spy_build_position(holding, data):
        build_position_calls.append((holding, data))
        return real_build_position(holding, data)
    monkeypatch.setattr(run_hourly.state, "build_position", _spy_build_position)

    # --- Cycle 1: the ticker's only available bar is stale (INC-9). --------
    frozen_now = dt.datetime(2026, 7, 30, 11, 0, tzinfo=config.MARKET_TZ)   # Thu, mid-session ET
    _freeze(monkeypatch, frozen_now)
    stale_idx = pd.date_range(end=dt.date(2026, 7, 27), periods=5, freq="D")   # 3 days stale
    monkeypatch.setattr(
        ingest.yf, "Ticker",
        lambda ticker: _StaleBarTicker(ticker, [50.0, 51.0, 52.0, 51.5, 53.0], stale_idx))

    run_hourly.main()

    assert build_position_calls == []   # the stale-bar skip happens BEFORE build_position is ever reached
    assert len(sb.call_log) == 1
    assert sb.call_log[0]["data_snapshot"]["parse_status"] == "no_data"
    assert "SHOP.TO" not in sb.verdict_state   # log_skip never touches verdict_state
    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"   # INC-8: skip counts as degraded

    # --- Cycle 2: the SAME ticker gets a genuinely live, non-stale read, but
    #     its fundamentals currency (CAD) disagrees with the recorded holding
    #     currency (USD) -- INC-10's mismatch guard. -------------------------
    live_idx = pd.date_range(end=dt.date(2026, 7, 30), periods=5, freq="D")   # last bar IS today
    monkeypatch.setattr(
        ingest.yf, "Ticker",
        lambda ticker: _LiveMismatchedCurrencyTicker(ticker, [50.0, 51.0, 52.0, 51.5, 53.0], live_idx))
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)

    run_hourly.main()

    assert len(build_position_calls) == 1
    holding_arg, data_arg = build_position_calls[0]
    assert holding_arg["currency"] == "USD"
    assert data_arg["fundamentals"]["currency"] == "CAD"
    assert len(sb.call_log) == 2
    position = sb.call_log[1]["data_snapshot"]["position"]
    assert position["currency_mismatched"] is True
    assert position["pl_pct"] is None   # FR11: suppressed, not computed from mismatched currencies
    assert sb.call_log[1]["data_snapshot"]["price"] == 53.0
    # The stale-bar skip in cycle 1 never wrote a verdict_state row, so cycle
    # 2's live read is a cold start -- the mismatch guard fires on the FIRST
    # genuine reading this ticker ever produced, not a later one.
    assert sb.verdict_state["SHOP.TO"]["current_verdict"] == "Buy"


# =============================================================================
# Combo 3 — an all-`no-read` run (INC-8's degraded accounting) that also
# aborts at a checkpoint (INC-12's FR35 classification): FR35 must not
# suppress the genuine degraded (no-read) signal, even though the abort
# correctly suppresses the heartbeat write itself.
# =============================================================================

def test_all_no_read_batch_that_aborts_mid_cycle_preserves_the_degraded_count_in_the_abort_row(
        monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("MSFT", "US"), _wl_row("GOOG", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    sb.verdict_state["MSFT"] = {"ticker": "MSFT", "current_verdict": "Hold"}
    sb.verdict_state["GOOG"] = {"ticker": "GOOG", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})

    def _judge(items, models=None):
        return {
            "AAPL": _ai("Hold", parse_status="failed"),     # genuine AI parse failure -- no-read
            "MSFT": _ai("Hold", parse_status="api_error"),  # genuine AI rate-limit -- no-read
            "GOOG": _ai("Buy"),                              # a real, clean verdict crossing
        }
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch", _judge)
    # False at checkpoint 1, False at checkpoint 2. AAPL/MSFT's no-read branch
    # never calls is_paused() at all (the guard sits only in the "change"
    # branch), so the next and only remaining is_paused() call is GOOG's own
    # checkpoint 3, which aborts.
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, True))

    run_hourly.main()

    assert sb.run_heartbeat == {}   # FR35: no heartbeat row at all this cycle -- by design
    assert len(sb.call_log) == 2    # AAPL and MSFT's no-read rows were genuinely written (FR15)
    assert {r["ticker"] for r in sb.call_log} == {"AAPL", "MSFT"}
    assert all(r["data_snapshot"]["parse_status"] in ("failed", "api_error") for r in sb.call_log)
    assert sb.verdict_state["GOOG"]["current_verdict"] == "Hold"   # GOOG's crossing left exactly pending

    # The degraded signal (2 genuine no-reads) is not lost: it survives in
    # the one record this cycle DOES leave behind -- the abort row's
    # causal-tie count. If FR35's accounting silently zeroed or excluded
    # no-read outcomes here, this assertion would catch it.
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"
    assert sb.abort_log[0]["real_rows_this_cycle"] == 2


# =============================================================================
# Combo 4 — discovery's candidate path, which INC-8, INC-9, and INC-12 all
# touch: a stale-bar ingest skip (INC-9), a confirmed push failure with no
# abort (INC-8), and a checkpoint-3 abort (INC-12), in one discovery run.
# =============================================================================

def test_discovery_candidate_path_combines_stale_skip_delivery_failure_and_pause_abort(
        monkeypatch, wire_discovery):
    sb = wire_discovery
    monkeypatch.setattr(
        run_discovery.prefilter, "find_candidates",
        lambda exclude, region: (
            [{"ticker": "STALECO", "signals": ["gainer"]},
             {"ticker": "FAILCO", "signals": ["gainer"]},
             {"ticker": "ABORTCO", "signals": ["gainer"]}],
            3, 0, {"raw": 3, "after_dedup": 3, "passed_quality": 3, "passed_signal": 3}))

    def _fake_market_data(ticker):
        if ticker == "STALECO":
            return {**_data(ticker), "has_price": False,
                     "notes": ["market appears closed today"]}
        return {**_data(ticker), "has_price": True}
    monkeypatch.setattr(run_discovery.ingest, "get_market_data", _fake_market_data)
    monkeypatch.setattr(run_discovery.ai_judge, "judge_batch",
                         lambda items, models=None: {"FAILCO": _ai("Buy"), "ABORTCO": _ai("Buy")})
    failing_notifier = FakeNotifier(returns=False)
    monkeypatch.setattr(run_discovery.notify, "get_notifier", lambda: failing_notifier)
    # False at checkpoint 1 (main entry), False at checkpoint 2 (ai_call,
    # after Phase-1 ingest -- STALECO already skipped by then), False at
    # FAILCO's checkpoint 3 (proceeds, its push genuinely fails), True at
    # ABORTCO's checkpoint 3 (aborts).
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, False, True))

    run_discovery.main()

    # STALECO: INC-9's stale-bar path -- skipped before the AI call, logged
    # (FR15), never reaches process_candidate/checkpoint 3 at all.
    staleco_rows = [r for r in sb.call_log if r["ticker"] == "STALECO"]
    assert len(staleco_rows) == 1
    assert staleco_rows[0]["data_snapshot"]["parse_status"] == "no_data"

    # FAILCO: INC-8's delivery-confirmed gate -- a real, confirmed push
    # failure, logged with alerted=False, no abort involved.
    failco_rows = [r for r in sb.call_log if r["ticker"] == "FAILCO"]
    assert len(failco_rows) == 1
    assert failco_rows[0]["alerted"] is False

    # ABORTCO: INC-12's checkpoint 3 -- nothing written for it at all (a
    # candidate abort leaves it exactly as unlogged as if this cycle had
    # never reached it).
    assert not any(r["ticker"] == "ABORTCO" for r in sb.call_log)

    assert sb.run_heartbeat == {}   # FR35: no heartbeat row this cycle
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"
    assert sb.abort_log[0]["workflow"] == "daily-discovery"
    # FAILCO's confirmed push-failure counts toward real_rows_this_cycle (a
    # genuine AI verdict was produced and a genuine delivery attempt was made
    # and failed); STALECO's stale-bar skip does NOT (it never reached the AI
    # at all) -- the precise boundary FR35's causal-tie accounting draws.
    assert sb.abort_log[0]["real_rows_this_cycle"] == 1
