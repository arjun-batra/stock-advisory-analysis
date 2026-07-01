"""Shared text helpers.

One home for the word-boundary clip that both rationale limits use: the stored
rationale (ai_judge.RATIONALE_MAX, 280) and the push-notification body
(notify.NOTIF_BODY_MAX, 150). The two modules previously carried identical
copies of this function.
"""


def clip(text: str, limit: int) -> str:
    """Trim to <= limit chars on a word boundary, adding an ellipsis if cut.

    The clipped text is user-facing (detail page / push body), so a hard slice
    would ship half-words. Clip on whitespace instead and signal the cut with a
    single-char ellipsis, keeping the result <= limit.
    """
    text = " ".join(str(text).split())              # normalize whitespace
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1]                      # leave room for the ellipsis
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]          # back up to the last whole word
    return clipped.rstrip(" ,.;:-") + "…"
