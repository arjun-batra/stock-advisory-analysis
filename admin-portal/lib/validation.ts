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

/**
 * FR11/FR29 (Decision #35, DEEP-006): holdings.currency is derived from the
 * held ticker's own watchlist.market, never admin-entered. This is the same
 * mapping sql/holdings_currency_derivation.sql's DB trigger enforces
 * unconditionally server-side — this constant is display-only (the portal
 * shows a read-only derived label; it never submits `currency` in a write
 * payload), so a mismatch between this map and the trigger can only ever
 * produce a wrong label, never a wrong write.
 */
export const MARKET_CURRENCY: Record<Market, Currency> = {
  US: "USD",
  TSX: "CAD",
  NSE: "INR",
};

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
 * Tunables (FR30, docs/design/admin-portal-tunables.md §16.4) — write-time validation mirroring
 * scripts/config.py's exact per-key cast/domain contract (`_TUNABLE_CASTS`), per DEEP-005/Decision #34.
 * As shipped in INC-6 this only checked for a blank value; that let a typo in a key whose cast can
 * never raise (ALERTS_ENABLED, GEMINI_MODEL/_BACKUP) through as a silent behaviour change, and a typo in
 * any numeric key through to a system-wide SystemExit outage at import time. Ten keys, ten rules — the
 * key set is fixed by the DB's own CHECK constraint (sql/admin_portal_tunables.sql), so this is not a
 * framework, just the ten cases. `sql/tunables_validate_trigger.sql` enforces the identical contract
 * server-side, so a direct SQL edit is caught the same way a portal edit is — this function is the
 * first line of defense (a better error, before any write attempt), not the only one.
 */
const _FLOAT_RE = /^-?\d+(\.\d+)?$/; // mirrors Python's float()
const _INT_RE = /^-?\d+$/; // mirrors Python's int() — no decimal point

const _NUMERIC_KEYS = [
  "DISCOVERY_GAINER_PCT",
  "DISCOVERY_LOSER_PCT",
  "DISCOVERY_VOL_SPIKE",
  "DISCOVERY_MIN_MARKET_CAP",
  "DISCOVERY_MIN_MARKET_CAP_INR",
] as const;

const _INTEGER_KEYS = ["DISCOVERY_SHORTLIST_MAX", "DISCOVERY_PUSH_COOLDOWN_DAYS"] as const;

export function validateTunableValue(key: string, value: string): string[] {
  if ((_NUMERIC_KEYS as readonly string[]).includes(key)) {
    return _FLOAT_RE.test(value) ? [] : [`Value must be numeric (e.g. "5" or "2.0").`];
  }
  if ((_INTEGER_KEYS as readonly string[]).includes(key)) {
    return _INT_RE.test(value) ? [] : [`Value must be an integer (e.g. "15"), no decimal point.`];
  }
  if (key === "ALERTS_ENABLED") {
    // The portal renders this key as a true/false select (structurally prevents the typo class), but
    // this check also guards a direct RPC/API call that bypasses the select.
    return ["true", "false"].includes(value.toLowerCase())
      ? []
      : [`Value must be exactly "true" or "false".`];
  }
  if (key === "GEMINI_MODEL") {
    // str() can't fail, but a blank primary model is still nonsensical — config.py has no fallback
    // for GEMINI_MODEL itself.
    return value.trim() ? [] : ["Value is required."];
  }
  if (key === "GEMINI_MODEL_BACKUP") {
    // Blank IS a supported, valid value — this is how an operator disables the fallback model
    // (scripts/config.py's own documented behavior). The INC-6 version of this function incorrectly
    // required non-blank for every key, which meant the portal could not express this state at all
    // (fixed in the same DEEP-005 pass, per docs/design/admin-portal-tunables.md §16.4).
    return [];
  }
  return [`Unknown tunable key: ${key}.`];
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
  return errors;
}
