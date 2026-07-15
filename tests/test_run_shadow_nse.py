"""run_shadow_nse.py -- the NSE shadow wallet pilot (FR32-FR39, NFR6, INC-1).

Mirrors tests/test_shadow.py's coverage of run_shadow.py, retargeted to the
NSE track, plus the NSE-specific isolation/gating requirements that didn't
exist on the US/CA track (FR32 market scoping, FR34 snapshot reuse, FR35
storage isolation, FR37 mutual cross-track isolation incl. the SystemExit
exit-0 guarantee, FR39 NSE market-hours gating). No real network/API/DB call
is ever made in this suite.
"""

import inspect

import pytest

import config
import run_shadow
import run_shadow_nse
import shadow


# --- FR32: existence & purpose -- NSE-only, never US/TSX ---------------------

def test_nse_markets_is_nse_only():
    assert run_shadow_nse.NSE_MARKETS == {"NSE"}
    assert "US" not in run_shadow_nse.NSE_MARKETS
    assert "TSX" not in run_shadow_nse.NSE_MARKETS


def test_run_shadow_nse_source_never_references_us_ca_shadow_table():
    """FR35/FR37: this module must never write to call_log_shadow (US/CA) or
    plain call_log as a write target -- only read call_log (production
    snapshot reuse, FR34) and read/write call_log_shadow_nse."""
    src = inspect.getsource(run_shadow_nse)
    assert 'sb.table("call_log_shadow_nse")' in src
    assert 'sb.table("call_log_shadow")' not in src   # never touches the US/CA table
    # The only call_log reference must be a read (select), never an insert target.
    assert 'sb.table("call_log").insert' not in src


# --- FR36: never alerts -------------------------------------------------------

def test_run_shadow_nse_never_imports_or_calls_notify():
    src = inspect.getsource(run_shadow_nse)
    assert "import notify" not in src
    assert "notify." not in src


def test_shadow_module_never_imports_notify():
    src = inspect.getsource(shadow)
    assert "import notify" not in src
    assert "notify." not in src


# --- shadow.judge_batch_shadow(items) helper reused for the NSE items --------

def _shadow_item(ticker="TCS", state="flat", entry_price=None, entry_date=None):
    return {
        "data": {
            "ticker": ticker, "market": "NSE", "price": 3500.0,
            "pct_change_1d": 1.0, "pct_change_5d": 2.0, "pct_change_20d": 3.0,
            "volume_vs_avg": 1.1,
            "fundamentals": {"currency": "INR"}, "headlines": [],
            "session_live": False, "volume_pro_rated": False,
        },
        "shadow_pos": {"state": state, "entry_price": entry_price, "entry_date": entry_date},
    }


def test_judge_batch_shadow_accepts_explicit_nse_models(mock_gemini):
    import json
    from conftest import FakeGeminiResponse
    verdict_json = json.dumps([{"ticker": "TCS", "verdict": "Buy",
                                 "confidence": "high", "rationale": "NSE call"}])
    client = mock_gemini([FakeGeminiResponse(verdict_json)])

    result = shadow.judge_batch_shadow([_shadow_item("TCS")], models=["nse-model-a", "nse-model-b"])

    assert result["TCS"]["verdict"] == "Buy"
    assert client.models.calls == ["nse-model-a"]   # explicit NSE model order used, not the US/CA default


def test_judge_batch_shadow_default_models_none_preserves_us_ca_behavior(mock_gemini, monkeypatch):
    """Non-negotiable: the new `models` param's default (None) must not change
    today's US/CA caller behavior -- it must resolve via ai_judge._models_to_try(None)
    exactly as before, i.e. config.GEMINI_MODEL / _BACKUP."""
    import ai_judge
    monkeypatch.setattr(config, "GEMINI_MODEL", "watchlist-primary")
    monkeypatch.setattr(config, "GEMINI_MODEL_BACKUP", "")
    import json
    verdict_json = json.dumps([{"ticker": "AAPL", "verdict": "Hold",
                                 "confidence": "low", "rationale": "us/ca call"}])
    from conftest import FakeGeminiResponse
    client = mock_gemini([FakeGeminiResponse(verdict_json)])

    result = shadow.judge_batch_shadow([_shadow_item("AAPL")])   # models=None, the default

    assert result["AAPL"]["verdict"] == "Hold"
    assert client.models.calls == ["watchlist-primary"]


