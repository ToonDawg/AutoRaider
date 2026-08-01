"""Offline integration: replay Arena screenshots through the real config."""

from __future__ import annotations

import logging
from pathlib import Path

from engine.runner import Outcome, SequenceRunner
from engine.validate import load_config
from tests.screenshot_screen import ScreenshotScreen

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "assets"
SHOTS = REPO / "tests" / "screenshots"
CONFIG = REPO / "configs" / "arena_v2.yaml"

# Replay order for the happy path. Capture 02 (ad) is absent; close_popup_ads
# fails on 01 and continues via on_failure, which is the normal case.
REPLAY_ORDER = [
    "01_bastion.png",
    "03_battle_menu.png",
    "04_arena_mode_selection.png",
    "05_arena_opponent_list.png",
    "06_pre_battle_team.png",
    "07_loading_screen.png",
    "08_mid_battle.png",
    "09_battle_results.png",
]


def test_arena_screenshot_replay_reaches_completed():
    missing = [name for name in REPLAY_ORDER if not (SHOTS / name).is_file()]
    assert not missing, f"missing screenshots for replay: {missing}"

    config = load_config(CONFIG)
    screen = ScreenshotScreen(
        screenshots=[SHOTS / name for name in REPLAY_ORDER],
        assets_dir=ASSETS,
    )
    result = SequenceRunner(
        config,
        screen,
        logging.getLogger("test_replay"),
        sleep=lambda _: None,
    ).run()

    assert result.outcome is Outcome.COMPLETED, (
        f"replay aborted at {result.last_node}; visited={result.visited}; "
        f"calls={screen.calls}; index={screen.index}"
    )
    assert "start_battle" in result.visited
    assert "return_to_opponent_list" in result.visited
    assert "leave_refill_prompt" not in result.visited
