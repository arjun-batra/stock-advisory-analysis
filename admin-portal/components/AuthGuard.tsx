"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase-client";
import { checkAuthorization } from "@/lib/admin-guard";
import KillSwitchToggle from "@/components/KillSwitchToggle";
import NavToggle from "@/components/NavToggle";

/**
 * Wraps every authenticated page (watchlist, holdings, tunables, track
 * record). Redirects to /login if there's no session, or if the signed-in
 * account isn't in admin_allowlist (docs/design/admin-portal.md §16.2). This
 * is a UX gate only — RLS is the real enforcement, so a failure here never
 * blocks a malicious client from being rejected server-side too.
 *
 * Also renders the FR32 kill-switch toggle (docs/design/admin-portal.md
 * §16.6) in the header — this is the one shared chrome every authenticated
 * route passes through (`app/(app)/layout.tsx` is a thin
 * `<AuthGuard>{children}</AuthGuard>` pass-through), so the toggle is visible
 * everywhere without a standalone page, per the design's own text.
 *
 * INC-13 (NFR8, Direction G, docs/design/admin-portal.md §16.10): below the
 * desktop breakpoint, the route nav + sign-out collapse behind `NavToggle`'s
 * hamburger control (AC3) — CSS-only, `NavToggle` holds only presentational
 * open/closed state. The kill-switch toggle stays directly visible at every
 * width rather than being hidden behind that control, so it's reachable with
 * zero extra clicks at any width.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<"checking" | "ok">("checking");
  const [email, setEmail] = useState("");

  useEffect(() => {
    let cancelled = false;
    const supabase = createClient();

    checkAuthorization(supabase).then((result) => {
      if (cancelled) return;
      if (result.status === "unauthenticated") {
        router.replace("/login");
        return;
      }
      if (result.status === "unauthorized") {
        router.replace("/login?error=not_authorized");
        return;
      }
      setEmail(result.email);
      setState("ok");
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") {
        router.replace("/login");
      }
    });

    return () => {
      cancelled = true;
      subscription.subscription.unsubscribe();
    };
  }, [router]);

  if (state === "checking") {
    return <p className="status-line">Checking session…</p>;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-header-brand">Admin Portal</span>
        <NavToggle>
          <nav>
            <a href="/watchlist">Watchlist</a>
            <a href="/holdings">Holdings</a>
            <a href="/tunables">Tunables</a>
            <a href="/track-record">Track record</a>
            <SignOutButton />
          </nav>
        </NavToggle>
        <div className="app-header-user">
          <KillSwitchToggle />
          <span className="user-chip" title={email}>
            {initials(email)}
          </span>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

// Purely cosmetic (avatar-chip initials) — never used for authorization, which is is_admin()/RLS.
function initials(email: string): string {
  const name = email.split("@")[0] ?? "";
  const parts = name.split(/[._-]/).filter(Boolean);
  const chars = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "");
  return chars.toUpperCase() || "?";
}

function SignOutButton() {
  const router = useRouter();
  return (
    <button
      type="button"
      className="link"
      onClick={async () => {
        const supabase = createClient();
        await supabase.auth.signOut();
        router.replace("/login");
      }}
    >
      Sign out
    </button>
  );
}
