# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AutoRaider is a Windows desktop-automation bot for the game "Raid: Shadow Legends". It finds game UI elements by image-template matching (pyautogui/pyscreeze at confidence 0.8) and clicks/swipes them, with a CustomTkinter GUI and a scheduler. The game window is resized to 900×600 at (500, 200).

The developer environment constraint is load-bearing: **the engine must be developed and tested with no game and no Windows.** The whole v2 test suite runs cross-platform against fakes.

## Commands

Tests and validation run anywhere (no game required):

```
venv/Scripts/python.exe -m pytest                          # full suite (99 passed, 3 skipped)
venv/Scripts/python.exe -m pytest -k arena_config          # filter by name
venv/Scripts/python.exe -m pytest tests/test_arena_config.py::test_arena_fights_until_tokens_run_out
venv/Scripts/python.exe -m engine.validate configs/arena_v2.yaml   # schema + assets + reachability
```

Windows + game required (live, do not run in CI/tests):

```
python main.py                          # launch the GUI app
python -m engine.run configs/arena_v2.yaml   # run one v2 sequence headless from the CLI
python -m hitl                          # HITL repair tool (re-crop config targets without editing Python)
```

Python 3.14 venv at `venv/`. `requirements.txt` (Windows deps, incl. pywin32) and `requirements-dev.txt` (cross-platform subset) — engine work needs neither pywin32 nor pyautogui.

## Two generations coexist

- **v1 (legacy, frozen):** imperative Python command classes in `Modules/`. Each hardcodes its navigation via `ClickHandler`. `ClassicArenaCommand` (`Modules/arena/DailyTenArenaCommand.py`) is the reference behaviour. Registered in `CommandFactory`, surfaced as Tasks-tab checkboxes, schedulable.
- **v2 (declarative engine, under migration):** game flows are YAML action graphs in `configs/*_v2.yaml`, walked by a "dumb runner" in `engine/`. v2 commands appear only on the V2 Engine tab and **cannot be scheduled**.

The epic guardrails (`docs/epic_v2/Epic_AutoRaider_v2.md`) say: during v2 work do not fix or modify the v1 modules, GUI, or scheduler — v2 runs **alongside** v1, not through it. Phase 4 (migration) is in progress; v2 commands are registered beside v1 rather than replacing them.

## The v2 engine

Data flow:

```
YAML -> pydantic (SequenceConfig) -> SequenceRunner -> ScreenActions protocol -> ClickHandler (real)
                                                                      |-> FakeScreen / ScreenshotScreen (tests)
```

The **`ScreenActions` protocol** (`engine/screen.py`) is the whole point of the design — it is the seam between the engine and the real world. `ClickHandler` (`utils/click_handler.py`) satisfies it structurally; tests use `FakeScreen` and `ScreenshotScreen`. This is what lets a developer with no game build and test the engine.

Graph semantics (`engine/models.py`, `engine/runner.py`):

- Each node is one action: `CLICK_IMAGE`, `WAIT_FOR_IMAGE`, `WAIT_UNTIL_DISAPPEARS`, `IMAGE_PRESENT`, `PRESS_KEY`, `SWIPE`, `CLICK_POINT`.
- Edges are `on_success` / `on_failure` pointing at other node keys. **A null edge ends the run**: `COMPLETED` on null `on_success`, `ABORTED` on null `on_failure`. Omit an edge where a failure means the bot is lost.
- **Loops are cycles in the graph, never counters.** No variables, expressions, or loop constructs in the YAML. `arena_v2.yaml` fights until tokens run out; the only clean exit is the `ArenaRefillGems.png` guard. A cycle that never exits hits `max_steps=200` and ends `STEP_LIMIT` with a crash dump instead of spinning forever.
- Image-action targets are **bare filenames** resolved against `assets/`. ClickHandler prepends the assets dir itself — a path-prefixed target becomes `assets/assets/...` and never matches. Asset names are compared case-sensitively.
- `ignore_visited` / `clear_visited` give `CLICK_IMAGE` the v1 "click each of several matching buttons" behaviour via multi-match selection (`match`: best / top / bottom) and a visited-points list.

Failure handling (`engine/run.py::run_sequence`): on a non-COMPLETED outcome it writes a crash dump (screenshot + JSON context) to `logs/dumps/`, **then** recovers (ESC back to bastion + close popups). The dump-before-recover ordering is load-bearing — recovery changes the screen. `logs/` is gitignored, so dumps never reach the repo on their own.

Cancellation: `CancellationToken` (`utils/cancellation.py`) is a thread-safe Event with interruptible `sleep()`. The GUI / F2 sets `cancel_flag` on the shared ClickHandler. `CancellationException` must propagate through the runner — if the runner catches it as a node failure, the cancel button silently stops working.

Cross-platform rule (load-bearing): `engine/` must stay importable on macOS with no game — no pyautogui, no pygetwindow, no `app` imports at module scope. `engine/run.py` imports those lazily inside `main()`; its `run_sequence()` / `screen_grabber()` are the shared, cross-platform core. The engine test suite must pass anywhere: `python -m pytest`.

## Testing strategy

- `tests/fakes.py` — `FakeScreen` (scripted per-image-name results queue, call recording) and `FakeClickHandler` (adds `region`, `back_to_bastion`, `delete_popup` for `SequenceCommand` tests). Test doubles must implement the full `ScreenActions` protocol.
- `tests/screenshot_screen.py` — `ScreenshotScreen` replays real captures from `tests/screenshots/*.png` (must be exactly 900×600) through the same pyscreeze matcher at confidence 0.8 the live bot uses. A matched click / swipe / keypress advances the frame; `wait_for_image` polls forward but does not advance past a match.
- `tests/test_assets_match.py` — every image target must match at least one delivered screenshot. Targets whose captures haven't been delivered are named loudly in `BLOCKED_BY_MISSING_CAPTURE` and skipped; do not silently drop them.

## Config layout

- `configs/*_v2.yaml` — one action graph per game mode (validated by `engine.validate`).
- `configs/rewards/` and `configs/daily_quests/` — lists of small subflow configs run best-effort: a failure dumps and the next subflow still starts (`SequenceCommand.bind` with a list sets `stop_on_failure=False`).
- `config.ini` — task checkboxes, presets (`SelectionItems`), and `[Schedules]` (name → preset on a timer). `[V2 Tasks]` holds v2 checkboxes; it is deliberately **not** a `SelectionItems` preset, which is what keeps v2 tasks off the scheduler.
- To add a v2 command: define the YAML, register its config path in `engine/sequence_command.py`, and bind it to a `CommandKeys` entry in `app/pyAutoRaid.py` via `SequenceCommand.bind(...)`. The V2 tab discovers v2 commands by `is_sequence_command()` on the registry.

## Current state (`docs/epic_v2/`)

The epic docs (`Epic_AutoRaider_v2.md`, `Ticket_1..5`, `Windows_Live_Runbook.md`) are the source of truth for phase status, screenshots still needed, and what is gated on a live run. Phases 1–3 shipped; Phase 4 (migration to v2) is in progress with a supervised loop run still outstanding. Do not "fix" `back_to_bastion()`'s unbounded ESC loop — that is deliberately carved out as Ticket 5.


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->
