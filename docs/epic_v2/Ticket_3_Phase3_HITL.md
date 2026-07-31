# Phase 3: Human-In-The-Loop Authoring UI

**Goal:** repair a broken image target by re-cropping it from the crash screenshot, without opening an editor.

**Depends on:** Phase 2 (crash dumps exist and record `config_path` + `failed_node`).

**Game access needed?** No. **Screenshots needed? Yes — this is a hard blocker.** The tool is unbuildable and untestable without realistic 900×600 game-window captures. See [Screenshots Required](./Screenshots_Required.md), captures 1–11.

## Scope

The single supported repair is: **a node's `target` points at a template that no longer matches, so replace it with a fresh crop of the same screenshot.**

**Out of scope, and worth being firm about:** adding or deleting nodes, editing edges, editing action types, a graph visualiser, live screen preview, testing the new crop against a live game, undo, and multi-node editing. Those turn a 300-line utility into a config IDE. If a repair needs any of them, the answer for now is "edit the YAML by hand".

---

## PR 3.1 — Crash dump viewer

A standalone CustomTkinter window, launched by `python -m hitl` and completely independent of `main.py`. `customtkinter` is already a dependency.

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
3. A dump whose PNG is missing shows an error row instead of crashing.

---

## PR 3.2 — Bounding box and crop

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
