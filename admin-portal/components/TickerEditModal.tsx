"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase-client";
import {
  MARKETS,
  MARKET_CURRENCY,
  STATUSES,
  TYPES,
  validateHoldingsRow,
  validateWatchlistRow,
  type Market,
} from "@/lib/validation";

export interface TickerRow {
  ticker: string;
  market: string;
  type: string;
  status: string;
  holding: { shares: number; cost_basis: number; currency: string } | null;
}

export function typeLabel(type: string): string {
  return type === "stock" ? "Stock" : type;
}

interface EditForm {
  market: string;
  type: string;
  status: string;
  shares: string;
  cost_basis: string;
}

/**
 * FR36/FR37 combined edit modal (docs/design/admin-portal.md §16.11.4,
 * built against docs/ux-mockups/direction-g-tickers-merge.html's
 * `.modal-static`/`.confirm-panel` markup). The sole edit surface for the
 * merged Tickers screen — replaces the old separate watchlist-only and
 * holdings-only edit modals.
 *
 * Write routing (§16.11.5 — the two RPCs exist ONLY for a status
 * transition or a delete):
 *  - market/type: always a direct `supabase.from("watchlist").update(...)`
 *    (existing admin_write_watchlist policy) — never routed through an RPC,
 *    even when a status transition happens in the same Save.
 *  - status unchanged, still held, shares/cost_basis edited: direct
 *    `supabase.from("holdings").update(...)` (existing admin_write_holdings
 *    policy).
 *  - watch-only -> held: `set_ticker_holding_status(p_ticker, 'held',
 *    shares, cost_basis)` — Save is blocked client-side until both fields
 *    pass the same >0 rule `validateHoldingsRow` already enforces.
 *  - held -> watch-only: Save does NOT write immediately — it reveals an
 *    in-modal confirmation panel naming the ticker and the exact
 *    shares/price about to be discarded; confirming applies any pending
 *    market/type edit first (same direct watchlist update as a plain edit,
 *    so it is never silently discarded) and then calls
 *    `set_ticker_holding_status(p_ticker, 'watch-only')`. Cancelling
 *    reverts `status` to "held" in the still-open form, nothing written.
 *  - Delete: `delete_ticker(p_ticker)`, gated behind its own confirmation.
 */
