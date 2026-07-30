"""INC-12 — kill-switch in-flight boundary checks + mid-run-abort classification
(FR24, FR35; DEEP-007; docs/design/operational-controls.md §13.6).

Every scenario in this file was previously verified only with dev's throwaway
scratch harness (docs/handoff.md's INC-12 entry, "Known limitations" section) —
none of it was guarded by a committed test before this file. Reuses the
FakeSupabase/FakeNotifier/_wl_row/_data/_ai doubles from test_state.py (same
convention test_run_orchestration.py already established: run the REAL
state.py/run_hourly.py/run_discovery.py/publish_prices.py code against an
in-memory Supabase stand-in, only patching the true I/O seams).
"""

import re
from pathlib import Path

import pytest

import config
import publish_prices
import run_discovery
import run_hourly
import state

from test_state import FakeNotifier, FakeSupabase, _Result, _ai, _data, _wl_row

SCRIPTS_DIR = Path(state.__file__).parent


# --- a thin extension of FakeSupabase adding kill_switch_state / -------------
# --- kill_switch_abort_log, the two tables this increment's code reads/writes

class KillSwitchFakeSupabase(FakeSupabase):
    def __init__(self, paused=False):
        super().__init__()
        self.paused = paused
        self.abort_log = []   # list of dict rows, insertion order

    def _execute_select(self, verb):
        if verb.table == "kill_switch_state":
            return _Result([{"paused": self.paused}])
        return super()._execute_select(verb)

    def _execute_insert(self, verb):
        # NOTE: the base class's _execute_insert unconditionally appends every
        # insert to self.call_log (it was written when call_log was the only
        # table state.py ever inserted into) -- must NOT delegate to it here,
        # or a kill_switch_abort_log row would silently also land in call_log.
        if verb.table == "kill_switch_abort_log":
            row = dict(verb.payload)
            self.abort_log.append(row)
            return _Result([row])
        return super()._execute_insert(verb)


@pytest.fixture
def sb():
    return KillSwitchFakeSupabase()


