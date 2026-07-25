# Frontend — detail page & dashboard rendering, CORS, known limitations

Part of `docs/design.md`'s module split (2026-07-25, REV-024). See `docs/design.md` for the index, module
map, §0 load-bearing decisions, and the requirement coverage map — read that first for orientation.
Section numbers below (§10–§12) are unchanged from the pre-split monolithic `docs/design.md`.

---

## 10. Detail page & dashboard rendering authority

Detail page: `components.md` §4.7. Dashboard (FR19–FR23): static GitHub Pages page, same host as the
detail page, **client-side SHA-256 passcode gate** (FR19, obfuscation-not-security, accepted for
read-only RLS-scoped data). Two reads per refresh cycle: (1) **live price** from server-published
`pages/prices.json` read via a relative URL (same-origin) — Yahoo is browser-CORS-blocked, §11 below;
"prices updated Ns ago" keys off the snapshot's own `generated_at` (honest data age, FR21/Decision #18);
(2) **last-run data** from `latest_call_per_ticker` via the anon key — **not** filtered on `alerted`, so
the dashboard shows what the system last *thought*. Tickers grouped **US & Canada** / **India (NSE)**
(FR20); held vs watch-only by badge (text+icon, not color alone). Last-run columns are **absent from the
DOM** until ≥1 `call_log` row exists (FR21). Auto-refresh on a **configurable** timer (FR22). Timestamps
client-rendered, device + IST (FR23). Anon key scoped to `call_log` + `watchlist` only, read-only. Full
layout/copy authority: `requirements_docs/stock-advisor-ui-handoff-v3-spec.md` (v4).

---

## 11. Browser-CORS constraint (Decision #18)

Yahoo's `v8/finance/chart` returns HTTP 200 server-side but carries no `Access-Control-Allow-Origin`
header; a headless-Chromium `fetch()` from a foreign origin fails for all three markets (Yahoo CORS-gates
selectively, `vary: Origin`). Consequence: the dashboard cannot fetch live prices client-side.
`publish-prices.yml` fetches prices server-side on the market cadence and commits `pages/prices.json`
(`{generated_at, prices: {ticker: {price, chg, market, currency}}}`), read same-origin by the dashboard.
Accepted freshness tradeoff: "live" price is "as of last publish" (~30-min cadence), matching NFR4.

---

## 12. Known limitations (recorded, not resolved)

Carried from `SD.md §11` — active watch items, not defects:
- **`confidence` field has no consumer** — requested, validated, persisted, surfaced on cards, but no
  push/alert/suppression logic reads it. Intended future use is push-gating; not built.
- **Schema-enforcement's effect on parse-retry rate is unmeasured** — expected to cut the fail-safe path;
  confirm against live `parse_status` distribution.
- **Supabase single point of failure** (`foundations.md` §2 item 6, NFR2) — scheduler + monitor both in
  pg_cron; an out-of-band uptime ping is the unbuilt mitigation.
- **Paid-tier spend sustainability** — a standing ops note (not the fallback story, which was
  timeout/503). Manageable by design (one batched call per run per market group, configurable per-market
  models, tracked tokens); watch monthly spend against NFR1's $0–15 cap.
- **First live NSE close-slot run with the runtime grace, and ca/in volume screens, not yet observed.**
- **RETIRED (2026-07-16).** The former "shadow-pilot evaluation method (FR31)" limitation entry is removed
  — both shadow tracks and the evaluation harness that assessed them are retired (see `docs/design.md`'s
  "Retired: shadow-pilot tracks" note); the question of whether they should "graduate" is moot.
