"""Shared configuration for the Stock Advisory Agent.

All secrets come from environment variables, which are wired up from GitHub
Actions encrypted secrets (see .github/workflows/hourly-watchlist.yml). Nothing
sensitive is ever hardcoded here — this file is in a public repo.
"""

import json
import os
import pathlib
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from supabase import create_client

# --- Secrets / config (set as GitHub Actions secrets; see workflow) -----------
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
# New-style secret key (sb_secret_...), replaces the legacy service_role JWT.
# Bypasses RLS; server-only — lives only in Actions secrets, never in code.
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")

# --- Admin-portal tunables (FR30, docs/design/tunables-fallback.md §16.4) ----
# Two runtime tiers only, table -> repo-committed cache -- NO permanent third
# hardcoded-literal tier (2026-07-28 design revision; see the design doc for
# why one was removed). Governs exactly the 10 curated keys below; every other
# tunable in this file is untouched and still reads a plain os.environ.get(...).

# Non-curated: bootstraps the fetch below, so it cannot itself be sourced from
# the `tunables` table.
TUNABLES_FETCH_TIMEOUT_MS = int(os.environ.get("TUNABLES_FETCH_TIMEOUT_MS", "5000"))
# Offline switch: tests/local runs skip the live fetch and resolve every
# curated key from tunables_cache.json deterministically (REV-041) -- avoids
# ~15 live connection attempts per suite run against tests/conftest.py's fake
# SUPABASE_URL host.
SKIP_TUNABLES_FETCH = os.environ.get("SKIP_TUNABLES_FETCH", "false").lower() == "true"

_CACHE_PATH = pathlib.Path(__file__).resolve().parent.parent / "tunables_cache.json"   # repo root,
    # REV-046 -- NOT inside a `config/` subdirectory: scripts/ is a flat, non-package directory on
    # sys.path, and a repo-root `config/` dir with no __init__.py would be a valid implicit namespace
    # package that could shadow this very module (`import config`) if the repo root ever preceded
    # scripts/ on sys.path.

_TUNABLE_CASTS: dict[str, "Callable[[str], object]"] = {}   # populated by every _tunable() call below;
    # write_tunables_cache_if_fetched() reuses this exact registry to validate before persisting
    # (REV-036) rather than re-deriving cast rules in a second place.


def _fetch_tunables() -> dict[str, str]:
    """This run's live fetch. Returns {} on ANY failure, or when explicitly
    skipped (REV-041's offline path). NEVER writes to the cache file itself --
    only write_tunables_cache_if_fetched(), called explicitly, does that. This
    is the ONE function qa patches to test every fallback-tier path
    deterministically, mirroring ai_provider._client."""
    if SKIP_TUNABLES_FETCH:
        print("  [config] SKIP_TUNABLES_FETCH set; using tunables_cache.json only "
              "(no live Supabase call made) — deterministic for tests/local runs")
        return {}
    try:
        # Deliberately NOT `create_client(..., options=ClientOptions(...))`: the
        # installed supabase-py's create_client()/Client.__init__ only sets
        # `options.storage` on ITS OWN internal default-constructed ClientOptions
        # (the `if options is None:` branch) -- the publicly-importable
        # `supabase.lib.client_options.ClientOptions` dataclass has no `storage`
        # field at all, so passing a caller-built instance here crashed with
        # `AttributeError: 'ClientOptions' object has no attribute 'storage'` on
        # every single call (2026-07-29 incident; confirmed against the exact
        # installed version, not the sketch this REV-041 code block used to
        # show). Fix: let create_client() build its own correct default, then set
        # the timeout on the already-constructed postgrest sub-client directly.
        client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
        client.postgrest.session.timeout = httpx.Timeout(TUNABLES_FETCH_TIMEOUT_MS / 1000)
        rows = client.table("tunables").select("key,value").execute().data
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"  [config] tunables fetch failed ({e}); falling back to tunables_cache.json")
        return {}


