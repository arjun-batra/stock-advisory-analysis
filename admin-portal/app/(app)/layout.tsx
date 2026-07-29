import AuthGuard from "@/components/AuthGuard";

/**
 * Shared authenticated layout for every gated route (watchlist, holdings,
 * tunables, track record). The kill-switch toggle (docs/design/admin-portal.md
 * §16.6/§16.8, INC-7) is rendered inside AuthGuard's own header rather than
 * here — AuthGuard is the component that actually owns the shared header
 * markup every route below this layout renders through; this file stays a
 * thin pass-through. Route-group folder (parens) so it doesn't affect the URL
 * path.
 */
export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthGuard>{children}</AuthGuard>;
}
