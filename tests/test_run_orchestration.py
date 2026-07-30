"""Regression coverage for the orchestrators' OWN decision logic (REV-055,
docs/review-log.md), as opposed to the pure modules underneath them (already
covered by test_state.py / test_config.py / test_ai_judge.py etc).

Before this file, `test_import_smoke.py:34-42` was the only coverage touching
`run_hourly.py` / `run_discovery.py`, and it asserted only import-cleanliness.
Untested, each traced to a specific past production defect:

  - run_hourly._sessions()                       -- which market group(s) run (issue #7)
  - run_hourly.main() FORCE_RUN-all-closed branch -- manual run outside all hours
  - run_hourly.main() both-sessions-open warning  -- sessions overlap (should never happen)
  - run_hourly.main() partial-vs-ok heartbeat     -- issue #2
  - run_discovery.main() quiet-day-vs-screener-failure heartbeat -- issue #8

Reuses the FakeSupabase/FakeNotifier in-memory doubles and the _wl_row/_data/_ai
builders from test_state.py (same convention: run the REAL state.py /
run_hourly.py / run_discovery.py code against an in-memory Supabase stand-in,
only patching the true network seams: yfinance via ingest.get_market_data,
Gemini via ai_judge.judge_batch, the Yahoo screener via prefilter.find_candidates).
"""

import datetime as dt

import pytest

import config
import run_hourly
import run_discovery

from test_state import FakeSupabase, FakeNotifier, _wl_row, _data, _ai


# --- run_hourly._sessions() (run_hourly.py:34-49) ------------------------------

def test_sessions_us_tsx_open_nse_closed_uses_default_models(monkeypatch):
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    sessions = run_hourly._sessions(dt.datetime(2026, 7, 13, 10, 0), dt.datetime(2026, 7, 13, 20, 0))
    by_name = {s["name"]: s for s in sessions}

    assert by_name["US/TSX"]["open"] is True
    assert by_name["US/TSX"]["markets"] == {"US", "TSX"}
    assert by_name["US/TSX"]["models"] is None   # falls back to config.GEMINI_MODEL/_BACKUP
    assert by_name["NSE"]["open"] is False


def test_sessions_nse_open_draws_its_own_model_pair(monkeypatch):
    monkeypatch.setattr(config, "is_market_open", lambda now: False)
    monkeypatch.setattr(config, "is_nse_open", lambda now: True)
    monkeypatch.setattr(config, "nse_models", lambda: ["nse-primary", "nse-backup"])
    sessions = run_hourly._sessions(dt.datetime(2026, 7, 13, 3, 0), dt.datetime(2026, 7, 13, 9, 20))
    by_name = {s["name"]: s for s in sessions}

    assert by_name["NSE"]["open"] is True
    assert by_name["NSE"]["markets"] == {"NSE"}
    assert by_name["NSE"]["models"] == ["nse-primary", "nse-backup"]   # separate quota bucket
    assert by_name["US/TSX"]["open"] is False


def test_sessions_both_closed():
    # Genuinely closed hours on both sides (no monkeypatch: real config gates,
    # a Saturday, so both sessions are shut regardless of wall-clock time).
    saturday_et = dt.datetime(2026, 7, 11, 12, 0, tzinfo=config.MARKET_TZ)
    saturday_ist = dt.datetime(2026, 7, 11, 12, 0, tzinfo=config.NSE_MARKET_TZ)
    sessions = run_hourly._sessions(saturday_et, saturday_ist)
    assert all(s["open"] is False for s in sessions)
    assert {s["name"] for s in sessions} == {"US/TSX", "NSE"}


# --- run_hourly.main() end-to-end decision branches -----------------------------

@pytest.fixture
def sb():
    return FakeSupabase()


@pytest.fixture
def wire_main(monkeypatch, sb):
    """Patch the two true I/O seams run_hourly.main() goes through (the Supabase
    client and the notifier), mirroring the FakeSupabase/FakeNotifier doubles
    test_state.py already exercises state.py's real read/write functions
    against. Everything else in main()/_process_group runs for real."""
    monkeypatch.setattr(run_hourly.state, "client", lambda: sb)
    monkeypatch.setattr(run_hourly.notify, "get_notifier", lambda: FakeNotifier())
    return sb


def test_all_markets_closed_without_force_run_is_a_noop(monkeypatch, wire_main, capsys):
    monkeypatch.setattr(config, "is_market_open", lambda now: False)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)

    run_hourly.main()

    out = capsys.readouterr().out
    assert "All markets closed - no-op, exit." in out
    # No heartbeat write on a genuine no-op: state.client() and checkpoint 1's
    # is_paused() ARE reached (REV-116 fix, docs/review-log.md Pass 28 -- moved
    # to the top of main(), ahead of the tunables-cache write and the market
    # gate) but state.write_heartbeat() is not -- main() returns at the
    # closed-market check below that, before any heartbeat write.
    assert wire_main.run_heartbeat == {}


