"""eval_shadow.py — the shared wallet-sim evaluation harness CLI (design.md
§17, FR31).

Covers:
  - build_report/render_report correctness against synthetic shadow +
    production rows (verdict counts, round-trip P&L, win rate, per-ticker
    breakdown, open-position marking).
  - Determinism: THE acceptance criterion for FR31 (design §17.3) — two
    build_report() calls over identical input produce byte-identical dicts.
  - Read-only guarantee (HARD, design §17.3): no insert/update/upsert/delete
    calls anywhere in eval_shadow.py or wallet_sim.py, as an automated
    regression guard (not just a manual grep).
  - CLI parsing: --track required/restricted, --since/--until defaulting and
    bare-date vs. full-ISO-datetime handling, naive-datetime UTC anchoring.
  - The read-only I/O seam (fetch_shadow_rows/fetch_production_rows) against a
    fake Supabase double, mirroring tests/test_run_shadow_nse.py's pattern.
  - EVAL_WINDOW_DAYS is config-driven (not hardcoded) — default_window() must
    react to a changed config value.
"""

import inspect
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

import config
import eval_shadow
import wallet_sim


# --- fake Supabase double (mirrors tests/test_run_shadow_nse.py) -------------

class FakeQuery:
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

    def lte(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def execute(self):
        class R:
            data = self._data
        return R()


class FakeEvalSupabase:
    """Table-keyed double; unexpected table access raises, so a test can prove
    the harness only ever reads the tables its `--track` selects."""

    def __init__(self, tables: dict):
        self._tables = tables
        self.tables_accessed = []

    def table(self, name):
        self.tables_accessed.append(name)
        if name not in self._tables:
            raise AssertionError(f"unexpected read from table {name!r}")
        return FakeQuery(self._tables[name])


def _shadow_row(ticker, verdict, timestamp, price=None):
    return {"ticker": ticker, "verdict": verdict, "timestamp": timestamp,
            "data_snapshot": {"price": price} if price is not None else {}}


def _prod_row(ticker, verdict, timestamp, alerted=False):
    return {"ticker": ticker, "verdict": verdict, "timestamp": timestamp, "alerted": alerted}


# --- build_report correctness --------------------------------------------------

def _synthetic_rows():
    shadow_rows = [
        # AAPL: one closed winning round trip, then flat
        _shadow_row("AAPL", "Buy", "2026-07-01T09:00:00Z", 100.0),
        _shadow_row("AAPL", "Hold", "2026-07-02T09:00:00Z", 102.0),
        _shadow_row("AAPL", "Sell", "2026-07-03T09:00:00Z", 110.0),
        # MSFT: one open position (still holding)
        _shadow_row("MSFT", "Buy", "2026-07-01T09:00:00Z", 300.0),
        _shadow_row("MSFT", "Hold", "2026-07-05T09:00:00Z", 280.0),
    ]
    production_rows = [
        _prod_row("AAPL", "Buy", "2026-07-01T09:00:00Z", alerted=True),
        _prod_row("AAPL", "Hold", "2026-07-02T09:00:00Z"),
        _prod_row("AAPL", "Sell", "2026-07-03T09:00:00Z", alerted=True),
        _prod_row("MSFT", "Buy", "2026-07-01T09:00:00Z", alerted=True),
        _prod_row("MSFT", "Hold", "2026-07-05T09:00:00Z"),
    ]
    return shadow_rows, production_rows


def test_build_report_verdict_counts_correct():
    shadow_rows, production_rows = _synthetic_rows()
    report = eval_shadow.build_report(shadow_rows, production_rows,
                                       track="us_ca", since="2026-07-01", until="2026-07-14")
    assert report["shadow"]["verdict_counts"] == {"Buy": 2, "Sell": 1, "Hold": 2}
    assert report["production"]["verdict_counts"] == {"Buy": 2, "Sell": 1, "Hold": 2}
    assert report["production"]["verdict_changes"] == 3   # 3 alerted=True rows


def test_build_report_round_trip_count_and_win_rate():
    shadow_rows, production_rows = _synthetic_rows()
    report = eval_shadow.build_report(shadow_rows, production_rows,
                                       track="us_ca", since="2026-07-01", until="2026-07-14")
    assert report["shadow"]["round_trips"] == 1
    assert report["shadow"]["wins"] == 1
    assert report["shadow"]["win_rate"] == 1.0
    expected_return = round((110.0 / 100.0 - 1) * 100, 4)
    assert report["shadow"]["realized_return_pct_sum"] == expected_return
    assert report["shadow"]["open_positions"] == 1


def test_build_report_per_ticker_breakdown_correct():
    shadow_rows, production_rows = _synthetic_rows()
    report = eval_shadow.build_report(shadow_rows, production_rows,
                                       track="us_ca", since="2026-07-01", until="2026-07-14")
    aapl = report["per_ticker"]["AAPL"]
    assert aapl["checks"] == 3
    assert aapl["round_trips"] == 1
    assert aapl["wins"] == 1
    assert aapl["win_rate"] == 1.0
    assert aapl["open_position"] is None

    msft = report["per_ticker"]["MSFT"]
    assert msft["checks"] == 2
    assert msft["round_trips"] == 0
    assert msft["win_rate"] is None            # no round trips -> None, not ZeroDivisionError
    assert msft["open_position"] is not None
    assert msft["open_position"]["entry_price"] == 300.0
    assert msft["open_position"]["mark_price"] == 280.0   # marked to latest snapshot price
    expected_unreal = round((280.0 / 300.0 - 1) * 100, 4)
    assert msft["open_position"]["unrealized_return_pct"] == expected_unreal

    assert report["tickers"] == ["AAPL", "MSFT"]


def test_build_report_losing_round_trip_is_not_counted_as_a_win():
    shadow_rows = [
        _shadow_row("TSLA", "Buy", "t1", 200.0),
        _shadow_row("TSLA", "Sell", "t2", 150.0),   # -25%, a loss
    ]
    report = eval_shadow.build_report(shadow_rows, [], track="us_ca", since="s", until="u")
    tsla = report["per_ticker"]["TSLA"]
    assert tsla["round_trips"] == 1
    assert tsla["wins"] == 0
    assert tsla["win_rate"] == 0.0
    assert tsla["realized_return_pct_sum"] == round((150.0 / 200.0 - 1) * 100, 4)


def test_build_report_empty_input_produces_empty_but_valid_report():
    report = eval_shadow.build_report([], [], track="nse", since="s", until="u")
    assert report["tickers"] == []
    assert report["per_ticker"] == {}
    assert report["shadow"]["round_trips"] == 0
    assert report["shadow"]["win_rate"] is None
    assert report["shadow"]["total_checks"] == 0
    assert report["production"]["total_checks"] == 0


# --- render_report correctness / no-crash on None fields ----------------------

def test_render_report_well_formed_and_does_not_crash_on_none_win_rate_or_open_position():
    shadow_rows, production_rows = _synthetic_rows()
    report = eval_shadow.build_report(shadow_rows, production_rows,
                                       track="us_ca", since="2026-07-01", until="2026-07-14")
    text = eval_shadow.render_report(report)
    assert isinstance(text, str)
    assert "track=us_ca" in text
    assert "AAPL" in text and "MSFT" in text
    assert "n/a" in text   # MSFT has no round trips -> win_rate rendered as n/a


def test_render_report_on_fully_empty_report_does_not_crash():
    report = eval_shadow.build_report([], [], track="us_ca", since="s", until="u")
    text = eval_shadow.render_report(report)
    assert "SHADOW" in text
    assert "win_rate=n/a" in text


# --- determinism: THE FR31 acceptance criterion (design §17.3) ----------------

def test_build_report_is_deterministic_identical_input_identical_output():
    """Two build_report() calls over identical input must produce byte-identical
    (== ) dicts. This is FR31's explicit reproducibility acceptance bar."""
    shadow_rows, production_rows = _synthetic_rows()
    report1 = eval_shadow.build_report(shadow_rows, production_rows,
                                        track="us_ca", since="2026-07-01", until="2026-07-14")
    report2 = eval_shadow.build_report(shadow_rows, production_rows,
                                        track="us_ca", since="2026-07-01", until="2026-07-14")
    assert report1 == report2


def test_build_report_deterministic_regardless_of_input_row_order():
    """Rows are sorted internally by ticker/timestamp, so a shuffled input row
    order must not change the output — order-independence is part of
    reproducibility."""
    shadow_rows, production_rows = _synthetic_rows()
    shuffled = list(reversed(shadow_rows))
    report_a = eval_shadow.build_report(shadow_rows, production_rows,
                                         track="us_ca", since="s", until="u")
    report_b = eval_shadow.build_report(shuffled, production_rows,
                                         track="us_ca", since="s", until="u")
    assert report_a == report_b


def test_render_report_is_deterministic():
    shadow_rows, production_rows = _synthetic_rows()
    report = eval_shadow.build_report(shadow_rows, production_rows,
                                       track="us_ca", since="s", until="u")
    assert eval_shadow.render_report(report) == eval_shadow.render_report(report)


def test_json_output_is_reproducible_byte_identical_with_sort_keys():
    """main() writes --output as sort_keys=True JSON so the file itself is
    byte-identical across runs on the same data (handoff.md's stated property)."""
    shadow_rows, production_rows = _synthetic_rows()
    report1 = eval_shadow.build_report(shadow_rows, production_rows,
                                        track="us_ca", since="s", until="u")
    report2 = eval_shadow.build_report(shadow_rows, production_rows,
                                        track="us_ca", since="s", until="u")
    assert json.dumps(report1, sort_keys=True) == json.dumps(report2, sort_keys=True)


# --- read-only guarantee (HARD, design §17.3) — automated regression guard ----

_WRITE_PATTERNS = (r"\.insert\(", r"\.update\(", r"\.upsert\(", r"\.delete\(")


def _code_without_docstrings(module):
    """Strip the module's own docstring text (which legitimately *mentions*
    these call names as prose) before scanning for real write calls."""
    src = inspect.getsource(module)
    doc = module.__doc__ or ""
    return src.replace(doc, "")


def test_eval_shadow_has_no_insert_update_upsert_delete_calls():
    code = _code_without_docstrings(eval_shadow)
    for pattern in _WRITE_PATTERNS:
        assert not re.search(pattern, code), \
            f"eval_shadow.py must never write to any table — found {pattern}"


def test_wallet_sim_has_no_insert_update_upsert_delete_calls():
    code = _code_without_docstrings(wallet_sim)
    for pattern in _WRITE_PATTERNS:
        assert not re.search(pattern, code), \
            f"wallet_sim.py must never write to any table — found {pattern}"


def test_eval_shadow_source_file_grep_matches_only_docstring_prose():
    """Same check as dev's manual grep (handoff.md), run against the actual
    source file on disk (not just inspect.getsource) as a standing regression
    guard: every matching line in the raw file must be inside the module
    docstring's own prose line, not a real call."""
    import pathlib
    path = pathlib.Path(eval_shadow.__file__)
    lines = path.read_text().splitlines()
    combined = r"\.insert\(|\.update\(|\.upsert\(|\.delete\("
    matches = [line for line in lines if re.search(combined, line)]
    for line in matches:
        assert "No .insert(" in line or "docstring" in line.lower(), \
            f"unexpected write-looking call in eval_shadow.py: {line!r}"
    # sanity: the docstring prose line itself IS present (proves the grep isn't vacuous)
    assert any("No .insert(" in line for line in matches)


def test_wallet_sim_source_file_has_zero_write_call_matches():
    import pathlib
    path = pathlib.Path(wallet_sim.__file__)
    text = path.read_text()
    combined = r"\.insert\(|\.update\(|\.upsert\(|\.delete\("
    assert not re.search(combined, text), "wallet_sim.py source has no legitimate reason to match at all"


def test_eval_shadow_never_imports_or_references_a_write_client_method_name():
    """Belt-and-suspenders: confirm every Supabase call chain in eval_shadow.py
    ends in .execute() following only select/eq/gte/lte/in_/order — read-only
    shape, never a write verb."""
    src = inspect.getsource(eval_shadow)
    # every sb.table(...) chain in the I/O functions
    assert "sb.table(" in src
    for forbidden in (".insert(", ".update(", ".upsert(", ".delete("):
        assert forbidden not in src.replace(eval_shadow.__doc__ or "", "")


# --- CLI parsing ----------------------------------------------------------------

def test_parse_args_track_required():
    with pytest.raises(SystemExit):
        eval_shadow._parse_args([])


def test_parse_args_track_rejects_invalid_choice():
    with pytest.raises(SystemExit):
        eval_shadow._parse_args(["--track", "bogus_track"])


def test_parse_args_track_accepts_us_ca():
    args = eval_shadow._parse_args(["--track", "us_ca"])
    assert args.track == "us_ca"
    assert args.since is None
    assert args.until is None


def test_parse_args_track_accepts_nse():
    args = eval_shadow._parse_args(["--track", "nse"])
    assert args.track == "nse"


def test_parse_args_since_until_optional_and_pass_through():
    args = eval_shadow._parse_args(["--track", "us_ca", "--since", "2026-07-01", "--until", "2026-07-14"])
    assert args.since == "2026-07-01"
    assert args.until == "2026-07-14"


def test_parse_args_output_optional():
    args = eval_shadow._parse_args(["--track", "us_ca", "--output", "report.json"])
    assert args.output == "report.json"
    args_no_output = eval_shadow._parse_args(["--track", "us_ca"])
    assert args_no_output.output is None


# --- default_window / parse_window_bound ---------------------------------------

def test_default_window_covers_last_n_days_ending_now():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    since, until = eval_shadow.default_window(now, 14)
    assert until == now.isoformat()
    assert since == (now - timedelta(days=14)).isoformat()


def test_default_window_reacts_to_a_different_days_value():
    """Configurability check: a different `days` value must shift the window,
    proving EVAL_WINDOW_DAYS isn't hardcoded inside default_window."""
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    since_14, _ = eval_shadow.default_window(now, 14)
    since_7, _ = eval_shadow.default_window(now, 7)
    assert since_14 != since_7
    assert since_7 == (now - timedelta(days=7)).isoformat()


def test_parse_window_bound_accepts_bare_date():
    result = eval_shadow.parse_window_bound("2026-07-01")
    dt = datetime.fromisoformat(result)
    assert dt.year == 2026 and dt.month == 7 and dt.day == 1
    assert dt.tzinfo is not None   # anchored to UTC


def test_parse_window_bound_accepts_full_iso_datetime():
    result = eval_shadow.parse_window_bound("2026-07-01T15:30:00")
    dt = datetime.fromisoformat(result)
    assert dt.hour == 15 and dt.minute == 30
    assert dt.tzinfo is not None


def test_parse_window_bound_anchors_naive_datetime_to_utc():
    result = eval_shadow.parse_window_bound("2026-07-01T00:00:00")
    dt = datetime.fromisoformat(result)
    assert dt.tzinfo == timezone.utc


def test_parse_window_bound_preserves_explicit_timezone():
    result = eval_shadow.parse_window_bound("2026-07-01T00:00:00+05:30")
    dt = datetime.fromisoformat(result)
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)


