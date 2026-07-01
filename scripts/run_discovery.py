"""Daily discovery orchestrator (Phase 4, solution design 6.2).

Reactive movers: screen the market for the day's movers/volume (US + Canada),
shortlist the quality-gated survivors, run the SAME full ingest + ONE batched AI
call as the watchlist — but on discovery's own 2.5 models, which draw from a
separate Gemini free-tier quota bucket so discovery can't eat into the
watchlist's allowance. Push Buys only, labeled "new candidate", with a 7-day
per-ticker push cooldown ("log always, push conditionally", design 4.3).

Runs once daily after close — deliberately NOT gated on market-open (it uses the
last close). Writes its own run_heartbeat row ("daily-discovery"). Phase 2-style
dry run until ALERTS_ENABLED is flipped on.
"""

import os
import time

import config
import ingest
import ai_judge
import prefilter
import state
import notify


def main() -> None:
    config.require_secrets()
    sb = state.client()
    notifier = notify.get_notifier()

    # Region selects the market set (Phase 6 D5): "na" = US + Canada (the 22:00 UTC
    # post-US-close dispatch); "in" = India NSE (a separate NSE-close-timed dispatch,
    # ~10:00 UTC / 15:30 IST). Defaults to "na" so the existing dispatch is unchanged.
    region = (os.environ.get("DISCOVERY_REGION", "na") or "na").lower()

    watchlist = state.get_watchlist_tickers(sb)
    candidates, screens_attempted, screens_errored, funnel = prefilter.find_candidates(
        exclude=watchlist, region=region)
    print(f"Discovery [{region}]: {len(candidates)} candidates after screen+gate "
          f"({screens_attempted - screens_errored}/{screens_attempted} screens ok, "
          f"{screens_errored} errored; alerts={'ON' if config.ALERTS_ENABLED else 'DRY-RUN'})")
    # Funnel breakdown (issue #8): makes a zero-candidate day diagnosable —
    # which stage zeroed out tells you whether to tune the quality gates or the
    # signal thresholds (or whether it's a genuinely quiet market).
    print(f"  funnel: raw={funnel['raw']} -> dedup/in-scope={funnel['after_dedup']} "
          f"-> passed_quality={funnel['passed_quality']} -> tripped_signal={funnel['passed_signal']}")

    if not candidates:
        # Distinguish a genuine quiet day (all screens ran, nothing passed gates)
        # from a silent screener failure (screens errored) — the latter must not
        # report a clean 'ok' (issue #2 principle applied to discovery).
        if screens_errored:
            state.write_heartbeat(sb, "daily-discovery", "partial")
            print(f"Done [partial]. 0 candidates but {screens_errored}/{screens_attempted} "
                  f"screens errored — treat as screener failure, NOT a quiet day.")
        else:
            state.write_heartbeat(sb, "daily-discovery", "ok")
            print("Done [ok]. No candidates today (all screens ran, nothing passed gates).")
        return

    recently = state.recently_pushed_candidates(sb, config.DISCOVERY_PUSH_COOLDOWN_DAYS)
    outcomes = {}

    # --- ingest the shortlist (full per-ticker data, paced like the hourly loop) ---
    items = []   # list of (candidate, data)
    for i, c in enumerate(candidates):
        if i > 0:
            time.sleep(config.YF_PACING_SECONDS)
        try:
            data = ingest.get_market_data(c["ticker"])
            if not data["has_price"]:
                reason = "rate-limited" if data.get("rate_limited") else "no data"
                print(f"  skip {c['ticker']} ({reason})")
                outcomes["skip"] = outcomes.get("skip", 0) + 1
                continue
            data["discovery_signals"] = c["signals"]   # carried into the stored snapshot
            items.append((c, data))
        except Exception as e:
            print(f"  ERROR {c['ticker']} (ingest): {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1

    # --- ONE batched AI call, on discovery's own models ---
    verdicts = ai_judge.judge_batch(
        [{"data": d, "position": None} for (_, d) in items],
        models=config.discovery_models(),
    )

    # --- log every candidate; push Buys that aren't within the 7-day cooldown ---
    for c, data in items:
        ticker = c["ticker"]
        try:
            ai = verdicts.get(ticker) or ai_judge.missing_verdict("candidate")
            push = ticker not in recently
            result = state.process_candidate(sb, notifier, data, ai, push=push)
            print(f"  {ticker:9} {ai['verdict']:4} -> {result} "
                  f"[{ai['parse_status']}/{ai.get('model_used', '?')}] {'+'.join(c['signals'])}")
            outcomes[result] = outcomes.get(result, 0) + 1
        except Exception as e:
            print(f"  ERROR {ticker}: {type(e).__name__}: {e}")
            outcomes["error"] = outcomes.get("error", 0) + 1

    degraded = outcomes.get("skip", 0) + outcomes.get("error", 0) + screens_errored
    status = "partial" if degraded else "ok"
    state.write_heartbeat(sb, "daily-discovery", status)
    print(f"Done [{status}]. {dict(outcomes)}"
          + (f" ({screens_errored}/{screens_attempted} screens errored)" if screens_errored else ""))


if __name__ == "__main__":
    main()
