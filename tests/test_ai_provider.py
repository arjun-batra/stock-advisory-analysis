"""ai_provider.py — provider selection + GeminiProvider client lifecycle (FR33).

Covers three things flagged as having zero permanent coverage:

- get_provider() selection (REV-077): both the explicit-arg path and the
  config-default path, happy + bogus-name cases, mirroring how QA verified
  this by hand during INC-4.
- GeminiProvider client caching keyed by timeout_ms (REV-076): the client is
  built once and reused across calls with the same timeout_ms, and rebuilt
  when timeout_ms changes -- mirrors dev's manual smoke test (3 calls same
  timeout_ms = 1 build; a 4th with a different timeout_ms = 1 rebuild).
- config.AI_TEMPERATURE flowing into the actual GenerateContentConfig passed
  to the SDK, and an env-var override actually changing it (REV-078).

These tests call GeminiProvider.generate() directly (not via ai_judge) and
patch the single `ai_provider._client` seam, same seam test_ai_judge.py's
`mock_gemini` fixture patches -- but with a local capturing fake so the
GenerateContentConfig object passed to generate_content can be inspected,
which the shared FakeGeminiModels fake (conftest.py) does not retain.
"""

import pytest

import config
from conftest import FakeGeminiResponse

import ai_provider
from ai_provider import BatchVerdictSchema, GeminiProvider, get_provider


class _CapturingModels:
    """Like conftest's FakeGeminiModels, but also retains the `config` kwarg
    passed to generate_content so tests can inspect it (e.g. temperature)."""

    def __init__(self, response_text="[]"):
        self.calls = []  # list of (model, config) tuples, in call order
        self._response_text = response_text

    def generate_content(self, model, contents, config):
        self.calls.append((model, config))
        return FakeGeminiResponse(self._response_text)


class _CapturingClient:
    def __init__(self, response_text="[]"):
        self.models = _CapturingModels(response_text)


# --- get_provider() selection (REV-077) ---------------------------------------

def test_get_provider_explicit_gemini_returns_gemini_provider():
    provider = get_provider("gemini")
    assert isinstance(provider, GeminiProvider)


def test_get_provider_explicit_gemini_uses_configured_api_key():
    provider = get_provider("gemini")
    assert provider._api_key == config.GEMINI_API_KEY


def test_get_provider_name_is_case_insensitive():
    provider = get_provider("GEMINI")
    assert isinstance(provider, GeminiProvider)


def test_get_provider_no_arg_falls_back_to_config_default(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "gemini")
    provider = get_provider()
    assert isinstance(provider, GeminiProvider)


def test_get_provider_bogus_explicit_arg_raises_systemexit_with_clear_message():
    with pytest.raises(SystemExit) as exc:
        get_provider("bogus")
    msg = str(exc.value)
    assert "bogus" in msg
    assert "gemini" in msg  # names the supported provider(s)


def test_get_provider_bogus_config_default_raises_systemexit_with_clear_message(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "bogus")
    with pytest.raises(SystemExit) as exc:
        get_provider()
    msg = str(exc.value)
    assert "bogus" in msg
    assert "gemini" in msg


# --- GeminiProvider client caching, keyed by timeout_ms (REV-076) -------------

def test_client_not_rebuilt_across_calls_with_same_timeout_ms(monkeypatch):
    builds = []  # list of (api_key, timeout_ms) per _client() invocation

    def fake_client_builder(api_key, timeout_ms):
        builds.append((api_key, timeout_ms))
        return _CapturingClient()

    monkeypatch.setattr(ai_provider, "_client", fake_client_builder)

    provider = GeminiProvider(api_key="test-key")
    schema = BatchVerdictSchema()

    for _ in range(3):
        provider.generate(model="m", system_prompt="sys", user_prompt="usr",
                           schema=schema, timeout_ms=180000)

    assert len(builds) == 1
    assert builds[0] == ("test-key", 180000)


