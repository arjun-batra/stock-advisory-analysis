// Static source-level checks over admin-portal/ and sql/admin_portal_rls.sql —
// these are permanent regression tests for things that are cheap to check by
// grepping the actual shipped source, without a live Supabase/Vercel session.
// Covers: AC1 (no email/password/magic-link UI anywhere), AC6 (admin_allowlist/
// is_admin() exist, RLS enabled, zero policies on admin_allowlist; both write
// policies gated on is_admin()), AC7 (no secret-looking string, and no
// *dynamic* process.env[...] access anywhere — the exact pattern that caused
// the real production bug fixed in commit 6895db0: NEXT_PUBLIC_* vars silently
// resolving to undefined because Next.js/webpack only statically inlines a
// literal `process.env.EXACT_NAME` expression, never a computed one).
//
// Run: node --experimental-strip-types --test tests/admin_portal/static_source_checks.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");
const PORTAL_DIR = path.join(REPO_ROOT, "admin-portal");
const RLS_SQL = path.join(REPO_ROOT, "sql", "admin_portal_rls.sql");

function grepPortal(pattern: string, extraArgs: string[] = []): string[] {
  try {
    const out = execFileSync(
      "grep",
      ["-rnE", ...extraArgs, pattern, "app", "lib", "components"],
      { cwd: PORTAL_DIR, encoding: "utf8" }
    );
    return out.trim().split("\n").filter(Boolean);
  } catch (e: unknown) {
    // grep exits 1 when there are zero matches — that's the expected "clean" case.
    const err = e as { status?: number };
    if (err.status === 1) return [];
    throw e;
  }
}

// Drops matches that only occur inside a `//` or `/* ... * ... */` comment
// line — several files here intentionally *describe in prose* the exact
// anti-pattern they avoid (e.g. supabase-client.ts's doc-comment explaining
// why process.env[name] is never used; login/page.tsx's doc-comment stating
// no magic-link UI exists). A prose mention of the forbidden pattern is not
// itself a live code path, so it must not fail these regression checks.
function codeOnly(lines: string[]): string[] {
  return lines.filter((line) => {
    const content = line.split(":").slice(2).join(":").trim();
    return !content.startsWith("*") && !content.startsWith("//");
  });
}

// --- AC7 / regression for the fixed production bug -----------------------
test("no dynamic process.env[...] (computed-key) access anywhere in admin-portal source", () => {
  const codeHits = codeOnly(grepPortal(String.raw`process\.env\[`));
  assert.deepEqual(
    codeHits,
    [],
    "dynamic process.env[name] access found in admin-portal source (Next.js never statically inlines this for NEXT_PUBLIC_* vars — see commit 6895db0)"
  );
});

test("every process.env reference in admin-portal source is a literal NEXT_PUBLIC_SUPABASE_* access", () => {
  const codeHits = codeOnly(grepPortal(String.raw`process\.env\.`));
  assert.ok(codeHits.length > 0, "expected at least one literal process.env.X reference (supabase-client.ts, auth/callback/route.ts)");
  for (const line of codeHits) {
    assert.match(
      line,
      /process\.env\.NEXT_PUBLIC_SUPABASE_(URL|ANON_KEY)\b/,
      `unexpected env var referenced outside the two documented NEXT_PUBLIC_* vars: ${line}`
    );
  }
});

// --- AC7: no secret-looking string anywhere in source ---------------------
test("no service_role / secret-key / PAT-looking string anywhere in admin-portal source", () => {
  const hits = grepPortal(
    String.raw`service_role|SUPABASE_SERVICE|GEMINI_API_KEY|GITHUB_TOKEN|_PAT\b|client_secret`,
    ["-i"]
  );
  assert.deepEqual(hits, []);
});

// --- AC1: no email/password or magic-link auth UI -------------------------
test("no email/password or magic-link/OTP sign-in code path anywhere in admin-portal source", () => {
  const hits = codeOnly(
    grepPortal(String.raw`signInWithPassword|signInWithOtp|signUp\(|type="password"|magic.?link`, ["-i"])
  );
  assert.deepEqual(hits, []);
});

