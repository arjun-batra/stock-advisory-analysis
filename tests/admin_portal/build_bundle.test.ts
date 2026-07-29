// Real `next build` regression test — this is the exact class of bug that
// slipped past unit-level review the first time: a dynamic `process.env[name]`
// helper type-checks fine and passes any pure-logic unit test, but silently
// resolves to `undefined` in the actual production bundle because
// Next.js/webpack only statically inlines a literal `process.env.EXACT_NAME`
// expression (see commit 6895db0, fixed post-handoff). The only way to catch
// this class of bug is to run the real build and inspect the real output —
// so this test does exactly that, with disposable marker env values (no real
// credentials involved).
//
// Slower than the other admin-portal tests (invokes `next build`, ~10-20s) —
// kept in its own file so it can be skipped/run separately if needed.
// Run: node --experimental-strip-types --test tests/admin_portal/build_bundle.test.ts

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync, rmSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");
const PORTAL_DIR = path.join(REPO_ROOT, "admin-portal");
const NEXT_DIR = path.join(PORTAL_DIR, ".next");

const MARKER_URL = "https://qa-test-marker-url.supabase.co";
const MARKER_ANON_KEY = "qa-test-marker-anon-key-do-not-treat-as-real";

let buildFailed: string | null = null;

before(() => {
  try {
    execFileSync("npx", ["next", "build"], {
      cwd: PORTAL_DIR,
      env: {
        ...process.env,
        NEXT_PUBLIC_SUPABASE_URL: MARKER_URL,
        NEXT_PUBLIC_SUPABASE_ANON_KEY: MARKER_ANON_KEY,
      },
      encoding: "utf8",
      timeout: 180_000,
    });
  } catch (e: unknown) {
    buildFailed = e instanceof Error ? e.message : String(e);
  }
});

after(() => {
  // Don't leave a build artifact behind — .next/ is gitignored but this
  // wasn't here before this test file ran.
  if (existsSync(NEXT_DIR)) rmSync(NEXT_DIR, { recursive: true, force: true });
});

function walkFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkFiles(full));
    else out.push(full);
  }
  return out;
}

test("next build succeeds with the two documented NEXT_PUBLIC_* env vars set", () => {
  assert.equal(buildFailed, null, `next build failed: ${buildFailed}`);
  assert.ok(existsSync(NEXT_DIR), ".next output directory was not produced");
});

test("built client bundle contains the literal env values (proves static inlining, not undefined) — regression test for commit 6895db0's fix", () => {
  assert.equal(buildFailed, null, "skipped: build did not succeed");
  const staticDir = path.join(NEXT_DIR, "static");
  assert.ok(existsSync(staticDir), "no .next/static directory produced");
  const files = walkFiles(staticDir).filter((f) => f.endsWith(".js"));
  const urlHits = files.filter((f) => readFileSync(f, "utf8").includes(MARKER_URL));
  const keyHits = files.filter((f) => readFileSync(f, "utf8").includes(MARKER_ANON_KEY));
  assert.ok(
    urlHits.length > 0,
    "NEXT_PUBLIC_SUPABASE_URL marker value not found anywhere in the built client bundle — " +
      "would indicate the dynamic process.env[name] regression is back (undefined at build time)"
  );
  assert.ok(
    keyHits.length > 0,
    "NEXT_PUBLIC_SUPABASE_ANON_KEY marker value not found anywhere in the built client bundle"
  );
});

test("no client-side source maps are emitted in production (would otherwise re-expose original source unnecessarily)", () => {
  assert.equal(buildFailed, null, "skipped: build did not succeed");
  const staticDir = path.join(NEXT_DIR, "static");
  const maps = walkFiles(staticDir).filter((f) => f.endsWith(".map"));
  assert.deepEqual(maps, []);
});

// --- INC-7 (FR31 track-record view): confirms the real build actually produces the route ---
test("INC-7: /track-record is listed in the real build's routes-manifest.json", () => {
  assert.equal(buildFailed, null, "skipped: build did not succeed");
  const routesManifestPath = path.join(NEXT_DIR, "routes-manifest.json");
  assert.ok(existsSync(routesManifestPath), "routes-manifest.json not produced");
  const manifest = JSON.parse(readFileSync(routesManifestPath, "utf8"));
  const staticRoutes: string[] = (manifest.staticRoutes ?? []).map((r: { page: string }) => r.page);
  assert.ok(
    staticRoutes.includes("/track-record"),
    `/track-record not found in routes-manifest.json staticRoutes: ${JSON.stringify(staticRoutes)}`
  );
});

test("INC-7: /track-record is statically prerendered in the real build output (server/app/track-record.html exists)", () => {
  assert.equal(buildFailed, null, "skipped: build did not succeed");
  const prerendered = path.join(NEXT_DIR, "server", "app", "track-record.html");
  assert.ok(existsSync(prerendered), "prerendered track-record.html not found in build output");
});

test("no service_role/secret-looking string appears anywhere in the built output (server or client)", () => {
  assert.equal(buildFailed, null, "skipped: build did not succeed");
  const allFiles = walkFiles(NEXT_DIR).filter((f) => f.endsWith(".js") && !f.includes(`${path.sep}node_modules${path.sep}`));
  const offenders: string[] = [];
  for (const f of allFiles) {
    const content = readFileSync(f, "utf8");
    if (/service_role|SUPABASE_SERVICE|GEMINI_API_KEY|GITHUB_TOKEN/.test(content)) {
      offenders.push(f);
    }
  }
  assert.deepEqual(
    offenders.map((f) => path.relative(NEXT_DIR, f)),
    [],
    "secret-looking string found in built output outside node_modules"
  );
});
