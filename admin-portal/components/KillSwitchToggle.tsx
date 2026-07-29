"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";

/**
 * FR32 kill-switch toggle. Reads `public.kill_switch_state.paused` on mount (readable only because
 * `sql/kill_switch_portal_grant.sql`'s `admin_read_kill_switch` policy grants `authenticated`+
 * `is_admin()` SELECT — INC-7) and flips it via `set_kill_switch(p_paused, p_source)` (INC-3,
 * admin-gated by the same migration). Rendered inside AuthGuard's shared header so it's visible on
 * every authenticated route (docs/design/admin-portal.md §16.6/§16.8: "surfaced on a shared
 * authenticated layout/header, not a standalone page"). `p_source: "admin-portal"` is a literal
 * identifying *this UI* (matching the design's exact contract text), not a tunable.
 */
export default function KillSwitchToggle() {
  const supabase = createClient();
  const [paused, setPaused] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadState() {
    setLoading(true);
    setError(null);
    const { data, error: fetchError } = await supabase
      .from("kill_switch_state")
      .select("paused")
      .eq("id", true)
      .single();
    if (fetchError) {
      setError(fetchError.message);
    } else {
      setPaused(data?.paused ?? null);
    }
    setLoading(false);
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleToggle() {
    if (paused === null) return;
    setToggling(true);
    setError(null);
    const { error: rpcError } = await supabase.rpc("set_kill_switch", {
      p_paused: !paused,
      p_source: "admin-portal",
    });
    if (rpcError) {
      setError(rpcError.message);
      setToggling(false);
      return;
    }
    await loadState(); // re-read from the table rather than optimistically flipping locally
    setToggling(false);
  }

  if (loading) {
    return <span className="status-line kill-switch">Kill-switch: loading…</span>;
  }
  if (error) {
    return <span className="error-message kill-switch">Kill-switch: {error}</span>;
  }

  return (
    <span className="kill-switch">
      <span className={`kill-switch-badge ${paused ? "paused" : "running"}`}>
        {paused ? "PAUSED" : "RUNNING"}
      </span>{" "}
      <button type="button" className="link" onClick={handleToggle} disabled={toggling}>
        {toggling ? "…" : paused ? "Resume" : "Pause"}
      </button>
    </span>
  );
}
