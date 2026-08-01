"""Drive the HITL window without a human: python -m helper_scripts.hitl_smoke

Ticket 3 ships `hitl/app.py` with a six-point manual checklist, because the
build machine had no `_tkinter` and the window had never been opened. This runs
that checklist mechanically — it constructs the real window, selects dumps,
simulates the drag, and applies a repair, asserting the things that are easy to
get wrong and invisible in a screenshot (1:1 scaling above all).

It deliberately lives in helper_scripts/ and not tests/. Importing `hitl.app`
needs python-tk and customtkinter, which are intentionally absent from
`requirements-dev.txt` so the suite cannot drift into depending on a display.
Run this by hand wherever a toolkit exists:

    brew install python-tk@3.13 && pip install customtkinter   # macOS
    pip install -r requirements.txt                            # Windows

What it cannot check is whether the window *looks* right — nothing clipped,
readable contrast, sensible proportions. Open `python -m hitl` and look at it.

The repo is left exactly as it was found: the config is restored from the bytes
read before the run, and any crop written into assets/dynamic/ is removed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import messagebox

import numpy as np
import pyscreeze
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "assets"
DYNAMIC = ASSETS / "dynamic"
CONFIG = REPO_ROOT / "configs" / "arena_v2.yaml"

failures: list[str] = []
dialogs: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def event(x: int, y: int):
    return types.SimpleNamespace(x=x, y=y)


def make_dump(dumps_dir: Path, stem: str, size: tuple[int, int] | None) -> Path:
    """A minimal dump pair. `size=None` writes the JSON with no PNG beside it."""
    context = {
        "timestamp": stem,
        "outcome": "ABORTED",
        "config_path": "configs/arena_v2.yaml",
        "sequence_name": "synthetic",
        "failed_node": "open_battle_menu",
        "action": "CLICK_IMAGE",
        "target": "battleBTN.png",
        "note": None,
        "steps": 1,
        "visited": ["open_battle_menu"],
        "screenshot": f"{stem}.png",
        "region": None,
    }
    json_path = dumps_dir / f"{stem}.json"
    json_path.write_text(json.dumps(context), encoding="utf-8")
    if size is not None:
        Image.new("RGB", size, "darkred").save(dumps_dir / f"{stem}.png")
    return json_path


def main() -> int:
    if Path.cwd() != REPO_ROOT:
        print(f"Run this from the repository root ({REPO_ROOT}).")
        return 1

    messagebox.showinfo = lambda t, m: dialogs.append(("info", t, m))
    messagebox.showerror = lambda t, m: dialogs.append(("error", t, m))

    from hitl.app import HitlApp, _list_dumps

    dumps = _list_dumps(REPO_ROOT / "logs" / "dumps")
    if not dumps:
        print("No dumps in logs/dumps/. Run: python -m helper_scripts.make_sample_dump")
        return 1

    config_before = CONFIG.read_bytes()
    dynamic_before = {p.name for p in DYNAMIC.glob("*.png")}

    try:
        run_checklist(HitlApp, _list_dumps, dumps)
    finally:
        CONFIG.write_bytes(config_before)
        for path in DYNAMIC.glob("*.png"):
            if path.name not in dynamic_before:
                path.unlink()
        print("\nRepo restored: config reverted, new crops removed.")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("All checks passed. Now open `python -m hitl` and look at it — layout, "
          "contrast and clipping are the parts this cannot judge.")
    return 0


def run_checklist(HitlApp, _list_dumps, dumps: list[Path]) -> None:
    # --- 1. listing, 2. 1:1 display, 3. drag, 4. save -----------------------
    print("\nChecklist 1-4, against the real dump in logs/dumps/:")
    app = HitlApp()
    app.update()
    check("window constructs", True, f"{app.winfo_width()}x{app.winfo_height()}")

    labels = [w.cget("text") for w in app._list_widgets]
    check("dumps listed with timestamp | sequence | node",
          all(t.count("|") == 2 for t in labels), labels[0] if labels else "empty")

    mtimes = [p.stat().st_mtime for p in _list_dumps(app.dumps_dir)]
    check("newest first", mtimes == sorted(mtimes, reverse=True))

    app.select_dump(dumps[0])
    app.update()
    image = Image.open(app._dump.png_path)
    check("screenshot shown 1:1 — photo pixels equal image pixels",
          (app._photo.width(), app._photo.height()) == image.size,
          f"photo={app._photo.width()}x{app._photo.height()} image={image.size}")
    check("scrollregion equals image size",
          tuple(map(int, map(float, app.canvas.cget("scrollregion").split()))) ==
          (0, 0, *image.size))
    check("context pane shows the failed node",
          app._dump.failed_node in app.context_box.get("1.0", "end"))
    check("current target template rendered",
          app._target_photo is not None, app.target_label.cget("text"))

    box = pyscreeze.locate(str(ASSETS / "classicArena.png"),
                           str(app._dump.png_path), confidence=0.8)
    left, top = int(box.left), int(box.top)
    width, height = int(box.width), int(box.height)
    app._on_press(event(left, top))
    app._on_drag(event(left + width, top + height))
    app._on_release(event(left + width, top + height))
    app.update()
    check("drag records the dragged rectangle in image pixels",
          app._selection == (left, top, width, height), str(app._selection))
    check("rectangle drawn on the canvas", app._rect_id is not None)
    check("toolbar reports the same numbers",
          f"left={left} top={top} width={width} height={height}"
          in app.coords_label.cget("text"), app.coords_label.cget("text"))

    app.save_target()
    app.update()
    check("save reported success", dialogs and dialogs[-1][0] == "info",
          dialogs[-1][1] if dialogs else "no dialog")

    crops = sorted(DYNAMIC.glob(f"{app._dump.failed_node}_*.png"))
    check("crop written as <node>_<timestamp>.png", bool(crops),
          crops[-1].name if crops else "none")

    if crops:
        crop = crops[-1]
        check("crop is the dragged size",
              Image.open(crop).size == (width, height))

        source = Image.open(app._dump.png_path).convert("RGB").crop(
            (left, top, left + width, top + height)
        )
        check("crop is pixel-identical to the region dragged",
              np.array_equal(np.array(source),
                             np.array(Image.open(crop).convert("RGB"))))

        # Deliberately a tolerance, not equality. pyscreeze yields every match
        # scoring above the threshold in raster order and takes the first, not
        # the best — so a smooth neighbourhood one row up can score 0.86 and win
        # over the exact 1.0 match. That is how the live bot matches too. The
        # pixel-identity check above is what proves the crop itself is right.
        found = pyscreeze.locate(str(crop), str(app._dump.png_path), confidence=0.8)
        near = found is not None and abs(int(found.left) - left) <= 2 \
            and abs(int(found.top) - top) <= 2
        check("crop is found by the live matcher where it came from (±2px)",
              near, str(found))

    diff = subprocess.run(["git", "diff", "--unified=0", "--", "configs/"],
                          cwd=REPO_ROOT, capture_output=True, text=True).stdout
    changed = [l for l in diff.splitlines()
               if re.match(r"^[+-][^+-]", l)]
    check("config diff is exactly one line changed", len(changed) == 2,
          " / ".join(s.strip() for s in changed) or "no diff")
    check("new target is a dynamic/ path",
          any(l.startswith("+") and "dynamic/" in l for l in changed))

    app.destroy()

    # --- 5. missing PNG, 6. unexpected size ---------------------------------
    print("\nChecklist 5-6, against synthetic dumps:")
    with TemporaryDirectory() as tmp:
        tmp_dumps = Path(tmp)
        orphan = make_dump(tmp_dumps, "2020-01-01_00-00-00", size=None)
        odd = make_dump(tmp_dumps, "2020-01-02_00-00-00", size=(640, 480))

        app = HitlApp(dumps_dir=tmp_dumps)
        app.update()

        app.select_dump(orphan)
        app.update()
        text = app.context_box.get("1.0", "end")
        check("dump with a missing PNG shows an error and does not crash",
              "Error loading" in text, text.strip().splitlines()[0] if text.strip() else "")

        app.select_dump(odd)
        app.update()
        check("non-900x600 dump warns",
              "640x480" in app.size_warning.cget("text"),
              app.size_warning.cget("text"))
        check("non-900x600 dump is still shown 1:1, never scaled",
              (app._photo.width(), app._photo.height()) == (640, 480))
        app.destroy()


if __name__ == "__main__":
    sys.exit(main())
