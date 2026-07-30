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

from collections import Counter
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
    # Per-region heartbeat key (NFR2; 2026-07-03 review gap 2). The two regional
    # runs previously shared one 'daily-discovery' key, so the monitor could only
    # validate the 22:00 UTC NA run — a silently-dead NSE dispatch never alerted,
    # and its heartbeat evidence was overwritten by the NA run the same day.
    # check_pipeline_health() now watches 'daily-discovery-in' in its own window.
    heartbeat_key = "daily-discovery" if region == "na" else f"daily-discovery-{region}"

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
        if screens_errored or config.TUNABLES_DEGRADED:
            state.write_heartbeat(sb, heartbeat_key, "partial")
            print(f"Done [partial]. 0 candidates but {screens_errored}/{screens_attempted} "
                  f"screens errored — treat as screener failure, NOT a quiet day.")
        else:
            state.write_heartbeat(sb, heartbeat_key, "ok")
            print("Done [ok]. No candidates today (all screens ran, nothing passed gates).")
        return

    recently = state.recently_pushed_candidates(sb, config.DISCOVERY_PUSH_COOLDOWN_DAYS)
    outcomes = Counter()

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
                # Skip-with-log, same as the hourly loop (FR15): a candidate that
                # passed the screen but failed ingest still leaves a track-record row.
                state.log_skip(sb, c["ticker"], data["notes"],
                               rate_limited=data.get("rate_limited", False),
                               label="new-candidate")
                outcomes["skip"] += 1
                continue
            data["discovery_signals"] = c["signals"]   # carried into the stored snapshot
            items.append((c, data))
        except Exception as e:
            print(f"  ERROR {c['ticker']} (ingest): {type(e).__name__}: {e}")
            outcomes["error"] += 1

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
            print(f"  {ticker:9} {ai['verdict']:4} ({ai.get('confidence') or '-'}) -> {result} "
                  f"[{ai['parse_status']}/{ai.get('model_used', '?')}] {'+'.join(c['signals'])}")
            outcomes[result] += 1
        except Exception as e:
            print(f"  ERROR {ticker}: {type(e).__name__}: {e}")
            outcomes["error"] += 1

    # DEEP-001/DEEP-002 fix (INC-8, components.md §4.8): "no-read" (fail-safe
    # Hold from a parse/API failure) and "candidate-push-failed" (a real,
    # confirmed push failure) both count as degraded — see run_hourly.py's
    # equivalent formula for the identical NFR2/Decision #31 rationale.
    degraded = outcomes["skip"] + outcomes["error"] + screens_errored + outcomes["no-read"] + outcomes["candidate-push-failed"]
    status = "partial" if (degraded or config.TUNABLES_DEGRADED) else "ok"
    state.write_heartbeat(sb, heartbeat_key, status)
    print(f"Done [{status}]. {dict(outcomes)}"
          + (f" ({screens_errored}/{screens_attempted} screens errored)" if screens_errored else ""))


if __name__ == "__main__":
    main()
