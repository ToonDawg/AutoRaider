"""Drive configs/arena_v2.yaml with FakeScreen — no game required."""

from __future__ import annotations

import logging
from pathlib import Path

from engine.runner import Outcome, SequenceRunner
from engine.validate import load_config
from tests.fakes import FakeScreen

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "arena_v2.yaml"

HAPPY_PATH_VISITED = [
    "close_popup_ads",
    "open_battle_menu",
    "open_arena_tab",
    "enter_classic_arena",
    "select_opponent",
    "check_out_of_tokens",
    "start_battle",
    "await_battle_end",
    "dismiss_results",
    "return_to_opponent_list",
]


def _logger() -> logging.Logger:
    return logging.getLogger("test_arena_config")


def test_arena_config_loads_and_validates():
    config = load_config(CONFIG_PATH)
    assert config.start_node == "close_popup_ads"
    assert "select_opponent" in config.nodes


def test_arena_happy_path_with_fake_screen():
    config = load_config(CONFIG_PATH)
    screen = FakeScreen(
        {
            "exitAdd.png": [False],  # no ad — take on_failure -> open_battle_menu
            "battleBTN.png": [True],
            "arenaTab.png": [True],
            "classicArena.png": [True],
            "arenaBattle.png": [True],
            "ArenaRefillGems.png": [False],  # tokens OK -> start_battle
            "arenaStart.png": [True],
            "tapToContinue.png": [True, True],  # wait then click
        }
    )
    result = SequenceRunner(
        config, screen, _logger(), sleep=lambda _: None
    ).run()
    assert result.outcome is Outcome.COMPLETED
    assert result.visited == HAPPY_PATH_VISITED
    assert result.last_node == "return_to_opponent_list"


def test_arena_refill_guard_stops_before_start_battle():
    config = load_config(CONFIG_PATH)
    screen = FakeScreen(
        {
            "exitAdd.png": [False],
            "battleBTN.png": [True],
            "arenaTab.png": [True],
            "classicArena.png": [True],
            "arenaBattle.png": [True],
            "ArenaRefillGems.png": [True],  # refill prompt present
        }
    )
    result = SequenceRunner(
        config, screen, _logger(), sleep=lambda _: None
    ).run()
    assert result.outcome is Outcome.COMPLETED
    assert result.last_node == "leave_refill_prompt"
    assert "start_battle" not in result.visited
    assert "leave_refill_prompt" in result.visited
    # Never attempted to click arenaStart
    assert all(
        c.args[0] != "arenaStart.png"
        for c in screen.calls
        if c.method == "click_image"
    )
