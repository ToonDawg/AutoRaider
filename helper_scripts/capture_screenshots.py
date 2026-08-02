"""Capture full-window screenshots while a v1 command runs.

Generalises the Arena-only capture script: pass a command key and optional
locate→filename map, and screenshots land under tests/screenshots/<task>/.

Usage (on the Windows game machine)::

    python helper_scripts/capture_screenshots.py iron_twins
    python helper_scripts/capture_screenshots.py daily_ten_classic_arena --task arena

Without ``--map``, every successful ``_locate_image`` / ``click_image`` /
``wait_for_image`` writes ``NN_<stem>.png`` the first time that template is
seen. Pass ``--map`` JSON to pin specific templates to specific filenames
(Arena's original behaviour).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from tkinter import Tk

import pygetwindow as gw
from PIL import ImageGrab

from app.pyAutoRaid import AutoRaider
from utils.command_factory import CommandKeys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS_ROOT = REPO_ROOT / "tests" / "screenshots"

# Built-in maps for known tasks. Keys are template filenames; values are
# output basenames under tests/screenshots/<task>/.
TASK_MAPS: dict[str, dict[str, str]] = {
    "arena": {
        "battleBTN.png": "01_bastion.png",
        "exitAdd.png": "02_bastion_ad.png",
        "arenaTab.png": "03_battle_menu.png",
        "classicArena.png": "04_arena_mode_selection.png",
        "arenaBattle.png": "05_arena_opponent_list.png",
        "arenaStart.png": "06_pre_battle_team.png",
        "tapToContinue.png": "09_battle_results.png",
        "ArenaRefillGems.png": "10_out_of_tokens.png",
    },
    "iron_twins": {
        "battleBTN.png": "01_bastion.png",
        "dungeons.png": "02_dungeons.png",
        "ironTwinsDungeon.png": "03_iron_twins.png",
        "ironTwinsStage15.png": "04_stage_15.png",
        "multiBattleButton.png": "05_multi_battle.png",
        "startMultiBattle.png": "06_start_multi.png",
        "multiBattleComplete.png": "07_multi_complete.png",
    },
    "tag_team_arena": {
        "battleBTN.png": "01_bastion.png",
        "arenaTab.png": "02_battle_menu.png",
        "TagTeamArena.png": "03_tag_team.png",
        "tagArenaBattle.png": "04_opponent.png",
        "tagArenaStart.png": "05_start.png",
        "tapToContinue.png": "06_results.png",
        "ArenaRefillGems.png": "07_out_of_tokens.png",
    },
}


def capture_screenshot(out_dir: Path, name: str) -> None:
    try:
        w = gw.getWindowsWithTitle("Raid: Shadow Legends")[0]
        im = ImageGrab.grab(bbox=(w.left, w.top, w.left + w.width, w.top + w.height))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / name
        im.save(out)
        print(f"Captured: {out} ({im.size[0]}x{im.size[1]})")
    except Exception as e:
        print(f"Failed to capture {name}: {e}")


def _install_hooks(
    click_handler: object,
    out_dir: Path,
    locate_targets: dict[str, str] | None,
) -> None:
    """Monkey-patch locate/click/wait to dump the game window on first hit."""
    captured: set[str] = set()
    auto_index = [0]

    def _name_for(image_name: str) -> str | None:
        if locate_targets is not None:
            return locate_targets.get(image_name)
        stem = Path(image_name).stem
        auto_index[0] += 1
        return f"{auto_index[0]:02d}_{stem}.png"

    def _maybe_capture(image_name: str) -> None:
        if image_name in captured:
            return
        name = _name_for(image_name)
        if name is None:
            return
        capture_screenshot(out_dir, name)
        captured.add(image_name)

    original_locate = click_handler._locate_image

    def wrapped_locate(image_name, description=""):
        res = original_locate(image_name, description)
        if res:
            _maybe_capture(image_name)
        return res

    click_handler._locate_image = wrapped_locate

    original_locate_all = click_handler._locate_all_buttons

    def wrapped_locate_all(image_name):
        res = original_locate_all(image_name)
        if res:
            _maybe_capture(image_name)
        return res

    click_handler._locate_all_buttons = wrapped_locate_all

    original_click = click_handler.click_image

    def wrapped_click_image(image_name, description="", retries=1, delay=1, **kwargs):
        if image_name not in captured and (
            locate_targets is None or image_name in locate_targets
        ):
            # Capture the screen *before* the click changes it.
            _maybe_capture(image_name)
        return original_click(
            image_name, description=description, retries=retries, delay=delay, **kwargs
        )

    click_handler.click_image = wrapped_click_image

    original_wait = click_handler.wait_for_image

    def wrapped_wait_for_image(
        image_name, description="", timeout=120, check_interval=2
    ):
        res = original_wait(image_name, description, timeout, check_interval)
        if res:
            _maybe_capture(image_name)
        return res

    click_handler.wait_for_image = wrapped_wait_for_image


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture full-window screenshots while a v1 command runs."
    )
    parser.add_argument(
        "command",
        help="CommandKeys value, e.g. iron_twins or daily_ten_classic_arena",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Output folder name under tests/screenshots/ (default: command key)",
    )
    parser.add_argument(
        "--map",
        default=None,
        help="JSON file mapping template → output basename, or a built-in task "
        f"name ({', '.join(TASK_MAPS)})",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-name every first-seen template (default when --map omitted "
        "and no built-in map matches --task)",
    )
    args = parser.parse_args()

    key = CommandKeys.from_string(args.command)
    if key is None:
        raise SystemExit(
            f"Unknown command {args.command!r}. "
            f"Known: {[m.value for m in CommandKeys]}"
        )

    task = args.task or args.command
    # Arena captures historically lived flat under tests/screenshots/ (no
    # subdirectory) — keep that so existing replay fixtures keep resolving.
    if task in ("arena", "daily_ten_classic_arena") and args.task != "arena_v2":
        out_dir = SCREENSHOTS_ROOT
    else:
        out_dir = SCREENSHOTS_ROOT / task

    locate_targets: dict[str, str] | None
    if args.map and args.map.endswith(".json"):
        locate_targets = json.loads(Path(args.map).read_text(encoding="utf-8"))
    elif args.map and args.map in TASK_MAPS:
        locate_targets = TASK_MAPS[args.map]
    elif not args.auto and task in TASK_MAPS:
        locate_targets = TASK_MAPS[task]
    else:
        locate_targets = None  # auto-name

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ScreenShotBot")

    root = Tk()
    root.withdraw()

    app = AutoRaider(root, logger)
    app.make_sure_raid_is_open()
    app.configure_game_window()
    time.sleep(3)

    _install_hooks(app.click_handler, out_dir, locate_targets)

    command = app.command_factory.get_command(key)
    if command is None:
        raise SystemExit(f"Factory returned no command for {key}")

    print(f"Starting {key.value} — screenshots → {out_dir}")
    command.execute()
    print(f"Run completed. Check {out_dir}")


if __name__ == "__main__":
    main()
