"""AI judgment layer (solution design 4.4 / 4.4a).

Builds the verdict prompt, calls the configured AI provider in strict-JSON
mode, validates the schema, retries once on a bad reply, and fails safe to
Hold if it still can't parse. A malformed response can only ever MISS a
signal, never fabricate one — and that claim holds specifically because
`_parse_batch`'s positional fallback (the one path that resolves a ticker
from an object the model didn't label) accepts that object only when its own
`ticker` field is absent, or normalizes to the ticker being resolved AND that
normalized form is unambiguous among the tickers actually requested this
batch; anything else falls through to a fail-safe Hold instead of borrowing a
different company's verdict/rationale under `parse_status: "ok"` (§4.4a,
DEEP-003 fix; the unambiguity guard closes BUG-005, a residual cross-market
collision the original §4.4a suffix-stripping match didn't account for).

Provider-neutral (FR33, `docs/design/operational-controls.md` §14): this
module never imports an SDK directly or classifies a provider's raw
exceptions — it talks only to `ai_provider.AIProvider`/`ProviderError`, so a
future second provider is a new `AIProvider` implementation, not a change here.
"""

import dataclasses
import json
import pathlib
import random
import time
from collections import Counter
from datetime import datetime, timezone

import config
from ai_provider import BatchVerdictSchema, ErrorClass, ProviderError, TokenUsage, get_provider
from textutil import clip

VALID_VERDICTS = {"Buy", "Sell", "Hold"}
VALID_CONFIDENCE = {"high", "medium", "low"}
RATIONALE_MAX = config.RATIONALE_MAX   # stored + shown in full on the detail page; the push is clipped separately
_FAIL_SAFE_PARSE = {"verdict": "Hold", "confidence": None,
                    "rationale": "The model reply could not be parsed; showing a fail-safe Hold."}
_FAIL_SAFE_API = {"verdict": "Hold", "confidence": None,
                  "rationale": "The AI service didn't return a usable response; showing a fail-safe Hold."}


def missing_verdict(noun: str = "ticker") -> dict:
    """Fail-safe result for a name the judge_batch return simply doesn't cover
    (defensive — the parser fail-safes every requested ticker, so this only
    fires if the result dict and the caller's item list ever disagree). Same
    fail-safe-to-Hold posture as _FAIL_SAFE_PARSE: parse_status='failed' means
    it never alerts and never advances verdict_state."""
    return {
        "verdict": "Hold", "confidence": None,
        "rationale": f"No verdict returned for this {noun}; fail-safe Hold.",
        "raw_model_response": "", "parse_status": "failed",
    }

# Prompt text is configuration, not code (dev.md; REV-096) -- lives in prompts/, read once
# at import time here (same lifecycle as the inline constant it replaces), then the one
# {RATIONALE_MAX} placeholder is resolved from config. Path is resolved relative to the
# repo root the same way config._CACHE_PATH is, and for the same reason: scripts/ is a
# flat, non-package directory on sys.path, so this can't be a package-relative import.
_PROMPT_PATH = pathlib.Path(__file__).resolve().parent.parent / "prompts" / "batch_system_prompt.txt"
try:
    BATCH_SYSTEM_PROMPT = _PROMPT_PATH.read_text().replace("{RATIONALE_MAX}", str(RATIONALE_MAX))
except OSError as e:
    raise SystemExit(f"[ai_judge] could not load prompt file {_PROMPT_PATH}: {e}")

# Provider-neutral description of the expected reply shape (belt to the
# prompt's braces) — each AIProvider implementation translates this into its
# own SDK's schema/response-format type (see ai_provider._response_schema for
# Gemini's constrained-decoding translation).
_SCHEMA = BatchVerdictSchema(verdicts=tuple(sorted(VALID_VERDICTS)),
                             confidences=tuple(sorted(VALID_CONFIDENCE)))


