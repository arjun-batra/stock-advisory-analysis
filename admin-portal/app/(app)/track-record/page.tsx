"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-client";

/**
 * FR31 track-record view. Read-only, paginated presentation of `public.call_log` — the full
 * auditable history (docs/design/admin-portal.md §16.5), not `latest_call_per_ticker` (that view is
 * DISTINCT-ON'd to one row per ticker, nothing to paginate; the dashboard already covers that
 * "latest snapshot" case). Reuses call_log's existing `anon_read_call_log` policy — no new SQL.
 *
 * Hard boundary (FR31 text, design §16.5): no new aggregation, scoring, or trend computation.
 * `parse_status`/`price`/`confidence` are extracted from `data_snapshot` with the exact same
 * `->>'key'` technique `sql/dashboard_latest_call_view.sql` already proved safe — never a computed
 * value, never the full jsonb blob (raw_model_response stays server-side).
 */

const PAGE_SIZE = 25; // UI pagination size, not a business tunable — no config-file entry.
const LABELS = ["watchlist", "new-candidate"] as const; // matches data-and-flow.md §5
const VERDICTS = ["Buy", "Sell", "Hold"] as const; // matches pages/common.js's VERDICT map

type SortColumn = "timestamp" | "ticker" | "verdict";

interface CallLogRow {
  id: string;
  ticker: string;
  verdict: string;
  rationale: string;
  timestamp: string;
  label: string;
  alerted: boolean;
  parse_status: string | null;
  price: string | null;
  confidence: string | null;
}

const CALL_LOG_SELECT =
  "id,ticker,verdict,rationale,timestamp,label,alerted," +
  "parse_status:data_snapshot->>parse_status," +
  "price:data_snapshot->>price," +
  "confidence:data_snapshot->>confidence";

export default function TrackRecordPage() {
  const supabase = createClient();
  const [rows, setRows] = useState<CallLogRow[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sortColumn, setSortColumn] = useState<SortColumn>("timestamp");
  const [sortAscending, setSortAscending] = useState(false);

  const [tickerFilter, setTickerFilter] = useState("");
  const [labelFilter, setLabelFilter] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("");
  const [appliedFilters, setAppliedFilters] = useState({ ticker: "", label: "", verdict: "" });

  async function loadRows() {
    setLoading(true);
    setError(null);

    let query = supabase.from("call_log").select(CALL_LOG_SELECT, { count: "exact" });
    if (appliedFilters.ticker.trim()) {
      query = query.ilike("ticker", `%${appliedFilters.ticker.trim()}%`);
    }
    if (appliedFilters.label) {
      query = query.eq("label", appliedFilters.label);
    }
    if (appliedFilters.verdict) {
      query = query.eq("verdict", appliedFilters.verdict);
    }

    const from = page * PAGE_SIZE;
    const to = from + PAGE_SIZE - 1;
    const { data, error: fetchError, count } = await query
      .order(sortColumn, { ascending: sortAscending })
      .range(from, to);

    if (fetchError) {
      setError(fetchError.message);
    } else {
      // supabase-js's select-string type parser doesn't resolve the `alias:col->>key` JSON-operator
      // syntax to a concrete row shape (no Database generic is wired up in this portal — see
      // lib/supabase-client.ts) — the runtime shape is exactly CallLogRow, so this is a type-only cast.
      setRows((data as unknown as CallLogRow[]) ?? []);
      setTotalCount(count ?? 0);
    }
    setLoading(false);
  }

  useEffect(() => {
    // Mount-time fetch, re-run whenever page/sort/applied-filters change — same reusable-named-
    // function pattern as watchlist/holdings/tunables.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, sortColumn, sortAscending, appliedFilters]);

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    setPage(0);
    setAppliedFilters({ ticker: tickerFilter, label: labelFilter, verdict: verdictFilter });
  }

  function clearFilters() {
    setTickerFilter("");
    setLabelFilter("");
    setVerdictFilter("");
    setPage(0);
    setAppliedFilters({ ticker: "", label: "", verdict: "" });
  }

  // BUG-011 fix: sort is a <select> + direction-toggle button, not clickable
  // <th> column headers -- a card layout (below) has no column-header row for
  // that affordance to live in. Same underlying sortColumn/sortAscending
  // state and .order() query as before, just a different control surface.
  function changeSortColumn(column: SortColumn) {
    setPage(0);
    setSortColumn(column);
    setSortAscending(false);
  }

  function toggleSortDirection() {
    setPage(0);
    setSortAscending((prev) => !prev);
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  function verdictClass(verdict: string): string {
    const v = verdict.toLowerCase();
    return v === "buy" || v === "sell" || v === "hold" ? v : "";
  }

  return (
    <section>
      <h1>Track record</h1>
      {error && <p className="error-message">{error}</p>}

      <form className="crud-form" onSubmit={applyFilters}>
        <label>
          Ticker contains
          <input value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value.toUpperCase())} />
        </label>
        <label>
          Label
          <select value={labelFilter} onChange={(e) => setLabelFilter(e.target.value)}>
            <option value="">(any)</option>
            {LABELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Verdict
          <select value={verdictFilter} onChange={(e) => setVerdictFilter(e.target.value)}>
            <option value="">(any)</option>
            {VERDICTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <div>
          <button type="submit" className="primary">
            Apply filters
          </button>{" "}
          <button type="button" className="link" onClick={clearFilters}>
            Clear
          </button>
        </div>
      </form>

      {loading ? (
        <p className="status-line">Loading…</p>
      ) : (
        <>
          <div className="sort-controls">
            <label>
              Sort by{" "}
              <select
                value={sortColumn}
                onChange={(e) => changeSortColumn(e.target.value as SortColumn)}
              >
                <option value="timestamp">Timestamp</option>
                <option value="ticker">Ticker</option>
                <option value="verdict">Verdict</option>
              </select>
            </label>
            <button type="button" className="link" onClick={toggleSortDirection}>
              {sortAscending ? "Ascending ▲" : "Descending ▼"}
            </button>
          </div>

          <div className="tr-cards">
            {rows.map((row) => (
              <div className="tr-card" key={row.id}>
                <div className="top">
                  <strong>{row.ticker}</strong>
                  <span className={`verdict-pill ${verdictClass(row.verdict)}`}>{row.verdict}</span>
                </div>
                <p className="rationale" title={row.rationale}>
                  {row.rationale}
                </p>
                <dl className="tr-fields">
                  <dt>Price</dt>
                  <dd>{row.price ?? ""}</dd>
                  <dt>Confidence</dt>
                  <dd>{row.confidence ?? ""}</dd>
                  <dt>Parse status</dt>
                  <dd>{row.parse_status ?? ""}</dd>
                  <dt>Label</dt>
                  <dd>{row.label}</dd>
                  <dt>Alerted</dt>
                  <dd>{row.alerted ? "yes" : "no"}</dd>
                </dl>
                <div className="foot">{new Date(row.timestamp).toLocaleString()}</div>
              </div>
            ))}
          </div>

          <p className="status-line">
            Page {page + 1} of {totalPages} ({totalCount} rows){" "}
            <button type="button" className="link" onClick={() => setPage(page - 1)} disabled={page <= 0}>
              Previous
            </button>{" "}
            <button
              type="button"
              className="link"
              onClick={() => setPage(page + 1)}
              disabled={page + 1 >= totalPages}
            >
              Next
            </button>
          </p>
        </>
      )}
    </section>
  );
}
