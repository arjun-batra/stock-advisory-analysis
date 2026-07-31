-- =====================================================================
-- ALERTS_ENABLED seed-description correction (DEEP-005, INC-10; repackaged REV-112, INC-10 fix round #2)
-- =====================================================================
-- Design: docs/design/admin-portal-tunables.md §16.4 ("Effective-value visibility" paragraph).
-- Depends on sql/admin_portal_tunables.sql (INC-6, already live: `tunables` table, seeded rows) already
-- existing -- this file is strictly additive on top of it: it does not redefine the table, any trigger,
-- or either RLS policy, and touches no row other than the one named below.
--
-- ALERTS_ENABLED's effective value is `_alerts_input AND ALERTS_ENABLED_TABLE` (scripts/config.py), but
-- this row's description (as originally seeded by INC-6) only ever described the table half, under the
-- label "Master switch for real pushes" -- nothing told an operator whether pushes were actually live.
-- sql/admin_portal_tunables.sql's own seed INSERT already carries the corrected text for a fresh deploy;
-- this UPDATE brings an already-live project's existing row in sync, since that INSERT cannot re-run
-- against a row that already exists (primary-key conflict).
--
-- REV-112: this correction previously lived as a trailing `update` appended to admin_portal_tunables.sql
-- -- an already-applied, non-re-runnable migration file (docs/runbook.md §2.3, "Deployed as part of
-- INC-6") that a release engineer would not re-run, so the correction would very likely never actually
-- reach the live project. Moved here, as its own additive, idempotent, re-runnable file, matching
-- BUG-008's convention and the two other new INC-10 files (tunables_validate_trigger.sql,
-- holdings_currency_derivation.sql). Safe to apply any number of times: scoped to one column, one
-- `where key = 'ALERTS_ENABLED'`.
--
-- APPLIED AND LIVE (2026-07-30, applied and confirmed directly against production, project
-- ikghqdtlbwifwnooytmm, Postgres 17.6.1): the live ALERTS_ENABLED row's description is corrected to
-- this file's text. This file's header previously read "Not applied live by dev" (REV-125) -- stale
-- once release applied it; the SQL below went live and was simply never updated afterward.

update public.tunables
   set description = 'Master switch for real pushes. Effective value is this AND the workflow''s alerts_enabled input -- that input defaults to true on every scheduled run and is false only during a deliberate manual dry-run test, so this table value is the one that actually matters day-to-day.'
 where key = 'ALERTS_ENABLED';
