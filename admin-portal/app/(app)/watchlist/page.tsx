"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";
import {
  MARKETS,
  STATUSES,
  TYPES,
  validateWatchlistRow,
  type WatchlistInput,
} from "@/lib/validation";

interface WatchlistRow {
  ticker: string;
  market: string;
  type: string;
  status: string;
  date_added: string;
}

const EMPTY_FORM: WatchlistInput = {
  ticker: "",
  market: MARKETS[0],
  type: TYPES[0],
  status: STATUSES[0],
};

export default function WatchlistPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<WatchlistRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<WatchlistInput>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<WatchlistInput>(EMPTY_FORM);

  async function loadRows() {
    setLoading(true);
    setError(null);
    const { data, error: fetchError } = await supabase
      .from("watchlist")
      .select("*")
      .order("ticker");
    if (fetchError) {
      setError(fetchError.message);
    } else {
      setRows(data ?? []);
    }
    setLoading(false);
  }

  useEffect(() => {
    // Mount-time fetch — loadRows is also called imperatively after each
    // CRUD action, so it stays a named, reusable function rather than being
    // inlined here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const errors = validateWatchlistRow(form);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const { error: insertError } = await supabase.from("watchlist").insert([
      {
        ticker: form.ticker.trim(),
        market: form.market,
        type: form.type,
        status: form.status,
      },
    ]);
    if (insertError) {
      setFormErrors([insertError.message]);
      return;
    }
    setForm(EMPTY_FORM);
    await loadRows();
  }

  function startEdit(row: WatchlistRow) {
    setEditingTicker(row.ticker);
    setEditForm({
      ticker: row.ticker,
      market: row.market,
      type: row.type,
      status: row.status,
    });
  }

  async function handleUpdate(ticker: string) {
    const errors = validateWatchlistRow(editForm);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const { error: updateError } = await supabase
      .from("watchlist")
      .update({ market: editForm.market, type: editForm.type, status: editForm.status })
      .eq("ticker", ticker);
    if (updateError) {
      setFormErrors([updateError.message]);
      return;
    }
    setEditingTicker(null);
    await loadRows();
  }

  async function handleDelete(ticker: string) {
    const { error: deleteError } = await supabase
      .from("watchlist")
      .delete()
      .eq("ticker", ticker);
    if (deleteError) {
      setError(deleteError.message);
      return;
    }
    await loadRows();
  }

  return (
    <section>
      <h1>Watchlist</h1>
      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="status-line">Loading…</p>
      ) : (
        <table className="crud-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Market</th>
              <th>Type</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) =>
              editingTicker === row.ticker ? (
                <tr key={row.ticker}>
                  <td>{row.ticker}</td>
                  <td>
                    <select
                      value={editForm.market}
                      onChange={(e) => setEditForm({ ...editForm, market: e.target.value })}
                    >
                      {MARKETS.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={editForm.type}
                      onChange={(e) => setEditForm({ ...editForm, type: e.target.value })}
                    >
                      {TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={editForm.status}
                      onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button type="button" className="link" onClick={() => handleUpdate(row.ticker)}>
                      Save
                    </button>{" "}
                    <button type="button" className="link" onClick={() => setEditingTicker(null)}>
                      Cancel
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={row.ticker}>
                  <td>{row.ticker}</td>
                  <td>{row.market}</td>
                  <td>{row.type}</td>
                  <td>{row.status}</td>
                  <td>
                    <button type="button" className="link" onClick={() => startEdit(row)}>
                      Edit
                    </button>{" "}
                    <button type="button" className="link" onClick={() => handleDelete(row.ticker)}>
                      Delete
                    </button>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      )}

      <h2>Add ticker</h2>
      <form className="crud-form" onSubmit={handleAdd}>
        {formErrors.map((msg) => (
          <p className="error-message" key={msg}>
            {msg}
          </p>
        ))}
        <label>
          Ticker
          <input
            value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
          />
        </label>
        <label>
          Market
          <select value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })}>
            {MARKETS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          Type
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="primary">
          Add
        </button>
      </form>
    </section>
  );
}
