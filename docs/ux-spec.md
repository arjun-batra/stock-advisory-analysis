# Admin Portal — UX Spec (NFR8: Responsive & Modern Visual Redesign)

**Owner:** designer. **Scope:** NFR8 only — a UI/UX-only visual and responsive redesign of the five
existing admin portal screens. **No functional change**: FR27–FR32 behavior, the `is_admin()`/RLS
authorization model, and the data model are untouched (see `docs/design/admin-portal.md` §16,
`docs/design/admin-portal-tunables.md`). This spec covers presentation only — layout, visual language,
states, copy, and responsive behavior.

**Gate:** per NFR8, Arjun selects exactly one direction below before any implementation starts. No
speculative screens are proposed — every screen here maps 1:1 to an existing FR.

**GATE CLEARED (2026-07-31): Direction G — "Compact Toggle" is SELECTED / APPROVED by Arjun.** This is
the final direction — no further direction iteration. Dev implements Direction G (§7.4) for INC-13.
Direction B remains rejected (§5). Directions A, C, D, E, F remain documented below as non-selected
alternates, kept for historical/traceability record only — they are not candidates for implementation.

| Screen | FR | Current content (source of truth) |
|---|---|---|
| Login | FR27 | Google OAuth button; allowlist check + reject UX (`admin-portal.md` §16.2) |
| Watchlist & Holdings CRUD | FR28, FR29 | `watchlist` (ticker, market, type, status) + `holdings` (shares, cost_basis, derived currency) (`admin-portal.md` §16.3) |
| Tunables editor | FR30 | 10 curated keys, each with description/example/current value (`admin-portal-tunables.md` §16.4) |
| Track-record view | FR31 | Read-only `call_log` / `latest_call_per_ticker` data, pagination/sort/filter only, no new aggregation (`admin-portal.md` §16.5) |
| Kill-switch toggle | FR32 | Reads/writes `kill_switch_state.paused` via `set_kill_switch()` RPC (`admin-portal.md` §16.6) |

