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

function typeLabel(type: string): string {
  return type === "stock" ? "Stock" : type;
}

export default function WatchlistPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<WatchlistRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<WatchlistInput>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<WatchlistInput>(EMPTY_FORM);
  const [isModalOpen, setIsModalOpen] = useState(false);

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

  function openAddModal() {
    setEditingTicker(null);
    setForm(EMPTY_FORM);
    setFormErrors([]);
    setIsModalOpen(true);
  }

  function openEditModal(row: WatchlistRow) {
    setEditingTicker(row.ticker);
    setEditForm({
      ticker: row.ticker,
      market: row.market,
      type: row.type,
      status: row.status,
    });
    setFormErrors([]);
    setIsModalOpen(true);
  }

  function closeModal() {
    setIsModalOpen(false);
    setEditingTicker(null);
    setFormErrors([]);
  }

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
    setIsModalOpen(false);
    await loadRows();
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
    setIsModalOpen(false);
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

  const isEditing = editingTicker !== null;
  const activeForm = isEditing ? editForm : form;
  const setActiveForm = isEditing ? setEditForm : setForm;

  return (
    <section>
      <h1>Watchlist</h1>
      {error && <p className="error-message">{error}</p>}

      <div className="toolbar">
        <button type="button" className="primary toolbar-add-btn" onClick={openAddModal}>
          + Add ticker
        </button>
      </div>

      {loading ? (
        <p className="status-line">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="empty-state">No tickers yet — add one to get started.</p>
      ) : (
        <div className="card-grid">
          {rows.map((row) => (
            <div className="ticker-card" key={row.ticker}>
              <div className="top">
                <strong>{row.ticker}</strong>
                <span className="mkt">{row.market}</span>
              </div>
              <span className="pill type">{typeLabel(row.type)}</span>{" "}
              <span className={`pill ${row.status === "held" ? "held" : "watch"}`}>
                {row.status === "held" ? "● Held" : "○ Watch-only"}
              </span>
              <div className="card-actions">
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Edit ${row.ticker}`}
                  onClick={() => openEditModal(row)}
                >
                  ✎
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Delete ${row.ticker}`}
                  onClick={() => handleDelete(row.ticker)}
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        className="fab"
        aria-label="Add ticker"
        onClick={openAddModal}
      >
        +
      </button>

      {isModalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div
            className="form-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="watchlist-modal-heading"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="watchlist-modal-heading">{isEditing ? "Edit ticker" : "Add ticker"}</h2>
            <form
              onSubmit={
                isEditing
                  ? (e) => {
                      e.preventDefault();
                      if (editingTicker) handleUpdate(editingTicker);
                    }
                  : handleAdd
              }
            >
              {formErrors.map((msg) => (
                <p className="error-message" key={msg}>
                  {msg}
                </p>
              ))}
              <div className="field">
                <label htmlFor="watchlist-ticker">Ticker</label>
                <input
                  id="watchlist-ticker"
                  disabled={isEditing}
                  value={activeForm.ticker}
                  onChange={(e) => setActiveForm({ ...activeForm, ticker: e.target.value.toUpperCase() })}
                />
              </div>
              <div className="field">
                <label htmlFor="watchlist-market">Market</label>
                <select
                  id="watchlist-market"
                  value={activeForm.market}
                  onChange={(e) => setActiveForm({ ...activeForm, market: e.target.value })}
                >
                  {MARKETS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="watchlist-type">Type</label>
                <select
                  id="watchlist-type"
                  value={activeForm.type}
                  onChange={(e) => setActiveForm({ ...activeForm, type: e.target.value })}
                >
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {typeLabel(t)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="watchlist-status">Status</label>
                <select
                  id="watchlist-status"
                  value={activeForm.status}
                  onChange={(e) => setActiveForm({ ...activeForm, status: e.target.value })}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s === "held" ? "Held" : "Watch-only"}
                    </option>
                  ))}
                </select>
              </div>
              <div className="modal-actions">
                <button type="submit" className="primary">
                  Save
                </button>
                <button type="button" className="secondary" onClick={closeModal}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