@pytest.fixture
def wire_main(monkeypatch, sb):
    monkeypatch.setattr(run_hourly.state, "client", lambda: sb)
    monkeypatch.setattr(run_hourly.notify, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    return sb


@pytest.fixture
def wire_discovery(monkeypatch, sb):
    monkeypatch.setattr(run_discovery.state, "client", lambda: sb)
    monkeypatch.setattr(run_discovery.notify, "get_notifier", lambda: FakeNotifier())
    return sb


def _sequenced_is_paused(*values):
    """Returns a fake is_paused(sb) that yields `values` in order, one per
    call, then repeats the last value forever (so a test only has to script
    the calls it cares about)."""
    calls = {"i": 0}

    def _fn(sb):
        i = min(calls["i"], len(values) - 1)
        calls["i"] += 1
        return values[i]
    _fn.call_count = lambda: calls["i"]
    return _fn


# =============================================================================
# The single most important thing: KillSwitchAbort(BaseException), not
# Exception -- and it must survive a bare `except Exception` guard.
# =============================================================================

def test_kill_switch_abort_subclasses_base_exception_not_exception():
    """increment-plan.md AC2's literal check, made permanent: a future refactor
    changing KillSwitchAbort's base class back to Exception must fail this
    test immediately, not silently reintroduce DEEP-007's exact defect."""
    assert issubclass(state.KillSwitchAbort, BaseException)
    assert not issubclass(state.KillSwitchAbort, Exception)


def test_kill_switch_abort_is_not_caught_by_a_bare_except_exception():
    """The load-bearing property itself, independent of run_hourly.py's
    internals: an `except Exception` guard -- the exact pattern every
    per-ticker/per-group loop in run_hourly.py/run_discovery.py uses -- must
    NOT catch a KillSwitchAbort. If a future edit changes the base class to
    plain Exception, this assertion flips from pass to fail."""
    outcome = None
    try:
        try:
            raise state.KillSwitchAbort("push")
        except Exception:
            outcome = "wrongly-caught-as-a-normal-error"
    except state.KillSwitchAbort:
        outcome = "correctly-propagated-uncaught"
    assert outcome == "correctly-propagated-uncaught"


def test_kill_switch_abort_propagates_through_process_group_uncounted_in_error(
        monkeypatch, wire_main, capsys):
    """AC5/AC7 end to end, against the real run_hourly.py code: a checkpoint-3
    abort mid-`_process_group`'s Phase-3 loop must NOT be caught by that loop's
    own `except Exception` (would miscount it as outcomes['error'], exactly
    the FR35 violation this increment exists to prevent) -- and must NOT
    produce an 'ERROR <ticker>: KillSwitchAbort' print line, which is what a
    wrongly-caught abort would look like."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("MSFT", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    sb.verdict_state["MSFT"] = {"ticker": "MSFT", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy"), "MSFT": _ai("Buy")})
    # False at checkpoint 1, False at checkpoint 2, False at AAPL's checkpoint
    # 3 (pushes), True at MSFT's checkpoint 3 (aborts).
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, False, True))

    run_hourly.main()

    out = capsys.readouterr().out
    assert "ERROR MSFT" not in out
    assert "KillSwitchAbort" not in out.replace(
        "[kill-switch] paused -- aborted at checkpoint=push", "")


# =============================================================================
# AC1 -- is_paused() itself
# =============================================================================

def test_is_paused_returns_the_flag_in_both_states(sb):
    sb.paused = True
    assert state.is_paused(sb) is True
    sb.paused = False
    assert state.is_paused(sb) is False


# =============================================================================
# AC2 -- call-site counts (grep-equivalent, permanent regression guard)
# =============================================================================

@pytest.mark.parametrize("filename,pattern,expected", [
    ("run_hourly.py", r"^\s*if state\.is_paused\(sb\):", 2),
    ("run_discovery.py", r"^\s*if state\.is_paused\(sb\):", 2),
    ("state.py", r"^\s*if is_paused\(sb\):", 2),
    ("publish_prices.py", r"^\s*if state\.is_paused\(sb\):", 1),
])
def test_checkpoint_call_site_counts(filename, pattern, expected):
    text = (SCRIPTS_DIR / filename).read_text()
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    assert len(matches) == expected, (
        f"{filename}: expected exactly {expected} call site(s) matching {pattern!r}, "
        f"found {len(matches)}")


def test_kill_switch_abort_class_declared_exactly_once_as_baseexception():
    text = (SCRIPTS_DIR / "state.py").read_text()
    matches = re.findall(r"^class KillSwitchAbort\(BaseException\):", text, flags=re.MULTILINE)
    assert len(matches) == 1


# =============================================================================
# AC3 -- checkpoint 1 / checkpoint 4: bare, side-effect-free early return
# =============================================================================

def test_checkpoint1_run_hourly_aborts_before_any_named_side_effect(monkeypatch, wire_main):
    """Checkpoint 1 is placed AFTER `sb = state.client()` / `notifier =
    notify.get_notifier()` are constructed (operational-controls.md §13.6.2 --
    the earliest point a pause read is possible), so constructing the
    notifier object itself is expected; what must never happen is any of the
    six named functions actually being invoked."""
    sb = wire_main
    sb.paused = True
    notifier = FakeNotifier()
    monkeypatch.setattr(run_hourly.notify, "get_notifier", lambda: notifier)
    for target, name in [
        (run_hourly.ingest, "get_market_data"),
        (run_hourly.ai_judge, "judge_batch"),
        (run_hourly.state, "write_heartbeat"),
        (run_hourly.state, "write_kill_switch_abort"),
    ]:
        monkeypatch.setattr(target, name,
                             lambda *a, **kw: (_ for _ in ()).throw(AssertionError(f"{name} must not be called")))

    run_hourly.main()   # must not raise

    assert sb.run_heartbeat == {}
    assert sb.abort_log == []
    assert notifier.calls == []


def test_checkpoint1_run_discovery_aborts_before_any_named_side_effect(monkeypatch, wire_discovery):
    sb = wire_discovery
    sb.paused = True
    for target, name in [
        (run_discovery.prefilter, "find_candidates"),
        (run_discovery.ai_judge, "judge_batch"),
        (run_discovery.state, "write_heartbeat"),
        (run_discovery.state, "write_kill_switch_abort"),
    ]:
        monkeypatch.setattr(target, name,
                             lambda *a, **kw: (_ for _ in ()).throw(AssertionError(f"{name} must not be called")))

    run_discovery.main()   # must not raise

    assert sb.run_heartbeat == {}
    assert sb.abort_log == []


def test_checkpoint4_publish_prices_skips_write_and_heartbeat_when_paused(monkeypatch, tmp_path):
    sb = KillSwitchFakeSupabase(paused=True)
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(publish_prices.state, "client", lambda: sb)
    out_path = tmp_path / "prices.json"
    monkeypatch.setattr(publish_prices, "OUT_PATH", str(out_path))
    monkeypatch.setattr(publish_prices.state, "write_heartbeat",
                         lambda *a, **kw: (_ for _ in ()).throw(AssertionError("write_heartbeat must not be called")))

    publish_prices.main()   # must not raise

    assert not out_path.exists()
    assert sb.run_heartbeat == {}
    assert sb.abort_log == []   # checkpoint 4 never writes this table (out of FR35 scope)


# =============================================================================
# AC4 -- checkpoint 2 ("ai_call"): zero prior rows this cycle
# =============================================================================

def test_checkpoint2_run_hourly_ai_call_abort(monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: (_ for _ in ()).throw(AssertionError("judge_batch must not be called")))
    # False at checkpoint 1 (main entry), True at checkpoint 2 (after Phase-1 ingest).
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, True))

    run_hourly.main()

    assert sb.run_heartbeat == {}
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "ai_call"
    assert sb.abort_log[0]["workflow"] == "hourly-watchlist"
    assert sb.abort_log[0]["real_rows_this_cycle"] == 0


def test_checkpoint2_run_discovery_ai_call_abort(monkeypatch, wire_discovery):
    sb = wire_discovery
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: (
                             [{"ticker": "NEWCO", "signals": ["gainer"]}], 1, 0,
                             {"raw": 1, "after_dedup": 1, "passed_quality": 1, "passed_signal": 1}))
    monkeypatch.setattr(run_discovery.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True})
    monkeypatch.setattr(run_discovery.ai_judge, "judge_batch",
                         lambda items, models=None: (_ for _ in ()).throw(AssertionError("judge_batch must not be called")))
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, True))

    run_discovery.main()

    assert sb.run_heartbeat == {}
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "ai_call"
    assert sb.abort_log[0]["workflow"] == "daily-discovery"
    assert sb.abort_log[0]["real_rows_this_cycle"] == 0


# =============================================================================
# AC5/AC7 -- checkpoint 3 ("push") mid-run: untouched state, one abort row,
# real_rows_this_cycle == count of real outcomes already produced this cycle.
# =============================================================================

def test_checkpoint3_push_abort_leaves_second_ticker_exactly_pending(monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("MSFT", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    sb.verdict_state["MSFT"] = {"ticker": "MSFT", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy"), "MSFT": _ai("Buy")})
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, False, True))

    run_hourly.main()

    assert sb.run_heartbeat == {}
    # AAPL got its full real outcome: pushed and advanced.
    assert len(sb.call_log) == 1
    assert sb.call_log[0]["ticker"] == "AAPL"
    assert sb.verdict_state["AAPL"]["current_verdict"] == "Buy"
    # MSFT's crossing is left exactly as pending as before this cycle touched it.
    assert sb.verdict_state["MSFT"] == {"ticker": "MSFT", "current_verdict": "Hold"}
    assert not any(r["ticker"] == "MSFT" for r in sb.call_log)
    # Exactly one causally-tied abort row.
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"
    assert sb.abort_log[0]["workflow"] == "hourly-watchlist"
    assert sb.abort_log[0]["real_rows_this_cycle"] == 1   # AAPL's change-alert, counted before the abort


def test_checkpoint3_push_abort_on_the_first_ticker_of_a_cycle_is_zero_rows(monkeypatch, wire_main):
    """Probe beyond the ACs: distinguishes a checkpoint-3 (push) abort with
    zero prior rows from checkpoint-2's zero-row sub-case (§13.6.3) -- same
    real_rows_this_cycle value, different checkpoint, both legitimate."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})
    # False at checkpoint 1, False at checkpoint 2, True at AAPL's checkpoint 3
    # -- the very first ticker to reach a push this cycle.
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, True))

    run_hourly.main()

    assert sb.call_log == []
    assert sb.verdict_state["AAPL"] == {"ticker": "AAPL", "current_verdict": "Hold"}
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"
    assert sb.abort_log[0]["real_rows_this_cycle"] == 0


