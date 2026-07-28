"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase-client";
import { checkAuthorization } from "@/lib/admin-guard";

/**
 * Root route: purely a redirect target. Logged-out (or non-admin) visits
 * land on /login; an authorized admin lands on /watchlist.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();
    checkAuthorization(supabase).then((result) => {
      if (result.status === "authorized") {
        router.replace("/watchlist");
      } else if (result.status === "unauthorized") {
        router.replace("/login?error=not_authorized");
      } else {
        router.replace("/login");
      }
    });
  }, [router]);

  return <p className="status-line">Loading…</p>;
}
