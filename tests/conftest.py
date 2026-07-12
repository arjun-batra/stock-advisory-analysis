"""Shared pytest fixtures / path setup for the baseline regression suite.

`scripts/` is a flat module directory (no package, no relative imports —
`state.py` does `import config`, `from textutil import clip`, etc.), so it has
to be on `sys.path` for tests to import it, exactly the way the real entry
points (`run_hourly.py`, `run_discovery.py`, ...) run it in production /
GitHub Actions (each script lives next to its imports in the same directory).
"""

import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# Minimal fake secrets so `import config` never explodes and `require_secrets()`
# can be exercised deliberately in tests that want to flip these off. Real
# external calls are never made in this suite — Gemini/yfinance/Supabase/ntfy
# are always mocked or simply never invoked (only pure functions are tested).
os.environ.setdefault("GEMINI_API_KEY", "test-fake-gemini-key")
os.environ.setdefault("SUPABASE_URL", "https://example.invalid.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-fake-secret-key")


# --- shared Gemini-call fakes (used by test_ai_judge.py and test_shadow.py) ---
#
# `shadow.judge_batch_shadow` explicitly reuses `ai_judge._client` /
# `ai_judge._generate` / `ai_judge._parse_batch` / `ai_judge._models_to_try`
# verbatim (see shadow.py's module docstring), so both test files patch the
# SAME single seam (`ai_judge._client`) and share this fake client machinery,
# mirroring how the production code actually shares it.

class FakeAPIError(Exception):
    """Stands in for google.genai's APIError: carries .code (HTTP int) and
    .status (canonical name), which ai_judge._is_retryable inspects."""

    def __init__(self, code=None, status=None, msg="simulated API error"):
        super().__init__(msg)
        self.code = code
        self.status = status


class FakeUsageMetadata:
    def __init__(self, total=100):
        self.prompt_token_count = 10
        self.candidates_token_count = 20
        self.thoughts_token_count = 0
        self.total_token_count = total


class FakeGeminiResponse:
    def __init__(self, text, usage=None):
        self.text = text
        self.usage_metadata = usage


class FakeGeminiModels:
    """Fake for client.models: generate_content() pops the next scripted
    response/exception off a queue, one per call, in call order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []   # list of model names, in call order

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if not self._responses:
            raise AssertionError("FakeGeminiModels: no more scripted responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeGeminiClient:
    def __init__(self, responses):
        self.models = FakeGeminiModels(responses)


@pytest.fixture
def mock_gemini(monkeypatch):
    """Patches the single shared seam (`ai_judge._client`) both ai_judge.judge_batch
    and shadow.judge_batch_shadow call through. Also stubs out time.sleep so a
    scripted retry/backoff path never actually sleeps in the test suite.

    Usage: `mock_gemini(responses)` where `responses` is a list of
    FakeGeminiResponse / Exception instances, consumed in call order across
    every model attempted (primary attempt(s), then backup attempt(s), etc).
    Returns the FakeGeminiClient so tests can inspect `.models.calls`.
    """
    import ai_judge

    monkeypatch.setattr(ai_judge.time, "sleep", lambda *_a, **_kw: None)
    holder = {}

    def _install(responses):
        client = FakeGeminiClient(responses)
        holder["client"] = client
        monkeypatch.setattr(ai_judge, "_client", lambda: client)
        return client

    return _install
