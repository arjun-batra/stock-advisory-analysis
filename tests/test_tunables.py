"""INC-6: admin portal tunables editor (FR30) -- scripts/config.py's two-tier
fallback chain (table -> repo-committed cache, no third hardcoded tier),
write-back validation, and the TUNABLES_DEGRADED -> heartbeat wiring.

Design: docs/design/admin-portal-tunables.md, docs/design/tunables-fallback.md,
docs/design/tunables-workflow-writeback.md (all §16.4). Acceptance criteria:
docs/design/increment-plan.md lines 189-282 (16 ACs) -- this file covers the
ACs that are independently scriptable without live Supabase/GitHub Actions
access (AC2, AC5, AC8, AC9, AC10 (both halves, via a mocked fetch), AC11
(structural), AC12, AC13, AC14, AC15 (structural), AC16 (structural)). AC1,
AC3, AC4, AC6, AC7, AC15's live-dispatch half, and AC16's live-retry half all
require a live Supabase project / a real workflow dispatch -- not reproducible
in this session, see docs/test-report.md.

Two techniques used throughout, both established by the design itself
(tunables-fallback.md REV-041's "single patchable seam" note):

1. `_fetch_tunables()` / `_tunable()` / `write_tunables_cache_if_fetched()` are
   plain module-level functions reading/writing module globals
   (`config._TUNABLES`, `config._TUNABLES_CACHE`, `config._TUNABLE_CASTS`,
   `config._CACHE_PATH`) -- most tests here monkeypatch those globals directly
   and call the functions, no reload needed.
2. Tests that need a REAL tier-1 fetch to run (to prove propagation end to end,
   AC5/AC10/AC13) patch `supabase.create_client` (the package-level symbol
   `scripts/config.py` imports via `from supabase import create_client`) BEFORE
   reloading `config` via the `reload_config` fixture from test_config.py --
   reload re-executes `from supabase import create_client`, which re-resolves
   against the (now-patched) `supabase` module attribute.
"""

import importlib
import json
import pathlib
import shutil
import socket
import subprocess
import sys

import pytest

import config
import run_hourly
import run_discovery
import publish_prices

from test_config import reload_config          # noqa: F401 -- reused fixture, see module docstring
from test_state import FakeSupabase, FakeNotifier, _wl_row, _data, _ai

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The 10 curated keys, at the seed value both sql/admin_portal_tunables.sql and
# tunables_cache.json commit (AC2 already diffs those two files directly below;
# this dict is a third independent transcription used only to build fake
# tier-1 fetch payloads for the tests in this file).
_SEED = {
    "GEMINI_MODEL": "gemini-2.5-flash",
    "GEMINI_MODEL_BACKUP": "gemini-2.5-flash-lite",
    "ALERTS_ENABLED": "true",
    "DISCOVERY_GAINER_PCT": "5",
    "DISCOVERY_LOSER_PCT": "-5",
    "DISCOVERY_VOL_SPIKE": "2.0",
    "DISCOVERY_MIN_MARKET_CAP": "2000000000",
    "DISCOVERY_MIN_MARKET_CAP_INR": "50000000000",
    "DISCOVERY_SHORTLIST_MAX": "15",
    "DISCOVERY_PUSH_COOLDOWN_DAYS": "7",
}


class _FakeExec:
    def __init__(self, data):
        self.data = data


class _FakeTunablesTable:
    def __init__(self, data):
        self._data = data

    def select(self, *_a):
        return self

    def execute(self):
        return _FakeExec(self._data)


class _FakeSupabaseClient:
    def __init__(self, data):
        self._data = data

    def table(self, _name):
        return _FakeTunablesTable(self._data)


@pytest.fixture
def mock_tunables_fetch(monkeypatch):
    """Patches supabase.create_client so config.py's tier-1 fetch (when NOT
    skipped) returns a controlled row set instead of hitting the network.
    Returns a setter the test calls BEFORE reload_config(...). `captured` (a
    dict passed by the caller) records the create_client kwargs, if given --
    used by the AC13 timeout-plumbing test."""
    import supabase as supabase_pkg

    def _set(rows, captured=None, raises=None):
        def fake_create_client(url, key, options=None):
            if captured is not None:
                captured["url"] = url
                captured["key"] = key
                captured["options"] = options
            if raises is not None:
                raise raises
            return _FakeSupabaseClient(rows)

        monkeypatch.setattr(supabase_pkg, "create_client", fake_create_client)

    return _set