test("login page only wires up Google OAuth (signInWithOAuth with provider: google)", () => {
  const loginSrc = readFileSync(path.join(PORTAL_DIR, "app", "login", "page.tsx"), "utf8");
  assert.match(loginSrc, /signInWithOAuth/);
  assert.match(loginSrc, /provider:\s*"google"/);
});

// --- AC6: admin_allowlist / is_admin() / RLS shape -------------------------
test("admin_allowlist: RLS enabled, zero CREATE POLICY statements target it", () => {
  const sql = readFileSync(RLS_SQL, "utf8");
  assert.match(sql, /alter table public\.admin_allowlist enable row level security/i);
  const policyLines = sql
    .split("\n")
    .filter((l) => /create policy/i.test(l) && /admin_allowlist/i.test(l));
  assert.deepEqual(policyLines, [], "admin_allowlist must have zero policies (REV-033) — a policy referencing it was found");
});

test("is_admin() is SECURITY DEFINER and reads from admin_allowlist", () => {
  const sql = readFileSync(RLS_SQL, "utf8");
  const fnMatch = sql.match(/create or replace function public\.is_admin\(\)[\s\S]*?\$\$;/i);
  assert.ok(fnMatch, "is_admin() function definition not found");
  assert.match(fnMatch![0], /security definer/i);
  assert.match(fnMatch![0], /admin_allowlist/);
});

test("both admin_write_watchlist and admin_write_holdings policies gate on public.is_admin() in USING and WITH CHECK", () => {
  const sql = readFileSync(RLS_SQL, "utf8");
  for (const policyName of ["admin_write_watchlist", "admin_write_holdings"]) {
    const re = new RegExp(
      `create policy "${policyName}"[\\s\\S]*?with check \\(public\\.is_admin\\(\\)\\)`,
      "i"
    );
    const match = sql.match(re);
    assert.ok(match, `${policyName} not found or not gated on is_admin() in both USING and WITH CHECK`);
    assert.match(match![0], /using \(public\.is_admin\(\)\)/i);
  }
});

// --- DEEP-006/INC-10 (FR11/FR29, Decision #35): holdings.currency is derived, not admin-entered ----
//
// INC-15 (docs/design/admin-portal.md §16.11) deleted the separate holdings/page.tsx
// and merged its edit form into TickerEditModal.tsx, with the "+ Add ticker" insert
// call now living in tickers/page.tsx. Repointed 2026-08-01 (qa) at the new files —
// same behavioral guarantee as before (currency is never an admin-entered field, never
// sent in a write payload, and displayed only as a read-only derived chip), just
// against the post-merge markup/call sites. Confirmed manually against
// docs/ux-mockups/direction-g-tickers-merge.html's `.field .derived` chip, which is the
// same mechanism, carried over unchanged (§16.11.4).

const TICKERS_PAGE = path.join(PORTAL_DIR, "app", "(app)", "tickers", "page.tsx");
const TICKER_EDIT_MODAL = path.join(PORTAL_DIR, "components", "TickerEditModal.tsx");
const HOLDINGS_CURRENCY_SQL = path.join(REPO_ROOT, "sql", "holdings_currency_derivation.sql");

