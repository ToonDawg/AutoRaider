# Phase 2: Telemetry & Crash Dumps

**Status: NEXT** — Phase 1 offline is done. Start here.

**Goal:** when the bot gets lost, leave behind enough evidence to fix it later without being at the machine.

**Depends on:** Phase 1 complete (`RunResult` with `Outcome` and `visited`). **Met.**

**Game access needed?** No, for the implementation. One screenshot is needed to exercise the viewer in Phase 3 — see [Screenshots Required](./Screenshots_Required.md), capture 11.

## How a senior would do this

Phase 2 is small on purpose. Keep it that way.

1. **Read the Phase 1 seams before writing.** Crash dumps hang off `RunResult` and the `engine.run` entry point — not inside `SequenceRunner`. The runner must stay I/O-free so FakeScreen / ScreenshotScreen tests stay trivial. If you feel the urge to add a callback hook into the loop, stop; Ticket 2 already rejected that.
2. **Inject `grab_screen`.** Do not call `ImageGrab` from `engine/dump.py` at import time or hard-wire it. Signature is already specified: pass a callable so unit tests inject a tiny `PIL.Image` and never touch the display. On the live path, the entry point closes over `ClickHandler.region` (900×600 window crop, or full screen when `--full-screen`).
3. **Order is load-bearing: dump, then recover.** Write the dump *before* `back_to_bastion()` / `delete_popup()`. ESC spam destroys the evidence if you reverse them. Put that ordering in `engine/run.py` and assert it with a recording fake (PR 2.2 acceptance).
4. **Dumping must never take down the run.** Wrap `write_crash_dump` in try/except; return `None` and log. A broken dump must not block Bastion recovery.
5. **Stay out of `Modules/` and `utils/`.** Phase 2 only adds `engine/dump.py`, wires it from `engine/run.py`, and adds `tests/test_dump.py`. Do not "fix" `back_to_bastion()`'s unbounded ESC loop as a drive-by — that is a separate ticket (noted at the bottom of this file).
6. **Do not wait for capture 11 to start coding.** PR 2.1/2.2 are fully testable with a synthetic image. Capture 11 unblocks Phase 3's viewer, not Phase 2's generator. Parallelize: implement dumps on macOS while someone on Windows grabs 02/10/11 and runs the Phase 1 live smoke.
7. **Definition of done for this ticket.** `ABORTED` and `STEP_LIMIT` write paired `.png` + `.json` under `logs/dumps/`; `COMPLETED` writes nothing; dump-before-recover is tested; live failure (when available) leaves a usable stuck-screen PNG.

## Scope

**In:** on an `ABORTED` or `STEP_LIMIT` run, write a screenshot plus a JSON context file, then recover to the Bastion.

**Out:** metrics, run history, success-rate tracking, uploading anything anywhere, dumping on successful runs, per-node screenshots. A dump on failure is the whole feature.

---

## PR 2.1 — Crash dump generator

`engine/dump.py`:

```python
def write_crash_dump(config: SequenceConfig, result: RunResult,
                     config_path: Path, dumps_dir: Path,
                     grab_screen: Callable[[], Image.Image]) -> Path | None:
    """Write <timestamp>.png and <timestamp>.json. Returns the JSON path, or None if dumping failed."""
```

### Where it is called from

From the `python -m engine.run` entry point, not from inside `SequenceRunner`.

Keeping the runner free of I/O keeps it trivially testable, and the screen has not changed between the runner returning and the caller reacting — the run stops the instant it hits a terminal edge. The alternative is a callback hook inside the loop, which is more machinery for no practical gain.

### Screenshot

Use `PIL.ImageGrab.grab()`. It is already how `utils/ocr_handler.py` captures the screen, and it adds no dependency.

Capture the **game window region only** — the same rect the engine searches (`ClickHandler.region`, from Ticket 1 PR 1.2), giving a 900×600 image:

```python
ImageGrab.grab(bbox=(left, top, left + width, top + height))
```

The dump must show exactly the haystack the matcher was looking at, so it has to follow the search region. It also keeps dumps small, keeps whatever else is on the desktop out of them, and means the Phase 3 crop tool can display them at 1:1.

If the region is `None` (the `--full-screen` case), fall back to `ImageGrab.grab()` and record which one was used in the JSON. Pass the capture function in as an argument so tests can inject a stored PNG.

### Files

`logs/dumps/YYYY-MM-DD_HH-MM-SS.png` and `.json`, sharing a timestamp stem. `logs/` is already in `.gitignore`, so dumps stay out of version control. Create `logs/dumps/` if missing.

```json
{
  "timestamp": "2026-08-01T09:31:44",
  "outcome": "ABORTED",
  "config_path": "configs/arena_v2.yaml",
  "sequence_name": "Arena - single classic battle",
  "failed_node": "select_opponent",
  "action": "CLICK_IMAGE",
  "target": "arenaBattle.png",
  "note": "Clicks the best single match. v1 clicked every visible Battle button.",
  "on_success": "check_out_of_tokens",
  "on_failure": null,
  "steps": 5,
  "visited": ["close_popup_ads", "open_battle_menu", "open_arena_tab", "enter_classic_arena", "select_opponent"],
  "screenshot": "2026-08-01_09-31-44.png",
  "region": [500, 200, 900, 600]
}
```

`visited` is the most useful field in the file — it shows the path taken, which is usually how you spot that the bot was on the wrong screen three nodes earlier. Phase 3 reads `config_path` and `failed_node` to know which YAML node to rewrite, so both are required.

### Dumping must never make things worse

Wrap the whole function in a `try/except`, log the failure, and return `None`. A crash dump failing to write must not take down the run or block Bastion recovery.

### Acceptance

Tests in `tests/test_dump.py`, no game required — inject a small generated `Image` as `grab_screen`:

1. An `ABORTED` result writes both files, sharing a timestamp stem.
2. The JSON contains the failed node's action, target, and the full `visited` list.
3. A `COMPLETED` result writes nothing.
4. A `STEP_LIMIT` result writes a dump with `outcome: "STEP_LIMIT"`.
5. A `grab_screen` that raises produces no exception, returns `None`, and logs.

---

## PR 2.2 — Recovery ordering

`back_to_bastion()` is already called in the entry point's `finally` from PR 1.3. This PR is about one thing that is easy to get backwards:

**Write the dump before recovering.** `back_to_bastion()` spams ESC in a loop until it reaches the home screen. If it runs first, the screenshot shows the Bastion and the evidence is gone. Order in the entry point:

1. `run()` returns
2. if the outcome is not `COMPLETED`, `write_crash_dump(...)`
3. `back_to_bastion()` then `delete_popup()` in a `finally`
4. log the dump path so it is visible in the day's log file

### Acceptance

1. A test with a fake screen and a recording fake asserts the dump is written before `press_key("esc")` is called.
2. A live failure run (whoever has the game) leaves a usable PNG of the stuck screen in `logs/dumps/`.

---

## Known risk, not fixed here

`ClickHandler.back_to_bastion()` is an unbounded `while True` ESC loop with no attempt cap. If the game is in a state where the quit prompt never appears, it hangs forever, and it swallows its own exceptions so nothing surfaces.

That is a pre-existing v1 bug and touching it is outside this epic's guardrails, but a hang here would silently eat every scheduled task afterwards. Flag it to the epic owner as a separate small ticket — an attempt cap of roughly 30 iterations with a warning log. **Do not fix it as a drive-by in this PR.**