def _fmt(v) -> str:
    """Render a possibly-missing value for the prompt ('n/a', never 'None')."""
    return "n/a" if v is None else str(v)


def _pct(v) -> str:
    """A percent-change field: number -> 'x%', explicit-string sentinel (e.g.
    'n/a (newly listed)') passed through, missing -> 'n/a'."""
    if v is None:
        return "n/a"
    return v if isinstance(v, str) else f"{v}%"


def _ticker_block(data: dict, position: dict | None) -> str:
    f = data.get("fundamentals", {})
    cur = f" {f['currency']}" if f.get("currency") else ""
    company = f" - {f['name']}" if f.get("name") else ""
    sector = " / ".join(s for s in (f.get("sector"), f.get("industry")) if s) or "n/a"
    rng = f.get("range_52w")
    rng_s = f"{rng[0]}-{rng[1]}{cur}" if rng else "n/a"
    mcap = f"{f['market_cap']}{cur}" if f.get("market_cap") is not None else "n/a"

    lines = [
        f"Ticker: {data['ticker']} ({data['market']}){company}",
        f"Sector/industry: {sector}",
        f"Position: {'HELD' if position else 'WATCH-ONLY'}",
    ]
    if position:
        lines.append(
            f"  Shares: {position['shares']}, Cost basis: {position['cost_basis']} "
            f"{position['currency']}, Current price: {data['price']}, "
            f"Unrealized P/L: {_pct(position['pl_pct'])}"
        )
    # Why the discovery screen shortlisted this name today (e.g. gainer,
    # volume-spike, 52w-high) — the very event the verdict should weigh.
    # Absent on watchlist tickers.
    if data.get("discovery_signals"):
        lines.append("Flagged today by the market screen for: "
                     + " + ".join(data["discovery_signals"]))
    # Session-aware labels (2026-07-03 hourly-run review, finding 4): mid-session
    # the last daily bar is LIVE, so calling it "last close" and comparing
    # partial-day volume to full-day averages misled the model on every
    # intraday run (whole-watchlist "volume vs avg 0.07-0.30" every morning).
    live = data.get("session_live")
    px_label = "live price (session in progress)" if live else "last close"
    d1_label = "today so far" if live else "1d"
    vol_s = _fmt(data["volume_vs_avg"])
    if data.get("volume_pro_rated"):
        vol_s += " (pro-rated estimate for the elapsed part of today's session)"
    lines += [
        "Price/volume (recent): "
        f"{px_label} {_fmt(data['price'])}{cur}, {d1_label} {_pct(data['pct_change_1d'])}, "
        f"5d {_pct(data['pct_change_5d'])}, 20d {_pct(data['pct_change_20d'])}, "
        f"volume vs 20d avg {vol_s}",
        "Fundamentals: "
        f"P/E {_fmt(f.get('pe'))}, market cap {mcap}, 52w range {rng_s}",
        "Recent news headlines (dated where known): "
        + ("; ".join(data.get("headlines", [])) or "none"),
    ]
    return "\n".join(lines)