test("tickers page + edit modal: no currency <select>/<input> anywhere in the add or edit form", () => {
  for (const file of [TICKERS_PAGE, TICKER_EDIT_MODAL]) {
    const src = readFileSync(file, "utf8");
    assert.doesNotMatch(src, /name=["']currency["']/, `unexpected currency form control in ${file}`);
    assert.doesNotMatch(src, /CURRENCIES\.map/, `unexpected currency <select> options in ${file}`);
  }
});

// Extracts the literal argument text of every `.insert(...)`/`.update(...)` call by
// counting paren/bracket/brace depth from the opening `(` to its true matching `)`,
// rather than a regex that (QA-observed, INC-14 handoff) depends on incidental
// "}<no-gap>)" shapes appearing elsewhere in the file to terminate a lazy match —
// that regex could silently start passing/failing based on unrelated function
// ordering (confirmed by removing openEditModal in a scratch test: match count
// dropped from 2 to 1 even though the currency-payload behavior didn't change).
function extractCallArgs(src: string, methodNames: string[]): { method: string; args: string }[] {
  const results: { method: string; args: string }[] = [];
  const callRe = new RegExp(`\\.(${methodNames.join("|")})\\(`, "g");
  let m: RegExpExecArray | null;
  while ((m = callRe.exec(src)) !== null) {
    const openParenIdx = m.index + m[0].length - 1;
    let depth = 0;
    let i = openParenIdx;
    for (; i < src.length; i++) {
      if (src[i] === "(" || src[i] === "[" || src[i] === "{") depth++;
      else if (src[i] === ")" || src[i] === "]" || src[i] === "}") {
        depth--;
        if (depth === 0) break;
      }
    }
    results.push({ method: m[1], args: src.slice(openParenIdx + 1, i) });
  }
  return results;
}

test("tickers page + edit modal: insert()/update()/rpc() payloads never send `currency` (server derives it unconditionally)", () => {
  // tickers/page.tsx: the "+ Add ticker" insert() (creates a watch-only watchlist
  // row, no holdings row -- see AC12). TickerEditModal.tsx: the plain
  // market/type update(), the plain shares/cost_basis update() (status unchanged,
  // already held), and the two set_ticker_holding_status/delete_ticker rpc() calls
  // (the two FR37 RPCs, §16.11.5) -- none of these payloads may carry a raw
  // `currency` key; the server (holdings_derive_currency trigger, unconditional)
  // is the sole place currency is set, both pre- and post-merge.
  const pageWrites = extractCallArgs(readFileSync(TICKERS_PAGE, "utf8"), ["insert", "update", "rpc"]);
  const modalWrites = extractCallArgs(readFileSync(TICKER_EDIT_MODAL, "utf8"), ["insert", "update", "rpc"]);
  const writeCalls = [...pageWrites, ...modalWrites];
  assert.ok(
    writeCalls.length >= 4,
    "expected at least an insert() (tickers/page.tsx), a plain update(), and both rpc() calls (TickerEditModal.tsx)"
  );
  for (const call of writeCalls) {
    assert.doesNotMatch(call.args, /currency\s*:/, `${call.method}() payload must not send currency: ${call.args}`);
  }
});

test("edit modal: displays a read-only derived currency (via MARKET_CURRENCY), not an editable field", () => {
  const src = readFileSync(TICKER_EDIT_MODAL, "utf8");
  assert.match(src, /MARKET_CURRENCY/);
  // Post-merge markup (docs/ux-mockups/direction-g-tickers-merge.html's `.field
  // .derived` chip) drops the old page's literal "Derived from market — not
  // editable." hint sentence, but keeps the same read-only-chip mechanism: a
  // <span className="derived"> showing the MARKET_CURRENCY-looked-up value
  // followed by "(from {market})" -- never an <input>/<select> for currency
  // (already asserted by the no-currency-form-control test above).
  assert.match(src, /className="derived"/);
  assert.match(src, /\(from\s*\{form\.market\}\)/);
});

test("holdings_currency_derivation.sql: trigger fires on BEFORE INSERT OR UPDATE and unconditionally sets new.currency", () => {
  const sql = readFileSync(HOLDINGS_CURRENCY_SQL, "utf8");
  assert.match(sql, /before insert or update on public\.holdings/i);
  assert.match(sql, /new\.currency\s*:=\s*v_currency/);
});

test("holdings_currency_derivation.sql: does not redefine the holdings table or admin_write_holdings policy (strictly additive)", () => {
  const sql = readFileSync(HOLDINGS_CURRENCY_SQL, "utf8");
  assert.doesNotMatch(sql, /create table/i);
  assert.doesNotMatch(sql, /create policy/i);
  assert.doesNotMatch(sql, /drop table/i);
  assert.doesNotMatch(sql, /drop policy/i);
});

test("holdings_currency_derivation.sql: trigger creation is idempotent -- create or replace, never a bare create trigger (BUG-008 regression guard)", () => {
  const sql = readFileSync(HOLDINGS_CURRENCY_SQL, "utf8");
  // Same defect class as tunables_validate_trigger.sql's BUG-008: a bare `create trigger` errors
  // `trigger "..." already exists` on a second apply. Assert the re-runnable property directly
  // rather than matching one particular syntax string. Strip SQL line comments first -- the
  // file's own BUG-008 explanatory comment mentions the literal string "create trigger" in prose.
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
