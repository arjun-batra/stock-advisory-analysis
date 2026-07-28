"""Shared configuration for the Stock Advisory Agent.

All secrets come from environment variables, which are wired up from GitHub
Actions encrypted secrets (see .github/workflows/hourly-watchlist.yml). Nothing
sensitive is ever hardcoded here — this file is in a public repo.
"""

import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# --- Secrets / config (set as GitHub Actions secrets; see workflow) -----------
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
# New-style secret key (sb_secret_...), replaces the legacy service_role JWT.
# Bypasses RLS; server-only — lives only in Actions secrets, never in code.
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")

# This is the SINGLE source of truth for these defaults (REV-039): the
# workflows deliberately do not forward a GitHub repo Variable for any of the
# four keys below, since an unset `${{ vars.X }}` arrives as an empty string,
# not an absent env var, which would silently blank the model rather than
# fall through to the default here. To change a model today, edit this file
# (a future admin-portal tunables table replaces this mechanism).
# Primary/backup both run on Google's PAID tier (load-bearing #6, design §4.4):
# gemini-3.5-flash / gemini-3.1-flash-lite showed stability issues in real
# operation, so both defaults are corrected to the gemini-2.5-flash family
# (2026-07-13 change request, Change 2). Backup is tried automatically if the
# primary errors on every attempt. Leave GEMINI_MODEL_BACKUP empty to disable
# the fallback and run primary-only.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MODEL_BACKUP = os.environ.get("GEMINI_MODEL_BACKUP", "gemini-2.5-flash-lite")

# NSE watchlist model pair (Phase 6, design §12 D3). Point at a different model
# for quota isolation from the US/TSX watchlist bucket, or leave unset to
# inherit GEMINI_MODEL / GEMINI_MODEL_BACKUP (NSE runs in a separate,
# non-overlapping session, so sharing the pair is a safe default). This
# inheritance is Python-level only now (REV-038/REV-039) -- no workflow env
# line intervenes, so editing GEMINI_MODEL above changes the NSE pair too
# unless NSE_GEMINI_MODEL is set explicitly.
NSE_GEMINI_MODEL = os.environ.get("NSE_GEMINI_MODEL", GEMINI_MODEL)
NSE_GEMINI_MODEL_BACKUP = os.environ.get("NSE_GEMINI_MODEL_BACKUP", GEMINI_MODEL_BACKUP)

# Phase 3 (not used yet in Phase 2):
NTFY_TOPIC       = os.environ.get("NTFY_TOPIC", "")
# NSE alerts go to their OWN ntfy topic (FR18 / design §12 D7) so India and
# US/TSX pushes can be filtered or muted independently on the same device. Set
# as a GitHub Actions secret (mirrors NTFY_TOPIC, read here at runtime). Left
# empty until the operator provisions the topic — notify.py then falls back to
# NTFY_TOPIC so no NSE alert is ever dropped.
NSE_NTFY_TOPIC   = os.environ.get("NSE_NTFY_TOPIC", "")
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

# Retry-with-backoff for the Gemini call (2026-07-07 outage: ~64% of the day's
# US/CA calls failed on transient 503 UNAVAILABLE / 504 DEADLINE_EXCEEDED over a
# ~4.5h high-demand window, with successes interleaved throughout — so retries
# recover most of them; the old single fixed-20s retry did not). The retry loop
# lives in ai_judge._generate, the ONE call function every track funnels through
# (production watchlist, discovery), so all tracks inherit identical behavior.
#   GEMINI_MAX_RETRIES: retries AFTER the initial attempt (3 -> up to 4 attempts).
#   GEMINI_RETRY_BASE_MS: exponential base delay (10s -> 20s -> 40s), slept with
#   FULL jitter (uniform 0..computed delay) so the 503-retrying calls of nearby
#   dispatch cycles don't hammer the API in lockstep.
# Both arrive from workflow `${{ vars.X }}` with NO literal fallback, so an unset
# Variable is an EMPTY string, not absent — a plain `os.environ.get(name,
# default)` default would never apply, so `or` is used instead to resolve the
# empty string to the intended default. The effective values are logged at
# call setup (ai_judge._client).
GEMINI_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES") or "3")
GEMINI_RETRY_BASE_MS = int(os.environ.get("GEMINI_RETRY_BASE_MS") or "10000")
# Per-request timeout for the Gemini call, in MILLISECONDS, honored on EVERY
# attempt including retries (it's set in the client's http_options, so it
# applies per request). Set high on purpose: 3.5-flash was responding but
# slowly, and the SDK's default timeout fired first, so we discarded completed
# (token-billed) responses and fell back to lite. 180s lets a slow-but-valid
# batch response land instead of being thrown away. Empty-string-safe like the
# retry vars above, since it's now also wired as a workflow Variable.
GEMINI_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS") or "180000")