def _load_tunables_cache() -> dict[str, str]:
    """Repo-committed last-known-good values, read once at import time. A
    missing/corrupted file returns {} -- every key lookup then falls through
    to _tunable()'s fail-loud SystemExit below if the live fetch also missed
    it. No hardcoded floor exists past this point."""
    try:
        return json.loads(_CACHE_PATH.read_text())
    except Exception as e:
        print(f"  [config] tunables cache read failed ({e}); no fallback tier left for these keys")
        return {}


_TUNABLES = _fetch_tunables()               # tier 1: this run's live Supabase fetch
_TUNABLES_CACHE = _load_tunables_cache()    # tier 2: last-known-good, repo-committed
TUNABLES_DEGRADED = False    # REV-045: set True the first time any curated key resolves from tier 2
                              # instead of tier 1 this run -- read by every entry point's heartbeat
                              # write so a persistently-stale tunables state is monitor-visible.


def _tunable(key: str, cast):
    """Two tiers only: live Supabase fetch, then the repo-committed cache.

    REV-036 fix: a tier-1 value that FAILS TO CAST fails loud immediately
    (SystemExit) instead of silently falling through to tier 2 -- a cast
    failure on a value Supabase actually returned is an operator-caused data
    error (e.g. a bad portal edit), not a fetch failure; silently falling
    through would let that bad value later get persisted into the cache by
    write_tunables_cache_if_fetched(), turning one typo into a permanently
    corrupted last-known-good. Only a MISSING key falls through to tier 2.
    """
    global TUNABLES_DEGRADED
    _TUNABLE_CASTS[key] = cast
    raw1 = _TUNABLES.get(key)
    if raw1 is not None:
        try:
            return cast(raw1)
        except (TypeError, ValueError):
            raise SystemExit(
                f"[config] tunable {key!r} was fetched from Supabase as {raw1!r} but failed to "
                f"cast. This is an operator-entered value error, not a fetch failure — refusing "
                f"to fall through to the cache tier and risk persisting it as the new "
                f"last-known-good. Fix the value in the tunables table (portal or SQL editor)."
            )
    raw2 = _TUNABLES_CACHE.get(key)
    if raw2 is not None:
        try:
            value = cast(raw2)
        except (TypeError, ValueError):
            raise SystemExit(
                f"[config] tunable {key!r} unavailable: Supabase tunables fetch did not include "
                f"this key, AND the cached value {raw2!r} in tunables_cache.json failed to cast. "
                f"Refusing to start with an unknown value for a portal-controlled tunable."
            )
        TUNABLES_DEGRADED = True
        print(f"  [config] tunable {key!r} resolved from tunables_cache.json (tier 2) — "
              f"live Supabase fetch did not include it this run")
        return value
    raise SystemExit(
        f"[config] tunable {key!r} unavailable: Supabase tunables fetch failed or did not "
        f"include this key, AND tunables_cache.json is missing, unreadable, or also "
        f"missing this key. Refusing to start with an unknown value for a portal-controlled "
        f"tunable rather than silently guessing one."
    )


