// INC-7 (FR31 track-record view, FR32 kill-switch UI) — static source-level
// checks over sql/kill_switch_portal_grant.sql, admin-portal/app/(app)/track-record/page.tsx,
// admin-portal/components/KillSwitchToggle.tsx, and AuthGuard.tsx's wiring of both. Mirrors
// tunables_static.test.ts's convention (permanent regression tests over the actual shipped
// source, no live Supabase/Vercel session needed). No live-Supabase network access this session
// (same constraint as every prior increment) — the live-behavior halves of AC2/AC3 remain
// deferred; see docs/test-report.md.
//
// Special attention: docs/design/increment-plan.md's own warning that a real Postgres syntax
// error (`CREATE POLICY ... FOR select, update` — invalid, comma lists aren't allowed in a
// policy's FOR clause) survived dev's build, a prior qa pass, AND two reviewer passes in INC-6,
// only caught when the orchestrator applied it live. The tests below lock in the fixed shape as a
// permanent regression guard.
//
// Run: node --experimental-strip-types --test tests/admin_portal/*.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");
const GRANT_SQL = path.join(REPO_ROOT, "sql", "kill_switch_portal_grant.sql");
const KILL_SWITCH_SQL = path.join(REPO_ROOT, "sql", "kill_switch.sql");
const TRACK_RECORD_PAGE = path.join(REPO_ROOT, "admin-portal", "app", "(app)", "track-record", "page.tsx");
const KILL_SWITCH_TOGGLE = path.join(REPO_ROOT, "admin-portal", "components", "KillSwitchToggle.tsx");
const AUTH_GUARD = path.join(REPO_ROOT, "admin-portal", "components", "AuthGuard.tsx");

// Drops SQL comment lines (`-- ...`) — several lines here intentionally *describe in prose* the
// exact bug class being guarded against (e.g. mentioning "CREATE POLICY ... FOR select, update" as
// the historical bug it fixes), which must not itself trip a regression check meant for live code.
function sqlCodeOnly(text: string): string[] {
  return text.split("\n").filter((l) => !l.trim().startsWith("--"));
}

// Drops TS/JS comment lines (`//`, `*` continuation, `/**`) for the same reason — several doc
// comments here describe the FR31 hard boundary or the call_log-vs-latest_call_per_ticker decision
// in prose, which must not trip a regression check meant for live code.
function tsCodeOnly(text: string): string[] {
  return text.split("\n").filter((l) => {
    const t = l.trim();
    return !t.startsWith("//") && !t.startsWith("*") && !t.startsWith("/*");
  });
}

// ===========================================================================
// sql/kill_switch_portal_grant.sql — grammar/shape checks
// ===========================================================================

test("kill_switch_portal_grant.sql: admin_read_kill_switch policy targets exactly one command (select), not a comma list — regression guard for the REV-091/REV-092 class bug (invalid Postgres CREATE POLICY ... FOR select, update)", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  const policyMatch = sql.match(/create policy "admin_read_kill_switch"[\s\S]*?using \(public\.is_admin\(\)\);/i);
  assert.ok(policyMatch, "admin_read_kill_switch policy not found or not fully gated on is_admin()");
  assert.match(policyMatch![0], /for select to authenticated/i);
  assert.doesNotMatch(policyMatch![0], /for\s+\w+\s*,/i, "FOR clause must name exactly one command, not a comma-separated list");
  assert.doesNotMatch(policyMatch![0], /for all/i);
});

test("kill_switch_portal_grant.sql: admin_read_kill_switch is the only CREATE POLICY statement in the file, on kill_switch_state", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  const policyLines = sqlCodeOnly(sql).filter((l) => /create policy/i.test(l));
  assert.equal(policyLines.length, 1, "expected exactly one CREATE POLICY statement in this file");
  assert.match(policyLines[0], /admin_read_kill_switch/);
  assert.match(policyLines[0], /on public\.kill_switch_state/);
});

