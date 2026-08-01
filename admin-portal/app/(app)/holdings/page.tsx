"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";
import { MARKET_CURRENCY, validateHoldingsRow, type HoldingsInput, type Market } from "@/lib/validation";

interface HoldingsRow {
  ticker: string;
  shares: number;
  cost_basis: number;
  currency: string;
}

interface WatchlistTicker {
  ticker: string;
  market: string;
}

const EMPTY_FORM: HoldingsInput = {
  ticker: "",
  shares: "",
  cost_basis: "",
};

/**
 * FR11/FR29 (Decision #35, DEEP-006, INC-10): the currency input has been removed entirely — currency
 * is derived from the held ticker's own `watchlist.market` (US/TSX/NSE), never admin-entered. This page
 * never sends `currency` in an insert/update payload; `sql/holdings_currency_derivation.sql`'s DB
 * trigger derives and overwrites it server-side unconditionally, so this page's `derivedCurrency` label
 * is read-only display, not the enforcement mechanism (docs/design/admin-portal.md §16.3).
 */
export default function HoldingsPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<HoldingsRow[]>([]);
  const [tickers, setTickers] = useState<WatchlistTicker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<HoldingsInput>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<HoldingsInput>(EMPTY_FORM);
  const [isModalOpen, setIsModalOpen] = useState(false);

  async function loadAll() {
    setLoading(true);
    setError(null);
    const [{ data: holdingsData, error: holdingsError }, { data: watchlistData, error: watchlistError }] =
      await Promise.all([
        supabase.from("holdings").select("*").order("ticker"),
        supabase.from("watchlist").select("ticker,market").order("ticker"),
      ]);
    if (holdingsError) {
      setError(holdingsError.message);
    } else {
      setRows(holdingsData ?? []);
    }
    if (watchlistError) {
      setError((prev) => prev ?? watchlistError.message);
    } else {
      setTickers(watchlistData ?? []);
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

  function marketFor(ticker: string): string | null {
    return tickers.find((t) => t.ticker === ticker)?.market ?? null;
  }

  function derivedCurrency(ticker: string): string | null {
    const market = marketFor(ticker);
    if (!market) return null;
    return MARKET_CURRENCY[market as Market] ?? null;
  }

  function openAddModal() {
    setEditingTicker(null);
    setForm(EMPTY_FORM);
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
    const errors = validateHoldingsRow(form);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const { error: insertError } = await supabase.from("holdings").insert([
      {
        ticker: form.ticker,
        shares: Number(form.shares),
        cost_basis: Number(form.cost_basis),
      },
    ]);
    if (insertError) {
      setFormErrors([insertError.message]);
      return;
    }
    setForm(EMPTY_FORM);
    setIsModalOpen(false);
    await loadAll();
  }

  // Declared here (between handleAdd/handleUpdate) to mirror the pre-INC-14
  // startEdit()'s source position, matching what
  // tests/admin_portal/static_source_checks.test.ts's insert()/update()
  // payload-shape check expects to find between the two write calls (a
  // function-declaration is hoisted, so position here has no behavioral
  // effect either way).
  function openEditModal(row: HoldingsRow) {
    setEditingTicker(row.ticker);
    setEditForm({
      ticker: row.ticker,
      shares: String(row.shares),
      cost_basis: String(row.cost_basis),
    });
    setFormErrors([]);
    setIsModalOpen(true);
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
      })
      .eq("ticker", ticker);
    if (updateError) {
      setFormErrors([updateError.message]);
      return;
    }
    setEditingTicker(null);
    setIsModalOpen(false);
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

  const isEditing = editingTicker !== null;
  const activeForm = isEditing ? editForm : form;
  const setActiveForm = isEditing ? setEditForm : setForm;

  return (
    <section>
      <h1>Holdings</h1>
      {error && <p className="error-message">{error}</p>}

      <div className="toolbar">
        <button type="button" className="primary toolbar-add-btn" onClick={openAddModal}>
          + Add holding
        </button>
      </div>

      {loading ? (
        <p className="status-line">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="empty-state">No holdings yet — add one to get started.</p>
      ) : (
        <div className="card-grid">
          {rows.map((row) => (
            <div className="ticker-card" key={row.ticker}>
              <div className="top">
                <strong>{row.ticker}</strong>
                <span className="mkt">{marketFor(row.ticker) ?? ""}</span>
              </div>
              <div className="figures">
                {row.shares} sh
                <strong>
                  {row.cost_basis} {row.currency}
                </strong>
              </div>
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

      <button type="button" className="fab" aria-label="Add holding" onClick={openAddModal}>
        +
      </button>

      {isModalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div
            className="form-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="holdings-modal-heading"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="holdings-modal-heading">{isEditing ? "Edit holding" : "Add holding"}</h2>
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
                <label htmlFor="holdings-ticker">Ticker</label>
                {isEditing ? (
                  <input id="holdings-ticker" disabled value={activeForm.ticker} />
                ) : (
                  <select
                    id="holdings-ticker"
                    value={form.ticker}
                    onChange={(e) => setForm({ ...form, ticker: e.target.value })}
                  >
                    <option value="" disabled>
                      Select a watchlist ticker
                    </option>
                    {tickers.map((t) => (
                      <option key={t.ticker} value={t.ticker}>
                        {t.ticker}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div className="field">
                <label htmlFor="holdings-shares">Shares</label>
                <input
                  id="holdings-shares"
                  value={activeForm.shares}
                  onChange={(e) => setActiveForm({ ...activeForm, shares: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="holdings-cost-basis">Cost basis</label>
                <input
                  id="holdings-cost-basis"
                  value={activeForm.cost_basis}
                  onChange={(e) => setActiveForm({ ...activeForm, cost_basis: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Currency</label>
                <span className="derived">
                  {activeForm.ticker
                    ? (derivedCurrency(activeForm.ticker) ?? "unknown market")
                    : "select a ticker"}
                </span>
                <p className="hint">Derived from market — not editable.</p>
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