def write_tunables_cache_if_fetched() -> None:
    """Validate and merge THIS RUN'S successful Supabase fetch into the
    existing cache, then write the result to tunables_cache.json. No-ops
    silently if this run's fetch failed entirely (_TUNABLES is empty) -- a
    failed fetch never touches a good cache.

    REV-036 fix (three changes from the original draft, which serialized
    `_TUNABLES` verbatim and unconditionally):
      1. VALIDATE before writing: a fetched value is only persisted if it
         still casts cleanly under `_TUNABLE_CASTS[key]` (populated by every
         `_tunable()` call above).
      2. MERGE, never overwrite: start from the existing cache and only
         update keys this run's fetch actually returned, so a fetch that
         legitimately omitted a key never deletes that key's last-known-good.
         The merged file can never be smaller than the cache already on disk.
      3. No-op cleanly when nothing changed, so the workflow's git-diff step
         (not this function) still decides whether a commit is needed.

    Decision #28: hourly-watchlist.yml is the SOLE writer (runs most
    frequently). Called ONLY from run_hourly.py's entry point --
    run_discovery.py and publish_prices.py never call this; they remain pure
    read-only consumers of _TUNABLES_CACHE via _tunable() above."""
    if not _TUNABLES:
        return
    merged = dict(_TUNABLES_CACHE)
    for key, raw in _TUNABLES.items():
        cast = _TUNABLE_CASTS.get(key)
        if cast is None:
            continue   # a key this run never read via _tunable(); leave the cache's value untouched
        try:
            cast(raw)   # validate only -- the cache stores the raw string, same shape as today
        except (TypeError, ValueError):
            print(f"  [config] tunables cache write-back: {key!r}={raw!r} failed to validate; "
                  f"keeping the existing cached value for this key")
            continue
        merged[key] = raw
    if merged == _TUNABLES_CACHE:
        return
    _CACHE_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")


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
# GEMINI_MODEL / GEMINI_MODEL_BACKUP are curated tunables (FR30) as of INC-6 --
# sourced from the `tunables` table / tunables_cache.json above, NOT from an
# env var (the env-var/GitHub-Variable wiring gap this comment used to
# describe is exactly what Decision #27 closed by moving these to Supabase).
GEMINI_MODEL = _tunable("GEMINI_MODEL", str)
GEMINI_MODEL_BACKUP = _tunable("GEMINI_MODEL_BACKUP", str)

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

# ALERTS_ENABLED (FR30 curated tunable) has TWO inputs, AND-gated -- this must
# keep the pre-existing safe-forced-test pattern working exactly as today
# ("for any off-hours forced run, set ALERTS_ENABLED=false" -- components.md
# §4.1): the workflow_dispatch input below can only ever SUPPRESS alerts,
# never force them on over the table/cache value, and vice versa.
_alerts_input = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"   # workflow_dispatch
    # input, unchanged -- Phase 2-era default: runs the full logic but sends NO real pushes.
ALERTS_ENABLED_TABLE = _tunable("ALERTS_ENABLED", lambda v: str(v).lower() == "true")
ALERTS_ENABLED = _alerts_input and ALERTS_ENABLED_TABLE   # if BOTH tiers missed this key,
    # _tunable() has already raised SystemExit above -- this line never runs on an unresolved value

# Manual override: run even when the market is closed (weekend / off-hours), for
# testing or backfill via workflow_dispatch. Leave unset on the scheduled run.
FORCE_RUN = os.environ.get("FORCE_RUN", "false").lower() == "true"

# Selects the AIProvider implementation ai_judge.judge_batch() uses (FR33,
# docs/design/operational-controls.md §14). Only "gemini" is implemented today
# (Decision #26 — no second provider built); ai_provider.get_provider() raises
# SystemExit for anything else. Not on the admin portal's curated tunables list
# (FR30) — single-valued today, nothing to edit.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")

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
# call setup (ai_judge.judge_batch).
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

