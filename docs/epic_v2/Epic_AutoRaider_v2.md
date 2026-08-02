# Epic: AutoRaider v2 — Declarative Engine & HITL Authoring

## Objective

Replace imperative, hardcoded Python bot logic with a configuration-driven state machine. Build a "dumb runner" that walks a YAML graph, and later a Human-In-The-Loop (HITL) UI that repairs broken automation by re-cropping image targets instead of editing Python.

## Scope discipline (read this before planning any work)

This epic is deliberately staged. **Phase 1 is a thin vertical slice: one Arena battle, end to end, driven by YAML.** Nothing else.

Do not build a generic workflow platform. Do not add features to the YAML schema because a future module "might need them". Every action type and every schema field must be justified by a node that exists in `configs/arena_v2.yaml` today. If a phase can ship with fewer moving parts, ship the smaller version.

## Working conditions for the assigned developer

**The developer implementing this epic does not have access to the game.** They cannot run RAID: Shadow Legends, cannot see the live screen, and cannot verify image matching interactively. The Windows-only host app (`app/pyAutoRaid.py`) calls `sys.exit(1)` on non-Windows platforms.

This constrains the architecture, and the constraint is load-bearing:

- **The engine must never touch the screen directly.** It talks to an injected interface (see Ticket 1). The real implementation is the existing `ClickHandler`; the test implementation is a hand-written fake.
- **Every Phase 1 acceptance test must pass with no game, no emulator, and no Windows.** Pure `pytest` against the fake.
- **Anything that genuinely needs to see the game requires screenshots to be supplied first.** Those are enumerated in [Screenshots Required](./Screenshots_Required.md). Tickets that are blocked on screenshots say so explicitly at the top.
- **The developer needs a cross-platform dependency subset.** `pip install -r requirements.txt` fails outright on macOS and Linux because `pywin32` has no distribution there. See Ticket 1's *Developer environment* section — engine work needs neither `pywin32` nor `pyautogui`.

The repository currently contains **zero full-screen game captures**. `assets/` holds 170 small template crops (most under 200px, the largest is `Brutal.png` at 885×563). Template crops are enough to *feed* the matcher but not enough to *test* it — you cannot verify that `arenaBattle.png` matches an Arena screen without an Arena screen.

## Guardrails

- **Do not fix the old modules.** Clan Boss, Dungeons, Doom Tower, Faction Wars stay untouched and unused. Classic Arena is the only reference behaviour.
- **Do not modify the old modules either.** `Modules/` and the existing GUI/scheduler must keep working exactly as they do today throughout Phases 1–3. v2 runs alongside v1, not through it.
- **No game logic in the engine.** The runner knows `CLICK_IMAGE`, not "Arena". No `if sequence == "arena"` anywhere in `engine/`.
- **Two permitted changes to existing code in Phase 1**, both to `ClickHandler`: a public `is_image_present()` wrapper, and an optional game-window `region` passed to the image lookups. Both default to today's behaviour so v1 modules are unaffected. Everything else in `utils/` is read-only for this epic.
- **Mandatory libraries:** `pydantic` (v2) for schema validation, `ruamel.yaml` for *both* reading and writing YAML. Do not add PyYAML — one YAML library only, and it has to be the comment-preserving one because Phase 3 writes back to these files.
- **Avoid the inner-platform trap.** No expressions, arithmetic, variables, or counters in the YAML. Actions, targets, and two edges (`on_success`, `on_failure`). Looping comes from cycles in the graph, not from a loop construct.

## Mental model

Today:

```
Python module -> hardcoded image search -> click -> hardcoded sleep -> ...
```

v2:

```
YAML -> pydantic validation -> dumb runner -> ScreenActions interface -> ClickHandler (real) or FakeScreen (tests)
```

The `ScreenActions` seam is the whole point of the design. It is what lets a developer with no game build and test the engine.

## Conflicts in the original draft

These were found by reading the current code. Each one is resolved in the ticket noted; they are listed here so the resolutions are not re-litigated mid-implementation.

### Blocking — the original design would not have run