test("kill_switch_portal_grant.sql: set_kill_switch is CREATE OR REPLACE (extends, not redefines from scratch) and matches kill_switch.sql's proven-shape preamble/closing", () => {
  const grantSql = readFileSync(GRANT_SQL, "utf8");
  const baseSql = readFileSync(KILL_SWITCH_SQL, "utf8");
  const fnMatch = grantSql.match(/create or replace function public\.set_kill_switch\([\s\S]*?\$\$;/i);
  assert.ok(fnMatch, "set_kill_switch function definition not found");
  const fnBody = fnMatch![0];
  assert.match(fnBody, /language plpgsql security definer set search_path = ''/i);
  assert.match(fnBody, /\$\$;\s*$/, "must close with a bare $$; (matching dollar-quote, not mismatched)");
  // Preamble/signature identical to the already-live INC-3 definition.
  const baseFnMatch = baseSql.match(/create or replace function public\.set_kill_switch\([\s\S]*?security definer set search_path = ''/i);
  assert.ok(baseFnMatch, "baseline set_kill_switch signature not found in kill_switch.sql");
  const normalize = (s: string) => s.replace(/\s+/g, " ").trim();
  assert.equal(
    normalize(fnBody.split("as $$")[0]),
    normalize(baseFnMatch![0]),
    "function signature/language/security clause must be unchanged from INC-3's proven-live definition"
  );
});

test("kill_switch_portal_grant.sql: set_kill_switch's new admin check only fires for authenticated (non-null auth.uid()) callers, preserving the null-auth.uid() trusted-direct-SQL path", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  const fnMatch = sql.match(/create or replace function public\.set_kill_switch\([\s\S]*?\$\$;/i);
  assert.ok(fnMatch);
  assert.match(fnMatch![0], /if auth\.uid\(\) is not null and not public\.is_admin\(\) then/i);
  assert.match(fnMatch![0], /raise exception 'not authorized';/i);
});

test("kill_switch_portal_grant.sql: grant execute to authenticated is present, targeting the (boolean, text) overload", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  assert.match(sql, /grant execute on function public\.set_kill_switch\(boolean, text\) to authenticated;/i);
});

test("kill_switch_portal_grant.sql: REVOKE statements are well-formed and scoped to the documented gap (kill_switch_state gets all 4 verbs, kill_switch_audit gets only truncate)", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  const stateRevoke = sql.match(/revoke ([a-z, ]+) on public\.kill_switch_state from ([a-z, ]+);/i);
  assert.ok(stateRevoke, "kill_switch_state REVOKE statement not found");
  const stateVerbs = stateRevoke![1].split(",").map((v) => v.trim().toLowerCase());
  assert.deepEqual(new Set(stateVerbs), new Set(["insert", "update", "delete", "truncate"]));
  const stateRoles = stateRevoke![2].split(",").map((v) => v.trim().toLowerCase());
  assert.deepEqual(new Set(stateRoles), new Set(["public", "anon", "authenticated"]));

  const auditRevoke = sql.match(/revoke ([a-z, ]+) on public\.kill_switch_audit from ([a-z, ]+);/i);
  assert.ok(auditRevoke, "kill_switch_audit REVOKE statement not found");
  const auditVerbs = auditRevoke![1].split(",").map((v) => v.trim().toLowerCase());
  assert.deepEqual(new Set(auditVerbs), new Set(["truncate"]), "kill_switch_audit should only gain the missing truncate verb here (insert/update/delete already revoked by kill_switch.sql)");
});

test("kill_switch_portal_grant.sql: REVOKE never touches select (the new policy's grant is untouched by the REVOKE)", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  const revokeLines = sql.split("\n").filter((l) => /^\s*revoke/i.test(l));
  for (const line of revokeLines) {
    assert.doesNotMatch(line, /\bselect\b/i, `REVOKE line must not include select: ${line}`);
  }
});