# --- AC2: tunables_cache.json seed byte-for-byte matches the SQL seed --------

def test_ac2_cache_seed_matches_sql_seed_byte_for_byte():
    cache = json.loads((REPO_ROOT / "tunables_cache.json").read_text())
    sql_text = (REPO_ROOT / "sql" / "admin_portal_tunables.sql").read_text()

    import re
    insert_block = sql_text.split("insert into public.tunables")[1]
    sql_pairs = dict(re.findall(r"\('([^']+)', '([^']*)',", insert_block))

    assert set(cache) == set(sql_pairs) == set(_SEED)
    for key in _SEED:
        assert cache[key] == sql_pairs[key] == _SEED[key], key
    # The specific, explicitly-called-out row (AC1/AC2's text): seeded "true",
    # not config.py's old bare "false" literal default.
    assert cache["ALERTS_ENABLED"] == "true"


# --- AC5: import-time pickup only, not hot-reloaded mid-run -----------------

def test_ac5_table_edit_propagates_on_next_process_start(mock_tunables_fetch, reload_config):
    edited = dict(_SEED, GEMINI_MODEL="edited-model")
    mock_tunables_fetch([{"key": k, "value": v} for k, v in edited.items()])

    cfg = reload_config(SKIP_TUNABLES_FETCH="false", SUPABASE_URL="https://example.invalid.supabase.co")

    assert cfg.GEMINI_MODEL == "edited-model"
    assert cfg.TUNABLES_DEGRADED is False   # all 10 keys resolved from tier 1 this run


def test_ac5_resolved_value_does_not_change_mid_process(mock_tunables_fetch, reload_config):
    rows = [{"key": k, "value": v} for k, v in _SEED.items()]
    mock_tunables_fetch(rows)
    cfg = reload_config(SKIP_TUNABLES_FETCH="false", SUPABASE_URL="https://example.invalid.supabase.co")
    assert cfg.GEMINI_MODEL == "gemini-2.5-flash"

    # Simulate a table edit happening AFTER this process already imported config.
    for row in rows:
        if row["key"] == "GEMINI_MODEL":
            row["value"] = "changed-after-import"

    # The already-resolved module constant is untouched -- no hot reload.
    assert cfg.GEMINI_MODEL == "gemini-2.5-flash"
    # A fresh fetch call WOULD see the new value (proves the mock itself is
    # live, i.e. the assertion above is a real "no hot reload" property, not
    # an artifact of a frozen mock):
    assert cfg._fetch_tunables()["GEMINI_MODEL"] == "changed-after-import"


def test_empty_string_is_a_resolved_value_not_a_missing_one(monkeypatch):
    """GEMINI_MODEL_BACKUP's own seeded description: 'leave empty to disable
    the fallback model' -- `_tunable()` must treat "" as present (only `is
    not None` falls through), not as a miss that falls to tier 2."""
    monkeypatch.setattr(config, "_TUNABLES", {"GEMINI_MODEL_BACKUP": ""})
    monkeypatch.setattr(config, "_TUNABLES_CACHE", {"GEMINI_MODEL_BACKUP": "should-not-be-used"})
    assert config._tunable("GEMINI_MODEL_BACKUP", str) == ""


# --- AC8: read-only entry points never write the cache -----------------------

def test_ac8_run_discovery_and_publish_prices_never_call_write_tunables_cache():
    for name in ("run_discovery.py", "publish_prices.py"):
        text = (REPO_ROOT / "scripts" / name).read_text()
        assert "write_tunables_cache_if_fetched" not in text, (
            f"{name} must remain a read-only tunables-cache consumer (Decision #28/#29)"
        )


def test_ac8_run_hourly_calls_write_tunables_cache_exactly_once():
    text = (REPO_ROOT / "scripts" / "run_hourly.py").read_text()
    assert text.count("write_tunables_cache_if_fetched(") == 1


# --- AC9: double-failure fails loud, names the key, exits non-zero ----------

