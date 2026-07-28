"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase-client";

/**
 * Google OAuth sign-in — the only sign-in path in this portal (FR27). No
 * email/password or magic-link UI is rendered anywhere in this file or
 * elsewhere in the app (docs/design/admin-portal.md §16.1).
 */
export default function LoginPage() {
  return (
    <main className="status-line">
      <h1>Stock Advisory — Admin Portal</h1>
      <Suspense fallback={null}>
        <NotAuthorizedNotice />
      </Suspense>
      <SignInButton />
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
    <button type="button" className="primary" onClick={signIn}>
      Sign in with Google
    </button>
  );
}