test("kill_switch.sql (INC-3 baseline): kill_switch_audit's existing REVOKE does not already include truncate (confirms the gap this file closes is real, not a duplicate)", () => {
  const sql = readFileSync(KILL_SWITCH_SQL, "utf8");
  const auditRevoke = sql.match(/revoke ([a-z, ]+) on public\.kill_switch_audit from [a-z, ]+;/i);
  assert.ok(auditRevoke);
  const verbs = auditRevoke![1].split(",").map((v) => v.trim().toLowerCase());
  assert.ok(!verbs.includes("truncate"), "baseline should not already revoke truncate — otherwise the new file's REVOKE is a no-op gap-closure, not a real fix");
});

test("kill_switch_portal_grant.sql: every CREATE/REPLACE/GRANT/REVOKE/POLICY statement is terminated with a semicolon (no dangling statement); $$ dollar-quote delimiters balanced", () => {
  const sql = readFileSync(GRANT_SQL, "utf8");
  const dollarQuoteCount = (sql.match(/\$\$/g) ?? []).length;
  assert.equal(dollarQuoteCount % 2, 0, "unbalanced $$ dollar-quote delimiters");
  const codeLines = sqlCodeOnly(sql).filter((l) => l.trim().length > 0);
  const lastCodeLine = codeLines[codeLines.length - 1];
  assert.match(lastCodeLine, /;\s*$/, `last non-comment line must end with a terminated statement, got: ${lastCodeLine}`);
});

// ===========================================================================
// track-record/page.tsx — AC1 hard boundary: no new aggregation/scoring
// ===========================================================================

