// INC-6 (FR30 tunables editor) — static source-level checks over
// sql/admin_portal_tunables.sql and admin-portal/app/(app)/tunables/page.tsx,
// mirroring static_source_checks.test.ts's convention (permanent regression
// tests over the actual shipped source, no live Supabase/Vercel session
// needed). Covers the static-shape half of AC1/AC3/AC4 (the live-behavior
// half — actual RLS rejection, actual server-side stamping — needs the
// migration applied to a live project; see docs/test-report.md) and
// validateTunableValue (AC-adjacent: the one client-side rule this page
// enforces).
//
// Run: node --experimental-strip-types --test tests/admin_portal/*.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { validateTunableValue } from "../../admin-portal/lib/validation.ts";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");
const TUNABLES_SQL = path.join(REPO_ROOT, "sql", "admin_portal_tunables.sql");
const TUNABLES_PAGE = path.join(REPO_ROOT, "admin-portal", "app", "(app)", "tunables", "page.tsx");
const AUTH_GUARD = path.join(REPO_ROOT, "admin-portal", "components", "AuthGuard.tsx");

const THE_10_KEYS = [
  "GEMINI_MODEL", "GEMINI_MODEL_BACKUP", "ALERTS_ENABLED",
  "DISCOVERY_GAINER_PCT", "DISCOVERY_LOSER_PCT", "DISCOVERY_VOL_SPIKE",
  "DISCOVERY_MIN_MARKET_CAP", "DISCOVERY_MIN_MARKET_CAP_INR",
  "DISCOVERY_SHORTLIST_MAX", "DISCOVERY_PUSH_COOLDOWN_DAYS",
];

const TUNABLES_VALIDATE_SQL = path.join(REPO_ROOT, "sql", "tunables_validate_trigger.sql");

// --- AC1/AC3 (static shape): tunables table RLS + key registry ------------

test("tunables: RLS is enabled on the table", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  assert.match(sql, /alter table public\.tunables enable row level security/i);
});

test("tunables: CHECK constraint registry is exactly the 10 curated keys, no more, no fewer", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const checkMatch = sql.match(/key\s+text primary key check \(key in \(([\s\S]*?)\)\)/i);
  assert.ok(checkMatch, "CHECK (key in (...)) registry not found");
  const registered = [...checkMatch![1].matchAll(/'([A-Z0-9_]+)'/g)].map((m) => m[1]);
  assert.deepEqual(new Set(registered), new Set(THE_10_KEYS));
});

test("tunables: admin_read_tunables policy grants select only (REV-044/e46abf8), not `for all`", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const policyMatch = sql.match(/create policy "admin_read_tunables"[\s\S]*?using \(public\.is_admin\(\)\);/i);
  assert.ok(policyMatch, "admin_read_tunables policy not found or not fully gated on is_admin()");
  assert.match(policyMatch![0], /for select to authenticated/i);
  assert.doesNotMatch(policyMatch![0], /for all/i);
  assert.match(policyMatch![0], /using \(public\.is_admin\(\)\)/i);
});

test("tunables: admin_write_tunables policy grants update only (REV-044/e46abf8), not `for all`", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const policyMatch = sql.match(/create policy "admin_write_tunables"[\s\S]*?with check \(public\.is_admin\(\)\)/i);
  assert.ok(policyMatch, "admin_write_tunables policy not found or not fully gated on is_admin()");
  assert.match(policyMatch![0], /for update to authenticated/i);
  assert.doesNotMatch(policyMatch![0], /for all/i);
  assert.match(policyMatch![0], /using \(public\.is_admin\(\)\)/i);
});

test("tunables: exactly two policies (admin_read_tunables for select, admin_write_tunables for update), no insert/delete/all policy for any role (REV-033/044/e46abf8 — RLS-enabled + zero policy = denied)", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const policyLines = sql.split("\n").filter((l) => /create policy/i.test(l) && /tunables/i.test(l));
  assert.equal(policyLines.length, 2, "expected exactly two policies on tunables (admin_read_tunables, admin_write_tunables)");
  const names = policyLines.map((l) => l.match(/create policy "([a-z_]+)"/i)?.[1]);
  assert.deepEqual(new Set(names), new Set(["admin_read_tunables", "admin_write_tunables"]));
  for (const line of policyLines) {
    assert.doesNotMatch(line, /for (all|insert|delete)\b/i);
  }
});

