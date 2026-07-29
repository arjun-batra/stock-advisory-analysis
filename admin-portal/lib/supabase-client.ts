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
 *
 * Next.js/webpack only inlines NEXT_PUBLIC_* vars into the client bundle
 * when they're referenced as a literal, static `process.env.EXACT_NAME`
 * expression — `process.env[name]` with a computed/variable name is NOT
 * statically analyzable and is never replaced, so it's always `undefined`
 * in the browser regardless of what's set in the deploy environment. Each
 * call site below must read its var via a literal `process.env.X`
 * expression; `requiredEnv` only validates the already-resolved value.
 */
function requiredEnv(name: string, value: string | undefined): string {
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
    requiredEnv("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
    requiredEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)
  );
}
