"use client";

import { useState } from "react";

/**
 * Presentational-only collapsible nav control for phone/tablet widths
 * (docs/design/admin-portal.md §16.10, INC-13/NFR8). Below the desktop
 * breakpoint the wrapped nav content is hidden until this button is
 * clicked; at desktop widths CSS forces the panel open regardless of this
 * component's local `open` state (see `.nav-panel` rules in
 * `app/globals.css`). No data/props beyond the nav markup passed as
 * children — purely local open/closed UI state, no Supabase call, no
 * business logic.
 */
export default function NavToggle({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="nav-toggle-wrap">
      <button
        type="button"
        className="nav-toggle-btn"
        aria-expanded={open}
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span aria-hidden="true">&#9776;</span>
      </button>
      <div className={`nav-panel${open ? " open" : ""}`}>{children}</div>
    </div>
  );
}
