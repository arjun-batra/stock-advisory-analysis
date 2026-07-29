# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs. (INC-7's full entry archived this pass — see
`docs/archive/test-report-archive.md`.)

---

## Hotfix — `ClientOptions` incompatibility broke live tunables fetch on every run — 2026-07-29

**Scope:** `scripts/config.py` (`_fetch_tunables()`, fix only), `docs/design/tunables-fallback.md` (REV-095,
as-built sync), `tests/test_tunables.py` (updated mock fixture), new
`tests/test_fetch_tunables_real_client_construction.py`. Branch: `claude/admin-portal-evaluation-txaehj`,
commit `77e535e`. Dev's handoff: `docs/handoff.md`. Not a numbered increment — an actively-firing production
bug found and fixed outside the increment loop (confirmed via live `hourly-watchlist.yml` job logs by the
orchestrator), verified with priority ahead of the next scheduled run.

**Bug:** `_fetch_tunables()` called `create_client(url, key, options=ClientOptions(postgrest_client_timeout=...))`.
The installed `supabase-py==2.31.0`'s `create_client()`/`Client.__init__` only sets `options.storage` on its
own internally default-constructed `ClientOptions` (the `if options is None:` branch) — the
publicly-importable `supabase.lib.client_options.ClientOptions` dataclass has no `storage` field at all, so
a caller-built instance skipped that branch and crashed with `AttributeError: 'ClientOptions' object has no
attribute 'storage'` on every call since INC-6 merged, forcing every run onto the tier-2 cache fallback
(`TUNABLES_DEGRADED=True`) and firing real "degraded" push notifications in production.

### Root-cause re-verification (independent, not taken on dev's account)

Reproduced against the pre-fix code (`git show 77e535e^:scripts/config.py`) and the actual installed
`supabase-py==2.31.0` in this environment:

```
python3 -c "from supabase import create_client; from supabase.lib.client_options import ClientOptions;
create_client('https://example.invalid.supabase.co', 'fake-key',
options=ClientOptions(postgrest_client_timeout=5.0))"
```
→ `AttributeError: 'ClientOptions' object has no attribute 'storage'`, confirming dev's diagnosis exactly
(installed version, exact traceback text) rather than reading the diff and trusting the commit message.

### Fix re-verification

Reproduced the fixed construction path directly (`create_client(url, key)` then
`client.postgrest.session.timeout = httpx.Timeout(...)`) against the same fake host: client construction no
longer raises `AttributeError`; the subsequent live call fails with a network/proxy-class error
(`ProxyError 403 Forbidden` in this sandboxed environment — the equivalent of a DNS failure against a real
`.invalid.supabase.co` host with no outbound proxy), caught by `_fetch_tunables()`'s own `except Exception`.
Also ran the fixed module directly end-to-end (`SKIP_TUNABLES_FETCH=false` against the fake host): logs
`tunables fetch failed (403 Forbidden); falling back to tunables_cache.json`, resolves every curated key
from tier 2, and reports `TUNABLES_DEGRADED == True` — the correct fallback behavior, no crash, no silent
data loss.

### Regression test critical read — `tests/test_fetch_tunables_real_client_construction.py`

This was the priority check, since a mocked-away seam would make the new test worthless for its stated
purpose. Confirmed the test file imports `create_client` directly from `supabase` and calls it unmocked
(no `monkeypatch.setattr(supabase, "create_client", ...)` anywhere in the file); the `reload_config` fixture
it reuses from `test_config.py` genuinely does `importlib.reload(config)` against real `os.environ` values,
not a patched `create_client`. All three tests in the file go through the real
`create_client()` → `Client.__init__` → `SyncPostgrestClient.__init__` chain against a `.invalid` (RFC 2606,
never-resolves) host — the exact seam `tests/test_tunables.py`'s pre-existing `mock_tunables_fetch` fixture
patches away (confirmed: that fixture monkeypatches the `supabase.create_client` symbol itself, which is why
the original bug shipped undetected). **Verdict: the new test genuinely exercises the real construction
path and would have caught this exact bug before it shipped.**

### Suite results

- `python3 -m pytest -q --tb=short` → **204 passed, 0 failed** — matches the handoff's reported count
  exactly (6 `DeprecationWarning`s from the supabase library's own internals, unrelated to this fix, no
  test failures).

### Entry-point import check

All three real entry points import cleanly with the fix in place, both with the fetch skipped and with it
attempted against a fake host:

- `scripts/run_hourly.py`, `scripts/run_discovery.py`, `scripts/publish_prices.py` — each imports without
  error under `SKIP_TUNABLES_FETCH=true`.
- `scripts/run_hourly.py` additionally re-checked under `SKIP_TUNABLES_FETCH=false` against
  `https://example.invalid.supabase.co` — logs the expected `403 Forbidden`/`tunables fetch failed` fallback
  line, never an `AttributeError`, and completes import with `TUNABLES_DEGRADED=True`.

### Shippability

Not a UI-facing change; verified via the real entry-point imports above (the actual code path
`hourly-watchlist.yml` executes each run) rather than a separate manual walkthrough. No live Supabase
project available this session (same constraint as every prior increment) — a genuine tier-1 fetch success
(real rows returned) was not re-verified live; that code path's shape (`.table().select().execute().data`)
is unchanged by this fix and was already covered by INC-6's mocked-fetch tests.

### Bugs filed

**None.** The fix resolves the reported crash exactly as diagnosed; no new defect found.

### Verdict

**PASS.** 204/204 full suite passing (0 regressions). Root cause independently reproduced against the real
installed `supabase-py==2.31.0` (not taken on dev's account); fix independently reproduced to fail only at
the network layer, never at client construction; new regression test confirmed to exercise the real,
unmocked `create_client()` seam that let the original bug ship undetected; all three entry points import
cleanly pre- and post-fetch-attempt. Safe to merge ahead of the next scheduled `hourly-watchlist.yml` run.

---

## Open bugs

None open. (BUG-003, filed and fixed during INC-6, is archived with that run — see
`docs/archive/test-report-archive.md`.)