def _generate(provider, model: str, system_prompt: str, user_prompt: str,
              schema: BatchVerdictSchema, timeout_ms: int, max_retries: int,
              retry_base_ms: int) -> tuple[str, bool, str | None, TokenUsage | None, int]:
    """One provider request with retry-on-transient-error. Returns
    (text, is_api_error, error_detail, usage, retries_used).

    THE shared call path: production watchlist/discovery (judge_batch) funnels
    every request through here, so retry behavior is identical by
    construction regardless of provider. Only ErrorClass.RETRYABLE
    ProviderErrors are retried, up to max_retries times, sleeping an
    exponential FULLY-jittered delay (uniform 0..base*2^n) between attempts;
    every attempt carries timeout_ms; every retry is logged with attempt
    number, error, and delay — no silent failures. retries_used is 0 on a
    first-attempt success.

    error_detail is the real exception (type + message) of the LAST attempt on
    failure — previously the caller logged a hardcoded "rate-limited/
    unavailable" guess, which hid whether the failure was a 429
    (ResourceExhausted), a timeout (Deadline Exceeded / read timeout), or a bad
    model name (NotFound). usage carries the token counts on success.
    """
    retries = 0
    while True:
        try:
            result = provider.generate(model=model, system_prompt=system_prompt,
                                        user_prompt=user_prompt, schema=schema,
                                        timeout_ms=timeout_ms)
            return result.text, False, None, result.usage, retries
        except ProviderError as e:
            if e.error_class != ErrorClass.RETRYABLE or retries >= max_retries:
                return "", True, e.detail, None, retries
            cap_s = retry_base_ms * (2 ** retries) / 1000.0
            delay_s = random.uniform(0, cap_s)
            retries += 1
            print(f"  [ai_judge] {model}: transient error ({e.detail}); retry "
                  f"{retries}/{max_retries} in {delay_s:.1f}s (cap {cap_s:.0f}s)")
            time.sleep(delay_s)


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


