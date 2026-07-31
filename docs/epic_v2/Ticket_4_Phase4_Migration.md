# Phase 4: Migration & Deprecation

**Goal**: Move the rest of the app to v2.

## PR 4.1: Drafting

- Write "best guess" YAML files for Clan Boss, Doom Tower, etc., based on the old broken code.

## PR 4.2: HITL Remediation

- Run them. They will fail. Use the new Phase 3 UI tool to visually fix their image targets until they run smoothly.

## PR 4.3: Cleanup

- Delete the entire `Modules/` directory containing the v1 Python logic.
