"""Hourly watchlist orchestrator (solution design 6.1, §12 D2).

Wakes up and checks which market session is actually open right now — the US/TSX
session (NYSE/TSX share 9:30-16:00 ET) or the NSE session (9:15-15:30 IST) — then
filters the watchlist to that session's tickers, ingests them, makes ONE batched
AI call for the group (kept to a single call to stay under the Gemini free-tier
daily request cap), and walks the results through the single-rule change logic
(design 6.3).

The two sessions never overlap (a fixed IST offset vs a DST-aware ET window;
verified across both DST regimes in the Phase-6 config test), so in practice one
group runs per wake-up. The loop still handles each open group independently and
gives each its OWN batched call with its OWN model try-order, so the
single-batch-call-per-open-market model holds even in the impossible-overlap case.

The runtime gate — NOT the pg_cron schedule — is the authority on "is the market
open" (load-bearing decision #4); this applies to the NSE IST gate too. One bad
ticker is skipped-with-log and never takes down the run for the others. A single
shared "hourly-watchlist" heartbeat is written at the end so a missed run is
visible (NFR2), regardless of which session ran.
"""

from datetime import datetime, timezone
import time

import config
import ingest
import ai_judge
import state
import notify


def _sessions(now_et: datetime, now_ist: datetime) -> list[dict]:
    """The market sessions this orchestrator serves (design §12 D2).

    Each entry groups the watchlist markets that trade in one session, the
    runtime gate saying whether it's open now, and the AI model try-order for its
    batched call. NSE draws its own model pair (config.nse_models / §12 D3) so it
    pulls from a separate Gemini free-tier quota bucket and can't eat into the
    US/TSX watchlist allowance; passing models=None lets ai_judge fall back to
    config.GEMINI_MODEL / _BACKUP for the US/TSX group.
    """
    return [
        {"name": "US/TSX", "markets": {"US", "TSX"},
         "open": config.is_market_open(now_et), "models": None},
        {"name": "NSE", "markets": {"NSE"},
         "open": config.is_nse_open(now_ist), "models": config.nse_models()},
    ]


def _process_group(sb, notifier, rows, holdings, models, now, outcomes) -> None:
    """Ingest + ONE batched AI call + per-ticker change detection for one market
    group. Mutates `outcomes` in place with per-result tallies.
    """
    # --- Phase 1: ingest everything (yfinance only, no AI/quota cost) ---
    # Paced apart + backoff-retried inside ingest to avoid Yahoo rate-limiting
    # the back-to-back loop (issue #1).
    items = []   # list of (wl_row, data, position)
    for i, row in enumerate(rows):
        ticker = row["ticker"]
        if i > 0:
            time.sleep(config.YF_PACING_SECONDS)
        try:
            data = ingest.get_market_data(ticker)
            if not data["has_price"]:
                reason = "rate-limited" if data.get("rate_limited") else "no data"
                print(f"  skip {ticker} ({reason}): {'; '.join(data['notes'])}")  # skip-with-log (7.5)
                state.log_skip(sb, ticker, data["notes"], rate_limited=data.get("rate_limited", False))
                outcomes["skip"] = outcomes.get("skip", 0) + 1
                continue
            position = state.build_position(holdings.get(ticker), data)
            items.append((row, data, position))
        except Exception as e:
            print(f"  ERROR {ticker} (ingest): {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1

    if not items:
        return

    # --- Phase 2: ONE batched AI call for this group, with its own model order ---
    verdicts = ai_judge.judge_batch(
        [{"data": d, "position": p} for (_, d, p) in items], models=models)

    # --- Phase 3: per-ticker single-rule change detection + logging ---
    for row, data, position in items:
        ticker = row["ticker"]
        try:
            ai = verdicts.get(ticker) or ai_judge.missing_verdict("ticker")
            result = state.process_ticker(sb, notifier, row, data, ai, now, position)
            tag = "NEW" if data["is_new"] else ""
            print(f"  {ticker:9} {ai['verdict']:4} -> {result} "
                  f"[{ai['parse_status']}/{ai.get('model_used', '?')}] {tag}")
            outcomes[result] = outcomes.get(result, 0) + 1
        except Exception as e:
            print(f"  ERROR {ticker}: {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1


def main() -> None:
    now = datetime.now(timezone.utc)
    now_et = datetime.now(config.MARKET_TZ)
    now_ist = datetime.now(config.NSE_MARKET_TZ)

    sessions = _sessions(now_et, now_ist)
    open_sessions = [s for s in sessions if s["open"]]

    # Gate-decision audit line (issue #7), now per-market: which session (if any)
    # the runtime gate saw open, whether this was a FORCE_RUN, and whether alerts
    # are live. A FORCE_RUN with ALERTS_ENABLED=true fires REAL ntfy pushes
    # regardless of hours — this line is the trail that tells a deliberate
    # off-hours test push apart from a gate defect.
    if sum(bool(s["open"]) for s in sessions) > 1:
        # Sessions are designed never to overlap. If they ever do, say so loudly
        # and still process each group independently rather than silently drop one.
        print("[gate] WARNING: US/TSX and NSE both report open — sessions should "
              "never overlap. Processing each group independently.")
    open_names = ", ".join(s["name"] for s in open_sessions) or "none"
    print(f"[gate] open={open_names} force_run={config.FORCE_RUN} "
          f"alerts={'ON' if config.ALERTS_ENABLED else 'DRY-RUN'} "
          f"| {now:%Y-%m-%d %H:%M:%S} UTC / {now_et:%H:%M %Z} / {now_ist:%H:%M %Z}")

    if not open_sessions and not config.FORCE_RUN:
        print("All markets closed - no-op, exit. "
              "(workflow_dispatch with force_run=true overrides)")
        return

    # FORCE_RUN with everything closed: run EVERY group (test/backfill). When a
    # session is genuinely open, run only that one — the normal path.
    run_sessions = sessions if (not open_sessions and config.FORCE_RUN) else open_sessions
    if not open_sessions:
        print("FORCE_RUN: all markets closed, running every group against last close "
              "(test/backfill). NOTE: with ALERTS_ENABLED=true this sends REAL pushes - "
              "set it false for a silent test.")

    config.require_secrets()
    sb = state.client()
    notifier = notify.get_notifier()

    watchlist = state.get_watchlist(sb)
    holdings = state.get_holdings_map(sb)

    outcomes = {}
    for s in run_sessions:
        rows = [r for r in watchlist if (r.get("market") or "US") in s["markets"]]
        print(f"[{s['name']}] {len(rows)} tickers, "
              f"alerts={'ON' if config.ALERTS_ENABLED else 'DRY-RUN'}")
        _process_group(sb, notifier, rows, holdings, s["models"], now, outcomes)

    # Heartbeat reflects whether the run was fully clean (issue #2): "partial"
    # when any ticker was skipped or errored, "ok" only when all succeeded. One
    # shared "hourly-watchlist" key across both sessions (design §12 D4/D5) — the
    # monitor computes the right staleness window per session off this same key.
    degraded = outcomes.get("skip", 0) + outcomes.get("error", 0)
    status = "partial" if degraded else "ok"
    state.write_heartbeat(sb, "hourly-watchlist", status)
    print(f"Done [{status}]. {dict(outcomes)}")


if __name__ == "__main__":
    main()