def _normalize_ticker(t: str) -> str:
    """Case-fold and strip a trailing .TO/.NS market suffix, so a ticker can be
    compared for identity regardless of case or suffix. Same suffix convention
    `ingest._market_for` already keys off — not a new one introduced here."""
    t = t.upper()
    for suffix in (".TO", ".NS"):
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _parse_batch(raw: str, tickers: list[str], model: str) -> dict | None:
    """Parse a JSON array of verdicts into {ticker: result}.

    Returns None only if no array could be extracted at all (caller retries).
    If an array is present but a given ticker is missing/invalid, that ticker
    gets a fail-safe Hold while the others still resolve.

    Positional-fallback attribution contract (§4.4a, DEEP-003 fix): when a
    requested ticker has no labeled object in the response, the array object
    at the same index is a candidate fallback ONLY when it corroborates the
    ticker being resolved — its own `ticker` field is absent (the model just
    forgot the label, in request order) or normalizes to the same ticker. A
    DIFFERENT normalized ticker at that index means the response array is
    misaligned (a dropped/shifted entry) — accepting it would misattribute
    another company's verdict/rationale under `parse_status: "ok"`, which is
    the one path that could fabricate rather than merely miss a signal. Any
    candidate that fails this check falls through to the same fail-safe Hold
    as every other parse failure.

    BUG-005 refinement: a normalized (suffix-stripped) match is only trusted
    when it's unambiguous — i.e. exactly one of THIS batch's DISTINCT
    requested tickers normalizes to that string. `_normalize_ticker` collapses
    distinct, real tickers that share a base symbol across markets (e.g.
    `ABC.TO` and `ABC.NS` both -> `ABC`); if two or more distinct requested
    tickers collide that way, a normalized-only match can't tell which one the
    object actually belongs to, so it must fail safe rather than guess (same
    "never fabricate, only miss" posture as the misaligned-array case above).
    The no-ticker-field case is unaffected by this guard: it never depends on
    normalization to identify a match in the first place.

    BUG-006 fix: ambiguity is counted over the DISTINCT requested tickers,
    not raw occurrences — the SAME ticker requested twice in one batch is not
    a cross-ticker collision, just a duplicate request, and must not count
    against itself. Additionally, a fail-safe result for a given ticker never
    overwrites an already-resolved ("ok") result for that same ticker — with
    a duplicate request, the two occurrences can independently reach
    different outcomes, and a later fail-safe silently clobbering an earlier
    good verdict (via `out`'s ticker-string keying) would throw away a
    legitimately available answer for no reason. An earlier "ok" is never
    replaced by a later "failed"; last-write-wins is otherwise unchanged
    (pre-existing behavior, not itself being redesigned here).
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

    by_ticker = {}
    for o in arr:
        if not (isinstance(o, dict) and o.get("ticker")):
            continue
        key = str(o["ticker"]).upper()
        if key in by_ticker:
            print(f"  [ai_judge] duplicate ticker '{key}' in model response; keeping the last occurrence")
        by_ticker[key] = o

    # How many DISTINCT requested tickers share each normalized form -- used
    # below to reject a normalized-only fallback match when it's ambiguous
    # which requested ticker the candidate actually belongs to (BUG-005: e.g.
    # ABC.TO and ABC.NS both normalize to "ABC"). Deduped by exact requested
    # string (case-folded) before counting, so the SAME ticker requested
    # twice in one batch counts once, not twice (BUG-006) -- that's a
    # duplicate request, not a second, distinct ticker colliding.
    distinct_requested = {x.upper() for x in tickers}
    normalized_counts = Counter(_normalize_ticker(x) for x in distinct_requested)

    out = {}
    for i, t in enumerate(tickers):
        o = by_ticker.get(t.upper())
        used_fallback = False
        if o is None and len(arr) == len(tickers) and isinstance(arr[i], dict):
            cand = arr[i]                        # positional fallback (same order requested)
            cand_ticker = cand.get("ticker")
            t_norm = _normalize_ticker(t)
            unambiguous_normalized_match = (
                cand_ticker and _normalize_ticker(str(cand_ticker)) == t_norm
                and normalized_counts[t_norm] == 1
            )
            if not cand_ticker or unambiguous_normalized_match:
                o, used_fallback = cand, True
        if used_fallback:
            print(f"  [ai_judge] positional fallback used for {t} (array index {i} had no "
                  f"matching 'ticker' label)")
        if isinstance(o, dict) and o.get("verdict") in VALID_VERDICTS and o.get("rationale"):
            conf = str(o.get("confidence", "")).lower()
            result = {"verdict": o["verdict"],
                      "confidence": conf if conf in VALID_CONFIDENCE else None,
                      "rationale": clip(o["rationale"], RATIONALE_MAX),
                      "raw_model_response": raw, "parse_status": "ok", "model_used": model}
        else:
            result = {**_FAIL_SAFE_PARSE, "raw_model_response": raw,
                      "parse_status": "failed", "model_used": model}
        # BUG-006: `out` is keyed by ticker string, so a ticker requested more
        # than once resolves independently at each occurrence and the later
        # one overwrites the earlier. A later fail-safe must never clobber an
        # already-resolved "ok" for the same ticker -- that would silently
        # discard a legitimately available answer. Last-write-wins is
        # otherwise unchanged (pre-existing behavior, not redesigned here).
        if result["parse_status"] == "failed" and out.get(t, {}).get("parse_status") == "ok":
            print(f"  [ai_judge] duplicate requested ticker '{t}' (index {i}): keeping the "
                  f"earlier resolved verdict, discarding a later fail-safe for the same ticker")
            continue
        out[t] = result
    return out


def judge_batch(items: list[dict], models: list[str] | None = None, provider=None) -> dict:
    """Judge every ticker in ONE AI call (cuts requests from N to 1 per run).

    items: list of {"data": <market data>, "position": <position|None>}.
    models: optional explicit model try-order (primary, backup...). Discovery
    passes its own 2.5 models here so it draws from separate free-tier quota
    buckets and can't eat into the watchlist's allowance; the watchlist call
    passes nothing and uses config.GEMINI_MODEL / _BACKUP.
    provider: optional AIProvider injection (tests only) — defaults to
    ai_provider.get_provider(config.AI_PROVIDER). No caller outside this
    module needs to pass it; run_hourly.py/run_discovery.py are unchanged.
    Returns {ticker: {verdict, confidence, rationale, raw_model_response,
    parse_status, model_used, usage, fallback_from, retry_count}}. retry_count
    is the batch-cumulative transport-retry tally from _generate (0 = clean
    first-attempt success). On a hard failure of every model every ticker fails
    safe to Hold, so a bad batch can only ever MISS signals, never fabricate one.
    """
    tickers = [it["data"]["ticker"] for it in items]
    if not items:
        return {}

    provider = provider or get_provider(config.AI_PROVIDER)
    print(f"  [ai_judge] call config: timeout={config.GEMINI_TIMEOUT_MS}ms, "
          f"max_retries={config.GEMINI_MAX_RETRIES}, "
          f"retry_base={config.GEMINI_RETRY_BASE_MS}ms (full jitter)")
    blocks = [f"--- Stock {i} ---\n{_ticker_block(it['data'], it['position'])}"
              for i, it in enumerate(items, 1)]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user = (f"Today's date: {today} (UTC). Use it to judge headline freshness "
            "and remember your own knowledge of these companies may be older.\n\n"
            + "\n\n".join(blocks) +
            "\n\nReturn a JSON array with one object per stock above, each "
            '{"ticker", "verdict", "confidence", "rationale"}, including every '
            "ticker exactly once.")

    def _enrich(parsed, usage, fallback_from, retry_count):
        # Stamp token usage + the (real) fallback error + the transport-retry
        # count onto every ticker's result. usage is the BATCH total for this
        # one API call — identical across the rows of a run, so sum it once per
        # run, not per ticker; retry_count is batch-cumulative the same way.
        # usage arrives from the provider as a TokenUsage dataclass; the
        # return contract stays the pre-existing plain dict.
        usage_dict = dataclasses.asdict(usage) if usage else None
        for v in parsed.values():
            v["usage"] = usage_dict
            v["fallback_from"] = fallback_from
            v["retry_count"] = retry_count
        return parsed

    last_raw = ""
    any_response = False   # did ANY model return text at all (vs pure API/quota errors)?
    notes: list[str] = []  # real errors of any model we fell back from
    total_retries = 0      # transport retries burned across every attempt this batch
    models = _models_to_try(models)
    last_model = models[0]

    for i, model in enumerate(models):
        last_model = model
        raw, api_err, err, usage, r = _generate(provider, model, BATCH_SYSTEM_PROMPT, user, _SCHEMA,
                                                  config.GEMINI_TIMEOUT_MS, config.GEMINI_MAX_RETRIES,
                                                  config.GEMINI_RETRY_BASE_MS)
        total_retries += r
        if api_err:
            last_raw = err or raw
            notes.append(f"{model}: {err}")
            nxt = f", trying {models[i + 1]}" if i + 1 < len(models) else ""
            print(f"  [ai_judge] {model} failed after {r} transport retries ({err}){nxt}")
            continue   # this model is exhausted; move to the backup, if any

        any_response = True
        fb = "; ".join(notes) or None
        parsed = _parse_batch(raw, tickers, model)
        if parsed is not None:
            return _enrich(parsed, usage, fb, total_retries)

        retry = user + "\n\nYour last reply was not a valid JSON array. Reply with ONLY the JSON array."
        raw2, _, _, usage2, r2 = _generate(provider, model, BATCH_SYSTEM_PROMPT, retry, _SCHEMA,
                                            config.GEMINI_TIMEOUT_MS, config.GEMINI_MAX_RETRIES,
                                            config.GEMINI_RETRY_BASE_MS)
        total_retries += r2
        parsed = _parse_batch(raw2, tickers, model)
        if parsed is not None:
            return _enrich(parsed, usage2 or usage, fb, total_retries)

        last_raw = f"{raw} || retry: {raw2}"
        notes.append(f"{model}: replied but unparseable")
        print(f"  [ai_judge] {model}: replied but never returned a parseable verdict array")

    # Every model in the list failed -> fail safe to Hold for all tickers.
    fail = _FAIL_SAFE_PARSE if any_response else _FAIL_SAFE_API
    status = "failed" if any_response else "api_error"
    fb = "; ".join(notes) or None
    return {t: {**fail, "raw_model_response": last_raw, "parse_status": status,
               "model_used": last_model, "usage": None, "fallback_from": fb,
               "retry_count": total_retries} for t in tickers}
