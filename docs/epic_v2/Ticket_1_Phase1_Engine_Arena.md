# Phase 1: The Engine & One Arena Battle

**Status: DONE (offline) — 2026-08-01.** PRs 1.1–1.4 shipped. Suite: `31 passed, 2 skipped` on macOS with no game. Remaining: live smoke run on Windows (PR 1.3 acceptance #4), and captures 02/10/11.

**Goal:** a YAML file drives a single Classic Arena battle from the Bastion and back, with no Arena-specific Python running.

**Game access needed?** PRs 1.1 and 1.2 need none. PR 1.3 needs one live smoke run by someone with the game. PR 1.4 is blocked on [screenshots](./Screenshots_Required.md).

## Scope

**In:** load and validate YAML, walk the node graph, call the existing `ClickHandler`, run one Arena battle, unit tests that run anywhere.

**Out, deliberately:** fighting N battles, scrolling the opponent list, the arena refresh button, Tag Team Arena, GUI integration, scheduler integration, crash dumps (Phase 2), and every action type not listed below. Do not add these "while you're in there".

## Developer environment (read before day one)

The image matching this epic relies on is a pure function of two files, so it behaves identically on Windows, macOS, and Linux. Three things will still stop you on day one if you don't know them.

### `pip install -r requirements.txt` fails on macOS and Linux

`pywin32>=306` has no non-Windows distribution, and pip aborts the whole install on it. Add a `requirements-dev.txt` with just what engine work needs:

```
pydantic>=2.0
ruamel.yaml>=0.18
pytest>=8.0
Pillow>=9.5.0
PyScreeze>=0.1.28
opencv-python>=4.10.0.84
numpy>=2.1.2
```

That covers PRs 1.1, 1.2 and 1.4 completely. Note what is absent: no `pyautogui`, no `pywin32`. Phase 3 adds only `customtkinter`, which is also cross-platform.

### `opencv-python` is mandatory, despite appearing unused

Nothing in this repo imports `cv2`, so it looks like a dependency that could be cleaned up. It cannot. PyScreeze selects its matching backend at import time based on whether `cv2` imports, and the Pillow fallback rejects the confidence argument outright:

```python
# pyscreeze/__init__.py, _locateAll_pillow
if confidence is not None:
    raise NotImplementedError('The confidence keyword argument is only available if OpenCV is installed.')
```

Every lookup in this codebase passes `confidence=0.8`, so without OpenCV nothing matches at all — live or offline. Do not remove it.

Keep the OpenCV version reasonably pinned, and do not write tests whose expected match sits right on the 0.8 boundary. `TM_CCOEFF_NORMED` scores are stable in practice, but a match at exactly 0.80 is not something to build a test suite on.

### `engine/` must not import `pyautogui`

`utils/click_handler.py` imports `pyautogui` at module scope. On macOS that pulls in pyobjc, and on a headless Linux box it fails outright — so any test that transitively imports it becomes unrunnable on the developer's machine, which defeats the whole point of the `ScreenActions` seam.

The rule: **`engine/models.py`, `engine/runner.py` and `engine/screen.py` may import from `utils.exceptions` and `utils.constants` and nothing else.** Both are dependency-free (`exceptions.py` imports nothing; `constants.py` imports only `typing`), so they are safe anywhere. `engine/run.py` is the only module permitted to import `ClickHandler`, and it is never imported by a test.

Enforce it with a test that imports `engine.runner` and asserts `pyautogui` is absent from `sys.modules`. One assertion, and it stops the seam eroding later.

## Known behaviour differences from v1 (accepted for the MVP)

1. **One opponent, not all visible ones.** `ClassicArenaCommand._process_visible_teams` calls `locateAllOnScreen("arenaBattle.png")` and clicks every match by coordinate. `CLICK_IMAGE` clicks the single best match. Fine for one battle; revisit only if we later need to fight a whole page.
2. **No battle counting.** The YAML has no counters by design. Repeating comes from a cycle in the graph (`on_success` pointing back at an earlier node), which gives "keep going until nothing matches" but not "exactly 10". Exact counts are a later conversation, not a Phase 1 problem.
3. **No scroll and no refresh.** If the visible opponents are exhausted, the sequence ends. v1 would scroll and refresh.
4. **`back_to_bastion()` is not an action.** The engine stops; whatever launched it does cleanup, mirroring how `_cleanup_after_task` works today.

---

## PR 1.1 — Schema, validation, and a validate command

**Status: DONE.** `engine/models.py`, `engine/validate.py`, `tests/test_models.py`, `pytest.ini`, deps in `requirements.txt` + `requirements-dev.txt`.

Create `engine/models.py`. Add `pydantic>=2.0` and `ruamel.yaml>=0.18` to `requirements.txt`.

### Action set

Four actions. This is the complete set for Phase 1, and each one is required by a node in the Arena config.

| Action | `target` means | Succeeds when |
|---|---|---|
| `CLICK_IMAGE` | asset filename | the template was found and clicked |
| `WAIT_FOR_IMAGE` | asset filename | the template appeared before `timeout_seconds` |
| `IMAGE_PRESENT` | asset filename | the template is on screen right now (single check, no click, no polling) |
| `PRESS_KEY` | a key name, e.g. `esc` | always, unless the key press raises |

`target` is overloaded on purpose — an asset filename for the image actions, a key name for `PRESS_KEY`. One field is simpler than two plus a validator to enforce which is set.

Notes on what is *not* here:

- **`WAIT_UNTIL_DISAPPEARS` is not in the MVP.** The original draft made it one of two actions, but Arena never waits for something to vanish; it waits for `tapToContinue.png` to *appear*. Add it when a config actually needs it.
- **There is no sleep action.** `settle_seconds` on `CLICK_IMAGE` and `PRESS_KEY` covers every pause in the Arena flow and avoids doubling the node count with sleep nodes.

### Models

```python
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, model_validator


class Action(StrEnum):
    CLICK_IMAGE = "CLICK_IMAGE"
    WAIT_FOR_IMAGE = "WAIT_FOR_IMAGE"
    IMAGE_PRESENT = "IMAGE_PRESENT"
    PRESS_KEY = "PRESS_KEY"


class ActionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action
    target: str
    timeout_seconds: int = 30
    check_interval_seconds: int = 2
    settle_seconds: int = 1
    retries: int = 1
    note: str | None = None
    on_success: str | None = None
    on_failure: str | None = None


class SequenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    start_node: str
    nodes: dict[str, ActionNode]

    @model_validator(mode="after")
    def _edges_point_at_real_nodes(self) -> "SequenceConfig":
        if self.start_node not in self.nodes:
            raise ValueError(f"start_node {self.start_node!r} is not a defined node")
        for key, node in self.nodes.items():
            for edge in ("on_success", "on_failure"):
                dest = getattr(node, edge)
                if dest is not None and dest not in self.nodes:
                    raise ValueError(f"node {key!r}.{edge} points at unknown node {dest!r}")
        return self
```

Four things here are deliberate and were wrong or missing in the draft:

- **`= None` on the edges.** In pydantic v2, `on_success: str | None` with no default is a *required* field that happens to accept null. Every node would have to spell out both edges.
- **`Action` as an enum, not `str`.** A typo like `CLIK_IMAGE` should fail at load, not at 2am mid-run.
- **`extra="forbid"`.** Catches misspelled field names (`on_sucess`) for one line of code.
- **Defaults match `utils/constants.py`** (`DEFAULT_WAIT_TIMEOUT = 30`, `DEFAULT_WAIT_INTERVAL = 2`) rather than the draft's 10.

### Asset existence check

Keep this out of the model — it is a filesystem concern, not a schema concern.

```python
def missing_assets(config: SequenceConfig, assets_dir: Path) -> list[str]:
    """Return targets of image actions that have no matching file in assets/."""
```

Compare against an actual directory listing (`{p.name for p in assets_dir.iterdir()}`), **not** `Path.exists()`. macOS and Windows filesystems are case-insensitive, so `loading_screen.png` vs `loadingScreen.png` would silently pass an `exists()` check and then fail on a live run where the matcher is case-sensitive about the real filename.

`PRESS_KEY` targets are skipped.

### The validate command

`python -m engine.validate configs/arena_v2.yaml` — loads with `ruamel.yaml`, validates, reports unknown assets and any nodes unreachable from `start_node`, prints the node graph, exits non-zero on error.

This is the developer's main feedback loop without a game. Make its error messages good.

### Acceptance

- Valid config loads and round-trips through the models.
- Each of these is rejected with a clear message: unknown `start_node`, an edge pointing at a missing node, an unknown action type, an unknown field name.
- `missing_assets` catches a case-mismatched filename on a case-insensitive filesystem.
- Tests: `tests/test_models.py`. No game, no Windows, no screenshots.

---

## PR 1.2 — The runner and the fake screen

**Status: DONE.** `engine/screen.py`, `engine/runner.py` (injected `sleep`), `tests/fakes.py`, `tests/test_runner.py`, `tests/test_seam.py` (subprocess import-purity + AST ClickHandler contract). Two permitted `ClickHandler` edits shipped with v1 defaults.

This PR is the reason a developer without the game can do this work. Get the seam right.

### The seam

`engine/screen.py`:

```python
from typing import Protocol


class ScreenActions(Protocol):
    def click_image(self, image_name: str, description: str = "",
                    retries: int = 1, delay: int = 1) -> bool: ...

    def wait_for_image(self, image_name: str, description: str = "",
                       timeout: int = 30, check_interval: int = 2) -> bool: ...

    def is_image_present(self, image_name: str, description: str = "") -> bool: ...

    def press_key(self, key: str, description: str = "") -> None: ...
```

These signatures are copied from the real `ClickHandler` so it already satisfies the protocol structurally — no adapter, no wrapper, no changes to how the existing bot works.

**Permitted edit 1 of 2.** `ClickHandler._locate_image` is private, so add a public wrapper in `utils/click_handler.py`:

```python
def is_image_present(self, image_name: str, description: str = "") -> bool:
    """Single non-blocking check for an image on screen."""
    return self._locate_image(image_name, description) is not None
```

### Permitted edit 2 of 2 — scope the search to the game window

Today every lookup searches the entire desktop. Scope it to the game window rect instead.

**This costs almost nothing, because pyscreeze adds the region offset back before returning.** In `_locateAll_opencv` the match coordinates are computed as `matchx = matches[1] * step + region[0]` (and the same in the Pillow path), so `locateOnScreen(img, region=...)` returns **absolute screen coordinates** exactly as it does today. No coordinate translation anywhere, and no change to any clicking code.

Add an optional region to `ClickHandler`:

```python
def __init__(self, logger: Any, region_provider: Callable[[], tuple[int, int, int, int] | None] | None = None):
    ...
    self._region_provider = region_provider

@property
def region(self) -> tuple[int, int, int, int] | None:
    """(left, top, width, height) of the game window, or None to search the whole screen."""
    return self._region_provider() if self._region_provider else None
```

Then pass `region=self.region` at the four `locateOnScreen` / `locateAllOnScreen` call sites in `click_handler.py`: `_locate_image`, `wait_until_disappears`, `delete_popup`, and `_locate_all_buttons`.

A **callable**, not a static tuple, because the window can be moved or resized mid-run and a cached rect would go stale silently. `AutoRaider` already holds `self.raid_window` from `pygetwindow`, so the provider is a one-liner reading `.left`, `.top`, `.width`, `.height`. Rect reads are cheap Win32 calls.

**`region_provider=None` reproduces today's behaviour exactly**, so v1 modules are completely unaffected. Only the v2 entry point passes one.

Why this is worth doing now rather than later:

- **Screenshots become machine-independent.** The capture deliverable is a 900×600 PNG instead of "a full desktop at exactly the right resolution and DPI". That removes the most fragile requirement in [Screenshots Required](./Screenshots_Required.md), and it means every test built on those captures stays valid.
- **It makes a bad capture self-evident.** A file that is not 900×600 is wrong, immediately. A subtly-wrong full-desktop capture looks fine and just silently fails to match.
- **Far fewer false positives.** Several templates are tiny — `loadingScreen.png` is 16×14, `useAutoSelect.png` is 17×15. Matching a 16×14 template at 0.8 confidence against a whole 1920×1080 desktop will find spurious hits in browser chrome, notifications, and desktop icons. Constraining the haystack to the game window materially reduces that.
- **Faster matching.** `matchTemplate` over 900×600 instead of 1920×1080 is roughly 4× fewer pixels. Note this is a partial win: `locateOnScreen` still grabs the full screen and crops afterwards (it calls `screenshot(region=None)` deliberately so coordinates stay absolute), so the capture cost is unchanged — only the matching cost drops.
- **Retrofitting it later invalidates every screenshot already captured.** Cheaper to decide now.

**What it does not fix:** display scaling. Templates were cropped at whatever Windows scaling the bot normally runs at; a capture taken at 125% still will not match. Window-scoping makes that *detectable* via the image dimensions rather than solving it.

**Live-run isolation.** Make the region opt-in with a flag on the entry point (`--full-screen` to disable it). If the PR 1.3 live run misbehaves, that flag isolates "the engine is wrong" from "the region is wrong" in one attempt.

Nothing else in `utils/` changes.

### Failure semantics — read carefully

The original draft's `try/except` runner does not work against this codebase. The real rules:

| Situation | What actually happens | Engine behaviour |
|---|---|---|
| `click_image` can't find the image | returns **`False`** | take `on_failure` |
| `wait_for_image` times out | returns **`False`** | take `on_failure` |
| `is_image_present` finds nothing | returns **`False`** | take `on_failure` |
| GUI cancel (`cancel_flag`) | raises **`CancellationException`** | **re-raise immediately.** Never treat as a node failure — swallowing it breaks the F2 cancel button |
| PyAutoGUI failsafe, or anything unexpected | raises | log with traceback, take `on_failure` |

`utils/exceptions.ImageNotFoundError` exists but is raised by nothing. Do not write code that catches it and expect that to work.

### The runner

`engine/runner.py`:

```python
class Outcome(StrEnum):
    COMPLETED = "COMPLETED"   # ran off a null on_success — the sequence finished
    ABORTED = "ABORTED"       # ran off a null on_failure — the bot is lost
    STEP_LIMIT = "STEP_LIMIT" # exceeded max_steps — probably a cycle with no exit


@dataclass
class RunResult:
    outcome: Outcome
    last_node: str
    steps: int
    visited: list[str]


class SequenceRunner:
    def __init__(self, config: SequenceConfig, screen: ScreenActions,
                 logger: Logger, max_steps: int = 200) -> None: ...

    def run(self) -> RunResult: ...
```

Loop shape:

```python
current = self.config.start_node
visited: list[str] = []

for step in range(1, self.max_steps + 1):
    node = self.config.nodes[current]
    visited.append(current)

    try:
        ok = self._execute(node)
    except CancellationException:
        raise
    except Exception:
        self.logger.exception("Node %s raised", current)
        ok = False

    next_key = node.on_success if ok else node.on_failure
    if next_key is None:
        outcome = Outcome.COMPLETED if ok else Outcome.ABORTED
        return RunResult(outcome, current, step, visited)
    current = next_key

return RunResult(Outcome.STEP_LIMIT, current, self.max_steps, visited)
```

Two points worth calling out:

- **A null edge terminates the run**, and *which* edge it was tells you whether things went well. That resolves the draft's dangling `bastion_fallback` reference without inventing a recovery action type or putting game knowledge in the engine.
- **`max_steps` replaces YAML counters.** Since looping comes from graph cycles and the YAML has no way to count, a mis-wired cycle would otherwise spin forever. 200 is arbitrary but generous; make it a constructor argument.

`_execute` dispatches on `node.action`. Keep it a flat dispatch with one branch per action and no game vocabulary anywhere.

`PRESS_KEY` returns `True` after sleeping `settle_seconds`. `CLICK_IMAGE` passes `settle_seconds` as `click_image(delay=...)`, which is what the existing handler already sleeps after a successful click.

### The fake

`tests/fakes.py` — a `FakeScreen` implementing `ScreenActions`, scripted with per-image results and recording every call in order. Roughly:

```python
FakeScreen(results={"battleBTN.png": [True], "arenaBattle.png": [False, True]})
```

Keep it under 50 lines. It is a test double, not a simulator.

### Acceptance

`tests/test_runner.py`, all passing with no game, no Windows, no screenshots:

1. A linear happy path visits nodes in the expected order and returns `COMPLETED`.
2. A failing node follows `on_failure`.
3. A node with a null `on_failure` that fails returns `ABORTED` with `last_node` set to that node.
4. `CancellationException` from the screen propagates out of `run()` and is **not** converted into a failure edge.
5. An arbitrary exception from the screen is logged and follows `on_failure`.
6. A deliberate two-node cycle terminates with `STEP_LIMIT` rather than hanging.
7. `IMAGE_PRESENT` takes `on_success` when the image is present and `on_failure` when it is not, and never clicks.
8. Node fields reach the handler correctly: `timeout_seconds` arrives as `timeout`, `settle_seconds` as `delay`, `retries` as `retries`.

Test 8 matters because the draft assumed `click_image(target, timeout=...)`, and `click_image` has no `timeout` parameter at all. Assert on the recorded kwargs.

---

## PR 1.3 — The Arena config and a live run

**Status: DONE (offline).** `configs/arena_v2.yaml`, `engine/run.py`, `tests/test_arena_config.py` (happy path + gem-refill guard). Live smoke run still open — see follow-up under Acceptance.

`configs/arena_v2.yaml`, transcribed from `Modules/arena/DailyTenArenaCommand.py`. Every asset below exists in `assets/` today.

**Targets are bare filenames.** `ClickHandler` resolves the assets directory itself and prepends it, so `assets/arenaBattle.png` becomes `assets/assets/arenaBattle.png` and never matches.

```yaml
# configs/arena_v2.yaml
name: "Arena - single classic battle"
start_node: close_popup_ads

# on_failure is omitted where a failure means the bot is lost.
# An omitted edge is null, which ends the run as ABORTED.

nodes:
  close_popup_ads:
    action: CLICK_IMAGE
    target: exitAdd.png
    settle_seconds: 3
    note: "Best effort - no ad on screen is the normal case, so both edges continue."
    on_success: open_battle_menu
    on_failure: open_battle_menu

  open_battle_menu:
    action: CLICK_IMAGE
    target: battleBTN.png
    settle_seconds: 1
    on_success: open_arena_tab

  open_arena_tab:
    action: CLICK_IMAGE
    target: arenaTab.png
    settle_seconds: 1
    on_success: enter_classic_arena

  enter_classic_arena:
    action: CLICK_IMAGE
    target: classicArena.png
    settle_seconds: 2
    on_success: select_opponent

  select_opponent:
    action: CLICK_IMAGE
    target: arenaBattle.png
    settle_seconds: 2
    note: "Clicks the best single match. v1 clicked every visible Battle button."
    on_success: check_out_of_tokens

  check_out_of_tokens:
    action: IMAGE_PRESENT
    target: ArenaRefillGems.png
    note: >-
      Guard against spending real gems. on_success means the refill prompt IS
      on screen, which is a legitimate stop rather than a failure.
    on_success: leave_refill_prompt
    on_failure: start_battle

  leave_refill_prompt:
    action: PRESS_KEY
    target: esc
    settle_seconds: 1
    on_success: null

  start_battle:
    action: CLICK_IMAGE
    target: arenaStart.png
    settle_seconds: 1
    on_success: await_battle_end

  await_battle_end:
    action: WAIT_FOR_IMAGE
    target: tapToContinue.png
    timeout_seconds: 120
    check_interval_seconds: 2
    note: "Battle end is detected by tapToContinue appearing. There is no victory or defeat detection in v1."
    on_success: dismiss_results

  dismiss_results:
    action: CLICK_IMAGE
    target: tapToContinue.png
    settle_seconds: 1
    on_success: return_to_opponent_list

  return_to_opponent_list:
    action: PRESS_KEY
    target: esc
    settle_seconds: 2
    on_success: null
```

### Entry point

`python -m engine.run configs/arena_v2.yaml`, a standalone script that builds a logger via `utils.logger.setup_logger`, constructs a `ClickHandler` with a `region_provider` reading the game window rect from `pygetwindow`, runs the sequence, logs the `RunResult`, and calls `click_handler.back_to_bastion()` and `delete_popup()` in a `finally`.

Support `--full-screen` to pass `region_provider=None`, so a live run can be repeated unscoped to isolate a region problem from an engine problem. Log the resolved region at startup — if it is not 900×600, that is the first thing to check when a run misbehaves.

Standalone on purpose. Do not touch `main.py`, `app/pyAutoRaid.py`, the command factory, the GUI, or `config.ini` in this phase. Wiring v2 into the scheduler is Phase 4's job, after the engine has earned it.

### Acceptance

1. `python -m engine.validate configs/arena_v2.yaml` passes with no missing assets and no unreachable nodes.
2. A graph-traversal test drives the config with `FakeScreen` scripted for the happy path and asserts the visited node order — no game required, and this is the part the assigned developer owns.
3. A test scripting `ArenaRefillGems.png` as present ends at `leave_refill_prompt` with `COMPLETED` and never reaches `start_battle`.
4. **Live smoke run** (needs someone with the game): starting from the Bastion, one Arena battle completes and the run returns `COMPLETED`. `Modules/arena/` is not imported.

#### Open follow-up — live smoke run (acceptance #4)

**Status: outstanding.** Phase 1 offline acceptance (1–3) and PR 1.4 replay shipped on macOS. The live smoke run cannot run here (`pywin32` / game window APIs are Windows-only).

On the Windows game machine:

```text
pip install -r requirements.txt   # full set, including pywin32
python -m engine.run configs/arena_v2.yaml
# If matching looks wrong, isolate region vs engine:
python -m engine.run configs/arena_v2.yaml --full-screen
```

Expect `outcome=COMPLETED` from Bastion through one Classic Arena battle. Log the region at startup — it should be 900×600. Do not fake this from macOS.

### Turning one battle into many (later, not now)

Once one battle is proven, point `return_to_opponent_list.on_success` back at `select_opponent`. The sequence then fights opponents until no Battle button matches, and ends. That is a one-line change and it is not part of this ticket — get one battle working first.

---

## PR 1.4 — Screenshot replay harness

**Status: DONE (partial coverage).** `tests/screenshot_screen.py` (forward-polling `wait_for_image`), `tests/test_assets_match.py`, `tests/test_replay.py` — replay 01→09 reaches `COMPLETED`. Skips by name for `exitAdd.png` (needs 02) and `ArenaRefillGems.png` (needs 10).

See [Screenshots Required](./Screenshots_Required.md), captures 1–10.

The `FakeScreen` tests prove the graph is wired correctly. They prove nothing about whether `arenaBattle.png` actually matches an Arena screen at confidence 0.8. That gap can only be closed with real captures, and it is where live runs usually break.

Build a second `ScreenActions` implementation that reads from a scripted list of screenshot files instead of the live screen:

- Matching: `pyscreeze.locate(needle_path, haystack_path, confidence=0.8)` — the same matcher and the same confidence the live bot uses, pointed at a file.
- `click_image` succeeds if the template is found in the current screenshot, then advances to the next screenshot in the list.
- `is_image_present` checks the current screenshot without advancing.
- `wait_for_image` polls **forward** through the screenshot list until the template matches or the list is exhausted, and does **not** advance past a successful match (so a following `CLICK_IMAGE` of the same target still finds it). Checking only the current frame would abort the Arena replay: after `start_battle` advances past capture 06, `await_battle_end` would look for `tapToContinue.png` on the loading screen and fail.
The supplied captures are **900×600 game-window crops**, which is exactly the haystack the region-scoped live search sees. That equivalence is what makes this harness a meaningful signal rather than an approximation, and it is the reason for permitted edit 2 in PR 1.2.

Reuse `ScreenActions` unchanged. Keep the whole thing around 60 lines; it is a test harness, not a game simulator.

### Acceptance

1. Every supplied screenshot is exactly 900×600. Anything else means the captures were taken at non-100% display scaling — fail loudly with the actual dimensions rather than producing confusing match failures downstream.
2. Every image target in `configs/arena_v2.yaml` is found in at least one supplied screenshot at confidence 0.8. Any target that fails is reported by name — that is a real bug in the asset crop, and exactly what this harness exists to surface.
3. Replaying the Arena screenshot sequence in order drives the config to `COMPLETED`.

---

## Deliverables

```
engine/__init__.py
engine/models.py       # Action, ActionNode, SequenceConfig, missing_assets
engine/screen.py       # ScreenActions protocol
engine/runner.py       # SequenceRunner, Outcome, RunResult
engine/validate.py     # python -m engine.validate
engine/run.py          # python -m engine.run
configs/arena_v2.yaml
tests/fakes.py
tests/screenshot_screen.py
tests/test_models.py
tests/test_runner.py
tests/test_seam.py
tests/test_arena_config.py
tests/test_assets_match.py
tests/test_replay.py
tests/screenshots/     # PR 1.4 captures (01, 03–09 delivered; 02, 10, 11 outstanding)
```

Plus `pydantic>=2.0`, `ruamel.yaml>=0.18` and `pytest>=8.0` added to `requirements.txt`, a new `requirements-dev.txt` (see Developer environment above), and a minimal `pytest.ini` — this repo has no test infrastructure at all today, so Phase 1 is establishing it.
