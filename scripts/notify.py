"""Notification dispatch (solution design 4.6).

Provider-agnostic behind a tiny interface so the rest of the pipeline doesn't
care which service sends the push. Phase 2 uses the DryRunNotifier — the change
logic runs and logs, but nothing is actually sent. Phase 3 flips ALERTS_ENABLED
=true and a real ntfy topic in, and the same call sites start pushing for real.

Each push carries a single market-matched timestamp (FR23): ET for US/TSX,
IST for NSE — formatted server-side here, since the device timezone isn't
available at send time.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import config

NOTIF_BODY_MAX = 150   # keep the push preview tidy; the full reason is on the detail page

# FR23: each market's alerts are stamped in that market's own timezone. US/TSX
# share ET; NSE uses IST (no DST). Unknown/missing market falls back to ET.
_MARKET_TZ = {
    "US":  ("America/New_York", "ET"),
    "TSX": ("America/New_York", "ET"),
    "NSE": ("Asia/Kolkata", "IST"),
}


def _market_timestamp(market: str | None) -> str:
    """Current wall-clock in the alert market's timezone, e.g. '10:30 AM ET'."""
    tzname, label = _MARKET_TZ.get((market or "").upper(), ("America/New_York", "ET"))
    now = datetime.now(ZoneInfo(tzname))
    return now.strftime("%-I:%M %p ") + label


def _clip_body(text: str, limit: int = NOTIF_BODY_MAX) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-") + "\u2026"


def _title(ticker: str, verdict: str, kind: str) -> str:
    if kind == "change":
        return f"{ticker} - Changed to {verdict}"
    return f"{ticker} - New candidate: {verdict}"   # Phase 4 discovery


def _compose_body(rationale: str, market: str | None) -> str:
    """Body = market-matched timestamp (FR23) + the rationale, clipped to fit."""
    prefix = f"{_market_timestamp(market)} \u00b7 "
    return prefix + _clip_body(rationale, NOTIF_BODY_MAX - len(prefix))


class DryRunNotifier:
    """Logs what it *would* send. Used in Phase 2 (no alerting yet)."""

    def push(self, ticker, verdict, rationale, *, kind, log_id, market=None):
        print(f"[DRY RUN] would push [{kind}] {_title(ticker, verdict, kind)} :: {_compose_body(rationale, market)} (log {log_id})")


class NtfyNotifier:
    def __init__(self, topic: str, detail_base: str = ""):
        self.topic = topic
        self.detail_base = detail_base

    def push(self, ticker, verdict, rationale, *, kind, log_id, market=None):
        headers = {"Title": _title(ticker, verdict, kind)}
        if self.detail_base and log_id:
            headers["Click"] = f"{self.detail_base}?log_id={log_id}"
        try:
            requests.post(f"https://ntfy.sh/{self.topic}",
                          data=_compose_body(rationale, market).encode("utf-8"), headers=headers, timeout=10)
        except Exception as e:
            print(f"[notify error] {ticker}: {type(e).__name__}: {e}")


def get_notifier():
    if config.ALERTS_ENABLED and config.NTFY_TOPIC:
        return NtfyNotifier(config.NTFY_TOPIC, config.DETAIL_PAGE_BASE)
    return DryRunNotifier()