def test_checkpoint3_process_candidate_abort_leaves_nothing_logged(monkeypatch, wire_discovery):
    """The discovery-side equivalent of checkpoint 3: process_candidate's own
    push branch, not process_ticker's."""
    sb = wire_discovery
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: (
                             [{"ticker": "NEWCO", "signals": ["gainer"]}], 1, 0,
                             {"raw": 1, "after_dedup": 1, "passed_quality": 1, "passed_signal": 1}))
    monkeypatch.setattr(run_discovery.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True})
    monkeypatch.setattr(run_discovery.ai_judge, "judge_batch",
                         lambda items, models=None: {"NEWCO": _ai("Buy")})
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, True))

    run_discovery.main()

    assert sb.call_log == []
    assert sb.run_heartbeat == {}
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"
    assert sb.abort_log[0]["workflow"] == "daily-discovery"
    assert sb.abort_log[0]["real_rows_this_cycle"] == 0


# =============================================================================
# AC6 -- resume: next cycle retries automatically, zero new code
# =============================================================================

def test_resume_after_checkpoint3_abort_pushes_the_pending_ticker(monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("MSFT", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    sb.verdict_state["MSFT"] = {"ticker": "MSFT", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy"), "MSFT": _ai("Buy")})
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, False, True))
    run_hourly.main()   # AAPL pushed, MSFT aborted-pending (see test above)
    assert sb.verdict_state["MSFT"]["current_verdict"] == "Hold"

    # Second cycle: same fixture data, kill switch now off throughout.
    # TUNABLES_DEGRADED neutralized so this test isolates the resume/push
    # behavior, not the (separately-tested, tunables-only) degraded heartbeat
    # rule -- same convention as test_run_orchestration.py's equivalent tests.
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    monkeypatch.setattr(state, "is_paused", lambda sb: False)
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy"), "MSFT": _ai("Buy")})

    run_hourly.main()

    assert sb.verdict_state["MSFT"]["current_verdict"] == "Buy"
    assert any(r["ticker"] == "MSFT" for r in sb.call_log)
    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "ok"   # a normal, non-aborted completion


# =============================================================================
# Probe: pause observed strictly between checkpoint 2 and checkpoint 3 in the
# same run -- covered by the "first ticker of a cycle" test above (checkpoint
# 2 passes, checkpoint 3 catches it on the very next opportunity). Explicit
# variant: checkpoint 2 passes with items already ingested, flag flips before
# ANY ticker reaches its own checkpoint 3.
# =============================================================================

def test_pause_flips_between_checkpoint2_and_checkpoint3(monkeypatch, wire_main):
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, False, True))

    run_hourly.main()

    assert sb.call_log == []
    assert len(sb.abort_log) == 1
    assert sb.abort_log[0]["checkpoint"] == "push"