# --- I/O seam: fetch_shadow_rows / fetch_production_rows ----------------------

def test_fetch_shadow_rows_reads_the_correct_table_for_track():
    sb = FakeEvalSupabase({"call_log_shadow": [_shadow_row("AAPL", "Buy", "t1", 100.0)]})
    rows = eval_shadow.fetch_shadow_rows(sb, "call_log_shadow", "since", "until")
    assert rows == [_shadow_row("AAPL", "Buy", "t1", 100.0)]
    assert sb.tables_accessed == ["call_log_shadow"]


def test_fetch_shadow_rows_never_touches_call_log_or_other_shadow_table():
    sb = FakeEvalSupabase({"call_log_shadow_nse": [_shadow_row("TCS", "Buy", "t1", 3500.0)]})
    rows = eval_shadow.fetch_shadow_rows(sb, "call_log_shadow_nse", "since", "until")
    assert len(rows) == 1
    assert sb.tables_accessed == ["call_log_shadow_nse"]


def test_fetch_production_rows_empty_tickers_short_circuits_no_query():
    sb = FakeEvalSupabase({"call_log": []})
    rows = eval_shadow.fetch_production_rows(sb, [], "since", "until")
    assert rows == []
    assert sb.tables_accessed == []   # never even called .table()


def test_fetch_production_rows_reads_call_log():
    sb = FakeEvalSupabase({"call_log": [_prod_row("AAPL", "Buy", "t1", alerted=True)]})
    rows = eval_shadow.fetch_production_rows(sb, ["AAPL"], "since", "until")
    assert rows == [_prod_row("AAPL", "Buy", "t1", alerted=True)]
    assert sb.tables_accessed == ["call_log"]


