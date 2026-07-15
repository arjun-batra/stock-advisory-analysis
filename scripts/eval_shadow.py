"""Shared wallet-sim evaluation harness (design.md §17, FR31).

A committed, re-runnable, read-only report of simulated shadow-track wallet
performance vs. production's actual verdicts, over a date window, for either
shadow track (`--track us_ca` -> call_log_shadow, `--track nse` ->
call_log_shadow_nse). Replaces the never-built "wallet-sim recursive-CTE walk"
the migration comments referenced.

Usage:
    python3 scripts/eval_shadow.py --track us_ca
    python3 scripts/eval_shadow.py --track nse --since 2026-07-01 --until 2026-07-14
    python3 scripts/eval_shadow.py --track us_ca --output report.json

HARD GUARANTEE: this script never writes to any table -- SELECT only, via
state.client() (secret key). No .insert(/.update(/.upsert(/.delete( calls
anywhere in this file (grep-verifiable, design §17.3).
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import config
import state
import wallet_sim

TRACKS = {"us_ca": "call_log_shadow", "nse": "call_log_shadow_nse"}
VERDICTS = ("Buy", "Sell", "Hold")


# --- pure: window/report computation (no I/O) --------------------------------

def default_window(now: datetime, days: int) -> tuple[str, str]:
    """[since, until] ISO strings covering the last `days` days ending now."""
    since = now - timedelta(days=days)
    return since.isoformat(), now.isoformat()


def parse_window_bound(value: str) -> str:
    """Accepts a bare date ("2026-07-01") or a full ISO datetime and returns a
    UTC-anchored ISO string comparable against `timestamp` columns."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _verdict_counts(rows: list[dict]) -> dict:
    counts = Counter(r.get("verdict") for r in rows if r.get("verdict"))
    return {v: counts.get(v, 0) for v in VERDICTS}


def build_report(shadow_rows: list[dict], production_rows: list[dict], *,
                  track: str, since: str, until: str) -> dict:
    """Pure: turns raw shadow-table + production call_log rows for the window
    into a deterministic evaluation report. The wallet-walk itself is
    wallet_sim.walk -- the same function the live orchestrators use, so this
    harness can never silently disagree with what actually ran."""
    by_ticker: dict[str, list[dict]] = {}
    for r in shadow_rows:
        by_ticker.setdefault(r["ticker"], []).append(r)

    per_ticker = {}
    total_round_trips = total_wins = total_open = 0
    total_realized = 0.0
    for ticker in sorted(by_ticker):
        rows = sorted(by_ticker[ticker], key=lambda r: r["timestamp"])
        walk_rows = [
            {"verdict": r.get("verdict"), "timestamp": r.get("timestamp"),
             "price": (r.get("data_snapshot") or {}).get("price")}
            for r in rows
        ]
        latest_price = walk_rows[-1]["price"] if walk_rows else None
        walked = wallet_sim.walk(walk_rows, mark_price=latest_price)

        round_trips = walked["round_trips"]
        wins = sum(1 for rt in round_trips if (rt["return_pct"] or 0) > 0)
        realized_sum = round(sum(rt["return_pct"] for rt in round_trips
                                  if rt["return_pct"] is not None), 4)

        per_ticker[ticker] = {
            "checks": len(rows),
            "verdict_counts": _verdict_counts(rows),
            "round_trips": len(round_trips),
            "wins": wins,
            "win_rate": round(wins / len(round_trips), 4) if round_trips else None,
            "realized_return_pct_sum": realized_sum,
            "open_position": walked["open"],
        }
        total_round_trips += len(round_trips)
        total_wins += wins
        total_realized += realized_sum
        if walked["open"]:
            total_open += 1

    prod_verdict_counts = _verdict_counts(production_rows)
    prod_changes = sum(1 for r in production_rows if r.get("alerted"))

    return {
        "track": track,
        "window": {"since": since, "until": until},
        "tickers": sorted(by_ticker),
        "per_ticker": per_ticker,
        "shadow": {
            "table": TRACKS[track],
            "total_checks": sum(len(v) for v in by_ticker.values()),
            "verdict_counts": _verdict_counts(shadow_rows),
            "round_trips": total_round_trips,
            "wins": total_wins,
            "win_rate": round(total_wins / total_round_trips, 4) if total_round_trips else None,
            "realized_return_pct_sum": round(total_realized, 4),
            "open_positions": total_open,
        },
        "production": {
            "table": "call_log",
            "total_checks": len(production_rows),
            "verdict_counts": prod_verdict_counts,
            "verdict_changes": prod_changes,
        },
    }


