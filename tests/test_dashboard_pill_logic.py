"""AC3 (increment-plan.md INC-8): `pages/dashboard.html`'s verdict-pill logic
must special-case parse_status in {"no_data","failed","api_error"} -- a
synthetic call_log row with parse_status="failed" must render the "no
reading" pill, not a Hold pill (DEEP-001/INC-8, components.md §4.8).

`pages/dashboard.html` has no module boundary (a big inline <script> reading
globals like LATEST/VERDICT/esc straight from the DOM) and this project has no
browser-automation tooling available (no playwright/puppeteer/selenium in this
environment -- checked at review time), so a literal rendered-DOM/browser
check (the AC's own "manual/qa browser check" framing) could not be performed
here and remains genuinely unverified by this pass; see docs/test-report.md.

What CAN be done, and is more than dev's own throwaway scratch script (never
committed) that this file replaces with permanent coverage: extract the ACTUAL
`botBlock` function verbatim out of the real, current `pages/dashboard.html`
source (regex, not hand-copied) and execute it for real under Node against
synthetic call_log rows covering every parse_status value that matters. This
exercises real JS runtime behavior, not just a source-text grep -- it would
catch a typo like `["no_data","faild","api_error"]` that a naive substring
grep would miss, and it re-derives itself from the file on every run so it
cannot silently go stale if the surrounding function is edited.
"""

import json
import pathlib
import re
import subprocess

import pytest

_DASHBOARD = pathlib.Path(__file__).resolve().parent.parent / "pages" / "dashboard.html"
_DETAIL = pathlib.Path(__file__).resolve().parent.parent / "pages" / "detail.html"


def _extract_bot_block_source() -> str:
    """Pull the literal `function botBlock(w){ ... }` block out of the real
    dashboard.html file, brace-matched (not a fixed line-count slice), so this
    test tracks the actual source even if unrelated lines shift around it."""
    text = _DASHBOARD.read_text()
    start = text.index("function botBlock(w){")
    depth = 0
    i = start
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
    else:
        raise AssertionError("could not brace-match the end of botBlock() in dashboard.html")
    return text[start:i + 1]


def _render(row: dict | None, market: str = "US") -> str:
    """Run the real, extracted botBlock() under Node against one synthetic
    LATEST row, with minimal stand-ins for the DOM/helper globals it reads."""
    bot_block_src = _extract_bot_block_source()
    harness = f"""
    const esc = (s) => String(s);
    const curSym = (m) => ({{US:"$", TSX:"CA$", NSE:"\\u20b9"}})[m] || "$";
    const relTime = (ms) => "2 hours ago";
    const fmtAbs = (ts) => ts;
    const VERDICT = {{
      Buy:  {{bg: "#0a0", text: "#fff"}},
      Sell: {{bg: "#a00", text: "#fff"}},
      Hold: {{bg: "#aa0", text: "#000"}},
    }};
    const LATEST = {json.dumps({"W": row} if row else {})};
    {bot_block_src}
    const w = {{ticker: "W", market: {json.dumps(market)}}};
    process.stdout.write(botBlock(w));
    """
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    return result.stdout


def _row(parse_status: str, verdict: str = "Hold") -> dict:
    return {
        "verdict": verdict, "rationale": "r", "label": "watchlist",
        "parse_status": parse_status, "confidence": None,
        "price": 100.0, "timestamp": "2026-07-30T12:00:00Z", "id": "log-1",
    }


@pytest.mark.parametrize("parse_status", ["no_data", "failed", "api_error"])
def test_no_reading_parse_statuses_render_no_data_pill_not_a_verdict(parse_status):
    html = _render(_row(parse_status, verdict="Hold"))
    assert "no data" in html
    # Must NOT render the placeholder "Hold" text as a real verdict pill.
    assert '>Hold</span>' not in html


def test_genuine_ok_hold_still_renders_the_real_hold_pill():
    """Regression guard the other direction: a real parse_status='ok' Hold
    verdict must still render normally -- the widened check must not swallow
    legitimate Hold verdicts too."""
    html = _render(_row("ok", verdict="Hold"))
    assert '>Hold</span>' in html
    assert "no data" not in html


def test_genuine_ok_buy_and_sell_render_normally():
    for verdict in ("Buy", "Sell"):
        html = _render(_row("ok", verdict=verdict))
        assert f">{verdict}</span>" in html
        assert "no data" not in html


def test_no_call_log_row_renders_nothing_fr21():
    """FR21: no call_log row yet for a ticker -> block absent entirely, no
    placeholder. Unrelated to INC-8 but shares the same function -- guards
    against an INC-8 edit accidentally breaking this pre-existing behavior."""
    assert _render(None) == ""


def test_detail_page_still_special_cases_failed_and_api_error_unchanged():
    """AC3: pages/detail.html needs no change for INC-8 -- confirm the
    fail-safe note it already had before this increment is still present."""
    text = _DETAIL.read_text()
    assert 'snap.parse_status === "failed"' in text
    assert 'snap.parse_status === "api_error"' in text


def test_dashboard_no_reading_array_is_the_widened_three_value_set():
    """Source-level lock (dev's own AC3 self-check, kept as a permanent
    regression guard alongside the runtime checks above): the exact widened
    array from components.md §4.8's fix."""
    text = _DASHBOARD.read_text()
    match = re.search(r'const NO_READING = (\[[^\]]*\]);', text)
    assert match, "NO_READING array not found in dashboard.html"
    values = json.loads(match.group(1).replace("'", '"'))
    assert set(values) == {"no_data", "failed", "api_error"}
