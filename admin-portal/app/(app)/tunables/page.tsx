"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";
import { validateTunableValue } from "@/lib/validation";

interface TunableRow {
  key: string;
  value: string;
  description: string;
  example: string;
  updated_at: string;
  updated_by: string | null;
}

/**
 * Friendly-label mapping (docs/ux-spec.md §2.3 — authoritative source for this table). Presentation
 * only: the raw key is still shown (demoted to a small monospace subtitle) and is what's actually
 * read/written against `public.tunables` — this map never touches validation, storage, or which key
 * maps to which input type.
 */
const FRIENDLY_LABELS: Record<string, string> = {
  GEMINI_MODEL: "Primary AI model",
  GEMINI_MODEL_BACKUP: "Backup AI model",
  ALERTS_ENABLED: "Alerts on/off switch",
  DISCOVERY_GAINER_PCT: "Gainer threshold (%)",
  DISCOVERY_LOSER_PCT: "Loser threshold (%)",
  DISCOVERY_VOL_SPIKE: "Volume spike multiple",
  DISCOVERY_MIN_MARKET_CAP: "Min. market cap — US/CA",
  DISCOVERY_MIN_MARKET_CAP_INR: "Min. market cap — NSE",
  DISCOVERY_SHORTLIST_MAX: "Max daily candidates",
  DISCOVERY_PUSH_COOLDOWN_DAYS: "Re-alert cooldown (days)",
};

/**
 * FR30 tunables editor. No static metadata array here — description/example
 * are DB columns, seeded once by sql/admin_portal_tunables.sql — this screen
 * is a straight read/render/write against public.tunables (docs/design/
 * admin-portal-tunables.md §16.4), same browser-side Supabase client + RLS
 * pattern as watchlist/holdings. No add/delete: the RLS policy only grants
 * `select, update` (REV-044) — the ten rows are migration-seeded and fixed by
 * the table's own CHECK constraint, so there is nothing to add or remove here.
 * `updated_at`/`updated_by` are server-stamped by the `tunables_stamp_update`
 * trigger — never client-supplied — this page only ever sends `value`.
 *
 * DEEP-005/INC-10: `validateTunableValue` is now key-aware, mirroring scripts/config.py's per-key
 * cast/domain contract (docs/design/admin-portal-tunables.md §16.4) — a bad value is rejected here
 * before any write attempt, and `sql/tunables_validate_trigger.sql` enforces the identical contract
 * server-side. `ALERTS_ENABLED` renders as a true/false select instead of free text, structurally
 * preventing the typo class that used to silently disable all real pushes.
 *
 * INC-13 (NFR8, Direction G, docs/design/admin-portal.md §16.10): all 10 keys render as always-
 * visible compact cards (no accordion/expand-collapse) — every card's value input and Save button are
 * visible without a tap, so editing state is now per-key (`drafts`/`rowErrors`) rather than a single
 * global editingKey/editValue pair. `handleUpdate`'s validate-then-write body is unchanged.
 */
export default function TunablesPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<TunableRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string[]>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);

  async function loadRows() {
    setLoading(true);
    setError(null);
    const { data, error: fetchError } = await supabase
      .from("tunables")
      .select("*")
      .order("key");
    if (fetchError) {
      setError(fetchError.message);
    } else {
      const nextRows = data ?? [];
      setRows(nextRows);
      setDrafts((prev) => {
        const next = { ...prev };
        for (const row of nextRows) {
          if (!(row.key in next)) next[row.key] = row.value;
        }
        return next;
      });
    }
    setLoading(false);
  }

  useEffect(() => {
    // Mount-time fetch — loadRows is also called imperatively after each
    // save, so it stays a named, reusable function rather than being inlined
    // here (same pattern as watchlist/holdings).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUpdate(key: string) {
    const editValue = drafts[key] ?? "";
    const errors = validateTunableValue(key, editValue);
    setRowErrors((prev) => ({ ...prev, [key]: errors }));
    if (errors.length > 0) return;

    setSavingKey(key);
    const { error: updateError } = await supabase
      .from("tunables")
      .update({ value: editValue.trim() })
      .eq("key", key);
    if (updateError) {
      setRowErrors((prev) => ({ ...prev, [key]: [updateError.message] }));
      setSavingKey(null);
      return;
    }
    setDrafts((prev) => ({ ...prev, [key]: editValue.trim() }));
    setSavingKey(null);
    await loadRows();
  }

  return (
    <section>
      <h1>Tunables</h1>
      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="status-line">Loading…</p>
      ) : (
        <div className="tunable-grid">
          {rows.map((row) => (
            <div className="tun-card" key={row.key}>
              <div className="friendly">{FRIENDLY_LABELS[row.key] ?? row.key}</div>
              <div className="key">{row.key}</div>
              <div className="desc">{row.description}</div>
              <div className="example">{row.example}</div>
              {(rowErrors[row.key] ?? []).map((msg) => (
                <p className="error-message" key={msg}>
                  {msg}
                </p>
              ))}
              <div className="row">
                {row.key === "ALERTS_ENABLED" ? (
                  // DEEP-005: a select, not free text — structurally prevents the typo class
                  // (e.g. "tru") that used to silently disable all real pushes with no error.
                  <select
                    value={drafts[row.key] ?? row.value}
                    onChange={(e) => setDrafts({ ...drafts, [row.key]: e.target.value })}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                ) : (
                  <input
                    value={drafts[row.key] ?? row.value}
                    onChange={(e) => setDrafts({ ...drafts, [row.key]: e.target.value })}
                  />
                )}
                <button
                  type="button"
                  className="primary"
                  onClick={() => handleUpdate(row.key)}
                  disabled={savingKey === row.key}
                >
                  {savingKey === row.key ? "Saving…" : "Save"}
                </button>
              </div>
              <div className="updated">
                {row.updated_at} {row.updated_by ? `(${row.updated_by})` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
