# Admin Portal — UX Spec (NFR8: Responsive & Modern Visual Redesign)

**Owner:** designer. **Scope:** NFR8 only — a UI/UX-only visual and responsive redesign of the five
existing admin portal screens. **No functional change**: FR27–FR32 behavior, the `is_admin()`/RLS
authorization model, and the data model are untouched (see `docs/design/admin-portal.md` §16,
`docs/design/admin-portal-tunables.md`). This spec covers presentation only — layout, visual language,
states, copy, and responsive behavior.

**Gate:** per NFR8, Arjun selects exactly one of the three directions below before any implementation
starts. No speculative screens are proposed — every screen here maps 1:1 to an existing FR.

| Screen | FR | Current content (source of truth) |
|---|---|---|
| Login | FR27 | Google OAuth button; allowlist check + reject UX (`admin-portal.md` §16.2) |
| Watchlist & Holdings CRUD | FR28, FR29 | `watchlist` (ticker, market, type, status) + `holdings` (shares, cost_basis, derived currency) (`admin-portal.md` §16.3) |
| Tunables editor | FR30 | 10 curated keys, each with description/example/current value (`admin-portal-tunables.md` §16.4) |
| Track-record view | FR31 | Read-only `call_log` / `latest_call_per_ticker` data, pagination/sort/filter only, no new aggregation (`admin-portal.md` §16.5) |
| Kill-switch toggle | FR32 | Reads/writes `kill_switch_state.paused` via `set_kill_switch()` RPC (`admin-portal.md` §16.6) |

---

## 1. Constraints (from NFR8, `docs/requirements.md` §6)

- **Devices:** phone, tablet, desktop — full responsive range, no horizontal scroll, no
  overlapping/clipped/truncated content, every control reachable and operable at all three.
- **Exact breakpoint pixels** are a tech-lead decision (`docs/design.md`), not this spec's. The
  wireframes below use **illustrative** breakpoints to demonstrate the behavior tech-lead's chosen
  pixels must reproduce: **phone ≤ 599px, tablet 600–1023px, desktop ≥ 1024px**.
- **No brand/reference constraint.** Three distinct directions are proposed below, researched from
  current (2024-2026) admin/SaaS UI conventions: dense data-console tools (Retool, Grafana, Bloomberg
  Terminal-style density), clean minimal SaaS dashboards (Linear, Vercel, Notion-style restraint), and
  friendly card-based SaaS (Stripe Dashboard, shadcn/ui-style component aesthetics).
- **Accessibility:** best-effort only — legible contrast, keyboard-focusable controls where practical.
  No WCAG conformance level is a pass/fail gate for this spec.
- **No functional regression:** every state/copy/interaction below describes the *existing* FR27–FR32
  behavior in new visual clothing. Nothing here changes what a control does, only how it looks/lays out.

---

## 2. Shared UX contract (identical across all 3 directions)

States, copy, and interaction behavior are **visual-direction-independent** — only the styling of these
states changes per direction (§4–§6). This section is the one place they're specified; the direction
sections below reference it rather than restating it.

### 2.1 Login (FR27)