# Yahoo Finance (yfinance) has no published rate limit and rate-limited the
# ingest loop mid-run (issue #1). Pace tickers apart and back off once on a
# rate-limit error. Ingest is batched
# into one Gemini call afterward, so a few seconds per ticker here is fine.
YF_PACING_SECONDS = float(os.environ.get("YF_PACING_SECONDS", "2"))
YF_BACKOFF_SECONDS = float(os.environ.get("YF_BACKOFF_SECONDS", "10"))
# History-fetch retry count (ingest._fetch_history) and the yfinance history
# window, both previously hardcoded at the call site.
YF_HISTORY_RETRIES = int(os.environ.get("YF_HISTORY_RETRIES", "2"))
YF_HISTORY_PERIOD = os.environ.get("YF_HISTORY_PERIOD", "3mo")
# Per-ticker headline cap (ingest._headlines), previously a function default.
HEADLINES_LIMIT = int(os.environ.get("HEADLINES_LIMIT", "5"))

# Push-notification body clip (notify._compose_body) and stored/shown
# rationale clip (ai_judge, detail page) — previously in-code constants in
# their respective modules, now tunable like everything else in this file.
NOTIF_BODY_MAX = int(os.environ.get("NOTIF_BODY_MAX", "150"))
RATIONALE_MAX = int(os.environ.get("RATIONALE_MAX", "280"))

# ntfy push endpoint (notify.NtfyNotifier) and its per-request timeout, in
# SECONDS -- previously hardcoded at the call site.
NTFY_BASE_URL = os.environ.get("NTFY_BASE_URL", "https://ntfy.sh/")
NTFY_TIMEOUT_SECONDS = float(os.environ.get("NTFY_TIMEOUT_SECONDS", "10"))

# --- Phase 4: daily discovery (reactive movers) ------------------------------
# Discovery uses DIFFERENT models from the watchlist on purpose: Gemini free-tier
# quotas are per-model, so a separate model pair gives discovery its own daily
# bucket and it can't eat into the watchlist's allowance. Discovery is one
# batched call/day, so even a throttled 2.5 Flash (20 RPD) is ample. This file
# is the single source of truth for the defaults (REV-039) -- the discovery
# workflow does not forward a GitHub repo Variable for either key.
DISCOVERY_GEMINI_MODEL = os.environ.get("DISCOVERY_GEMINI_MODEL", "gemini-2.5-flash")
DISCOVERY_GEMINI_MODEL_BACKUP = os.environ.get("DISCOVERY_GEMINI_MODEL_BACKUP", "gemini-2.5-flash-lite")

# Prefilter quality gates (all tunable). A candidate must clear ALL of these to
# reach the AI. Defaults set with Arjun after the screener smoke test.
DISCOVERY_MIN_MARKET_CAP = float(os.environ.get("DISCOVERY_MIN_MARKET_CAP", "2000000000"))   # $2B
DISCOVERY_MIN_PRICE      = float(os.environ.get("DISCOVERY_MIN_PRICE", "5"))                 # $5
DISCOVERY_MIN_VOLUME     = float(os.environ.get("DISCOVERY_MIN_VOLUME", "500000"))           # 500k shares/day
# Only real primary exchanges — excludes Cboe CA secondary listings, OTC, pink sheets.
DISCOVERY_ALLOWED_EXCHANGES = {"NYSE", "NYSEArca", "NasdaqGS", "NasdaqGM", "NasdaqCM", "Nasdaq", "Toronto"}

