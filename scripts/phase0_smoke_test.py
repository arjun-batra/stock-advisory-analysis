#!/usr/bin/env python3
"""
Phase 0 - Yahoo Finance smoke test for the Stock Advisory Agent.

Purpose: BEFORE any build work, confirm the unofficial Yahoo Finance API actually
returns the fields the system depends on, for every real watchlist ticker (US + TSX).
The whole stack sits on this one unofficial data source with no SLA, and TSX
fundamentals are the known weak spot - so we find the gaps now, not in Phase 3.

Maps to solution-design.md:
  - Section 9, Phase 0 (this test, and its exit criteria)
  - Section 4.4a  (what the AI prompt is fed: price/volume, fundamentals, news)
  - Section 5     (the data_snapshot contract the detail page renders)

Verdicts:
  PASS    - full history + all fundamentals present
  PARTIAL - price fine, a fundamental (P/E, mcap, 52w) missing (TSX em-dash case)
  NEW     - valid price data but <~20 sessions of history (recent IPO); 20d metrics
            not yet computable. Self-resolves as sessions accrue. NOT a blocker.
  FAIL    - no usable price data at all (delisted/halted/bad ticker). Hard blocker.

Exit criteria: no FAIL. NEW and PARTIAL are acceptable - the data source returns
usable data; NEW just needs time, PARTIAL is handled by the UI's em-dash variant.

Run:
  pip install yfinance
  python3 phase0_smoke_test.py
  # optional: pass tickers on the command line to override the list below
  python3 phase0_smoke_test.py AAPL MSFT SHOP.TO RY.TO
"""

import sys
import time
from datetime import datetime, timezone

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    sys.exit("Missing dependency. Run:  pip install yfinance")

# ----------------------------------------------------------------------------
# REPLACE THIS with your real watchlist. TSX tickers need the .TO suffix.
# ----------------------------------------------------------------------------
TICKERS = [
    # US
    "AAPL", "TSLA", "AMZN", "NFLX", "NVDA", "GOOG", "COST", "BB", "SPCX",
    # TSX  -> .TO suffix
    "L.TO", "DOL.TO", "RY.TO", "TD.TO", "BNS.TO", "SHOP.TO",
]
# ----------------------------------------------------------------------------

MIN_HISTORY_ROWS = 21      # need >=20 trading days for the 20d change + 20d avg volume
STALE_AFTER_DAYS = 5       # last bar older than this => likely halted/delisted
PACING_SECONDS = 0.7       # be polite to Yahoo; mirrors the rate-pacing note in 4.4


def _get(d, *keys):
    """Return the first non-null value across several possible key spellings."""
    for k in keys:
        try:
            v = d[k] if not hasattr(d, "get") else d.get(k)
        except Exception:
            v = None
        if v not in (None, "", 0):
            return v
    return None


def check_price_volume(tk: "yf.Ticker") -> dict:
    """Pull history and compute whatever derived metrics the history depth allows.

    Three cases, distinguished for the caller:
      - no price data at all         -> has_price=False  (true FAIL)
      - price data but < MIN rows    -> is_new=True       (newly listed, partial metrics)
      - price data with full history -> price_ok=True      (all metrics computed)
    """
    out = {"price_ok": False, "has_price": False, "is_new": False, "rows": 0, "notes": []}
    try:
        h = tk.history(period="3mo", auto_adjust=False)
    except Exception as e:
        out["notes"].append(f"history error: {type(e).__name__}: {str(e)[:120]}")
        return out

    out["rows"] = len(h)
    if h is None or h.empty:
        out["notes"].append("no price data returned (empty) - delisted/halted/bad ticker?")
        return out

    close = h["Close"].dropna()
    vol = h["Volume"].dropna()
    last_date = close.index[-1].to_pydatetime()
    age_days = (datetime.now(timezone.utc) - last_date.replace(tzinfo=timezone.utc)).days
    out["has_price"] = True
    out["last_close"] = round(float(close.iloc[-1]), 4)
    out["last_date"] = last_date.date().isoformat()
    if age_days > STALE_AFTER_DAYS:
        out["notes"].append(f"stale: last bar is {age_days}d old")

    n = len(close)
    try:
        if n >= 2:
            out["pct_1d"] = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2)
        if n >= 6:
            out["pct_5d"] = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2)
        if n >= MIN_HISTORY_ROWS:
            out["pct_20d"] = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2)
            avg20 = vol.iloc[-21:-1].mean()
            out["vol_vs_avg"] = round(float(vol.iloc[-1] / avg20), 2) if avg20 else None
            out["price_ok"] = True
        else:
            out["is_new"] = True
            out["notes"].append(
                f"newly listed: only {n} trading days - 20d metrics unavailable "
                f"until ~{MIN_HISTORY_ROWS} sessions accrue"
            )
    except Exception as e:
        out["notes"].append(f"metric compute error: {type(e).__name__}: {str(e)[:120]}")
    return out


