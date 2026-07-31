# Test Report — Latest Run

**Owner:** qa. Older run entries moved to `docs/archive/test-report-archive.md` per doc-hygiene rule — this
file holds only the latest run and open bugs.

---

## Live-execution verification checklist — track-record view — 2026-07-31

**Scope.** `docs/requirements.md`'s "FR31, FR32 — Deferred, pending live execution" section (Decision #36)
live-execution verification checklist, step 3: "confirm the track-record table shows real data" against
the real deployed admin portal (`admin-portal/app/(app)/track-record/page.tsx`, FR31,
`docs/design/admin-portal.md` §16.5), signed in as an admin via Google OAuth against the live Supabase
project (`ikghqdtlbwifwnooytmm`).

### Result: FAIL — filed as BUG-009

Step 3 fails: the signed-in admin sees an empty track-record table, no error message. Root cause isolated
via direct SQL against the live project (not a code read) — see BUG-009 below. Filed to Open bugs, handed
to dev; not fixed by qa.

### Verdict

**FAIL** on live-execution checklist step 3. No other checklist steps re-run this pass (scope was this one
failing step and its root cause). No production code touched by qa. 1 bug filed (BUG-009).

---

## Open bugs

**BUG-009 — Admin portal track-record view shows an empty table for every signed-in admin, no error
(FR31, `docs/design/admin-portal.md` §16.5) — critical, blocks live-execution checklist step 3.**

**Discovered via:** `docs/requirements.md`'s live-execution verification checklist (Decision #36, "FR31,
FR32 — Deferred, pending live execution"), step 3 ("confirm the track-record table shows real data")
failed against the live deployed portal.

**Repro (either):**
1. Sign in to the admin portal via Google OAuth, visit `/track-record` — table renders empty, no error
   shown.
2. Or, against Supabase project `ikghqdtlbwifwnooytmm` directly: confirm `public.call_log` has 8,890 rows
   (7,825 in the last 30 days — data is present, not missing); confirm `call_log`'s only RLS SELECT policy
   is `"anon read call_log"`, scoped `TO anon`, `USING (true)`; query `pg_auth_members` and confirm
   `authenticated` is NOT a member of `anon`.

**Root cause:** `admin-portal/lib/supabase-client.ts` is a browser client carrying the signed-in user's
session, so every portal query after Google OAuth login runs as Postgres role `authenticated`, not `anon`.
`call_log`'s sole SELECT policy is scoped `TO anon` only, so it does not apply to `authenticated` sessions
— RLS silently returns zero rows (not an error, since RLS filtering isn't an error condition). Contrast:
`watchlist`/`holdings` don't show this symptom because each has an `admin_write_<table>` policy scoped
`TO authenticated` with `cmd: ALL`, and `ALL` implicitly covers `SELECT` too, so authenticated admins get
read access as a side effect of the write policy. `call_log` is read-only from the portal's side, so it
never got an equivalent policy — §16.5's design assumed the existing anon policy was sufficient without
accounting for the portal caller running as `authenticated` once logged in.

**Expected vs. actual:** Expected — signed-in admin sees the real `call_log` data (8,890 rows /
7,825 last-30-days) in the track-record table. Actual — empty table, no error, for every signed-in admin.

**Expected fix direction:** add an additional RLS SELECT policy on `public.call_log` scoped `TO
authenticated` (mirroring the existing `"anon read call_log"` policy's `USING (true)`), analogous to how
`watchlist`/`holdings` already grant authenticated read access via their `ALL`-scoped write policies. No
code change needed in `admin-portal/`; SQL-only fix in `sql/` (owner: dev, per file-ownership table — qa
does not fix production code/schema).

**Owner:** dev.

---

**BUG-007 — `_parse_batch`'s duplicate-requested-ticker resolution is silently last-write-wins when both
occurrences resolve legitimately (`ok`) to DIFFERENT verdicts — minor, deferred by design — INC-9, BUG-006
fix-cycle-2 residual, filed for the record, not currently blocking.** Unchanged this pass — the C901
refactor is a verbatim move and does not touch this residual's last-write-wins behavior in `_store_result`.
Full detail: `docs/archive/test-report-archive.md`'s INC-9 BUG-006 fix-cycle-2 entry (repro:
`tests/test_ai_judge.py::test_parse_batch_duplicate_ticker_divergent_ok_verdicts_last_write_wins_undocumented_elsewhere`).
**Owner:** tech-lead (design-level call on `_parse_batch`'s ticker-keyed return contract, if ever
addressed).
