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

SYSTEM_PROMPT = (
    "You are a disciplined, unemotional equity analyst. You output ONLY a single "
    "JSON object and nothing else - no markdown, no code fences, no prose before "
    "or after. Default to \"Hold\" unless the data clearly supports action. You do "
    "not assume any fixed investment style or time horizon; weigh each stock on "
    "its own context.\n\n"
    "Schema (all fields required):\n"
    '{"verdict": "Buy" | "Sell" | "Hold", '
    '"rationale": "<a clear, simple, plain-language reason for the verdict, one or two short sentences>"}'
)

VALID_VERDICTS = {"Buy", "Sell", "Hold"}
RATIONALE_MAX = 280   # stored + shown in full on the detail page; the push is clipped separately
_FAIL_SAFE_PARSE = {"verdict": "Hold",
                    "rationale": "The model reply could not be parsed; showing a fail-safe Hold."}
_FAIL_SAFE_API = {"verdict": "Hold",
                  "rationale": "The AI service was rate-limited and didn't respond; showing a fail-safe Hold."}

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


def _clip(text: str, limit: int = RATIONALE_MAX) -> str:
    """Trim to <= limit chars on a word boundary, adding an ellipsis if cut.

    The rationale becomes the push-notification body, so the old hard slice
    (text[:140]) shipped half-words to the user. Clip on whitespace instead and
    signal the cut with a single-char ellipsis, keeping the result <= limit.
    """
    text = " ".join(str(text).split())              # normalize whitespace
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1]                      # leave room for the ellipsis
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]          # back up to the last whole word
    return clipped.rstrip(" ,.;:-") + "\u2026"


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


def _build_user_prompt(data: dict, position: dict | None) -> str:
    return _ticker_block(data, position) + "\n\nGive your verdict as JSON per the schema."


def _parse(raw: str) -> dict | None:
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("verdict") not in VALID_VERDICTS:
        return None
    if not obj.get("rationale"):
        return None
    return {"verdict": obj["verdict"], "rationale": _clip(obj["rationale"])}


def _generate(client, prompt, cfg) -> tuple[str, bool]:
    """Return (text, is_api_error). Captures 429/quota errors instead of raising."""
    try:
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=prompt, config=cfg)
        return (resp.text or "").strip(), False
    except Exception as e:
        return f"<api error: {type(e).__name__}: {str(e)[:160]}>", True


def judge(data: dict, position: dict | None = None) -> dict:
    """Return {verdict, rationale, raw_model_response, parse_status}."""
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    user = _build_user_prompt(data, position)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        temperature=0.2,
    )

    raw, api_err = _generate(client, user, cfg)

    # API error (e.g. 429 rate limit): a JSON-correction retry is pointless and
    # just burns more quota, so back off once and then fail safe to Hold.
    if api_err:
        time.sleep(config.GEMINI_API_BACKOFF_SECONDS)
        raw, api_err = _generate(client, user, cfg)
        if api_err:
            return {**_FAIL_SAFE_API, "raw_model_response": raw, "parse_status": "api_error"}

    parsed = _parse(raw)
    if parsed:
        return {**parsed, "raw_model_response": raw, "parse_status": "ok"}

    # Got a reply, but it wasn't valid JSON -> one correction retry.
    retry = user + "\n\nYour last reply was not valid JSON. Reply with ONLY the JSON object."
    raw2, _ = _generate(client, retry, cfg)
    parsed = _parse(raw2)
    if parsed:
        return {**parsed, "raw_model_response": raw2, "parse_status": "retried"}

    return {**_FAIL_SAFE_PARSE, "raw_model_response": f"{raw} || retry: {raw2}", "parse_status": "failed"}


def _parse_batch(raw: str, tickers: list[str]) -> dict | None:
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
            out[t] = {"verdict": o["verdict"], "rationale": _clip(o["rationale"]),
                      "raw_model_response": raw, "parse_status": "ok"}
        else:
            out[t] = {**_FAIL_SAFE_PARSE, "raw_model_response": raw, "parse_status": "failed"}
    return out


def judge_batch(items: list[dict]) -> dict:
    """Judge every ticker in ONE Gemini call (cuts requests from N to 1 per run).

    items: list of {"data": <market data>, "position": <position|None>}.
    Returns {ticker: {verdict, rationale, raw_model_response, parse_status}}.
    On a hard failure every ticker fails safe to Hold, so a bad batch can only
    ever MISS signals that run, never fabricate one.
    """
    tickers = [it["data"]["ticker"] for it in items]
    if not items:
        return {}

    client = genai.Client(api_key=config.GEMINI_API_KEY)
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

    raw, api_err = _generate(client, user, cfg)
    if api_err:
        time.sleep(config.GEMINI_API_BACKOFF_SECONDS)
        raw, api_err = _generate(client, user, cfg)
        if api_err:
            return {t: {**_FAIL_SAFE_API, "raw_model_response": raw, "parse_status": "api_error"}
                    for t in tickers}

    parsed = _parse_batch(raw, tickers)
    if parsed is not None:
        return parsed

    retry = user + "\n\nYour last reply was not a valid JSON array. Reply with ONLY the JSON array."
    raw2, _ = _generate(client, retry, cfg)
    parsed = _parse_batch(raw2, tickers)
    if parsed is not None:
        return parsed

    combined = f"{raw} || retry: {raw2}"
    return {t: {**_FAIL_SAFE_PARSE, "raw_model_response": combined, "parse_status": "failed"}
            for t in tickers}
