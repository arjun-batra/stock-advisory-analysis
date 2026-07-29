# Admin portal — tunables cache workflow write-back (FR30, §16.4 continued)

Split out of `docs/design/tunables-fallback.md` (2026-07-28, doc hygiene — that file exceeded the
~400-line module-split guidance once REV-040's mitigations landed). See `docs/design.md` for the
index/module map/§0/increment plan, `admin-portal-tunables.md` for the `tunables` table/RLS/seed, and
`tunables-fallback.md` for `scripts/config.py`'s two-tier fetch → cache fallback chain (`_fetch_tunables`,
`_tunable`, `write_tunables_cache_if_fetched`) — read that file first; this one is the workflow-YAML half
of the same section, §16.4: which workflow writes the cache back to git, and REV-040's race/privilege
mitigations on that write path. Section number unchanged — still §16.4, third file it lives in.

**Status: IMPLEMENTED**, same status/history as `admin-portal-tunables.md`/`tunables-fallback.md` —
dev-built, qa-tested (PASS — `docs/test-report.md`; BUG-003 found and fixed), reviewer Pass 18 verdict
**NOT CLEAR pending REV-086 fix in progress** (`docs/review-log.md`) — not yet reviewer-clear. Builds in
**INC-6**.

---

**Workflow step, `hourly-watchlist.yml` only** (added directly after "Run hourly watchlist check",
mirroring `publish-prices.yml`'s "Commit prices.json if changed" step in spirit — bot identity, `[skip
ci]` convention — but **not** a verbatim copy: REV-040 (`docs/review-log.md:329-352`) found the original
verbatim-copy version raced against `publish-prices.yml`'s own commit-on-change step (same `*/30`
window, different concurrency group) and over-broadened `hourly-watchlist.yml`'s token permissions
workflow-wide. **REV-040 also raised the write-ownership trade-off itself** — whether
`hourly-watchlist.yml` should be the writer at all, versus `publish-prices.yml` (which already has
`contents: write` and the commit step) — as a question to re-put to Arjun via pm, not a defect in
Decision #28. **Resolved:** Decision #29 (requirements.md, pm) confirms `hourly-watchlist.yml` stays the
sole writer — Arjun's reasoning is that it's the workflow actually triggered off the Supabase-scheduled
jobs, making it the natural place to write state back — **on condition of** the two mitigations below,
which REV-040 specified as the price of keeping this design rather than switching writers:

**REV-040(a) — shared `concurrency` group, so the two commit steps can never race in the first place.**
`hourly-watchlist.yml` and `publish-prices.yml` currently have *different* concurrency groups
(`hourly-watchlist` and `publish-prices` respectively — confirmed by reading both files directly), so
GitHub schedules them independently and both can be mid-push to `main` at the same moment during the
overlapping `*/30` window. Fix: **rename both workflows' concurrency group to one shared name**,
`repo-commit`. Two files, one line each:

```yaml
# hourly-watchlist.yml — was `group: hourly-watchlist`
concurrency:
  group: repo-commit   # RENAMED (REV-040a) — shared with publish-prices.yml so their commit-on-change
  cancel-in-progress: false   #   steps can never run at the same time

# publish-prices.yml — was `group: publish-prices`
concurrency:
  group: repo-commit   # RENAMED (REV-040a) — shared with hourly-watchlist.yml, same reason
  cancel-in-progress: false