# --- NSE discovery gates (Phase 6 D5) ----------------------------------------
# The region=in Yahoo screener returns BOTH NSE and BSE listings (D5 smoke test:
# 45% NSI / 55% BSE, same names dual-listed). §12 is NSE discovery, so filter to
# NSE only (exchange 'NSI') and drop the BSE ('.BO') duplicates.
DISCOVERY_ALLOWED_EXCHANGES_IN = {"NSI"}
# marketCap comes back in INR, so the USD $2B floor above is meaningless here.
# Default ₹5,000 crore (₹5e10 ≈ $0.6B): a liquid mid/large-cap floor. The USD-$2B
# equivalent (~₹1.66e11) would leave almost nothing — the D5 probe's median mover
# mcap was ~₹4e10. TUNABLE / for ratification, like every discovery threshold.
DISCOVERY_MIN_MARKET_CAP_INR = float(os.environ.get("DISCOVERY_MIN_MARKET_CAP_INR", "50000000000"))  # ₹5e10
# INR price floor (rupees), analogous to the $5 US floor. ₹50 default.
DISCOVERY_MIN_PRICE_INR = float(os.environ.get("DISCOVERY_MIN_PRICE_INR", "50"))
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
# Look-back window (days) for the "just reported" side of the earnings signal
# (prefilter._signals) — the forward-looking side is DISCOVERY_EARNINGS_DAYS above.
DISCOVERY_EARNINGS_RECENT_DAYS = int(os.environ.get("DISCOVERY_EARNINGS_RECENT_DAYS", "2"))
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

# Runtime close grace, in MINUTES (design §0 item 9 / §4.1). The SQL dispatch
# gates absorb pg_cron's SUB-SECOND jitter with a +5 min bound (16:05 ET /
# 15:35 IST, migration fix_market_close_boundary_jitter) — but this Python gate
# runs MINUTES after dispatch (runner queue + checkout + pip install), so with
# an exact-close bound the correctly-dispatched final slot of every trading day
# arrived here at ~16:01-16:03 ET and was silently no-op'd — the very defect the
# SQL fix targeted, one layer down. The grace is wider than the SQL slack
# because it absorbs dispatch-to-execution latency, not scheduler jitter. The
# open bound stays exact; the next */30 slot (16:30 ET / 16:00 IST) is never
# dispatched by the SQL gates, so this grace admits no post-close run.
RUNTIME_CLOSE_GRACE_MIN = int(os.environ.get("RUNTIME_CLOSE_GRACE_MIN", "10"))


def _is_open(now: datetime, open_t: time, close_t: time) -> bool:
    """Weekday + session-hours gate, close extended by RUNTIME_CLOSE_GRACE_MIN."""
    if now.weekday() >= 5:                  # Saturday / Sunday
        return False
    latest = (datetime.combine(now.date(), close_t)
              + timedelta(minutes=RUNTIME_CLOSE_GRACE_MIN)).time()
    return open_t <= now.time() <= latest


def is_market_open(now_et: datetime | None = None) -> bool:
    now = now_et or datetime.now(MARKET_TZ)
    return _is_open(now, MARKET_OPEN, MARKET_CLOSE)


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
    # Same runtime close grace as the ET gate (15:30 + grace): the NSE SQL gate's
    # 15:35 bound saves the exact-close dispatch, and this keeps the workflow's
    # own gate from dropping it a minute later.
    now = now_ist or datetime.now(NSE_MARKET_TZ)
    return _is_open(now, NSE_MARKET_OPEN, NSE_MARKET_CLOSE)


_ALL_SECRETS = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SECRET_KEY": SUPABASE_SECRET_KEY,
}


def require_secrets(*names: str) -> None:
    """Fail fast with a clear message if a required secret is missing.

    Defaults to the full three-secret list (existing callers); pass specific
    names for an entry point that only needs a subset, e.g. publish_prices.py
    doesn't call Gemini and shouldn't require GEMINI_API_KEY.
    """
    wanted = names or tuple(_ALL_SECRETS)
    missing = [n for n in wanted if not _ALL_SECRETS[n]]
    if missing:
        raise SystemExit(f"Missing required environment secrets: {', '.join(missing)}")
