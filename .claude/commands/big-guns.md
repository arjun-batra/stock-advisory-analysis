---
description: "Invoke the big-guns deep analysis on demand. Usage: /big-guns [optional focus area]"
---

Optional focus area: $ARGUMENTS

Before proceeding, remind the user to run THIS main session on the highest model available in their tier — `big-guns` runs with `model: inherit`, so its analysis quality is capped by the orchestrator's own model.

Then invoke the `big-guns` subagent, passing the optional focus area ("$ARGUMENTS") if given. It reads idea-brief.md, requirements.md, design.md, code-map.md, and code, and appends `[DEEP]`-tagged findings to `docs/review-log.md`.

When it returns:
1. Present the findings summary and the overall assessment verbatim.
2. Route any blockers/majors to the owning agent per CLAUDE.md's normal triage flow — do not fix anything in the main thread.

Good moments to run this: after design approval on complex projects, before closure on anything handling money or advice, or when an increment exceeds 3 fix cycles.