# Sampling temperature for the Gemini call (ai_provider.GeminiProvider.generate). Kept LOW by default
# to reduce run-to-run verdict drift (requirements_docs/SD.md); tunable per CLAUDE.md's no-hardcoded-
# tunables rule, same pattern as GEMINI_TIMEOUT_MS/GEMINI_MAX_RETRIES/GEMINI_RETRY_BASE_MS.
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.2"))

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
# DISCOVERY_MIN_MARKET_CAP is a curated tunable (FR30) as of INC-6 -- sourced
# from the `tunables` table / tunables_cache.json, not an env var.
DISCOVERY_MIN_MARKET_CAP = _tunable("DISCOVERY_MIN_MARKET_CAP", float)   # $2B
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
# Curated tunable (FR30) as of INC-6 -- sourced from the `tunables` table / tunables_cache.json.
DISCOVERY_MIN_MARKET_CAP_INR = _tunable("DISCOVERY_MIN_MARKET_CAP_INR", float)   # ₹5e10
# INR price floor (rupees), analogous to the $5 US floor. ₹50 default.
DISCOVERY_MIN_PRICE_INR = float(os.environ.get("DISCOVERY_MIN_PRICE_INR", "50"))
# Movement thresholds for the gainers/losers screens (abs % move to qualify).
# Both curated tunables (FR30) as of INC-6 -- sourced from the `tunables` table / tunables_cache.json.
DISCOVERY_GAINER_PCT = _tunable("DISCOVERY_GAINER_PCT", float)
DISCOVERY_LOSER_PCT  = _tunable("DISCOVERY_LOSER_PCT", float)
# Volume-spike signal: today's volume >= this multiple of the 3-month average.
# Curated tunable (FR30) as of INC-6 -- sourced from the `tunables` table / tunables_cache.json.
DISCOVERY_VOL_SPIKE = _tunable("DISCOVERY_VOL_SPIKE", float)
# 52-week-extreme signal: price within this fraction of the 52w high/low.
DISCOVERY_52W_PROXIMITY = float(os.environ.get("DISCOVERY_52W_PROXIMITY", "0.02"))
# Earnings-proximity signal (FR4): flag a name whose next earnings date is within
# this many days (best-effort, from the screener's earnings timestamp when present).
DISCOVERY_EARNINGS_DAYS = int(os.environ.get("DISCOVERY_EARNINGS_DAYS", "7"))
# Look-back window (days) for the "just reported" side of the earnings signal
# (prefilter._signals) — the forward-looking side is DISCOVERY_EARNINGS_DAYS above.
DISCOVERY_EARNINGS_RECENT_DAYS = int(os.environ.get("DISCOVERY_EARNINGS_RECENT_DAYS", "2"))
# Max candidates sent to the AI in the single daily batched call.
# Curated tunable (FR30) as of INC-6 -- sourced from the `tunables` table / tunables_cache.json.
DISCOVERY_SHORTLIST_MAX = _tunable("DISCOVERY_SHORTLIST_MAX", int)
# Per-candidate push cooldown: a name flagged within this many days is logged
# but not re-pushed (design 4.3 — "log always, push conditionally"). Curated
# tunable (FR30) as of INC-6 -- sourced from the `tunables` table / tunables_cache.json.
DISCOVERY_PUSH_COOLDOWN_DAYS = _tunable("DISCOVERY_PUSH_COOLDOWN_DAYS", int)

# All 10 curated tunables are resolved by this point (import-time, once per process
# -- NOT hot-reloaded mid-run). This startup line is how a portal edit's effect is
# actually confirmed operationally: edit a row, re-run a script, and the new value
# appears here (AC5).
print(f"  [config] tunables resolved (degraded={TUNABLES_DEGRADED}): "
      f"GEMINI_MODEL={GEMINI_MODEL!r} GEMINI_MODEL_BACKUP={GEMINI_MODEL_BACKUP!r} "
      f"ALERTS_ENABLED_TABLE={ALERTS_ENABLED_TABLE!r} DISCOVERY_GAINER_PCT={DISCOVERY_GAINER_PCT!r} "
      f"DISCOVERY_LOSER_PCT={DISCOVERY_LOSER_PCT!r} DISCOVERY_VOL_SPIKE={DISCOVERY_VOL_SPIKE!r} "
      f"DISCOVERY_MIN_MARKET_CAP={DISCOVERY_MIN_MARKET_CAP!r} "
      f"DISCOVERY_MIN_MARKET_CAP_INR={DISCOVERY_MIN_MARKET_CAP_INR!r} "
      f"DISCOVERY_SHORTLIST_MAX={DISCOVERY_SHORTLIST_MAX!r} "
      f"DISCOVERY_PUSH_COOLDOWN_DAYS={DISCOVERY_PUSH_COOLDOWN_DAYS!r}")


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
