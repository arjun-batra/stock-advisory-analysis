"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";
import { MARKETS, TYPES, validateWatchlistRow } from "@/lib/validation";
import TickerEditModal, { typeLabel, type TickerRow } from "@/components/TickerEditModal";

interface WatchlistRow {
  ticker: string;
  market: string;
  type: string;
  status: string;
}

interface HoldingsRow {
  ticker: string;
  shares: number;
  cost_basis: number;
  currency: string;
}

interface LatestCallRow {
  ticker: string;
  verdict: string;
  rationale: string;
  timestamp: string;
  confidence: string | null;
}

const EMPTY_ADD_FORM = { ticker: "", market: MARKETS[0] as string, type: TYPES[0] as string };

function verdictClass(verdict: string): string {
  const v = verdict.toLowerCase();
  return v === "buy" || v === "sell" || v === "hold" ? v : "";
}

/**
 * FR36 merged Tickers screen (docs/design/admin-portal.md §16.11.3, built
 * against docs/ux-mockups/direction-g-tickers-merge.html). Replaces the old
 * separate watchlist/page.tsx and holdings/page.tsx. No schema change — reads
 * `watchlist` + `holdings` + `latest_call_per_ticker` and joins them
 * client-side by ticker, same RLS-authorized read pattern every existing
 * portal page already uses (no new policy needed for any of the three
 * reads).
 */
