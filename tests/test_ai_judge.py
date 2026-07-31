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
from collections import Counter as _Counter

import config
from conftest import FakeAPIError, FakeGeminiResponse, FakeUsageMetadata

import ai_judge
import state


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
    # BUG-006 fix-cycle-2 (RESOLVED 2026-07-30): normalized_counts is now built
    # over DISTINCT requested tickers, so this same-ticker duplicate no longer
    # inflates its own count and the second occurrence's legitimate bare-'ABC'
    # match is accepted rather than wrongly rejected as "ambiguous".
    assert out["ABC.TO"]["parse_status"] == "ok", (
        "BUG-006: duplicate-ticker-in-batch causes the guard to reject a "
        "legitimate normalized match as 'ambiguous' (Counter counts the "
        "same requested ticker's own duplicate, not a distinct colliding "
        "ticker) -- see docs/test-report.md open bugs")


# --- BUG-006 fix-cycle-2 re-test: counting fix + overwrite guard --------------

def test_parse_batch_duplicate_alongside_genuine_collision_still_fails_safe(capsys):
    """Regression guard for the highest-stakes assertion in the fix-cycle-2
    re-test: the BUG-006 counting fix (dedup by DISTINCT requested ticker
    before building normalized_counts) must not accidentally swallow a
    genuine cross-ticker collision when a duplicate request is ALSO present
    in the same batch. Batch: ABC.TO requested twice (duplicate) plus ABC.NS
    once (a genuinely distinct, real ticker colliding on the same normalized
    base 'ABC' -- BUG-005's own scenario). distinct_requested = {ABC.TO,
    ABC.NS}, so normalized_counts['ABC'] == 2 for a REAL reason (two distinct
    tickers), not an artifact of the duplicate. The second ABC.TO occurrence's
    bare-'ABC' candidate must still fail safe as ambiguous -- if dedup had
    over-corrected (e.g. deduping across distinct tickers, or by normalized
    form instead of exact string), this would wrongly resolve 'ok' and
    reopen BUG-005's fabrication path."""
    raw = json.dumps([
        {"verdict": "Buy", "confidence": "high", "rationale": "first-ABC.TO-unlabeled"},
        {"ticker": "ABC", "verdict": "Sell", "confidence": "low", "rationale": "second-ABC.TO-bare-ambiguous"},
        {"ticker": "ABC.NS", "verdict": "Hold", "confidence": "medium", "rationale": "abcns-direct"},
    ])

    out = ai_judge._parse_batch(raw, ["ABC.TO", "ABC.TO", "ABC.NS"], "test-model")

    # First ABC.TO occurrence resolves legitimately (no-label fallback, never
    # depends on normalization/ambiguity).
    # Second ABC.TO occurrence's bare-'ABC' candidate is genuinely ambiguous
    # against the real ABC.NS collision and must fail safe -- but the
    # overwrite guard means the surviving out["ABC.TO"] is still the FIRST
    # occurrence's good result, not clobbered by the second's fail-safe.
    assert out["ABC.TO"]["parse_status"] == "ok"
    assert out["ABC.TO"]["rationale"] == "first-ABC.TO-unlabeled"
    assert out["ABC.NS"]["parse_status"] == "ok"
    assert out["ABC.NS"]["rationale"] == "abcns-direct"
    log = capsys.readouterr().out
    assert "duplicate requested ticker 'ABC.TO' (index 1): keeping the earlier resolved verdict" in log


def test_parse_batch_overwrite_guard_reachable_independent_of_counting_fix(capsys):
    """Confirms dev's reachability claim rather than accepting it on word: the
    overwrite guard (a later fail-safe never clobbers an already-resolved
    'ok' for the same ticker key) fires via a mechanism OTHER than the
    counting bug the same fix cycle just closed -- a genuine cross-ticker
    ambiguity (see test above) is sufficient to make the second occurrence
    of a duplicate request fail safe even with correct counting, so the
    guard is not dead code."""
    raw = json.dumps([
        {"verdict": "Buy", "confidence": "high", "rationale": "first-ABC.TO-unlabeled"},
        {"ticker": "ABC", "verdict": "Sell", "confidence": "low", "rationale": "second-ABC.TO-bare-ambiguous"},
        {"ticker": "ABC.NS", "verdict": "Hold", "confidence": "medium", "rationale": "abcns-direct"},
    ])

    out = ai_judge._parse_batch(raw, ["ABC.TO", "ABC.TO", "ABC.NS"], "test-model")

    assert out["ABC.TO"]["parse_status"] == "ok"
    # If the guard were dead code (unreachable given the counting fix), the
    # second occurrence's fail-safe would have overwritten the first, and
    # this would be "failed" instead.
    assert out["ABC.TO"]["rationale"] != "second-ABC.TO-bare-ambiguous"
    assert "keeping the earlier resolved verdict, discarding a later fail-safe" in capsys.readouterr().out


