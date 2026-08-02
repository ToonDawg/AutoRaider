"""Drive configs/arena_v2.yaml with FakeScreen — no game required."""

from __future__ import annotations

import logging
from pathlib import Path

from engine.runner import Outcome, SequenceRunner
from engine.validate import load_config
from tests.fakes import FakeScreen

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "arena_v2.yaml"

PREAMBLE = [
    "close_popup_ads",
    "open_battle_menu",
    "open_arena_tab",
    "enter_classic_arena",
]

# One turn of the cycle. return_to_opponent_list feeds back into select_opponent.
BATTLE_LOOP = [
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


def test_arena_fights_until_tokens_run_out():
    """Three battles, then the refill prompt appears and the loop exits.

    This is the whole repeat mechanism: no counter anywhere, just a cycle whose
    only clean exit is the token guard. The count here comes from how many
    times the fake says the refill prompt is absent.
    """
    battles = 3
    config = load_config(CONFIG_PATH)
    screen = FakeScreen(
        {
            "exitAdd.png": [False],  # no ad — take on_failure -> open_battle_menu
            "battleBTN.png": [True],
            "arenaTab.png": [True],
            "classicArena.png": [True],
            "arenaBattle.png": [True] * (battles + 1),
            # tokens OK for three battles, then the refill prompt shows up
            "ArenaRefillGems.png": [False] * battles + [True],
            "arenaStart.png": [True] * battles,
            "tapToContinue.png": [True, True] * battles,  # wait then click, each
        }
    )
    result = SequenceRunner(
        config, screen, _logger(), sleep=lambda _: None
    ).run()

    assert result.outcome is Outcome.COMPLETED
    assert result.visited == (
        PREAMBLE
        + BATTLE_LOOP * battles
        + ["select_opponent", "check_out_of_tokens", "leave_refill_prompt"]
    )
    assert result.last_node == "leave_refill_prompt"
    assert result.visited.count("start_battle") == battles


def test_a_guard_that_never_fires_is_capped_not_infinite():
    """The loop's safety net. If `ArenaRefillGems.png` never matches — a stale
    crop, say — the cycle has no exit, and the run must end at max_steps with a
    crash dump rather than fighting forever.
    """
    config = load_config(CONFIG_PATH)
    max_steps = 40
    screen = FakeScreen(
        {
            "exitAdd.png": [False],
            "battleBTN.png": [True],
            "arenaTab.png": [True],
            "classicArena.png": [True],
            "arenaBattle.png": [True] * max_steps,
            "ArenaRefillGems.png": [False] * max_steps,
            "arenaStart.png": [True] * max_steps,
            "tapToContinue.png": [True] * (2 * max_steps),
        }
    )
    result = SequenceRunner(
        config, screen, _logger(), max_steps=max_steps, sleep=lambda _: None
    ).run()

    assert result.outcome is Outcome.STEP_LIMIT
    assert result.steps == max_steps


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
