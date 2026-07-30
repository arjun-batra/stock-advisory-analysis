-- =====================================================================
-- Tunables write-time validation (FR30 sharpened, Decision #34) — INC-10
-- =====================================================================
-- Design: docs/design/admin-portal-tunables.md §16.4 ("FIX ROUND (DEEP-005, INC-10)").
-- Depends on sql/admin_portal_tunables.sql (INC-6, already live: `tunables` table, key-registry CHECK,
-- `_stamp_tunable_update()` trigger, `admin_read_tunables`/`admin_write_tunables` policies) already
-- existing — this file is strictly additive on top of it: it does NOT redefine the table, the stamp
-- trigger, or either RLS policy.
--
-- DEEP-005: the portal/DB validated only non-emptiness, and three of the ten curated keys'
-- scripts/config.py casts can never raise (`str` for GEMINI_MODEL/_BACKUP, the hand-rolled
-- `lambda v: str(v).lower() == "true"` for ALERTS_ENABLED) — so a typo silently changed system
-- behaviour (e.g. ALERTS_ENABLED="tru" -> False, all real pushes go dark, no error, no monitor signal)
-- while a typo in any of the seven numeric keys instead took down every scheduled entry point at once
-- via SystemExit at import time. This trigger mirrors scripts/config.py's exact per-key cast/domain
-- contract (`_TUNABLE_CASTS`) so a bad value is rejected here BEFORE it is ever written — a direct SQL
-- edit is caught exactly like a portal edit (admin-portal/lib/validation.ts's client-side mirror of
-- the same ten rules is the first line of defense, not the only one).
--
-- Trigger-ordering note: named `tunables_0_validate_update` (not `tunables_1_validate` as the design
-- doc's illustrative name suggested) specifically so it is NOT a rename of the already-live
-- `tunables_stamp_update` trigger (sql/admin_portal_tunables.sql) — Postgres fires same-event BEFORE
-- triggers in `tgname` alphabetical order, and '0' sorts before 's', so `tunables_0_validate_update`
-- already fires strictly before `tunables_stamp_update` without touching that trigger at all. This
-- keeps the fix purely additive per the live-project caution for this round (renaming/dropping an
-- already-applied trigger is exactly the "redefine an existing object" risk being avoided) while still
-- satisfying INC-10 AC4: a rejected update never reaches the stamp trigger, so `updated_at`/`updated_by`
-- are never touched on a failed write. Verify via
-- `select tgname from pg_trigger where tgrelid = 'public.tunables'::regclass order by tgname`.
--
-- Not applied live by dev — release/INC-11 applies this against the live project per the orchestrator's
-- explicit instruction for this increment (this is new validation logic on a live table other
-- surfaces already write to; application needs the user's involvement, not a code-review-time apply).

create or replace function public._validate_tunable_update() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Mirrors scripts/config.py's _TUNABLE_CASTS exactly, one rule per curated key — ten keys, ten
  -- rules, no framework (docs/design/admin-portal-tunables.md §16.4). The table's own key-registry
  -- CHECK (sql/admin_portal_tunables.sql) already restricts `key` to these ten, so the ELSE branch
  -- below is unreachable today; it exists only so a future key added to that CHECK can't silently
  -- skip validation here.
  case new.key
    when 'DISCOVERY_GAINER_PCT', 'DISCOVERY_LOSER_PCT', 'DISCOVERY_VOL_SPIKE',
         'DISCOVERY_MIN_MARKET_CAP', 'DISCOVERY_MIN_MARKET_CAP_INR' then
      -- mirrors float(): optional sign, digits, optional decimal part
      if new.value !~ '^-?[0-9]+(\.[0-9]+)?$' then
        raise exception 'tunables.value for key % must be numeric (e.g. "5" or "2.0"), got %',
          new.key, new.value;
      end if;
    when 'DISCOVERY_SHORTLIST_MAX', 'DISCOVERY_PUSH_COOLDOWN_DAYS' then
      -- mirrors int(): optional sign, digits only, no decimal point
      if new.value !~ '^-?[0-9]+$' then
        raise exception 'tunables.value for key % must be an integer (e.g. "15"), got %',
          new.key, new.value;
      end if;
    when 'ALERTS_ENABLED' then
      -- mirrors `lambda v: str(v).lower() == "true"` made unambiguous: only "true"/"false" (any
      -- case) are accepted — anything else, which config.py's cast would otherwise silently coerce
      -- to False, is rejected here instead of ever reaching that cast.
      if lower(new.value) not in ('true', 'false') then
        raise exception 'tunables.value for key % must be exactly "true" or "false" (case-insensitive), got %',
          new.key, new.value;
      end if;
    when 'GEMINI_MODEL' then
      -- str() can't fail, but a blank primary model is still nonsensical — config.py has no
      -- fallback for GEMINI_MODEL itself.
      if btrim(new.value) = '' then
        raise exception 'tunables.value for key % must not be blank', new.key;
      end if;
    when 'GEMINI_MODEL_BACKUP' then
      -- Deliberately NO check: blank is how an operator disables the fallback model (config.py's
      -- own documented behavior, scripts/config.py's GEMINI_MODEL_BACKUP comment) — rejecting blank
      -- here would make that supported state impossible to write, which was itself part of DEEP-005's
      -- finding (admin-portal-tunables.md §16.4).
      null;
    else
      raise exception 'tunables key % has no known validation rule — add one to _validate_tunable_update() before allowing writes to it',
        new.key;
  end case;
  return new;
end; $$;

create trigger tunables_0_validate_update
  before update on public.tunables
  for each row execute function public._validate_tunable_update();