def test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere(capsys):
    """Documents (does not endorse) the scoping decision dev made and qa
    reviewed in the BUG-006 fix-cycle-2 handoff: when a duplicate ticker
    request's two occurrences BOTH resolve legitimately ('ok') but to
    DIFFERENT verdicts, the overwrite guard does not apply (it only protects
    ok-over-ok is unguarded, deliberately left out of scope this increment
    per qa's own bug report and the ripple cost of changing `_parse_batch`'s
    ticker-keyed return contract). The later occurrence silently wins with
    NO log line distinguishing this from an ordinary single-resolution --
    this test locks in that current behavior as a known, tracked gap (not a
    fix-cycle-2 regression) so a future change is deliberate, not accidental."""
    raw = json.dumps([
        {"verdict": "Buy", "confidence": "high", "rationale": "first-occ-buy"},
        {"verdict": "Sell", "confidence": "low", "rationale": "second-occ-sell"},
    ])

    out = ai_judge._parse_batch(raw, ["ABC.TO", "ABC.TO"], "test-model")

    assert out["ABC.TO"]["parse_status"] == "ok"
    # Last-write-wins: the SECOND occurrence's legitimate verdict silently
    # overwrites the FIRST's, discarding a divergent, equally-legitimate
    # verdict with no trace in the log beyond the two ordinary
    # "positional fallback used" lines (no divergence-specific warning).
    assert out["ABC.TO"]["verdict"] == "Sell"
    assert out["ABC.TO"]["rationale"] == "second-occ-sell"
    log = capsys.readouterr().out
    assert log.count("positional fallback used for ABC.TO") == 2
    assert "discarding" not in log  # only the failed-over-ok guard logs a discard


# --- _ticker_block with a HELD position (FR11/FR29, REV-113, INC-10 fix round #2) ---
# Coverage gap dev flagged against itself in the fix-cycle-2 handoff: no existing test
# exercised _ticker_block with a non-None position at all before these were added. Both
# positions below are built via state.build_position so the whole real data/position
# contract (including the new currency_mismatched flag) is exercised, not a hand-rolled
# dict that could drift from what build_position actually returns.

def _held_data(ticker="SHOP.TO", market="TSX", price=68.0, fundamentals_currency="CAD"):
    return {
        "ticker": ticker, "market": market,
        "price": price, "pct_change_1d": 1.0, "pct_change_5d": 2.0,
        "pct_change_20d": 3.0, "volume_vs_avg": 1.1,
        "fundamentals": {"currency": fundamentals_currency},
        "headlines": [], "session_live": False, "volume_pro_rated": False,
    }


def test_ticker_block_currency_mismatch_omits_cost_basis_and_states_not_comparable(capsys):
    """REV-113: a holding whose currency disagrees with the ticker's own fundamentals
    currency must not let cost_basis and price sit side by side (raw or otherwise) --
    the block must state plainly that no gain/loss should be computed."""
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "USD"}
    data = _held_data()
    position = state.build_position(holding, data)
    assert position["currency_mismatched"] is True  # sanity: the fixture is a real mismatch
    capsys.readouterr()  # discard build_position's WARNING log, not under test here

    block = ai_judge._ticker_block(data, position)

    assert "Cost basis:" not in block  # the labeled figure, not the prose mentioning the concept
    assert "50.0" not in block
    assert "Unrealized P/L" not in block
    assert "not comparable" in block
    assert "do not compute or state an unrealized" in block
    # Both currencies named so the model understands *why* they're withheld.
    assert "USD" in block
    assert "CAD" in block
    # Shares are not currency-denominated -- still fine to show.
    assert "Shares: 10" in block


def test_ticker_block_currency_mismatch_leaks_no_cost_basis_figure_by_any_route(capsys):
    """The point of REV-113 is that a model cannot derive a P/L from mismatched-currency
    inputs -- not just that one line's wording changed. Walk the WHOLE block: the raw
    cost_basis number must not survive anywhere (e.g. smuggled into another field), and
    the price that legitimately remains (for price/volume analysis) must be unambiguously
    labeled with the fundamentals currency, not left bare next to the withheld cost basis."""
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "USD"}
    data = _held_data(price=68.42, fundamentals_currency="CAD")
    position = state.build_position(holding, data)
    capsys.readouterr()

    block = ai_judge._ticker_block(data, position)

    # The distinctive cost-basis figure (50.0) must not appear anywhere in the block --
    # not on the held-position line (already checked above) and not smuggled into any
    # other field (fundamentals/price/volume lines etc.).
    assert "50.0" not in block
    assert "50" not in block
    # The price DOES legitimately remain, but only in the unrelated Price/volume line,
    # and only ever labeled with the fundamentals currency (CAD here) -- never bare next
    # to an unlabeled number a model could pair it with.
    price_lines = [ln for ln in block.splitlines() if "68.42" in ln]
    assert len(price_lines) == 1
    assert price_lines[0].startswith("Price/volume")
    assert "CAD" in price_lines[0]


