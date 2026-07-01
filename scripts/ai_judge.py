"""AI judgment layer (solution design 4.4 / 4.4a).

Builds the verdict prompt, calls Gemini in strict-JSON mode, validates the
schema, retries once on a bad reply, and fails safe to Hold if it still can't
parse — so a malformed response can only ever MISS a signal, never fabricate one.
"""

import json
import time

from google import genai
from google.genai import types

import config
from textutil import clip

VALID_VERDICTS = {"Buy", "Sell", "Hold"}
RATIONALE_MAX = 280   # stored + shown in full on the detail page; the push is clipped separately
_FAIL_SAFE_PARSE = {"verdict": "Hold",
                    "rationale": "The model reply could not be parsed; showing a fail-safe Hold."}
_FAIL_SAFE_API = {"verdict": "Hold",
                  "rationale": "The AI service didn't return a usable response; showing a fail-safe Hold."}


def missing_verdict(noun: str = "ticker") -> dict:
    """Fail-safe result for a name the judge_batch return simply doesn't cover
    (defensive — the parser fail-safes every requested ticker, so this only
    fires if the result dict and the caller's item list ever disagree). Same
    fail-safe-to-Hold posture as _FAIL_SAFE_PARSE: parse_status='failed' means
    it never alerts and never advances verdict_state."""
    return {
        "verdict": "Hold",
        "rationale": f"No verdict returned for this {noun}; fail-safe Hold.",
        "raw_model_response": "", "parse_status": "failed",
    }

BATCH_SYSTEM_PROMPT = (
    "You are a disciplined, unemotional equity analyst. You are given several "
    "stocks at once. For EACH stock, decide Buy / Sell / Hold and give a clear, "
    "simple, plain-language reason in one or two short sentences. Default to "
    "\"Hold\" unless the data clearly supports action. You do not assume any fixed "
    "investment style or time horizon; weigh each stock on its own context.\n\n"
    "Output ONLY a JSON array and nothing else - no markdown, no code fences, no "
    "prose before or after. One object per stock, in the same order you were given "
    "them, including every ticker exactly once. Each object:\n"
    '{"ticker": "<symbol>", "verdict": "Buy" | "Sell" | "Hold", '
    '"rationale": "<one or two short sentences>"}'
)


def _ticker_block(data: dict, position: dict | None) -> str:
    f = data.get("fundamentals", {})
    lines = [
        f"Ticker: {data['ticker']} ({data['market']})",
        f"Position: {'HELD' if position else 'WATCH-ONLY'}",
    ]
    if position:
        lines.append(
            f"  Shares: {position['shares']}, Cost basis: {position['cost_basis']} "
            f"{position['currency']}, Current price: {data['price']}, "
            f"Unrealized P/L: {position['pl_pct']}%"
        )
    lines += [
        "Price/volume (recent): "
        f"last close {data['price']}, 1d {data['pct_change_1d']}%, "
        f"5d {data['pct_change_5d']}%, 20d {data['pct_change_20d']}%, "
        f"volume vs 20d avg {data['volume_vs_avg']}",
        "Fundamentals: "
        f"P/E {f.get('pe')}, market cap {f.get('market_cap')}, "
        f"52w range {f.get('range_52w')}",
        "Recent news headlines: " + ("; ".join(data.get("headlines", [])) or "none"),
    ]
    return "\n".join(lines)


def _client():
    """Gemini client with an explicit, generous request timeout.

    Root cause of the 3.5-flash -> lite fallbacks (observed live): 3.5-flash
    *did* respond (tokens were billed on Google's dashboard) but slowly, and the
    SDK's default client timeout fired first — so we discarded a completed,
    token-charged response and fell back to lite. A high explicit timeout lets a
    slow-but-valid response land instead of being thrown away.
    """
    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=config.GEMINI_TIMEOUT_MS),
    )


def _usage(resp) -> dict | None:
    """Pull token counts off a response's usage_metadata, if present."""
    um = getattr(resp, "usage_metadata", None)
    if um is None:
        return None
    return {
        "prompt": getattr(um, "prompt_token_count", None),
        "output": getattr(um, "candidates_token_count", None),
        "thoughts": getattr(um, "thoughts_token_count", None),
        "total": getattr(um, "total_token_count", None),
    }


def _generate(client, model: str, prompt, cfg) -> tuple[str, bool, str | None, dict | None]:
    """Return (text, is_api_error, error_detail, usage).

    error_detail is the real exception (type + message) on failure — previously
    the caller logged a hardcoded "rate-limited/unavailable" guess, which hid
    whether the failure was a 429 (ResourceExhausted), a timeout (Deadline
    Exceeded / read timeout), or a bad model name (NotFound). usage carries the
    token counts on success.
    """
    try:
        resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
        return (resp.text or "").strip(), False, None, _usage(resp)
    except Exception as e:
        return "", True, f"{type(e).__name__}: {str(e)[:200]}", None


def _models_to_try(models: list[str] | None = None) -> list[str]:
    """Resolve the model try-order. Pass an explicit list (e.g. the discovery
    models) to override; otherwise default to the watchlist primary + backup.
    """
    if models:
        return [m for m in models if m]
    out = [config.GEMINI_MODEL]
    if config.GEMINI_MODEL_BACKUP and config.GEMINI_MODEL_BACKUP != config.GEMINI_MODEL:
        out.append(config.GEMINI_MODEL_BACKUP)
    return out