# --- FR33: wallet-walk -- self-derived from call_log_shadow_nse ONLY ---------

class FakeShadowNseQuery:
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


class FakeShadowNseSupabase:
    """Table-keyed in-memory double. Tables NOT explicitly provided default to
    a poison value (a sentinel list) so a test can assert the code under test
    never read from a table it shouldn't."""

    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        if name not in self._tables:
            raise AssertionError(f"unexpected read/write to table {name!r} -- FR33/FR35 isolation violated")
        return FakeShadowNseQuery(self._tables[name])


def _nse_row(ticker, verdict, timestamp, price=None):
    return {"ticker": ticker, "verdict": verdict, "timestamp": timestamp,
            "data_snapshot": {"price": price} if price is not None else {}}


def test_nse_wallet_walk_buy_flips_flat_to_holding():
    sb = FakeShadowNseSupabase({"call_log_shadow_nse": [
        _nse_row("TCS", "Buy", "2026-07-10T09:00:00Z", price=3500.0),
    ]})
    positions = run_shadow_nse._derive_shadow_positions(sb, ["TCS"])

    assert positions["TCS"]["state"] == "holding"
    assert positions["TCS"]["entry_price"] == 3500.0
    assert positions["TCS"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_nse_wallet_walk_sell_flips_holding_to_flat():
    sb = FakeShadowNseSupabase({"call_log_shadow_nse": [
        _nse_row("TCS", "Buy", "2026-07-10T09:00:00Z", price=3500.0),
        _nse_row("TCS", "Sell", "2026-07-11T09:00:00Z", price=3600.0),
    ]})
    positions = run_shadow_nse._derive_shadow_positions(sb, ["TCS"])

    assert positions["TCS"]["state"] == "flat"
    assert positions["TCS"]["entry_price"] is None
    assert positions["TCS"]["entry_date"] is None


def test_nse_wallet_walk_hold_is_a_no_op():
    sb = FakeShadowNseSupabase({"call_log_shadow_nse": [
        _nse_row("TCS", "Buy", "2026-07-10T09:00:00Z", price=3500.0),
        _nse_row("TCS", "Hold", "2026-07-11T09:00:00Z", price=3550.0),
    ]})
    positions = run_shadow_nse._derive_shadow_positions(sb, ["TCS"])

    assert positions["TCS"]["state"] == "holding"
    assert positions["TCS"]["entry_price"] == 3500.0
    assert positions["TCS"]["entry_date"] == "2026-07-10T09:00:00Z"


def test_nse_wallet_walk_empty_history_is_flat():
    sb = FakeShadowNseSupabase({"call_log_shadow_nse": []})
    positions = run_shadow_nse._derive_shadow_positions(sb, ["TCS"])

    assert positions["TCS"] == {"state": "flat", "entry_price": None, "entry_date": None}


def test_nse_wallet_walk_reads_only_call_log_shadow_nse_never_call_log_or_call_log_shadow():
    """FR33 (HARD-adjacent): the double raises AssertionError on any read from
    a table other than call_log_shadow_nse -- if the walk ever touched call_log
    or call_log_shadow, this test would fail with that AssertionError."""
    sb = FakeShadowNseSupabase({"call_log_shadow_nse": [
        _nse_row("TCS", "Buy", "2026-07-10T09:00:00Z", price=3500.0),
    ]})
    positions = run_shadow_nse._derive_shadow_positions(sb, ["TCS"])
    assert positions["TCS"]["state"] == "holding"


def test_nse_wallet_walk_covers_only_requested_tickers_independently():
    sb = FakeShadowNseSupabase({"call_log_shadow_nse": [
        _nse_row("TCS", "Buy", "2026-07-10T09:00:00Z", price=3500.0),
        _nse_row("INFY", "Sell", "2026-07-10T09:00:00Z", price=1500.0),   # Sell-while-flat: no-op
    ]})
    positions = run_shadow_nse._derive_shadow_positions(sb, ["TCS", "INFY"])

    assert positions["TCS"]["state"] == "holding"
    assert positions["INFY"]["state"] == "flat"


# --- FR34: same-cycle production snapshot reuse -------------------------------

class FakeCallLogQuery(FakeShadowNseQuery):
    pass


class FakeCallLogSupabase:
    """Records the table name and filter args used, so tests can assert the
    read targets `call_log` with `label='watchlist'` (FR34)."""

    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return self

    def select(self, *a, **kw):
        self.calls.append(("select", a, kw))
        return self

    def eq(self, *a, **kw):
        self.calls.append(("eq", a, kw))
        return self

    def in_(self, *a, **kw):
        self.calls.append(("in_", a, kw))
        return self

    def gte(self, *a, **kw):
        self.calls.append(("gte", a, kw))
        return self

    def order(self, *a, **kw):
        self.calls.append(("order", a, kw))
        return self

    def execute(self):
        class R:
            data = self._rows
        return R()


def test_latest_production_snapshots_reads_call_log_label_watchlist_for_nse_tickers():
    sb = FakeCallLogSupabase([
        {"ticker": "TCS", "timestamp": "2026-07-14T10:00:00Z", "data_snapshot": {"price": 3500.0}},
    ])
    result = run_shadow_nse._latest_production_snapshots(sb, ["TCS"], "2026-07-14T09:40:00Z")

    assert result["TCS"]["data_snapshot"]["price"] == 3500.0
    assert ("table", "call_log") in sb.calls
    assert ("eq", ("label", "watchlist"), {}) in sb.calls
    assert ("in_", ("ticker", ["TCS"]), {}) in sb.calls


def test_latest_production_snapshots_keeps_only_latest_row_per_ticker():
    sb = FakeCallLogSupabase([
        # newest-first, as the real ordered query returns
        {"ticker": "TCS", "timestamp": "2026-07-14T10:05:00Z", "data_snapshot": {"price": 3510.0}},
        {"ticker": "TCS", "timestamp": "2026-07-14T09:45:00Z", "data_snapshot": {"price": 3500.0}},
    ])
    result = run_shadow_nse._latest_production_snapshots(sb, ["TCS"], "2026-07-14T09:40:00Z")
    assert result["TCS"]["data_snapshot"]["price"] == 3510.0   # first-seen (newest) wins


def test_shadow_nse_snapshot_lookback_default_stays_under_nse_dispatch_cadence():
    """FR34: the lookback window MUST stay under the 30-min NSE dispatch
    cadence so it can never pick up a prior cycle's snapshot."""
    assert config.SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN < 30


# --- FR35: isolated storage (structural mirror check vs the US/CA migration) -

def test_nse_sql_migration_mirrors_us_ca_structurally_and_has_rls_no_grant():
    import pathlib
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    us_ca_sql = (repo_root / "sql" / "shadow_call_log_migration.sql").read_text()
    nse_sql = (repo_root / "sql" / "shadow_nse_call_log_migration.sql").read_text()

    assert "call_log_shadow_nse" in nse_sql
    assert "enable row level security" in nse_sql.lower()
    # No permissive policy, no actual GRANT statement (SQL code, not comment
    # prose) to anon/authenticated in EITHER migration.
    def _sql_statements_only(sql):
        """Strip `--` line comments so a comment merely *mentioning* the word
        'grant' (documenting the absence of one) doesn't false-positive."""
        return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())

    for sql, name in ((us_ca_sql, "US/CA"), (nse_sql, "NSE")):
        code = _sql_statements_only(sql).lower()
        assert "create policy" not in code, f"{name} migration must not create a policy"
        assert "grant " not in code, f"{name} migration must not grant anon/authenticated access"

    # Structural mirror: same column set (order-independent), same shadow-only
    # columns, same two-index shape.
    def _columns(sql):
        import re
        cols = re.findall(r"^\s*(\w+)\s+(?:uuid|text|timestamptz|boolean|jsonb)\b", sql, re.MULTILINE)
        return set(cols)

    assert _columns(nse_sql) == _columns(us_ca_sql)
    assert "prompt_variant" in nse_sql and "shadow_position_state" in nse_sql
    assert nse_sql.lower().count("create index") == us_ca_sql.lower().count("create index") == 2


