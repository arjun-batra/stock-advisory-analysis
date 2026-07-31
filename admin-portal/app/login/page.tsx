"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase-client";

/**
 * Google OAuth sign-in — the only sign-in path in this portal (FR27). No
 * email/password or magic-link UI is rendered anywhere in this file or
 * elsewhere in the app (docs/design/admin-portal.md §16.1).
 *
 * INC-13 (NFR8, Direction G): centered card layout matching
 * docs/ux-mockups/direction-g-compact-toggle.html's login screen — markup/
 * CSS only, `signIn()`'s OAuth call below is unchanged.
 */
export default function LoginPage() {
  return (
    <main className="login-wrap">
      <div className="login-card">
        <div className="logo-circle">SA</div>
        <h1>Stock Advisory — Admin</h1>
        <p className="sub">Sign in with your authorized Google account to continue.</p>
        <Suspense fallback={null}>
          <NotAuthorizedNotice />
        </Suspense>
        <SignInButton />
      </div>
    </main>
  );
}

function NotAuthorizedNotice() {
  const params = useSearchParams();
  const error = params.get("error");
  if (error === "not_authorized") {
    return (
      <p className="error-message" role="alert">
        Not authorized. This Google account is not on the admin allowlist.
      </p>
    );
  }
  if (error === "auth_failed") {
    return (
      <p className="error-message" role="alert">
        Sign-in failed. Please try again.
      </p>
    );
  }
  return null;
}

function SignInButton() {
  async function signIn() {
    const supabase = createClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  return (
    <button type="button" className="google-btn" onClick={signIn}>
      Sign in with Google
    </button>
  );
}