def test_force_run_with_everything_closed_runs_every_group(monkeypatch, wire_main, capsys):
    """run_hourly.py:130-134 (issue #7 / manual test-or-backfill path): with
    every session closed and FORCE_RUN set, BOTH groups still run against last
    close, not just skipped."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("TATASTEEL", "NSE")]
    monkeypatch.setattr(config, "is_market_open", lambda now: False)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", True)
    # Every ticker fails ingest, deterministically, so we don't need a real
    # yfinance/Gemini round-trip to prove both groups were actually processed.
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {"has_price": False, "notes": ["no data"], "rate_limited": False})

    run_hourly.main()

    out = capsys.readouterr().out
    assert "FORCE_RUN: all markets closed, running every group against last close" in out
    assert "[US/TSX] 1 tickers" in out    # both groups ran, not just the (nonexistent) open one
    assert "[NSE] 1 tickers" in out
    assert len(sb.call_log) == 2          # skip-with-log fired for both tickers


def test_both_sessions_open_prints_warning_and_still_processes_both(monkeypatch, wire_main, capsys):
    """run_hourly.py:113-117: sessions are designed never to overlap; if they
    ever do, this must be loud (not silently dropped) and both groups must
    still run independently."""
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: True)
    monkeypatch.setattr(config, "FORCE_RUN", False)

    run_hourly.main()

    out = capsys.readouterr().out
    assert "WARNING: US/TSX and NSE both report open" in out
    assert "open=US/TSX, NSE" in out
    assert "[US/TSX] 0 tickers" in out
    assert "[NSE] 0 tickers" in out


def test_no_warning_when_only_one_session_open(monkeypatch, wire_main, capsys):
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)

    run_hourly.main()

    out = capsys.readouterr().out
    assert "WARNING" not in out


# --- run_hourly.main() partial-vs-ok heartbeat (run_hourly.py:154-156) ---------

def test_heartbeat_is_partial_when_a_ticker_is_skipped(monkeypatch, wire_main):
    """issue #2: a run with any skip must not report a clean 'ok'."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {"has_price": False, "notes": ["rate limited"], "rate_limited": True})

    run_hourly.main()

    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"


def test_heartbeat_is_ok_when_every_ticker_processes_cleanly(monkeypatch, wire_main):
    """INC-6/AC14 (REV-045) note: `status` now also ORs in
    config.TUNABLES_DEGRADED (tests/conftest.py's SKIP_TUNABLES_FETCH=true
    default makes every curated key resolve from tier 2, so it's True for the
    whole suite unless neutralized). This test's own purpose is the
    TICKER-cleanliness half of the "ok" rule (issue #2) -- neutralize the
    tunables-degraded half here so a real ticker-level regression can't hide
    behind it. The degraded half is asserted on its own in
    test_tunables.py::test_ac14_run_discovery_heartbeat_is_partial_when_degraded...
    and this file's sibling test_heartbeat_is_partial_when_tunables_are_degraded
    below, for run_hourly specifically."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})

    run_hourly.main()

    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "ok"
    assert len(sb.call_log) == 1
    assert sb.call_log[0]["alerted"] is False   # cold start, FR8: no fabricated alert


def test_heartbeat_is_partial_when_tunables_are_degraded(monkeypatch, wire_main):
    """INC-6/AC14 (REV-045): a tier-2 (cache) resolution must be
    monitor-visible via the heartbeat even when every ticker processes
    cleanly -- the counterpart to the test above."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", True)
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})

    run_hourly.main()

    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"