# --- FR37: exception safety -- main() always exits 0, incl. SystemExit -------

def test_run_shadow_nse_main_swallows_plain_exception_and_returns(monkeypatch):
    def _boom():
        raise RuntimeError("simulated cycle failure")
    monkeypatch.setattr(run_shadow_nse, "_run_cycle", _boom)

    run_shadow_nse.main()   # must not raise


def test_run_shadow_nse_main_swallows_systemexit_and_returns(monkeypatch):
    """The specific bug dev found and fixed: config.require_secrets() raises
    SystemExit (a BaseException, not Exception), so `except Exception` alone
    does NOT catch it. run_shadow_nse.py widened the catch to
    (Exception, SystemExit) -- this test proves that fix actually works."""
    def _boom():
        raise SystemExit("Missing required environment secrets: GEMINI_API_KEY")
    monkeypatch.setattr(run_shadow_nse, "_run_cycle", _boom)

    run_shadow_nse.main()   # must NOT propagate SystemExit -- this is the regression test


def test_run_shadow_main_us_ca_track_now_swallows_systemexit_matching_nse(monkeypatch):
    """REV-018 fix verification: run_shadow.py's main() previously caught only
    `except Exception`, which does NOT catch SystemExit (a BaseException). A
    missing-secrets SystemExit from config.require_secrets() during
    _run_cycle() therefore propagated out of main() uncaught, breaking the
    "main() always exits 0" isolation guarantee FR29/NFR5 rely on. dev widened
    the catch to (Exception, SystemExit), matching run_shadow_nse.py's
    existing pattern (see test_run_shadow_nse_main_swallows_systemexit_and_returns
    above) -- this test proves the US/CA track fix actually works."""
    def _boom():
        raise SystemExit("Missing required environment secrets: GEMINI_API_KEY")
    monkeypatch.setattr(run_shadow, "_run_cycle", _boom)

    run_shadow.main()   # must NOT propagate SystemExit -- the gap is now closed


