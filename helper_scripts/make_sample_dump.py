"""Write a real crash dump into logs/dumps/ without the game.

    python -m helper_scripts.make_sample_dump

The HITL window reads `logs/dumps/`, so it has nothing to show on a machine
that has never run the bot. The dump fixture in tests/test_repair.py cannot
fill that gap: it writes into pytest's tmp_path and points `config_path` at a
throwaway copy of the config, so a repair made against it would edit a temp
file and vanish.

This produces the real thing instead — the same `run_sequence` and
`write_crash_dump` the live bot uses, driven over the delivered captures, with
`config_path` pointing at the committed `configs/arena_v2.yaml`. Saving a
target from the window therefore leaves a genuine one-line diff, which is the
behaviour worth smoke-testing. Revert it with `git checkout configs/`.

The failure is honest rather than sabotaged: the capture chain simply stops
before the Classic Arena screen, so `enter_classic_arena` cannot find
`classicArena.png`. The dump screenshot is capture 04, which is the screen
that button is actually on — the everyday case the HITL tool exists for, where
a template has stopped matching a screen it should match.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PIL import Image

from engine.dump import DUMPS_DIR
from engine.run import run_sequence
from engine.runner import Outcome
from engine.validate import load_config
from tests.screenshot_screen import ScreenshotScreen

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "assets"
SHOTS = REPO_ROOT / "tests" / "screenshots"

# Recorded relative, exactly as `python -m engine.run configs/arena_v2.yaml`
# records it on a live run, so the window resolves the path the same way here
# as it will in the field.
CONFIG_REL = Path("configs") / "arena_v2.yaml"

# Stops one screen short of the Classic Arena selection, so the run aborts at
# enter_classic_arena with capture 04 still on screen.
CHAIN = ["01_bastion.png", "03_battle_menu.png"]
STUCK_ON = "04_arena_mode_selection.png"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s - %(message)s", stream=sys.stderr
    )
    logger = logging.getLogger("make_sample_dump")

    if Path.cwd() != REPO_ROOT:
        # engine.dump and hitl.app both resolve logs/dumps against the CWD.
        logger.error("Run this from the repository root (%s).", REPO_ROOT)
        return 1

    missing = [n for n in CHAIN + [STUCK_ON] if not (SHOTS / n).is_file()]
    if missing:
        logger.error("Missing captures: %s", ", ".join(missing))
        return 1

    dumps_dir = DUMPS_DIR
    result = run_sequence(
        load_config(CONFIG_REL),
        CONFIG_REL,
        ScreenshotScreen([SHOTS / name for name in CHAIN], assets_dir=ASSETS),
        logger,
        grab_screen=lambda: Image.open(SHOTS / STUCK_ON),
        region=(500, 200, 900, 600),
        recover=lambda: None,
        dumps_dir=dumps_dir,
    )

    if result.outcome is Outcome.COMPLETED:
        logger.error(
            "The replay completed, so nothing was dumped. The capture chain no "
            "longer stops where this script assumes it does."
        )
        return 1

    newest = max(dumps_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    print(f"\nWrote {newest} and {newest.with_suffix('.png')}")
    print(f"Outcome {result.outcome.value} at node {result.last_node!r}.")
    print("\nNow run:  python -m hitl")
    print("Undo any repair you save with:  git checkout configs/ && rm -rf assets/dynamic/*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