def test_heartbeat_is_partial_when_a_ticker_errors_mid_run(monkeypatch, wire_main):
    """The 'error' half of degraded = outcomes['skip'] + outcomes['error']."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)

    def _boom(ticker):
        raise RuntimeError("simulated ingest crash")

    monkeypatch.setattr(run_hourly.ingest, "get_market_data", _boom)

    run_hourly.main()

    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"
    assert sb.call_log == []   # the crash happened before any log write


# --- run_discovery.main() quiet-day-vs-screener-failure (run_discovery.py:55-66) -

@pytest.fixture
def wire_discovery(monkeypatch, sb):
    monkeypatch.setattr(run_discovery.state, "client", lambda: sb)
    monkeypatch.setattr(run_discovery.notify, "get_notifier", lambda: FakeNotifier())
    return sb


_EMPTY_FUNNEL = {"raw": 10, "after_dedup": 10, "passed_quality": 0, "passed_signal": 0}


def test_quiet_day_all_screens_ok_reports_ok(monkeypatch, wire_discovery, capsys):
    """issue #8: zero candidates with every screen having run cleanly is a
    genuine quiet day, not a failure.

    BUG-003 fix note: the early-return branch now also ORs in
    config.TUNABLES_DEGRADED (True by default under conftest.py's
    SKIP_TUNABLES_FETCH=true) -- neutralize it here so this test isolates the
    screen-cleanliness half of the "ok" rule, same pattern as
    test_heartbeat_is_ok_when_every_ticker_processes_cleanly above. The
    degraded half of this branch is covered by
    test_tunables.py::test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded."""
    sb = wire_discovery
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: ([], 5, 0, _EMPTY_FUNNEL))
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)

    run_discovery.main()

    out = capsys.readouterr().out
    assert "Done [ok]. No candidates today (all screens ran, nothing passed gates)." in out
    assert sb.run_heartbeat["daily-discovery"]["status"] == "ok"


def test_zero_candidates_with_screen_errors_reports_partial_not_ok(monkeypatch, wire_discovery, capsys):
    """issue #8's actual regression: a broken screener that also yields zero
    candidates must NOT masquerade as a clean quiet day."""
    sb = wire_discovery
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: ([], 5, 2, _EMPTY_FUNNEL))

    run_discovery.main()

    out = capsys.readouterr().out
    assert "screens errored — treat as screener failure, NOT a quiet day." in out
    assert sb.run_heartbeat["daily-discovery"]["status"] == "partial"


def test_zero_candidates_with_all_screens_errored_is_still_partial(monkeypatch, wire_discovery):
    """Edge case: every screen errored (not just some) — still 'partial', never 'ok'."""
    sb = wire_discovery
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: ([], 4, 4, _EMPTY_FUNNEL))

    run_discovery.main()

    assert sb.run_heartbeat["daily-discovery"]["status"] == "partial"


# --- INC-8 / DEEP-001 / NFR2 / Decision #31: heartbeat must reflect an
# all-AI-failure run as degraded, not 'ok' -----------------------------------
# increment-plan.md AC1: "A qa test that drives every ticker in a batch to
# parse_status='failed' ... asserts run_heartbeat.status == 'partial' -- the
# exact case DEEP-001 found reading 'ok'. Same assertion for a mixed batch
# (some no-read, some quiet)."

def test_heartbeat_is_partial_when_every_ticker_ai_call_fails(monkeypatch, wire_main):
    """DEEP-001's exact reproduction: every requested ticker's AI call fails
    (parse_status='failed', e.g. an expired key / provider outage / bad model
    string) -- pre-fix, none of these hit 'skip' or 'error', so the run wrote
    status='ok' despite zero verdicts being produced. Must be 'partial'."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("MSFT", "US")]
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {
                             "AAPL": _ai("Hold", parse_status="failed"),
                             "MSFT": _ai("Hold", parse_status="api_error"),
                         })

    run_hourly.main()

    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"
    # And it's for the right reason: every row is a no-read, not a skip/error.
    assert all(row["data_snapshot"]["parse_status"] in ("failed", "api_error")
               for row in sb.call_log)


def test_heartbeat_is_partial_for_mixed_no_read_and_quiet_batch(monkeypatch, wire_main):
    """A batch where some tickers no-read and others are genuinely quiet
    (verdict unchanged) must still report 'partial' overall -- the no-read
    count alone must drive it, not just an all-failed batch."""
    sb = wire_main
    sb.watchlist = [_wl_row("AAPL", "US"), _wl_row("MSFT", "US")]
    monkeypatch.setattr(config, "is_market_open", lambda now: True)
    monkeypatch.setattr(config, "is_nse_open", lambda now: False)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    # AAPL already has an established Buy verdict (no change -> quiet);
    # MSFT's AI call fails this cycle (no-read).
    sb.verdict_state["AAPL"] = {"ticker": "AAPL", "current_verdict": "Buy"}
    monkeypatch.setattr(run_hourly.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True, "is_new": False})
    monkeypatch.setattr(run_hourly.ai_judge, "judge_batch",
                         lambda items, models=None: {
                             "AAPL": _ai("Buy"),
                             "MSFT": _ai("Hold", parse_status="failed"),
                         })

    run_hourly.main()

    assert sb.run_heartbeat["hourly-watchlist"]["status"] == "partial"


def test_discovery_heartbeat_is_partial_when_every_candidate_ai_call_fails(monkeypatch, wire_discovery):
    """DEEP-001's discovery-side equivalent: every shortlisted candidate's AI
    call fails -- must not report 'ok' just because screens themselves ran
    cleanly and candidates were found."""
    sb = wire_discovery
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: (
                             [{"ticker": "NEWCO", "signals": ["gainer"]}], 5, 0, _EMPTY_FUNNEL))
    monkeypatch.setattr(run_discovery.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True})
    monkeypatch.setattr(run_discovery.ai_judge, "judge_batch",
                         lambda items, models=None: {"NEWCO": _ai("Hold", parse_status="failed")})

    run_discovery.main()

    assert sb.run_heartbeat["daily-discovery"]["status"] == "partial"