# --- FR37: mutual isolation -- independent kill switches (see also test_config.py)

def test_nse_kill_switch_independent_of_us_ca_kill_switch(monkeypatch):
    monkeypatch.setattr(config, "SHADOW_NSE_ENABLED", False)
    monkeypatch.setattr(config, "SHADOW_ENABLED", True)
    assert config.SHADOW_NSE_ENABLED is False
    assert config.SHADOW_ENABLED is True   # untouched by flipping the NSE switch


# --- FR37: workflow-level isolation belts -------------------------------------
# PyYAML is not a project dependency (requirements.txt is dev's file, not
# QA's to add to) -- these tests use `pytest.importorskip` so the suite skips
# them cleanly (rather than erroring) in an environment without it, instead of
# introducing a new production/test dependency unilaterally. Install `pyyaml`
# to actually exercise this coverage locally: `pip install pyyaml`.

def _workflow_steps():
    yaml = pytest.importorskip("yaml")
    import pathlib
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    wf = yaml.safe_load((repo_root / ".github" / "workflows" / "hourly-watchlist.yml").read_text())
    return wf["jobs"]["watchlist"]["steps"]


def test_workflow_parses_as_valid_yaml():
    steps = _workflow_steps()
    assert len(steps) >= 3


def test_both_shadow_steps_have_continue_on_error_and_timeout_minutes():
    steps = _workflow_steps()
    shadow_steps = [s for s in steps if "shadow" in s.get("name", "").lower()]
    assert len(shadow_steps) == 2, "expected exactly the US/CA and NSE shadow steps"
    for s in shadow_steps:
        assert s.get("continue-on-error") is True, f"{s['name']} missing continue-on-error"
        assert isinstance(s.get("timeout-minutes"), int) and s["timeout-minutes"] > 0, \
            f"{s['name']} missing a positive timeout-minutes"


