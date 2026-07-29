"""Regression coverage for the 2026-07-29 live incident: `_fetch_tunables()`'s
old `create_client(..., options=ClientOptions(...))` call crashed with
`AttributeError: 'ClientOptions' object has no attribute 'storage'` on EVERY
call against the installed supabase-py==2.31.0, because that version's
`create_client()`/`Client.__init__` only populates `options.storage` on its
OWN internally default-constructed `ClientOptions` (the `if options is None:`
branch) -- the publicly-importable `supabase.lib.client_options.ClientOptions`
dataclass has no `storage` field at all, so a caller-built instance passed
into `options=` skipped that branch and crashed downstream.

`tests/test_tunables.py`'s existing `mock_tunables_fetch` fixture patches
`supabase.create_client` itself, so it never exercised the REAL
`create_client()`/`Client.__init__` code this bug lived in -- exactly what let
this ship undetected (BUG source: mocking the whole seam, not just the
network I/O below it). These tests go through the real, unmocked
`supabase.create_client()` -> real `Client.__init__` -> real
`SyncPostgrestClient.__init__` chain, so a reintroduction of the same
incompatibility (e.g. a supabase-py upgrade/downgrade that changes this
contract again) fails loud here instead of only in production.

No live Supabase project or credentials required: test 1 never attempts
network I/O (construction + attribute-set only); test 2 targets a
non-resolving host (`.invalid`, reserved by RFC 2606 to never resolve) so the
real fetch attempt fails on a network/proxy error -- caught by
`_fetch_tunables()`'s own `except Exception` -- rather than hanging or
succeeding.
"""

import httpx
import pytest
from supabase import create_client

import config
from test_config import reload_config          # noqa: F401 -- reused fixture


def test_real_create_client_and_postgrest_timeout_set_does_not_raise():
    """Exercises the exact two lines `_fetch_tunables()` runs, against the
    REAL (unmocked) supabase-py client construction path. Before the fix,
    the equivalent `create_client(url, key, options=ClientOptions(...))` call
    raised AttributeError here, on construction, before any network I/O."""
    client = create_client("https://example.invalid.supabase.co", "fake-key")

    client.postgrest.session.timeout = httpx.Timeout(9.0)

    assert isinstance(client.postgrest.session.timeout, httpx.Timeout)
    assert client.postgrest.session.timeout.connect == 9.0


def test_fetch_tunables_real_path_fails_on_network_not_on_client_construction(
    reload_config, capsys,
):
    """Full end-to-end real path (`config._fetch_tunables()`, unmocked) against
    a host that can never resolve. Must fall back to {} (tier-2/cache) via the
    generic `except Exception` handler -- and the logged failure reason must
    NOT be the AttributeError this bug produced, proving the crash happened
    (or didn't) at the network step, not at client construction."""
    cfg = reload_config(
        SKIP_TUNABLES_FETCH="false",
        TUNABLES_FETCH_TIMEOUT_MS="2000",
        SUPABASE_URL="https://example.invalid.supabase.co",
    )
    out = capsys.readouterr().out

    assert cfg.TUNABLES_DEGRADED is True   # tier-1 fetch failed -> fell through to tier-2 cache
    assert "tunables fetch failed" in out
    assert "has no attribute 'storage'" not in out
    assert "AttributeError" not in out


def test_fetch_tunables_function_directly_does_not_raise_attributeerror(monkeypatch):
    """Same real path, called directly (no module reload) with a short
    timeout, asserting `_fetch_tunables()` itself never lets an
    AttributeError escape -- it must always resolve to {} on any failure."""
    monkeypatch.setattr(config, "SKIP_TUNABLES_FETCH", False)
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.invalid.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SECRET_KEY", "fake-key")
    monkeypatch.setattr(config, "TUNABLES_FETCH_TIMEOUT_MS", 2000)

    try:
        result = config._fetch_tunables()
    except AttributeError as e:
        pytest.fail(f"_fetch_tunables() must never raise AttributeError, got: {e}")

    assert result == {}