def test_ac9_direct_double_miss_raises_systemexit_naming_the_key(monkeypatch):
    monkeypatch.setattr(config, "_TUNABLES", {})
    monkeypatch.setattr(config, "_TUNABLES_CACHE", {})
    with pytest.raises(SystemExit) as exc:
        config._tunable("DISCOVERY_VOL_SPIKE", float)
    msg = str(exc.value)
    assert "DISCOVERY_VOL_SPIKE" in msg
    assert "tunables_cache.json" in msg   # names both failed sources, not just one


def test_ac9_corrupted_cache_file_is_treated_as_a_miss(tmp_path, monkeypatch):
    bad_cache = tmp_path / "tunables_cache.json"
    bad_cache.write_text("{not valid json")
    monkeypatch.setattr(config, "_CACHE_PATH", bad_cache)
    assert config._load_tunables_cache() == {}


def test_ac9_entry_point_import_exits_nonzero_on_double_miss(tmp_path):
    """Literal AC9 reproduction: a real `import config` subprocess, in a
    scratch copy of scripts/ with NO tunables_cache.json present at all (the
    'missing' half of AC9) and a fetch forced to fail fast (bad SUPABASE_URL,
    no network hang) -- asserts SystemExit naming the key and a non-zero exit.
    Runs in an isolated tmp_path copy so the real repo-root
    tunables_cache.json is never touched."""
    scratch_repo = tmp_path / "repo_copy"
    shutil.copytree(REPO_ROOT / "scripts", scratch_repo / "scripts")
    assert not (scratch_repo / "tunables_cache.json").exists()   # the scratch repo has no cache file

    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, 'scripts'); import config"],
        cwd=scratch_repo,
        env={
            "PATH": "/usr/bin:/bin",
            "SKIP_TUNABLES_FETCH": "false",
            "SUPABASE_URL": "not-a-valid-url",
            "SUPABASE_SECRET_KEY": "x",
            "GEMINI_API_KEY": "x",
        },
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode != 0
    assert "GEMINI_MODEL" in result.stdout + result.stderr   # first curated key resolved, per _tunable() order
    assert "unavailable" in (result.stdout + result.stderr)


# --- AC10: ALERTS_ENABLED AND-gate direction (both halves) -------------------

def test_ac10_table_false_suppresses_a_scheduled_default_true_run(mock_tunables_fetch, reload_config):
    """Scheduled (no-inputs) dispatch: workflow env ALERTS_ENABLED arrives
    "true" (the workflow_dispatch input's own YAML default). Table says
    false -> must suppress."""
    rows = [{"key": k, "value": v} for k, v in dict(_SEED, ALERTS_ENABLED="false").items()]
    mock_tunables_fetch(rows)
    cfg = reload_config(ALERTS_ENABLED="true", SKIP_TUNABLES_FETCH="false",
                         SUPABASE_URL="https://example.invalid.supabase.co")
    assert cfg.ALERTS_ENABLED_TABLE is False
    assert cfg.ALERTS_ENABLED is False


def test_ac10_manual_dry_run_input_suppresses_even_when_table_true(mock_tunables_fetch, reload_config):
    """Manual off-hours dry run: inputs.alerts_enabled=false -> workflow env
    ALERTS_ENABLED="false". Table says true -> input still wins as a floor,
    proving the portal toggle can only ever suppress, never force alerts on."""
    rows = [{"key": k, "value": v} for k, v in dict(_SEED, ALERTS_ENABLED="true").items()]
    mock_tunables_fetch(rows)
    cfg = reload_config(ALERTS_ENABLED="false", SKIP_TUNABLES_FETCH="false",
                         SUPABASE_URL="https://example.invalid.supabase.co")
    assert cfg.ALERTS_ENABLED_TABLE is True
    assert cfg.ALERTS_ENABLED is False


def test_ac10_both_true_is_the_only_combination_that_alerts(mock_tunables_fetch, reload_config):
    """Proves the AND-gate direction, not just 'some interaction exists'."""
    rows = [{"key": k, "value": v} for k, v in dict(_SEED, ALERTS_ENABLED="true").items()]
    mock_tunables_fetch(rows)
    cfg = reload_config(ALERTS_ENABLED="true", SKIP_TUNABLES_FETCH="false",
                         SUPABASE_URL="https://example.invalid.supabase.co")
    assert cfg.ALERTS_ENABLED is True


