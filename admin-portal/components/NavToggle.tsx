"use client";

import { useState } from "react";

/**
 * Presentational-only nav shell for the Tickers/Tunables/Track record links
 * (docs/design/admin-portal.md §16.11.1/§16.11.2, INC-15).
 *
 * Root-cause fix (§16.11.1, "Option A"): the shipped INC-13/14 defect was an
 * extra `<nav>` wrapper between `.nav-panel`'s flex container and the actual
 * `<a>` links, so `flex-direction` had nothing to arrange (a flex container
 * with exactly one child has no row/column to choose between) — the visible
 * vertical stacking came from an unrelated `.nav-panel a { display:block;
 * width:100% }` descendant rule that reached through the wrapper regardless
 * of viewport. `children` here is passed as bare `<a>` elements (no wrapping
 * `<nav>`) and rendered twice, each time as the *direct* children of a real
 * flex container:
 *   - `.nav-strip` (>=640px): a single horizontal row, `overflow-x:auto` so
 *     it scrolls instead of wrapping/clipping if content ever doesn't fit
 *     (NFR8's amended carve-out, §16.11.2).
 *   - `.nav-panel-mobile` (<640px): the unchanged hamburger dropdown.
 * Both are always present in the DOM; CSS `display` alone decides which is
 * visible at a given width (same "both exist, CSS switches" pattern as the
 * approved mockup, `docs/ux-mockups/direction-g-tickers-merge.html`).
 *
 * No data/props beyond the nav markup passed as children — purely local
 * open/closed UI state, no Supabase call, no business logic.
 */
export default function NavToggle({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="nav-strip-wrap">
        <nav className="nav-strip">{children}</nav>
      </div>

      <button
        type="button"
        className="nav-toggle-btn"
        aria-expanded={open}
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span aria-hidden="true">&#9776;</span>
      </button>
      <nav className={`nav-panel-mobile${open ? " open" : ""}`}>{children}</nav>
    </>
  );
}