| # | Conflict | Reality | Resolved in |
|---|---|---|---|
| 1 | Runner pseudo-code branches on `try/except` | `ClickHandler.click_image` / `wait_for_image` return **`False`** on failure. They do not raise. `utils/exceptions.ImageNotFoundError` is defined but never raised anywhere. | Ticket 1 |
| 2 | `click_image(target, timeout=...)` | `click_image(image_name, description="", retries=1, delay=1)` — there is no `timeout` parameter. Timeout only exists on `wait_for_image` / `wait_until_disappears`. | Ticket 1 |
| 3 | `target: "assets/arena_battle_button.png"` | `ClickHandler` resolves the assets directory itself and prepends it. A path-prefixed target becomes `assets/assets/...` and never matches. Targets must be **bare filenames**. | Ticket 1 |
| 4 | Example assets don't exist | There is no `arena_battle_button.png` or `loading_screen.png`. The real files are `arenaBattle.png` and `loadingScreen.png` (case matters). | Ticket 1 |
| 5 | Action set can't express Arena | Arena needs `PRESS_KEY` (it escapes out of screens constantly) and a non-clicking presence check (the gem-refill guard). Conversely it never needs `WAIT_UNTIL_DISAPPEARS` — battle completion is detected by `tapToContinue.png` *appearing*. | Ticket 1 |
| 6 | `on_failure: "bastion_fallback"` | No such node is defined in the example and no action type could implement it. | Ticket 1 — a null edge terminates the run; the caller does cleanup |
| 7 | "No counters" vs "complete Arena battle loop" | Classic Arena fights up to 100 teams by counting. A YAML with no counters **cannot** express "fight exactly 10". | Ticket 1 — MVP is **one** battle. Repeat-until-exhausted comes free from a graph cycle; exact counts are deferred. **Settled 2026-08-01:** the owner chose until-exhausted, and the graph cycle was indeed all it took — one edge, no schema change |
| 8 | `CancellationException` | Raised by `ClickHandler` when the GUI sets `cancel_flag`. If the runner catches it as a normal failure, the F2 cancel button silently stops working. | Ticket 1 — must propagate |

### Schema and correctness

| # | Conflict | Reality | Resolved in |
|---|---|---|---|
| 9 | `on_success: Optional[str]` | In pydantic v2 this is a **required** field that merely accepts `None`. Every node would have to spell out both edges. Needs `= None`. | Ticket 1 |
| 10 | `action_type: str` | A typo like `CLIK_IMAGE` passes validation and fails at 2am mid-run. Use a `Literal` / `StrEnum`. | Ticket 1 |
| 11 | No graph validation | Nothing checks that `start_node` exists or that edges point at real nodes. This is the cheapest, highest-value validation available. | Ticket 1 |
| 12 | `timeout_seconds: int = 10` | `DEFAULT_WAIT_TIMEOUT` is 30 and `DEFAULT_WAIT_INTERVAL` is 2. Pick one default and document it. | Ticket 1 |
| 13 | Multi-target clicking | Classic Arena uses `locateAllOnScreen` to find every visible battle button and clicks each by coordinate. `CLICK_IMAGE` clicks one match. | Ticket 1 — out of MVP scope, noted as a known behaviour difference |

### Downstream phases

| # | Conflict | Reality | Resolved in |
|---|---|---|---|
| 14 | Phase 3 example cites `victory.png` at node `check_victory_screen` | `victory.png` exists on disk but is referenced by **zero** lines of Python. There is no victory or defeat detection in Arena at all. | Ticket 3 — use a real failure as the example |
| 15 | Phase 3 writes `assets/dynamic/{uuid}.png` into `target` | Same double-prefix bug as #3, and UUID filenames are unreadable in a config a human maintains. | Ticket 3 — `dynamic/<node>_<timestamp>.png` |
| 16 | Phase 4 "delete the entire `Modules/` directory" | `Modules/` is imported by `app/pyAutoRaid.py`, registered in `utils/command_factory.py`, referenced by command keys in `config.ini` presets and schedules, surfaced as GUI checkboxes, and `DailyQuests` calls `arena_battles.execute(5)` directly. Deleting it breaks the running app. | Ticket 4 — replaced with a staged, reversible cutover |
| 17 | `pydantic` / `ruamel.yaml` assumed available | Neither is in `requirements.txt`. `opencv-python` is listed but never imported. | Ticket 1 |