# --- AC12 (REV-036): cache write-back validates and never shrinks -----------

def test_ac12_write_back_never_shrinks_and_rejects_bad_casts(tmp_path, monkeypatch):
    cache_path = tmp_path / "tunables_cache.json"
    cache_path.write_text(json.dumps(_SEED))
    monkeypatch.setattr(config, "_CACHE_PATH", cache_path)
    monkeypatch.setattr(config, "_TUNABLES_CACHE", dict(_SEED))

    fetched = dict(_SEED)
    del fetched["DISCOVERY_PUSH_COOLDOWN_DAYS"]     # this run's fetch omitted a key
    fetched["DISCOVERY_LOSER_PCT"] = "not-a-number"  # this run's fetch returned a bad-cast value
    fetched["GEMINI_MODEL"] = "gemini-3.0-updated"    # a legitimate change
    monkeypatch.setattr(config, "_TUNABLES", fetched)
    # real casts are already registered for all 10 real keys by this module's own import
    assert set(_SEED) <= set(config._TUNABLE_CASTS)

    config.write_tunables_cache_if_fetched()

    written = json.loads(cache_path.read_text())
    assert set(written) == set(_SEED)                              # never shrinks
    assert written["DISCOVERY_PUSH_COOLDOWN_DAYS"] == _SEED["DISCOVERY_PUSH_COOLDOWN_DAYS"]  # untouched
    assert written["DISCOVERY_LOSER_PCT"] == _SEED["DISCOVERY_LOSER_PCT"]  # bad cast never persisted
    assert written["GEMINI_MODEL"] == "gemini-3.0-updated"          # legit change persisted


def test_ac12_write_back_is_a_noop_when_this_runs_fetch_entirely_failed(tmp_path, monkeypatch):
    cache_path = tmp_path / "tunables_cache.json"
    cache_path.write_text(json.dumps({"GEMINI_MODEL": "untouched"}))
    monkeypatch.setattr(config, "_CACHE_PATH", cache_path)
    monkeypatch.setattr(config, "_TUNABLES_CACHE", {"GEMINI_MODEL": "untouched"})
    monkeypatch.setattr(config, "_TUNABLES", {})   # this run's fetch failed entirely

    config.write_tunables_cache_if_fetched()

    assert json.loads(cache_path.read_text()) == {"GEMINI_MODEL": "untouched"}


def test_ac12_tier1_cast_failure_fails_loud_never_reaches_cache_write(tmp_path, monkeypatch):
    """A value SUPABASE actually returned that fails its cast must SystemExit
    immediately (an operator-entered error) rather than silently falling to
    tier 2 and later getting persisted as the new last-known-good."""
    monkeypatch.setattr(config, "_TUNABLES", {"DISCOVERY_GAINER_PCT": "5%"})
    monkeypatch.setattr(config, "_TUNABLES_CACHE", {"DISCOVERY_GAINER_PCT": "5"})  # a good cache value exists

    with pytest.raises(SystemExit) as exc:
        config._tunable("DISCOVERY_GAINER_PCT", float)

    msg = str(exc.value)
    assert "DISCOVERY_GAINER_PCT" in msg and "5%" in msg
    assert "refusing" in msg.lower()


# --- AC13 (REV-041): fetch timeout + deterministic offline seam -------------

def test_ac13_timeout_tunable_default_and_override(reload_config):
    cfg = reload_config(TUNABLES_FETCH_TIMEOUT_MS=None, SKIP_TUNABLES_FETCH="true")
    assert cfg.TUNABLES_FETCH_TIMEOUT_MS == 5000

    cfg = reload_config(TUNABLES_FETCH_TIMEOUT_MS="9000", SKIP_TUNABLES_FETCH="true")
    assert cfg.TUNABLES_FETCH_TIMEOUT_MS == 9000