def check_fundamentals(tk: "yf.Ticker") -> dict:
    """P/E, market cap, 52-week range. fast_info first (reliable), .info fallback."""
    out = {"pe": None, "market_cap": None, "range_52w": None, "currency": None, "notes": []}

    fi = {}
    try:
        fi = dict(tk.fast_info)
    except Exception:
        try:
            fi = tk.fast_info
        except Exception:
            fi = {}

    info = {}
    try:
        info = tk.info or {}
    except Exception as e:
        out["notes"].append(f".info unavailable: {type(e).__name__}")

    out["currency"] = _get(fi, "currency") or _get(info, "currency")
    out["market_cap"] = _get(fi, "market_cap", "marketCap") or _get(info, "marketCap")
    out["pe"] = _get(info, "trailingPE", "forwardPE")  # P/E only lives in .info

    hi = _get(fi, "year_high", "yearHigh") or _get(info, "fiftyTwoWeekHigh")
    lo = _get(fi, "year_low", "yearLow") or _get(info, "fiftyTwoWeekLow")
    if hi and lo:
        out["range_52w"] = (round(float(lo), 2), round(float(hi), 2))
    return out


def check_news(tk: "yf.Ticker") -> dict:
    """Count headlines; handle both old and new yfinance news schemas."""
    out = {"count": 0, "sample": []}
    try:
        items = tk.news or []
    except Exception:
        items = []
    titles = []
    for it in items:
        title = None
        if isinstance(it, dict):
            if "title" in it:
                title = it.get("title")
            elif isinstance(it.get("content"), dict):
                title = it["content"].get("title")
        if title:
            titles.append(title)
    out["count"] = len(titles)
    out["sample"] = titles[:2]
    return out


def verdict(pv: dict, fund: dict) -> str:
    if not pv.get("has_price"):
        return "FAIL"
    if pv.get("is_new"):
        return "NEW"
    missing = [k for k, v in (("P/E", fund["pe"]),
                              ("market cap", fund["market_cap"]),
                              ("52w range", fund["range_52w"])) if v is None]
    return "PASS" if not missing else "PARTIAL"


