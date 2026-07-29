/**
 * Pure validation helpers mirroring sql/schema.sql's CHECK constraints for
 * `watchlist` (docs/design/admin-portal.md §16.3) — no validation rule
 * invented beyond what the DB already enforces. Kept separate from the form
 * components so they're independently testable.
 */

export const MARKETS = ["US", "TSX", "NSE"] as const;
export const TYPES = ["stock", "ETF"] as const;
export const STATUSES = ["held", "watch-only"] as const;
export const CURRENCIES = ["USD", "CAD", "INR"] as const;

export type Market = (typeof MARKETS)[number];
export type WatchlistType = (typeof TYPES)[number];
export type WatchlistStatus = (typeof STATUSES)[number];
export type Currency = (typeof CURRENCIES)[number];

export interface WatchlistInput {
  ticker: string;
  market: string;
  type: string;
  status: string;
}

export interface HoldingsInput {
  ticker: string;
  shares: string;
  cost_basis: string;
  currency: string;
}

export function validateWatchlistRow(input: WatchlistInput): string[] {
  const errors: string[] = [];
  if (!input.ticker.trim()) errors.push("Ticker is required.");
  if (!MARKETS.includes(input.market as Market)) {
    errors.push(`Market must be one of: ${MARKETS.join(", ")}.`);
  }
  if (!TYPES.includes(input.type as WatchlistType)) {
    errors.push(`Type must be one of: ${TYPES.join(", ")}.`);
  }
  if (!STATUSES.includes(input.status as WatchlistStatus)) {
    errors.push(`Status must be one of: ${STATUSES.join(", ")}.`);
  }
  return errors;
}

/**
 * Tunables (FR30, docs/design/admin-portal-tunables.md §16.4) — the portal only ever UPDATEs one of
 * the 10 migration-seeded rows (RLS grants `select, update` only, REV-044); there is no add/delete
 * form, so the only client-side rule worth enforcing is "don't submit a blank value" — every other
 * constraint (which keys exist, cast validity) is enforced server-side by the CHECK constraint and
 * scripts/config.py's own cast, not duplicated here.
 */
export function validateTunableValue(value: string): string[] {
  const errors: string[] = [];
  if (!value.trim()) errors.push("Value is required.");
  return errors;
}

export function validateHoldingsRow(input: HoldingsInput): string[] {
  const errors: string[] = [];
  if (!input.ticker.trim()) errors.push("Ticker is required.");
  const shares = Number(input.shares);
  if (!Number.isFinite(shares) || shares <= 0) {
    errors.push("Shares must be a number greater than 0.");
  }
  const costBasis = Number(input.cost_basis);
  if (!Number.isFinite(costBasis) || costBasis <= 0) {
    errors.push("Cost basis must be a number greater than 0.");
  }
  if (!CURRENCIES.includes(input.currency as Currency)) {
    errors.push(`Currency must be one of: ${CURRENCIES.join(", ")}.`);
  }
  return errors;
}