def test_ac13_timeout_is_actually_passed_into_client_options(mock_tunables_fetch, reload_config):
    captured = {}
    mock_tunables_fetch([{"key": k, "value": v} for k, v in _SEED.items()], captured=captured)

    reload_config(SKIP_TUNABLES_FETCH="false", TUNABLES_FETCH_TIMEOUT_MS="9000",
                  SUPABASE_URL="https://example.invalid.supabase.co")

    assert captured["options"].postgrest_client_timeout == 9.0   # ms -> seconds


def test_ac13_skip_tunables_fetch_makes_zero_network_calls(reload_config, monkeypatch):
    def _boom(*_a, **_kw):
        raise AssertionError("a network call was attempted despite SKIP_TUNABLES_FETCH=true")

    monkeypatch.setattr(socket.socket, "connect", _boom)

    cfg = reload_config(SKIP_TUNABLES_FETCH="true")

    assert cfg.GEMINI_MODEL == _SEED["GEMINI_MODEL"]   # resolved from tunables_cache.json (tier 2)
    assert cfg.TUNABLES_DEGRADED is True


# --- AC14 (REV-045): TUNABLES_DEGRADED reaches the heartbeat at all 3 entry points ---
# run_hourly's happy-path ("ok") and degraded-forces-partial cases live in
# test_run_orchestration.py (the pre-existing heartbeat coverage for that
# entry point) -- see test_heartbeat_is_ok_when_every_ticker_processes_cleanly
# (now neutralizes TUNABLES_DEGRADED to isolate the ticker-cleanliness half)
# and test_heartbeat_is_partial_when_tunables_are_degraded (new, this file's
# sibling assertion for that entry point). This section covers the other two.

_EMPTY_FUNNEL = {"raw": 10, "after_dedup": 10, "passed_quality": 0, "passed_signal": 0}


def test_ac14_run_discovery_heartbeat_is_partial_when_degraded_even_with_a_clean_candidate_run(monkeypatch):
    sb = FakeSupabase()
    monkeypatch.setattr(run_discovery.state, "client", lambda: sb)
    monkeypatch.setattr(run_discovery.notify, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: ([{"ticker": "AAPL", "signals": ["gainer"]}], 5, 0, _EMPTY_FUNNEL))
    monkeypatch.setattr(run_discovery.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True})
    monkeypatch.setattr(run_discovery.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", True)

    run_discovery.main()

    assert sb.run_heartbeat["daily-discovery"]["status"] == "partial"


def test_ac14_run_discovery_heartbeat_is_ok_when_not_degraded_and_run_is_clean(monkeypatch):
    """Configurability/edge-case counterpart: same clean run, TUNABLES_DEGRADED
    False -> "ok" -- proves the wiring is a real OR, not an always-partial bug."""
    sb = FakeSupabase()
    monkeypatch.setattr(run_discovery.state, "client", lambda: sb)
    monkeypatch.setattr(run_discovery.notify, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: ([{"ticker": "AAPL", "signals": ["gainer"]}], 5, 0, _EMPTY_FUNNEL))
    monkeypatch.setattr(run_discovery.ingest, "get_market_data",
                         lambda ticker: {**_data(ticker), "has_price": True})
    monkeypatch.setattr(run_discovery.ai_judge, "judge_batch",
                         lambda items, models=None: {"AAPL": _ai("Buy")})
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)

    run_discovery.main()

    assert sb.run_heartbeat["daily-discovery"]["status"] == "ok"


