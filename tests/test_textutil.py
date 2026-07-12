"""textutil.clip() — the shared word-boundary clip used for both the stored
rationale (ai_judge.RATIONALE_MAX=280, feeds FR14's detail-page reasoning) and
the push-notification body (notify.NOTIF_BODY_MAX=150, feeds FR13's one-line
alert). Pure function, no external deps -> highest value-per-effort baseline
coverage target.
"""

import pytest

from textutil import clip


def test_short_string_unchanged():
    assert clip("Buy signal", 280) == "Buy signal"


def test_empty_string():
    assert clip("", 280) == ""


def test_whitespace_only_string_normalizes_to_empty():
    # " ".join("   \n\t  ".split()) == "" -- whitespace-only collapses to empty,
    # which is <= any positive limit, so no ellipsis is added.
    assert clip("   \n\t  ", 10) == ""


def test_exact_limit_boundary_unchanged():
    text = "x" * 50
    assert clip(text, 50) == text
    assert len(clip(text, 50)) == 50


def test_one_over_limit_gets_clipped():
    text = "x" * 51
    out = clip(text, 50)
    assert len(out) <= 50
    assert out.endswith("…")


def test_very_long_input_stays_within_limit():
    text = "The company reported strong earnings. " * 50
    out = clip(text, 150)
    assert len(out) <= 150
    assert out.endswith("…")


def test_clips_on_word_boundary_not_mid_word():
    text = "This rationale explains why the verdict changed to Buy today"
    out = clip(text, 30)
    assert len(out) <= 30
    # the clipped text (minus the ellipsis) must be a prefix made of whole words
    # from the original — i.e. it must not end mid-word.
    stripped = out[:-1].rstrip(" ,.;:-")
    assert text.startswith(stripped)
    assert not text[len(stripped):len(stripped) + 1].isalnum() or stripped == ""


def test_trailing_punctuation_stripped_before_ellipsis():
    text = "Reversal confirmed, volume spiking hard right now, " + "z" * 20
    out = clip(text, 40)
    # no ",", ".", ";", ":" or "-" directly before the ellipsis
    assert out[-2] not in ",.;:-"


def test_unicode_company_names_not_mangled():
    # NSE company names / rationale text can carry non-ASCII (e.g. currency
    # symbols, accented characters). clip() must count characters, not bytes,
    # and must not crash or truncate mid-multibyte-character.
    text = "Reliance Industries reported strong Q1 numbers – price near ₹2,950, up sharply"
    out = clip(text, 40)
    assert len(out) <= 40
    assert isinstance(out, str)


def test_unicode_short_string_passes_through():
    text = "₹ gain of 5% today"
    assert clip(text, 280) == text


def test_internal_whitespace_normalized():
    text = "Buy   signal\n\nwith   extra   whitespace"
    out = clip(text, 280)
    assert out == "Buy signal with extra whitespace"


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_very_small_limits_never_exceed_limit(limit):
    text = "A fairly long rationale sentence that will need clipping for sure"
    out = clip(text, limit)
    assert len(out) <= limit
