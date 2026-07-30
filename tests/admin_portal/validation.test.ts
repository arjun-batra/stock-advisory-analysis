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
  validateTunableValue,
  MARKETS,
  TYPES,
  STATUSES,
  CURRENCIES,
  MARKET_CURRENCY,
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

// --- holdings: currency is no longer client-validated, but its replacement (the
// market -> currency derivation map) must still be locked down (DEEP-006/INC-10,
// restores the coverage the deleted "every declared currency is accepted" test
// used to provide, now against the mechanism that actually governs currency) ----
test("MARKET_CURRENCY: every market maps to a member of CURRENCIES, matching sql/holdings_currency_derivation.sql's case mapping", () => {
  assert.deepEqual(MARKET_CURRENCY, { US: "USD", TSX: "CAD", NSE: "INR" });
  for (const market of Object.keys(MARKET_CURRENCY)) {
    assert.ok(
      (CURRENCIES as readonly string[]).includes(MARKET_CURRENCY[market as keyof typeof MARKET_CURRENCY]),
      `MARKET_CURRENCY[${market}] must be one of CURRENCIES`
    );
  }
  // every declared market is covered (configurability: MARKETS drives the map's keys)
  assert.deepEqual(Object.keys(MARKET_CURRENCY).sort(), [...MARKETS].sort());
});

// --- tunables: validateTunableValue per-key rules (FR30 sharpened, DEEP-005/INC-10) --
// scripts/config.py's _TUNABLE_CASTS ten-key contract, mirrored client-side. Happy path/
// edge case/invalid input per numeric-vs-integer-vs-boolean-vs-string key class.

test("validateTunableValue: all 5 float keys accept an integer, a decimal, and a negative value", () => {
  for (const key of [
    "DISCOVERY_GAINER_PCT",
    "DISCOVERY_LOSER_PCT",
    "DISCOVERY_VOL_SPIKE",
    "DISCOVERY_MIN_MARKET_CAP",
    "DISCOVERY_MIN_MARKET_CAP_INR",
  ]) {
    assert.deepEqual(validateTunableValue(key, "5"), [], `${key}: "5"`);
    assert.deepEqual(validateTunableValue(key, "2.5"), [], `${key}: "2.5"`);
    assert.deepEqual(validateTunableValue(key, "-5.0"), [], `${key}: "-5.0"`);
  }
});

test("validateTunableValue: float keys reject a non-numeric value (e.g. a stray %)", () => {
  const errors = validateTunableValue("DISCOVERY_GAINER_PCT", "5%");
  assert.ok(errors.length > 0);
  assert.ok(errors[0].toLowerCase().includes("numeric"));
});

test("validateTunableValue: the 2 integer keys accept a whole number but reject a decimal", () => {
  for (const key of ["DISCOVERY_SHORTLIST_MAX", "DISCOVERY_PUSH_COOLDOWN_DAYS"]) {
    assert.deepEqual(validateTunableValue(key, "15"), [], `${key}: "15"`);
    const errors = validateTunableValue(key, "15.5");
    assert.ok(errors.length > 0, `${key}: "15.5" should be rejected`);
    assert.ok(errors[0].toLowerCase().includes("integer"));
  }
});

test("validateTunableValue: ALERTS_ENABLED accepts only true/false, case-insensitively", () => {
  assert.deepEqual(validateTunableValue("ALERTS_ENABLED", "true"), []);
  assert.deepEqual(validateTunableValue("ALERTS_ENABLED", "FALSE"), []);
  assert.deepEqual(validateTunableValue("ALERTS_ENABLED", "True"), []);
  // DEEP-005's exact repro strings -- must never silently pass validation
  for (const bad of ["yes", "tru", "True ", "1", "0", ""]) {
    const errors = validateTunableValue("ALERTS_ENABLED", bad);
    assert.ok(errors.length > 0, `ALERTS_ENABLED: ${JSON.stringify(bad)} must be rejected`);
  }
});

test("validateTunableValue: GEMINI_MODEL requires non-blank", () => {
  assert.deepEqual(validateTunableValue("GEMINI_MODEL", "gemini-2.5-pro"), []);
  assert.ok(validateTunableValue("GEMINI_MODEL", "").length > 0);
  assert.ok(validateTunableValue("GEMINI_MODEL", "   ").length > 0);
});

test("validateTunableValue: GEMINI_MODEL_BACKUP accepts blank (DEEP-005's fix -- disables the fallback) and non-blank alike", () => {
  assert.deepEqual(validateTunableValue("GEMINI_MODEL_BACKUP", ""), []);
  assert.deepEqual(validateTunableValue("GEMINI_MODEL_BACKUP", "gemini-2.5-flash-lite"), []);
});

test("validateTunableValue: unknown key is rejected (defense against a future unvalidated key slipping in)", () => {
  assert.ok(validateTunableValue("NOT_A_REAL_KEY", "anything").length > 0);
});
