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


# --- DEEP-003 / §4.4a: positional-fallback attribution contract --------------
# _parse_batch is exercised directly (not via judge_batch/mock_gemini) since
# these are unit-level tests of the attribution logic itself, matching
# increment-plan.md INC-9 AC1's own framing ("a qa test feeds _parse_batch...").

def test_parse_batch_misattributed_shifted_array_fails_safe_not_borrowed(capsys):
    """The exact DEEP-003 evidence shape: request [AAPL, MSFT, TSLA], the model
    drops TSLA and hallucinates an extra ticker in its slot -> response
    [AAPL, XOM, MSFT]. TSLA's positional slot (index 2) actually holds MSFT's
    own labeled object -- accepting it would misattribute MSFT's verdict/
    rationale onto TSLA under parse_status='ok'. TSLA must fail safe instead;
    MSFT (which has its own direct label) must still resolve correctly."""
    raw = json.dumps([
        {"ticker": "AAPL", "verdict": "Buy", "confidence": "high", "rationale": "aapl-reason"},
        {"ticker": "XOM", "verdict": "Sell", "confidence": "low", "rationale": "xom-reason (hallucinated)"},
        {"ticker": "MSFT", "verdict": "Hold", "confidence": "medium", "rationale": "msft-reason"},
    ])

    out = ai_judge._parse_batch(raw, ["AAPL", "MSFT", "TSLA"], "test-model")

    # TSLA must NOT come back as MSFT under parse_status="ok".
    assert out["TSLA"]["parse_status"] == "failed"
    assert out["TSLA"]["verdict"] == "Hold"
    assert out["TSLA"]["rationale"] != "msft-reason"
    assert "msft-reason" not in out["TSLA"]["rationale"]
    # MSFT itself still resolves normally via its own direct label.
    assert out["MSFT"]["parse_status"] == "ok"
    assert out["MSFT"]["verdict"] == "Hold"
    assert out["MSFT"]["rationale"] == "msft-reason"
    assert out["AAPL"]["parse_status"] == "ok"
    # No fallback was legitimately used for TSLA -- the candidate was rejected,
    # not accepted, so the log line must not fire for it.
    assert "positional fallback used for TSLA" not in capsys.readouterr().out


def test_parse_batch_legitimate_fallback_missing_ticker_label_still_resolves(capsys):
    """A same-order response where one object simply has no 'ticker' label at
    all (the model forgot the label, not a misaligned array) is the
    legitimate case the fallback exists to serve -- that ticker must still
    resolve positionally with parse_status='ok', and the log line must fire."""
    raw = json.dumps([
        {"ticker": "AAPL", "verdict": "Buy", "confidence": "high", "rationale": "aapl-reason"},
        {"verdict": "Sell", "confidence": "low", "rationale": "msft-reason-unlabeled"},
        {"ticker": "TSLA", "verdict": "Hold", "confidence": "medium", "rationale": "tsla-reason"},
    ])

    out = ai_judge._parse_batch(raw, ["AAPL", "MSFT", "TSLA"], "test-model")

    assert out["MSFT"]["parse_status"] == "ok"
    assert out["MSFT"]["verdict"] == "Sell"
    assert out["MSFT"]["rationale"] == "msft-reason-unlabeled"
    assert "positional fallback used for MSFT" in capsys.readouterr().out


def test_parse_batch_normalize_ticker_suffix_stripping_must_not_collide_cross_market():
    """_normalize_ticker strips a trailing .TO/.NS before comparing (§4.4a), so
    two DIFFERENT watchlist tickers that share a base symbol across markets
    (e.g. ABC.TO and ABC.NS) normalize to the identical string 'ABC'. Here
    ABC.TO has its own direct label at array index 1; ABC.NS has no object of
    its own and falls to the positional-fallback check at its own index (1),
    which is ABC.TO's already-consumed object. If the normalized-ticker
    corroboration check treats that as a match, ABC.NS would silently inherit
    ABC.TO's verdict/rationale under parse_status='ok' -- a cross-market
    fabrication the DEEP-003 fix's own invariant ("never fabricate, only
    miss") forbids just as much as the single-market case AC1 covers.
    ABC.NS has no object of its own; it must fail safe, not borrow ABC.TO's."""
    raw = json.dumps([
        {"verdict": "Buy", "confidence": "high", "rationale": "unlabeled-object"},
        {"ticker": "ABC.TO", "verdict": "Sell", "confidence": "low", "rationale": "abc-to-reason"},
    ])

    out = ai_judge._parse_batch(raw, ["ABC.TO", "ABC.NS"], "test-model")

    assert out["ABC.TO"]["parse_status"] == "ok"
    assert out["ABC.TO"]["rationale"] == "abc-to-reason"
    assert out["ABC.NS"]["parse_status"] == "failed", (
        "BUG: ABC.NS resolved parse_status='ok' by borrowing ABC.TO's verdict/"
        "rationale via _normalize_ticker's .TO/.NS-stripping collision -- see "
        "docs/test-report.md open bugs")


# --- BUG-005 fix-cycle-1: unambiguity-guard edge probes -----------------------
# The guard (`normalized_counts[t_norm] == 1`) is per-batch, so its behavior
# depends on batch composition. These probe the guard's own new edges rather
# than re-testing BUG-005's original repro (covered above).