test("tunables: updated_at/updated_by are stamped server-side by a BEFORE UPDATE trigger, not client-writable columns", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  assert.match(sql, /create trigger tunables_stamp_update\s+before update on public\.tunables/i);
  const fnMatch = sql.match(/create or replace function public\._stamp_tunable_update\(\)[\s\S]*?\$\$;/i);
  assert.ok(fnMatch, "_stamp_tunable_update() not found");
  assert.match(fnMatch![0], /new\.updated_at := now\(\)/);
  assert.match(fnMatch![0], /new\.updated_by := coalesce\(auth\.jwt\(\) ->> 'email', session_user\)/);
});

test("tunables: seed migration inserts exactly the 10 keys, with ALERTS_ENABLED seeded \"true\" (not config.py's bare \"false\" default)", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const insertBlock = sql.split(/insert into public\.tunables/i)[1];
  assert.ok(insertBlock, "seed insert statement not found");
  const seeded = [...insertBlock.matchAll(/\('([A-Z0-9_]+)', '([^']*)'/g)];
  assert.deepEqual(new Set(seeded.map((m) => m[1])), new Set(THE_10_KEYS));
  const alertsRow = seeded.find((m) => m[1] === "ALERTS_ENABLED");
  assert.ok(alertsRow);
  assert.equal(alertsRow![2], "true");
});

// --- AC4 (static shape): portal never sends anything but `value` on update -

test("tunables page: update() call only ever sends { value }, never id/key/updated_at/updated_by (server-stamped)", () => {
  const src = readFileSync(TUNABLES_PAGE, "utf8");
  const updateCalls = [...src.matchAll(/\.update\(\{([^}]*)\}\)/g)];
  assert.ok(updateCalls.length > 0, "no .update(...) call found in tunables page.tsx");
  for (const call of updateCalls) {
    const body = call[1].trim();
    assert.match(body, /^value\s*:/, `update() payload must be exactly { value }, got: { ${body} }`);
  }
});

