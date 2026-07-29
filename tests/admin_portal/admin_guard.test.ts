// Tests admin-portal/lib/admin-guard.ts's checkAuthorization() — the portal-UI
// allowlist gate behind AC2/AC3 (docs/design/increment-plan.md INC-5 ACs 2-3;
// docs/design/admin-portal.md §16.2 "Defense in depth" layer 2). This is
// explicitly the UX layer, NOT the security boundary (RLS/is_admin() at the
// DB layer is, per the design doc) — these tests lock down the UI-gate
// contract with a fake Supabase client; they do not and cannot substitute for
// AC2's live "devtools network tab shows no successful query" check or AC5's
// live RLS rejection (see docs/test-report.md INC-5 entry for what those
// relied on instead — this QA session has no live Supabase network access,
// org egress policy blocked it, see report).
//
// Run: node --experimental-strip-types --test tests/admin_portal/admin_guard.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { checkAuthorization } from "../../admin-portal/lib/admin-guard.ts";

interface FakeClientOpts {
  session: { user: { email: string } } | null;
  isAdmin?: boolean;
  rpcError?: unknown;
}

function makeFakeClient(opts: FakeClientOpts) {
  let signedOut = false;
  const client = {
    auth: {
      getSession: async () => ({ data: { session: opts.session } }),
      signOut: async () => {
        signedOut = true;
      },
    },
    rpc: async (name: string) => {
      assert.equal(name, "is_admin", "checkAuthorization must call the is_admin() RPC, not query admin_allowlist directly");
      return { data: opts.isAdmin ?? false, error: opts.rpcError ?? null };
    },
  };
  return { client, wasSignedOut: () => signedOut };
}

// --- happy path: allowlisted account -------------------------------------
test("checkAuthorization: allowlisted account (is_admin=true) -> authorized, not signed out", async () => {
  const { client, wasSignedOut } = makeFakeClient({
    session: { user: { email: "avbatra@outlook.com" } },
    isAdmin: true,
  });
  const result = await checkAuthorization(client as never);
  assert.deepEqual(result, { status: "authorized", email: "avbatra@outlook.com" });
  assert.equal(wasSignedOut(), false);
});

// --- edge case: no session at all (logged-out visit, AC1) ----------------
test("checkAuthorization: no session -> unauthenticated (no RPC call needed to know this)", async () => {
  const { client } = makeFakeClient({ session: null });
  const result = await checkAuthorization(client as never);
  assert.deepEqual(result, { status: "unauthenticated" });
});

// --- invalid/rejected input: non-allowlisted account (AC2) ---------------
test("checkAuthorization: signed-in but non-allowlisted account -> unauthorized AND signed out immediately", async () => {
  const { client, wasSignedOut } = makeFakeClient({
    session: { user: { email: "not-arjun@gmail.com" } },
    isAdmin: false,
  });
  const result = await checkAuthorization(client as never);
  assert.deepEqual(result, { status: "unauthorized", email: "not-arjun@gmail.com" });
  assert.equal(wasSignedOut(), true, "AC2 requires the non-allowlisted session be signed out immediately");
});

test("checkAuthorization: is_admin() RPC error -> treated as unauthorized (fails closed, not open)", async () => {
  const { client, wasSignedOut } = makeFakeClient({
    session: { user: { email: "avbatra@outlook.com" } },
    isAdmin: undefined,
    rpcError: new Error("network error"),
  });
  const result = await checkAuthorization(client as never);
  assert.equal(result.status, "unauthorized");
  assert.equal(wasSignedOut(), true);
});

test("checkAuthorization: session with no email -> falls back to empty string, still gated by is_admin()", async () => {
  const { client } = makeFakeClient({
    session: { user: { email: undefined as unknown as string } },
    isAdmin: false,
  });
  const result = await checkAuthorization(client as never);
  assert.equal(result.status, "unauthorized");
  assert.equal((result as { email: string }).email, "");
});
