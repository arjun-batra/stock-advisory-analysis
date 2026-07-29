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
 * FR30 tunables editor. No static metadata array here — description/example
 * are DB columns, seeded once by sql/admin_portal_tunables.sql — this screen
 * is a straight read/render/write against public.tunables (docs/design/
 * admin-portal-tunables.md §16.4), same browser-side Supabase client + RLS
 * pattern as watchlist/holdings. No add/delete: the RLS policy only grants
 * `select, update` (REV-044) — the ten rows are migration-seeded and fixed by
 * the table's own CHECK constraint, so there is nothing to add or remove here.
 * `updated_at`/`updated_by` are server-stamped by the `tunables_stamp_update`
 * trigger — never client-supplied — this page only ever sends `value`.
 */
export default function TunablesPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<TunableRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [formErrors, setFormErrors] = useState<string[]>([]);

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
      setRows(data ?? []);
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

  function startEdit(row: TunableRow) {
    setEditingKey(row.key);
    setEditValue(row.value);
    setFormErrors([]);
  }

  async function handleUpdate(key: string) {
    const errors = validateTunableValue(editValue);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const { error: updateError } = await supabase
      .from("tunables")
      .update({ value: editValue.trim() })
      .eq("key", key);
    if (updateError) {
      setFormErrors([updateError.message]);
      return;
    }
    setEditingKey(null);
    await loadRows();
  }

  return (
    <section>
      <h1>Tunables</h1>
      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="status-line">Loading…</p>
      ) : (
        <table className="crud-table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Description</th>
              <th>Example</th>
              <th>Value</th>
              <th>Last updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) =>
              editingKey === row.key ? (
                <tr key={row.key}>
                  <td>{row.key}</td>
                  <td>{row.description}</td>
                  <td>{row.example}</td>
                  <td>
                    {formErrors.map((msg) => (
                      <p className="error-message" key={msg}>
                        {msg}
                      </p>
                    ))}
                    <input value={editValue} onChange={(e) => setEditValue(e.target.value)} />
                  </td>
                  <td>
                    {row.updated_at} {row.updated_by ? `(${row.updated_by})` : ""}
                  </td>
                  <td>
                    <button type="button" className="link" onClick={() => handleUpdate(row.key)}>
                      Save
                    </button>{" "}
                    <button type="button" className="link" onClick={() => setEditingKey(null)}>
                      Cancel
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={row.key}>
                  <td>{row.key}</td>
                  <td>{row.description}</td>
                  <td>{row.example}</td>
                  <td>{row.value}</td>
                  <td>
                    {row.updated_at} {row.updated_by ? `(${row.updated_by})` : ""}
                  </td>
                  <td>
                    <button type="button" className="link" onClick={() => startEdit(row)}>
                      Edit
                    </button>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      )}
    </section>
  );
}
