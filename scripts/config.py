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
# Primary: 3.5 Flash (GA May 2026, strongest reasoning in the Flash line).
# Backup: 3.1 Flash-Lite (confirmed free tier, ~500 RPD on this project per
# AI Studio) — tried automatically if the primary errors on every attempt,
# whether that's a true rate limit, an outage, or the primary simply not being
# free-tier-enabled on this project. Leave GEMINI_MODEL_BACKUP empty to disable
# the fallback and run primary-only.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_MODEL_BACKUP = os.environ.get("GEMINI_MODEL_BACKUP", "gemini-3.1-flash-lite")

# NSE watchlist model pair (Phase 6, design §12 D3). Same Variable-driven
# pattern as GEMINI_MODEL: point at a different model for quota isolation from
# the US/TSX watchlist bucket, or the same string to share it -- a config-time
# choice, no code change either way. Defaults to the same models as the US/TSX
# watchlist since NSE runs in a separate, non-overlapping session anyway.
NSE_GEMINI_MODEL = os.environ.get("NSE_GEMINI_MODEL", GEMINI_MODEL)
NSE_GEMINI_MODEL_BACKUP = os.environ.get("NSE_GEMINI_MODEL_BACKUP", GEMINI_MODEL_BACKUP)

# Phase 3 (not used yet in Phase 2):
NTFY_TOPIC       = os.environ.get("NTFY_TOPIC", "")
DETAIL_PAGE_BASE = os.environ.get("DETAIL_PAGE_BASE", "")

# Phase 2 runs the full logic but sends NO real pushes. Phase 3 flips this true.
ALERTS_ENABLED = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"

# Manual override: run even when the market is closed (weekend / off-hours), for
# testing or backfill via workflow_dispatch. Leave unset on the scheduled run.
FORCE_RUN = os.environ.get("FORCE_RUN", "false").lower() == "true"

# --- Tunables (solution design 6.3) ------------------------------------------
# REMINDER_INTERVAL_DAYS / COOLDOWN_HOURS removed (issue #11): the single-rule
# model has no reminder and no cooldown, so neither constant has a consumer.
MIN_HISTORY_ROWS       = 21      # need >=20 sessions for the 20d metrics

# On a 429/API error, wait this long before a single retry (rate-limit recovery).
GEMINI_API_BACKOFF_SECONDS = float(os.environ.get("GEMINI_API_BACKOFF_SECONDS", "20"))
# Per-request timeout for the Gemini call, in MILLISECONDS. Set high on purpose:
# 3.5-flash was responding but slowly, and the SDK's default timeout fired first,
# so we discarded completed (token-billed) responses and fell back to lite. 180s
# lets a slow-but-valid batch response land instead of being thrown away.
GEMINI_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "180000"))

# Yahoo Finance (yfinance) has no published rate limit and rate-limited the
# ingest loop mid-run (issue #1). Pace tickers apart and back off once on a
# rate-limit error, same shape as the Gemini handling above. Ingest is batched
# into one Gemini call afterward, so a few seconds per ticker here is fine.
YF_PACING_SECONDS = float(os.environ.get("YF_PACING_SECONDS", "2"))
YF_BACKOFF_SECONDS = float(os.environ.get("YF_BACKOFF_SECONDS", "10"))

# --- Phase 4: daily discovery (reactive movers) ------------------------------
# Discovery uses DIFFERENT models from the watchlist on purpose: Gemini free-tier
# quotas are per-model, so a separate model pair gives discovery its own daily
# bucket and it can't eat into the watchlist's allowance. Discovery is one
# batched call/day, so even a throttled 2.5 Flash (20 RPD) is ample.
DISCOVERY_GEMINI_MODEL = os.environ.get("DISCOVERY_GEMINI_MODEL", "gemini-2.5-flash")
DISCOVERY_GEMINI_MODEL_BACKUP = os.environ.get("DISCOVERY_GEMINI_MODEL_BACKUP", "gemini-2.5-flash-lite")

