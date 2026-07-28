"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase-client";
import { checkAuthorization } from "@/lib/admin-guard";

/**
 * Wraps every authenticated page (watchlist, holdings). Redirects to /login
 * if there's no session, or if the signed-in account isn't in
 * admin_allowlist (docs/design/admin-portal.md §16.2). This is a UX gate
 * only — RLS is the real enforcement, so a failure here never blocks a
 * malicious client from being rejected server-side too.
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
    <div>
      <header className="app-header">
        <nav>
          <a href="/watchlist">Watchlist</a>
          <a href="/holdings">Holdings</a>
        </nav>
        <div className="app-header-user">
          <span>{email}</span>
          <SignOutButton />
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

function SignOutButton() {
  const router = useRouter();
  return (
    <button
      type="button"
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
