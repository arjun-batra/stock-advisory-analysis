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
from textutil import clip

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


def _title(ticker: str, verdict: str, kind: str) -> str:
    if kind == "change":
        return f"{ticker} - Changed to {verdict}"
    return f"{ticker} - New candidate: {verdict}"   # Phase 4 discovery


def _compose_body(rationale: str, market: str | None) -> str:
    """Body = market-matched timestamp (FR23) + the rationale, clipped to fit."""
    prefix = f"{_market_timestamp(market)} \u00b7 "
    return prefix + clip(rationale, NOTIF_BODY_MAX - len(prefix))


def _topic_for(market: str | None, default_topic: str, nse_topic: str) -> str:
    """FR18 / design §12 D7 — route by market at send time. NSE goes to its own
    topic so India and US/TSX alerts can be filtered/muted independently; if the
    NSE topic isn't provisioned yet, fall back to the default so no alert drops.
    """
    if (market or "").upper() == "NSE" and nse_topic:
        return nse_topic
    return default_topic


class DryRunNotifier:
    """Logs what it *would* send, including the topic it would route to. Used in
    Phase 2 (no alerting yet) and whenever ALERTS_ENABLED/NTFY_TOPIC are unset."""

    def __init__(self, topic: str = "", nse_topic: str = ""):
        self.topic = topic
        self.nse_topic = nse_topic

    def push(self, ticker, verdict, rationale, *, kind, log_id, market=None):
        topic = _topic_for(market, self.topic, self.nse_topic) or "(no topic set)"
        print(f"[DRY RUN] would push [{kind}] -> topic '{topic}' :: "
              f"{_title(ticker, verdict, kind)} :: {_compose_body(rationale, market)} (log {log_id})")


class NtfyNotifier:
    def __init__(self, topic: str, detail_base: str = "", nse_topic: str = ""):
        self.topic = topic
        self.nse_topic = nse_topic
        self.detail_base = detail_base

    def push(self, ticker, verdict, rationale, *, kind, log_id, market=None):
        topic = _topic_for(market, self.topic, self.nse_topic)
        headers = {"Title": _title(ticker, verdict, kind)}
        if self.detail_base and log_id:
            headers["Click"] = f"{self.detail_base}?log_id={log_id}"
        try:
            requests.post(f"https://ntfy.sh/{topic}",
                          data=_compose_body(rationale, market).encode("utf-8"), headers=headers, timeout=10)
        except Exception as e:
            print(f"[notify error] {ticker}: {type(e).__name__}: {e}")


def get_notifier():
    if config.ALERTS_ENABLED and config.NTFY_TOPIC:
        return NtfyNotifier(config.NTFY_TOPIC, config.DETAIL_PAGE_BASE, config.NSE_NTFY_TOPIC)
    return DryRunNotifier(config.NTFY_TOPIC, config.NSE_NTFY_TOPIC)