export default function TickersPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<TickerRow[]>([]);
  const [latestCalls, setLatestCalls] = useState<Record<string, LatestCallRow>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const [editingTicker, setEditingTicker] = useState<TickerRow | null>(null);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [addForm, setAddForm] = useState(EMPTY_ADD_FORM);
  const [addErrors, setAddErrors] = useState<string[]>([]);

  async function loadAll() {
    setLoading(true);
    setError(null);

    const [watchlistRes, holdingsRes, callsRes] = await Promise.all([
      supabase.from("watchlist").select("*").order("ticker"),
      supabase.from("holdings").select("*"),
      supabase.from("latest_call_per_ticker").select("ticker,verdict,rationale,timestamp,confidence"),
    ]);

    // One error surface for either underlying query failing — never two
    // separate error strings stacked (docs/ux-spec.md §11.2's card-states
    // table).
    if (watchlistRes.error || holdingsRes.error || callsRes.error) {
      setError("Couldn't load your tickers.");
      setRows([]);
      setLatestCalls({});
      setLoading(false);
      return;
    }

    const holdingsByTicker = new Map<string, HoldingsRow>(
      ((holdingsRes.data as HoldingsRow[]) ?? []).map((h) => [h.ticker, h])
    );
    const callsByTicker = new Map<string, LatestCallRow>(
      ((callsRes.data as unknown as LatestCallRow[]) ?? []).map((c) => [c.ticker, c])
    );

    const merged: TickerRow[] = ((watchlistRes.data as WatchlistRow[]) ?? []).map((w) => {
      const holding = holdingsByTicker.get(w.ticker);
      return {
        ticker: w.ticker,
        market: w.market,
        type: w.type,
        status: w.status,
        holding: holding
          ? { shares: holding.shares, cost_basis: holding.cost_basis, currency: holding.currency }
          : null,
      };
    });

    setRows(merged);
    setLatestCalls(Object.fromEntries(callsByTicker));
    setLoading(false);
  }

  useEffect(() => {
    // Mount-time fetch — loadAll is also called imperatively after each CRUD
    // action, so it stays a named, reusable function rather than being
    // inlined here (same convention as every other portal page).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openAddModal() {
    setAddForm(EMPTY_ADD_FORM);
    setAddErrors([]);
    setIsAddOpen(true);
  }

  function closeAddModal() {
    setIsAddOpen(false);
    setAddErrors([]);
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    // "+ Add ticker" reuses the existing watch-only-only creation flow
    // (§16.11.4/AC12) — the new RPCs have no insert path, so a ticker must
    // exist watch-only before it can be promoted to held via the FR37 modal
    // transition. Status is not offered as a field here; it's hardcoded.
    const errors = validateWatchlistRow({
      ticker: addForm.ticker,
      market: addForm.market,
      type: addForm.type,
      status: "watch-only",
    });
    setAddErrors(errors);
    if (errors.length > 0) return;

    const { error: insertError } = await supabase.from("watchlist").insert([
      {
        ticker: addForm.ticker.trim().toUpperCase(),
        market: addForm.market,
        type: addForm.type,
        status: "watch-only",
      },
    ]);
    if (insertError) {
      setAddErrors([insertError.message]);
      return;
    }
    closeAddModal();
    await loadAll();
  }

  const filteredRows = rows.filter((r) => r.ticker.toUpperCase().includes(search.trim().toUpperCase()));

  return (
    <section>
      <h1>Tickers</h1>
      {error && (
        <p className="error-message">
          {error} <button type="button" className="link" onClick={loadAll}>Retry</button>
        </p>
      )}

      <div className="toolbar">
        <input
          className="search"
          placeholder="Search tickers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search tickers"
        />
        <button type="button" className="primary" onClick={openAddModal}>
          + Add ticker
        </button>
      </div>

      {loading ? (
        <p className="status-line">Loading…</p>
      ) : filteredRows.length === 0 && rows.length === 0 ? (
        <div className="empty-state">
          <p>No tickers yet.</p>
          <p>Add your first ticker to start tracking a stock or ETF.</p>
          <button type="button" className="primary" onClick={openAddModal}>
            Add ticker
          </button>
        </div>
      ) : (
        <div className="tickers-list">
          {filteredRows.map((row) => {
            const latestCall = latestCalls[row.ticker] ?? null;
            return (
              <div
                className="ticker-row-card"
                key={row.ticker}
                role="button"
                tabIndex={0}
                onClick={() => setEditingTicker(row)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setEditingTicker(row);
                  }
                }}
              >
                <div className="head">
                  <strong>{row.ticker}</strong>
                  <span className="mkt">{row.market}</span>
                  <span className="pill type">{typeLabel(row.type)}</span>
                  <span className={`pill ${row.status === "held" ? "held" : "watch"}`}>
                    {row.status === "held" ? "● Held" : "○ Watch-only"}
                  </span>
                </div>

                {row.holding && (
                  <div className="holding-line">
                    {row.holding.shares} sh &middot;{" "}
                    <strong>
                      {row.holding.cost_basis} {row.holding.currency}
                    </strong>{" "}
                    per share
                  </div>
                )}

                {latestCall ? (
                  <>
                    <div className="verdict-row">
                      <span className={`verdict-pill ${verdictClass(latestCall.verdict)}`}>
                        {latestCall.verdict}
                      </span>
                      <span>{new Date(latestCall.timestamp).toLocaleString()}</span>
                      {latestCall.confidence && (
                        <>
                          <span>&middot;</span>
                          <span>Confidence: {latestCall.confidence}</span>
                        </>
                      )}
                    </div>
                    <div className="rationale">{latestCall.rationale}</div>
                  </>
                ) : (
                  <p className="cold-start-note">
                    No checks logged yet for this ticker — results will appear here after the next run.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {isAddOpen && (
        <div className="modal-overlay" onClick={closeAddModal}>
          <div
            className="form-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-ticker-modal-heading"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="add-ticker-modal-heading">Add ticker</h2>
            <form onSubmit={handleAdd}>
              {addErrors.map((msg) => (
                <p className="error-message" key={msg}>
                  {msg}
                </p>
              ))}
              <div className="field">
                <label htmlFor="add-ticker-ticker">Ticker</label>
                <input
                  id="add-ticker-ticker"
                  value={addForm.ticker}
                  onChange={(e) => setAddForm({ ...addForm, ticker: e.target.value.toUpperCase() })}
                />
              </div>
              <div className="field">
                <label htmlFor="add-ticker-market">Market</label>
                <select
                  id="add-ticker-market"
                  value={addForm.market}
                  onChange={(e) => setAddForm({ ...addForm, market: e.target.value })}
                >
                  {MARKETS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="add-ticker-type">Type</label>
                <select
                  id="add-ticker-type"
                  value={addForm.type}
                  onChange={(e) => setAddForm({ ...addForm, type: e.target.value })}
                >
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {typeLabel(t)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="modal-actions">
                <div className="right">
                  <button type="button" className="secondary" onClick={closeAddModal}>
                    Cancel
                  </button>
                  <button type="submit" className="primary">
                    Save
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingTicker && (
        <TickerEditModal
          ticker={editingTicker}
          onClose={() => setEditingTicker(null)}
          onSaved={loadAll}
        />
      )}
    </section>
  );
}