def test_client_rebuilt_when_timeout_ms_differs(monkeypatch):
    builds = []

    def fake_client_builder(api_key, timeout_ms):
        builds.append(timeout_ms)
        return _CapturingClient()

    monkeypatch.setattr(ai_provider, "_client", fake_client_builder)

    provider = GeminiProvider(api_key="test-key")
    schema = BatchVerdictSchema()

    # 3 calls at the same timeout_ms, then a 4th at a different one.
    for _ in range(3):
        provider.generate(model="m", system_prompt="sys", user_prompt="usr",
                           schema=schema, timeout_ms=180000)
    provider.generate(model="m", system_prompt="sys", user_prompt="usr",
                       schema=schema, timeout_ms=90000)

    assert builds == [180000, 90000]


def test_client_cache_is_per_instance_not_global(monkeypatch):
    """Two separate GeminiProvider instances must each build their own client
    -- the cache lives on the instance, not as module/global state."""
    builds = []

    def fake_client_builder(api_key, timeout_ms):
        builds.append(api_key)
        return _CapturingClient()

    monkeypatch.setattr(ai_provider, "_client", fake_client_builder)
    schema = BatchVerdictSchema()

    GeminiProvider(api_key="key-a").generate(
        model="m", system_prompt="s", user_prompt="u", schema=schema, timeout_ms=1000)
    GeminiProvider(api_key="key-b").generate(
        model="m", system_prompt="s", user_prompt="u", schema=schema, timeout_ms=1000)

    assert builds == ["key-a", "key-b"]


# --- config.AI_TEMPERATURE flows into the generation config (REV-078) --------

def test_temperature_flows_from_config_default(monkeypatch):
    client = _CapturingClient()
    monkeypatch.setattr(ai_provider, "_client", lambda *_a, **_kw: client)

    provider = GeminiProvider(api_key="test-key")
    provider.generate(model="m", system_prompt="s", user_prompt="u",
                       schema=BatchVerdictSchema(), timeout_ms=1000)

    _, cfg = client.models.calls[0]
    assert config.AI_TEMPERATURE == 0.2  # documented default
    assert cfg.temperature == config.AI_TEMPERATURE


def test_temperature_override_changes_generation_config(monkeypatch):
    monkeypatch.setattr(config, "AI_TEMPERATURE", 0.9)
    client = _CapturingClient()
    monkeypatch.setattr(ai_provider, "_client", lambda *_a, **_kw: client)

    provider = GeminiProvider(api_key="test-key")
    provider.generate(model="m", system_prompt="s", user_prompt="u",
                       schema=BatchVerdictSchema(), timeout_ms=1000)

    _, cfg = client.models.calls[0]
    assert cfg.temperature == 0.9


def test_temperature_default_via_env_var_reload():
    """Explicit configurability check via the real env-var path (not just
    monkeypatching the config attribute directly): AI_TEMPERATURE is read
    from os.environ at config import time (config.py), defaulting to 0.2."""
    import importlib
    import os

    original = os.environ.get("AI_TEMPERATURE")
    try:
        os.environ["AI_TEMPERATURE"] = "0.75"
        importlib.reload(config)
        assert config.AI_TEMPERATURE == 0.75

        client = _CapturingClient()
        import ai_provider as ap
        orig_client_fn = ap._client
        ap._client = lambda *_a, **_kw: client
        try:
            provider = GeminiProvider(api_key="test-key")
            provider.generate(model="m", system_prompt="s", user_prompt="u",
                               schema=BatchVerdictSchema(), timeout_ms=1000)
        finally:
            ap._client = orig_client_fn

        _, cfg = client.models.calls[0]
        assert cfg.temperature == 0.75
    finally:
        if original is None:
            os.environ.pop("AI_TEMPERATURE", None)
        else:
            os.environ["AI_TEMPERATURE"] = original
        importlib.reload(config)