def test_ac14_run_discovery_zero_candidates_early_return_ignores_tunables_degraded(monkeypatch):
    """DOCUMENTS A GAP, not a spec pass: run_discovery.py:55-66's early-return
    branch (zero candidates, no screen errors) hardcodes "ok" and never
    consults config.TUNABLES_DEGRADED -- unlike the later computed `status =`
    line (run_discovery.py:115) that every other branch goes through. AC14's
    text ("all three entry points") does not carve out this branch. Filed as
    BUG-003 (docs/test-report.md) -- dev already flagged this exact gap in
    docs/handoff.md's Known Limitations, unresolved. This test locks in and
    documents the CURRENT (gap) behavior; it is expected to start failing
    (in a good way) once BUG-003 is fixed, at which point invert the
    assertion to "partial"."""
    sb = FakeSupabase()
    monkeypatch.setattr(run_discovery.state, "client", lambda: sb)
    monkeypatch.setattr(run_discovery.notify, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(run_discovery.prefilter, "find_candidates",
                         lambda exclude, region: ([], 5, 0, _EMPTY_FUNNEL))
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", True)

    run_discovery.main()

    assert sb.run_heartbeat["daily-discovery"]["status"] == "ok"   # see BUG-003 -- should arguably be "partial"


def test_ac14_publish_prices_heartbeat_is_partial_when_degraded_even_with_zero_skips(monkeypatch, tmp_path):
    sb = FakeSupabase()
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(publish_prices.state, "client", lambda: sb)
    monkeypatch.setattr(publish_prices.ingest, "get_market_data",
                         lambda ticker: {"has_price": True, "price": 100.0, "pct_change_1d": 1.0,
                                          "market": "US", "fundamentals": {"currency": "USD"}})
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", True)
    monkeypatch.chdir(tmp_path)   # publish_prices.main() writes pages/prices.json relative to cwd

    publish_prices.main()

    assert sb.run_heartbeat["publish-prices"]["status"] == "partial"


def test_ac14_publish_prices_heartbeat_is_ok_when_not_degraded_and_no_skips(monkeypatch, tmp_path):
    sb = FakeSupabase()
    sb.watchlist = [_wl_row("AAPL", "US")]
    monkeypatch.setattr(publish_prices.state, "client", lambda: sb)
    monkeypatch.setattr(publish_prices.ingest, "get_market_data",
                         lambda ticker: {"has_price": True, "price": 100.0, "pct_change_1d": 1.0,
                                          "market": "US", "fundamentals": {"currency": "USD"}})
    monkeypatch.setattr(config, "TUNABLES_DEGRADED", False)
    monkeypatch.chdir(tmp_path)

    publish_prices.main()

    assert sb.run_heartbeat["publish-prices"]["status"] == "ok"


# --- AC11 / AC15 / AC16: workflow YAML structural checks (no live dispatch) --
# Structural (content-based), not a git-diff-against-a-commit check, so this
# stays meaningful after future commits land -- the one-time diff-vs-baseline
# comparison for THIS increment was independently confirmed via `git diff`
# directly (see docs/test-report.md), not encoded as a durable test here.

def _workflow_text(name):
    return (REPO_ROOT / ".github" / "workflows" / name).read_text()


def _uncommented_lines(text):
    """Strips full-line and trailing '#' comments so structural YAML checks
    below don't false-positive on this file's own prose comments (which
    intentionally discuss `permissions:`/`tunables` in English)."""
    out = []
    for line in text.splitlines():
        stripped = line.split("#", 1)[0]
        if stripped.strip():
            out.append(stripped)
    return "\n".join(out)


def test_ac15_hourly_and_publish_prices_share_the_repo_commit_concurrency_group():
    for name in ("hourly-watchlist.yml", "publish-prices.yml"):
        text = _uncommented_lines(_workflow_text(name))
        assert "group: repo-commit" in text, name
        assert "group: hourly-watchlist" not in text, name
        assert "group: publish-prices" not in text, name


def test_ac16_permissions_block_is_job_scoped_not_top_level():
    text = _uncommented_lines(_workflow_text("hourly-watchlist.yml"))
    jobs_idx = text.index("\njobs:\n")
    header, body = text[:jobs_idx], text[jobs_idx:]

    assert "permissions:" not in header, "no top-level permissions: block may exist (REV-040b)"
    assert "permissions:" in body
    assert "contents: write" in body


def test_ac16_commit_step_has_a_bounded_retry_loop_with_error_annotation():
    text = _workflow_text("hourly-watchlist.yml")
    assert "Commit tunables cache if changed" in text
    assert "max_attempts=3" in text
    assert "git pull --rebase" in text and "git push origin" in text
    assert "::error::failed to push tunables_cache.json after" in text


def test_ac11_publish_prices_gained_nothing_besides_the_concurrency_rename():
    text = _workflow_text("publish-prices.yml")
    assert "tunables_cache.json" not in text
    assert "Commit tunables cache" not in text


def test_ac11_daily_discovery_workflow_is_untouched_by_tunables():
    text = _uncommented_lines(_workflow_text("daily-discovery.yml"))
    assert "tunables" not in text.lower()