test("track-record page: no aggregation/derived-analytics code (no .reduce, no win-rate/score computation, no cross-row math)", () => {
  const src = tsCodeOnly(readFileSync(TRACK_RECORD_PAGE, "utf8")).join("\n");
  assert.doesNotMatch(src, /\.reduce\(/);
  assert.doesNotMatch(src, /win.?rate/i);
  assert.doesNotMatch(src, /\bscore\b/i);
  assert.doesNotMatch(src, /\btrend\b/i);
});

test("track-record page: every projected field is a raw call_log column or a single ->>'key' JSON extraction, never a computed value", () => {
  const src = readFileSync(TRACK_RECORD_PAGE, "utf8");
  const selectMatch = src.match(/CALL_LOG_SELECT\s*=\s*([\s\S]*?);/);
  assert.ok(selectMatch, "CALL_LOG_SELECT constant not found");
  const selectString = selectMatch![1].replace(/\s|"/g, "").replace(/\+/g, "");
  const fields = selectString.split(",").filter(Boolean);
  for (const field of fields) {
    assert.match(
      field,
      /^[a-z_]+$|^[a-z_]+:data_snapshot->>[a-z_]+$/,
      `unexpected field shape (not a raw column or single ->>'key' extraction): ${field}`
    );
  }
  assert.ok(fields.length > 0);
});

test("track-record page: no write path — no .insert(/.update(/.delete( against any table", () => {
  const src = readFileSync(TRACK_RECORD_PAGE, "utf8");
  assert.doesNotMatch(src, /\.insert\(/);
  assert.doesNotMatch(src, /\.update\(/);
  assert.doesNotMatch(src, /\.delete\(/);
});

test("track-record page: reads via .from(\"call_log\"), not latest_call_per_ticker (full auditable log, per §16.5)", () => {
  const rawSrc = readFileSync(TRACK_RECORD_PAGE, "utf8");
  const codeSrc = tsCodeOnly(rawSrc).join("\n");
  assert.match(rawSrc, /\.from\("call_log"\)/);
  assert.doesNotMatch(codeSrc, /latest_call_per_ticker/, "no live code path should query latest_call_per_ticker (prose mentions in doc comments are fine)");
});

test("track-record page: pagination uses .range(), sort uses .order() — UI-side only, not a stored view/function", () => {
  const src = readFileSync(TRACK_RECORD_PAGE, "utf8");
  assert.match(src, /\.range\(/);
  assert.match(src, /\.order\(/);
  assert.match(src, /PAGE_SIZE\s*=\s*25/);
});

test("track-record page: filters are ilike/eq predicates only, not derived/computed filter values", () => {
  const src = readFileSync(TRACK_RECORD_PAGE, "utf8");
  assert.match(src, /\.ilike\("ticker"/);
  assert.match(src, /\.eq\("label"/);
  assert.match(src, /\.eq\("verdict"/);
});

// ===========================================================================
// KillSwitchToggle.tsx — AC2 shape: live paused on load, correct RPC params,
// re-reads state after toggling rather than optimistically flipping
// ===========================================================================

test("KillSwitchToggle: reads kill_switch_state.paused on mount via the singleton row (id = true)", () => {
  const src = readFileSync(KILL_SWITCH_TOGGLE, "utf8");
  assert.match(src, /\.from\("kill_switch_state"\)/);
  assert.match(src, /\.select\("paused"\)/);
  assert.match(src, /\.eq\("id",\s*true\)/);
  assert.match(src, /\.single\(\)/);
});

test("KillSwitchToggle: toggle calls the set_kill_switch RPC with p_paused: !paused and p_source: \"admin-portal\" (matches §16.6's exact contract)", () => {
  const src = readFileSync(KILL_SWITCH_TOGGLE, "utf8");
  const rpcMatch = src.match(/supabase\.rpc\("set_kill_switch",\s*\{([\s\S]*?)\}\)/);
  assert.ok(rpcMatch, "supabase.rpc(\"set_kill_switch\", {...}) call not found");
  const body = rpcMatch![1];
  assert.match(body, /p_paused:\s*!paused/);
  assert.match(body, /p_source:\s*"admin-portal"/);
});

test("KillSwitchToggle: after a successful toggle, re-reads state from the table rather than optimistically flipping local state (design's explicit 'not an optimistic flip' requirement)", () => {
  const src = readFileSync(KILL_SWITCH_TOGGLE, "utf8");
  const handleToggleMatch = src.match(/async function handleToggle\(\)\s*\{([\s\S]*?)\n\s{2}\}/);
  assert.ok(handleToggleMatch, "handleToggle function not found");
  const body = handleToggleMatch![1];
  // setPaused must not be called directly inside handleToggle (that would be an optimistic flip) —
  // the only path to a new `paused` value must be via loadState() (which itself calls setPaused).
  assert.doesNotMatch(body, /\bsetPaused\(/, "handleToggle must not call setPaused directly (optimistic flip) — must re-read via loadState() instead");
  assert.match(body, /await loadState\(\)/, "handleToggle must re-read state from the table after a successful RPC call");
  // Confirm the re-read happens after the RPC call, not before (ordering matters).
  const rpcIndex = body.indexOf("supabase.rpc(");
  const reloadIndex = body.indexOf("await loadState()");
  assert.ok(rpcIndex >= 0 && reloadIndex >= 0 && reloadIndex > rpcIndex, "loadState() must be called after the rpc() call, not before");
});

test("KillSwitchToggle: renders a PAUSED/RUNNING badge and Pause/Resume button reflecting the loaded paused state", () => {
  const src = readFileSync(KILL_SWITCH_TOGGLE, "utf8");
  assert.match(src, /PAUSED/);
  assert.match(src, /RUNNING/);
  assert.match(src, /Resume/);
  assert.match(src, /Pause/);
});

// ===========================================================================
// AuthGuard.tsx — both new UI surfaces are reachable/rendered from the one
// shared authenticated chrome
// ===========================================================================

test("AuthGuard: nav includes a link to /track-record", () => {
  const src = readFileSync(AUTH_GUARD, "utf8");
  assert.match(src, /href="\/track-record"/);
});

test("AuthGuard: renders <KillSwitchToggle /> inside the shared header (visible on every authenticated route)", () => {
  const src = readFileSync(AUTH_GUARD, "utf8");
  assert.match(src, /import KillSwitchToggle from "@\/components\/KillSwitchToggle";/);
  assert.match(src, /<KillSwitchToggle\s*\/>/);
});
