// Tests admin-portal/lib/validation.ts against FR28/FR29 field constraints
// (docs/design/admin-portal.md §16.3 — form fields mirror sql/schema.sql's
// CHECK constraints 1:1, no invented validation rules). Run with:
//   node --experimental-strip-types --test tests/admin_portal/validation.test.ts
// (Node's native TS type-stripping — no new devDependency added; see
// docs/test-report.md INC-5 entry for why this approach was chosen over
// installing a JS test framework.)

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  validateWatchlistRow,
  validateHoldingsRow,
  MARKETS,
  TYPES,
  STATUSES,
} from "../../admin-portal/lib/validation.ts";

// --- watchlist: happy path ---------------------------------------------
test("validateWatchlistRow: valid row -> no errors", () => {
  assert.deepEqual(
    validateWatchlistRow({ ticker: "AAPL", market: "US", type: "stock", status: "held" }),
    []
  );
});

test("validateWatchlistRow: every declared market/type/status combination is accepted", () => {
  for (const market of MARKETS) {
    for (const type of TYPES) {
      for (const status of STATUSES) {
        assert.deepEqual(
          validateWatchlistRow({ ticker: "X", market, type, status }),
          [],
          `expected no errors for ${market}/${type}/${status}`
        );
      }
    }
  }
});

// --- watchlist: edge case (whitespace-only ticker) ----------------------
test("validateWatchlistRow: whitespace-only ticker is rejected (edge case, not just empty string)", () => {
  const errors = validateWatchlistRow({ ticker: "   ", market: "US", type: "stock", status: "held" });
  assert.ok(errors.includes("Ticker is required."));
});

// --- watchlist: invalid input --------------------------------------------
test("validateWatchlistRow: invalid market/type/status all flagged, ticker missing flagged", () => {
  const errors = validateWatchlistRow({ ticker: "", market: "LSE", type: "bond", status: "sold" });
  assert.equal(errors.length, 4);
  assert.ok(errors.some((e) => e.includes("Ticker is required")));
  assert.ok(errors.some((e) => e.includes("Market must be one of")));
  assert.ok(errors.some((e) => e.includes("Type must be one of")));
  assert.ok(errors.some((e) => e.includes("Status must be one of")));
});

// --- holdings: happy path -------------------------------------------------
// DEEP-006/INC-10 (Decision #35): HoldingsInput/validateHoldingsRow dropped `currency` — it's now
// derived server-side from the held ticker's watchlist.market (sql/holdings_currency_derivation.sql),
// never admin-entered/validated client-side. These call sites are updated to the new shape (same
// mechanical adaptation as tunables_static.test.ts's validateTunableValue call sites above); the
// currency-specific assertions/tests are removed since there is no longer a client-side currency rule
// to test — the DB trigger is the sole enforcement mechanism now.
test("validateHoldingsRow: valid row -> no errors", () => {
  assert.deepEqual(
    validateHoldingsRow({ ticker: "AAPL", shares: "10", cost_basis: "150.50" }),
    []
  );
});

// --- holdings: edge cases (boundary of the >0 CHECK constraint) ----------
test("validateHoldingsRow: shares of exactly 0 is rejected (matches DB CHECK shares > 0)", () => {
  const errors = validateHoldingsRow({ ticker: "AAPL", shares: "0", cost_basis: "1" });
  assert.ok(errors.includes("Shares must be a number greater than 0."));
});

test("validateHoldingsRow: negative cost_basis is rejected (matches DB CHECK cost_basis > 0)", () => {
  const errors = validateHoldingsRow({ ticker: "AAPL", shares: "1", cost_basis: "-5" });
  assert.ok(errors.includes("Cost basis must be a number greater than 0."));
});

// --- holdings: invalid input ----------------------------------------------
test("validateHoldingsRow: non-numeric shares/cost_basis and missing ticker all flagged", () => {
  const errors = validateHoldingsRow({
    ticker: "",
    shares: "not-a-number",
    cost_basis: "also-not-a-number",
  });
  assert.equal(errors.length, 3);
  assert.ok(errors.some((e) => e.includes("Ticker is required")));
  assert.ok(errors.some((e) => e.includes("Shares must be a number greater than 0")));
  assert.ok(errors.some((e) => e.includes("Cost basis must be a number greater than 0")));
});
