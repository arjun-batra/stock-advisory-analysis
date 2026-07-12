"""ai_judge.py — the AI judgment layer (FR9, FR10; REV-003 follow-up).

Covers judge_batch's control flow with `google.genai.Client` fully mocked
(never a real network/API call): the happy path (valid JSON parses straight
to verdicts), the parse-retry-once-then-fail-safe-to-Hold path, the
model-fallback path (primary exhausts its transport retries, backup
succeeds), and that `fallback_from`/`retry_count` land correctly on every
result. Per the task brief, this does not exhaustively test every
prompt-string detail — it focuses on the load-bearing fail-safe guarantee:
a bad batch can only ever MISS a signal, never fabricate one.
"""

import json

import config
from conftest import FakeAPIError, FakeGeminiResponse, FakeUsageMetadata

import ai_judge


def _item(ticker="AAPL", market="US"):
    return {
        "data": {
            "ticker": ticker, "market": market,
            "price": 100.0, "pct_change_1d": 1.0, "pct_change_5d": 2.0,
            "pct_change_20d": 3.0, "volume_vs_avg": 1.1,
            "fundamentals": {}, "headlines": [], "session_live": False,
            "volume_pro_rated": False,
        },
        "position": None,
    }


def _verdict_json(ticker="AAPL", verdict="Buy", confidence="high", rationale="strong setup"):
    return json.dumps([{"ticker": ticker, "verdict": verdict,
                        "confidence": confidence, "rationale": rationale}])


# --- happy path: valid JSON on the first attempt ------------------------------

def test_judge_batch_happy_path_parses_valid_json(mock_gemini):
    mock_gemini([FakeGeminiResponse(_verdict_json(), usage=FakeUsageMetadata(total=250))])

    result = ai_judge.judge_batch([_item("AAPL")], models=["primary-model"])

    assert result["AAPL"]["verdict"] == "Buy"
    assert result["AAPL"]["confidence"] == "high"
    assert result["AAPL"]["rationale"] == "strong setup"
    assert result["AAPL"]["parse_status"] == "ok"
    assert result["AAPL"]["model_used"] == "primary-model"
    assert result["AAPL"]["retry_count"] == 0
    assert result["AAPL"]["fallback_from"] is None
    assert result["AAPL"]["usage"]["total"] == 250


def test_judge_batch_happy_path_multi_ticker_all_resolve(mock_gemini):
    both = json.dumps([
        {"ticker": "AAPL", "verdict": "Buy", "confidence": "high", "rationale": "a"},
        {"ticker": "MSFT", "verdict": "Sell", "confidence": "low", "rationale": "b"},
    ])
    mock_gemini([FakeGeminiResponse(both)])

    result = ai_judge.judge_batch([_item("AAPL"), _item("MSFT")], models=["primary-model"])

    assert result["AAPL"]["verdict"] == "Buy"
    assert result["MSFT"]["verdict"] == "Sell"


def test_judge_batch_empty_items_returns_empty_dict():
    assert ai_judge.judge_batch([]) == {}


# --- parse-retry-once, then fail safe to Hold ---------------------------------

def test_judge_batch_retries_parse_once_then_fails_safe_to_hold(mock_gemini):
    """Two consecutive unparseable replies from the ONLY model in the try-order:
    judge_batch must retry the parse exactly once (per its docstring) and then
    fail every ticker safe to Hold -- never crash, never fabricate a verdict."""
    client = mock_gemini([
        FakeGeminiResponse("this is not JSON at all"),
        FakeGeminiResponse("still not JSON"),
    ])

    result = ai_judge.judge_batch([_item("AAPL")], models=["primary-model"])

    assert result["AAPL"]["verdict"] == "Hold"
    assert result["AAPL"]["confidence"] is None
    assert result["AAPL"]["parse_status"] == "failed"
    assert "parsed" in result["AAPL"]["rationale"].lower() or "fail-safe" in result["AAPL"]["rationale"].lower()
    # exactly two calls were made: the original prompt + one parse-retry prompt
    assert len(client.models.calls) == 2
    assert result["AAPL"]["fallback_from"] == "primary-model: replied but unparseable"


