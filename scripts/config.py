"""Shared configuration for the Stock Advisory Agent.

All secrets come from environment variables, which are wired up from GitHub
Actions encrypted secrets (see .github/workflows/hourly-watchlist.yml). Nothing
sensitive is ever hardcoded here — this file is in a public repo.
"""

import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

# --- Secrets / config (set as GitHub Actions secrets; see workflow) -----------
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
# New-style secret key (sb_secret_...), replaces the legacy service_role JWT.
# Bypasses RLS; server-only — lives only in Actions secrets, never in code.
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")

# Non-secret, but kept in env so you can change the model without a code edit.
# Verify the current free-tier model name in Google AI Studio. As of mid-2026
# the free tier is Flash / Flash-Lite only (Pro is paid). Flash-Lite gives more
# RPM if you ever need the headroom.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Phase 3 (not used yet in Phase 2):
NTFY_TOPIC       = os.environ.get("NTFY_TOPIC", "")
DETAIL_PAGE_BASE = os.environ.get("DETAIL_PAGE_BASE", "")

# Phase 2 runs the full logic but sends NO real pushes. Phase 3 flips this true.
ALERTS_ENABLED = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"

# Manual override: run even when the market is closed (weekend / off-hours), for
# testing or backfill via workflow_dispatch. Leave unset on the scheduled run.
FORCE_RUN = os.environ.get("FORCE_RUN", "false").lower() == "true"

# --- Tunables (solution design 6.3) ------------------------------------------
REMINDER_INTERVAL_DAYS = 7
COOLDOWN_HOURS         = 24
MIN_HISTORY_ROWS       = 21      # need >=20 sessions for the 20d metrics

# Pace the AI loop under the free-tier RPM cap (~10-15 RPM). 7s ~= 8-9 RPM.
GEMINI_PACING_SECONDS = float(os.environ.get("GEMINI_PACING_SECONDS", "7"))

# --- Market hours (NYSE/TSX share the session: 9:30-16:00 ET) ----------------
# Hours-and-weekday only. Deliberately NO per-exchange holiday calendar
# (accepted risk, design 2 item 5); a closed market's tickers fall through to
# skip-with-log when Yahoo returns nothing.
MARKET_TZ    = ZoneInfo("America/New_York")
MARKET_OPEN  = time(9, 30)
MARKET_CLOSE = time(16, 0)


def is_market_open(now_et: datetime | None = None) -> bool:
    now = now_et or datetime.now(MARKET_TZ)
    if now.weekday() >= 5:                  # Saturday / Sunday
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def require_secrets() -> None:
    """Fail fast with a clear message if a required secret is missing."""
    missing = [n for n, v in (
        ("GEMINI_API_KEY", GEMINI_API_KEY),
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_SECRET_KEY", SUPABASE_SECRET_KEY),
    ) if not v]
    if missing:
        raise SystemExit(f"Missing required environment secrets: {', '.join(missing)}")