| State | Behavior / copy |
|---|---|
| Default | Centered single action: **"Sign in with Google"** button. No email/password fields exist (FR27 — Google OAuth is the only path). |
| Loading (during OAuth redirect/callback) | Button shows a spinner + disabled state, label changes to **"Signing in…"** |
| Error — not authorized | After a successful Google sign-in that fails the `admin_allowlist` check, the user is immediately signed out and shown: **"This Google account isn't authorized for this admin portal."** with a **"Try a different account"** action (re-triggers sign-in). Per `admin-portal.md` §16.2, this is a UX courtesy — RLS is the real boundary. |
| Error — OAuth failure (network/provider) | **"Sign-in failed. Please try again."** with a retry button. |
| Success | Immediate redirect to the watchlist screen (portal's default landing view). |

### 2.2 Watchlist & Holdings CRUD (FR28, FR29)

One combined screen: a table of watchlist entries; holdings fields (shares, cost basis) appear inline
for rows where `status = held`.

| Column | Notes |
|---|---|
| Ticker | text |
| Market | `US` / `TSX` / `NSE` badge |
| Type | `stock` / `ETF` |
| Status | `held` / `watch-only` badge (visually distinct, not color-only — icon + text) |
| Shares | only populated/visible when held |
| Cost basis | only populated/visible when held, shown with currency |
| Currency | **read-only derived label**, e.g. "CAD (from TSX)" — never an input (Decision #35) |
| Actions | Edit, Delete |

| State | Behavior / copy |
|---|---|
| Loading | Skeleton rows (3–5 placeholder rows) while the initial fetch runs. |
| Empty | **"No tickers yet."** / **"Add your first watchlist entry to start tracking a stock or ETF."** + a prominent **"Add ticker"** primary action. No table chrome shown (no empty table with just a header). |
| Error — fetch | **"Couldn't load your watchlist."** + **"Retry"** button. |
| Add/Edit form | Fields: Ticker (text), Market (select: US/TSX/NSE), Type (select: Stock/ETF, default Stock), Status (select: Held/Watch-only). If Status = Held: Shares (number, >0), Cost basis (number, >0), and a **read-only** "Currency: `<CCY>` (from `<market>`)" label appears, derived from the selected Market — never submitted as an editable field. |
| Error — validation (inline, per field) | "Ticker is required." / "Shares must be greater than 0." / "Cost basis must be greater than 0." Shown under the offending field, not as a single top-of-form banner, so the user knows exactly which control to fix. |
| Error — save (server/RLS rejection) | **"Couldn't save. Please try again."** (generic — an RLS rejection here would indicate a bug, not a user-fixable input problem). |
| Delete confirmation | Modal/inline confirm: **"Remove `<TICKER>` from your watchlist? This can't be undone."** with **Cancel** / **Remove** (destructive style) actions. |
| Success | Inline confirmation (e.g. a toast or a brief row highlight): **"Saved."** / **"Removed."** Table updates without a full page reload. |

### 2.3 Tunables editor (FR30)

10 fixed rows (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `ALERTS_ENABLED`, `DISCOVERY_GAINER_PCT`,
`DISCOVERY_LOSER_PCT`, `DISCOVERY_VOL_SPIKE`, `DISCOVERY_MIN_MARKET_CAP`,
`DISCOVERY_MIN_MARKET_CAP_INR`, `DISCOVERY_SHORTLIST_MAX`, `DISCOVERY_PUSH_COOLDOWN_DAYS`) — the set is
fixed, never add/remove rows in this UI.

Each row/card shows: **key name**, **description**, **example value**, **current value** (editable),
**last updated** (`updated_at` + `updated_by`).

| State | Behavior / copy |
|---|---|
| Loading | Skeleton for all 10 rows. |
| Error — fetch | **"Couldn't load tunables."** + **"Retry"**. (No empty state — the 10 rows always exist once seeded; an unexpected zero-row result is an error, not "no data yet".) |
| Field type per key | `ALERTS_ENABLED` renders as a **true/false select**, never free text (structurally prevents the typo class per Decision #34). `DISCOVERY_GAINER_PCT`/`DISCOVERY_LOSER_PCT`/`DISCOVERY_VOL_SPIKE`/`DISCOVERY_MIN_MARKET_CAP`/`DISCOVERY_MIN_MARKET_CAP_INR` accept decimal numbers. `DISCOVERY_SHORTLIST_MAX`/`DISCOVERY_PUSH_COOLDOWN_DAYS` accept integers only. `GEMINI_MODEL` requires non-blank text. `GEMINI_MODEL_BACKUP` allows blank (documented as "leave empty to disable the fallback model"). |
| Error — validation (inline, per field) | "Must be a number, e.g. `5.0`." (decimal keys) / "Must be a whole number, e.g. `20`." (integer keys) / "Must be true or false." (`ALERTS_ENABLED`) / "This field can't be blank." (`GEMINI_MODEL`). Rejected before write — value is never saved. |
| Success | Row shows **"Saved"** confirmation; **"Last updated"** timestamp/actor refreshes immediately. |
| Note copy (ALERTS_ENABLED description, verbatim from seed) | "...also requires the workflow's `alerts_enabled` input to be true — true on every scheduled run by default, false only during a deliberate manual dry-run test." Rendered as-is under the field, not summarized. |

### 2.4 Track-record view (FR31)

Read-only. Columns: Ticker, Market, Verdict (Buy/Sell/Hold badge), Rationale, Price, P/L% (held tickers
only), Alerted (yes/no), Timestamp (device tz primary, IST secondary per FR23's client-render rule).
Controls: sort (by timestamp/ticker/verdict), filter (by market, by ticker), pagination. No new
aggregation/scoring — a straight, cleaner presentation of `call_log`.

| State | Behavior / copy |
|---|---|
| Loading | Skeleton rows. |
| Empty (cold start) | **"No checks logged yet."** / **"Once the system runs its next check, results will appear here."** |
| Empty (filtered to zero results) | **"No results match this filter."** + a **"Clear filter"** action. |
| Error — fetch | **"Couldn't load track record."** + **"Retry"**. |
| Success | Paginated table, current filter/sort state visible and reversible (e.g. a "Clear filter" affordance whenever a filter is active). |

### 2.5 Kill-switch toggle (FR32)

A single toggle control, persistent across the portal (surfaced in the shared header, not a standalone
page) reflecting `kill_switch_state.paused`.

| State | Behavior / copy |
|---|---|
| Loading (initial read) | Toggle shown in a disabled/muted state until the current flag value loads. |
| Running (not paused) | Toggle in the "on"/active position, label **"System: Running"**, styled with the direction's success token. |
| Paused | Toggle in the "off" position, label **"System: Paused"**, styled with the direction's warning/danger token. Sub-label: **"Last paused `<time>` by `<actor>`."** |
| In-flight (write pending) | Toggle disabled, label **"Pausing…" / "Resuming…"**. |
| Error | Toggle reverts to its prior state; a brief message: **"Couldn't update system state. Try again."** |
| Success | Toggle reflects new state immediately; sub-label updates to the new `updated_at`/`updated_by`. |

---

## 3. Design-token discipline

Every direction below is specified as **named tokens** (color/spacing/type), never inline hex/px values.
Dev's theme config (Tailwind config, CSS custom properties, or equivalent — tech-lead's call in
`docs/design.md`) should define these exact token names; components reference tokens, never literals.
The HTML mockups in `docs/ux-mockups/` implement each direction's tokens as CSS custom properties
(`--color-*`, `--space-*`, `--font-*`, `--radius-*`) for the same reason — so resizing the mockup in a
browser demonstrates the intended responsive behavior directly.

---

## 4. Direction A — "Minimal / Clean"

**Visual language:** Light theme, generous whitespace, a single accent hue, restrained borders instead
of heavy shadows, system sans-serif. Modeled on the current wave of restrained SaaS dashboards (Linear,
Vercel, Notion-style admin views) — calm, low-chrome, content-first.

### 4.1 Tokens

| Token | Value | Used for |
|---|---|---|
| `color-bg` | `#FAFAFA` | page background |
| `color-surface` | `#FFFFFF` | cards, table rows, form panels |
| `color-border` | `#E5E5E5` | hairline dividers, input borders |
| `color-text-primary` | `#18181B` | body/headings |
| `color-text-secondary` | `#71717A` | captions, helper text, timestamps |
| `color-accent` | `#4F46E5` (indigo-600) | primary buttons, links, active nav |
| `color-accent-hover` | `#4338CA` | hover/pressed state |
| `color-success` | `#16A34A` | Running / Buy / saved confirmations |
| `color-warning` | `#CA8A04` | Hold / paused |
| `color-danger` | `#DC2626` | Sell / delete / validation errors |
| `space-1`…`space-8` | `4/8/12/16/24/32/48/64px` | layout rhythm, 4px base unit |
| `font-size-xs`…`2xl` | `12/14/16/18/24/32px` | type scale, 1.25 ratio-ish |
| `font-weight-regular` / `-medium` / `-semibold` | `400/500/600` | body / labels / headings |
| `radius-sm` / `-md` | `4px / 8px` | inputs/buttons / cards |
| `shadow-sm` | 1 subtle low-opacity shadow, cards only on hover | rare, mostly border-based |

### 4.2 Watchlist & Holdings CRUD — responsive

**Desktop (≥1024px):** left sidebar nav (Watchlist, Tunables, Track Record; kill-switch + user menu in a
top header bar) + full-width data table, all columns visible, Add button top-right of the table panel.

```
┌─ Sidebar ─┬────────────────── Header: [kill-switch] [user ▾] ───────────────┐
│ Watchlist │  Watchlist & Holdings                          [+ Add ticker]   │
│ Tunables  │ ┌────────┬──────┬──────┬───────────┬──────┬───────────┬───────┐ │
│ Track Rec │ │ Ticker │ Mkt  │ Type │ Status    │Shares│Cost Basis │Actions│ │
│           │ ├────────┼──────┼──────┼───────────┼──────┼───────────┼───────┤ │
│           │ │ AAPL   │ US   │Stock │ Held      │ 10   │$150.00 USD│Edit·Del│ │
│           │ │ VOO    │ US   │ ETF  │ Held      │  5   │$410.00 USD│Edit·Del│ │
│           │ │ TD     │ TSX  │Stock │ Held      │ 25   │C$85.20 CAD│Edit·Del│ │
│           │ │ MSFT   │ US   │Stock │ Watch-only│  —   │     —     │Edit·Del│ │
│           │ │RELIANCE│ NSE  │Stock │ Watch-only│  —   │     —     │Edit·Del│ │
│           │ └────────┴──────┴──────┴───────────┴──────┴───────────┴───────┘ │
└───────────┴───────────────────────────────────────────────────────────────┘
```

**Tablet (600–1023px):** sidebar collapses to a top icon-bar (or a slide-out drawer triggered by a
hamburger); table drops the Type column (least essential at a glance) and narrows Cost Basis; Add button
moves to a floating action position or stays top-right, full width.

```
┌ ☰  Watchlist & Holdings                              [+ Add] ┐
│ ┌────────┬──────┬───────────┬──────┬──────────┬───────────┐ │
│ │ Ticker │ Mkt  │ Status    │Shares│Cost Basis │  Actions  │ │
│ ├────────┼──────┼───────────┼──────┼──────────┼───────────┤ │
│ │ AAPL   │ US   │ Held      │ 10   │$150.00 USD│ Edit · Del│ │
│ │ TD     │ TSX  │ Held      │ 25   │C$85.20 CAD│ Edit · Del│ │
│ └────────┴──────┴───────────┴──────┴──────────┴───────────┘ │
└────────────────────────────────────────────────────────────┘
```

**Phone (≤599px):** table becomes a stacked card list — one card per ticker, label/value pairs, Edit/Del
as icon buttons in the card's top-right corner; Add ticker is a full-width sticky button or a bottom
floating action button (FAB); nav becomes a bottom tab bar (Watchlist / Tunables / Track Rec) with
kill-switch accessible from a top-right icon.

```
┌ ≡  Watchlist            [⚙] ┐
│ ┌──────────────────────────┐ │
│ │ AAPL  · US · Stock  [✎][🗑]│ │
│ │ Held · 10 sh · $150.00 USD│ │
│ ├──────────────────────────┤ │
│ │ TD    · TSX · Stock [✎][🗑]│ │
│ │ Held · 25 sh · C$85.20 CAD│ │
│ ├──────────────────────────┤ │
│ │ MSFT  · US · Stock  [✎][🗑]│ │
│ │ Watch-only                │ │
│ └──────────────────────────┘ │
│      [ + Add ticker ]        │
├──────────────────────────────┤
│ [Watchlist][Tunables][Track] │  ← bottom tab bar
└──────────────────────────────┘
```

Add/Edit form on phone: a full-screen sheet (not a small modal), one field per row, the derived
Currency label appears directly under the Market select once chosen.

### 4.3 Tunables editor — responsive

**Desktop:** two-column table-like layout — key/description on the left (40%), example + current value +
last-updated + save on the right (60%), one row per key, hairline dividers between rows (no heavy card
borders, consistent with the calm aesthetic).

```
┌──────────────────────────────┬────────────────────────────────────────┐
│ GEMINI_MODEL                 │ e.g. "gemini-2.0-flash"                │
│ Primary Gemini model used    │ [ gemini-2.0-flash            ] [Save] │
│ for AI judgment calls.       │ Last updated 2026-07-20 by arjun@…      │
├──────────────────────────────┼────────────────────────────────────────┤
│ ALERTS_ENABLED                │ true / false                          │
│ Master alert switch (AND-    │ [ true ▾ ] [Save]                      │
│ gated with workflow input).  │ Last updated 2026-07-20 by arjun@…      │
└──────────────────────────────┴────────────────────────────────────────┘
```

**Tablet:** same two-column idea, narrower — description text wraps more; input width shrinks but
never below a usable ~120px.

**Phone:** each key becomes its own stacked card: key name (bold, monospace-accent), description (wraps
full width), example as a small helper line, input full-width, Save as a full-width or right-aligned
small button, last-updated as a small caption below.

```
┌ GEMINI_MODEL ───────────────┐
│ Primary Gemini model used   │
│ for AI judgment calls.      │
│ e.g. "gemini-2.0-flash"     │
│ [ gemini-2.0-flash        ] │
│              [ Save ]       │
│ Updated 2026-07-20 · arjun  │
└──────────────────────────────┘
```

### 4.4 Login / Track-record / Kill-switch — responsive summary

| Screen | Phone | Tablet | Desktop |
|---|---|---|---|
| Login | Single centered card, full-width button, ~80% viewport width | Same card, fixed max-width ~360px, centered | Same card, centered in viewport, subtle background pattern optional |
| Track record | Table → stacked cards (verdict badge + rationale + timestamp per card); filter/sort collapse into a single "Filters" sheet triggered by a button | Table with fewer columns (Rationale truncates with "…more"); filters inline as a row of selects | Full table, all columns, filters inline above the table |
| Kill-switch | Icon + label in the top bar; tapping opens a small confirm sheet before toggling (prevents accidental taps) | Same as phone or an inline toggle in the header if width allows | Inline toggle + status label directly in the persistent header, no confirm step needed (bigger hit target, mouse-precision) |

---

## 5. Direction B — "Dense / Data-forward"

**Visual language:** Dark theme by default, monospace for all data values (tickers, numbers, timestamps),
compact row height, information density prioritized over whitespace. Modeled on operator/data-console
tools (Grafana, Retool, terminal-style trading tools) — appropriate for a single power-user who wants to
scan a lot of state quickly.

### 5.1 Tokens

| Token | Value | Used for |
|---|---|---|
| `color-bg` | `#0B0E14` | page background |
| `color-surface` | `#141821` | panels, table rows |
| `color-surface-alt` | `#1B202B` | alternating row stripe |
| `color-border` | `#2A303C` | dividers |
| `color-text-primary` | `#E4E7EB` | body/headings |
| `color-text-secondary` | `#8B94A3` | captions, helper text |
| `color-accent` | `#22D3EE` (cyan-400) | active nav, links, focus ring |
| `color-accent-hover` | `#67E8F9` | hover |
| `color-success` | `#22C55E` | Running / Buy |
| `color-warning` | `#EAB308` | Hold / paused |
| `color-danger` | `#F87171` | Sell / delete / errors |
| `space-1`…`space-8` | `2/4/8/12/16/24/32/40px` | tighter rhythm than Direction A |
| `font-size-xs`…`2xl` | `11/12/14/16/20/28px` | smaller baseline, higher density |
| `font-family-mono` | monospace stack (data cells) | tickers, numbers, timestamps, keys |
| `font-family-sans` | system sans stack (labels/copy) | descriptions, buttons, nav |
| `radius-sm` | `2px` | inputs/buttons — sharper corners than A/C |
| `row-height-compact` | `32px` | table row height (vs. ~48px in A) |

### 5.2 Watchlist & Holdings CRUD — responsive

**Desktop:** persistent left rail (icon + label nav), dense table with every column plus a status-dot
column, monospace numeric alignment (right-aligned numbers), inline row-edit (click a cell to edit
in-place) rather than a separate modal, reducing navigation for a power user.

```
┌ ▎WL ▎TN ▎TR ├───────────────────────────────────────── kill:[● RUN] admin▾ ┐
│ Watchlist                                                    [+ Add row]  │
│ ┌─┬────────┬─────┬──────┬──────────┬───────┬────────────┬───────────────┐ │
│ │●│ TICKER │ MKT │ TYPE │ STATUS   │ SHARES│ COST BASIS │   ACTIONS     │ │
│ ├─┼────────┼─────┼──────┼──────────┼───────┼────────────┼───────────────┤ │
│ │●│ AAPL   │ US  │ STK  │ HELD     │    10 │  150.00 USD│ [edit] [del]  │ │
│ │●│ VOO    │ US  │ ETF  │ HELD     │     5 │  410.00 USD│ [edit] [del]  │ │
│ │●│ TD     │ TSX │ STK  │ HELD     │    25 │   85.20 CAD│ [edit] [del]  │ │
│ │○│ MSFT   │ US  │ STK  │ WATCH    │     — │          — │ [edit] [del]  │ │
│ │○│RELIANCE│ NSE │ STK  │ WATCH    │     — │          — │ [edit] [del]  │ │
│ └─┴────────┴─────┴──────┴──────────┴───────┴────────────┴───────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**Tablet:** rail collapses to icons-only (labels on tap/hover); table hides the Type column and the
per-row status dot merges into the Status text (e.g. "HELD ●"); horizontal scroll is explicitly avoided
— low-priority columns (Type) are dropped first, per NFR8.

**Phone:** rail becomes a bottom bar (WL / TN / TR icons); table converts to a compact list — each row is
a single dense line (not a padded card, consistent with the density ethos): `AAPL US·STK HELD 10sh
$150.00 [✎][🗑]`, tap the row to expand an inline detail/edit panel beneath it (accordion), rather than a
navigation to a new sheet — keeps density even at small width.

```
┌▎WL kill:[●RUN]────────────────┐
│ Watchlist          [+ Add]    │
│ AAPL  US·STK HELD 10 150.00 ⌄ │
│ ┌────────────────────────────┐│ ← expanded on tap
│ │ Shares: [10   ] Cost:[150.00││
│ │ Currency: USD (from US)    ││
│ │        [Save]  [Delete]    ││
│ └────────────────────────────┘│
│ TD    TSX·STK HELD 25 85.20 ⌄ │
│ MSFT  US·STK WATCH        —  ⌄ │
├────────────────────────────────┤
│   [WL]   [TN]   [TR]           │
└────────────────────────────────┘
```

### 5.3 Tunables editor — responsive

**Desktop:** a dense grid, 2 keys per row on very wide screens or 1 per row with a compact horizontal
layout (key | description | example | value input | updated | save) all on one line — maximizes rows
visible without scrolling for all 10 keys.

```
┌ GEMINI_MODEL          Primary model for AI judgment   e.g. gemini-2.0-flash [gemini-2.0-flash] upd:07-20 [Save] ┐
│ ALERTS_ENABLED         Master alert switch (AND-gate)  true/false            [true ▾]           upd:07-20 [Save] │
│ DISCOVERY_GAINER_PCT   Gainer-signal threshold %       e.g. 5.0              [5.0]               upd:07-15 [Save] │
```

**Tablet:** the single-line layout wraps to two lines per key (key+description on line 1, example/value/
save on line 2), still no card chrome — a hairline divider only.

**Phone:** each key collapses to a 2-line block, monospace key name as a small heading, tap to expand
description/example (accordion, matching the CRUD screen's density-preserving pattern) — value input and
Save always visible without expanding (the thing you actually edit shouldn't require a tap to reach).

```
┌ GEMINI_MODEL ⌄ ───────────────┐
│ [ gemini-2.0-flash        ]   │
│                     [Save]    │
│ upd 07-20 · arjun              │
└────────────────────────────────┘
```

### 5.4 Login / Track-record / Kill-switch — responsive summary

| Screen | Phone | Tablet | Desktop |
|---|---|---|---|
| Login | Dark full-bleed card, monospace "admin-portal" wordmark, single Google button | Same, fixed-width card ~340px | Same, centered, optional subtle grid/scanline background texture consistent with the console aesthetic |
| Track record | Dense list rows (ticker, verdict-dot, price, time), tap row for full rationale in an expand panel | Table, Rationale column truncated with hover/tap-to-reveal | Full dense table, all columns, sortable column headers (click to sort, no separate sort UI needed) |
| Kill-switch | Status dot + text always visible in top bar (`● RUN` / `● PAUSE`), tap opens confirm | Inline toggle in header | Inline toggle + dot + last-changed caption, all in the persistent header |

---

## 6. Direction C — "Card-based / Friendly SaaS"

**Visual language:** Light theme, soft rounded corners, layered shadows instead of hairlines, generous
color-coded badges, content organized as cards/tiles rather than raw tables wherever it aids scanability.
Modeled on approachable modern SaaS product UIs (Stripe Dashboard, shadcn/ui component patterns) —
friendlier and more visual than Direction A, while still calmer than Direction B.

### 6.1 Tokens

| Token | Value | Used for |
|---|---|---|
| `color-bg` | `#F4F5F7` | page background |
| `color-surface` | `#FFFFFF` | cards |
| `color-border` | `#E8E9ED` (used sparingly — shadows do most separation) | rare hairlines |
| `color-text-primary` | `#1F2430` | headings/body |
| `color-text-secondary` | `#6B7280` | captions |
| `color-accent` | `#7C3AED` (violet-600) | primary buttons, active states |
| `color-accent-hover` | `#6D28D9` | hover |
| `color-success-bg` / `-fg` | `#DCFCE7` / `#166534` | Held/Buy/Running badges |
| `color-warning-bg` / `-fg` | `#FEF3C7` / `#92400E` | Hold/Paused badges |
| `color-danger-bg` / `-fg` | `#FEE2E2` / `#991B1B` | Sell/error/delete badges |
| `color-info-bg` / `-fg` | `#DBEAFE` / `#1E40AF` | Watch-only/informational badges |
| `space-1`…`space-8` | `4/8/16/20/24/32/48/64px` | slightly airier than Direction A at the card level |
| `font-size-xs`…`2xl` | `12/14/16/20/28/36px` | rounder, larger headings than A/B |
| `radius-md` / `-lg` | `12px / 20px` | cards, buttons, badges (pill-shaped) |
| `shadow-card` | soft, low-opacity, multi-layer | every card's default resting state |

### 6.2 Watchlist & Holdings CRUD — responsive

**Desktop:** a 3-column card grid (each ticker is a card, not a table row) with a top toolbar (search +
Add ticker + view toggle table/cards, table view available as a density option but cards is the default
here); each card shows ticker, market/type pill badges, status pill, shares/cost-basis if held, and
Edit/Delete icon buttons in the card footer.

```
┌ [🔍 Search]                                    [Table|Cards] [+ Add ticker] ┐
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                     │
│ │ AAPL   (US)   │ │ VOO    (US)   │ │ TD     (TSX)  │                     │
│ │ Stock ● Held  │ │ ETF   ● Held  │ │ Stock ● Held  │                     │
│ │ 10 sh          │ │ 5 sh          │ │ 25 sh         │                     │
│ │ $150.00 USD    │ │ $410.00 USD   │ │ C$85.20 CAD   │                     │
│ │      [✎] [🗑]  │ │      [✎] [🗑]  │ │      [✎] [🗑]  │                     │
│ └───────────────┘ └───────────────┘ └───────────────┘                     │
│ ┌───────────────┐ ┌───────────────┐                                       │
│ │ MSFT   (US)   │ │RELIANCE (NSE) │                                       │
│ │ Stock ◐ Watch │ │ Stock ◐ Watch │                                       │
│ │      [✎] [🗑]  │ │      [✎] [🗑]  │                                       │
│ └───────────────┘ └───────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Tablet:** grid drops to 2 columns; card content unchanged.

**Phone:** grid drops to 1 column (full-width cards, stacked); Add ticker becomes a bottom FAB
(floating "+" button); search collapses behind a search icon that expands to a full-width field on tap.

```
┌ ☰  Watchlist        [🔍] ┐
│ ┌───────────────────────┐│
│ │ AAPL   (US)    Stock  ││
│ │ ● Held · 10 sh        ││
│ │ $150.00 USD           ││
│ │            [✎]  [🗑]  ││
│ └───────────────────────┘│
│ ┌───────────────────────┐│
│ │ TD     (TSX)   Stock  ││
│ │ ● Held · 25 sh        ││
│ │ C$85.20 CAD           ││
│ │            [✎]  [🗑]  ││
│ └───────────────────────┘│
│                     ( + )│ ← FAB
├───────────────────────────┤
│ [Watchlist][Tunables][TR] │
└───────────────────────────┘
```

Add/Edit form: a rounded bottom-sheet on phone (slides up), a centered modal card on tablet/desktop; the
derived Currency shown as a pill badge next to the Market field once selected, e.g. "🇨🇦 CAD".

### 6.3 Tunables editor — responsive

**Desktop:** an accordion-of-cards, one card per key, collapsed by default showing key + current value +
a "modified" pill if changed from the seed; expand to reveal description/example/save. A 2-column
masonry layout for the 10 cards to reduce scroll on wide screens.

```
┌ [GEMINI_MODEL         gemini-2.0-flash        ⌄] ┌ [ALERTS_ENABLED       true            ⌄] │
│ [GEMINI_MODEL_BACKUP  (blank)                 ⌄] ┌ [DISCOVERY_GAINER_PCT  5.0             ⌄] │
```

Expanded card:
```
┌ GEMINI_MODEL                                    ▼ ┐
│ Primary Gemini model used for AI judgment calls.   │
│ Example: gemini-2.0-flash                          │
│ [ gemini-2.0-flash                    ]  [ Save ]  │
│ Last updated 2026-07-20 by arjun@…                  │
└─────────────────────────────────────────────────────┘
```

**Tablet:** single-column accordion (masonry drops to 1 column), same card content.

**Phone:** identical accordion pattern, full width, one open card at a time recommended (opening a new
one collapses the previous) to keep scroll length manageable.

### 6.4 Login / Track-record / Kill-switch — responsive summary

| Screen | Phone | Tablet | Desktop |
|---|---|---|---|
| Login | Rounded illustration/logo card, full-width Google button with pill shape | Centered card, ~380px, soft shadow | Centered card on a soft gradient/pattern background |
| Track record | Each `call_log` row as a compact card (verdict pill, ticker, price, relative time); tap to expand full rationale | 2-column card grid or a simplified table with pill badges for verdict | Full table with verdict pills, filter chips (pill-shaped, removable) above the table |
| Kill-switch | A pill-shaped status badge in the header ("🟢 Running" / "🟠 Paused"), tap opens a confirm bottom-sheet | Inline pill toggle in header | Inline pill + toggle switch + "last changed" caption in the persistent header |

---

## 7. Mockup files

Static, self-contained HTML/CSS (no build step) demonstrating each direction with realistic sample data.
Resize the browser window to see the phone/tablet/desktop behavior described above.

| Direction | File |
|---|---|
| A — Minimal / Clean | `docs/ux-mockups/direction-a-minimal.html` |
| B — Dense / Data-forward | `docs/ux-mockups/direction-b-dense.html` |
| C — Card-based / Friendly SaaS | `docs/ux-mockups/direction-c-cards.html` |

Each file includes: Login, Watchlist & Holdings CRUD (with an open Add/Edit form example), Tunables
editor, Track-record view, and the kill-switch toggle in its header — all five FR27–FR32 screens, with
sample data matching the rows used in the wireframes above (AAPL, VOO, TD, MSFT, RELIANCE).

---

## 8. Selection & next steps

Per NFR8, Arjun reviews the three mockup files (and this spec) and selects exactly one direction — this
selection is the GATE; dev may not start implementing any visual/responsive change before it happens.
Once selected:
- tech-lead records the chosen direction, the exact breakpoint pixel values, and the token→theme-config
  mapping in `docs/design.md` (or a module file) before INC start.
- This spec's §2 (states/copy) applies unchanged regardless of which direction is picked — it is not a
  per-direction choice.
- Any deviation between the implemented UI and the selected direction's mockups is logged by reviewer in
  `docs/review-log.md` tagged `[UX-GAP]`, per this agent's standing responsibility.

## 9. Requirement traceability

| FR | Screen | Covered in |
|---|---|---|
| FR27 | Login | §2.1, §4.4/§5.4/§6.4 |
| FR28 | Watchlist CRUD | §2.2, §4.2/§5.2/§6.2 |
| FR29 | Holdings CRUD (same screen) | §2.2, §4.2/§5.2/§6.2 |
| FR30 | Tunables editor | §2.3, §4.3/§5.3/§6.3 |
| FR31 | Track-record view | §2.4, §4.4/§5.4/§6.4 |
| FR32 | Kill-switch toggle | §2.5, §4.4/§5.4/§6.4 |