def run(tickers):
    print(f"Phase 0 smoke test  |  {len(tickers)} tickers  |  "
          f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    rows = []
    for i, sym in enumerate(tickers):
        is_tsx = sym.upper().endswith(".TO")
        try:
            tk = yf.Ticker(sym)
            pv = check_price_volume(tk)
            fund = check_fundamentals(tk)
            news = check_news(tk)
        except Exception as e:
            pv, fund, news = {"price_ok": False, "notes": [f"fatal: {e}"]}, {}, {"count": 0}
        v = verdict(pv, fund)

        missing = [k for k, val in (("P/E", fund.get("pe")),
                                    ("mcap", fund.get("market_cap")),
                                    ("52w", fund.get("range_52w"))) if val is None]
        line = f"[{v:7}] {sym:10} ({'TSX' if is_tsx else 'US'})"
        if pv.get("has_price"):
            line += (f"  close={pv['last_close']} {fund.get('currency') or '?'}"
                     f"  1d={pv.get('pct_1d')}%  5d={pv.get('pct_5d')}%"
                     f"  20d={pv.get('pct_20d')}%  vol/avg={pv.get('vol_vs_avg')}x"
                     f"  news={news['count']}")
        if missing:
            line += f"  MISSING: {', '.join(missing)}"
        for note in pv.get("notes", []):
            line += f"\n            ! {note}"
        print(line)

        rows.append({
            "ticker": sym, "market": "TSX" if is_tsx else "US", "verdict": v,
            "rows": pv.get("rows"), "last_close": pv.get("last_close"),
            "currency": fund.get("currency"),
            "pct_1d": pv.get("pct_1d"), "pct_5d": pv.get("pct_5d"),
            "pct_20d": pv.get("pct_20d"), "vol_vs_avg": pv.get("vol_vs_avg"),
            "pe": fund.get("pe"), "market_cap": fund.get("market_cap"),
            "range_52w": fund.get("range_52w"), "news": news["count"],
            "missing": ", ".join(missing), "notes": "; ".join(pv.get("notes", [])),
        })
        time.sleep(PACING_SECONDS)

    write_report(rows)
    summarize(rows)


def write_report(rows):
    df = pd.DataFrame(rows)
    df.to_csv("phase0_results.csv", index=False)
    with open("phase0_results.md", "w") as f:
        f.write(f"# Phase 0 results — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("| Ticker | Mkt | Verdict | Close | Cur | 1d% | 5d% | 20d% | Vol/avg | P/E | MktCap | 52w | News | Missing |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['ticker']} | {r['market']} | {r['verdict']} | "
                    f"{r['last_close']} | {r['currency'] or '—'} | {r['pct_1d']} | "
                    f"{r['pct_5d']} | {r['pct_20d']} | {r['vol_vs_avg']} | "
                    f"{r['pe'] or '—'} | {r['market_cap'] or '—'} | "
                    f"{'✓' if r['range_52w'] else '—'} | {r['news']} | {r['missing'] or '—'} |\n")
    print("\nWrote phase0_results.md and phase0_results.csv")


def summarize(rows):
    n = len(rows)
    fails = [r for r in rows if r["verdict"] == "FAIL"]
    news = [r for r in rows if r["verdict"] == "NEW"]
    partials = [r for r in rows if r["verdict"] == "PARTIAL"]
    tsx_partial = [r for r in partials if r["market"] == "TSX"]
    passes = n - len(fails) - len(news) - len(partials)
    print("\n" + "=" * 60)
    print(f"  PASS {passes}   PARTIAL {len(partials)}   NEW {len(news)}   FAIL {len(fails)}   (of {n})")
    print("=" * 60)
    if fails:
        print("\n  HARD BLOCKERS — no usable price data, system can't judge these:")
        for r in fails:
            print(f"    - {r['ticker']}: {r['notes'] or 'no price data'}")
    if news:
        print("\n  NEWLY LISTED — valid, but <20 sessions of history (not a blocker):")
        for r in news:
            print(f"    - {r['ticker']} ({r['market']}): {r['notes']}")
        print("    These pass on data availability; the 20d metrics fill in automatically once "
              "enough sessions accrue. Build must treat 20d fields as n/a meanwhile (sec 4.4a/7.5).")
    if partials:
        print("\n  Fundamentals gaps (render em-dash per UI handoff, not a blocker):")
        for r in partials:
            print(f"    - {r['ticker']} ({r['market']}): missing {r['missing']}")
        if tsx_partial:
            print(f"\n  Note: {len(tsx_partial)}/{len([r for r in rows if r['market']=='TSX'])} "
                  f"TSX tickers have fundamentals gaps — the known risk in Section 2. "
                  f"Confirm the missing fields aren't ones the AI prompt leans on.")
    if not fails:
        print("\n  Exit criteria MET: every ticker returns usable data from the source "
              "(NEW = needs time, PARTIAL = em-dash handled). Phase 0 passes.")
    else:
        print("\n  Exit criteria NOT met: resolve the hard blockers above before Phase 1.")


if __name__ == "__main__":
    run(sys.argv[1:] if len(sys.argv) > 1 else TICKERS)