# =============================================================================
# Probe: is_paused() itself failing (Supabase unreachable) -- fail-open or
# fail-closed?
# =============================================================================

class _SupabaseUnreachable(Exception):
    pass


def test_is_paused_failure_at_checkpoint1_fails_closed_the_run_never_proceeds(monkeypatch, wire_main):
    """Checkpoint 1 sits outside any try/except in main(). If is_paused()
    itself raises (e.g. a real network error reaching Supabase), that
    exception is NOT swallowed and NOT treated as "not paused" -- it
    propagates uncaught, and the run crashes before touching the watchlist,
    Yahoo, or the AI. This is fail-CLOSED with respect to the irreversible
    action (nothing downstream ever runs), but via a loud crash rather than a
    graceful abort -- which is the correct FR24 posture (never silently
    proceed as if unpaused when the pause state itself can't be determined),
    and unlike a real KillSwitchAbort it is NOT classified as expected-quiet
    (no kill_switch_abort_log row), so NFR2 alerting is not suppressed."""
    sb = wire_main
    monkeypatch.setattr(state, "is_paused",
                         lambda sb: (_ for _ in ()).throw(_SupabaseUnreachable("network down")))
    monkeypatch.setattr(run_hourly.state, "get_watchlist",
                         lambda sb: (_ for _ in ()).throw(AssertionError("must not reach watchlist fetch")))

    with pytest.raises(_SupabaseUnreachable):
        run_hourly.main()

    assert sb.run_heartbeat == {}
    assert sb.abort_log == []   # not misclassified as a deliberate pause


