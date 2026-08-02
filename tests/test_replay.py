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

# Capture 02 (ad) is absent; close_popup_ads fails on 01 and continues via
# on_failure, which is the normal case.
PREAMBLE = [
    "01_bastion.png",
    "03_battle_menu.png",
    "04_arena_mode_selection.png",
]

# One battle, starting from the opponent list. ESC at the end lands us back on
# the list, so replaying this twice is what the graph's cycle actually sees.
ONE_BATTLE = [
    "05_arena_opponent_list.png",
    "06_pre_battle_team.png",
    "07_loading_screen.png",
    "08_mid_battle.png",
    "09_battle_results.png",
]

BATTLES = 2
REPLAY_ORDER = PREAMBLE + ONE_BATTLE * BATTLES


def test_arena_screenshot_replay_loops_over_real_frames():
    """Every target matches its real frame, in graph order, twice round the loop.

    The run cannot reach COMPLETED here, and that is not a defect in the config:
    the only clean exit is the refill prompt, and capture 10 has not been
    delivered, so the corpus contains no out-of-tokens frame. It therefore ends
    the one honest way it can — the screenshots run dry and `select_opponent`
    finds no Battle button. `test_arena_config.py` covers the clean exit against
    FakeScreen; this test covers the templates against real pixels.
    """
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

    context = (
        f"outcome={result.outcome} last_node={result.last_node}; "
        f"visited={result.visited}; calls={screen.calls}; index={screen.index}"
    )
    assert result.visited.count("start_battle") == BATTLES, context
    assert result.visited.count("return_to_opponent_list") == BATTLES, context
    assert result.visited.count("select_opponent") == BATTLES + 1, context

    # Ran out of screenshots rather than out of tokens.
    assert result.outcome is Outcome.ABORTED, context
    assert result.last_node == "select_opponent", context
    assert screen.current is None, context
    assert "leave_refill_prompt" not in result.visited, context
