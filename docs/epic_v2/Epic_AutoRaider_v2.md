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
| 7 | "No counters" vs "complete Arena battle loop" | Classic Arena fights up to 100 teams by counting. A YAML with no counters **cannot** express "fight exactly 10". | Ticket 1 — MVP is **one** battle. Repeat-until-exhausted comes free from a graph cycle; exact counts are deferred |
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
| 1 | [Engine & one Arena battle](./Ticket_1_Phase1_Engine_Arena.md) | **DONE (offline)** — PRs 1.1–1.4 shipped; live smoke run still open | Optional for core; required for the asset-match check (PR 1.4) |
| 2 | [Telemetry & crash dumps](./Ticket_2_Phase2_Telemetry.md) | **DONE (offline)** — PRs 2.1–2.2 shipped; live failure run still open | No, for the implementation. A live failed run now *produces* capture 11 |
| 3 | [HITL authoring UI](./Ticket_3_Phase3_HITL.md) | Blocked on capture 11 | **Yes, hard blocker** — the UI is meaningless without real captures |
| 4 | [Migration & deprecation](./Ticket_4_Phase4_Migration.md) | Not started | Yes, per module migrated |

Supporting document: [Screenshots Required](./Screenshots_Required.md) — the capture checklist for whoever has game access.

### Phase 1 offline checklist (shipped 2026-08-01)

- [x] PR 1.1 — schema, validation, `python -m engine.validate`
- [x] PR 1.2 — `ScreenActions` seam, runner, `FakeScreen`, ClickHandler region + `is_image_present`
- [x] PR 1.3 — `configs/arena_v2.yaml`, `python -m engine.run`, FakeScreen graph tests
- [x] PR 1.4 — screenshot replay harness; asset match + replay to `COMPLETED` on captures 01, 03–09
- [ ] PR 1.3 acceptance #4 — **live smoke run on Windows** (explicit follow-up; do not fake from macOS)
- [ ] Captures 02, 10, 11 — still outstanding (10 completes gem-guard coverage; 11 hard-blocks Phase 3)

### Phase 2 offline checklist (shipped 2026-08-01)

- [x] PR 2.1 — `engine/dump.py`, paired `.png` + `.json` under `logs/dumps/`, injected `grab_screen`
- [x] PR 2.2 — `run_sequence()` extracted from `engine/run.py`; dump-before-recover asserted with a recording fake
- [ ] PR 2.2 acceptance #2 — **live failure run on Windows.** See [Ticket 2 → Windows follow-ups](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups)
- [ ] `back_to_bastion()` attempt cap — flagged for the epic owner as a separate ticket, deliberately not fixed here

Suite is now `43 passed, 2 skipped` on macOS with no game.

### Next task: Phase 3, once capture 11 exists

See [Ticket 3](./Ticket_3_Phase3_HITL.md). **Do not start it until capture 11 exists** — the UI has nothing to display without it.

The cheapest way to get capture 11 is now one deliberately-failed live v2 run: the Phase 2 crash dump writes a 900×600 PNG of whatever screen the bot was stuck on, which is exactly what Phase 3 needs and closes PR 2.2 acceptance #2 at the same time. Details in [Ticket 2 → Windows follow-ups](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups).

If the game machine is free, the Phase 1 live smoke run is still the only outstanding gate that proves clicks actually work.

## Definition of done for the epic

1. A single Arena battle runs start to finish from `configs/arena_v2.yaml` with no Arena-specific Python executed. *(offline proven; live Windows smoke still open)*
2. The engine has unit tests that pass on any OS with no game installed. **Done** (`31 passed, 2 skipped` on macOS).
3. A failed run leaves a screenshot and a JSON context file behind. **Done offline** (`engine/dump.py`); live failure run on Windows still outstanding.
4. A human can repair a broken image target through the HITL UI without opening an editor. *(Phase 3)*
5. `Modules/arena/DailyTenArenaCommand.py` is still present and still works. Removing v1 is Phase 4's problem, and only once v2 has proven itself over real runs.

## Open questions for the epic owner

1. **What OS is the assigned developer on?** **Resolved: macOS.** Offline Phase 1 is fully runnable here; live `ClickHandler` runs stay on Windows.
2. **Who captures the screenshots, and when?** 01 and 03–09 delivered. Still need 02 (ad), 10 (out-of-tokens), and **11 (lost screen — Phase 3 blocker)**. See [Screenshots Required](./Screenshots_Required.md).
3. **Is anyone available to do live smoke runs on the game machine?** **Yes, on request.** That run closes PR 1.3 acceptance #4 — still outstanding.
