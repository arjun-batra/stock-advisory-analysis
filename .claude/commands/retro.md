---
description: "Mine project artifacts for delivery friction and propose template edits. Runs at Phase 4 closure or on demand. Usage: /retro"
---

You are the Orchestrator. Run a retrospective on THIS project's delivery process — not a feature review. Mine existing artifacts for friction; do NOT interview the user first. Bring findings, then discuss.

## 1. Mine the artifacts
- `docs/test-report.md` (+ archive): fix cycles per increment. More than 1 fix cycle = why? Design gap, weak/ambiguous acceptance criteria, or dev quality issue?
- `docs/review-log.md` (+ archive): which finding tags (`[HARDCODED]`, `[BLOAT]`, `[STRUCTURE]`, etc.) recurred across increments? Recurrence means a write-time rule is missing or unclear, not that agents are careless.
- `docs/handoff.md` + `git log`: increments whose implementation deviated from the design or increment plan.
- Gates (1-3 + closure): did any gate pass without catching anything, project-wide? Did the user override or push back on the same kind of decision more than once?
- Token/effort: which phase (discovery, requirements, design, a specific increment) consumed the most sessions/turns relative to the value delivered?

## 2. Write docs/retro.md
3-5 findings max, each evidence-linked (cite the doc/log entry or commit). For each finding, include one of:
- **PROPOSED TEMPLATE EDIT** — the exact file and rule change in the `delivery-team-template` repo that would prevent recurrence, or
- **"project-specific, no template change"** if the friction is unique to this project.

## 3. Discuss with the user
Present the findings and proposed edits. The user approves which proposals to apply — do not apply any unapproved.

## 4. Apply approved template edits
For each approved proposal:
1. Clone the template shallow: `git clone --depth 1 https://github.com/arjun-batra/delivery-team-template /tmp/delivery-team-template-retro`.
2. Apply the edit in the clone.
3. Bump `VERSION` and add a `CHANGELOG.md` entry (1-3 lines) — no silent template edits, per the template's own versioning rule.
4. Commit and push the clone directly (or hand the diff to the user if you lack push access).
5. Delete the temp clone.
6. Remind the user: bump the template version was just done — they still need to run `/sync-team` in this and any other active repos to pull the change.
