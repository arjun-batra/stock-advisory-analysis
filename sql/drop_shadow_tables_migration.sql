-- Retirement of the shadow verdict pilots (US/CA + NSE); see the "Retired:
-- shadow-pilot tracks" note in design.md.
-- Covers FR24-FR31/NFR5 and FR32-FR39/NFR6, retired 2026-07-16. Drops the two
-- shadow call-log tables; nothing else in the schema depends on them.
DROP TABLE IF EXISTS call_log_shadow;
DROP TABLE IF EXISTS call_log_shadow_nse;
