"""Provider-neutral AI interface (FR33) — see docs/design/operational-controls.md
§14 for the hand-rolled-vs-LiteLLM decision (already made, not re-litigated here)
and the exact interface shape below.

`GeminiProvider` is the sole live implementation. `ai_judge.py` talks ONLY to
`AIProvider`/`ProviderResult`/`ProviderError` — no `google.genai` import (and no
Gemini-SDK error classification) lives anywhere outside this file.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import httpx
from google import genai
from google.genai import types

import config


@dataclass(frozen=True)
class TokenUsage:
    prompt: int | None
    output: int | None
    thoughts: int | None      # provider-specific ("thinking" tokens); None if not applicable
    total: int | None


@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: TokenUsage | None


class ErrorClass(str, Enum):
    RETRYABLE = "retryable"   # transient transport/capacity error — safe to retry
    FATAL = "fatal"           # deterministic (bad request/auth/model name) — retrying wastes nothing but time


class ProviderError(Exception):
    """The ONLY exception type ai_judge.py catches from a provider. Every
    AIProvider implementation must translate its SDK's raw exceptions into
    this, classified via ErrorClass, so ai_judge.py never needs a
    provider-specific except clause."""

    def __init__(self, detail: str, error_class: "ErrorClass"):
        super().__init__(detail)
        self.detail = detail
        self.error_class = error_class


@dataclass(frozen=True)
class BatchVerdictSchema:
    """Provider-neutral description of the expected batch response shape —
    the array-of-{ticker,verdict,confidence,rationale} contract. Each
    AIProvider implementation is responsible for translating this into its
    own SDK's schema/response-format type internally."""
    verdicts: tuple[str, ...] = ("Buy", "Sell", "Hold")
    confidences: tuple[str, ...] = ("high", "medium", "low")


class AIProvider(ABC):
    @abstractmethod
    def generate(self, *, model: str, system_prompt: str, user_prompt: str,
                 schema: BatchVerdictSchema, timeout_ms: int) -> ProviderResult:
        """One request/response. Must raise ProviderError (never a bare SDK
        exception) on any failure."""


# Errors worth retrying are the TRANSIENT transport/capacity ones only
# (2026-07-07 outage: 503 UNAVAILABLE "high demand" and 504 DEADLINE_EXCEEDED,
# interleaved with successes all through the window; 429 is the rate-limit case
# the old single fixed-delay retry targeted). Any other 4xx (bad request, auth,
# bad model name) is deterministic — retrying just burns quota. A 200 whose
# JSON doesn't parse is a prompt problem, not a transport one: ai_judge.py's own
# parse-retry handles that, this classifier never sees it.
_RETRYABLE_CODES = {429, 503, 504}
_RETRYABLE_STATUSES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED"}


def _classify(e: Exception) -> ErrorClass:
    """The SDK raises APIError carrying .code (HTTP int) and .status (canonical
    name); a CLIENT-side deadline (timeout_ms expiring locally) surfaces as an
    httpx timeout — the SDK's transport — or a bare TimeoutError."""
    if isinstance(e, (httpx.TimeoutException, TimeoutError)):
        return ErrorClass.RETRYABLE
    if (getattr(e, "code", None) in _RETRYABLE_CODES
            or getattr(e, "status", None) in _RETRYABLE_STATUSES):
        return ErrorClass.RETRYABLE
    return ErrorClass.FATAL


def _usage(resp) -> TokenUsage | None:
    """Pull token counts off a response's usage_metadata, if present."""
    um = getattr(resp, "usage_metadata", None)
    if um is None:
        return None
    return TokenUsage(
        prompt=getattr(um, "prompt_token_count", None),
        output=getattr(um, "candidates_token_count", None),
        thoughts=getattr(um, "thoughts_token_count", None),
        total=getattr(um, "total_token_count", None),
    )


def _response_schema(schema: BatchVerdictSchema):
    """Structural enforcement of the reply shape (belt to the prompt's braces):
    a typed schema (constrained decoding, not just a JSON-mode flag — §14.1
    point 5) guarantees the verdict/confidence enums and required keys, so
    ai_judge's parse-retry path should almost never fire."""
    return types.Schema(
        type=types.Type.ARRAY,
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "ticker": types.Schema(type=types.Type.STRING),
                "verdict": types.Schema(type=types.Type.STRING, enum=list(schema.verdicts)),
                "confidence": types.Schema(type=types.Type.STRING, enum=list(schema.confidences)),
                "rationale": types.Schema(type=types.Type.STRING),
            },
            required=["ticker", "verdict", "confidence", "rationale"],
            property_ordering=["ticker", "verdict", "confidence", "rationale"],
        ),
    )


def _client(api_key: str, timeout_ms: int):
    """Client with an explicit, generous request timeout.

    Root cause of the 3.5-flash -> lite fallbacks (observed live): 3.5-flash
    *did* respond (tokens were billed on Google's dashboard) but slowly, and the
    SDK's default client timeout fired first — so a completed, token-charged
    response was discarded and the call fell back to lite. A high explicit
    timeout lets a slow-but-valid response land instead of being thrown away.
    """
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def generate(self, *, model: str, system_prompt: str, user_prompt: str,
                 schema: BatchVerdictSchema, timeout_ms: int) -> ProviderResult:
        client = _client(self._api_key, timeout_ms)
        cfg = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=_response_schema(schema),
            temperature=0.2,
        )
        try:
            resp = client.models.generate_content(model=model, contents=user_prompt, config=cfg)
            return ProviderResult(text=(resp.text or "").strip(), usage=_usage(resp))
        except Exception as e:
            detail = f"{type(e).__name__}: {str(e)[:200]}"
            raise ProviderError(detail, _classify(e)) from e


def get_provider(name: str | None = None) -> AIProvider:
    name = (name or config.AI_PROVIDER).lower()
    providers = {"gemini": lambda: GeminiProvider(config.GEMINI_API_KEY)}
    if name not in providers:
        raise SystemExit(f"Unknown AI_PROVIDER '{name}'; supported: {sorted(providers)}")
    return providers[name]()