def test_nse_shadow_step_runs_after_production_and_us_ca_shadow_steps():
    steps = _workflow_steps()
    names = [s.get("name", "") for s in steps]

    def _idx(substr):
        for i, n in enumerate(names):
            if substr.lower() in n.lower():
                return i
        raise AssertionError(f"no step found containing {substr!r} in {names}")

    prod_i = _idx("hourly watchlist check")
    us_ca_i = _idx("US/CA pilot")
    nse_i = _idx("NSE pilot")
    assert prod_i < us_ca_i < nse_i


def test_nse_shadow_step_passes_no_ntfy_or_detail_page_vars():
    steps = _workflow_steps()
    nse_step = next(s for s in steps if "NSE pilot" in s.get("name", ""))
    env = nse_step.get("env", {})
    for forbidden in ("NTFY_TOPIC", "NSE_NTFY_TOPIC", "DETAIL_PAGE_BASE"):
        assert forbidden not in env, f"NSE shadow step must not pass {forbidden} (FR36)"


def test_nse_shadow_step_gated_by_its_own_kill_switch_expression():
    steps = _workflow_steps()
    nse_step = next(s for s in steps if "NSE pilot" in s.get("name", ""))
    assert nse_step.get("if") == "${{ vars.SHADOW_NSE_ENABLED != 'false' }}"


def test_us_ca_shadow_step_gated_by_its_own_independent_kill_switch_expression():
    steps = _workflow_steps()
    us_ca_step = next(s for s in steps if "US/CA pilot" in s.get("name", ""))
    assert us_ca_step.get("if") == "${{ vars.SHADOW_ENABLED != 'false' }}"


# --- FR39: NSE market-hours gating (kill-switch -> market-gate order) --------

def test_run_cycle_is_a_clean_noop_when_kill_switch_off(monkeypatch, capsys):
    monkeypatch.setattr(config, "SHADOW_NSE_ENABLED", False)
    run_shadow_nse._run_cycle()   # must return cleanly, no exception
    out = capsys.readouterr().out
    assert "disabled" in out.lower()


def test_run_cycle_is_a_clean_noop_when_market_closed_and_not_forced(monkeypatch, capsys):
    import datetime as dt
    monkeypatch.setattr(config, "SHADOW_NSE_ENABLED", True)
    monkeypatch.setattr(config, "FORCE_RUN", False)
    monkeypatch.setattr(config, "is_nse_open", lambda *_a, **_kw: False)

    run_shadow_nse._run_cycle()   # must return cleanly before ever calling require_secrets/DB
    out = capsys.readouterr().out
    assert "closed" in out.lower() or "no-op" in out.lower()


def test_kill_switch_checked_before_market_gate_order_matches_production():
    """FR39: the kill-switch check must precede the market-gate check (same
    order as production's NSE group and as run_shadow.py's US/CA gate) -- a
    disabled kill switch short-circuits before ever evaluating market hours."""
    import inspect as _inspect
    src = _inspect.getsource(run_shadow_nse._run_cycle)
    kill_idx = src.index("SHADOW_NSE_ENABLED")
    gate_idx = src.index("is_nse_open")
    assert kill_idx < gate_idx
