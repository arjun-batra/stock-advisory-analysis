"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";
import { CURRENCIES, validateHoldingsRow, type HoldingsInput } from "@/lib/validation";

interface HoldingsRow {
  ticker: string;
  shares: number;
  cost_basis: number;
  currency: string;
}

const EMPTY_FORM: HoldingsInput = {
  ticker: "",
  shares: "",
  cost_basis: "",
  currency: CURRENCIES[0],
};

export default function HoldingsPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<HoldingsRow[]>([]);
  const [tickers, setTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<HoldingsInput>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<HoldingsInput>(EMPTY_FORM);

  async function loadAll() {
    setLoading(true);
    setError(null);
    const [{ data: holdingsData, error: holdingsError }, { data: watchlistData, error: watchlistError }] =
      await Promise.all([
        supabase.from("holdings").select("*").order("ticker"),
        supabase.from("watchlist").select("ticker").order("ticker"),
      ]);
    if (holdingsError) {
      setError(holdingsError.message);
    } else {
      setRows(holdingsData ?? []);
    }
    if (watchlistError) {
      setError((prev) => prev ?? watchlistError.message);
    } else {
      setTickers((watchlistData ?? []).map((r: { ticker: string }) => r.ticker));
    }
    setLoading(false);
  }

  useEffect(() => {
    // Mount-time fetch — loadAll is also called imperatively after each CRUD
    // action, so it stays a named, reusable function rather than being
    // inlined here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const errors = validateHoldingsRow(form);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const { error: insertError } = await supabase.from("holdings").insert([
      {
        ticker: form.ticker,
        shares: Number(form.shares),
        cost_basis: Number(form.cost_basis),
        currency: form.currency,
      },
    ]);
    if (insertError) {
      setFormErrors([insertError.message]);
      return;
    }
    setForm(EMPTY_FORM);
    await loadAll();
  }

  function startEdit(row: HoldingsRow) {
    setEditingTicker(row.ticker);
    setEditForm({
      ticker: row.ticker,
      shares: String(row.shares),
      cost_basis: String(row.cost_basis),
      currency: row.currency,
    });
  }

  async function handleUpdate(ticker: string) {
    const errors = validateHoldingsRow(editForm);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const { error: updateError } = await supabase
      .from("holdings")
      .update({
        shares: Number(editForm.shares),
        cost_basis: Number(editForm.cost_basis),
        currency: editForm.currency,
      })
      .eq("ticker", ticker);
    if (updateError) {
      setFormErrors([updateError.message]);
      return;
    }
    setEditingTicker(null);
    await loadAll();
  }

  async function handleDelete(ticker: string) {
    const { error: deleteError } = await supabase.from("holdings").delete().eq("ticker", ticker);
    if (deleteError) {
      setError(deleteError.message);
      return;
    }
    await loadAll();
  }

  return (
    <section>
      <h1>Holdings</h1>
      {error && <p className="error-message">{error}</p>}
      {loading ? (
        <p className="status-line">Loading…</p>
      ) : (
        <table className="crud-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Shares</th>
              <th>Cost basis</th>
              <th>Currency</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) =>
              editingTicker === row.ticker ? (
                <tr key={row.ticker}>
                  <td>{row.ticker}</td>
                  <td>
                    <input
                      value={editForm.shares}
                      onChange={(e) => setEditForm({ ...editForm, shares: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={editForm.cost_basis}
                      onChange={(e) => setEditForm({ ...editForm, cost_basis: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      value={editForm.currency}
                      onChange={(e) => setEditForm({ ...editForm, currency: e.target.value })}
                    >
                      {CURRENCIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
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
                  <td>{row.shares}</td>
                  <td>{row.cost_basis}</td>
                  <td>{row.currency}</td>
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

      <h2>Add holding</h2>
      <form className="crud-form" onSubmit={handleAdd}>
        {formErrors.map((msg) => (
          <p className="error-message" key={msg}>
            {msg}
          </p>
        ))}
        <label>
          Ticker
          <select value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })}>
            <option value="" disabled>
              Select a watchlist ticker
            </option>
            {tickers.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          Shares
          <input value={form.shares} onChange={(e) => setForm({ ...form, shares: e.target.value })} />
        </label>
        <label>
          Cost basis
          <input
            value={form.cost_basis}
            onChange={(e) => setForm({ ...form, cost_basis: e.target.value })}
          />
        </label>
        <label>
          Currency
          <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
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
