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


# --- defaults (2026-07-13 change request, Change 2 / design.md §16 note): ---
# --- corrected from gemini-3.5-flash / gemini-3.1-flash-lite (unstable) to ---
# --- the paid-tier gemini-2.5-flash family, standardized across every track --

def test_default_model_is_gemini_2_5_flash(reload_config):
    cfg = reload_config(GEMINI_MODEL=None)
    assert cfg.GEMINI_MODEL == "gemini-2.5-flash"


def test_default_backup_model(reload_config):
    cfg = reload_config(GEMINI_MODEL_BACKUP=None)
    assert cfg.GEMINI_MODEL_BACKUP == "gemini-2.5-flash-lite"


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


def test_shadow_enabled_any_non_true_explicit_value_fails_closed_typo(reload_config):
    """FR30 (corrected wording): fail-open applies ONLY to a truly unset/empty
    Variable. Any explicitly-set-but-wrong value -- including a typo like
    'flase' -- is not the empty string, so it skips the `or "true"` fallback,
    compares unequal to "true", and fails CLOSED (disables the pilot)."""
    cfg = reload_config(SHADOW_ENABLED="flase")   # typo
    assert cfg.SHADOW_ENABLED is False


def test_shadow_enabled_case_insensitive_false(reload_config):
    cfg = reload_config(SHADOW_ENABLED="FALSE")
    assert cfg.SHADOW_ENABLED is False


# --- FR38/NFR6: NSE shadow kill switch, same fail-open-on-empty-only shape ----
# --- as SHADOW_ENABLED (FR30), but a fully INDEPENDENT Variable (FR37) --------

def test_shadow_nse_enabled_defaults_true_when_unset(reload_config):
    cfg = reload_config(SHADOW_NSE_ENABLED=None)
    assert cfg.SHADOW_NSE_ENABLED is True


def test_shadow_nse_enabled_defaults_true_when_empty_string(reload_config):
    """A deleted/mistyped GitHub Variable arrives as an empty string — the
    accepted-risk fail-open case (FR38)."""
    cfg = reload_config(SHADOW_NSE_ENABLED="")
    assert cfg.SHADOW_NSE_ENABLED is True


def test_shadow_nse_enabled_false_disables(reload_config):
    cfg = reload_config(SHADOW_NSE_ENABLED="false")
    assert cfg.SHADOW_NSE_ENABLED is False


def test_shadow_nse_enabled_any_non_true_explicit_value_fails_closed_typo(reload_config):
    """FR38: fail-open applies ONLY to a truly unset/empty Variable. Any
    explicitly-set-but-wrong value -- including typos like 'flase'/'no'/'0' --
    is not the empty string, so it skips the `or "true"` fallback, compares
    unequal to "true", and fails CLOSED (disables the NSE pilot)."""
    for typo in ("flase", "no", "0"):
        cfg = reload_config(SHADOW_NSE_ENABLED=typo)
        assert cfg.SHADOW_NSE_ENABLED is False, f"expected fail-closed for {typo!r}"


def test_shadow_nse_enabled_case_insensitive_false(reload_config):
    cfg = reload_config(SHADOW_NSE_ENABLED="FALSE")
    assert cfg.SHADOW_NSE_ENABLED is False


def test_shadow_nse_enabled_is_independent_of_shadow_enabled(reload_config):
    """FR37 kill-switch independence: flipping SHADOW_NSE_ENABLED off must not
    affect SHADOW_ENABLED, and vice versa -- the two tracks toggle separately."""
    cfg = reload_config(SHADOW_NSE_ENABLED="false", SHADOW_ENABLED=None)
    assert cfg.SHADOW_NSE_ENABLED is False
    assert cfg.SHADOW_ENABLED is True

    cfg = reload_config(SHADOW_ENABLED="false", SHADOW_NSE_ENABLED=None)
    assert cfg.SHADOW_ENABLED is False
    assert cfg.SHADOW_NSE_ENABLED is True


def test_shadow_nse_prompt_variant_default(reload_config):
    cfg = reload_config(SHADOW_NSE_PROMPT_VARIANT=None)
    assert cfg.SHADOW_NSE_PROMPT_VARIANT == "position_aware_v1"


def test_shadow_nse_prompt_variant_override_propagates(reload_config):
    cfg = reload_config(SHADOW_NSE_PROMPT_VARIANT="custom_variant_v2")
    assert cfg.SHADOW_NSE_PROMPT_VARIANT == "custom_variant_v2"


def test_shadow_nse_snapshot_lookback_min_default_is_20(reload_config):
    """FR34: the lookback MUST stay under the 30-min NSE dispatch cadence."""
    cfg = reload_config(SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN=None)
    assert cfg.SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN == 20
    assert cfg.SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN < 30, \
        "lookback must stay under the 30-min NSE dispatch cadence (FR34)"


def test_shadow_nse_snapshot_lookback_min_override_propagates(reload_config):
    cfg = reload_config(SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN="15")
    assert cfg.SHADOW_NSE_SNAPSHOT_LOOKBACK_MIN == 15


def test_nse_models_helper_returns_nse_model_pair(reload_config):
    cfg = reload_config(NSE_GEMINI_MODEL="nse-primary", NSE_GEMINI_MODEL_BACKUP="nse-backup")
    assert cfg.nse_models() == ["nse-primary", "nse-backup"]


def test_nse_models_helper_drops_empty_backup(reload_config):
    cfg = reload_config(NSE_GEMINI_MODEL="nse-primary", NSE_GEMINI_MODEL_BACKUP="")
    assert cfg.nse_models() == ["nse-primary"]


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


# --- EVAL_WINDOW_DAYS (design §17.4, INC-2, FR31) ------------------------------

def test_eval_window_days_defaults_to_14(reload_config):
    cfg = reload_config(EVAL_WINDOW_DAYS=None)
    assert cfg.EVAL_WINDOW_DAYS == 14


def test_eval_window_days_override_propagates(reload_config):
    cfg = reload_config(EVAL_WINDOW_DAYS="7")
    assert cfg.EVAL_WINDOW_DAYS == 7


# --- require_secrets() fail-fast behavior ---------------------------------------

def test_require_secrets_fails_fast_when_missing(reload_config):
    cfg = reload_config(GEMINI_API_KEY=None, SUPABASE_URL="set", SUPABASE_SECRET_KEY="set")
    with pytest.raises(SystemExit) as exc:
        cfg.require_secrets()
    assert "GEMINI_API_KEY" in str(exc.value)


def test_require_secrets_passes_when_all_present(reload_config):
    cfg = reload_config(GEMINI_API_KEY="k", SUPABASE_URL="u", SUPABASE_SECRET_KEY="s")
    cfg.require_secrets()   # must not raise