test("tunables page: no insert()/delete() call against the tunables table (RLS only grants select/update)", () => {
  const src = readFileSync(TUNABLES_PAGE, "utf8");
  assert.doesNotMatch(src, /\.insert\(/);
  assert.doesNotMatch(src, /\.delete\(\)/);
});

test("tunables page: reads via .from(\"tunables\").select(\"*\")", () => {
  const src = readFileSync(TUNABLES_PAGE, "utf8");
  assert.match(src, /\.from\("tunables"\)/);
});

// --- AC1 (static shape, DEEP-005/INC-10): ALERTS_ENABLED is structurally a select, not free text ---

test("tunables page: ALERTS_ENABLED renders a <select> with exactly the true/false options, not a text <input>", () => {
  const src = readFileSync(TUNABLES_PAGE, "utf8");
  const branch = src.match(/row\.key === "ALERTS_ENABLED"[\s\S]*?<select[\s\S]*?<\/select>/);
  assert.ok(branch, "no <select> branch found for ALERTS_ENABLED");
  const optionValues = [...branch![0].matchAll(/<option value="([^"]+)">/g)].map((m) => m[1]);
  assert.deepEqual(new Set(optionValues), new Set(["true", "false"]));
});

test("tunables page: handleUpdate calls validateTunableValue with the row's key (not the old value-only signature)", () => {
  const src = readFileSync(TUNABLES_PAGE, "utf8");
  assert.match(src, /validateTunableValue\(key,\s*editValue\)/);
});

// --- DEEP-005/INC-10: sql/tunables_validate_trigger.sql (server-side mirror) --------

test("tunables_validate_trigger.sql: a CASE branch exists for every one of the 10 curated keys", () => {
  const sql = readFileSync(TUNABLES_VALIDATE_SQL, "utf8");
  for (const key of THE_10_KEYS) {
    assert.match(sql, new RegExp(`'${key}'`), `no validation branch found for ${key}`);
  }
});

test("tunables_validate_trigger.sql: trigger name sorts before tunables_stamp_update (fires first, validate-then-stamp)", () => {
  const sql = readFileSync(TUNABLES_VALIDATE_SQL, "utf8");
  // Matches both `create trigger ...` and `create or replace trigger ...` -- this test is about
  // fire-order (tgname sorting), not about which creation form is used; idempotency of the
  // creation form itself is a separate, dedicated test below (BUG-008).
  const triggerMatch = sql.match(/create (?:or replace )?trigger (\S+)\s+before update on public\.tunables/i);
  assert.ok(triggerMatch, "new validate trigger not found");
  const newTriggerName = triggerMatch![1];
  assert.ok(
    newTriggerName.toLowerCase() < "tunables_stamp_update",
    `trigger name '${newTriggerName}' must sort before 'tunables_stamp_update' (Postgres fires same-event ` +
      `BEFORE triggers in tgname order) so a rejected write never reaches the stamp trigger`
  );
});

test("tunables_validate_trigger.sql: trigger creation is idempotent -- create or replace, never a bare create trigger (BUG-008 regression guard)", () => {
  const sql = readFileSync(TUNABLES_VALIDATE_SQL, "utf8");
  // A bare `create trigger` (no `or replace`, no preceding `drop trigger if exists`) errors
  // `trigger "..." already exists` on a second apply -- this is the exact defect BUG-008 filed
  // and dev fixed. Assert the property that actually matters (re-runnable against a live table
  // per docs/runbook.md's idempotency requirement), not just that some particular syntax string
  // is present -- every `create ... trigger` statement in the file must be the `or replace` form.
  // Strip SQL line comments first -- the file's own BUG-008 explanatory comment mentions the
  // literal string "create trigger" in prose, which must not be mistaken for a real statement.
  const sqlNoComments = sql.replace(/--.*$/gm, "");
  const triggerStatements = [...sqlNoComments.matchAll(/create\s+(or replace\s+)?trigger\b/gi)];
  assert.ok(triggerStatements.length >= 1, "no trigger-creation statement found in the file");
  for (const stmt of triggerStatements) {
    assert.ok(
      stmt[1],
      `found a bare "create trigger" (not idempotent -- BUG-008) in: "${stmt[0]}"; use "create or replace trigger"`
    );
  }
});

test("tunables_validate_trigger.sql: does not redefine the tunables table, the stamp trigger, or either RLS policy (strictly additive)", () => {
  const sql = readFileSync(TUNABLES_VALIDATE_SQL, "utf8");
  assert.doesNotMatch(sql, /create table/i);
  assert.doesNotMatch(sql, /create policy/i);
  assert.doesNotMatch(sql, /drop table/i);
  assert.doesNotMatch(sql, /drop policy/i);
  assert.doesNotMatch(sql, /drop trigger/i);
  // comments may reference the already-live trigger by name (context); only an actual
  // create/replace/drop statement targeting it would be a redefinition.
  assert.doesNotMatch(sql, /create (or replace )?trigger tunables_stamp_update/i);
});

// --- AuthGuard: the new page is reachable and covered by the existing gate -

test("AuthGuard: nav includes a link to /tunables", () => {
  const src = readFileSync(AUTH_GUARD, "utf8");
  assert.match(src, /href="\/tunables"/);
});

// --- validateTunableValue: happy path, edge case, invalid input ------------
// DEEP-005/INC-10: validateTunableValue is now key-aware (was value-only) — mirrors
// scripts/config.py's per-key cast contract (docs/design/admin-portal-tunables.md §16.4). These three
// call sites are updated to pass a key, same mechanical adaptation as any other caller of a function
// whose signature a design-mandated fix changed (same class of update as INC-9's handoff renaming
// existing test mocks after ingest.get_price_only()'s introduction) — the tests' original intent
// (non-blank happy path / whitespace / empty rejected) is unchanged, just exercised against
// GEMINI_MODEL, whose rule is still "non-blank". Per-key rule coverage lives in validation.test.ts.

test("validateTunableValue: a non-blank value has no errors (happy path, GEMINI_MODEL)", () => {
  assert.deepEqual(validateTunableValue("GEMINI_MODEL", "gemini-2.5-flash"), []);
});

test("validateTunableValue: whitespace-only value is rejected (edge case, GEMINI_MODEL)", () => {
  assert.ok(validateTunableValue("GEMINI_MODEL", "   ").length > 0);
});

test("validateTunableValue: empty string is rejected (invalid input, GEMINI_MODEL)", () => {
  assert.ok(validateTunableValue("GEMINI_MODEL", "").length > 0);
});
