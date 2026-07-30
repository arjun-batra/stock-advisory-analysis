"""notify.py — pure alert-composition logic (FR12, FR13, FR18, FR23).

Only the pure functions and DryRunNotifier are exercised (no real network
call — NtfyNotifier.push is covered separately with requests.post mocked so
no test in this suite ever reaches ntfy.sh).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests as requests_module

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
            def raise_for_status(self):
                pass   # a real 2xx response: raise_for_status is a no-op
        return R()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    n = notify.NtfyNotifier(topic="us-topic", detail_base="https://example.test/d", nse_topic="nse-topic")
    result = n.push("AAPL", "Sell", "reversal confirmed", kind="change", log_id="log-1", market="US")

    # FR34/DEEP-002 (AC4): a genuine 2xx must report delivery as True, not just
    # "requests.post was called" -- the old mock (a bare status_code, no
    # raise_for_status) would have silently returned False here once push()
    # started calling raise_for_status(), and nothing would have noticed.
    assert result is True
    assert len(calls) == 1
    assert calls[0]["url"] == "https://ntfy.sh/us-topic"
    assert calls[0]["headers"]["Title"] == "AAPL - Changed to Sell"
    assert calls[0]["headers"]["Click"] == "https://example.test/d?log_id=log-1"


def test_ntfy_notifier_swallows_network_errors_without_crashing(monkeypatch, capsys):
    def fake_post(*a, **kw):
        raise ConnectionError("network down")

    monkeypatch.setattr(notify.requests, "post", fake_post)
    n = notify.NtfyNotifier(topic="us-topic")
    result = n.push("AAPL", "Sell", "reversal", kind="change", log_id="log-1", market="US")   # must not raise
    # FR34/DEEP-002 (AC4): a network exception must report False (not raise, not None).
    assert result is False
    out = capsys.readouterr().out
    assert "[notify] ERROR push failed for AAPL: ConnectionError: network down" in out


def test_ntfy_notifier_returns_false_without_raising_on_non_2xx_response(monkeypatch, capsys):
    """AC4's own explicit named test: mock requests.post to return a 500 and
    assert push() returns False without raising."""
    def fake_post(*a, **kw):
        class R:
            status_code = 500
            def raise_for_status(self):
                raise requests_module.HTTPError("500 Server Error")
        return R()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    n = notify.NtfyNotifier(topic="us-topic")
    result = n.push("AAPL", "Sell", "reversal", kind="change", log_id="log-1", market="US")   # must not raise

    assert result is False
    assert "[notify] ERROR push failed for AAPL" in capsys.readouterr().out


def test_dry_run_notifier_push_returns_none_explicitly():
    """AC4: DryRunNotifier.push() returns None unconditionally -- a third,
    explicit state distinct from True (delivered) and False (failed)."""
    n = notify.DryRunNotifier(topic="t1")
    result = n.push("AAPL", "Buy", "breakout", kind="change", log_id="abc", market="US")
    assert result is None
