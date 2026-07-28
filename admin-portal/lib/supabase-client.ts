import { createBrowserClient } from "@supabase/ssr";

/**
 * The browser Supabase client — used by every feature in this portal
 * (login/allowlist check, watchlist CRUD, holdings CRUD). Carries the
 * signed-in user's session; anon/publishable key only, RLS is the
 * authorization boundary for every write (docs/design/admin-portal.md
 * §16.1/§16.7). No server-side data path exists in this portal.
 *
 * Both env vars are intentionally public (NEXT_PUBLIC_*, inlined into the
 * client bundle by Next.js at build time) — same posture as the existing
 * read-only dashboard (pages/common.js).
 */
function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. Set it in the Vercel ` +
        `project settings (or admin-portal/.env.local for local dev) — see ` +
        `docs/handoff.md for the exact values.`
    );
  }
  return value;
}

export function createClient() {
  return createBrowserClient(
    requiredEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requiredEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
  );
}