def render_report(report: dict) -> str:
    """Deterministic, human-readable stdout rendering of build_report()'s output."""
    lines = []
    w = report["window"]
    lines.append(f"Shadow wallet-sim evaluation — track={report['track']} "
                 f"({report['shadow']['table']} vs {report['production']['table']})")
    lines.append(f"Window: {w['since']} .. {w['until']}")
    lines.append("")

    sh = report["shadow"]
    lines.append(f"SHADOW   checks={sh['total_checks']} "
                 f"verdicts={_fmt_counts(sh['verdict_counts'])}")
    win_rate = f"{sh['win_rate'] * 100:.2f}%" if sh["win_rate"] is not None else "n/a"
    lines.append(f"         round_trips={sh['round_trips']} wins={sh['wins']} "
                 f"win_rate={win_rate} realized_return_sum={sh['realized_return_pct_sum']}% "
                 f"open_positions={sh['open_positions']}")

    pr = report["production"]
    lines.append(f"PRODUCTION checks={pr['total_checks']} "
                 f"verdicts={_fmt_counts(pr['verdict_counts'])} "
                 f"verdict_changes={pr['verdict_changes']}")
    lines.append("")

    lines.append(f"Per-ticker breakdown ({len(report['tickers'])} tickers)")
    for ticker in report["tickers"]:
        t = report["per_ticker"][ticker]
        wr = f"{t['win_rate'] * 100:.2f}%" if t["win_rate"] is not None else "n/a"
        open_desc = "flat"
        if t["open_position"]:
            op = t["open_position"]
            unreal = f"{op['unrealized_return_pct']:.2f}%" if op["unrealized_return_pct"] is not None else "n/a"
            open_desc = f"holding@{op['entry_price']} (unrealized {unreal})"
        lines.append(f"  {ticker:10} checks={t['checks']:3} "
                     f"verdicts={_fmt_counts(t['verdict_counts'])} "
                     f"round_trips={t['round_trips']} wins={t['wins']} win_rate={wr} "
                     f"realized_return_sum={t['realized_return_pct_sum']}% open={open_desc}")

    return "\n".join(lines)


def _fmt_counts(counts: dict) -> str:
    return " ".join(f"{v}={counts[v]}" for v in VERDICTS)


# --- I/O: reads only, never writes -------------------------------------------

def fetch_shadow_rows(sb, table: str, since_iso: str, until_iso: str) -> list[dict]:
    return (sb.table(table)
            .select("ticker,verdict,timestamp,data_snapshot")
            .eq("label", "watchlist")
            .gte("timestamp", since_iso).lte("timestamp", until_iso)
            .order("ticker").order("timestamp")
            .execute().data or [])


def fetch_production_rows(sb, tickers: list[str], since_iso: str, until_iso: str) -> list[dict]:
    if not tickers:
        return []
    return (sb.table("call_log")
            .select("ticker,verdict,timestamp,alerted")
            .eq("label", "watchlist").in_("ticker", tickers)
            .gte("timestamp", since_iso).lte("timestamp", until_iso)
            .order("ticker").order("timestamp")
            .execute().data or [])


# --- entry point ---------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--track", required=True, choices=sorted(TRACKS),
                    help="which shadow track to evaluate")
    p.add_argument("--since", default=None,
                    help="window start (ISO date/datetime); default: EVAL_WINDOW_DAYS ago")
    p.add_argument("--until", default=None,
                    help="window end (ISO date/datetime); default: now")
    p.add_argument("--output", default=None,
                    help="optional path to also write the report as JSON")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    default_since, default_until = default_window(datetime.now(timezone.utc), config.EVAL_WINDOW_DAYS)
    since_iso = parse_window_bound(args.since) if args.since else default_since
    until_iso = parse_window_bound(args.until) if args.until else default_until

    config.require_secrets()
    sb = state.client()

    table = TRACKS[args.track]
    shadow_rows = fetch_shadow_rows(sb, table, since_iso, until_iso)
    tickers = sorted({r["ticker"] for r in shadow_rows})
    production_rows = fetch_production_rows(sb, tickers, since_iso, until_iso)

    report = build_report(shadow_rows, production_rows, track=args.track,
                           since=since_iso, until=until_iso)
    print(render_report(report))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, sort_keys=True)
        print(f"\n[eval_shadow] wrote {args.output}")


if __name__ == "__main__":
    main()
