import AuthGuard from "@/components/AuthGuard";

/**
 * Shared authenticated layout for every gated route (watchlist, holdings —
 * and, per docs/design/admin-portal.md §16.8, the future kill-switch toggle
 * in INC-7). Route-group folder (parens) so it doesn't affect the URL path.
 */
export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthGuard>{children}</AuthGuard>;
}
