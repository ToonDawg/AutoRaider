"""Graph tests for the migrated v2 configs — FakeScreen only, no pixels."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from engine.runner import Outcome, SequenceRunner
from engine.validate import load_config
from tests.fakes import FakeScreen

CONFIGS = Path("configs")


def _logger() -> logging.Logger:
    return logging.getLogger("test_v2_configs")


def _run(config_path: Path, results: dict[str, list[bool]], **kwargs):
    config = load_config(config_path)
    screen = FakeScreen(results)
    sleeps: list[float] = []
    result = SequenceRunner(
        config, screen, _logger(), sleep=sleeps.append, **kwargs
    ).run()
    return result, screen


@pytest.mark.parametrize(
    "path",
    [
        CONFIGS / "iron_twins_v2.yaml",
        CONFIGS / "tag_team_arena_v2.yaml",
        CONFIGS / "faction_wars_v2.yaml",
        CONFIGS / "clan_boss_v2.yaml",
        CONFIGS / "doom_tower_v2.yaml",
        CONFIGS / "rewards" / "market_v2.yaml",
        CONFIGS / "rewards" / "clan_v2.yaml",
        CONFIGS / "rewards" / "gem_mine_v2.yaml",
        CONFIGS / "rewards" / "guardian_ring_v2.yaml",
        CONFIGS / "rewards" / "quest_claims_v2.yaml",
        CONFIGS / "rewards" / "shop_v2.yaml",
        CONFIGS / "rewards" / "timed_rewards_v2.yaml",
        CONFIGS / "rewards" / "inbox_v2.yaml",
        CONFIGS / "daily_quests" / "campaign_v2.yaml",
        CONFIGS / "daily_quests" / "summon_v2.yaml",
        CONFIGS / "daily_quests" / "tavern_v2.yaml",
        CONFIGS / "arena_v2.yaml",
    ],
)
def test_config_loads_and_validates(path: Path):
    config = load_config(path)
    assert config.start_node in config.nodes
    assert config.name


def test_iron_twins_happy_path_uses_bottom_match_and_wait_until_disappears():
    result, screen = _run(
        CONFIGS / "iron_twins_v2.yaml",
        {
            "exitAdd.png": [False],
            "battleBTN.png": [True],
            "dungeons.png": [True],
            "ironTwinsDungeon.png": [True],
            "ironTwinsStage15.png": [True, False],  # click, then absent
            "multiBattleButton.png": [True],
            "startMultiBattle.png": [True],
            "turnOffMultiBattle.png": [True, True],  # wait_for, then disappears
            "multiBattleComplete.png": [True],
        },
    )
    assert result.outcome is Outcome.COMPLETED
    click = next(c for c in screen.calls if c.method == "click_image"
                 and c.args[0] == "ironTwinsStage15.png")
    assert click.kwargs["match"] == "bottom"
    assert any(c.method == "wait_until_disappears" for c in screen.calls)


def test_tag_team_swipes_when_no_opponent_then_exits_on_refill():
    result, screen = _run(
        CONFIGS / "tag_team_arena_v2.yaml",
        {
            "exitAdd.png": [False],
            "battleBTN.png": [True],
            "arenaTab.png": [True],
            "TagTeamArena.png": [True],
            "tagArenaBattle.png": [False, True],  # miss, then hit after scroll
            "arenaConfirm.png": [False],
            "ArenaRefillGems.png": [True],
        },
    )
    assert result.outcome is Outcome.COMPLETED
    assert any(c.method == "swipe" and c.args[0] == "up" for c in screen.calls)
    assert "leave_refill_prompt" in result.visited


def test_faction_wars_banner_uses_offset():
    result, screen = _run(
        CONFIGS / "faction_wars_v2.yaml",
        {
            "exitAdd.png": [False],
            "battleBTN.png": [True],
            "factionWars.png": [True],
            "FactionWarBanner.png": [False],  # none on right → swipe left path
        },
        max_steps=20,
    )
    assert result.outcome is Outcome.COMPLETED
    assert "done" in result.visited
    assert any(c.method == "swipe" for c in screen.calls)


def test_inbox_collect_passes_offset():
    result, screen = _run(
        CONFIGS / "rewards" / "inbox_v2.yaml",
        {
            "inbox_brew.png": [False],
            "inbox_purple_forge.png": [False],
            "inbox_yellow_forge.png": [False],
            "inbox_coin.png": [False],
            "inbox_potion.png": [False],
        },
    )
    assert result.outcome is Outcome.COMPLETED
    # press_key opens inbox; every collect attempt carries the +250 offset
    clicks = [c for c in screen.calls if c.method == "click_image"]
    assert clicks
    assert all(c.kwargs["offset"] == (250, 0) for c in clicks)


def test_gem_mine_uses_click_point():
    result, screen = _run(CONFIGS / "rewards" / "gem_mine_v2.yaml", {})
    assert result.outcome is Outcome.COMPLETED
    points = [c for c in screen.calls if c.method == "click_point"]
    assert [(c.args[0], c.args[1]) for c in points] == [(800, 560), (800, 560)]
