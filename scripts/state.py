"""State & persistence + the core decision logic (solution design 5, 6.3).

Holds the Supabase reads/writes and the single-rule change state machine: any
verdict change -> immediate alert, no change -> silence (issue #11). Every check
writes a call_log row (FR15) — quiet rows carry alerted=false / alert_type=null.
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


def _insert_state(sb: Client, ticker: str, fields: dict) -> None:
    """Cold-start only — INSERT a fresh verdict_state row (all fields supplied)."""
    sb.table("verdict_state").upsert({"ticker": ticker, **fields}).execute()


def _update_state(sb: Client, ticker: str, fields: dict) -> None:
    """Partial UPDATE on an existing row (issue #3).

    The old single _upsert_state was used for both INSERT and partial UPDATE.
    On a partial field set, PostgREST's upsert emits ON CONFLICT DO UPDATE SET
    across ALL columns, nulling any column not supplied — which violated the
    NOT NULL on current_verdict and broke every quiet/no-read row. A real UPDATE
    touches only the supplied columns, leaving current_verdict intact.
    """
    sb.table("verdict_state").update(fields).eq("ticker", ticker).execute()


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


# --- discovery (Phase 4) -----------------------------------------------------

def get_watchlist_tickers(sb: Client) -> set[str]:
    """Uppercased set of watchlist tickers, to exclude from discovery up front."""
    return {r["ticker"].upper() for r in get_watchlist(sb)}


def recently_pushed_candidates(sb: Client, days: int) -> set[str]:
    """Tickers pushed as a new-candidate within the last `days` (7-day dedup).

    'log always, push conditionally' (design 4.3): a candidate logged again
    within the window is still written, but the push is suppressed.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = (sb.table("call_log").select("ticker")
            .eq("label", "new-candidate").eq("alerted", True)
            .gte("timestamp", since).execute().data or [])
    return {r["ticker"].upper() for r in rows}


def process_candidate(sb, notifier, data, ai, *, push: bool) -> str:
    """Log a discovered candidate and push it (Buys only) if not deduped.

    Discovery never touches verdict_state — candidates aren't watchlist members
    and have no change/cooldown/reminder lifecycle. A non-reading (rate-limited
    or unparseable) is logged but never pushed.
    """
    ticker = data["ticker"]
    verdict = ai["verdict"]
    rationale = ai["rationale"]
    snap = _snapshot(data, ai)

    if ai.get("parse_status") in ("failed", "api_error"):
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="new-candidate", alert_type=None, alerted=False, snapshot=snap)
        return "no-read"

    do_push = push and verdict == "Buy"
    log_id = write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                            label="new-candidate", alert_type=None, alerted=do_push, snapshot=snap)
    if do_push:
        notifier.push(ticker, verdict, rationale, kind="candidate", log_id=log_id)
        return "candidate-pushed"
    return "candidate-logged"


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
        # Token counts for THIS Gemini call. For the watchlist/discovery batch
        # it's one API call, so this total is the batch total and is identical on
        # every row of the run — aggregate it once per run, not summed per row.
        "tokens": ai.get("usage"),
        # Real error of any model we fell back from (e.g. a 3.5-flash timeout
        # before lite answered); null on a clean primary success.
        "fallback_from": ai.get("fallback_from"),
        "discovery_signals": data.get("discovery_signals"),
    }


# --- the state machine (design 6.3) ------------------------------------------

def process_ticker(sb, notifier, wl_row, data, ai, now: datetime) -> str:
    """Run one watchlist ticker through the single-rule change logic (design 6.3).

    SINGLE RULE (issue #11): any verdict change -> immediate alert; no change ->
    silence. No cooldown, no debounce, no standing-verdict reminder. The cold
    start is the only special case, and it's a no-alert baseline, not an
    exception to the rule. The 24h cooldown, the post-cold-start bootstrap path,
    and FR7's 7-day reminder were all removed here (were: change-suppressed /
    bootstrap-alert / reminder). A standing Buy/Sell that never changes is now
    silent by design — the system signals on threshold *crossings*, not standing
    states (accepted, solution design 2 item 4).

    Returns a short label of what happened, for the run log.
    """
    ticker = wl_row["ticker"]
    verdict = ai["verdict"]
    rationale = ai["rationale"]
    snap = _snapshot(data, ai)

    state = get_verdict_state(sb, ticker)

    # ---- non-reading: rate-limited (api_error) or unparseable (failed). The
    #      "Hold" here is a fail-safe placeholder, NOT a real verdict, so never
    #      let it advance current_verdict or fire a (spurious) change alert. Log
    #      the row for the audit trail (FR15); only touch last_checked_at. This
    #      guard is load-bearing under the single rule: without it a fail-safe
    #      Hold could read as a real change -> Hold and fire a fabricated alert. ----
    if ai.get("parse_status") in ("failed", "api_error"):
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="watchlist", alert_type=None, alerted=False, snapshot=snap)
        if state is not None:
            _update_state(sb, ticker, {"last_checked_at": now.isoformat()})
        return "no-read"

    # ---- cold start: establish the baseline silently (avoids a go-live dump) ----
    if state is None:
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="watchlist", alert_type=None, alerted=False, snapshot=snap)
        _insert_state(sb, ticker, {
            "current_verdict": verdict,
            "last_checked_at": now.isoformat(),
        })
        return "cold-start"

    # ---- no change -> silence (still logged for the track record, FR15) ----
    if verdict == state.get("current_verdict"):
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="watchlist", alert_type=None, alerted=False, snapshot=snap)
        _update_state(sb, ticker, {"last_checked_at": now.isoformat()})
        return "quiet"

    # ---- change -> immediate alert, no cooldown ----
    log_id = write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                            label="watchlist", alert_type="change", alerted=True, snapshot=snap)
    notifier.push(ticker, verdict, rationale, kind="change", log_id=log_id)
    _update_state(sb, ticker, {
        "current_verdict": verdict,
        "last_checked_at": now.isoformat(),
    })
    return "change-alert"
