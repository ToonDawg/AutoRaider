import time
import logging
from pathlib import Path
from tkinter import Tk

import pygetwindow as gw
from PIL import ImageGrab

from app.pyAutoRaid import AutoRaider
from Modules.arena.DailyTenArenaCommand import ClassicArenaCommand

# Repo-relative output — works regardless of where the checkout lives.
REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = REPO_ROOT / "tests" / "screenshots"


def capture_screenshot(name: str) -> None:
    try:
        w = gw.getWindowsWithTitle("Raid: Shadow Legends")[0]
        im = ImageGrab.grab(bbox=(w.left, w.top, w.left + w.width, w.top + w.height))
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        out = SCREENSHOT_DIR / name
        im.save(out)
        print(f"Captured: {out} ({im.size[0]}x{im.size[1]})")
    except Exception as e:
        print(f"Failed to capture {name}: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ScreenShotBot")

    root = Tk()
    root.withdraw()

    app = AutoRaider(root, logger)
    app.make_sure_raid_is_open()
    app.configure_game_window()
    time.sleep(3)

    # Track what we've captured to avoid duplicates
    captured = set()

    # Intercept _locate_image for screens we click on
    original_locate = app.click_handler._locate_image
    locate_targets = {
        "battleBTN.png": "01_bastion.png",
        "exitAdd.png": "02_bastion_ad.png",
        "arenaTab.png": "03_battle_menu.png",
        "classicArena.png": "04_arena_mode_selection.png",
        "ArenaRefillGems.png": "10_out_of_tokens.png",
    }

    def wrapped_locate(image_name, description=""):
        res = original_locate(image_name, description)
        if res and image_name in locate_targets and image_name not in captured:
            capture_screenshot(locate_targets[image_name])
            captured.add(image_name)
        return res

    app.click_handler._locate_image = wrapped_locate

    # Intercept _locate_all_buttons for the arena battle list
    original_locate_all = app.click_handler._locate_all_buttons

    def wrapped_locate_all(image_name):
        res = original_locate_all(image_name)
        if res and image_name == "arenaBattle.png" and "arenaBattle.png" not in captured:
            capture_screenshot("05_arena_opponent_list.png")
            captured.add("arenaBattle.png")
        return res

    app.click_handler._locate_all_buttons = wrapped_locate_all

    # Intercept click_image to capture pre-battle team right before starting
    original_click_image = app.click_handler.click_image

    def wrapped_click_image(image_name, description="", retries=1, delay=1):
        if image_name == "arenaStart.png" and image_name not in captured:
            capture_screenshot("06_pre_battle_team.png")
            captured.add(image_name)
        return original_click_image(image_name, description, retries, delay)

    app.click_handler.click_image = wrapped_click_image

    # Intercept wait_for_image to capture during and after battle
    original_wait = app.click_handler.wait_for_image

    def wrapped_wait_for_image(image_name, description="", timeout=120, check_interval=2):
        if image_name == "tapToContinue.png":
            # Right after battle start, game is loading
            time.sleep(4)
            capture_screenshot("07_loading_screen.png")

            # Wait a bit more for the actual battle to be underway
            time.sleep(10)
            capture_screenshot("08_mid_battle.png")

            # Wait for battle to finish
            res = original_wait(image_name, description, timeout, check_interval)
            if res:
                # Give UI a sec to settle
                time.sleep(1)
                capture_screenshot("09_battle_results.png")
            return res

        return original_wait(image_name, description, timeout, check_interval)

    app.click_handler.wait_for_image = wrapped_wait_for_image

    cmd = ClassicArenaCommand(app, logger, app.click_handler)

    print("Starting arena command to collect screenshots...")
    # Execute just 1 battle to grab most of what we need
    cmd.execute(count=1)

    print(f"Run completed. Check {SCREENSHOT_DIR}")
