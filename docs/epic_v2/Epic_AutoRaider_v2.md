# Epic: AutoRaider v2 - Declarative Architecture & HITL Engine

## 🎯 Objective
Transition AutoRaider from imperative, hardcoded Python scripts to a configuration-driven state machine. We will build a "dumb runner" that executes YAML files, and eventually, a Human-In-The-Loop (HITL) UI to fix broken automation without touching the Python codebase.

## 🛑 Guardrails & Core Principles (READ FIRST)
As you work on this Epic, adhere strictly to the following rules:

- **DO NOT fix the old modules**: Ignore Clan Boss, Dungeons, Faction Wars, etc. We are abandoning the old Python logic. We are ONLY using the working Arena logic as our baseline to prove the new engine works.
- **NO Game Logic in Python**: The new Python runner should not know what "Arena" or "Raid" is. It should only know how to read a YAML node (e.g., "CLICK"), execute it via our ClickHandler, and move to the next node. Do not write `if game_state == 'arena'` in the core engine.
- **Mandatory Libraries**:
  - Use `pydantic` for validating the YAML configuration on startup.
  - Use `ruamel.yaml` for modifying YAML files (do NOT use the standard yaml library, as it deletes comments and formatting when writing to files).
- **The "Inner-Platform" Trap**: Do not add complex math, variables, or counters to the YAML. Keep the YAML simple: Actions, Targets, and State Transitions (`on_success`, `on_failure`).

## 🏗️ The Mental Model (How it works)

**Currently, the bot does this:**
`Python Code -> Hardcoded Image Search -> Click -> Hardcoded Wait -> ...`

**In v2, the bot will do this:**
`YAML File -> Pydantic Validation -> Dumb Python Engine -> Click/Wait -> Next YAML Node`

## 📅 Roadmap Overview
- [Ticket 1: Phase 1 - The Engine & The Arena Staging Ground](./Ticket_1_Phase1_Engine_Arena.md)
- [Ticket 2: Phase 2 - Telemetry & Crash Dumps](./Ticket_2_Phase2_Telemetry.md)
- [Ticket 3: Phase 3 - Human-In-The-Loop (HITL) Authoring UI](./Ticket_3_Phase3_HITL.md)
- [Ticket 4: Phase 4 - Migration & Deprecation](./Ticket_4_Phase4_Migration.md)
