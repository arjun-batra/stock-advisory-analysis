"""State & persistence + the core decision logic (solution design 5, 6.3).

Holds the Supabase reads/writes and the change / cooldown / standing-reminder
state machine. Every check writes a call_log row (FR15, v4) — quiet rows carry
alerted=false / alert_type=null. In Phase 2 the notifier is a dry-run stub, so
the logic runs and logs but nothing is actually pushed.
"""

from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

import config


def client() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_SECRET_KEY)


# --- reads -------------------------------------------------------------------

def get_watchlist(sb: Client) -> list[dict]:
    return sb.table("watchlist").select("*").execute().data or []


def get_holdings_map(sb: Client) -> dict:
    rows = sb.table("holdings").select("*").execute().data or []
    return {r["ticker"]: r for r in rows}


def get_verdict_state(sb: Client, ticker: str) -> dict | None:
    rows = sb.table("verdict_state").select("*").eq("ticker", ticker).limit(1).execute().data
    return rows[0] if rows else None


# --- writes ------------------------------------------------------------------

def write_call_log(sb, *, ticker, verdict, rationale, label, alert_type, alerted, snapshot) -> str:
    row = {
        "ticker": ticker, "verdict": verdict, "rationale": rationale,
        "label": label, "alert_type": alert_type, "alerted": alerted,
        "data_snapshot": snapshot,
    }
    res = sb.table("call_log").insert(row).execute()
    return (res.data or [{}])[0].get("id", "")


def _upsert_state(sb: Client, ticker: str, fields: dict) -> None:
    sb.table("verdict_state").upsert({"ticker": ticker, **fields}).execute()


def write_heartbeat(sb: Client, workflow: str, status: str) -> None:
    sb.table("run_heartbeat").upsert({
        "workflow_name": workflow,
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
    }).execute()


def log_skip(sb, ticker: str, notes: list[str], *, rate_limited: bool = False) -> None:
    """Write a minimal call_log row for a ticker skipped in ingestion.

    Previously a skip was console-only (issue #1), so a missed ticker left no
    trace in Supabase. This writes a quiet, non-alerting row (alerted=false,
    alert_type=null) with parse_status="no_data" so missed cycles are queryable
    in the track record. verdict_state is deliberately NOT touched — a skip is
    "no reading this cycle," never a verdict.
    """
    snap = {
        "parse_status": "no_data",
        "rate_limited": rate_limited,
        "notes": notes,
    }
    write_call_log(sb, ticker=ticker, verdict="Hold",
                   rationale="; ".join(notes) or "No usable market data; skipped this cycle.",
                   label="watchlist", alert_type=None, alerted=False, snapshot=snap)


# --- helpers -----------------------------------------------------------------

def build_position(holding: dict | None, data: dict) -> dict | None:
    if not holding:
        return None
    cost = holding.get("cost_basis") or 0
    price = data.get("price") or 0
    pl_pct = round((price / cost - 1) * 100, 2) if cost else None
    return {
        "shares": holding.get("shares"),
        "cost_basis": cost,
        "currency": holding.get("currency"),
        "pl_pct": pl_pct,
    }


def _snapshot(data: dict, ai: dict) -> dict:
    return {
        "price": data.get("price"),
        "pct_change_1d": data.get("pct_change_1d"),
        "pct_change_5d": data.get("pct_change_5d"),
        "pct_change_20d": data.get("pct_change_20d"),
        "volume_vs_avg": data.get("volume_vs_avg"),
        "fundamentals": data.get("fundamentals", {}),
        "headlines": data.get("headlines", []),
        "raw_model_response": ai.get("raw_model_response"),
        "parse_status": ai.get("parse_status"),
        "model_used": ai.get("model_used"),
    }


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


# --- the state machine (design 6.3) ------------------------------------------

def process_ticker(sb, notifier, wl_row, data, ai, now: datetime) -> str:
    """Run one watchlist ticker through the change/cooldown/reminder logic.

    Returns a short label of what happened, for the run log.
    """
    ticker = wl_row["ticker"]
    verdict = ai["verdict"]
    rationale = ai["rationale"]
    snap = _snapshot(data, ai)
    cooldown = timedelta(hours=config.COOLDOWN_HOURS)
    interval = timedelta(days=config.REMINDER_INTERVAL_DAYS)

    state = get_verdict_state(sb, ticker)

    # ---- non-reading: rate-limited (api_error) or unparseable (failed). The
    #      "Hold" here is a fail-safe placeholder, NOT a real verdict, so never
    #      let it advance current_verdict or fire a (spurious) change alert. Log
    #      the row for the audit trail (FR15); only touch last_checked_at. ----
    if ai.get("parse_status") in ("failed", "api_error"):
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="watchlist", alert_type=None, alerted=False, snapshot=snap)
        if state is not None:
            _upsert_state(sb, ticker, {"last_checked_at": now.isoformat()})
        return "no-read"

    # ---- cold start ----
    if state is None:
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="watchlist", alert_type=None, alerted=False, snapshot=snap)
        _upsert_state(sb, ticker, {
            "current_verdict": verdict, "last_alert_verdict": None,
            "last_alert_at": None,
            "reminder_due_at": (now + interval).isoformat(),
            "last_checked_at": now.isoformat(),
        })
        return "cold-start"

    last_alert_at = _parse_dt(state.get("last_alert_at"))
    reminder_due_at = _parse_dt(state.get("reminder_due_at"))

    # ---- CASE 1: verdict changed ----
    if verdict != state.get("current_verdict"):
        in_cooldown = last_alert_at is not None and (now - last_alert_at) < cooldown
        if in_cooldown:
            # suppressed: log but don't push; still advance current_verdict
            write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                           label="watchlist", alert_type=None, alerted=False, snapshot=snap)
            _upsert_state(sb, ticker, {"current_verdict": verdict, "last_checked_at": now.isoformat()})
            return "change-suppressed"

        log_id = write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                                label="watchlist", alert_type="change", alerted=True, snapshot=snap)
        notifier.push(ticker, verdict, rationale, kind="change", log_id=log_id)
        _upsert_state(sb, ticker, {
            "current_verdict": verdict, "last_alert_verdict": verdict,
            "last_alert_at": now.isoformat(),
            "reminder_due_at": (now + interval).isoformat(),
            "last_checked_at": now.isoformat(),
        })
        return "change-alert"

    # ---- CASE 2: unchanged, standing Buy/Sell, reminder due ----
    if verdict in ("Buy", "Sell") and reminder_due_at is not None and now >= reminder_due_at:
        log_id = write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                                label="watchlist", alert_type="reminder", alerted=True, snapshot=snap)
        notifier.push(ticker, verdict, rationale, kind="reminder", log_id=log_id)
        _upsert_state(sb, ticker, {
            "last_alert_at": now.isoformat(),
            "reminder_due_at": (now + interval).isoformat(),
            "last_checked_at": now.isoformat(),
        })
        return "reminder"

    # ---- unchanged Hold, or not-yet-due: log quietly ----
    write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                   label="watchlist", alert_type=None, alerted=False, snapshot=snap)
    _upsert_state(sb, ticker, {"last_checked_at": now.isoformat()})
    return "quiet"
