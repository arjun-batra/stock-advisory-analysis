"""notify.py — pure alert-composition logic (FR12, FR13, FR18, FR23).

Only the pure functions and DryRunNotifier are exercised (no real network
call — NtfyNotifier.push is covered separately with requests.post mocked so
no test in this suite ever reaches ntfy.sh).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import notify


# --- FR23: notification timestamp is single-timezone, market-matched ----------

def test_us_timestamp_uses_et_label():
    ts = notify._market_timestamp("US")
    assert ts.endswith("ET")


def test_tsx_timestamp_uses_et_label():
    ts = notify._market_timestamp("TSX")
    assert ts.endswith("ET")


def test_nse_timestamp_uses_ist_label():
    ts = notify._market_timestamp("NSE")
    assert ts.endswith("IST")


def test_unknown_market_defaults_to_et():
    assert notify._market_timestamp(None).endswith("ET")
    assert notify._market_timestamp("").endswith("ET")
    assert notify._market_timestamp("MARS").endswith("ET")


def test_timestamp_format_matches_spec_pattern():
    # Format: "10:30 AM ET" / "8:00 PM IST" -- no leading zero on the hour.
    ts = notify._market_timestamp("US")
    parts = ts.split(" ")
    assert len(parts) == 3
    assert parts[1] in ("AM", "PM")
    assert parts[2] == "ET"
    assert not parts[0].split(":")[0].startswith("0")


# --- FR18: NSE alerts route to their own topic, with a safe fallback ----------

def test_nse_routes_to_nse_topic_when_provisioned():
    topic = notify._topic_for("NSE", "default-topic", "nse-topic")
    assert topic == "nse-topic"


def test_nse_falls_back_to_default_topic_when_unprovisioned(capsys):
    topic = notify._topic_for("NSE", "default-topic", "")
    assert topic == "default-topic"
    # fallback must be operator-visible in the run log (issue #35 fix), not silent
    out = capsys.readouterr().out
    assert "[FR18 fallback]" in out


def test_us_and_tsx_always_use_default_topic():
    assert notify._topic_for("US", "default-topic", "nse-topic") == "default-topic"
    assert notify._topic_for("TSX", "default-topic", "nse-topic") == "default-topic"


def test_unknown_market_uses_default_topic():
    assert notify._topic_for(None, "default-topic", "nse-topic") == "default-topic"


# --- FR13: alert title/body composition ----------------------------------------

def test_change_title_format():
    assert notify._title("AAPL", "Buy", "change") == "AAPL - Changed to Buy"


def test_candidate_title_format():
    assert notify._title("NEWCO", "Buy", "candidate") == "NEWCO - New candidate: Buy"


def test_body_prefixed_with_market_timestamp_and_clipped_to_max():
    body = notify._compose_body("A" * 300, "US")
    assert len(body) <= notify.NOTIF_BODY_MAX
    assert body.split(" · ")[0].endswith("ET")


# --- DryRunNotifier: end-to-end composition without any network call ---------

def test_dry_run_notifier_never_touches_network(capsys):
    n = notify.DryRunNotifier(topic="t1", nse_topic="t2")
    n.push("AAPL", "Buy", "strong breakout", kind="change", log_id="abc123", market="US")
    out = capsys.readouterr().out
    assert "[DRY RUN]" in out
    assert "AAPL" in out
    assert "abc123" in out


def test_get_notifier_returns_dry_run_when_alerts_disabled(monkeypatch):
    import config
    monkeypatch.setattr(config, "ALERTS_ENABLED", False)
    n = notify.get_notifier()
    assert isinstance(n, notify.DryRunNotifier)


def test_get_notifier_returns_dry_run_when_topic_unset(monkeypatch):
    import config
    monkeypatch.setattr(config, "ALERTS_ENABLED", True)
    monkeypatch.setattr(config, "NTFY_TOPIC", "")
    n = notify.get_notifier()
    assert isinstance(n, notify.DryRunNotifier)


def test_get_notifier_returns_real_notifier_when_enabled_and_topic_set(monkeypatch):
    import config
    monkeypatch.setattr(config, "ALERTS_ENABLED", True)
    monkeypatch.setattr(config, "NTFY_TOPIC", "real-topic")
    n = notify.get_notifier()
    assert isinstance(n, notify.NtfyNotifier)


# --- NtfyNotifier.push: network call fully mocked, never hits ntfy.sh --------

def test_ntfy_notifier_posts_to_correct_topic_url_mocked(monkeypatch):
    calls = []

    def fake_post(url, data=None, headers=None, timeout=None):
        calls.append(dict(url=url, data=data, headers=headers, timeout=timeout))
        class R:
            status_code = 200
        return R()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    n = notify.NtfyNotifier(topic="us-topic", detail_base="https://example.test/d", nse_topic="nse-topic")
    n.push("AAPL", "Sell", "reversal confirmed", kind="change", log_id="log-1", market="US")

    assert len(calls) == 1
    assert calls[0]["url"] == "https://ntfy.sh/us-topic"
    assert calls[0]["headers"]["Title"] == "AAPL - Changed to Sell"
    assert calls[0]["headers"]["Click"] == "https://example.test/d?log_id=log-1"


def test_ntfy_notifier_swallows_network_errors_without_crashing(monkeypatch, capsys):
    def fake_post(*a, **kw):
        raise ConnectionError("network down")

    monkeypatch.setattr(notify.requests, "post", fake_post)
    n = notify.NtfyNotifier(topic="us-topic")
    n.push("AAPL", "Sell", "reversal", kind="change", log_id="log-1", market="US")   # must not raise
    assert "[notify error]" in capsys.readouterr().out
