"""Notification dispatch (solution design 4.6).

Provider-agnostic behind a tiny interface so the rest of the pipeline doesn't
care which service sends the push. Phase 2 uses the DryRunNotifier — the
change/reminder logic runs and logs, but nothing is actually sent. Phase 3 flips
ALERTS_ENABLED=true and a real ntfy topic in, and the same call sites start
pushing for real.
"""

import requests

import config


def _title(ticker: str, verdict: str, kind: str) -> str:
    if kind == "change":
        return f"{ticker} - Changed to {verdict}"
    if kind == "reminder":
        return f"{ticker} - Still {verdict}"
    return f"{ticker} - New candidate: {verdict}"   # Phase 4 discovery


class DryRunNotifier:
    """Logs what it *would* send. Used in Phase 2 (no alerting yet)."""

    def push(self, ticker, verdict, rationale, *, kind, log_id):
        print(f"[DRY RUN] would push [{kind}] {_title(ticker, verdict, kind)} :: {rationale} (log {log_id})")


class NtfyNotifier:
    def __init__(self, topic: str, detail_base: str = ""):
        self.topic = topic
        self.detail_base = detail_base

    def push(self, ticker, verdict, rationale, *, kind, log_id):
        headers = {"Title": _title(ticker, verdict, kind)}
        if self.detail_base and log_id:
            headers["Click"] = f"{self.detail_base}?log_id={log_id}"
        try:
            requests.post(f"https://ntfy.sh/{self.topic}",
                          data=rationale.encode("utf-8"), headers=headers, timeout=10)
        except Exception as e:
            print(f"[notify error] {ticker}: {type(e).__name__}: {e}")


def get_notifier():
    if config.ALERTS_ENABLED and config.NTFY_TOPIC:
        return NtfyNotifier(config.NTFY_TOPIC, config.DETAIL_PAGE_BASE)
    return DryRunNotifier()