def test_parse_batch_wellformed_response_with_ambiguous_pair_present_is_unaffected(capsys):
    """A batch containing the ABC.TO/ABC.NS collision pair, but where the model
    replies with a fully-labeled, well-formed response (every ticker has its
    own direct-label object) never needs the fallback at all. The guard must
    not reject or otherwise disturb a case that never needed rescuing -- both
    tickers resolve via their own direct label, and no fallback log line
    fires for either."""
    raw = json.dumps([
        {"ticker": "ABC.TO", "verdict": "Buy", "confidence": "high", "rationale": "to-reason"},
        {"ticker": "ABC.NS", "verdict": "Sell", "confidence": "low", "rationale": "ns-reason"},
    ])

    out = ai_judge._parse_batch(raw, ["ABC.TO", "ABC.NS"], "test-model")

    assert out["ABC.TO"]["parse_status"] == "ok"
    assert out["ABC.TO"]["rationale"] == "to-reason"
    assert out["ABC.NS"]["parse_status"] == "ok"
    assert out["ABC.NS"]["rationale"] == "ns-reason"
    log = capsys.readouterr().out
    assert "positional fallback used for" not in log


def test_parse_batch_single_ticker_batch_bare_normalized_match_still_resolves(capsys):
    """A single-ticker batch requesting ABC.TO, answered with a bare 'ABC'
    ticker field, is the unambiguous case §4.4a exists to serve (normalized
    form has exactly one candidate in the batch) -- must still resolve, not
    be caught by the ambiguity guard meant for cross-ticker collisions."""
    raw = json.dumps([{"ticker": "ABC", "verdict": "Buy", "confidence": "high",
                       "rationale": "bare-abc-answer"}])

    out = ai_judge._parse_batch(raw, ["ABC.TO"], "test-model")

    assert out["ABC.TO"]["parse_status"] == "ok"
    assert out["ABC.TO"]["rationale"] == "bare-abc-answer"
    assert "positional fallback used for ABC.TO" in capsys.readouterr().out


def test_parse_batch_three_way_base_symbol_collision_normalized_candidate_fails_safe():
    """Three requested tickers share the same base symbol (ABC.TO, ABC.NS,
    ABC). ABC.TO and ABC (bare) both resolve via their own exact direct
    label. ABC.NS has no object of its own and falls to the positional
    fallback, whose candidate at that index carries an explicit `ticker`
    field ('ABC.TO', already consumed by ABC.TO's own direct match) that
    only normalizes -- not exactly matches -- the ticker being resolved.
    With 3 requested tickers sharing the normalized form 'ABC'
    (normalized_counts['ABC'] == 3), this must fail safe, not guess which of
    the 3 the candidate belongs to."""
    raw = json.dumps([
        {"verdict": "Buy", "confidence": "high", "rationale": "abcto-unlabeled"},
        {"ticker": "ABC.TO", "verdict": "Sell", "confidence": "low", "rationale": "abcns-borrowed-abcto-label"},
        {"ticker": "ABC", "verdict": "Hold", "confidence": "medium", "rationale": "bare-abc-direct"},
    ])

    out = ai_judge._parse_batch(raw, ["ABC.TO", "ABC.NS", "ABC"], "test-model")

    assert out["ABC.TO"]["parse_status"] == "ok"
    assert out["ABC.TO"]["rationale"] == "abcns-borrowed-abcto-label"
    assert out["ABC"]["parse_status"] == "ok"
    assert out["ABC"]["rationale"] == "bare-abc-direct"
    assert out["ABC.NS"]["parse_status"] == "failed", (
        "3-way base-symbol collision: ABC.NS must fail safe, not borrow "
        "ABC.TO's verdict/rationale via the normalized-field candidate.")


def test_parse_batch_duplicate_ticker_in_requested_batch_drops_legitimate_second_match():
    """BUG-006 repro (new, found probing the BUG-005 guard's own edge, not a
    variation of BUG-005 itself): when the SAME ticker string appears twice
    in the requested `tickers` list (a duplicate request, not two different
    tickers), `normalized_counts` counts it twice purely because of the
    duplicate -- there is no genuine cross-ticker collision. The second
    occurrence's legitimate bare-ticker normalized match is then wrongly
    rejected as 'ambiguous' by the guard, and because `out` is keyed by
    ticker string, that rejection OVERWRITES the first occurrence's already
    -- correctly -- resolved entry. Expected: both occurrences should be
    unaffected by a same-ticker duplicate (the guard's ambiguity concept
    only makes sense across DISTINCT normalized forms); actual: the final
    `out['ABC.TO']` is a fail-safe Hold, discarding a legitimately available
    answer."""
    raw = json.dumps([
        {"ticker": "AAPL", "verdict": "Buy", "confidence": "high", "rationale": "aapl-reason"},
        {"verdict": "Sell", "confidence": "low", "rationale": "first-ABC.TO-unlabeled"},
        {"ticker": "ABC", "verdict": "Hold", "confidence": "medium", "rationale": "second-ABC.TO-bare-answer"},
    ])

    out = ai_judge._parse_batch(raw, ["AAPL", "ABC.TO", "ABC.TO"], "test-model")

    assert out["AAPL"]["parse_status"] == "ok"
    # BUG-006: this currently fails -- the surviving out["ABC.TO"] entry is a
    # fail-safe Hold (the second occurrence's legitimate bare-'ABC' match was
    # rejected as "ambiguous" purely because the ticker was requested twice),
    # clobbering the first occurrence's own correctly-resolved entry.
    assert out["ABC.TO"]["parse_status"] == "ok", (
        "BUG-006: duplicate-ticker-in-batch causes the guard to reject a "
        "legitimate normalized match as 'ambiguous' (Counter counts the "
        "same requested ticker's own duplicate, not a distinct colliding "
        "ticker) -- see docs/test-report.md open bugs")