# Prefilter quality gates (all tunable). A candidate must clear ALL of these to
# reach the AI. Defaults set with Arjun after the screener smoke test.
DISCOVERY_MIN_MARKET_CAP = float(os.environ.get("DISCOVERY_MIN_MARKET_CAP", "2000000000"))   # $2B
DISCOVERY_MIN_PRICE      = float(os.environ.get("DISCOVERY_MIN_PRICE", "5"))                 # $5
DISCOVERY_MIN_VOLUME     = float(os.environ.get("DISCOVERY_MIN_VOLUME", "500000"))           # 500k shares/day
# Only real primary exchanges — excludes Cboe CA secondary listings, OTC, pink sheets.
DISCOVERY_ALLOWED_EXCHANGES = {"NYSE", "NYSEArca", "NasdaqGS", "NasdaqGM", "NasdaqCM", "Nasdaq", "Toronto"}
# Movement thresholds for the gainers/losers screens (abs % move to qualify).
DISCOVERY_GAINER_PCT = float(os.environ.get("DISCOVERY_GAINER_PCT", "5"))
DISCOVERY_LOSER_PCT  = float(os.environ.get("DISCOVERY_LOSER_PCT", "-5"))
# Volume-spike signal: today's volume >= this multiple of the 3-month average.
DISCOVERY_VOL_SPIKE = float(os.environ.get("DISCOVERY_VOL_SPIKE", "2.0"))
# 52-week-extreme signal: price within this fraction of the 52w high/low.
DISCOVERY_52W_PROXIMITY = float(os.environ.get("DISCOVERY_52W_PROXIMITY", "0.02"))
# Earnings-proximity signal (FR4): flag a name whose next earnings date is within
# this many days (best-effort, from the screener's earnings timestamp when present).
DISCOVERY_EARNINGS_DAYS = int(os.environ.get("DISCOVERY_EARNINGS_DAYS", "7"))
# Max candidates sent to the AI in the single daily batched call.
DISCOVERY_SHORTLIST_MAX = int(os.environ.get("DISCOVERY_SHORTLIST_MAX", "15"))
# Per-candidate push cooldown: a name flagged within this many days is logged
# but not re-pushed (design 4.3 — "log always, push conditionally").
DISCOVERY_PUSH_COOLDOWN_DAYS = int(os.environ.get("DISCOVERY_PUSH_COOLDOWN_DAYS", "7"))


def discovery_models() -> list[str]:
    return [m for m in (DISCOVERY_GEMINI_MODEL, DISCOVERY_GEMINI_MODEL_BACKUP) if m]


def nse_models() -> list[str]:
    return [m for m in (NSE_GEMINI_MODEL, NSE_GEMINI_MODEL_BACKUP) if m]


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


# --- NSE market hours (Phase 6, design §12) -----------------------------------
# NSE trades 09:15-15:30 IST. IST has no DST (fixed UTC+5:30), so unlike the
# ET session this window never needs a twice-a-year check. Same posture as
# US/TSX: hours-and-weekday only, no dedicated NSE holiday calendar (accepted
# risk, design §2 item 5 / Requirements FR17) -- a closed session (weekend or
# holiday) falls through to skip-with-log when Yahoo returns nothing.
NSE_MARKET_TZ    = ZoneInfo("Asia/Kolkata")
NSE_MARKET_OPEN  = time(9, 15)
NSE_MARKET_CLOSE = time(15, 30)


def is_nse_open(now_ist: datetime | None = None) -> bool:
    now = now_ist or datetime.now(NSE_MARKET_TZ)
    if now.weekday() >= 5:                  # Saturday / Sunday
        return False
    return NSE_MARKET_OPEN <= now.time() <= NSE_MARKET_CLOSE


def require_secrets() -> None:
    """Fail fast with a clear message if a required secret is missing."""
    missing = [n for n, v in (
        ("GEMINI_API_KEY", GEMINI_API_KEY),
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_SECRET_KEY", SUPABASE_SECRET_KEY),
    ) if not v]
    if missing:
        raise SystemExit(f"Missing required environment secrets: {', '.join(missing)}")
