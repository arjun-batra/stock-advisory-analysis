# Requirements Changelog Archive

Older changelog entries moved out of `docs/requirements.md` to keep that file's live changelog capped at
the 10 most recent entries (per CLAUDE.md document-hygiene rule). Entries are appended here in the order
they were archived; each keeps its original date and text unchanged.

| Date | Change | Reason |
|---|---|---|
| 2026-07-12 | **Adoption-pass port.** Created `docs/requirements.md` by porting FR1–FR23 / NFR1–NFR4, the Problem/Goals/Scope sections, and the full Decisions Log (#1–#18) verbatim (lightly reformatted, no meaning changes) from `requirements_docs/stock-advisory-agent-requirements.md` (v5). Original v5 doc retained untouched in `requirements_docs/` as historical record. Added a Configuration section (§11 at the time) as the reviewer hardcoding-audit baseline, populated from `scripts/config.py` and SD.md. | Multi-agent-template adoption: port current source-of-truth docs into the new `docs/` locations without altering meaning. |
| 2026-07-12 | Added an Experimental Tracks section (§10) documenting a previously-undocumented shadow wallet pilot (FR24–FR31, NFR5), explicitly outside core v1 scope. Retired and removed outright 2026-07-16 — see requirements.md changelog and git history. | Documenting shipped-but-undocumented code as explicit requirements; superseded by later retirement. |
| 2026-07-12 | **Synced §11 audit baseline with 6 newly-extracted tunables.** Added `YF_HISTORY_RETRIES` (`2`), `YF_HISTORY_PERIOD` (`3mo`), `HEADLINES_LIMIT` (`5`), `NOTIF_BODY_MAX` (`150`), `RATIONALE_MAX` (`280`) to the Core system table and `DISCOVERY_EARNINGS_RECENT_DAYS` (`2`) to the Discovery prefilter table. Each default equals the literal it replaced (no behavior change from these keys). Baseline-only sync; no new/changed FR/NFR. | Dev's debt-cleanup pass moved these previously-hardcoded literals into `scripts/config.py` as env-overridable tunables, resolving reviewer findings REV-007–REV-012; the hardcoding-audit baseline table must list every tunable. |