def test_ticker_block_currency_mismatch_fails_on_pre_fix_behavior():
    """Guard against regression to the pre-REV-113 rendering: reconstructs the exact
    pre-fix _ticker_block held-position line (cost_basis and price on one unlabeled
    line, pl_pct suppressed to n/a but the two raw figures still adjacent) and confirms
    the CURRENT code no longer does that for a mismatch. This is the same assertion as
    the test above; kept separate and documented so a future refactor that silently
    reintroduces the old branch is caught by name."""
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "USD"}
    data = _held_data()
    position = state.build_position(holding, data)
    block = ai_judge._ticker_block(data, position)
    # The old (pre-fix) line shape would have been:
    #   "  Shares: 10, Cost basis: 50.0 USD, Current price: 68.0, Unrealized P/L: n/a"
    # None of that shape should be present now.
    assert "Cost basis: 50.0 USD" not in block
    assert "Unrealized P/L: n/a" not in block


def test_ticker_block_agreeing_currency_position_line_unchanged():
    """Held-position block for a NON-mismatched holding must be exactly the pre-REV-113
    shape (byte-identical wording), proving the fix only branches on an actual mismatch."""
    holding = {"shares": 10, "cost_basis": 50.0, "currency": "CAD"}
    data = _held_data(price=60.0, fundamentals_currency="CAD")
    position = state.build_position(holding, data)
    assert position["currency_mismatched"] is False

    block = ai_judge._ticker_block(data, position)

    assert "  Shares: 10, Cost basis: 50.0 CAD, Current price: 60.0, Unrealized P/L: 20.0%" in block
    assert "not comparable" not in block


# --- _positional_candidate: direct unit coverage of the corroboration gate ---
# (C901 refactor, commit 0a24460) DEEP-003 and BUG-005 both live entirely inside
# this one now-named helper. It was previously only reachable indirectly through
# _parse_batch's full 16-branch body; testing it directly pins the rule's exact
# boundary independent of the surrounding extraction/dict-building logic, so a
# future edit to _parse_batch's plumbing can't silently change this rule's
# semantics without a directly-failing test.

def test_positional_candidate_rejects_length_mismatch():
    """Array length must equal the requested-ticker count, or there's no
    positional correspondence to trust at all."""
    arr = [{"verdict": "Buy"}]
    cand, used = ai_judge._positional_candidate(0, "AAPL", arr, ["AAPL", "MSFT"], _Counter())
    assert cand is None and used is False


def test_positional_candidate_accepts_unlabeled_object_in_request_order():
    """DEEP-003 legitimate path: the model just forgot the 'ticker' label."""
    arr = [{"verdict": "Buy", "rationale": "no label"}]
    cand, used = ai_judge._positional_candidate(0, "AAPL", arr, ["AAPL"], _Counter())
    assert used is True and cand == arr[0]


def test_positional_candidate_rejects_a_different_labeled_ticker_at_the_same_index():
    """DEEP-003 misattribution case: the object at this index carries SOMEONE
    ELSE's ticker label -- never trust it as a stand-in, even positionally."""
    arr = [{"ticker": "MSFT", "verdict": "Buy", "rationale": "wrong company"}]
    cand, used = ai_judge._positional_candidate(0, "AAPL", arr, ["AAPL"], _Counter({"AAPL": 1}))
    assert cand is None and used is False


def test_positional_candidate_accepts_unambiguous_normalized_match():
    """BUG-005 legitimate path: suffix-stripped match, and this normalized form
    belongs to exactly one distinct requested ticker this batch."""
    arr = [{"ticker": "ABC", "verdict": "Buy", "rationale": "base symbol"}]
    counts = _Counter({"ABC": 1})
    cand, used = ai_judge._positional_candidate(0, "ABC.TO", arr, ["ABC.TO"], counts)
    assert used is True and cand == arr[0]


def test_positional_candidate_rejects_ambiguous_normalized_match():
    """BUG-005 fix: two DISTINCT requested tickers normalize to the same base
    symbol -- a normalized-only match can't tell which one it belongs to, so it
    must fail safe rather than guess."""
    arr = [{"ticker": "ABC", "verdict": "Buy", "rationale": "which market?"}]
    counts = _Counter({"ABC": 2})   # ABC.TO and ABC.NS both normalize to "ABC"
    cand, used = ai_judge._positional_candidate(0, "ABC.TO", arr, ["ABC.TO", "ABC.NS"], counts)
    assert cand is None and used is False
