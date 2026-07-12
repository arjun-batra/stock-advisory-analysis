"""Shared pytest fixtures / path setup for the baseline regression suite.

`scripts/` is a flat module directory (no package, no relative imports —
`state.py` does `import config`, `from textutil import clip`, etc.), so it has
to be on `sys.path` for tests to import it, exactly the way the real entry
points (`run_hourly.py`, `run_discovery.py`, ...) run it in production /
GitHub Actions (each script lives next to its imports in the same directory).
"""

import os
import sys

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
