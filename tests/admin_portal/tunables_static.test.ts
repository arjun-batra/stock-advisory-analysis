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

test("tunables: admin_write_tunables policy is scoped to select/update only (REV-044), not `for all`", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const policyMatch = sql.match(/create policy "admin_write_tunables"[\s\S]*?with check \(public\.is_admin\(\)\)/i);
  assert.ok(policyMatch, "admin_write_tunables policy not found or not fully gated on is_admin()");
  assert.match(policyMatch![0], /for select, update to authenticated/i);
  assert.doesNotMatch(policyMatch![0], /for all/i);
  assert.match(policyMatch![0], /using \(public\.is_admin\(\)\)/i);
});

test("tunables: no insert/delete policy exists for any role (REV-033/044 — RLS-enabled + zero policy = denied)", () => {
  const sql = readFileSync(TUNABLES_SQL, "utf8");
  const policyLines = sql.split("\n").filter((l) => /create policy/i.test(l) && /tunables/i.test(l));
  assert.equal(policyLines.length, 1, "expected exactly one policy on tunables (admin_write_tunables)");
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

// --- AuthGuard: the new page is reachable and covered by the existing gate -

test("AuthGuard: nav includes a link to /tunables", () => {
  const src = readFileSync(AUTH_GUARD, "utf8");
  assert.match(src, /href="\/tunables"/);
});

// --- validateTunableValue: happy path, edge case, invalid input ------------

test("validateTunableValue: a non-blank value has no errors (happy path)", () => {
  assert.deepEqual(validateTunableValue("gemini-2.5-flash"), []);
});

test("validateTunableValue: whitespace-only value is rejected (edge case)", () => {
  assert.ok(validateTunableValue("   ").length > 0);
});

test("validateTunableValue: empty string is rejected (invalid input)", () => {
  assert.ok(validateTunableValue("").length > 0);
});