def test_is_paused_failure_at_checkpoint3_is_caught_as_an_ordinary_per_ticker_error(
        monkeypatch, wire_main, capsys):
    """Checkpoint 3 sits INSIDE process_ticker's per-ticker call, which
    run_hourly._process_group's Phase-3 loop wraps in `except Exception`. A
    real (non-KillSwitchAbort) exception from is_paused() there IS caught by
    that pre-existing guard, counted as a normal outcomes['error'], and does
    NOT crash the whole run or the other ticker's processing -- a materially
    different fail mode from checkpoint 1's hard crash above. The run still
    correctly alerts (heartbeat 'partial'), since this is a genuine problem,
    not a deliberate pause."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Hold"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})
    # False at checkpoint 1 and checkpoint 2, then a real error at AAPL's checkpoint 3.
    calls = {"i": 0}

    def _is_paused(sb_arg):
        calls["i"] += 1
        if calls["i"] < 3:
            return False
        raise _SupabaseUnreachable("network down")
    monkeypatch.setattr(state, "is_paused", _is_paused)

    run_hourly.main()   # must NOT raise -- caught by _process_group's except Exception

    out = capsys.readouterr().out
    assert "ERROR AAPL" in out
    assert "_SupabaseUnreachable" in out
    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"
    assert sb.abort_log == []   # never classified as a deliberate pause


# =============================================================================
# REV-116 (Pass 28, docs/review-log.md) -- DEEP-007 residual: the
# tunables-cache write (a real `contents: write` commit path) must never fire
# before checkpoint 1's pause read, in either direction.
#
# Every other test in this suite runs with SKIP_TUNABLES_FETCH=true
# (tests/conftest.py), which empties config._TUNABLES at import time and
# makes write_tunables_cache_if_fetched()'s own `if not _TUNABLES: return`
# guard a silent no-op regardless of call ordering -- exactly why 22 prior
# boundary tests all passed while the defect (write ran unconditionally as
# main()'s first statement, before state.client()/checkpoint 1 even existed)
# was live. This test deliberately bypasses that skip: it populates
# config._TUNABLES/_TUNABLES_CACHE directly (not via the SKIP_TUNABLES_FETCH
# env var, so the module-level skip stays in effect for every other test in
# the suite) and wraps the REAL write_tunables_cache_if_fetched with a
# call-counting spy that still calls through, so the assertion is against the
# function actually doing its real merge/validate/write work, not a stub that
# would pass no matter where the call sits.
# =============================================================================

@pytest.fixture
def real_tunables_write_spy(monkeypatch, tmp_path):
    """Makes config.write_tunables_cache_if_fetched() do real work (real
    merge/validate against a real, temporary cache file) instead of the
    SKIP_TUNABLES_FETCH no-op every other test relies on, and counts calls
    without changing behavior (wraps, does not replace, the real function)."""
    monkeypatch.setattr(config, "_TUNABLES", {"GEMINI_MODEL": "gemini-spy-test-value"})
    monkeypatch.setattr(config, "_TUNABLES_CACHE", {})   # differs from _TUNABLES -> a real write would occur
    monkeypatch.setattr(config, "_CACHE_PATH", tmp_path / "tunables_cache.json")

    real_fn = config.write_tunables_cache_if_fetched
    calls = {"n": 0}

    def _spy():
        calls["n"] += 1
        return real_fn()
    monkeypatch.setattr(config, "write_tunables_cache_if_fetched", _spy)
    calls["path"] = tmp_path / "tunables_cache.json"
    return calls


def test_rev116_tunables_cache_write_not_reached_while_paused(monkeypatch, wire_main, real_tunables_write_spy):
    """The core REV-116 regression: a paused run must reach zero calls to the
    real tunables-cache write, not just an empty _TUNABLES-masked no-op.
    Fails on the pre-fix ordering (git show d875078:scripts/run_hourly.py),
    where the write was main()'s unconditional first statement, reachable
    before state.client()/checkpoint 1 existed at all."""
    sb = wire_main
    sb.paused = True

    run_hourly.main()

    assert real_tunables_write_spy["n"] == 0
    assert not real_tunables_write_spy["path"].exists()


def test_rev116_tunables_cache_still_refreshes_on_closed_market_when_not_paused(
        monkeypatch, wire_main, real_tunables_write_spy):
    """The design property (docs/design/tunables-fallback.md) this fix must
    NOT regress: 'the cache refreshes on every dispatch regardless of whether
    the market check inside main() goes on to skip work.' Market closed, no
    FORCE_RUN, kill switch not paused -- checkpoint 1's own gate must exit
    early (no watchlist fetch, no AI call), but the real tunables write must
    still have fired exactly once before that early exit, exactly as it did
    pre-fix, and must have actually written the merged file."""
    sb = wire_main
    sb.paused = False
    monkeypatch.setattr(config, "is_market_open", lambda now: False)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(run_hourly.state, "get_watchlist",
                         lambda sb: (_ for _ in ()).throw(AssertionError(
                             "must not reach the watchlist fetch on a closed, non-forced market")))

    run_hourly.main()

    assert real_tunables_write_spy["n"] == 1
    assert real_tunables_write_spy["path"].exists()
    import json
    assert json.loads(real_tunables_write_spy["path"].read_text())["GEMINI_MODEL"] == "gemini-spy-test-value"


# =============================================================================
# Probe: two aborts in one run -- can it ever happen?
# =============================================================================

def test_only_one_abort_row_ever_written_even_with_two_open_market_groups(monkeypatch, wire_main):
    """main()'s try/except wraps the ENTIRE `for s in run_sessions` loop, not
    each group individually -- the first KillSwitchAbort to propagate breaks
    out of the loop for good and returns. A second, already-open market group
    must never get a chance to also abort in the same run."""
    sb = wire_main
    monkeypatch.setattr(config, "is_nse_open", lambda now: True)   # both groups open
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("INFY", "NSE")]
    judge_calls = []
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: (judge_calls.append(items) or {}))
    # False at checkpoint 1, True at the FIRST group's checkpoint 2 (US/TSX,
    # processed before NSE per _sessions()' ordering) -- aborts immediately,
    # NSE's own _process_group must never even be entered.
    monkeypatch.setattr(state, "is_paused", _sequenced_is_paused(False, True))

    run_hourly.main()

    assert judge_calls == []                 # neither group's AI call ever fired
    assert len(sb.abort_log) == 1             # exactly one row, not two
    assert sb.call_log == []                  # NSE's ticker never got so much as a skip/log
