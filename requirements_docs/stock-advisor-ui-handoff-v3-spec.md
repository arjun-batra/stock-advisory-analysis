# Stock Advisory Agent — UI handoff v3 (spec extract)
 
**This is the rendering authority** for all user-facing output (notification copy, detail page, dashboard). Where this and the Solution Design describe the same surface, **this wins**. It's a text extract of the visual handoff (`stock-advisor-ui-handoff-v3.html`) — same rules, no mockup markup. Pull the HTML only when you need to see a rendered mockup.
 
*v3 deltas: FR23 notification fix · NSE badge · Dashboard FR19–22 · reminder state retired · rationale length reconciled to SD v9 (280 stored / 150 push). Tokens unchanged from v1.*
 
---
 
## Design tokens (locked)
 
| Group | Values |
|---|---|
| Surfaces | `--bg-page #faf9f6` · `--bg-surface #fff` · `--bg-subtle #f1efe8` · `--border #e5e3da` |
| Text | `--text-primary #1a1a18` · `--text-secondary #6b6a64` · `--text-tertiary #9a988f` |
| Buy | `--buy-bg #eaf3de` · `--buy-text #27500a` |
| Sell | `--sell-bg #fcebeb` · `--sell-text #791f1f` |
| Hold | `--hold-bg #f1efe8` · `--hold-text #444441` |
| Info (change) | `--info-bg #e6f1fb` · `--info-text #0c447c` |
| Candidate | `--cand-bg #eeedfe` · `--cand-text #3c3489` |
| Amber (callout) | `--amber-bg #faeeda` · `--amber-text #854f0b` |
| Radii | `--r-sm 6px` · `--r-md 10px` · `--r-lg 14px` |
| Font | system stack (`-apple-system,…`); mono for IDs/code |
 
**Global rules:** 8px grid · 1px borders · **no shadows** · system font · meaning is always carried by **color + text + icon together** (never color alone) · mobile-first; detail page caps ~420px, dashboard caps ~480px.
 
**Pills (semantic → token):** `p-buy`/`p-sell`/`p-hold` (verdict) · `p-chg` = info (change) · `p-cand` = candidate · `p-mkt` = neutral market badge (`--bg-subtle`/`--text-secondary`, **not** a verdict color) · `p-held` (amber, "Held") · `p-watch` (neutral, "Watching").
 
---
 
## Deliverable 1 — Push notifications
 
**FR23 timestamp — single, market-matched, server-side.** Push is formatted server-side (no device tz). One timezone, no secondary, no brackets:
- US / TSX → **ET only** (`"10:04 AM ET"`)
- NSE → **IST only** (`"7:34 PM IST"`)
**Copy templates (two types × two markets = four states):**
```
Type A — verdict change   (label=='watchlist' AND alert_type=='change')
  title = "{ticker} — Changed to {verdict}"
  body  = "{timestamp} · {rationale}"     e.g. "10:30 AM ET · Volume surged 3×…"
 
Type B — new candidate    (label=='new-candidate')
  title = "{ticker} — New candidate: {verdict}"
  body  = "{timestamp} · {rationale}"
```
- Change-alert pill text is **"watchlist update"** (not "verdict change").
- **Body budget `NOTIF_BODY_MAX = 150` chars total** (timestamp prefix included); clip on a word boundary, append `…` if truncated. The stored rationale (≤280) may exceed what fits.
- New-candidate pushes are **Buy only** (Sell/Hold from discovery are logged silently).
- **`alert_type=='reminder'` is removed** — dead code, no fallback render. If `notify.py` ever emits it, that's a build error.
---
 
## Deliverable 2 — Detail page
 
**FR23 timestamp — client-rendered dual tz** (browser, device tz available):
```
Default (device not IST):   "Jun 19 · 10:04 AM ET (8:34 PM IST)"   primary device tz · secondary IST in brackets
Device already IST:         "Jun 19 · 8:34 PM IST"                  single timestamp, no duplicate
```
 
**Binding map (render → source):**
| Element | Source / rule |
|---|---|
| Pill + timestamp | `call_log.label` · `call_log.timestamp` rendered dual-tz (FR23) |
| Ticker + market badge | `watchlist.ticker` · `watchlist.market` |
| Verdict headline | `alert_type=='change'` → "Changed to {verdict}"; reminder path does not exist |
| Rationale | `call_log.rationale` · up to **280** stored & shown in full here (`RATIONALE_MAX`); push clips to 150 |
| **Your position** | `holdings.{shares,cost_basis}` · `data_snapshot.price` · computed P/L. **Omit the entire block when `watchlist.status=='watch-only'`** (FR3) — not hidden, not empty |
| Price & volume | `data_snapshot.{price,pct_change_1d,pct_change_5d,volume_vs_avg}` |
| Fundamentals | `data_snapshot.fundamentals` (P/E, market cap, 52w range); **missing field → em-dash (—)**, never "0"/blank |
| Headlines | `data_snapshot.headlines` · titles only, max 5 |
| Footer | NFR3 disclaimer (static) · `call_log.id` (UUID, not serial) |
 
