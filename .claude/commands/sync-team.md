---
description: "Sync this repo's workflow files from the delivery-team-template. Usage: /sync-team"
---

You are the Orchestrator. Update THIS repo's workflow files from the upstream template, leaving project content untouched.

## 1. Fetch the template
Clone shallow to a temp dir: `git clone --depth 1 https://github.com/arjun-batra/delivery-team-template /tmp/delivery-team-template-sync` (use `gh repo clone` if plain git auth fails).

## 2. Overwrite workflow files only
Copy from the temp clone into this repo, overwriting: `.claude/agents/`, `.claude/commands/`, `.claude/settings.json`, `CLAUDE.md`, `.claudeignore`, `.github/workflows/audit.yml`.
NEVER touch `README.md`, `docs/`, `src/`, `tests/` — those are this project's own content, not template scaffolding.

## 3. Report the version jump
- Read the new version from the temp clone's `VERSION` file (call it Y).
- Read this repo's previously recorded version from `.claude/template-version` (call it X). If the file doesn't exist, treat X as "unknown" (pre-versioning sync).
- Write `Y` to `.claude/template-version` (create the file if missing).
- Report "synced from vX -> vY", then list the temp clone's `CHANGELOG.md` entries newer than vX (all entries if X was unknown).

## 4. Clean up and commit
Delete the temp clone. Commit: "Sync delivery workflow from template (vX -> vY)".

## 5. Tell the user
A session restart may be needed to load changed agents/commands.