export default function TickerEditModal({
  ticker,
  onClose,
  onSaved,
}: {
  ticker: TickerRow;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const supabase = createClient();
  const [form, setForm] = useState<EditForm>({
    market: ticker.market,
    type: ticker.type,
    status: ticker.status,
    shares: ticker.holding ? String(ticker.holding.shares) : "",
    cost_basis: ticker.holding ? String(ticker.holding.cost_basis) : "",
  });
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNewlyHeld = ticker.status !== "held";
  const holdingErrors =
    form.status === "held"
      ? validateHoldingsRow({ ticker: ticker.ticker, shares: form.shares, cost_basis: form.cost_basis })
      : [];
  const sharesError = holdingErrors.some((e) => e.startsWith("Shares"))
    ? "Shares must be greater than 0."
    : null;
  const costError = holdingErrors.some((e) => e.startsWith("Cost basis"))
    ? "Price per share must be greater than 0."
    : null;
  const saveDisabled = form.status === "held" && holdingErrors.length > 0;

  function updateField<K extends keyof EditForm>(key: K, value: EditForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSaveClick(e: React.FormEvent) {
    e.preventDefault();
    if (saveDisabled || saving) return;
    if (ticker.status === "held" && form.status === "watch-only") {
      setConfirming(true);
      return;
    }
    await doSave();
  }

  // Plain field edit — market/type never go through an RPC, regardless of
  // whether status also changes in this same Save (§16.11.5). Shared by
  // doSave and confirmSwitchToWatchOnly so a pending market/type edit is
  // never silently dropped on the held->watch-only confirmation path
  // (REV-152).
  async function applyMarketTypeEdit(): Promise<string | null> {
    const watchlistErrors = validateWatchlistRow({
      ticker: ticker.ticker,
      market: form.market,
      type: form.type,
      status: form.status,
    });
    if (watchlistErrors.length > 0) {
      return watchlistErrors.join(" ");
    }
    const { error: watchlistError } = await supabase
      .from("watchlist")
      .update({ market: form.market, type: form.type })
      .eq("ticker", ticker.ticker);
    return watchlistError ? watchlistError.message : null;
  }

  async function doSave() {
    setSaving(true);
    setError(null);

    const watchlistEditError = await applyMarketTypeEdit();
    if (watchlistEditError) {
      setError(watchlistEditError);
      setSaving(false);
      return;
    }

    const statusChanged = form.status !== ticker.status;

    if (statusChanged) {
      const { error: rpcError } = await supabase.rpc("set_ticker_holding_status", {
        p_ticker: ticker.ticker,
        p_status: form.status,
        p_shares: form.status === "held" ? Number(form.shares) : null,
        p_cost_basis: form.status === "held" ? Number(form.cost_basis) : null,
      });
      if (rpcError) {
        setError(rpcError.message);
        setSaving(false);
        return;
      }
    } else if (form.status === "held") {
      const { error: holdingsError } = await supabase
        .from("holdings")
        .update({ shares: Number(form.shares), cost_basis: Number(form.cost_basis) })
        .eq("ticker", ticker.ticker);
      if (holdingsError) {
        setError(holdingsError.message);
        setSaving(false);
        return;
      }
    }

    setSaving(false);
    await onSaved();
    onClose();
  }

  async function confirmSwitchToWatchOnly() {
    setSaving(true);
    setError(null);

    const watchlistEditError = await applyMarketTypeEdit();
    if (watchlistEditError) {
      setError(watchlistEditError);
      setSaving(false);
      return;
    }

    const { error: rpcError } = await supabase.rpc("set_ticker_holding_status", {
      p_ticker: ticker.ticker,
      p_status: "watch-only",
    });
    if (rpcError) {
      setError(rpcError.message);
      setSaving(false);
      return;
    }
    setSaving(false);
    await onSaved();
    onClose();
  }

  function cancelConfirm() {
    setConfirming(false);
    updateField("status", "held");
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${ticker.ticker}? This can't be undone.`)) return;
    setSaving(true);
    setError(null);
    const { error: deleteError } = await supabase.rpc("delete_ticker", { p_ticker: ticker.ticker });
    if (deleteError) {
      setError(deleteError.message);
      setSaving(false);
      return;
    }
    setSaving(false);
    await onSaved();
    onClose();
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="form-modal modal-static"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ticker-modal-heading"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="ticker-modal-heading">{ticker.ticker}</h2>
        <div className="modal-subhead">
          {ticker.market} &middot; {typeLabel(ticker.type)}
        </div>

        {error && <p className="error-message">{error}</p>}

        {confirming ? (
          <div className="confirm-panel">
            <strong>Switch {ticker.ticker} to watch-only?</strong>
            This deletes the recorded {ticker.holding?.shares} sh @ {ticker.holding?.cost_basis}{" "}
            {ticker.holding?.currency} holding &mdash; this can&apos;t be undone.
            <div className="confirm-actions">
              <button type="button" className="secondary" onClick={cancelConfirm} disabled={saving}>
                Cancel
              </button>
              <button
                type="button"
                className="primary danger"
                onClick={confirmSwitchToWatchOnly}
                disabled={saving}
              >
                Confirm &mdash; remove holding
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSaveClick}>
            <div className="field">
              <label htmlFor="ticker-market">Market</label>
              <select
                id="ticker-market"
                value={form.market}
                onChange={(e) => updateField("market", e.target.value)}
              >
                {MARKETS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="ticker-type">Type</label>
              <select id="ticker-type" value={form.type} onChange={(e) => updateField("type", e.target.value)}>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {typeLabel(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="ticker-status">Status</label>
              <select
                id="ticker-status"
                value={form.status}
                onChange={(e) => updateField("status", e.target.value)}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s === "held" ? "Held" : "Watch-only"}
                  </option>
                ))}
              </select>
            </div>

            {form.status === "held" && (
              <div className="new-fields">
                {isNewlyHeld && (
                  <p className="new-fields-note">
                    Switching to Held &mdash; both fields below are required before Save
                  </p>
                )}
                <div className="field">
                  <label htmlFor="ticker-shares">
                    Shares {isNewlyHeld && <span className="req">*</span>}
                  </label>
                  <input
                    id="ticker-shares"
                    value={form.shares}
                    placeholder="e.g. 10"
                    onChange={(e) => updateField("shares", e.target.value)}
                  />
                  {sharesError && <div className="error">{sharesError}</div>}
                </div>
                <div className="field">
                  <label htmlFor="ticker-cost-basis">
                    Price per share {isNewlyHeld && <span className="req">*</span>}
                  </label>
                  <input
                    id="ticker-cost-basis"
                    value={form.cost_basis}
                    placeholder="e.g. 410.00"
                    onChange={(e) => updateField("cost_basis", e.target.value)}
                  />
                  {costError && <div className="error">{costError}</div>}
                </div>
                <div className="field">
                  <label>Currency</label>
                  <span className="derived">
                    {(MARKET_CURRENCY[form.market as Market] ?? "unknown")} (from {form.market})
                  </span>
                </div>
              </div>
            )}

            <div className="modal-actions">
              <button type="button" className="secondary danger" onClick={handleDelete} disabled={saving}>
                Delete
              </button>
              <div className="right">
                <button type="button" className="secondary" onClick={onClose} disabled={saving}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary"
                  disabled={saveDisabled || saving}
                  title={saveDisabled ? "Blocked until Shares and Price per share are valid" : undefined}
                >
                  Save
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