**Currency:** symbol per market — `$` (US) · `CA$` (TSX) · `₹` (NSE). Derived from `watchlist.market`, **not** the ticker suffix. No FX conversion.
 
**Variants (all carry forward):**
- **Sell** — sell-text color; rationale references cost basis for held positions.
- **Hold** — gray (hold-text), **not red**; a change to Hold is a real signal, not an error.
- **Watch-only** — "Your position" block fully omitted; page goes rationale → Price & volume.
- **New candidate** — bare verdict headline (no "Changed to" prefix); label drives this.
- **New-candidate simplified** — discovery tickers have no `watchlist` row: no market badge on the ticker row, no position block (not watch-only — simply not on the watchlist); market inferred client-side from suffix (`.NS→NSE, .TO→TSX, bare→US`) for display only.
- **Missing fundamentals** — em-dash for any missing field.
- **AI parse failure** — `parse_status=='failed'` → forced **Hold**, no alert; only reachable by direct URL; show "Model response couldn't be parsed — showing fail-safe Hold."
---
 
## Deliverable 3 — Dashboard (Phase 7, not yet built)
 
**Layout:** mobile-first, ~480px cap, same card aesthetic as the detail page. One **card per ticker**. **Card top always renders** (ticker + live price + 1d change + market badge + held/watching badge). **Card bottom (`tc-bot`) renders only when `call_log` has ≥1 row for that ticker** — not CSS-hidden, **not in the DOM** at all. No placeholder/dashes/"N/A".
 
**Two distinct freshness signals — keep visually separate:**
1. **Live price** — header "Prices updated 43s ago" (relative only, no absolute); resets each auto-refresh tick (FR22). Browser fetches Yahoo directly (anon key has no price data).
2. **AI verdict age** — per-card "2h ago / 6h ago"; driven by check cadence, does **not** reset on price refresh.
**Last-run block (`tc-bot`, when present):** most-recent `call_log` row regardless of `alerted` (shows what the system last *thought*, not only what it pushed) — verdict pill + "at {last-run price}" + rationale + relative time. A row with `label=='new-candidate'` adds a "discovery scan" badge beside the verdict pill (transitional; disappears after the first watchlist run covers it).
 
**FR23 on dashboard:** relative time is **primary** ("2h ago"); absolute dual-tz is a small **secondary** ("10:04 AM ET (8:34 PM IST)"; single tz if device is IST). The "last refreshed" line is relative only.
 
**Grouping & badges:** US/TSX and NSE India are **separate, labelled groups** (not interleaved). Held vs watch-only via `watchlist.status` → "Held"/"Watching" badge, distinguished by **text + icon**, not color/position alone (FR20). Currency symbol per market.
 
**Access & security:** access-controlled — **no unauthenticated public access** (FR19); mechanism is a build-time choice (JS gate vs host-level auth) given GitHub Pages is static. Read-only **anon key scoped to `call_log` + `watchlist` only**; no other table reachable, no write path. Auto-refresh interval is **build-time config, not hardcoded** (FR22).
 
---
 
## Build / QA checklist (rule digest)
 
- Notifications: US/TSX → ET only; NSE → IST only; no brackets. Four states ship (change/new-candidate × ET/IST).
- Change-alert pill says **"watchlist update"** (not "verdict change").
- Push body = `"{timestamp} · {rationale}"`, ≤150 chars total (`NOTIF_BODY_MAX`), word-boundary clip.
- New-candidate push = **Buy only**; Sell/Hold logged silently.
- Detail timestamp dual-tz when device ≠ IST; single tz when device is IST.
- Detail new-candidate template: no market badge, no position block; market inferred from suffix for display only.
- "Your position" omitted entirely for watch-only.
- Fundamentals/missing field → em-dash; never "0"/null/blank.
- Currency symbols `$`/`CA$`/`₹` from `watchlist.market`; no FX.
- Detail footer: NFR3 disclaimer + UUID log id.
- Dashboard: `tc-bot` absent (not hidden) when zero `call_log` rows; live price always renders; latest `call_log` row shown regardless of `alerted`; "discovery scan" badge when latest row is `new-candidate`.
- Dashboard: Held/Watching from `watchlist.status` by text+icon; US/TSX and NSE groups separately labelled; ~480px cap; disclaimer footer; auto-refresh interval configurable.
- **Reminder state ("Still Buy" / "weekly reminder" pill) absent everywhere.**
 
