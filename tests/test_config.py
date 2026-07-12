"""config.py — the tunables surface (docs/requirements.md §11, design.md §9).

Covers: (1) env-var overrides actually propagate and defaults are correct when
unset (the reviewer's hardcoding-audit baseline — "No tunable may live only in
code"), (2) the FR30/NFR5 shadow kill-switch's documented fail-open posture,
(3) the market-hours gate boundary, including the RUNTIME_CLOSE_GRACE_MIN
tunable actually shifting the boundary (explicit configurability check per QA
rules: change a config value, verify behavior changes).

Each test that needs a different env value reloads the `config` module, since
its tunables are read once at import time (matching how the real entry points
consume it). The module is reloaded again afterward so no test's env leakage
survives into the next.
"""

import datetime as dt
import importlib
import os

import pytest

import config


@pytest.fixture
def reload_config():
    """Reload config with a patched environment, restoring both the original
    environment AND the original module state on teardown so tests never leak
    env/config state into each other. (Deliberately manages os.environ itself,
    rather than via the `monkeypatch` fixture, so the restore-then-reload
    ordering is guaranteed: reverting env after the config reload would leave
    the module holding stale values from the mutated environment.)"""
    original_env = dict(os.environ)

    def _do(**env):
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(config)
        return config

    yield _do
    os.environ.clear()
    os.environ.update(original_env)
    importlib.reload(config)


# --- defaults (also locks in the qa/test-plan-full-codebase.md correction: ---
# --- the real default is gemini-3.5-flash, NOT gemini-3-flash) ----------------

def test_default_model_is_gemini_3_5_flash(reload_config):
    cfg = reload_config(GEMINI_MODEL=None)
    assert cfg.GEMINI_MODEL == "gemini-3.5-flash"


def test_default_backup_model(reload_config):
    cfg = reload_config(GEMINI_MODEL_BACKUP=None)
    assert cfg.GEMINI_MODEL_BACKUP == "gemini-3.1-flash-lite"


def test_default_discovery_models(reload_config):
    cfg = reload_config(DISCOVERY_GEMINI_MODEL=None, DISCOVERY_GEMINI_MODEL_BACKUP=None)
    assert cfg.DISCOVERY_GEMINI_MODEL == "gemini-2.5-flash"
    assert cfg.DISCOVERY_GEMINI_MODEL_BACKUP == "gemini-2.5-flash-lite"


def test_nse_model_pair_inherits_watchlist_pair_by_default(reload_config):
    cfg = reload_config(GEMINI_MODEL="watchlist-model", GEMINI_MODEL_BACKUP="watchlist-backup",
                         NSE_GEMINI_MODEL=None, NSE_GEMINI_MODEL_BACKUP=None)
    assert cfg.NSE_GEMINI_MODEL == "watchlist-model"
    assert cfg.NSE_GEMINI_MODEL_BACKUP == "watchlist-backup"


# --- env-var overrides actually propagate --------------------------------------

def test_gemini_timeout_ms_override_propagates(reload_config):
    cfg = reload_config(GEMINI_TIMEOUT_MS="99000")
    assert cfg.GEMINI_TIMEOUT_MS == 99000


def test_gemini_timeout_ms_default_when_unset(reload_config):
    cfg = reload_config(GEMINI_TIMEOUT_MS=None)
    assert cfg.GEMINI_TIMEOUT_MS == 180000


def test_nse_model_override_propagates(reload_config):
    cfg = reload_config(NSE_GEMINI_MODEL="custom-nse-model")
    assert cfg.NSE_GEMINI_MODEL == "custom-nse-model"


def test_discovery_min_market_cap_override_propagates(reload_config):
    cfg = reload_config(DISCOVERY_MIN_MARKET_CAP="123456789")
    assert cfg.DISCOVERY_MIN_MARKET_CAP == 123456789.0


def test_alerts_enabled_is_off_by_default(reload_config):
    cfg = reload_config(ALERTS_ENABLED=None)
    assert cfg.ALERTS_ENABLED is False


def test_alerts_enabled_true_override(reload_config):
    cfg = reload_config(ALERTS_ENABLED="true")
    assert cfg.ALERTS_ENABLED is True


def test_gemini_max_retries_empty_string_env_uses_default(reload_config):
    """Documented empty-string trap (config.py comment): the workflow may pass
    an unset Variable through as an empty string, which `or "3"` must still
    resolve to the numeric default, not crash on int('')."""
    cfg = reload_config(GEMINI_MAX_RETRIES="")
    assert cfg.GEMINI_MAX_RETRIES == 3


# --- FR30/NFR5: shadow kill switch defaults fail-OPEN, only "false" disables --