def _parse_batch(raw: str, tickers: list[str], model: str) -> dict | None:
    """Parse a JSON array of verdicts into {ticker: result}.

    Returns None only if no array could be extracted at all (caller retries).
    If an array is present but a given ticker is missing/invalid, that ticker
    gets a fail-safe Hold while the others still resolve.
    """
    try:
        obj = json.loads(raw)
    except Exception:
        return None

    arr = None
    if isinstance(obj, list):
        arr = obj
    elif isinstance(obj, dict):                  # tolerate {"stocks": [...]} shapes
        for v in obj.values():
            if isinstance(v, list):
                arr = v
                break
    if arr is None:
        return None

    by_ticker = {str(o["ticker"]).upper(): o
                 for o in arr if isinstance(o, dict) and o.get("ticker")}

    out = {}
    for i, t in enumerate(tickers):
        o = by_ticker.get(t.upper())
        if o is None and len(arr) == len(tickers) and isinstance(arr[i], dict):
            o = arr[i]                           # positional fallback (same order requested)
        if isinstance(o, dict) and o.get("verdict") in VALID_VERDICTS and o.get("rationale"):
            out[t] = {"verdict": o["verdict"], "rationale": clip(o["rationale"], RATIONALE_MAX),
                      "raw_model_response": raw, "parse_status": "ok", "model_used": model}
        else:
            out[t] = {**_FAIL_SAFE_PARSE, "raw_model_response": raw,
                      "parse_status": "failed", "model_used": model}
    return out


def judge_batch(items: list[dict], models: list[str] | None = None) -> dict:
    """Judge every ticker in ONE Gemini call (cuts requests from N to 1 per run).

    items: list of {"data": <market data>, "position": <position|None>}.
    models: optional explicit model try-order (primary, backup...). Discovery
    passes its own 2.5 models here so it draws from separate free-tier quota
    buckets and can't eat into the watchlist's allowance; the watchlist call
    passes nothing and uses config.GEMINI_MODEL / _BACKUP.
    Returns {ticker: {verdict, rationale, raw_model_response, parse_status,
    model_used, usage, fallback_from}}. On a hard failure of every model every
    ticker fails safe to Hold, so a bad batch can only ever MISS signals, never
    fabricate one.
    """
    tickers = [it["data"]["ticker"] for it in items]
    if not items:
        return {}

    client = _client()
    blocks = [f"--- Stock {i} ---\n{_ticker_block(it['data'], it['position'])}"
              for i, it in enumerate(items, 1)]
    user = ("\n\n".join(blocks) +
            "\n\nReturn a JSON array with one object per stock above, each "
            '{"ticker", "verdict", "rationale"}, including every ticker exactly once.')
    cfg = types.GenerateContentConfig(
        system_instruction=BATCH_SYSTEM_PROMPT,
        response_mime_type="application/json",
        temperature=0.2,
    )

    def _enrich(parsed, usage, fallback_from):
        # Stamp token usage + the (real) fallback error onto every ticker's
        # result. usage is the BATCH total for this one API call — identical
        # across the rows of a run, so sum it once per run, not per ticker.
        for v in parsed.values():
            v["usage"] = usage
            v["fallback_from"] = fallback_from
        return parsed

    last_raw = ""
    any_response = False   # did ANY model return text at all (vs pure API/quota errors)?
    notes: list[str] = []  # real errors of any model we fell back from
    models = _models_to_try(models)
    last_model = models[0]

    for i, model in enumerate(models):
        last_model = model
        raw, api_err, err, usage = _generate(client, model, user, cfg)
        if api_err:
            time.sleep(config.GEMINI_API_BACKOFF_SECONDS)
            raw, api_err, err, usage = _generate(client, model, user, cfg)
        if api_err:
            last_raw = err or raw
            notes.append(f"{model}: {err}")
            nxt = f", trying {models[i + 1]}" if i + 1 < len(models) else ""
            print(f"  [ai_judge] {model} failed after retry ({err}){nxt}")
            continue   # this model is exhausted; move to the backup, if any

        any_response = True
        fb = "; ".join(notes) or None
        parsed = _parse_batch(raw, tickers, model)
        if parsed is not None:
            return _enrich(parsed, usage, fb)

        retry = user + "\n\nYour last reply was not a valid JSON array. Reply with ONLY the JSON array."
        raw2, _, _, usage2 = _generate(client, model, retry, cfg)
        parsed = _parse_batch(raw2, tickers, model)
        if parsed is not None:
            return _enrich(parsed, usage2 or usage, fb)

        last_raw = f"{raw} || retry: {raw2}"
        notes.append(f"{model}: replied but unparseable")
        print(f"  [ai_judge] {model}: replied but never returned a parseable verdict array")

    # Every model in the list failed -> fail safe to Hold for all tickers.
    fail = _FAIL_SAFE_PARSE if any_response else _FAIL_SAFE_API
    status = "failed" if any_response else "api_error"
    fb = "; ".join(notes) or None
    return {t: {**fail, "raw_model_response": last_raw, "parse_status": status,
               "model_used": last_model, "usage": None, "fallback_from": fb} for t in tickers}