> **2026-08-01 change request (FR36–FR38, Decision #40):** the Watchlist and Holdings rows above are
> merged into a single **"Tickers"** screen, the portal renamed to **"Sentinel Portal,"** and the nav
> redesigned — see **§11** for the full spec and `docs/ux-mockups/direction-g-tickers-merge.html` for the
> mockup. The table above is left as-is for historical/traceability context on the pre-merge NFR8 scope.

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

Each row/card shows: **friendly label** (primary heading), **raw key name** (demoted — small monospace
subtitle directly under the friendly label, so Arjun can still map a field back to `scripts/config.py`),
**description**, **example value**, **current value** (editable), **last updated** (`updated_at` +
`updated_by`).

**Friendly-label mapping (2026-07-31, presentation-layer refinement of FR30 — labels only, no change to
the underlying keys, validation, or storage):** every mockup that renders the tunables editor (directions
A, C, D, E, F, G — all active candidates) leads with the friendly label below and demotes the raw
`SNAKE_CASE` key to a small monospace line beneath it, never dropping the raw key entirely. This table is
the single source of truth for the mapping — dev implements these exact strings verbatim in INC-13, not
the raw key names, as the primary on-screen label.

| Raw key (`scripts/config.py` / `tunables` table) | Friendly label (primary heading) |
|---|---|
| `GEMINI_MODEL` | Primary AI model |
| `GEMINI_MODEL_BACKUP` | Backup AI model |
| `ALERTS_ENABLED` | Alerts on/off switch |
| `DISCOVERY_GAINER_PCT` | Gainer threshold (%) |
| `DISCOVERY_LOSER_PCT` | Loser threshold (%) |
| `DISCOVERY_VOL_SPIKE` | Volume spike multiple |
| `DISCOVERY_MIN_MARKET_CAP` | Min. market cap — US/CA |
| `DISCOVERY_MIN_MARKET_CAP_INR` | Min. market cap — NSE |
| `DISCOVERY_SHORTLIST_MAX` | Max daily candidates |
| `DISCOVERY_PUSH_COOLDOWN_DAYS` | Re-alert cooldown (days) |

Note: the non-selected alternate mockups (A, C, D, E, F — historical record only, per §9) sample only a
subset of these 10 keys in their illustrative data (varies 4–6 keys per direction, consistent with each
file's existing sample-data scope); the table above is authoritative for **all 10** curated keys
regardless of which subset a given non-selected mockup happens to render. **Direction G's mockup
(`docs/ux-mockups/direction-g-compact-toggle.html`), as the SELECTED/canonical reference for INC-13, is
the exception: it renders all 10 curated keys**, each with the friendly label from the mapping table
above. The `description`/`example`/`current value` fields and their copy are unchanged from the rest of
this section — only the primary heading and the demotion of the raw key are new.

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

**Desktop:** two-column table-like layout — friendly label + demoted raw key + description on the left
(40%), example + current value + last-updated + save on the right (60%), one row per key, hairline
dividers between rows (no heavy card borders, consistent with the calm aesthetic). The friendly label is
the bold primary heading; the raw key renders directly beneath it as a small monospace-secondary line
(never removed — see the friendly-label mapping table above).

```
┌──────────────────────────────┬────────────────────────────────────────┐
│ Primary AI model              │ e.g. "gemini-2.0-flash"                │
│ GEMINI_MODEL                  │ [ gemini-2.0-flash            ] [Save] │
│ Primary Gemini model used     │ Last updated 2026-07-20 by arjun@…      │
│ for AI judgment calls.        │                                         │
├──────────────────────────────┼────────────────────────────────────────┤
│ Alerts on/off switch          │ true / false                          │
│ ALERTS_ENABLED                │ [ true ▾ ] [Save]                      │
│ Master alert switch (AND-     │ Last updated 2026-07-20 by arjun@…      │
│ gated with workflow input).   │                                         │
└──────────────────────────────┴────────────────────────────────────────┘
```

**Tablet:** same two-column idea, narrower — description text wraps more; input width shrinks but
never below a usable ~120px.

**Phone:** each key becomes its own stacked card: friendly label (bold, primary heading), raw key name
demoted directly beneath it (small monospace, secondary color), description (wraps full width), example
as a small helper line, input full-width, Save as a full-width or right-aligned small button,
last-updated as a small caption below.

```
┌ Primary AI model ────────────┐
│ GEMINI_MODEL                 │
│ Primary Gemini model used    │
│ for AI judgment calls.       │
│ e.g. "gemini-2.0-flash"      │
│ [ gemini-2.0-flash         ] │
│              [ Save ]        │
│ Updated 2026-07-20 · arjun   │
└───────────────────────────────┘
```

### 4.4 Login / Track-record / Kill-switch — responsive summary

| Screen | Phone | Tablet | Desktop |
|---|---|---|---|
| Login | Single centered card, full-width button, ~80% viewport width | Same card, fixed max-width ~360px, centered | Same card, centered in viewport, subtle background pattern optional |
| Track record | Table → stacked cards (verdict badge + rationale + timestamp per card); filter/sort collapse into a single "Filters" sheet triggered by a button | Table with fewer columns (Rationale truncates with "…more"); filters inline as a row of selects | Full table, all columns, filters inline above the table |
| Kill-switch | Icon + label in the top bar; tapping opens a small confirm sheet before toggling (prevents accidental taps) | Same as phone or an inline toggle in the header if width allows | Inline toggle + status label directly in the persistent header, no confirm step needed (bigger hit target, mouse-precision) |

---

## 5. Direction B — "Dense / Data-forward" — **REJECTED by Arjun (2026-07-31)**

> **Status: rejected.** Arjun reviewed directions A, B, and C and said: *"I like A and C, more ideas
> with those as baseline."* B (dark theme, monospace, dense data-console aesthetic) is ruled out
> entirely — no further iteration on this direction. Section kept below, unedited, for traceability
> only (per document-hygiene: decisions are recorded, not deleted). New variations (§7–§9) build only
> on A's and C's visual language, never reintroducing B's dark/monospace/console aesthetic.

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

**Desktop:** an accordion-of-cards, one card per key, collapsed by default showing the friendly label
(primary, bold) with the raw key demoted beneath it (small monospace-secondary) + current value + a
"modified" pill if changed from the seed; expand to reveal description/example/save. A 2-column masonry
layout for the 10 cards to reduce scroll on wide screens.

```
┌ [Primary AI model              gemini-2.0-flash ⌄] ┌ [Alerts on/off switch          true    ⌄] │
│ [ GEMINI_MODEL                                    ] │ [ ALERTS_ENABLED                        ] │
```

Expanded card:
```
┌ Primary AI model                                ▼ ┐
│ GEMINI_MODEL                                       │
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

## 7. New variations — siblings of A and C

Per Arjun's 2026-07-31 review feedback ("I like A and C, more ideas with those as baseline"), the three
directions below are **not** a fourth fresh concept — each is explicitly derived from Direction A's or
Direction C's tokens/layout (§4/§6), varying accent color, typography, card density, or which specific
screens get card treatment vs. hairline-table treatment. None reintroduce Direction B's dark theme,
monospace, or console density (§5, rejected). The shared UX contract (§2 states/copy) is unchanged —
these are visual/layout variations only, same as A/B/C were.

### 7.1 Direction D — "Warm Minimal" (baseline: Direction A)

**Visual language:** Identical structure and restraint to Direction A — light theme, hairline borders,
single accent, generous whitespace, sidebar nav, table-first layout. The variation is the palette and
typographic voice: a warm terracotta accent and off-white/cream background (instead of A's cool
grey/indigo), plus a serif typeface reserved for headings only (body copy stays the same system sans as
A) for a slightly more editorial, less corporate feel. No layout, breakpoint, or component change from
A — every wireframe in §4.2–§4.4 applies unchanged to this direction.

#### 7.1.1 Tokens (deltas from Direction A — unlisted tokens are identical to §4.1)

| Token | Value | Used for |
|---|---|---|
| `color-bg` | `#FDF8F3` | page background (warm off-white vs. A's cool `#FAFAFA`) |
| `color-surface` | `#FFFFFF` | cards, table rows, form panels (unchanged) |
| `color-border` | `#E7DFD3` | hairline dividers, input borders (warm-tinted grey) |
| `color-text-primary` | `#231B14` | body/headings (warm near-black) |
| `color-text-secondary` | `#8A7A68` | captions, helper text, timestamps |
| `color-accent` | `#C2410C` (orange-700, terracotta) | primary buttons, links, active nav — replaces A's indigo |
| `color-accent-hover` | `#9A3412` | hover/pressed state |
| `color-success` | `#15803D` | Running / Buy / saved confirmations |
| `color-warning` | `#A16207` | Hold / paused |
| `color-danger` | `#B91C1C` | Sell / delete / validation errors |
| `font-family-serif` | `"Iowan Old Style","Palatino Linotype",Georgia,serif` | **new token** — section/screen headings and login title only; all body copy, labels, buttons, and table content remain the system sans stack from A |
| `space-*` / `font-size-*` (body) / `radius-*` / `shadow-sm` | identical to Direction A §4.1 | layout rhythm, type scale, corner radii unchanged |

#### 7.1.2 Layout, responsive behavior, states

Identical to Direction A §4.2–§4.4 in every respect (desktop sidebar + table, tablet icon-rail +
dropped Type column, phone stacked cards + bottom tab bar, full-screen sheet for Add/Edit). No new
wireframes are needed — see §4 directly. Mockup: `docs/ux-mockups/direction-d-warm-minimal.html`.

### 7.2 Direction E — "Minimal / Card Hybrid" (baseline: Direction A + Direction C)

**Visual language:** A deliberate per-screen hybrid, not a blend of every pixel. Chrome (sidebar, header,
kill-switch toggle), Login, the Tunables editor, and the Track-record table keep Direction A's calm
hairline-border restraint exactly as specified in §4. The Watchlist & Holdings CRUD screen — the one
screen that is fundamentally about individual entities (each ticker is a "thing" with its own state) —
uses Direction C's soft-shadow card-grid treatment instead of a table, on the reasoning that cards suit
entity browsing while tables/lists suit logs and settings. Shadow depth is toned down from C's fuller
`shadow-card` to a lighter single-layer + soft-glow shadow, so the card screen still reads as "restrained
A family" rather than "full C". Accent is teal (distinct from both A's indigo and C's violet) to signal
that this is its own direction, not a re-skin.

#### 7.2.1 Tokens

| Token | Value | Used for |
|---|---|---|
| `color-bg` | `#FAFAFA` | page background (Direction A's) |
| `color-surface` | `#FFFFFF` | cards, table rows, form panels |
| `color-border` | `#E5E5E5` | hairline dividers, input borders (Direction A's) |
| `color-text-primary` | `#18181B` | body/headings |
| `color-text-secondary` | `#71717A` | captions, helper text, timestamps |
| `color-accent` | `#0D9488` (teal-600) | primary buttons, links, active nav, watchlist card accents |
| `color-accent-hover` | `#0F766E` | hover/pressed state |
| `color-success` | `#16A34A` | Running / Buy / saved confirmations |
| `color-warning` | `#CA8A04` | Hold / paused |
| `color-danger` | `#DC2626` | Sell / delete / validation errors |
| `space-*` / `font-size-*` | identical to Direction A §4.1 | layout rhythm, type scale |
| `radius-sm` / `-md` | `4px / 8px` | inputs/buttons/tables (Direction A's, for hairline-treated screens) |
| `radius-lg` | `14px` | **new token** — watchlist card corners only (between A's 8px and C's 20px, deliberately more restrained than C) |
| `shadow-card` | `0 1px 2px rgba(15,20,20,0.04), 0 2px 8px rgba(15,20,20,0.05)` | **new token** — watchlist cards only; lighter than Direction C's `shadow-card` |

#### 7.2.2 Screen-by-screen treatment

| Screen | Treatment | Notes |
|---|---|---|
| Login (FR27) | Direction A's hairline card, no shadow flourish | Unchanged from §4.4/§2.1 |
| Watchlist & Holdings CRUD (FR28, FR29) | **Direction C's card grid** (3-col desktop / 2-col tablet / 1-col phone, FAB on phone), toned-down shadow per §7.2.1 | Card content identical to §6.2's ticker-card anatomy (ticker, market/type pills, status pill, shares/cost-basis, edit/delete icon buttons). Add/Edit form is a centered panel (soft-shadow, matching card treatment), not a full hairline form-panel. |
| Tunables editor (FR30) | **Direction A's hairline two-column row layout**, unchanged | Same as §4.3 — no cards, no accordion; a deliberately calmer settings screen distinct from the card-heavy watchlist |
| Track-record view (FR31) | **Direction A's table** on tablet/desktop; verdict rendered as a small pill (light nod to C) rather than a square badge; phone collapses to simple stacked cards (lighter-weight than the watchlist's cards, no shadow) for readability at narrow widths | Filters/sort/pagination behavior unchanged from §2.4 |
| Kill-switch (FR32) | Direction A's toggle + label in the persistent header | Unchanged from §4.4/§2.5 |

Responsive breakpoints (phone ≤599px / tablet 600–1023px / desktop ≥1024px) match §1's illustrative
pixels throughout. Mockup: `docs/ux-mockups/direction-e-hybrid.html`.

### 7.3 Direction F — "Compact Cards" (baseline: Direction C, denser variant)

**Visual language:** Same friendly-SaaS card language as Direction C — light theme, rounded corners,
pill badges, card-based layout for entities — turned up in information density: a flatter single-layer
shadow (vs. C's layered soft shadow), smaller corner radii, tighter spacing scale, and more cards per row
at each breakpoint. The Tunables editor departs furthest from C: instead of an accordion where only the
value peeks out until expanded, all 10 keys render as always-visible compact cards (key, description,
example, input, and Save all visible without a tap) — because for a single power-user, an extra tap per
key to reach the very control they're there to use is unnecessary friction; density here serves the same
"see everything at once" goal C's Watchlist and Track-record screens already have. Accent is emerald,
distinct from C's violet, so the two directions are never visually confusable side-by-side.

#### 7.3.1 Tokens (deltas from Direction C — unlisted tokens follow the same naming scheme as §6.1)

| Token | Value | Used for |
|---|---|---|
| `color-bg` | `#F4F5F7` | page background (same as C) |
| `color-surface` | `#FFFFFF` | cards (same as C) |
| `color-border` | `#E8E9ED` | rare hairlines (same as C) |
| `color-text-primary` | `#1F2430` | headings/body (same as C) |
| `color-text-secondary` | `#6B7280` | captions (same as C) |
| `color-accent` | `#059669` (emerald-600) | primary buttons, active states — replaces C's violet |
| `color-accent-hover` | `#047857` | hover |
| `color-success-bg` / `-fg`, `color-warning-bg` / `-fg`, `color-danger-bg` / `-fg`, `color-info-bg` / `-fg` | same values as Direction C §6.1 | badge/pill backgrounds |
| `space-1`…`space-8` | `4/6/10/14/18/24/36/48px` | **tighter than C's** `4/8/16/20/24/32/48/64px` |
| `font-size-xs`…`2xl` | `11/13/15/17/22/28px` | **smaller than C's** `12/14/16/20/28/36px` |
| `radius-md` | `8px` | inputs, tunable cards, track-record cards (vs. C's `12px`) |
| `radius-lg` | `14px` | watchlist cards, modals (vs. C's `20px`) |
| `shadow-card` | `0 1px 2px rgba(20,20,43,0.08)` | **single-layer, flatter** than Direction C's two-layer shadow |

#### 7.3.2 Screen-by-screen density changes vs. Direction C

| Screen | Direction C (§6) | Direction F (this) |
|---|---|---|
| Watchlist & Holdings CRUD | 3-col card grid desktop / 2-col tablet / 1-col phone | **4-col** desktop / 3-col tablet / 2-col phone — same card anatomy, tighter padding |
| Tunables editor | Accordion-of-cards, collapsed by default, 2-col masonry desktop | **Always-visible compact cards** (no expand/collapse), 3-col grid desktop / 2-col tablet / 1-col phone — value input and Save visible without a tap |
| Track-record view | 2-col card grid (all breakpoints capped there) | **3-col** card grid desktop / 2-col tablet / 1-col phone, tighter card padding |
| Login | Centered card, ~380px, soft shadow, pill button | Same layout, narrower card (~340px), flatter shadow, smaller logo circle |
| Kill-switch | Pill status badge + toggle in header | Same pattern, same pill/toggle components, just the emerald accent + tighter header padding |

Responsive breakpoints (phone ≤599px / tablet 600–1023px / desktop ≥1024px) match §1's illustrative
pixels throughout. Mockup: `docs/ux-mockups/direction-f-compact-cards.html`.

### 7.4 Direction G — "Compact Toggle" (baseline: Direction F density + Direction E's kill-switch treatment) — **SELECTED / APPROVED by Arjun (2026-07-31)**

> **Status: SELECTED.** This is the final, approved direction for INC-13 implementation — the NFR8 gate
> is cleared. No further direction iteration follows this decision; any future visual change to the admin
> portal is a change request against this selected direction, not a new candidate direction.

**Visual language:** Not a new palette or layout — Direction G is Direction F (§7.3), unchanged, in
every respect (tokens, card density, 4-col watchlist grid, always-visible compact tunable cards,
flatter single-layer shadow, tighter spacing scale) **except** the kill-switch control in the shared
header. Per Arjun's 2026-07-31 review of D/E/F ("I like System toggle in E but I like compactness of
F"), F's static pill badge (`<span class="pill running">🟢 System: Running</span>`) is replaced with
Direction E's interactive sliding toggle-switch component (§7.2, the `.toggle` element next to the
"System: Running"/"System: Paused" label) — same on/off sliding mechanic and green-running /
grey-and-shifted-left-paused color logic as E — resized down to F's tighter compact scale. No other
screen, token, or layout changes anywhere in this direction; every other wireframe/table in §7.3
(§7.3.1 tokens, §7.3.2 density table) applies to Direction G unchanged.

#### 7.4.1 Tokens

Identical to Direction F §7.3.1 — no new or changed color/spacing/type/radius/shadow tokens. This is a
component-treatment change, not a new palette.

#### 7.4.2 Kill-switch component — treatment delta from Direction F

| Aspect | Direction F (§7.3, replaced) | Direction G (this) |
|---|---|---|
| Markup | `<span class="pill running">🟢 System: Running</span>` / `<span class="pill paused">🟠 System: Paused</span>` — a single static pill element | `<div class="killswitch"><span>System: Running</span><div class="toggle"></div></div>` — a label plus a separate sliding toggle-switch element, matching Direction E's `.killswitch`/`.toggle` structure (§7.2.1's `docs/ux-mockups/direction-e-hybrid.html` lines 62–65, 234) |
| Interaction affordance | Pill communicates state only; the tap/click target for toggling isn't visually distinguished from a status label | Toggle-switch shape itself signals "this is the control" (thumb + track), same affordance logic as a native OS toggle — clicking/tapping the toggle (not just a surrounding pill) triggers the state change, consistent with the shared UX contract's kill-switch interaction states (§2.5) |
| Running state | `.pill.running` — `background: var(--color-success-bg)`, `color: var(--color-success-fg)`, 🟢 emoji prefix | `.toggle` (no `.paused` class) — track `background: var(--color-accent)` (F's emerald), thumb (white circle) slid to the right via `::after{ right:2px }` |
| Paused state | `.pill.paused` — `background: var(--color-warning-bg)`, `color: var(--color-warning-fg)`, 🟠 emoji prefix | `.toggle.paused` — track `background: var(--color-border)` (grey), thumb slid to the left via `::after{ right:auto; left:2px }` — same class-driven sliding mechanic as Direction E, just re-scaled |
| Sizing (compact-scale adaptation) | Pill: `padding: 3px var(--space-3)`, `font-size: var(--font-size-xs)` (F's 11px) | Toggle track: 30×17px, thumb: 13px circle — scaled down from Direction E's 36×20px track / 16px thumb (built on F's `--space-1`/`--space-2` rhythm rather than E's larger `--space-2`/`--space-4`, consistent with F's overall tighter density) |
| Label text | Embedded inside the pill string, with emoji | Separate `<span>System: Running</span>` sibling to the left of the toggle, `font-size: var(--font-size-sm)` (F's 13px), no emoji — matches Direction E's label/toggle split, dropping the emoji to fit F's flatter/icon-light visual language (F uses emoji only for nav icons, not status pills elsewhere per §7.3) |
| States (loading/in-flight/error/success) | Governed entirely by the shared UX contract, §2.5 — unchanged by this component swap. In Direction G: loading = toggle muted/disabled (reduced opacity, no pointer events); in-flight = toggle disabled, label reads "Pausing…"/"Resuming…"; error = toggle snaps back to prior position + brief inline message below the header; success = toggle position updates immediately, label updates to match |

No other screen (login, watchlist/holdings CRUD, tunables editor, track-record) differs from Direction
F — see §7.3.2's density table, which applies unchanged. Responsive breakpoints (phone ≤599px / tablet
600–1023px / desktop ≥1024px) match §1's illustrative pixels throughout, identical to every other
direction's mockup. Mockup: `docs/ux-mockups/direction-g-compact-toggle.html`.

#### 7.4.3 Extension (2026-08-01 change request; FR36–FR38; Decision #40)

Direction G is extended, not replaced, to cover the Tickers-merge, click-to-modal, and nav-redesign
change request. All of §7.4/§7.4.1/§7.4.2 above remains true and unchanged (tokens, kill-switch toggle
component, every other screen's density). The delta is specified in full in **§11** below, and rendered
in a new mockup file, `docs/ux-mockups/direction-g-tickers-merge.html`, which shares §7.3.1's exact token
set (no new palette) and layers only the FR36–FR38 changes on top of the existing canonical
`direction-g-compact-toggle.html`. §11 is the canonical reference for the merged Tickers screen and the
redesigned nav going forward; `direction-g-compact-toggle.html` remains the canonical reference for
Login, Tunables, Track-record, and the kill-switch component, which are untouched by this change request.

---

## 8. Mockup files

Static, self-contained HTML/CSS (no build step) demonstrating each direction with realistic sample data.
Resize the browser window to see the phone/tablet/desktop behavior described above.

| Direction | Status | File |
|---|---|---|
| A — Minimal / Clean | non-selected alternate (historical record) | `docs/ux-mockups/direction-a-minimal.html` |
| B — Dense / Data-forward | **rejected** (Arjun, 2026-07-31) | `docs/ux-mockups/direction-b-dense.html` |
| C — Card-based / Friendly SaaS | non-selected alternate (historical record) | `docs/ux-mockups/direction-c-cards.html` |
| D — Warm Minimal (baseline: A) | non-selected alternate (historical record) | `docs/ux-mockups/direction-d-warm-minimal.html` |
| E — Minimal / Card Hybrid (baseline: A + C) | non-selected alternate (historical record) | `docs/ux-mockups/direction-e-hybrid.html` |
| F — Compact Cards (baseline: C) | non-selected alternate (historical record) | `docs/ux-mockups/direction-f-compact-cards.html` |
| G — Compact Toggle (baseline: F density + E's kill-switch toggle) | **SELECTED / APPROVED by Arjun (2026-07-31) — dev implements this for INC-13** | `docs/ux-mockups/direction-g-compact-toggle.html` |
| G — Tickers merge extension (FR36–FR38, 2026-08-01 CR; baseline: G, §7.4.3/§11) | **SELECTED / APPROVED by Arjun (2026-08-01) — dev implements this for INC-15** | `docs/ux-mockups/direction-g-tickers-merge.html` |

Each file includes: Login, Watchlist & Holdings CRUD (with an open Add/Edit form example), Tunables
editor, Track-record view, and the kill-switch toggle in its header — all five FR27–FR32 screens, with
sample data matching the rows used in the wireframes above (AAPL, VOO, TD, MSFT, RELIANCE). The exception
is `direction-g-tickers-merge.html`, which per §11 shows the merged Tickers screen (superseding the
Watchlist/Holdings screens) and the redesigned nav, and does not re-render Login/Tunables/Track-record
(unchanged — see `direction-g-compact-toggle.html` for those).

---

## 9. Selection & next steps

**GATE 3 (NFR8 direction selection) is CLEARED.** Arjun reviewed the mockup files (and this spec) and
selected **Direction G — "Compact Toggle" (§7.4), approved 2026-07-31**. This is the single source of
truth dev implements for INC-13 — no other direction (A, C, D, E, F — non-selected alternates kept for
historical record; B — rejected, §5) is a candidate for implementation. No further direction iteration
follows this decision.

Canonical reference for INC-13: `docs/ux-spec.md` §7.4 (Direction G spec) + §7.3 (Direction F density,
which G inherits unchanged except the kill-switch component per §7.4.2) + §2 (shared states/copy, applies
to every direction identically) + `docs/ux-mockups/direction-g-compact-toggle.html` (canonical HTML
reference, all 10 FR30 tunable keys represented per §2.3's friendly-label mapping table).

Next steps now that the gate is cleared:
- tech-lead records Direction G, the exact breakpoint pixel values, and the token→theme-config mapping
  (§7.3.1 tokens, unchanged for G) in `docs/design.md` (or a module file) before INC-13 starts.
- This spec's §2 (states/copy) applies unchanged — it was never a per-direction choice.
- Any deviation between the implemented UI and Direction G's mockup/spec is logged by reviewer in
  `docs/review-log.md` tagged `[UX-GAP]`, per this agent's standing responsibility.

## 10. Requirement traceability

| FR | Screen | Covered in |
|---|---|---|
| FR27 | Login | §2.1, §4.4/§5.4/§6.4/§7.1.2/§7.2.2/§7.3.2/§7.4 (unchanged from F) |
| FR28 | Watchlist CRUD | §2.2, §4.2/§5.2/§6.2/§7.1.2/§7.2.2/§7.3.2/§7.4 (unchanged from F) |
| FR29 | Holdings CRUD (same screen) | §2.2, §4.2/§5.2/§6.2/§7.1.2/§7.2.2/§7.3.2/§7.4 (unchanged from F) |
| FR30 | Tunables editor | §2.3, §4.3/§5.3/§6.3/§7.1.2/§7.2.2/§7.3.2/§7.4 (unchanged from F) |
| FR31 | Track-record view | §2.4, §4.4/§5.4/§6.4/§7.1.2/§7.2.2/§7.3.2/§7.4 (unchanged from F) |
| FR32 | Kill-switch toggle | §2.5, §4.4/§5.4/§6.4/§7.1.2/§7.2.2/§7.3.2, §7.4.2 (Direction G's toggle-treatment delta) |
| FR28 (amended 2026-08-01) | Tickers screen (relocated from standalone Watchlist) | §11.2/§11.3 — CRUD/validation unchanged, screen/nav surface only |
| FR29 (amended 2026-08-01) | Tickers screen/modal (relocated from standalone Holdings) | §11.2/§11.3/§11.4/§11.5 — CRUD/validation unchanged; status-transition gating added per FR37 |
| FR36 | Tickers screen (merged) | §11.2, §11.3 |
| FR37 | Tickers modal — status-transition sub-flows | §11.4 (watch-only→held), §11.5 (held→watch-only) |
| FR38 | Rebrand — "Sentinel Portal" | §11.6 |
| NFR8 (amended 2026-08-01) | Nav mechanism + merged Tickers screen | §11.1 (nav row-fix + horizontal-scroll variant), §11.2 (1-per-row cards, all breakpoints) |

---

## 11. Extension — FR36–FR38 Tickers merge, click-to-modal, nav redesign (2026-08-01 change request; Decision #40) — **SELECTED / APPROVED by Arjun (2026-08-01)**

> **Status: SELECTED / APPROVED.** Arjun reviewed this section and `direction-g-tickers-merge.html` and
> approved them on 2026-08-01 — this is the NFR8-style gate being cleared for INC-15. This is the final,
> canonical reference dev implements for INC-15. No further iteration on this piece precedes INC-15; any
> future visual change to the Tickers screen or nav is a change request against this approved extension,
> not a re-opening of this review.

This section documents an approved change request against the already-SELECTED Direction G
(§7.4/§7.4.3). It is an extension of Direction G, not a new direction and not a re-opening of the NFR8
direction gate — no other direction (A–F) is affected or a candidate again. Every token referenced below
is Direction F/G's existing set (§7.3.1) — **no new color, spacing, type, radius, or shadow token is
introduced by this change request.**

### 11.0 What's unchanged

Login (FR27, §2.1), the Tunables editor (FR30, §2.3/§7.3.2), the Track-record view (FR31, §2.4/§7.3.2),
and the kill-switch component (FR32, §2.5/§7.4.2) are **untouched** by this change request — their
existing Direction G spec and `direction-g-compact-toggle.html` markup remain canonical. Only the
Watchlist/Holdings screens (now merged into "Tickers") and the shared header/nav are affected.

### 11.1 Nav — rebrand, item-count, and redesign (FR38; NFR8 amended)

- **Brand:** every occurrence of "Admin Portal" (header brand label, browser `<title>`) changes to
  **"Sentinel Portal."** This is a string swap only — no layout, token, or component change follows from
  it.
- **Item count:** nav goes from four items to three — **Tickers / Tunables / Track record.** "Holdings"
  is removed as a separate nav item; its capability folds into the Tickers screen (§11.2).
- **Desktop — defect fix (not new design):** at desktop width, the nav renders as a single literal
  horizontal row, never a vertically stacked list. This corrects the shipped INC-13/14 defect
  (`nav-panel`'s `flex-direction: row` override under `@media (min-width: 1024px)` in
  `admin-portal/app/globals.css` failing to take effect in practice) — tech-lead root-causes and fixes
  the CSS; this spec's job is only to confirm the intended visual result: nav items laid out left-to-right,
  inline with (or immediately after) the brand label, no wrapping, no per-item block/stacked layout, using
  Direction G's existing nav-link typography (`--font-size-sm`, `--color-text-secondary`, active item in
  `--color-accent` on the existing tinted-pill active background) — same visual treatment already
  specified for the (buggy) implementation, just actually laid out horizontally.
- **New — horizontally-scrollable nav at a mid-width tier:** where three nav items plus the brand, the
  kill-switch control, and the user chip don't comfortably fit in one un-scrolled row but the viewport is
  still wide enough that collapsing behind the burger menu (`.nav-toggle-btn`/`.nav-panel`) would be a
  regression from "nav visible at a glance," the nav item strip becomes **horizontally scrollable**
  instead of wrapping or crowding:
  - Visual pattern: the three nav items render as a `.nav-strip` — a single-row flex/inline container with
    `overflow-x: auto`, `white-space: nowrap` (or equivalent), each item styled as a small pill/tab
    (reusing Direction G's existing pill shape — `border-radius: 999px`, `padding: 3px var(--space-3)`,
    `font-size: var(--font-size-xs)` — the same shape as the status/type pills elsewhere, applied here to
    nav items instead of introducing a new tab-strip visual language).
  - **Scroll-edge indicator:** a subtle fade/scroll-shadow overlay signals there's more content to reveal
    off-screen — implemented as a `::after` (and, once scrolled, a mirrored `::before`) pseudo-element on
    `.nav-strip`'s container: a ~24px-wide gradient from transparent to `var(--color-surface)` (the
    header's own background token, so the fade blends into the header rather than introducing a new
    color), positioned absolutely over the trailing (and, once scrolled past the start, leading) edge.
    No visible scrollbar chrome — a thin/auto-hiding scrollbar is acceptable, but the strip must remain
    genuinely draggable/swipeable, never a trap.
  - This is an **explicit, narrow carve-out** to the portal's general no-horizontal-scroll rule (NFR8,
    §1), scoped only to this nav container — nothing else on any screen scrolls horizontally.
  - Exact pixel boundaries for "mid-width tier" are tech-lead's call (per NFR8's amendment); this spec's
    illustrative mockup demonstrates the pattern at an illustrative **700–899px** band, between the
    illustrative phone/tablet/desktop breakpoints already used throughout this document (§1).
  - **Below** the horizontal-scroll tier (illustrative ≤699px in the mockup), the existing hamburger
    (`.nav-toggle-btn` / `.nav-panel.open`) fallback is unchanged — this redesign adds a middle tier, it
    does not remove the narrowest-tier fallback.

### 11.2 Tickers screen (FR36) — merges Watchlist + Holdings

- **Title:** "Tickers" (replaces "Watchlist" / "Watchlist & Holdings").
- **Toolbar:** unchanged from Direction G — search field + "+ Add ticker" primary action. Add opens the
  same modal described in §11.3, in "add" mode: Status defaults to Watch-only; Shares/Price-per-share
  fields are not shown until Status = Held (§11.4).
- **Card layout — one card per row, at phone, tablet, and desktop alike.** This supersedes the 4-col/3-col/
  2-col watchlist card-grid density specified for Direction F/G (§7.3.2's Watchlist row) and every earlier
  direction's watchlist grid (§4.2/§5.2/§6.2/§7.1.2/§7.2.2) — those remain accurate only for the
  non-selected alternate directions' own (pre-merge) watchlist screens, kept for historical record. The
  Tunables grid and the Track-record card grid are **unaffected** — still per §7.3.2/§2.3/§2.4.
- **Card content (top to bottom):**
  1. Header row: ticker (bold), market badge (`US`/`TSX`/`NSE`), type pill (Stock/ETF), status pill
     (`● Held` / `○ Watch-only`) — identical markup/tokens to the existing `.pill.held`/`.pill.watch`
     styling already shipped (`admin-portal/app/globals.css`).
  2. **If held:** shares owned + price per share on one line, e.g. `10 sh · $150.00 USD per share`. "Price
     per share" is a **UI relabel of the existing `holdings.cost_basis` field** — same value, same
     validation, only the on-screen copy changes (the standalone Holdings screen's "Cost basis" label is
     retired along with that screen). **If watch-only:** this line is omitted entirely — no placeholder
     dash, no empty row — consistent with the shared UX contract's "no placeholder, no empty cells"
     convention (§2.2, and FR21's dashboard precedent).
  3. Verdict row: latest verdict rendered with the existing `.verdict-pill.buy`/`.sell`/`.hold` styling
     (reused verbatim from the Track-record screen's convention, §2.4/§7.3.1 — same color tokens, same
     class names, no new verdict-color scheme for this screen) + the verdict's timestamp + its
     **confidence level**, shown as **plain inline text** (e.g. `Confidence: high`), matching
     `track-record/page.tsx`'s existing convention of extracting `confidence` from
     `call_log.data_snapshot->>confidence` and rendering it as bare text (not a colored badge — confidence
     is not a status the way verdict is). Timestamp format follows FR23's client-render rule (device tz
     primary + IST secondary, e.g. `10:30 AM ET (8:00 PM IST)`; a relative-time nicety, e.g. "2 hours ago,"
     may sit alongside it the way the dashboard already does, per FR21/FR23, but never replaces the actual
     timestamp). **If no check has completed yet for this ticker, this entire row is omitted** — same
     "hidden until at least one check exists, no placeholder" rule as FR21/§2.2.
  4. Rationale: the latest verdict's full rationale text, wrapped in full (not truncated with an ellipsis
     the way the denser 3-col Track-record cards may — a 1-col full-width Tickers card has room for the
     complete sentence).
  5. **No inline edit/delete icon buttons on the card** — the small-icon affordance (`✎`/`🗑` buttons in
     the card's `.card-actions` corner) is removed entirely. The card has no other interactive child; the
     whole card is the click target (§11.3).
- **Card states:**

  | State | Behavior / copy |
  |---|---|
  | Loading | Skeleton, 3–5 placeholder rows (unchanged shape from §2.2). |
  | Empty | **"No tickers yet."** / **"Add your first ticker to start tracking a stock or ETF."** + prominent **"Add ticker"** action (copy updated from "watchlist entry" to "ticker" to match the merged screen's vocabulary; no other change from §2.2's empty-state pattern). |
  | Error — fetch | **"Couldn't load your tickers."** + **"Retry."** Covers a failure of either the underlying `watchlist` or `holdings` query — one error surface for what is now one screen, never two separate error strings stacked. |
  | Success | Cards render 1-per-row; clicking any card opens the modal (§11.3). |

- **Hover/click affordance:** the whole `.ticker-card` gets `cursor: pointer` and a subtle hover elevation
  (existing `--shadow-card` token, bumped to a slightly stronger inline hover value — no new shadow token
  — e.g. `box-shadow: 0 2px 6px rgba(20,20,43,0.12)` on `:hover`) so the click affordance reads clearly now
  that the per-row icon buttons are gone.

### 11.3 Click-to-modal interaction (FR36)

Clicking/tapping anywhere on a `.ticker-card` opens a single modal — the sole edit surface for this
screen, replacing both the old watchlist-only and holdings-only edit modals.

- **Modal header:** ticker, market, type, status — read-only identifying labels, matching the card's own
  header row.
- **Combined edit form**, single scroll if needed, one Save/Cancel/Delete action set:
  - Market (select), Type (select), Status (select: Held / Watch-only) — the existing watchlist fields,
    unchanged behavior/validation from §2.2.
  - **If Status = Held:** Shares (number), Price per share (number — the relabeled `cost_basis`), and the
    existing read-only derived-Currency label (unchanged, Decision #35) appear in the form.
  - **Delete** (destructive-styled, visually separated from Save/Cancel) removes the ticker entirely —
    same confirmation copy/pattern as §2.2's existing ticker-delete flow (naming the ticker, "This can't be
    undone").
- FR28/FR29's existing validation rules (CHECK constraints, currency derivation) apply unchanged to
  whichever underlying table (`watchlist` and/or `holdings`) the edit touches — this modal is a UI
  consolidation of two forms, not a new validation surface.

### 11.4 Watch-only → Held transition (FR37)

- Triggered inside the modal (§11.3) by changing Status from Watch-only to Held.
- The instant Status = Held is selected — before Save is clicked — the Shares and Price-per-share fields
  appear inline in the form, both marked required (`*` after the label, matching the portal's existing
  required-field convention).
- **Save is blocked** until both fields are populated and pass FR29's existing validation (`shares > 0`,
  `cost_basis > 0`); attempting to Save with either field empty or invalid surfaces the existing inline
  per-field error copy from §2.2 ("Shares must be greater than 0." / a parallel "Price per share must be
  greater than 0." for the relabeled field) directly under the offending field — never a single top-of-
  form banner.
- **On successful Save:** modal closes; the card immediately reflects the held state (the shares/price
  line from §11.2 now appears); toast/inline confirmation **"Saved."** (unchanged from §2.2).

### 11.5 Held → Watch-only transition (FR37) — delete-with-confirmation

- Triggered inside the modal (§11.3) by changing Status from Held to Watch-only.
- Clicking Save with this transition pending does **not** save silently — it surfaces a confirmation step
  first (an in-modal confirm panel, replacing the form momentarily, consistent with §2.2's existing
  delete-confirmation pattern rather than a new dialog type), naming the ticker and the data about to be
  discarded, e.g.:

  > **"Switch AAPL to watch-only?**
  > This deletes the recorded 10 sh @ $150.00 USD holding — this can't be undone."

  Actions: **Cancel** (returns to the form; Status reverts to Held, no data touched) / **Confirm — remove
  holding** (destructive-styled, proceeds).
- **On confirm:** the ticker's `holdings` row is deleted, `watchlist.status` updates to `watch-only`, modal
  closes, the card reflects the watch-only state (shares/price line disappears per §11.2), toast/inline
  confirmation **"Removed holding — AAPL is now watch-only."**
- **On cancel:** modal returns to the edit form with Status reset to Held, nothing is written.
- **Designer's flag (non-blocking):** pm's stated default for this transition is delete-with-confirmation,
  and that is what this spec and the mockup build to. A "hide, don't delete" alternative (soft-archiving
  the `holdings` row — e.g. leaving it in place, unlinked, restorable if the ticker flips back to Held)
  would avoid discarding previously-entered shares/price data on what could be an accidental status flip,
  and may read as a friendlier default. This is flagged here for visibility only, per the brief's request
  — it does not gate or alter FR37 without a separate change request through pm.

### 11.6 Rebrand (FR38)

- Header brand label (`.app-header-brand` in the live implementation; the mockup's `<h1>`/login-card
  heading) and the browser `<title>`: **"Sentinel Portal"** everywhere "Admin Portal" previously appeared.
- No token, layout, or component change follows from the rebrand — string swap only.

### 11.7 Mockup

`docs/ux-mockups/direction-g-tickers-merge.html` — new, self-contained file extending Direction G's exact
token set (§7.3.1, unchanged). Demonstrates:
- The 3-item nav ("Tickers / Tunables / Track record"), "Sentinel Portal" brand, with the corrected
  horizontal-row layout at desktop width and the horizontally-scrollable pill-strip variant (with
  scroll-shadow edge fade) demonstrable at the illustrative 700–899px mid-tier via real CSS media queries
  — resize the browser to inspect all three nav tiers (hamburger / horizontal-scroll / horizontal-row).
- The merged Tickers screen, 1-per-row cards, showing watch-only status, held status with shares/price per
  share, verdict + timestamp + confidence, and rationale, using the same sample tickers as every other
  mockup (AAPL, VOO, TD, MSFT, RELIANCE).
- The click-to-modal interaction in two states: (a) a watch-only→held transition in progress (mandatory
  Shares/Price-per-share fields visible, Save blocked with a validation message shown), and (b) a normal
  held-ticker edit/delete state, with the held→watch-only delete-confirmation sub-flow (§11.5) shown as an
  inline confirm panel.

Login, Tunables, and Track-record are **not** re-rendered in this file (unchanged — see
`direction-g-compact-toggle.html`).
