# Phase 3: Human-In-The-Loop Authoring UI

**Status: DONE — 2026-08-01.** PRs 3.1–3.3 shipped. The pure repair core is tested in the suite; the CustomTkinter window was then opened on macOS after `brew install python-tk@3.13` and driven through all six checklist points by `helper_scripts/hitl_smoke.py`. One human check remains — a real mouse drag, which the smoke script cannot simulate honestly. See [Windows follow-ups](#windows-follow-ups) below.

**Goal:** repair a broken image target by re-cropping it from the crash screenshot, without opening an editor.

**Depends on:** Phase 2 (crash dumps exist and record `config_path` + `failed_node`). **Met** — `engine/dump.py` writes both fields; the exact file shape is in [Ticket 2 → PR 2.1](./Ticket_2_Phase2_Telemetry.md#files).

**Game access needed?** No. **Screenshots needed?** Captures 01 and 03–09 are delivered and are enough to build and test all three PRs. Capture 11 is a realism check, not a structural blocker — see below.

## How a senior would do this

### 1. The capture-11 blocker is weaker than it looks — re-scope it

The epic calls capture 11 a hard blocker. That was written when the repository held **zero** full-screen captures. Eight are delivered now, and Phase 2 ships a dump writer, so the situation has changed and the blocker should be re-read rather than inherited.

Work through what each PR actually needs:

| PR | Needs | Have it? |
|---|---|---|
| 3.3 config mutation | A YAML file and a dump JSON | Yes — no image involved at all |
| 3.2 crop | Any 900×600 capture and a known region | Yes — eight of them |
| 3.1 viewer | A dump pair to display | Yes, once one is generated |

Nothing on that list requires a screen the bot was genuinely lost on. **Generate the fixture instead of waiting for it**, using the code that already exists:

- `ScreenshotScreen` (PR 1.4) drives the engine against the replay chain **`01 → 03 → 04 → 05`**. Capture 05 alone is not enough: the sequence starts at `close_popup_ads`, and `battleBTN.png` is not on the opponent list, so a single-frame fixture aborts at `open_battle_menu` instead of `select_opponent`.
- Point a copy of the config's `select_opponent` target at an asset that will not match on capture 05 (e.g. `bastion.png` — it exists, so the config still loads, but will never locate).
- `run_sequence` (PR 2.2) reaches `ABORTED` at `select_opponent`, and `write_crash_dump` (PR 2.1) writes a real, self-consistent dump pair whose PNG is capture 05.

That fixture is worth more than a hand-written JSON because the real writer produced it — if the dump format drifts, the Phase 3 tests break, which is exactly what you want. Build it as a pytest fixture, not a checked-in artifact.
What capture 11 still buys, and why it is worth asking for anyway: it is the only way to confirm the tool helps in the case it exists to serve — a screen with something *unanticipated* on it. Treat that as a review step once the capture arrives, not as a gate on writing code. And note the shortcut in [Ticket 2 → Windows follow-ups](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups): a deliberately-failed live run now produces capture 11 by itself.

### 2. Build it inside-out: 3.3, then 3.2, then 3.1

The PRs are numbered UI-first. Build them in the opposite order.

The YAML mutation and the crop are pure functions with sharp acceptance criteria and no GUI. The CustomTkinter window is a thin view over them, and it is the only part with no meaningful automated coverage. Build the UI first and the phase is spent clicking around a window to test logic that could have been asserted in milliseconds. Build the core first and the window is ~150 lines of wiring over already-proven functions.

There is also a hard dependency in that direction: PR 3.3's validation step needs the `missing_assets` change (see below), and PR 3.1 has nothing to display until a dump fixture exists.

### 3. Same seam discipline as Phases 1 and 2 — and this time the OS enforces it

`_tkinter` is **not available in this Python at all** (`brew install python-tk@3.13` is needed, and `customtkinter` is not in `requirements-dev.txt` yet). So the suite currently cannot import a GUI module even if it wanted to.

Do not treat that as a problem to fix before starting. Treat it as the same lesson Phase 1 learned about `pyautogui` and Phase 2 learned about `pygetwindow`, now enforced for free:

```
hitl/repair.py   # pure: load dump, crop, rewrite YAML, validate. No tkinter.
hitl/app.py      # CustomTkinter window. Imported by nothing except __main__.
hitl/__main__.py # python -m hitl
```

Tests import `repair.py` only. Add the guard that `tests/test_seam.py` already has for `engine.runner` and `engine.run`: importing `hitl.repair` must not pull in `tkinter` or `customtkinter`. Install python-tk when you want to *look* at the window, not to run the suite.

### 4. Prove the crop with a round-trip, not a pixel comparison

Acceptance 3.2 #2 asks for pixel-identity between the crop and the source region. Go one better, because it costs one line and catches strictly more:

```python
box = pyscreeze.locate(str(new_crop), str(source_screenshot), confidence=0.8)
assert (box.left, box.top) == (crop_x, crop_y)
```

Crop a region, then locate the crop in the image it came from and assert it comes back **at the coordinates you cropped from**. Pixel equality proves the bytes match; this proves the coordinate space is right end to end, which is the bug this tool is actually prone to. It is also acceptance 3.3 #5 in miniature.

### 5. `missing_assets` is the one permitted edit to Phase 1 code — land it first, alone

PR 3.3 needs targets like `dynamic/foo.png` to validate, and `missing_assets` currently does a flat `assets_dir.iterdir()`. Switch it to a recursive walk producing paths relative to the assets root.

Two things not to break: it must keep comparing against **real directory entries** rather than `Path.exists()` (that is what catches case mismatches on macOS and Windows), and `tests/test_models.py` already asserts that behaviour. Ship it as its own small commit ahead of the UI work so a regression there is unambiguous.

`assets/dynamic/` does not exist yet — PR 3.2 has to create it, and something needs to keep it in git.

### 6. Restore from bytes, not from the parse tree

Acceptance 3.3 #4 wants an invalid result to leave the file untouched. Read the original file's **text** before writing, and restore that text on failure. Do not "restore" by re-serialising the ruamel tree — that is the code path you are trying to prove is safe, so it is the last thing to trust when it has already produced a bad result.

### 7. Sharpen "comments survive" into a one-line diff

Acceptance 3.3 #2 says formatting elsewhere is byte-identical. State it as a test that is impossible to fudge: after a repair, the diff against the original is **exactly one line changed**. That single assertion covers comment preservation, `note:` survival, key order, quoting style, and indentation all at once — and it is the reason `ruamel.yaml` is mandated over PyYAML.

**Verified trap:** a naive `YAML()` round-trip of `configs/arena_v2.yaml` produces a nine-line diff, not one. Two causes, both configuration:

```python
yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096   # stop re-wrapping the long note: on await_battle_end
yaml.representer.add_representer(
    type(None),
    lambda r, d: r.represent_scalar("tag:yaml.org,2002:null", "null"),
)
```

Without `width=4096`, the long `note:` re-wraps. Without the null representer, `on_success: null` degrades to `on_success:` (twice). With both, a no-op round-trip is byte-identical and a real repair is a one-line diff. These settings live in `hitl/repair.py` and have their own regression test — do not "simplify" them.

### 8. Definition of done for this ticket

A dump generated from capture 05 can be opened, a fresh target cropped from it, and `configs/arena_v2.yaml` rewritten — with a one-line diff, passing validation, and the new crop provably locatable in the screenshot it came from. The GUI is the least interesting part of that sentence, which is the correct outcome.

## Scope

The single supported repair is: **a node's `target` points at a template that no longer matches, so replace it with a fresh crop of the same screenshot.**

**Out of scope, and worth being firm about:** adding or deleting nodes, editing edges, editing action types, a graph visualiser, live screen preview, testing the new crop against a live game, undo, and multi-node editing. Those turn a 300-line utility into a config IDE. If a repair needs any of them, the answer for now is "edit the YAML by hand".

---

## PR 3.1 — Crash dump viewer

**Status: DONE (written, unverified).** `hitl/app.py` + `python -m hitl`. Never opened on the build machine — `_tkinter` is missing. Smoke-test is a [Windows follow-up](#windows-follow-ups).

A standalone CustomTkinter window, launched by `python -m hitl` and completely independent of `main.py`. `customtkinter` is already a dependency in `requirements.txt` (not `requirements-dev.txt`).

- List dumps from `logs/dumps/`, newest first, labelled with timestamp, sequence name, and failed node.
- On selection, show the screenshot alongside the JSON context, rendered readably rather than as a raw dump: which node failed, what action, what target it was looking for, and the `visited` path that led there.
- Show the current target template image next to the screenshot. Being able to see the crop the bot was hunting for, right beside the screen it was hunting in, is usually enough to spot the problem instantly.

### Display the screenshot at 1:1

Dumps are **900×600 game-window captures** (Ticket 2), not full-desktop grabs, so they fit comfortably in a window on any modern monitor.

**Show them at 1:1 and do not implement zoom or scale-to-fit.** As long as displayed pixels map one-to-one onto image pixels, canvas coordinates are crop coordinates and there is no conversion to get wrong. Scaled display is the classic bug in this kind of tool — crops look correct in the UI, land tens of pixels off on disk, then fail to match at 0.8 confidence with no obvious cause. Not scaling is both simpler and safer.

Guard it rather than assuming it: if a loaded image is not 900×600, show a warning and still display it at 1:1 in a scrollable canvas. Never silently scale.

Display the pixel coordinates of the current selection in the UI regardless — it makes any coordinate bug immediately visible.

### Acceptance

1. Given a directory of dump pairs, all are listed newest first.
2. Selecting one shows the screenshot, the parsed context, and the existing target template.
3. A dump whose PNG is missing shows an error row instead of crashing. `write_crash_dump` captures the screen before writing anything, so it never produces a JSON without its PNG — but `logs/dumps/` is a directory humans copy files in and out of, so still handle it.

---

## PR 3.2 — Bounding box and crop

**Status: DONE.** Pure crop logic in `hitl/repair.py::crop_target`; canvas drag-select lives in `hitl/app.py`.

- Click-drag a rectangle over the displayed screenshot on a `tkinter` Canvas.
- Show the live selection size in image pixels (which, at 1:1, are canvas pixels).
- "Save Target" crops that region from the loaded image and writes it to `assets/dynamic/<node_name>_<YYYYMMDD-HHMMSS>.png`.

Named after the node and timestamp rather than a UUID. These filenames end up in a config a human reads and maintains; `dynamic/select_opponent_20260801-093144.png` is self-documenting and `dynamic/3f2a...png` is not. The timestamp keeps successive repairs of the same node from colliding, and leaves the previous crop on disk to fall back to.

Reject a zero-area or absurdly small selection with a message rather than writing a broken asset.

### Acceptance

1. A crop of a known region of a test image produces a file with exactly the expected dimensions.
2. The saved crop is pixel-identical to that region of the source image — assert on pixel content, not just size. This is the test that catches any coordinate drift between canvas and image.
3. A zero-area selection is rejected and writes nothing.

---

## PR 3.3 — Config mutation with `ruamel.yaml`

**Status: DONE.** `hitl/repair.py::rewrite_target` with the verified ruamel settings; restore-from-bytes on validation failure.

Rewrite the failed node's `target` in the original config.

1. Read `config_path` and `failed_node` from the dump JSON.
2. Load the YAML with `ruamel.yaml` in round-trip mode, set `nodes[failed_node]["target"]`, write it back.
3. Re-run validation (`engine.models` plus `missing_assets`) on the result. If it fails, restore the original text and show the error — never leave a broken config on disk.

### The target path

The new target must be **`dynamic/<name>.png`**, not `assets/dynamic/<name>.png`.

`ClickHandler._get_image_path` does `str(self.asset_path / image_name)`, so an `assets/`-prefixed value resolves to `assets/assets/dynamic/...` and never matches. Same trap as the top-level targets in Ticket 1. Subdirectories work fine here — `assets / "dynamic/foo.png"` resolves correctly.

**This requires a small change to `missing_assets` from PR 1.1.** It currently lists `assets_dir.iterdir()`, which will not see files inside `dynamic/`. Switch it to a recursive walk producing paths relative to the assets root, so both `arenaBattle.png` and `dynamic/foo.png` validate. Keep the case-sensitive comparison against real directory entries.

### Comments must survive

That is the entire reason `ruamel.yaml` is mandated over PyYAML. The `note:` fields and header comments in `arena_v2.yaml` are the documentation for how the sequence works; a tool that silently strips them on every repair makes the config worse each time it is used.

Assert this in a test — round-trip a config containing comments and check they are still present in the output.

### Review before it lands

Configs are in git, so `git diff configs/` after a repair is the review mechanism. Log the file path and the old and new target values so the change is traceable from the log file. Do not build an undo feature; `git checkout` is the undo.

### Acceptance

1. Applying a repair changes only the intended node's `target`.
2. Comments and formatting elsewhere in the file are byte-identical afterwards.
3. The rewritten config still passes validation and `missing_assets`, including for a target inside `dynamic/`.
4. A repair that would produce an invalid config leaves the file untouched and surfaces the error.
5. End-to-end on a supplied screenshot: load a dump, crop a new target, save, and confirm the new crop is found in that same screenshot by `pyscreeze.locate` at confidence 0.8. That last check is what proves the repair actually works, and it reuses the PR 1.4 harness.

---

## Note on the original draft's example

The draft used *"Failed looking for `assets/victory.png` at node `check_victory_screen`"*. `victory.png` exists in `assets/` but is referenced by zero lines of Python, and there is no victory or defeat detection anywhere in the Arena flow — v1 detects the end of a battle purely via `tapToContinue.png`. Use a node that actually exists, such as `select_opponent` looking for `arenaBattle.png`, so the demo is reproducible.

---

## Windows follow-ups

Everything below needs a machine with a display toolkit (and, for some items, the game). The pure repair core is tested on macOS, and as of 2026-08-01 **the window itself has been opened and driven** — see item 1 for exactly how much of it that proves.

### 1. Smoke-test the HITL window — DONE on macOS, with one human check left

`brew install python-tk@3.13` turned out to be all that stood between this Mac and the window. `customtkinter` went into the venv only; it stays out of `requirements-dev.txt` (tests never import `hitl.app`, and adding it would only make the seam violable). Having it installed makes the seam guard *stronger*, not weaker — before, `assert 'customtkinter' not in sys.modules` could pass simply because the package did not exist.

```text
brew install python-tk@3.13 && pip install customtkinter   # macOS
pip install -r requirements.txt                            # Windows, already includes it

python -m helper_scripts.make_sample_dump    # a real dump in logs/dumps/, no game needed
python -m helper_scripts.hitl_smoke          # drives the window, checks the six points below
python -m hitl                               # then look at it
```

All six points now pass mechanically — 20 assertions in `helper_scripts/hitl_smoke.py`, which constructs the real window, selects dumps, simulates the drag and applies a repair, then restores the config and deletes the crop it made:

1. Dumps under `logs/dumps/` are listed newest first, labelled with timestamp, sequence name, and failed node.
2. Selecting one shows the screenshot **at 1:1** (900×600 canvas pixels = image pixels), the parsed context, and the current target template image beside it.
3. Click-drag draws a rectangle; the toolbar shows `left / top / width / height` in image pixels.
4. **Save Target** writes `assets/dynamic/<node>_<YYYYMMDD-HHMMSS>.png`, rewrites the failed node's `target` to `dynamic/<that file>`, and leaves a one-line `git diff` on the config.
5. A dump whose PNG is missing shows an error in the context pane rather than crashing the window.
6. If a loaded image is not 900×600, a warning appears and the image is still shown at 1:1 in a scrollable canvas — never silently scaled.

**What this does not prove, and why it still matters.** The smoke script injects synthetic drag coordinates straight into the canvas handlers, so it steps over the one mapping a human uses: pointer position → canvas coordinate → image pixel. That is exactly where the scaling trap lives. **Someone still has to drag over a landmark with a real mouse and confirm the toolbar numbers are image pixels** — pick something whose position you can check independently, drag its bounding box, and verify the reported `left/top` against where it actually sits in the PNG. It also cannot judge layout, contrast or clipping. Open the window and look at it.

**The classic bug to watch for:** if crops look right in the UI but fail to match at confidence 0.8 afterwards, the window is scaling the screenshot. Report that immediately; do not "fix" it by adjusting confidence.

Two findings from the smoke run, neither fixed:

- **CustomTkinter warns on the target thumbnail.** `_show_target` hands a raw `ImageTk.PhotoImage` to a `CTkLabel`, which warns that it cannot scale it on a HiDPI display. Harmless — the thumbnail is informational and feeds no coordinates, and the screenshot canvas is a raw `tk.Canvas` that this does not touch. Switching to `CTkImage` would silence it by introducing scaling into the one tool whose entire discipline is not scaling, so it is left for the epic owner to call.
- **`pyscreeze.locate` returns the first match above the threshold in raster order, not the best one.** A crop taken at `top=228` located back at `top=227`, because that row scores 0.865 — over the 0.8 threshold and earlier in the scan. The crop was verified pixel-identical to its source region and OpenCV's argmax is exactly right, so this is the matcher's behaviour, not a crop bug. It applies equally to the live bot, which uses the same matcher. Assert crop round-trips with a small tolerance, not equality.

### 2. Capture 11 — realism check on the finished tool

Capture 11 is **not** a gate on Phase 3 shipping. What it uniquely gives you is a screen with something *unanticipated* on it. Once you have a dump from a real lost screen:

```text
python -m hitl
# select the capture-11 dump, crop a fresh target, Save Target
git diff configs/
python -m engine.validate configs/arena_v2.yaml
```

Confirm the new crop is found in that same dump PNG by eye and, if you want belt-and-braces, by a one-liner:

```text
python -c "import pyscreeze; print(pyscreeze.locate('assets/dynamic/<crop>.png', 'logs/dumps/<dump>.png', confidence=0.8))"
```

Shortcut to produce capture 11: a deliberately-failed live run — see [Ticket 2 → Windows follow-ups](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups).

### 3. Still open from Phases 1 and 2

- **Phase 1 live smoke run** — PR 1.3 acceptance #4. Unchanged.
- **Phase 2 live failure run** — PR 2.2 acceptance #2 (also delivers capture 11).
- **Captures 02 and 10** — 10 completes the gem-refill guard coverage.
- **`back_to_bastion()` unbounded ESC loop** — tracked in [Ticket 2 → Known risk, not fixed here](./Ticket_2_Phase2_Telemetry.md#known-risk-not-fixed-here). Needs its own ticket from the epic owner. **Do not fix it as a drive-by in Phase 3.**

---

## Deliverables

```
engine/models.py               # missing_assets walks recursively (posix-relative paths)
assets/dynamic/.gitkeep        # crop destination; kept in git
hitl/__init__.py
hitl/repair.py                 # load_dump, crop_target, rewrite_target, validate_config
hitl/app.py                    # CustomTkinter window — written, unverified without _tkinter
hitl/__main__.py               # python -m hitl
tests/test_repair.py           # fixture via 01/03/04/05 chain; one-line diff; crop round-trip; e2e
tests/test_seam.py             # + guard: hitl.repair imports without tkinter/customtkinter
tests/test_models.py           # + dynamic/ subdirectory coverage for missing_assets
```

`customtkinter` stays out of `requirements-dev.txt` on purpose. It is already in `requirements.txt` for the existing GUI. Do not add it to the dev set "so the window imports" — that would only make the seam easier to violate.