# --- end-to-end (I/O seam through to a rendered report) ------------------------

def test_end_to_end_fetch_and_build_report_via_fake_double():
    shadow_rows, production_rows = _synthetic_rows()
    sb = FakeEvalSupabase({"call_log_shadow": shadow_rows, "call_log": production_rows})
    fetched_shadow = eval_shadow.fetch_shadow_rows(sb, "call_log_shadow", "s", "u")
    tickers = sorted({r["ticker"] for r in fetched_shadow})
    fetched_prod = eval_shadow.fetch_production_rows(sb, tickers, "s", "u")
    report = eval_shadow.build_report(fetched_shadow, fetched_prod, track="us_ca", since="s", until="u")
    assert report["tickers"] == ["AAPL", "MSFT"]
    text = eval_shadow.render_report(report)
    assert "AAPL" in text


# --- EVAL_WINDOW_DAYS is config-driven, not hardcoded -------------------------

def test_main_uses_config_eval_window_days_not_a_hardcoded_value(monkeypatch):
    """Configurability check: change config.EVAL_WINDOW_DAYS and confirm
    eval_shadow.main() actually queries a different window (proving it reads
    the config value at call time, not a hardcoded literal)."""
    captured = {}

    class Sb(FakeEvalSupabase):
        pass

    sb = FakeEvalSupabase({"call_log_shadow": [], "call_log": []})
    monkeypatch.setattr(config, "EVAL_WINDOW_DAYS", 3)
    monkeypatch.setattr(eval_shadow, "config", config)
    monkeypatch.setattr(eval_shadow.state, "client", lambda: sb)
    monkeypatch.setattr(config, "require_secrets", lambda: None)

    original_fetch = eval_shadow.fetch_shadow_rows

    def _spy_fetch(sb_, table, since_iso, until_iso):
        captured["since"] = since_iso
        captured["until"] = until_iso
        return original_fetch(sb_, table, since_iso, until_iso)

    monkeypatch.setattr(eval_shadow, "fetch_shadow_rows", _spy_fetch)

    eval_shadow.main(["--track", "us_ca"])

    since_dt = datetime.fromisoformat(captured["since"])
    until_dt = datetime.fromisoformat(captured["until"])
    assert (until_dt - since_dt).days == 3
