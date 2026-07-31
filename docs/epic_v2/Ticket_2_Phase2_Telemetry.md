# Phase 2: Telemetry & Crash Dumps

**Goal:** when the bot gets lost, leave behind enough evidence to fix it later without being at the machine.

**Depends on:** Phase 1 complete (`RunResult` with `Outcome` and `visited`).

**Game access needed?** No, for the implementation. One screenshot is needed to exercise the viewer in Phase 3 — see [Screenshots Required](./Screenshots_Required.md), capture 11.

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
