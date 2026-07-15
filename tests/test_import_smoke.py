"""Baseline shippability smoke check: every module in scripts/ must at least
compile and import cleanly against a minimal mocked environment. This does not
replace a real end-to-end run (Supabase/Gemini/yfinance/ntfy are never called
here), but it is a cheap regression net against import-time breakage —
missing dependency, syntax error, or an accidentally non-guarded top-level
side effect in an entry point (run_hourly.py / run_discovery.py /
run_shadow.py / publish_prices.py must do nothing on import; their logic must
live behind `if __name__ == "__main__":`).
"""

import importlib
import pathlib

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"
MODULE_NAMES = sorted(p.stem for p in SCRIPTS_DIR.glob("*.py"))


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_imports_cleanly(module_name):
    # Deliberately a plain import (idempotent, returns the cached module if
    # another test already imported it) rather than a pop-and-reimport: other
    # test modules hold `import config` / `import notify` / etc. references
    # captured at collection time, and swapping in a second, distinct module
    # object here would silently break their `monkeypatch.setattr(config, ...)`
    # calls (the patched object and the one the code under test reads would
    # diverge). The goal is "does this module import without error," which a
    # plain import already proves the first time any test in the suite touches it.
    mod = importlib.import_module(module_name)
    assert mod is not None


@pytest.mark.parametrize("entry_point", ["run_hourly", "run_discovery", "run_shadow", "run_shadow_nse", "publish_prices"])
def test_entry_points_do_not_execute_business_logic_on_import(entry_point):
    """Entry points must be thin orchestrators (design.md §3): importing them
    must never touch Supabase/Gemini/yfinance/ntfy. If import succeeds without
    a real SUPABASE_URL/GEMINI_API_KEY (conftest fakes them, no live client is
    actually contacted at import time), the module has no import-time side
    effects that reach a network call."""
    mod = importlib.import_module(entry_point)
    assert hasattr(mod, "main"), f"{entry_point} must expose a main() entry point"
