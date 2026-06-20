"""AI judgment layer (solution design 4.4 / 4.4a).

Builds the verdict prompt, calls Gemini in strict-JSON mode, validates the
schema, retries once on a bad reply, and fails safe to Hold if it still can't
parse — so a malformed response can only ever MISS a signal, never fabricate one.
"""

import json

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
    '"rationale": "<one sentence, max 140 chars, plain language>"}'
)

VALID_VERDICTS = {"Buy", "Sell", "Hold"}
RATIONALE_MAX = 140
_FAIL_SAFE = {"verdict": "Hold", "rationale": "model response could not be parsed; fail-safe Hold"}


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


def _build_user_prompt(data: dict, position: dict | None) -> str:
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
        "",
        "Give your verdict as JSON per the schema.",
    ]
    return "\n".join(lines)


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


def judge(data: dict, position: dict | None = None) -> dict:
    """Return {verdict, rationale, raw_model_response, parse_status}."""
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    user = _build_user_prompt(data, position)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        temperature=0.2,
    )

    raw = ""
    try:
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=user, config=cfg)
        raw = (resp.text or "").strip()
    except Exception as e:
        raw = f"<api error: {type(e).__name__}: {str(e)[:120]}>"

    parsed = _parse(raw)
    if parsed:
        return {**parsed, "raw_model_response": raw, "parse_status": "ok"}

    # one retry with a terse correction appended
    raw2 = ""
    try:
        retry = user + "\n\nYour last reply was not valid JSON. Reply with ONLY the JSON object."
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=retry, config=cfg)
        raw2 = (resp.text or "").strip()
    except Exception as e:
        raw2 = f"<api error: {type(e).__name__}: {str(e)[:120]}>"

    parsed = _parse(raw2)
    if parsed:
        return {**parsed, "raw_model_response": raw2, "parse_status": "retried"}

    # still bad -> fail safe to Hold, keep both raw replies for debugging
    return {**_FAIL_SAFE, "raw_model_response": f"{raw} || retry: {raw2}", "parse_status": "failed"}