```

**Load-bearing property this must not break:** `hourly-watchlist.yml`'s *original* concurrency group
existed to serialize overlapping watchlist runs against each other, so two runs can never double-write
`verdict_state` for a ticker (`non-functional-ops.md` §7.4). Renaming the group only **adds** a second
workflow to the same queue — it does not remove the original guarantee, since two `hourly-watchlist.yml`
runs still share the (renamed) group and still serialize against each other exactly as before. Net
effect of the merge: `hourly-watchlist.yml` runs, `publish-prices.yml` runs, and (unchanged) overlapping
`hourly-watchlist.yml` runs are now all one FIFO queue instead of two independent ones. Accepted
tradeoff: a `publish-prices.yml` run may now queue for a few minutes behind a `hourly-watchlist.yml` run
in the same window (or vice versa) rather than running concurrently — both are already tolerant of the
existing 30-minute cadence slack (NFR4), so this is a non-issue in practice, not a new freshness risk.

**REV-040(b) — permission scoped to the job, not the whole workflow file.** `hourly-watchlist.yml` is
the workflow holding every production secret (`GEMINI_API_KEY`, `SUPABASE_SECRET_KEY`, both ntfy topics)
and processing third-party input (Yahoo headlines, model output) — REV-040 flagged a top-level
`permissions: contents: write` here as the largest privilege increase in the whole change request, since
a workflow-level block applies to every job the file will ever contain, including any job added later
without necessarily re-auditing this decision. Fix: declare `permissions` under the `watchlist` job
specifically, not at the workflow's top level — functionally identical today (the file has exactly one
job) but scoped correctly and future-proof against a later second job inheriting write access it was
never meant to have:

```yaml
jobs:
  watchlist:
    permissions:
      contents: write   # NEW — scoped to THIS JOB (REV-040b), not a top-level workflow `permissions:`
                         # block; the rest of the workflow's default token permissions are untouched
    runs-on: ubuntu-latest
    steps:
      # ...unchanged steps above ("Check out repo" through "Run hourly watchlist check")...
```

**REV-040's second suggested mitigation — bounded retry around the actual `git push`, not just the
rebase.** The original draft guarded only the rebase (`git pull --rebase … || true`), leaving `git push`
itself unguarded — a lost race (from *any* other committer to this branch, not only
`publish-prices.yml`) failed the step outright, red-X'ing `hourly-watchlist.yml` — the trading workflow
— **after its real work (checks, alerts) had already completed successfully**. REV-040 called this
"alarming, and it trains the operator to ignore failures on the most important workflow." Fix: retry the
pull-rebase-then-push pair as a unit (a push retry must re-rebase first, or it fails again for the
identical reason), bounded at 3 attempts with a short randomized backoff — this step runs after the
job's real work is done, so a few extra seconds of retry latency here is free. The `|| true` on the
rebase is removed as part of this fix: a genuine rebase failure now feeds into the retry loop instead of
being silently swallowed and left to fail opaquely at the push.

```yaml
      - name: Commit tunables cache if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add tunables_cache.json
          if git diff --cached --quiet; then
            echo "tunables_cache.json unchanged — nothing to commit."
            exit 0
          fi
          git commit -m "chore: refresh tunables cache [skip ci]"

          max_attempts=3
          attempt=1
          until git pull --rebase origin "${GITHUB_REF_NAME}" && git push origin "HEAD:${GITHUB_REF_NAME}"; do
            if [ "$attempt" -ge "$max_attempts" ]; then
              echo "::error::failed to push tunables_cache.json after ${max_attempts} attempts"
              exit 1
            fi
            sleep_s=$(( (RANDOM % 5) + 2 ))
            echo "push attempt ${attempt}/${max_attempts} failed (lost the race or a transient error) — retrying in ${sleep_s}s"
            attempt=$((attempt + 1))
            sleep "$sleep_s"
          done
          echo "tunables_cache.json pushed (attempt ${attempt}/${max_attempts})."
