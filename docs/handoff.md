# Handoff — Review-log Pass 11: dev-assigned findings

Source: `docs/review-log.md` Pass 11 (REV-033..061), dev's assigned subset per Arjun's go-ahead:
REV-039 (major, model-name literal duplication / drift), REV-051 (require_secrets generalization),
REV-052 (dev's half: detail.html headline slice, textutil.py docstring, notify.py ntfy tunables),
REV-053 (pages/common.js + common.css extraction), REV-054 (httpx pin), REV-056 (dev's half: .gitignore).
This is a direct fix pass against the live, currently-running production system — no live DB change,
mechanical/self-contained code fixes only.

## Files changed
- `scripts/config.py` — `require_secrets()` now takes `*names`, defaulting to the existing three-secret
  list; added `NTFY_BASE_URL`/`NTFY_TIMEOUT_SECONDS` tunables (REV-052); comments on the model-name block
  and `DISCOVERY_GEMINI_MODEL*` updated to state this file is now the single source of truth for those
  defaults (REV-039). No default *values* changed — same models, same secrets list.
- `.github/workflows/hourly-watchlist.yml` / `.github/workflows/daily-discovery.yml` — removed the
  `${{ vars.X || 'literal' }}`-style env lines for `GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`,
  `NSE_GEMINI_MODEL`, `NSE_GEMINI_MODEL_BACKUP`, `DISCOVERY_GEMINI_MODEL`, `DISCOVERY_GEMINI_MODEL_BACKUP`
  entirely (REV-039), rather than just dropping the literal tail — an unset `${{ vars.X }}` arrives as an
  *empty string* env var, which would defeat `config.py`'s two-arg `os.environ.get(name, default)` and
  silently blank the model, so no env line is passed for these six keys and `config.py`'s own
  defaults/inheritance apply unconditionally. This also fixes REV-038 (NSE model inheritance): confirmed
  live that setting `GEMINI_MODEL` now propagates to `NSE_GEMINI_MODEL` when the latter is unset (see
  Verification below). `GEMINI_MAX_RETRIES`/`GEMINI_RETRY_BASE_MS`/`GEMINI_TIMEOUT_MS` wiring is untouched
  (already used the safe `or`-default pattern, not in scope).
- `scripts/publish_prices.py` — replaced the inline required-secrets check with
  `config.require_secrets("SUPABASE_URL", "SUPABASE_SECRET_KEY")` (REV-051); dropped the now-unused
  manual `os.environ.get` loop (import `os` still used elsewhere in the file).
- `scripts/textutil.py` — docstring no longer restates the `RATIONALE_MAX`/`NOTIF_BODY_MAX` literal
  values (280/150), which are env-tunable and can drift from the docstring; points at `config.py` instead
  (REV-052).
- `scripts/notify.py` — `NtfyNotifier.push` now reads the ntfy base URL and request timeout from
  `config.NTFY_BASE_URL`/`config.NTFY_TIMEOUT_SECONDS` instead of hardcoding `https://ntfy.sh/` and
  `timeout=10` (REV-052).
- `requirements.txt` — added `httpx==0.28.1` (pinned to the version already resolved transitively today)
  since `scripts/ai_judge.py` imports it directly (REV-054).
- `pages/detail.html` — removed the client-side `.slice(0,5)` re-cap on `snap.headlines`; the pipeline
  already limits the stored array to `config.HEADLINES_LIMIT` before it's written, so the client-side cap
  was a second, driftable copy of the same tunable (REV-052). Also updated per REV-053 below.
- `pages/common.js` / `pages/common.css` (new) — shared `SUPABASE_URL`/`SUPABASE_PUBLISHABLE_KEY`,
  `esc()`, the `VERDICT` colour map, `_TZSHORT`/`tzLabel()`/`clockIn()`, and the CSS `:root` token block,
  previously duplicated verbatim in both pages (REV-053). Also unifies the two different currency-lookup
  shapes into one: `CUR` (currency code -> symbol) + `MKT_CUR_CODE` (market -> currency code), with
  `curSymByCode`/`curSymByMarket` helpers. Both pages load `common.js`/`common.css` same-origin (no CORS).
- `pages/dashboard.html` / `pages/detail.html` — load `common.css`/`common.js`, drop the duplicated
  declarations, alias `curSym` to `curSymByMarket` (dashboard, which only ever has a market) or
  `curSymByCode` (detail, which has currency codes directly). `clockIn(iso, tz)` on the dashboard now
  calls the shared 3-arg `clockIn(iso, tz, withDate)` with `withDate` omitted (defaults falsy — identical
  behavior to the page's previous 2-arg version).
- `.gitignore` — removed the `.shadow-pilot-session-state.md` entry, a leftover from the fully-retired
  shadow-pilot track, flagged ambiguous-ownership since 2026-07-16 and never actioned (REV-056, dev's half
  only — the runbook/README parts of REV-056 are release's/pm's job).

## Explicitly out of scope (flagged, not touched)
- `sql/phase5_monitoring.sql:37` also hardcodes the ntfy base URL (same issue as REV-052's `notify.py`
  finding) — this is SQL, tech-lead's/release's domain per the task brief, not edited here.
- REV-039/038's suggested fix text says "owner: tech-lead (design), dev at INC-6" — implemented now,
  ahead of INC-6, as a mechanical dedup per explicit instruction. **Flag for the orchestrator**: this
  touches `.github/workflows/hourly-watchlist.yml` and `daily-discovery.yml`, which INC-3-7's admin-portal
  design (tech-lead, in flight, `docs/design/admin-portal-tunables.md`) also plans to modify (adding the
  tunables-cache fetch/writer wiring). Check for conflicts before tech-lead's INC-6 branch merges — this
  pass only removed the literal-fallback env lines for six model-name keys; it did not touch the
  `permissions:`/`concurrency:` blocks or add any new env keys.
- `docs/runbook.md` §2.2 documents the now-removed `vars.GEMINI_MODEL` GitHub-UI override path — release's
  artifact, not edited here; flagging since it will read stale once this lands.

## How to run / verify
```
python3 -m pip install -r requirements.txt
python3 -m pytest -q --tb=short          # 157 passed, 0 regressions (baseline before this pass: 144)
node --check pages/common.js             # syntax check (also checked both pages' inline scripts concatenated with common.js)

SUPABASE_URL=x SUPABASE_SECRET_KEY=x GEMINI_API_KEY=x python3 -c "
import sys; sys.path.insert(0, 'scripts')
import config, notify, publish_prices, ai_judge, textutil
config.require_secrets('SUPABASE_URL', 'SUPABASE_SECRET_KEY')  # subset form
config.require_secrets()                                        # default form, both must not raise
print(config.NTFY_BASE_URL, config.NTFY_TIMEOUT_SECONDS)
"

# REV-038 side-effect check: NSE model now inherits GEMINI_MODEL when unset
SUPABASE_URL=x SUPABASE_SECRET_KEY=x GEMINI_API_KEY=x GEMINI_MODEL=custom-model python3 -c "
import sys; sys.path.insert(0, 'scripts'); import config
assert config.NSE_GEMINI_MODEL == 'custom-model'
"
```

## Known limitations
- Removing the workflow-level model overrides means an operator can no longer swap
  `GEMINI_MODEL`/`DISCOVERY_GEMINI_MODEL`/etc. from the GitHub UI Variables tab without a code edit, until
  INC-6's admin-portal tunables table ships (tech-lead's in-flight work). This is the explicit intent of
  REV-039's suggested fix, not an oversight — noted here so it isn't mistaken for a capability regression.
- `pages/common.js`/`common.css` extraction covers exactly the items REV-053 named (Supabase URL/key,
  `esc()`, `VERDICT`, timezone helpers, `:root` CSS, currency shape). Other duplicated CSS classes between
  the two pages (`.mkt`, `.pill`, etc., not flagged in the review) were left as-is — out of the assigned
  finding's scope.
