# Phase 2: Telemetry & Crash Dumps

**Status: DONE (offline) — 2026-08-01.** PRs 2.1 and 2.2 shipped. Suite: `43 passed, 2 skipped` on macOS with no game (was 31/2 after Phase 1). Remaining: one live failure run on Windows (PR 2.2 acceptance #2) — see [Windows follow-ups](#windows-follow-ups) below.

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
6. **Do not wait for capture 11 to start coding.** PR 2.1/2.2 are fully testable with a synthetic image. Capture 11 is a realism check on Phase 3's finished tool, not a gate on Phase 2's generator (and not a gate on Phase 3 either — see [Ticket 3](./Ticket_3_Phase3_HITL.md)). Parallelize: implement dumps on macOS while someone on Windows grabs 02/10/11 and runs the Phase 1 live smoke.
7. **Definition of done for this ticket.** `ABORTED` and `STEP_LIMIT` write paired `.png` + `.json` under `logs/dumps/`; `COMPLETED` writes nothing; dump-before-recover is tested; live failure (when available) leaves a usable stuck-screen PNG.

## Scope

**In:** on an `ABORTED` or `STEP_LIMIT` run, write a screenshot plus a JSON context file, then recover to the Bastion.

**Out:** metrics, run history, success-rate tracking, uploading anything anywhere, dumping on successful runs, per-node screenshots. A dump on failure is the whole feature.

---

## PR 2.1 — Crash dump generator

**Status: DONE.** `engine/dump.py`, tests in `tests/test_dump.py`. All five acceptance criteria pass against a synthetic `PIL.Image`; no game, no display.

`engine/dump.py`:

```python
def write_crash_dump(config: SequenceConfig, result: RunResult,
                     config_path: Path, dumps_dir: Path,
                     grab_screen: Callable[[], Image.Image]) -> Path | None:
    """Write <timestamp>.png and <timestamp>.json. Returns the JSON path, or None if dumping failed."""
```

Two keyword-only arguments were added to the sketch above:

- **`region`** — the JSON has a `region` field, so the value has to come from somewhere, and `grab_screen` deliberately hides it. `None` records that the capture was the whole desktop, which is how the file records which of the two paths was taken.
- **`logger`** — the rest of the engine takes its logger explicitly rather than reaching for a module global. Defaults to `logging.getLogger(__name__)`.

The `COMPLETED` guard lives inside `write_crash_dump` as well as at the call site. That makes the function total — no caller can talk it into dumping a successful run — and it is what makes acceptance #3 a real assertion rather than a test of the caller.

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

The screen is captured **first**, before the directory is created or either file is opened. A failed `ImageGrab` therefore leaves nothing behind rather than a JSON file pointing at a PNG that does not exist — Phase 3's viewer can assume the two always arrive together.

### Acceptance

Tests in `tests/test_dump.py`, no game required — inject a small generated `Image` as `grab_screen`:

1. An `ABORTED` result writes both files, sharing a timestamp stem.
2. The JSON contains the failed node's action, target, and the full `visited` list.
3. A `COMPLETED` result writes nothing.
4. A `STEP_LIMIT` result writes a dump with `outcome: "STEP_LIMIT"`.
5. A `grab_screen` that raises produces no exception, returns `None`, and logs.

---

## PR 2.2 — Recovery ordering

**Status: DONE (offline).** `engine/run.py` refactored into a testable `run_sequence()` plus a Windows-only `main()`; ordering asserted in `tests/test_dump.py`. Acceptance #1 passes; #2 (live failure run) is a Windows follow-up.

`back_to_bastion()` is already called in the entry point's `finally` from PR 1.3. This PR is about one thing that is easy to get backwards:

**Write the dump before recovering.** `back_to_bastion()` spams ESC in a loop until it reaches the home screen. If it runs first, the screenshot shows the Bastion and the evidence is gone. Order in the entry point:

1. `run()` returns
2. if the outcome is not `COMPLETED`, `write_crash_dump(...)`
3. `back_to_bastion()` then `delete_popup()` in a `finally`
4. log the dump path so it is visible in the day's log file

### How the entry point had to change to make that testable

`engine/run.py` imported `pygetwindow` and `ClickHandler` at module scope, so on macOS it could not be imported at all, let alone tested. Acceptance #1 requires testing it. The split:

- **`run_sequence(config, config_path, screen, logger, *, grab_screen, region, recover, dumps_dir)`** — owns run → dump → recover. Takes the `ScreenActions` seam and a `recover` callable, so it runs against `FakeScreen` on any OS. This is the function that holds the ordering.
- **`main()`** — argparse, logger, `ClickHandler`, region resolution, and a `recover` closure over `back_to_bastion()` + `delete_popup()`. `import pygetwindow` and `from utils.click_handler import ClickHandler` moved **inside** `main()`; that is the only reason they are function-local, and there is a comment there saying so.

`tests/test_seam.py` gained one guard: importing `engine.run` must not pull in `pyautogui` or `pygetwindow`. Without it the split silently rots the first time someone tidies the imports back to the top of the file.

**Behaviour on Windows is unchanged** — same order, same cleanup calls, same `--full-screen` flag, same exit codes.

The region is resolved **once**, in `main()`, and the same tuple feeds the startup log, the `ImageGrab` bbox, and the JSON's `region` field. They cannot disagree. `ClickHandler.region` stays a live property for matching, where a moved window actually matters.

### Acceptance

1. **Done.** A test with a fake screen and a recording fake asserts the dump is written before `press_key("esc")` is called. The recording fake snapshots `logs/dumps/` at the instant recovery starts and asserts a `.png` and `.json` are already there, which is the property that matters rather than a bare call order.
2. **Outstanding — needs the game.** A live failure run leaves a usable PNG of the stuck screen in `logs/dumps/`.

---

## Windows follow-ups

Everything below needs the game machine. Nothing here blocks Phase 3's implementation — capture 11 is a realism check on the finished HITL tool, not a gate (see [Ticket 3](./Ticket_3_Phase3_HITL.md)).

### 1. Capture 11 — and the shortcut to getting it

**A live failed v2 run now produces capture 11 as a side effect.** The dump PNG *is* "any screen where the bot would be lost", captured at 900×600 from the same rect the matcher searched. That closes PR 2.2 acceptance #2 and delivers the [capture 11](./Screenshots_Required.md) realism check for the HITL tool in one run, and the result is more representative than a posed stand-in.

To force a failure deliberately, run the sequence from somewhere other than the Bastion:

```text
pip install -r requirements.txt
python -m engine.run configs/arena_v2.yaml   # started from a random screen
```

Expect `outcome=ABORTED`, a `Crash dump written: logs/dumps/<timestamp>.json` line in the log, and a matching PNG. Send both files.

### 2. Check the dump PNG is 900×600

Same display-scaling trap as the [screenshot captures](./Screenshots_Required.md#if-your-captures-are-not-900600): `ImageGrab.grab(bbox=...)` at non-100% scaling will not return the size the window rect claims. If the dump PNG is not 900×600, report the size and the scaling percentage rather than resizing it — it means the region the matcher searched and the pixels it actually compared are not the same shape, which is worth knowing on its own.

### 3. Still open from Phase 1

- **Live smoke run** — PR 1.3 acceptance #4. Unchanged by this phase.
- **Captures 02 and 10** — 10 completes the gem-refill guard coverage.

---

## Known risk, not fixed here

**Status: flagged, not fixed, now tracked in [Ticket 5](./Ticket_5_BackToBastion_Cap.md).** Confirmed present at `utils/click_handler.py:347` and deliberately left alone here.

Writing that ticket turned up something this section understated: **F2 cannot interrupt the loop at all.** `press_key` and `_locate_image` never check `cancel_flag`, and `back_to_bastion()` catches bare `Exception`, which would swallow a `CancellationException` even if one were raised. Since `SequenceCommand._cleanup_after_task` calls it from a `finally`, every v2 failure ends in a loop that neither stops itself nor answers the cancel key. Detail in Ticket 5.

`ClickHandler.back_to_bastion()` is an unbounded `while True` ESC loop with no attempt cap. If the game is in a state where the quit prompt never appears, it hangs forever, and it swallows its own exceptions so nothing surfaces.

That is a pre-existing v1 bug and touching it is outside this epic's guardrails, but a hang here would silently eat every scheduled task afterwards. Flag it to the epic owner as a separate small ticket — an attempt cap of roughly 30 iterations with a warning log. **Do not fix it as a drive-by in this PR.**

Phase 2 makes this slightly more visible without touching it: the dump is already on disk before the ESC loop starts, so if a run does hang in `back_to_bastion()`, the evidence of *why the run failed* survives. The hang itself still has to be killed by hand.

---

## Deliverables

```
engine/dump.py                 # write_crash_dump, DUMPS_DIR
engine/run.py                  # run_sequence() extracted; Windows imports moved into main()
tests/test_dump.py             # PR 2.1 generator + PR 2.2 ordering
tests/test_seam.py             # + one guard: engine.run imports without pyautogui/pygetwindow
```

No new dependencies — `Pillow` was already in both `requirements.txt` and `requirements-dev.txt`. `engine/dump.py` has no PIL runtime dependency at all: it only needs `image.save`, so `PIL.Image` is imported under `TYPE_CHECKING` purely for the `grab_screen` type hint. `ImageGrab` is called from `engine/run.py` and nowhere else. Nothing in `Modules/` or `utils/` was touched.
