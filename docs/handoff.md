# Handoff — debt cleanup pass (REV-007, REV-008, REV-009, REV-010, REV-011, REV-012, REV-014)

Source: `docs/review-log.md` reviewer findings, fixed per user request. Config baseline references:
`docs/design.md` §9, `docs/requirements.md` §11 (tech-lead/pm to add the new keys below to those tables
in a follow-up — not updated here per scope).

## Files touched
- `scripts/config.py` — added the six new tunables listed below.
- `scripts/prefilter.py` — REV-007 (pacing sleeps), REV-012 (earnings recent-days lookback).
- `scripts/ingest.py` — REV-008 (history retries), REV-009 (history period), REV-010 (headline limit).
- `scripts/notify.py` — REV-011 (`NOTIF_BODY_MAX` now sourced from config).
- `scripts/ai_judge.py` — REV-011 (`RATIONALE_MAX` now sourced from config).
- `requirements.txt` — REV-014 (exact version pins).

## New config keys (all in `scripts/config.py`, env-var override with the prior hardcoded value as default)

| Key | Default | Replaces | Site |
|---|---|---|---|
| `YF_HISTORY_RETRIES` | `2` | `for attempt in range(2)` | `scripts/ingest.py:31` (`_fetch_history`) |
| `YF_HISTORY_PERIOD` | `"3mo"` | `tk.history(period="3mo", ...)` | `scripts/ingest.py:33` (`_fetch_history`) |
| `HEADLINES_LIMIT` | `5` | `_headlines(tk, limit: int = 5, ...)` default | `scripts/ingest.py:138` (`_headlines`) |
| `NOTIF_BODY_MAX` | `150` | `NOTIF_BODY_MAX = 150` local constant | `scripts/notify.py:21` (now `config.NOTIF_BODY_MAX`, aliased at module level so `notify.NOTIF_BODY_MAX` still resolves — existing call site at `notify.py:48` and `tests/test_notify.py:85` reference the module attribute unchanged) |
| `RATIONALE_MAX` | `280` | `RATIONALE_MAX = 280` local constant | `scripts/ai_judge.py:22` (now `config.RATIONALE_MAX`, aliased at module level the same way; call sites `ai_judge.py:46,294`) |
| `DISCOVERY_EARNINGS_RECENT_DAYS` | `2` | `now - 2 * 86400` | `scripts/prefilter.py:127` (`_signals`), seconds conversion (`* 86400`) kept at the call site |

REV-007 reused the **existing** `YF_PACING_SECONDS` tunable (default `2`) at the five `time.sleep(1)`
call sites in `scripts/prefilter.py` (`find_candidates`, lines 192/197/204/209/214 pre-edit — US/CA/NSE
gainers/losers/actives pacing) per the explicit instruction to reuse it rather than invent a new
constant. **Behavior note:** this changes the actual sleep at those 5 sites from a hardcoded 1s to the
`YF_PACING_SECONDS` default of 2s (every other pacing point in the codebase already uses this tunable at
2s) — a deliberate 1s increase in inter-screen pacing per the reviewer's explicit direction, not an
oversight. All other changes preserve prior behavior exactly (every new tunable's default equals the
value it replaced, verified by import + override smoke test below).

## `requirements.txt` pins (REV-014)

Resolved via `pip install -r requirements.txt` into a clean venv (Python 3.11.15) followed by
`pip freeze`, then pinned with `==` (no packages added/removed/upgraded — just the same five pinned to
what resolves today):

```
yfinance==1.5.1
google-genai==2.11.0
supabase==2.31.0
requests==2.34.2
tzdata==2026.3
```

This also makes README.md's existing "Python dependencies are pinned in `requirements.txt`" claim true;
README.md itself was not touched (pm-owned).

## How to verify configurability
Override any of the six new keys as an env var before running a script that imports `scripts/config.py`,
e.g.:
```
HEADLINES_LIMIT=9 NOTIF_BODY_MAX=99 RATIONALE_MAX=42 YF_HISTORY_RETRIES=5 \
YF_HISTORY_PERIOD=6mo DISCOVERY_EARNINGS_RECENT_DAYS=3 python3 scripts/run_hourly.py
```
`config.<KEY>` and the consuming module's behavior should both reflect the override (confirmed for all
six in the smoke test below).

## Smoke test performed
- `python3 -m pytest tests/ -q` from repo root: **130 passed, 1 failed** — the pre-existing
  `test_shadow_enabled_only_literal_false_disables_a_typo_stays_open` failure only (untouched, per
  instructions — pm/tech-lead/qa handling separately). No new failures introduced.
- Imported `config`, `notify`, `ai_judge`, `ingest`, `prefilter` with default env: confirmed every new
  key's value and type matches the prior hardcoded literal exactly (`YF_HISTORY_RETRIES=2` int,
  `YF_HISTORY_PERIOD="3mo"` str, `HEADLINES_LIMIT=5` int reflected in `ingest._headlines`'s signature
  default, `NOTIF_BODY_MAX=150`/`RATIONALE_MAX=280` int reflected in `notify.NOTIF_BODY_MAX` /
  `ai_judge.RATIONALE_MAX`, `DISCOVERY_EARNINGS_RECENT_DAYS=2`).
- Re-ran the same import with all six env vars overridden (see command above): confirmed every value and
  every consuming call site (including the `_headlines` function-default binding) picked up the override.

## Known limitations
- `docs/design.md` §9 and `docs/requirements.md` §11 config tables do not yet list these six keys —
  tech-lead/pm own that update per the task instructions, not done here.
- REV-007's pacing-sleep behavior change (1s -> 2s at 5 call sites) is a small, deliberate timing
  change flagged above for qa/reviewer awareness even though the rest of this pass is a pure no-op
  refactor.
