"""State & persistence + the core decision logic (solution design 5, 6.3).

Holds the Supabase reads/writes and the single-rule change state machine: any
verdict change -> immediate alert, no change -> silence (issue #11). Every check
writes a call_log row (FR15) — quiet rows carry alerted=false / alert_type=null.
"""

from datetime import datetime, timedelta, timezone
import uuid

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

def write_call_log(sb, *, id=None, ticker, verdict, rationale, label, alert_type, alerted, snapshot) -> str:
    """`id`, when supplied, is a client-generated uuid (str(uuid.uuid4())) written
    into the row rather than left to the table's `gen_random_uuid()` default.
    This lets a caller know the row's id BEFORE the insert — needed so the same
    id can be handed to notify.push() (for the tap-through URL) and to this
    write in the same call, removing the old ordering assumption that the log
    row had to exist before the push (components.md §4.6, FR34/DEEP-002)."""
    row = {
        "ticker": ticker, "verdict": verdict, "rationale": rationale,
        "label": label, "alert_type": alert_type, "alerted": alerted,
        "data_snapshot": snapshot,
    }
    if id is not None:
        row["id"] = id
    res = sb.table("call_log").insert(row).execute()
    return (res.data or [{}])[0].get("id", id or "")


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


def log_skip(sb, ticker: str, notes: list[str], *, rate_limited: bool = False,
             label: str = "watchlist") -> None:
    """Write a minimal call_log row for a ticker skipped in ingestion.

    Previously a skip was console-only (issue #1), so a missed ticker left no
    trace in Supabase. This writes a quiet, non-alerting row (alerted=false,
    alert_type=null) with parse_status="no_data" so missed cycles are queryable
    in the track record. verdict_state is deliberately NOT touched — a skip is
    "no reading this cycle," never a verdict. Discovery passes
    label="new-candidate" so a screened candidate that failed ingest leaves a
    trace too (FR15 posture; 2026-07-03 review gap 6) — discovery never touches
    verdict_state anyway, so nothing else changes.
    """
    snap = {
        "parse_status": "no_data",
        "rate_limited": rate_limited,
        "notes": notes,
    }
    write_call_log(sb, ticker=ticker, verdict="Hold",
                   rationale="; ".join(notes) or "No usable market data; skipped this cycle.",
                   label=label, alert_type=None, alerted=False, snapshot=snap)


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

    Delivery-confirmed contract (FR34/DEEP-002, components.md §4.6): `alerted`
    is written True only on a confirmed push (`delivered is True`); a failed or
    dry-run (`None`) push writes `alerted=False`. This is what makes
    `recently_pushed_candidates()`'s `alerted=True` filter (Decision #32) no
    longer falsely dedupe an undelivered candidate for the cooldown window.
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
    if not do_push:
        write_call_log(sb, ticker=ticker, verdict=verdict, rationale=rationale,
                       label="new-candidate", alert_type=None, alerted=False, snapshot=snap)
        return "candidate-logged"

    log_id = str(uuid.uuid4())
    delivered = notifier.push(ticker, verdict, rationale, kind="candidate", log_id=log_id, market=data.get("market"))
    write_call_log(sb, id=log_id, ticker=ticker, verdict=verdict, rationale=rationale,
                   label="new-candidate", alert_type=None, alerted=(delivered is True), snapshot=snap)
    if delivered is False:
        return "candidate-push-failed"
    return "candidate-pushed"


# --- helpers -----------------------------------------------------------------

def build_position(holding: dict | None, data: dict) -> dict | None:
    """FR11/FR29 (Decision #35, DEEP-006): defense-in-depth on top of the
    holdings.currency DB trigger (sql/holdings_currency_derivation.sql), which
    guarantees holdings.currency agrees with watchlist.market but not that
    watchlist.market is itself correct for the ticker's actual listing (a
    narrower, residual risk). If the holding's currency disagrees with the
    ticker's own independently-fetched fundamentals currency, pl_pct is
    suppressed rather than computed from mismatched currencies -- FR11's
    explicit requirement (non-functional-ops.md §7.3). A missing fundamentals
    currency (Yahoo didn't return one) is "unknown", not "disagrees" -- pl_pct
    is still computed in that case, unchanged from pre-INC-10 behavior.

    `currency_mismatched` is exposed on the returned dict (REV-113, INC-10
    fix round #2) so `ai_judge._ticker_block` -- the only other consumer that
    needs to know about the mismatch -- can also withhold the raw cost-basis/
    price figures from the prompt, without re-deriving this same condition a
    second time.
    """
    if not holding:
        return None
    cost = holding.get("cost_basis") or 0
    price = data.get("price") or 0
    currency = holding.get("currency")
    fundamentals_currency = (data.get("fundamentals") or {}).get("currency")
    mismatched = bool(fundamentals_currency and currency and fundamentals_currency != currency)
    if mismatched:
        print(f"  [state] WARNING holding currency mismatch for {data.get('ticker')}: "
              f"holdings.currency={currency!r} vs fundamentals.currency={fundamentals_currency!r} "
              f"(watchlist.market likely wrong for this ticker) — suppressing pl_pct per FR11")
        pl_pct = None
    else:
        pl_pct = round((price / cost - 1) * 100, 2) if cost else None
    return {
        "shares": holding.get("shares"),
        "cost_basis": cost,
        "currency": currency,
        "pl_pct": pl_pct,
        "currency_mismatched": mismatched,
    }