### Environment notes (not blocking, but know them)

- **Platform:** Windows PC client via Plarium Play, window resized to **900×600** at position **(500, 200)**. Not an emulator, no ADB.
- **Matching:** `pyautogui` / `pyscreeze` `locateOnScreen` at a hardcoded confidence of **0.8**, in absolute screen coordinates. No DPI or resolution adaptation. v1 searches the **whole desktop**; v2 scopes the search to the game window rect (Ticket 1, PR 1.2). Passing `region=` to pyscreeze still returns absolute coordinates — it adds the region offset back before yielding — so scoping needs no coordinate maths and no changes to clicking.
- **Templates are window-scale.** The largest asset, `Brutal.png`, is 885×563 — very nearly the full 900×600 window, which confirms the crops were taken from a window at that size. Several others are tiny (`loadingScreen.png` at 16×14, `useAutoSelect.png` at 17×15), which is exactly why searching the whole desktop invites false positives.
- **`utils/constants.py` claims 1920×1080 with centre (960, 540)** and swipes drag from that point. That is a desktop-centre assumption, not the game window centre — it happens to land inside the 900×600 window at (500, 200), but only by luck. Do not build on it. Region-scoping does not fix swipes; they stay as they are for now.
- **Python 3.13** locally; the code already uses 3.10+ syntax (`X | Y` unions, builtin generics).
- **No tests, no CI, no pytest config exist.** Phase 1 creates the first ones.

## Roadmap

Ship in order. Each phase must be demonstrably working before the next starts.

| Phase | Ticket | Status | Needs screenshots? |
|---|---|---|---|
| 1 | [Engine & one Arena battle](./Ticket_1_Phase1_Engine_Arena.md) | **DONE** — PRs 1.1–1.4 shipped and live-proven on the game machine | Capture 10 is now **blocking**, since the Arena config loops |
| 2 | [Telemetry & crash dumps](./Ticket_2_Phase2_Telemetry.md) | **DONE** — PRs 2.1–2.2 shipped; live failure run passed, but its dump never reached the repo | No, for the implementation. The live failed run *produced* capture 11 — it just needs sending |
| 3 | [HITL authoring UI](./Ticket_3_Phase3_HITL.md) | **DONE (offline)** — PRs 3.1–3.3 shipped; window driven on macOS, real-mouse drag still unchecked | Captures 01, 03–09 were enough. Capture 11 is a realism check |
| 4 | [Migration & deprecation](./Ticket_4_Phase4_Migration.md) | **IN PROGRESS** — PR 4.1 shipped and live-proven; Arena now loops and needs run 6; 4.2 gated, 4.3 not started | Yes, per module migrated |
| 5 | [`back_to_bastion()` attempt cap](./Ticket_5_BackToBastion_Cap.md) | **NOT STARTED** — carved out of Phase 2 so it stops being a drive-by temptation | No |

Supporting documents:

- [Screenshots Required](./Screenshots_Required.md) — the capture checklist for whoever has game access.
- [Windows live-run runbook](./Windows_Live_Runbook.md) — every outstanding live proof, in the order to do them.
- [Ticket 5](./Ticket_5_BackToBastion_Cap.md) — the `back_to_bastion()` cap, carved out of Phase 2 so it stays out of other PRs.

### Phase 1 offline checklist (shipped 2026-08-01)

