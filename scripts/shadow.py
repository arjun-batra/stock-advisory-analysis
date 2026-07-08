"""Shadow verdict pilot — position-aware prompt variant (US/CA, non-production).

A parallel, NON-production verdict track. It reuses ai_judge's model-call
machinery verbatim (client, generate+retry, parse, model try-order, response
schema — so it shares GEMINI_MODEL / GEMINI_TIMEOUT_MS with production and never
copies a model string) and changes ONLY the prompt: it tells the model, per
ticker, whether THIS shadow track currently holds a position (entry price+date),
and requires a Sell on a HOLDING name to cite the specific reversal since entry.

Everything else — headlines, fundamentals, the confidence rubric, the JSON
contract — is identical to production (ai_judge.BATCH_SYSTEM_PROMPT), so the
pilot isolates the position-awareness variable only. This module imports
ai_judge but does NOT modify it; the production verdict path is untouched.
"""

from datetime import datetime, timezone

from google.genai import types

import ai_judge


def _fmt_entry_date(entry_date: str | None) -> str:
    """Render an ISO entry timestamp as a plain date for the prompt."""
    if not entry_date:
        return "unknown date"
    try:
        return datetime.fromisoformat(entry_date.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return str(entry_date)[:10]


# Position-awareness + explicit reversal-trigger addendum, appended AFTER the
# verbatim production system prompt so every other instruction (default-to-Hold,
# BUY-vs-AVOID bar, confidence rubric, JSON-only contract, headline handling) is
# byte-identical to production. We deliberately do NOT tell the model to suppress
# Buy-while-holding or Sell-while-flat verdicts — the wallet-walk already ignores
# those, and suppressing them at the prompt level would pollute the verdict-count
# comparison against production.
SHADOW_SYSTEM_PROMPT = ai_judge.BATCH_SYSTEM_PROMPT + (
    "\n\nADDITIONAL CONTEXT FOR THIS RUN — your current positions.\n"
    "Each stock includes a line 'Current shadow position: HOLDING at <price> "
    "since <date>' or 'Current shadow position: FLAT'. This is the authoritative "
    "record of whether you already hold that stock on this track; treat a HOLDING "
    "stock as a HELD position and a FLAT stock as a WATCH-ONLY name for the verdict "
    "meanings above.\n"
    "- If a stock is HOLDING: a Sell verdict must name the SPECIFIC condition that "
    "has changed since your entry (the entry price and date are given) — a concrete "
    "reversal of the thesis that put you in, e.g. a broken fundamental, a new "
    "material headline, or a decisive technical break. Do NOT issue a Sell that is "
    "merely a fresh, independent read of today's conditions without pointing to what "
    "changed since entry. State that change in the rationale.\n"
    "- If a stock is FLAT: judge a Buy on the same bar you already use for starting "
    "a position — no change to that standard.\n"
    "Apply your normal default-to-Hold discipline throughout; position awareness "
    "adds context, it does not lower the bar for action."
)


def _shadow_ticker_block(data: dict, shadow_pos: dict) -> str:
    """The production per-ticker block with the position section driven by the
    SHADOW track's own wallet-walk state instead of the holdings table.

    Market-data lines (sector, price/volume, fundamentals, headlines, discovery
    flags, session-live labels) are reproduced EXACTLY as ai_judge._ticker_block
    renders them, using the same helpers — the only intended difference from
    production is the two position lines. Keep this in lockstep with
    ai_judge._ticker_block if that block's market-data lines ever change.
    """
    f = data.get("fundamentals", {})
    cur = f" {f['currency']}" if f.get("currency") else ""
    company = f" - {f['name']}" if f.get("name") else ""
    sector = " / ".join(s for s in (f.get("sector"), f.get("industry")) if s) or "n/a"
    rng = f.get("range_52w")
    rng_s = f"{rng[0]}-{rng[1]}{cur}" if rng else "n/a"
    mcap = f"{f['market_cap']}{cur}" if f.get("market_cap") is not None else "n/a"

    holding = shadow_pos.get("state") == "holding"
    if holding:
        entry = f"{ai_judge._fmt(shadow_pos.get('entry_price'))}{cur}"
        shadow_line = (f"Current shadow position: HOLDING at {entry} since "
                       f"{_fmt_entry_date(shadow_pos.get('entry_date'))}.")
    else:
        shadow_line = "Current shadow position: FLAT."

    lines = [
        f"Ticker: {data['ticker']} ({data['market']}){company}",
        f"Sector/industry: {sector}",
        # Map the shadow wallet state onto the production HELD/WATCH-ONLY label so
        # the verdict-meaning rubric in the system prompt lines up.
        f"Position: {'HELD' if holding else 'WATCH-ONLY'}",
        shadow_line,
    ]
    if data.get("discovery_signals"):
        lines.append("Flagged today by the market screen for: "
                     + " + ".join(data["discovery_signals"]))
    live = data.get("session_live")
    px_label = "live price (session in progress)" if live else "last close"
    d1_label = "today so far" if live else "1d"
    vol_s = ai_judge._fmt(data["volume_vs_avg"])
    if data.get("volume_pro_rated"):
        vol_s += " (pro-rated estimate for the elapsed part of today's session)"
    lines += [
        "Price/volume (recent): "
        f"{px_label} {ai_judge._fmt(data['price'])}{cur}, {d1_label} {ai_judge._pct(data['pct_change_1d'])}, "
        f"5d {ai_judge._pct(data['pct_change_5d'])}, 20d {ai_judge._pct(data['pct_change_20d'])}, "
        f"volume vs 20d avg {vol_s}",
        "Fundamentals: "
        f"P/E {ai_judge._fmt(f.get('pe'))}, market cap {mcap}, 52w range {rng_s}",
        "Recent news headlines (dated where known): "
        + ("; ".join(data.get("headlines", [])) or "none"),
    ]
    return "\n".join(lines)


def judge_batch_shadow(items: list[dict]) -> dict:
    """One position-aware Gemini call for the whole US/CA batch (shadow track).

    items: list of {"data": <reconstructed production market snapshot>,
                    "shadow_pos": <{state, entry_price, entry_date}>}.

    Mirrors ai_judge.judge_batch's orchestration (single batched call, one retry
    on a bad reply, fail-safe-to-Hold on hard failure so a bad batch can only ever
    MISS a signal) but with the shadow system prompt + shadow blocks. Uses the
    SAME model try-order as production's watchlist call (config.GEMINI_MODEL /
    _BACKUP via ai_judge._models_to_try) and the same timeout/retry policy —
    shared config and shared call function (ai_judge._generate), not copies.
    Returns {ticker: {verdict, confidence, rationale, raw_model_response,
    parse_status, model_used, usage, fallback_from, retry_count}}.
    """
    if not items:
        return {}
    tickers = [it["data"]["ticker"] for it in items]

    client = ai_judge._client()
    blocks = [f"--- Stock {i} ---\n{_shadow_ticker_block(it['data'], it['shadow_pos'])}"
              for i, it in enumerate(items, 1)]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user = (f"Today's date: {today} (UTC). Use it to judge headline freshness "
            "and remember your own knowledge of these companies may be older.\n\n"
            + "\n\n".join(blocks) +
            "\n\nReturn a JSON array with one object per stock above, each "
            '{"ticker", "verdict", "confidence", "rationale"}, including every '
            "ticker exactly once.")
    cfg = types.GenerateContentConfig(
        system_instruction=SHADOW_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=ai_judge._RESPONSE_SCHEMA,
        temperature=0.2,
    )

    def _enrich(parsed, usage, fallback_from, retry_count):
        for v in parsed.values():
            v["usage"] = usage
            v["fallback_from"] = fallback_from
            v["retry_count"] = retry_count
        return parsed

    last_raw = ""
    any_response = False
    notes: list[str] = []
    total_retries = 0   # transport retries burned across every attempt this batch
    models = ai_judge._models_to_try(None)   # same order as production's watchlist call
    last_model = models[0]

    for i, model in enumerate(models):
        last_model = model
        # Transient-error retry (exponential backoff + full jitter) happens
        # INSIDE the shared ai_judge._generate — identical policy to production
        # by construction, nothing shadow-specific here.
        raw, api_err, err, usage, r = ai_judge._generate(client, model, user, cfg)
        total_retries += r
        if api_err:
            last_raw = err or raw
            notes.append(f"{model}: {err}")
            nxt = f", trying {models[i + 1]}" if i + 1 < len(models) else ""
            print(f"  [shadow] {model} failed after {r} transport retries ({err}){nxt}")
            continue

        any_response = True
        fb = "; ".join(notes) or None
        parsed = ai_judge._parse_batch(raw, tickers, model)
        if parsed is not None:
            return _enrich(parsed, usage, fb, total_retries)

        retry = user + "\n\nYour last reply was not a valid JSON array. Reply with ONLY the JSON array."
        raw2, _, _, usage2, r2 = ai_judge._generate(client, model, retry, cfg)
        total_retries += r2
        parsed = ai_judge._parse_batch(raw2, tickers, model)
        if parsed is not None:
            return _enrich(parsed, usage2 or usage, fb, total_retries)

        last_raw = f"{raw} || retry: {raw2}"
        notes.append(f"{model}: replied but unparseable")
        print(f"  [shadow] {model}: replied but never returned a parseable verdict array")

    fail = ai_judge._FAIL_SAFE_PARSE if any_response else ai_judge._FAIL_SAFE_API
    status = "failed" if any_response else "api_error"
    fb = "; ".join(notes) or None
    return {t: {**fail, "raw_model_response": last_raw, "parse_status": status,
                "model_used": last_model, "usage": None, "fallback_from": fb,
                "retry_count": total_retries} for t in tickers}