def test_shadow_enabled_defaults_true_when_unset(reload_config):
    cfg = reload_config(SHADOW_ENABLED=None)
    assert cfg.SHADOW_ENABLED is True


def test_shadow_enabled_defaults_true_when_empty_string(reload_config):
    """A deleted/mistyped GitHub Variable arrives as an empty string — the
    accepted-risk fail-open case (FR30)."""
    cfg = reload_config(SHADOW_ENABLED="")
    assert cfg.SHADOW_ENABLED is True


def test_shadow_enabled_false_disables(reload_config):
    cfg = reload_config(SHADOW_ENABLED="false")
    assert cfg.SHADOW_ENABLED is False


def test_shadow_enabled_only_literal_false_disables_a_typo_stays_open(reload_config):
    """FR30's recorded accepted risk: a mistyped value (not the literal string
    'false') silently keeps the pilot running."""
    cfg = reload_config(SHADOW_ENABLED="flase")   # typo
    assert cfg.SHADOW_ENABLED is True


def test_shadow_enabled_case_insensitive_false(reload_config):
    cfg = reload_config(SHADOW_ENABLED="FALSE")
    assert cfg.SHADOW_ENABLED is False


# --- market-hours gate boundary + RUNTIME_CLOSE_GRACE_MIN configurability -----

def _et(hour, minute, weekday_date=dt.date(2026, 7, 13)):
    """2026-07-13 is a Monday."""
    return dt.datetime.combine(weekday_date, dt.time(hour, minute), tzinfo=config.MARKET_TZ)


def test_market_open_at_session_open_boundary():
    assert config.is_market_open(_et(9, 30)) is True


def test_market_closed_one_minute_before_open():
    assert config.is_market_open(_et(9, 29)) is False


def test_market_open_at_exact_close_with_default_grace():
    assert config.is_market_open(_et(16, 0)) is True


def test_market_open_still_within_default_grace_window():
    # default RUNTIME_CLOSE_GRACE_MIN=10 -> 16:00 + 10min = 16:10 inclusive
    assert config.is_market_open(_et(16, 10)) is True


def test_market_closed_just_past_default_grace_window():
    assert config.is_market_open(_et(16, 11)) is False


def test_market_closed_on_weekend():
    saturday = dt.date(2026, 7, 11)
    assert config.is_market_open(_et(12, 0, weekday_date=saturday)) is False


def test_runtime_close_grace_min_is_configurable_and_shifts_the_boundary(reload_config):
    """Explicit configurability check: change RUNTIME_CLOSE_GRACE_MIN and
    confirm the close boundary actually moves, proving it isn't hardcoded."""
    cfg = reload_config(RUNTIME_CLOSE_GRACE_MIN="0")
    assert cfg.RUNTIME_CLOSE_GRACE_MIN == 0
    now_at_16_05 = dt.datetime.combine(dt.date(2026, 7, 13), dt.time(16, 5), tzinfo=cfg.MARKET_TZ)
    # with zero grace, 16:05 (which was open under the default 10-min grace) is now closed
    assert cfg.is_market_open(now_at_16_05) is False

    cfg = reload_config(RUNTIME_CLOSE_GRACE_MIN="30")
    now_at_16_20 = dt.datetime.combine(dt.date(2026, 7, 13), dt.time(16, 20), tzinfo=cfg.MARKET_TZ)
    assert cfg.is_market_open(now_at_16_20) is True


# --- NSE session gate (FR17) ----------------------------------------------------

def _ist(hour, minute, weekday_date=dt.date(2026, 7, 13)):
    return dt.datetime.combine(weekday_date, dt.time(hour, minute), tzinfo=config.NSE_MARKET_TZ)


def test_nse_market_open_at_session_open():
    assert config.is_nse_open(_ist(9, 15)) is True


def test_nse_market_closed_before_open():
    assert config.is_nse_open(_ist(9, 14)) is False


def test_nse_market_open_within_default_grace_after_close():
    assert config.is_nse_open(_ist(15, 40)) is True   # 15:30 + 10min grace


def test_nse_market_closed_past_grace_after_close():
    assert config.is_nse_open(_ist(15, 41)) is False


# --- require_secrets() fail-fast behavior ---------------------------------------

def test_require_secrets_fails_fast_when_missing(reload_config):
    cfg = reload_config(GEMINI_API_KEY=None, SUPABASE_URL="set", SUPABASE_SECRET_KEY="set")
    with pytest.raises(SystemExit) as exc:
        cfg.require_secrets()
    assert "GEMINI_API_KEY" in str(exc.value)


def test_require_secrets_passes_when_all_present(reload_config):
    cfg = reload_config(GEMINI_API_KEY="k", SUPABASE_URL="u", SUPABASE_SECRET_KEY="s")
    cfg.require_secrets()   # must not raise
