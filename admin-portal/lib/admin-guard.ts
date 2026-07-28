import type { SupabaseClient } from "@supabase/supabase-js";

export type AuthorizationState =
  | { status: "unauthenticated" }
  | { status: "unauthorized"; email: string }
  | { status: "authorized"; email: string };

/**
 * The portal-UI allowlist check (docs/design/admin-portal.md §16.2, "Defense
 * in depth" layer 2 — a UX improvement, NOT the security boundary; RLS +
 * is_admin() at the database layer is). Signs the user out immediately if
 * their signed-in Google account isn't in admin_allowlist.
 */
export async function checkAuthorization(
  supabase: SupabaseClient
): Promise<AuthorizationState> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return { status: "unauthenticated" };
  }

  const email = session.user.email ?? "";
  const { data: isAdmin, error } = await supabase.rpc("is_admin");
  if (error || !isAdmin) {
    await supabase.auth.signOut();
    return { status: "unauthorized", email };
  }

  return { status: "authorized", email };
}
