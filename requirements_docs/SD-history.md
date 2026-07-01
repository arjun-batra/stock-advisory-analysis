# Stock Advisory Agent — Solution Design: change history
 
Archived change-note stack (v2 → v13), split out of the working Solution Design for token hygiene. The
working document (`stock-advisory-agent-solution-design.md`) carries the current-state design plus a
distilled **Load-bearing decisions** list; this file preserves the full provenance — what changed in
each revision and why. Read newest-first.
 
---
 
> **v13 note — access-control ratification (doc-only, no code/schema change).** A cross-functional
> consistency review (Requirements ↔ UI-handoff ↔ SD, 2026-06-30) surfaced two undocumented access-
> control assumptions and one ambiguous requirement reading. All three were taken to Product for a
> ruling; this revision folds the rulings into the SD side. The Requirements-side edits (FR17 reword,
> new Decision Log row #17, amended Decision Log row #11) are Product-owned and tracked separately in
> that document's own version bump.
>
> 1. **Detail-page access posture ratified (§4.7).** The detail page has always been UUID-URL-only
>    with no auth gate, but this was an unstated SD assumption, not a Product decision — FR19's
>    access-control requirement was written against the dashboard and never explicitly said whether it
>    also applied to the detail page. **Ruling: FR19 scopes to the dashboard only.** The detail page's
>    UUID-only posture is now Requirements Decision Log row **#17**; §4.7 cross-references it.
> 2. **Dashboard access mechanism ratified (§2 item 7, §13).** §13 previously described the JS-gate vs.
>    Cloudflare Access choice as open ("mechanism is chosen at build time"). **Ruling: a client-side JS
>    password gate is sufficient for v1**, given the data is informational, read-only, and RLS-scoped to
>    two tables — reserving Cloudflare Access as the documented upgrade path if sensitivity ever rises.
>    This is now Requirements Decision Log row #11 (amended); §2 item 7 and §13 cross-reference it, and
>    the corresponding §11 Open Items bullet ("dashboard access mechanism... one build-time decision
>    left") is removed since it's resolved.
> 3. **Issue #15 scope expanded (§12).** The NSE/INR CHECK-constraint migration (issue #15) now also
>    bundles a basic `holdings.shares > 0` / `holdings.cost_basis > 0` input-validation guard — same
>    table family, same migration window as the constraint widening, cheaper than a separate pass. No
>    FR requires this guard; it was flagged in the same review as a low-cost addition. §12 and the issue
>    itself (GitHub) reflect the expanded scope.
>
> **Not ruled on / explicitly out of scope for v13:** FR17's NSE-holiday-calendar wording is a
> **Requirements-only** edit (SD's posture — skip-with-log, no maintained calendar, §2 risk 5 — was
> already correct and needed no change; only the requirement's wording was misaligned with it). No SD
> section changed for that item. No code, migration, or Supabase change was made in this pass — issue
> #15's expanded scope is tracked for the Phase-6 migration, not executed here.
 
---
 
> **v12 note — code-ahead reconciliation (the pass v10/v11 deferred).** A file-by-file code review of
> `main` HEAD (`e133d70`) against SD v11, cross-checked against live Supabase (constraints, cron, RLS,
> data state), closed the long-standing *code-vs-doc* gap. **Five items the SD still described as
> "pending/not-built" were verified shipped and substantive** (not stubs), and those sections were
> corrected to read as built. **No code or DB was changed in this pass** — it is doc-only; the genuine
> code/schema gaps the review also found were *filed as issues*, not fixed.
>
> *Marked shipped (verified in code):*
> 1. **Earnings-proximity signal (§4.3)** — live in `prefilter._signals()` (`DISCOVERY_EARNINGS_DAYS`),
>    best-effort on the screener's earnings timestamp. SD had said "being added."
> 2. **FR23 push timestamp (§4.6)** — live in `notify._market_timestamp` / `_compose_body` (ET for
>    US/TSX, IST for NSE; ET fallback). SD had said "sends no timestamp."
> 3. **FR23 detail-page dual-tz (§4.7)** — live in `detail.html fmtTs`/`clockIn`/`tzLabel` (device-tz
>    primary + IST secondary, deduped when device is IST). SD had said "hardcodes ET only."
> 4. **"Your position" block (§4.7, §5)** — live: `state.build_position()` + `_snapshot()` persist a
>    `position` object into `data_snapshot` for held tickers, `detail.html posBlock` renders it (absent
>    for watch-only). SD had said "does not render / does not persist." (Dormant in practice: 0 held
>    tickers / empty `holdings` — ruled working-as-intended.)
> 5. **Scheduler DDL (§8)** — `sql/scheduler_pgcron.sql` is committed (dispatch fn + base crons + Vault
>    prereqs) and verified to match the live `cron.job` inventory (jobs 1–3) with no drift. SD had said
>    "MISSING."
>
> *Also corrected:* the **§12 "no schema change" claim** — the live `watchlist.market` (US/TSX) and
> `holdings.currency` (USD/CAD) CHECKs reject NSE/INR, so NSE needs a constraint-widening migration
> first (issue **#15**); §12, the §9 Phase-6 row, and the components list now say so. The **§13** "no
> schema change" wording was likewise refined: no table/column change, but the Phase-7 dashboard needs
> a `watchlist` SELECT RLS policy (issue **#16**).
>
> *Genuine gaps filed (not fixed in this pass):* **#13** detail-page new-candidate market badge vs
> UI-handoff (`detail.html` renders `.mkt` on discovery rows); **#14** `call_log.alert_type` CHECK
> still permits retired `reminder`; **#15** NSE/INR CHECK widening (Phase-6 blocker); **#16** missing
> `watchlist` SELECT RLS policy (Phase-7 blocker); **#17** `ai_judge._FAIL_SAFE_API` rationale
> misattributes total AI failure to "rate-limited" (against load-bearing decision #3 / §4.4a).
>
> **Explicitly NOT touched in v12:** no Requirements or UI-handoff edits (those route to Product /
> Designer); no code or Supabase changes (log-only); §12 (NSE) and §13 (dashboard) remain
> confirmed-but-unbuilt.
 
---
 
> **v11 note — two more document-contradiction fixes (C5–C6).** A second document-vs-document pass
> (UI-handoff v3 ↔ SD, and an SD-internal cross-check) found two contradictions v10 didn't cover.
> Both are doc-only corrections on **unbuilt** surfaces (dashboard / NSE discovery), so no behavior
> changed and no Requirements or UI-handoff edit was made — the upstream/authoritative source wins in
> each case.
>
> 1. **C5 — dashboard live-price source (§13).** SD §13 said the dashboard pulls live price "via the
>    same `yfinance` wrapper (§4.2) the watchlist workflow uses." That is mechanically impossible: the
>    dashboard is a static GitHub Pages page, and `yfinance` is a Python library that runs only inside
>    GitHub Actions. UI-handoff v3 (rendering authority) correctly says the **browser fetches Yahoo
>    directly**. Corrected §13 read-1 to client-side browser fetch of Yahoo's HTTP endpoints; the anon
>    key has no price data, so the browser must hit Yahoo itself. **Winner: UI-handoff v3.**
> 2. **C6 — NSE discovery universe (§12 D5).** §12 D5 said NSE discovery seeds "a `region=in`-aware
>    candidate universe (NSE constituents)… alongside the US/TSX universe," and the components list
>    added "NSE constituent universe rows." This contradicts §4.3 / load-bearing decision #7, which
>    killed the `candidate_universe` table (vestigial) and forbids reintroducing it — and there is no
>    US/TSX universe to sit "alongside." Reconciled D5 + the components list to the §4.3 model: NSE
>    discovery uses the **live screener with a `region=in` EquityQuery** (mirroring the existing
>    `region=ca` Canada query), no seeded universe. **Winner: §4.3 / decision #7.**
>
> **Explicitly NOT touched in v11:** the §12 "no schema change" claim (a separate doc-vs-reality item —
> the live `market`/`currency` CHECK constraints are US/TSX-only — pending its own ruling), and the
> *code-ahead* reconciliation still deferred from v10 (earnings signal §4.3, FR23 timestamps §4.6/§4.7,
> position block §4.7, scheduler DDL §8). Those are out of scope for these two contradiction fixes.
 
---
 
 
> ↔ SD, UI-handoff v3 ↔ SD) found four places where the SD still carried stale "to-be-done / flagged
> to X" notes that the source-of-truth docs had already resolved. In every case the SD trailed its own
> upstream doc; the source-of-truth doc wins and the SD was corrected. **No behavior changed; no
> Requirements or UI-handoff edit was made.**
>
> 1. **C1 — 52-week discovery signal (§4.3).** SD called the 52-week-extreme signal "an implementation
>    detail beyond FR4's three" and "flagged to Product." Requirements v3 (FR4 + Decision #14) already
>    canonicalizes **four** signals including 52-week. Corrected: all four are FR4-backed; the
>    "beyond FR4 / flagged to Product" framing is removed.
> 2. **C2 — rationale length (§4.4a).** SD claimed "the UI handoff still cites 140 chars — flagged to
>    the Designer." UI-handoff v3 is already at 280 stored / 150 push. Stale parenthetical removed; no
>    Designer action is outstanding.
> 3. **C3 — cadence label (§6.1).** SD titled the flow "Hourly Watchlist Check," but the cadence is
>    **30 minutes** (FR6/NFR1/NFR4; live cron `*/30`). Heading relabeled to "Intraday Watchlist Check
>    — 30-min cadence"; a note explains that "hourly" survives only as the legacy `hourly-watchlist.yml`
>    filename / heartbeat key, not the actual interval. *(A side flag to Product is recorded inline:
>    Requirements is internally inconsistent — v2 note says "currently hourly," FR6 text says "every 30
>    minutes." That's Product's to reconcile.)*
> 4. **C4 — FR7 reconciliation (§6.3).** SD §6.3 still said "Requirements-doc reconciliation owed,"
>    contradicting both Requirements v3 (FR7 already carries the single-rule model) and SD §11 ("done in
>    requirements v3"). Rewritten to mark the FR7/FR8 reconciliation complete.
>
> **Explicitly NOT done in v10 (still pending):** the *code-ahead* reconciliation. Since SD v9, a
> chunk of the v9 "code queue" has shipped (earnings signal §4.3, FR23 push+detail timestamps
> §4.6/§4.7, detail-page position block §4.7, scheduler DDL §8), but the SD still describes these as
> pending/not-built. That is a code-vs-doc pass (its own version bump) and is out of scope for these
> four document-contradiction fixes.
 
---
 
> **v9 note — code-review reconciliation.** A file-by-file review found the SD had drifted from the
> deployed code in several places. This revision fixes the **document** side of those gaps; the
> **code** side (and the GitHub-committed scheduler DDL) is tracked separately as pending work.
>
> *Document corrected to match live code:*
> 1. **Discovery sourcing (§4.3, §6.2).** The SD described a static `candidate_universe` table pulled
>    via `yf.download()`. The code actually uses Yahoo's **live server-side screener**
>    (`yf.screen` day_gainers / day_losers / most_actives + a `region=ca` query). FR4 is
>    mechanism-agnostic, so this is purely an SD correction. `candidate_universe` is **vestigial**.
> 2. **Prefilter signals (§4.3).** Documented as the actual four signals: **mover, volume-spike,
>    earnings-proximity, and 52-week-extreme.** Earnings is being **added to the code** (was missing);
>    52-week-extreme is an implementation signal beyond FR4's three.
> 3. **One batched AI call, not per-ticker (§4.4, §6.1).** Code makes a single `judge_batch()` call
>    per run; the "one call per ticker" line and the per-ticker loop in the §6.1 diagram were wrong.
> 4. **`data_snapshot` contract (§5)** expanded to the fields actually written (`pct_change_20d`,
>    `model_used`, `discovery_signals`, `rate_limited`) and the real `parse_status` values
>    (`ok | retried | failed | api_error | no_data`).
> 5. **Rationale length (§4.4a)** corrected to the code's limits (≤280 stored, push clipped to 150);
>    the "140 chars" figure was stale. *(UI handoff still says 140 — flagged to the Designer.)*
> 6. **Discovery pushes Buys only (§4.3, §6.2)** — now documented.
> 7. **Key terminology (§4.7, §7.2)** — "anon key" → Supabase **publishable** (client) / **secret**
>    (server) keys, matching the code.
> 8. **AI temperature (§4.4a)** — the `temperature=0.2` setting is now documented.
> 9. **Repo structure (§8)** corrected — real entrypoints listed; `dashboard.html` marked planned.
> 10. **Detail-page position block (§4.7)** — the held-position block (UI handoff) is documented as
>     required; it's being **added to the code**.
> 11. **NSE separate ntfy topic (§12)** — FR18's separate-topic requirement is now captured as a D-item.
>
> *Code/infra work spawned by this review is pending (GitHub commit queue): add earnings screen;
> commit the scheduler DDL to `sql/`; add the position block; build FR23 timestamps (push + detail);
> remove the dead reminder paths + dead pacing constant; small detail-page copy/symbol fixes.*
 
> **v8 note — reconciling to requirements v3 + UI handoff v3.** No built behavior is re-opened; this
> revision folds in newly-confirmed scope and corrects one stale deferral.
>
> 1. **NSE elevated from PROPOSED to confirmed planned scope (§12).** Requirements v3 (FR1, FR4, FR17,
>    FR18) commit NSE as real work — unbuilt, but no longer a proposal. D1–D6 are now
>    requirements-backed design decisions. **D5 is corrected:** NSE discovery is now **in scope**
>    (FR4 puts NSE in the daily scan), reversing the v7 "deferred." ⚠️ **Tech-Lead flag (mechanism,
>    not a re-open):** the *what* is settled, but NSE discovery cannot ride the existing 22:00 UTC
>    dispatch without screening stale/pre-open data — it needs its own NSE-close-timed discovery
>    dispatch. Documented in the corrected D5.
> 2. **New §13 — Dashboard (FR19–FR22).** Read-only GitHub Pages surface; live price + last-run
>    `call_log` per ticker; market-grouped; client-rendered timestamps; auto-refresh. Layout defers
>    to UI handoff v3.
> 3. **FR23 timestamp behavior split by surface.** Push notifications carry a **single, market-matched
>    timezone** (ET for US/TSX, IST for NSE), server-formatted (§4.6). Detail page (§4.7) and dashboard
>    (§13) are **client-rendered**: device timezone primary + IST secondary in brackets, deduped when
>    the device is already IST.
> 4. **§4.3 prefilter criteria confirmed.** The three criteria (price movers, volume spikes above
>    recent average, earnings within a near-term window) are now stated as locked (FR4), not examples;
>    thresholds stay tunable.
> 5. **§8/§9/§10/§11 refreshed** — `pages/dashboard.html` added; NSE is Phase 6 and dashboard Phase 7
>    (both confirmed, not yet built); new test scenarios for the dashboard and FR23; NSE removed from
>    Open Items (now tracked as a phase).
>
> Unchanged and explicitly *not* re-opened: §6.3 single-rule alerting, §4.4/§4.4a AI prompt, §4.1
> scheduler, §4.8 monitor, §5 schema (dashboard reads existing tables; NSE adds rows only), §7.
 
> **v7 note — QA batch #6–#12 landed; pending markers cleared; two diagnoses corrected.** Every
> ⏳ PENDING fix from v6 has now shipped, so those markers flip to live and move out of Open Items.
> Two places where the v6 doc's *diagnosis* differed from what live data showed are corrected (the
> Gemini fallback cause was never RPD/quota), and the single-rule cleanup is reflected as built, not
> just specified.
>
> *Pending → live (issues #7, #8, #9, #12):*
> 1. **ET-aware, DST-correct gating is live (§4.1, §4.8).** `dispatch_watchlist_if_open()` gates the
>    watchlist dispatch on ET wall-clock (`09:30–16:00` America/New_York + weekday); the wide
>    `*/30 13-21 UTC` cron stays as the DST superset and the gate trims it to the live ET session.
>    The monitor's watchlist window is now ET-aware (`10:15–16:00` ET), killing the daily false
>    "stalled" alert that fired ~90 min past the EDT close.
> 2. **Safe forced-test pattern documented + audited (§4.1, issue #7).** `run_hourly` emits a
>    `[gate]` audit line (market_open, force_run, alerts, UTC+ET); the `FORCE_RUN` branch documents
>    that `ALERTS_ENABLED=true` sends *real* pushes off-hours.
> 3. **Discovery pre-gate observability is live (§4.3, issue #8).** `find_candidates()` returns a
>    funnel (`raw → after_dedup → passed_quality → passed_signal`); the "3 zero-candidate days is a
>    tuning signal" note is now measurable instead of aspirational.
> 4. **`monitor_alerts` RLS (issue #6)** turned out already fixed via migration — removed from Open
>    Items.
>
> *Built, not just specified (issue #11 cleanup):*
> 5. **Single-rule alert logic is in code (§6.3).** The post-cold-start **bootstrap path (the v5-era
>    #5 fix) was removed** along with the dead cooldown/reminder config constants. Stated consequence:
>    a standing Buy/Sell after cold start is now **silent until it changes** — consistent with the
>    §2 item 4 risk that the system signals on threshold *crossings*, not standing states.
> 6. **`verdict_state` is physically three columns now (§5):** `ticker`, `current_verdict`,
>    `last_checked_at`. The dropped `bootstrapped` flag is named. `dispatch_watchlist_if_open` flips
>    from ⏳ pending to live.
>
> *Diagnosis corrections (doc was wrong vs. live data):*
> 7. **Gemini fallback cause was never RPD (§2 item 3, §4.4a).** Live capture (#10) shows the real
>    cause was a **503 high-demand** response, and the original recurring fallbacks were a
>    **client-side timeout on slow-but-valid responses** — not 429/RPD exhaustion. The 180s timeout
>    fix was right; the *attribution* to quota was wrong and is corrected.
> 8. **RPD sustainability (#10 Problem 2) is a standing ops note, not a defect (§11).** Configurable
>    model Variable + separate dual-model buckets + trackable `data_snapshot.tokens` make it an
>    ongoing watch item, not a fix.
 
> **v6 note — reconciling the SD with what's actually deployed.** Phases 0–5 shipped, and the
> implementation drifted from and extended v5. This revision folds reality back in, drafts the
> pending defect fixes, and adds the NSE proposal. Where v5 and deployment conflicted, **deployment
> wins and the contradiction is named here** for auditability.
>
> *Shipped changes folded in (were already live, contradicted v5):*
> 1. **Scheduling moved off GitHub native cron entirely (§4.1).** v5 said GitHub Actions `schedule:`
>    cron triggers the workflows. That was not just wrong but actively harmful — GitHub's shared
>    scheduler silently dropped most ticks under load (a `*/30` schedule fired ~3 of ~16 daily).
>    Now Supabase `pg_cron` + `pg_net` call GitHub's `workflow_dispatch` REST API; workflows are
>    dispatch-only. The "never trust the schedule to mean 'market is open' — the runtime gate is the
>    real safety net" principle is **kept**, restated around pg_cron.
> 2. **Reliability is now an active dead-man monitor, not a passive heartbeat (§4.8, NFR2, §9).**
>    v5's "GitHub emails on failure + queryable heartbeat" couldn't catch a run that *never triggers*
>    (dropped tick, expired PAT, disabled job). Phase 5 shipped a `health-monitor` pg_cron job running
>    `check_pipeline_health()` that actively pushes ntfy alerts on staleness/no-show/degraded, deduped
>    via a `monitor_alerts` table.
> 3. **New Supabase objects (§5).** `monitor_alerts` table; functions `dispatch_github_workflow`,
>    `send_ntfy`, `_raise_monitor`, `_clear_monitor`, `check_pipeline_health`; `pg_cron`/`pg_net`
>    extensions; Vault secrets. `data_snapshot` extended with `tokens` and `fallback_from`.
> 4. **Gemini fallback root cause corrected (§4.4a, §2).** Repeated primary→backup fallbacks were
>    **not** quota — a client-side timeout fired before a slow-but-valid (already token-billed)
>    response returned. Fixed with `GEMINI_TIMEOUT_MS` (180s) and real-exception capture.
> 5. **Model names are configurable repo Variables (§4.4), not hardcoded.**
>
> *Alert logic rewritten (issue #11) — the big behavioral change:*
> 6. **§6.3 collapsed to a single rule: any verdict change → immediate alert; no change → silence.**
>    The 24h cooldown is **removed** (the debounce was already gone in v3). **FR7's 7-day
>    standing-verdict reminder is RETIRED** per owner ruling — "no change → silence" is now absolute,
>    no exceptions. `reminder_due_at` and the two-clock cold-start machinery come out of the schema.
>    **Requirements-doc reconciliation owed:** FR7 as written no longer reflects behavior; the single
>    rule is now effectively the merged FR7+FR8 and the requirements doc should be updated to match.
>
> *Pending defect fixes (drafted here, marked ⏳ — they revise the SD when the fix lands):*
> 7. **ET-aware, DST-correct market gating (§4.1, §4.8 — issues #9, #12).** ⏳
> 8. **Discovery pre-gate observability + threshold tuning (§4.3, §9 — issue #8).** ⏳
> 9. **`FORCE_RUN`/`ALERTS_ENABLED` safe-test documentation (§4.1 — issue #7).** ⏳
>
> *Proposed, not built:*
> 10. **§12 — India NSE expansion, watchlist-only, discovery deferred.** Clearly fenced as a proposal.
 
> **v5 note:** New-listing handling added (Phase 0). A recently-IPO'd ticker returns valid price
> data but too few sessions for the 20-day metrics — compute 1d/5d, pass the 20d fields as
> `n/a (newly listed)`, never skip/fail on history depth. Sections 4.4a, 7.5.
 
> **v4 note:** Four review gaps closed — FR15 every-check logging, discovery dedup, UUID detail-page
> id, NYSE/TSX holiday-calendar divergence. Sections 2, 4.1, 4.3, 4.7, 5, 6.1, 6.2, 6.3, 7.2, 10.
 
> **v3 note:** FR7/FR8 reconciled as a hybrid (change alert + standing-verdict reminder); two-run
> debounce removed. **Superseded by v6** — the hybrid and the reminder are both retired under the
> single-rule model (issue #11). Retained here for history.
 
> **v2 note:** Senior-review pass — AI prompt fully specified (§4.4a), public-repo cost fix (§7.1),
> concurrency/manual-edit/timezone/universe-ownership gaps made explicit.
 