- [x] PR 1.1 — schema, validation, `python -m engine.validate`
- [x] PR 1.2 — `ScreenActions` seam, runner, `FakeScreen`, ClickHandler region + `is_image_present`
- [x] PR 1.3 — `configs/arena_v2.yaml`, `python -m engine.run`, FakeScreen graph tests
- [x] PR 1.4 — screenshot replay harness; asset match + replay on captures 01, 03–09 (reached `COMPLETED` while a run was one battle; see [the loop finding](#finding-arena-now-loops-which-promotes-capture-10-to-blocking) for why it no longer can)
- [x] PR 1.3 acceptance #4 — **live smoke run on Windows** (explicit follow-up; do not fake from macOS)
- [ ] **Capture 10 — now blocking.** It was "completes gem-guard coverage" while a run was one battle. Now that the Arena config loops, `ArenaRefillGems.png` is the only clean exit and *every* run ends on it, so an unverified crop is the difference between stopping and spending gems. See [the loop finding](#finding-arena-now-loops-which-promotes-capture-10-to-blocking)
- [ ] Captures 02 and 11 — still outstanding (11 is a realism check on the HITL tool, no longer a Phase 3 gate)

### Phase 2 offline checklist (shipped 2026-08-01)

- [x] PR 2.1 — `engine/dump.py`, paired `.png` + `.json` under `logs/dumps/`, injected `grab_screen`
- [x] PR 2.2 — `run_sequence()` extracted from `engine/run.py`; dump-before-recover asserted with a recording fake
- [x] PR 2.2 acceptance #2 — **live failure run on Windows.** See [Ticket 2 → Windows follow-ups](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups). **The dump it produced has not reached the repo** — `logs/` is gitignored, so it needs attaching by hand, and PR 4.2's gate has no input without it
- [ ] `back_to_bastion()` attempt cap — now written up as [Ticket 5](./Ticket_5_BackToBastion_Cap.md); still deliberately not fixed

Suite is now `43 passed, 2 skipped` on macOS with no game.

### Phase 3 offline checklist (shipped 2026-08-01)

- [x] `missing_assets` recursive walk (posix-relative paths) — own commit ahead of the UI
- [x] PR 3.3 — `hitl/repair.py` rewrite with ruamel (`width=4096` + null representer); one-line-diff + restore-from-bytes tests
- [x] PR 3.2 — `crop_target` with dimension, pixel-identity, and locate round-trip tests; `assets/dynamic/`
- [x] PR 3.1 — `hitl/app.py` CustomTkinter window + `python -m hitl` — opened and driven on macOS after `brew install python-tk@3.13`
- [x] Seam guard: importing `hitl.repair` pulls in neither `tkinter` nor `customtkinter` — now meaningful, since customtkinter is installed in the venv
- [x] GUI smoke-test — all six checklist points pass via `helper_scripts/hitl_smoke.py` (20 assertions against the real window)
- [ ] One human check: a **real mouse drag** on the canvas. The smoke script injects synthetic coordinates, which steps over the pointer → image-pixel mapping where the scaling trap lives
- [ ] Capture 11 realism check on the finished tool

Suite after Phase 3: `55 passed, 2 skipped` on macOS with no game.

### Phase 4 checklist (PR 4.1 shipped 2026-08-01)

- [x] PR 4.1 — `engine/sequence_command.py`; `classic_arena_v2` registered **beside** v1, off in every preset
- [x] Counter question — **resolved by the epic owner: option 3, "until exhausted".** Implemented as a cycle in `configs/arena_v2.yaml`, not a counter. See [the loop finding](#finding-arena-now-loops-which-promotes-capture-10-to-blocking)
- [x] PR 4.1 acceptance 1–3 — **live, on the game machine** ([runbook run 5](./Windows_Live_Runbook.md#5-v2-engine-tab))
- [x] Post-live cleanup — the live session's own commit regressed the suite and `config.ini`; see [what the live run brought back](#what-the-live-run-brought-back)
- [ ] **Supervised loop run** — the Arena config now fights until tokens run out, and that has never run live ([runbook run 6](./Windows_Live_Runbook.md#6-supervised-loop-run-until-tokens-run-out))
- [ ] PR 4.2 — **gated.** Needs the soak *and* one real failure fixed through the HITL tool with no Python edits
- [ ] PR 4.3 — one second module, after 4.2

Suite after the post-live cleanup: `66 passed, 2 skipped` on macOS with no game.

New finding from PR 4.1: **an in-app v2 run is not window-scoped.** The app builds `ClickHandler` without a `region_provider`, so it searches the whole desktop while `python -m engine.run` searches the game window. Left alone rather than fixed, because changing it would change matching for all eight v1 commands. See [Ticket 4 → Finding](./Ticket_4_Phase4_Migration.md#finding-the-in-app-path-is-not-window-scoped).

### What the live run brought back

Runs 1, 2 and 5 passed on the game machine — a v2 click lands, and the YAML-driven battle runs from the app's own thread. That is the epic's central risk retired.

The commit made during that session also carried four regressions back with it. All are fixed now, and they are recorded because three of them are the kind of thing that recurs:

| # | What happened | Why it matters | Resolution |
|---|---|---|---|
| 1 | `SequenceCommand.execute` read `V2_Settings/arena_repeats` from `self.app.config_handler` | Six tests failed (`app` is `None` in tests by design), and it put a game-specific key inside the deliberately game-agnostic adapter | Reverted. The repeat count is not a config value — see the counter decision above |
| 2 | All five task presets and `SelectionItems` were deleted from `config.ini`, while `[Schedules]` still named all five | Every one of the nine schedules resolved to a missing section and would have failed silently at its next fire | Presets restored from `6c6bf61`; all nine verified to resolve |
| 3 | `[Tasks] classic_arena_v2 = True` | v2 became on-by-default in the only surviving task section, inverting the "cannot fire on a timer" rule | v2 keys moved to their own `[V2 Tasks]` section and out of the Tasks tab entirely |
| 4 | A GUI settings tab for `arena_repeats` | The count is not a setting, and a v2 tab full of config is not what was wanted | Rebuilt as a v2 *task list* — checkbox per YAML command, run through the same `run_task` path |

**Root cause of #2, worth its own attention.** `TasksTab.remove_selection_item` calls `delete_section(item)` and rewrites `SelectionItems`, but never touches `[Schedules]`. Removing a preset therefore orphans every schedule naming it, and the breakage only surfaces when that schedule next fires. Clicking Remove five times is what emptied the file. There is now a warning naming the affected schedule IDs, but the underlying asymmetry is a v1 GUI bug and is not fixed here.

**Structural consequence of #3 and #4.** v1 tasks live on the Tasks tab, v2 tasks live on the V2 Engine tab, and the two read different config sections. Because the scheduler resolves a schedule's name to a `SelectionItems` preset, and `[V2 Tasks]` is not one, a v2 task can no longer be put on a timer by ticking a box. That is now a property of the layout rather than a convention someone has to remember.

### Finding: Arena now loops, which promotes capture 10 to blocking

The epic owner chose "until exhausted" over an exact count, and the guardrails already said how: *looping comes from cycles in the graph, not from a loop construct*. So `return_to_opponent_list.on_success` points back at `select_opponent`, and that is the entire change. No counter, no schema change, no new action type.

This is strictly better than the counter that PR 4.1 built. [Ticket 4 noted](./Ticket_4_Phase4_Migration.md#resolved-2026-08-01-option-3-until-exhausted) that `repeat=5` cannot see *why* an attempt ended, so a caller asking for five would navigate to the Arena five times and ESC back out of the refill prompt four of them. The cycle exits the moment tokens run out, because the token guard is the exit.

It also moves risk. `check_out_of_tokens` was close to decorative — with one battle per run you would only reach it by starting with zero tokens. It is now the only clean way out, so **every run ends there**, and `ArenaRefillGems.png` has never been matched against a real screen: capture 10 is undelivered and `tests/test_assets_match.py` skips that template by name. If the crop is stale, `check_out_of_tokens` returns false and `start_battle` clicks `arenaStart.png` at a refill modal. The likely outcome is no match and a clean abort with a dump; the bad outcome is a match on the modal's confirm button, which spends real gems.

Two things bound that risk, and neither is a substitute for capture 10:

- `SequenceRunner.max_steps` is 200, so a cycle that never finds its exit ends as `STEP_LIMIT` with a crash dump rather than fighting forever. At 6 steps per battle that ceiling is about 32 battles, comfortably above any real token count. Covered by `test_a_guard_that_never_fires_is_capped_not_infinite`.
- The first live loop run is supervised, with few tokens and a finger on F2 ([runbook run 6](./Windows_Live_Runbook.md#6-supervised-loop-run-until-tokens-run-out)). That run either confirms the guard or produces capture 10 as a crash dump, so it is worth doing either way.

One offline test got weaker and should not be quietly restored. `test_replay.py` could previously assert the config reaches `COMPLETED` against real screenshots; with a cycle it cannot, because the only clean exit needs an out-of-tokens frame the corpus does not contain. It now proves what it uniquely can — every template matching its real frame, in graph order, across two turns of the loop — and ends at the honest corpus-exhaustion abort. The clean exit is covered against `FakeScreen` in `test_arena_config.py`. Delivering capture 10 is what would let the replay assert `COMPLETED` again.

### Next task: the supervised loop run, then the PR 4.2 gate

Two things stand between here and PR 4.2, both on the game machine and both in the [runbook](./Windows_Live_Runbook.md):

1. **[Run 6](./Windows_Live_Runbook.md#6-supervised-loop-run-until-tokens-run-out)** — the loop has never run live. Supervised, low tokens, F2 ready. Delivers capture 10 one way or the other.
2. **The crash dump from the failed run** (runbook run 4). It was produced live but never reached the repo, because `logs/` is gitignored. PR 4.2's gate is a real failure repaired entirely through `python -m hitl`, and without that dump the gate has no input. [Run 3](./Windows_Live_Runbook.md#3-hitl-real-mouse-drag)'s real-mouse-drag check wants the same file.

PR 4.2 does not start until one real failure has been diagnosed and repaired entirely through `python -m hitl`. That criterion is the epic's premise, not a checkbox — if it cannot be met, the right outcome is to stop at PR 4.1 and say so.

Still deliberately not fixed: `back_to_bastion()`'s unbounded ESC loop, now written up as [Ticket 5](./Ticket_5_BackToBastion_Cap.md). It is not a drive-by for any Phase 4 PR.

## Definition of done for the epic

1. An Arena battle runs start to finish from `configs/arena_v2.yaml` with no Arena-specific Python executed. **Done** — offline and live on the game machine. The config now fights until tokens run out rather than stopping at one battle, via a graph cycle; that loop has not yet run live ([run 6](./Windows_Live_Runbook.md#6-supervised-loop-run-until-tokens-run-out)).
2. The engine has unit tests that pass on any OS with no game installed. **Done** (`66 passed, 2 skipped` on macOS).
3. A failed run leaves a screenshot and a JSON context file behind. **Done** — offline (`engine/dump.py`) and live. The live dump has not been sent back, and it is the input PR 4.2 is gated on.
4. A human can repair a broken image target through the HITL UI without opening an editor. **Done offline** (`hitl/repair.py` tested; `hitl/app.py` opened and driven on macOS). One human check left: a real mouse drag.
5. `Modules/arena/DailyTenArenaCommand.py` is still present and still works. Removing v1 is Phase 4's problem, and only once v2 has proven itself over real runs.

## Open questions for the epic owner

1. **What OS is the assigned developer on?** **Resolved: macOS.** Offline Phase 1 is fully runnable here; live `ClickHandler` runs stay on Windows.
2. **Who captures the screenshots, and when?** 01 and 03–09 delivered. Still need **10 (out-of-tokens — now blocking)**, 02 (ad), and 11 (lost screen — realism check for the HITL tool). 10 and 11 both come out of runs that are already on the list, so the answer is now "whoever does [run 6](./Windows_Live_Runbook.md#6-supervised-loop-run-until-tokens-run-out) and remembers to copy `logs/` out". See [Screenshots Required](./Screenshots_Required.md).
3. **Is anyone available to do live smoke runs on the game machine?** **Yes — and runs 1, 2 and 5 have now passed.** What that session showed is that the runs are not the bottleneck; getting the artefacts back off the machine is. `logs/` is gitignored, so both the run logs and the crash dump stayed behind.
4. **Does `DailyQuests` need exactly 5 Arena battles, or all of them?** Now that Arena fights until tokens run out, "exactly 5" would reopen the [counter decision](./Ticket_4_Phase4_Migration.md#resolved-2026-08-01-option-3-until-exhausted) rather than being a parameter. Worth answering before PR 4.2, not during it.