def _snapshot(data: dict, ai: dict, position: dict | None = None) -> dict:
    snap = {
        # Market ("US"/"TSX"/"NSE") anchors the detail page's currency symbol and
        # market badge (SD §4.7, UI-handoff v3). Populated from ingest's
        # _market_for(ticker); detail.html's ticker-suffix/fundamentals-currency
        # fallbacks are now a legacy-row safety net, not the live mechanism (#31).
        "market": data.get("market"),
        "price": data.get("price"),
        "pct_change_1d": data.get("pct_change_1d"),
        "pct_change_5d": data.get("pct_change_5d"),
        "pct_change_20d": data.get("pct_change_20d"),
        "volume_vs_avg": data.get("volume_vs_avg"),
        # Session context for the price/volume fields above: session_live=true
        # means `price` was a LIVE mid-session price (not a settled close) and
        # volume_pro_rated=true means volume_vs_avg was scaled up for the
        # elapsed session fraction. The detail page labels both accordingly.
        "session_live": data.get("session_live", False),
        "volume_pro_rated": data.get("volume_pro_rated", False),
        "fundamentals": data.get("fundamentals", {}),
        "headlines": data.get("headlines", []),
        "raw_model_response": ai.get("raw_model_response"),
        # Model's self-rated confidence in the verdict (high/medium/low; null on
        # fail-safes). Stored for tuning — e.g. a future gate pushing only
        # high-confidence discovery Buys.
        "confidence": ai.get("confidence"),
        "parse_status": ai.get("parse_status"),
        "model_used": ai.get("model_used"),
        # Token counts for THIS Gemini call. For the watchlist/discovery batch
        # it's one API call, so this total is the batch total and is identical on
        # every row of the run — aggregate it once per run, not summed per row.
        "tokens": ai.get("usage"),
        # Real error of any model we fell back from (e.g. a 3.5-flash timeout
        # before lite answered); null on a clean primary success.
        "fallback_from": ai.get("fallback_from"),
        # Transport retries (503/504/429/timeout, ai_judge._generate) burned to
        # get this result. 0 = first-attempt success; like `tokens`, the count
        # is per BATCH call, so it repeats on every row of the run. Null only
        # on rows that never reached the AI call (skips, missing_verdict).
        "retry_count": ai.get("retry_count"),
        "discovery_signals": data.get("discovery_signals"),
    }
    # Held-position context (FR2/FR11) so the detail page can render the
    # "Your position" block. Omitted entirely for watch-only tickers (position
    # is None) — no empty block. Current price is read from snap.price.
    if position:
        snap["position"] = position
    return snap


# --- the state machine (design 6.3) ------------------------------------------

def process_ticker(sb, notifier, wl_row, data, ai, now: datetime, position: dict | None = None) -> str:
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
    snap = _snapshot(data, ai, position)

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

    # ---- change -> immediate alert, no cooldown; delivery-gated state advance
    #      (FR34/DEEP-002, components.md §4.6). log_id is generated client-side
    #      BEFORE the push so it can be passed into both push() (tap-through
    #      URL) and this write_call_log() call, instead of the old order that
    #      let alerted get written before the outcome was known. ----
    log_id = str(uuid.uuid4())
    delivered = notifier.push(ticker, verdict, rationale, kind="change", log_id=log_id, market=wl_row.get("market"))
    write_call_log(sb, id=log_id, ticker=ticker, verdict=verdict, rationale=rationale,
                   label="watchlist", alert_type="change", alerted=(delivered is True), snapshot=snap)
    if delivered is False:
        # Real, confirmed failure: the crossing stays pending. current_verdict
        # is NOT advanced, so the next cycle re-evaluates the same new AI
        # verdict against the still-unadvanced prior verdict and retries the
        # push automatically (FR34's literal retry contract) — not a new
        # cooldown/reminder mechanism, just the single-rule comparison not yet
        # having been told the first attempt succeeded.
        _update_state(sb, ticker, {"last_checked_at": now.isoformat()})
        return "push-failed"
    # delivered is True (real success) or None (dry run) -> crossing consumed
    # either way. A dry run is a deliberate, expected non-send; not advancing
    # on it would let a verdict backlog build up silently while
    # ALERTS_ENABLED=false and dump all at once the moment it flips back on.
    _update_state(sb, ticker, {
        "current_verdict": verdict,
        "last_checked_at": now.isoformat(),
    })
    return "change-alert"