```

Both mitigations are independent defenses, not redundant: the shared concurrency group (REV-040a) is the
*primary* defense — in the steady state it should mean the two workflows' commit steps are never even
scheduled to overlap, so the retry loop normally has nothing to retry. The bounded retry (REV-040's
second ask) is defense-in-depth for everything else that can still push to `main` between this step's
pull and push — a manual commit, a concurrency-group edge case, a third workflow added later — so a
stray push never turns into a hard failure on the trading workflow.

`daily-discovery.yml` gets **no** YAML changes at all — it already checks out the full repo (so
`tunables_cache.json` is present on disk via `actions/checkout`), reads it transparently through
`_tunable()`'s tier-2 fallback exactly like every other script, and never calls
`write_tunables_cache_if_fetched()`. No new permission needed — reading a checked-out file requires no
special token scope. **`publish-prices.yml` gets exactly the one-line concurrency-group rename above
(REV-040a) and nothing else** — it remains a read-only tunables-cache consumer; it does not gain the
commit step, the job-scoped `permissions` block, or the retry loop, none of which apply to it.

**`ALERTS_ENABLED` — the one key with a real second input to reconcile.** `ALERTS_ENABLED` is *also*
driven by the existing `workflow_dispatch` input (`${{ inputs.alerts_enabled }}` → env var
`ALERTS_ENABLED`, still untouched, no YAML change), the documented **safe forced-test pattern**
(`components.md` §4.1: "for any off-hours forced run, set `ALERTS_ENABLED=false`"). That must keep working
exactly as today. Resolution — pure Python, backed by the two-tier `_tunable()` chain above:

```python
_alerts_input = os.environ.get("ALERTS_ENABLED", "false").lower() == "true"   # workflow_dispatch input, unchanged
ALERTS_ENABLED = _alerts_input and ALERTS_ENABLED_TABLE   # ALERTS_ENABLED_TABLE resolves through
                                                            # table -> cache; if BOTH miss, _tunable()
                                                            # has already raised SystemExit above — this
                                                            # line never runs on an unresolved value
```

The portal's toggle can only ever **suppress** alerts, never force them on over an explicit manual
dry-run request. (The pre-existing `${{ vars.GEMINI_MODEL || '...' }}` / `_BACKUP` Variable wiring
already in `hourly-watchlist.yml` remains a harmless, unread vestige — `_tunable()` never consults that
env var; optional future cleanup, not INC-6 scope.)

The 10 keys (verbatim from FR30 / `requirements.md` §10's portal-exposure note): `GEMINI_MODEL`,
`GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`, `DISCOVERY_LOSER_PCT`,
`DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`, `DISCOVERY_MIN_MARKET_CAP_INR`,
`DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`. No other tunable is reachable from this UI;
the other ~18 non-curated tunables are completely unaffected — still GitHub Variables/code defaults.

**Status: all open questions are resolved, not deferred.** Decision #27 closed the GitHub-Variables
wiring gap. Decision #28 closed the failed-fetch fallback question (cache file, not a frozen literal)
and proposed `hourly-watchlist.yml` as sole writer, for Arjun to confirm or override. **Decision #29**
(requirements.md, pm, 2026-07-28) confirms it, conditioned on REV-040's two mitigations above (shared
`concurrency` group, job-scoped `permissions`, bounded push retry) — see the "Workflow step" section
above for the resolved design, not a proposal any more. The 2026-07-28 review pass also closed the
fallback-chain question (two tiers, fail loud — not the permanent third tier an earlier draft added).
**No open question remains for INC-6.**

**Review fixes folded into this design (dates/REV IDs, newest first):** REV-040 (2026-07-28, `[SECURITY]`
+ `[DESIGN-GAP]`, major) — shared concurrency group + job-scoped permissions + bounded push retry, all
above. Pass-11 fixes (2026-07-28): cache write-back validates before persisting, merges instead of
overwriting, tier-1 cast failure fails loud (REV-036); Supabase fetch gained an explicit timeout tunable
and a deterministic offline test seam (REV-041); a tier-2 fallback sets `config.TUNABLES_DEGRADED`,
surfaced through all three entry points' heartbeat status (REV-045); cache file moved to
`tunables_cache.json` at the repo root, out of a `config/` subdirectory that would have collided with the
`config` module name (REV-046). **Follow-up needed at INC-6 build time, not a design gap:**
`tests/conftest.py` needs a corresponding `os.environ.setdefault("SKIP_TUNABLES_FETCH", "true")` alongside
its existing fake-secrets block, so the test suite exercises the offline path by default — this is qa's
file, noted here for INC-6's dev/qa handoff, not implemented in this design pass.