def test_judge_batch_invalid_input_missing_ticker_in_reply_fails_safe_for_that_ticker(mock_gemini):
    """A reply that parses as JSON but never mentions one of the requested
    tickers must fail THAT ticker safe to Hold without touching the others."""
    only_aapl = json.dumps([{"ticker": "AAPL", "verdict": "Buy",
                             "confidence": "high", "rationale": "ok"}])
    mock_gemini([FakeGeminiResponse(only_aapl)])

    result = ai_judge.judge_batch([_item("AAPL"), _item("MSFT")], models=["primary-model"])

    assert result["AAPL"]["verdict"] == "Buy"
    assert result["AAPL"]["parse_status"] == "ok"
    assert result["MSFT"]["verdict"] == "Hold"
    assert result["MSFT"]["parse_status"] == "failed"


# --- model fallback: primary exhausts transport retries, backup succeeds -----

def test_judge_batch_falls_back_to_backup_model_after_primary_exhausts_retries(mock_gemini):
    """Primary raises a retryable transport error on every attempt (initial +
    config.GEMINI_MAX_RETRIES retries), so judge_batch must move on to the
    backup model, which then succeeds. fallback_from must name the primary's
    real error, and retry_count must equal the transport retries actually
    burned (all against the primary; the backup succeeds on its first try)."""
    primary_failures = [FakeAPIError(code=503, status="UNAVAILABLE", msg="high demand")
                         for _ in range(config.GEMINI_MAX_RETRIES + 1)]
    client = mock_gemini(primary_failures + [FakeGeminiResponse(_verdict_json())])

    result = ai_judge.judge_batch([_item("AAPL")], models=["primary-model", "backup-model"])

    assert result["AAPL"]["verdict"] == "Buy"
    assert result["AAPL"]["parse_status"] == "ok"
    assert result["AAPL"]["model_used"] == "backup-model"
    assert result["AAPL"]["retry_count"] == config.GEMINI_MAX_RETRIES
    assert result["AAPL"]["fallback_from"] is not None
    assert "primary-model:" in result["AAPL"]["fallback_from"]
    # primary attempted (max_retries + 1) times, backup attempted once
    assert client.models.calls.count("primary-model") == config.GEMINI_MAX_RETRIES + 1
    assert client.models.calls.count("backup-model") == 1


def test_judge_batch_non_retryable_error_does_not_retry_before_falling_back(mock_gemini):
    """A deterministic 4xx (e.g. bad model name) must NOT be retried -- retrying
    a deterministic failure just burns quota. Exactly one attempt per model."""
    client = mock_gemini([
        FakeAPIError(code=404, status="NOT_FOUND", msg="model not found"),
        FakeGeminiResponse(_verdict_json()),
    ])

    result = ai_judge.judge_batch([_item("AAPL")], models=["bad-model", "backup-model"])

    assert result["AAPL"]["verdict"] == "Buy"
    assert result["AAPL"]["retry_count"] == 0
    assert client.models.calls.count("bad-model") == 1


# --- hard failure: every model fails -> fail-safe to Hold for every ticker ---

def test_judge_batch_every_model_failing_fails_safe_to_hold_with_api_error_status(mock_gemini):
    """When no model ever returns any text at all (pure transport/API failure,
    as opposed to a parseable-but-wrong reply), parse_status must be
    'api_error' (not 'failed') and every ticker must fail safe to Hold --
    a hard outage can only ever miss signals, never fabricate one."""
    failures = [FakeAPIError(code=404, status="NOT_FOUND") for _ in range(2)]
    mock_gemini(failures)

    result = ai_judge.judge_batch([_item("AAPL"), _item("MSFT")],
                                   models=["primary-model", "backup-model"])

    for t in ("AAPL", "MSFT"):
        assert result[t]["verdict"] == "Hold"
        assert result[t]["parse_status"] == "api_error"
    assert "primary-model:" in result["AAPL"]["fallback_from"]
    assert "backup-model:" in result["AAPL"]["fallback_from"]
