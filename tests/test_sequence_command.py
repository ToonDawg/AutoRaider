"""SequenceCommand — the v1-app adapter. No game, no Windows, no display.

The sequence under test is a throwaway three-node YAML rather than
configs/arena_v2.yaml: `run_sequence` builds its own `SequenceRunner` with the
real `time.sleep`, so a config with settle times would charge those seconds to
the suite. The Arena graph itself is covered in test_arena_config.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from PIL import Image

from engine.sequence_command import ARENA_V2_CONFIG, SequenceCommand
from engine.validate import load_config
from tests.fakes import FakeClickHandler
from utils.exceptions import CancellationException

REGION = (500, 200, 900, 600)

MINI_SEQUENCE = """\
name: test sequence
start_node: open_battle_menu
nodes:
  open_battle_menu:
    action: CLICK_IMAGE
    target: battleBTN.png
    on_success: select_opponent

  select_opponent:
    action: CLICK_IMAGE
    target: arenaBattle.png
    on_success: leave

  leave:
    action: PRESS_KEY
    target: esc
    settle_seconds: 0
"""


def _logger() -> logging.Logger:
    return logging.getLogger("test_sequence_command")


def _image() -> Image.Image:
    return Image.new("RGB", (900, 600), "navy")


def _config_file(tmp_path: Path) -> Path:
    path = tmp_path / "mini.yaml"
    path.write_text(MINI_SEQUENCE, encoding="utf-8")
    return path


def _command(
    tmp_path: Path,
    click_handler: FakeClickHandler,
    repeat: int = 1,
    config_path: Path | None = None,
) -> SequenceCommand:
    return SequenceCommand(
        None,  # the adapter never touches `app`
        _logger(),
        click_handler,
        config_path or _config_file(tmp_path),
        repeat,
        grab_screen=_image,
        dumps_dir=tmp_path / "dumps",
    )


def _passing_handler(attempts: int = 1, **kwargs) -> FakeClickHandler:
    return FakeClickHandler(
        {
            "battleBTN.png": [True] * attempts,
            "arenaBattle.png": [True] * attempts,
        },
        **kwargs,
    )


def _methods(handler: FakeClickHandler) -> list[str]:
    return [c.method for c in handler.calls]


def _dumps(tmp_path: Path) -> list[str]:
    dumps_dir = tmp_path / "dumps"
    return sorted(p.suffix for p in dumps_dir.iterdir()) if dumps_dir.is_dir() else []


# --- registration -----------------------------------------------------------


def test_bind_constructs_from_the_three_arguments_the_factory_passes():
    """CommandFactory always calls (app, logger, click_handler). Binding the
    config path up front is what lets a v2 command register without the factory
    — shared with all eight v1 commands — having to change.
    """
    handler = FakeClickHandler()
    command = SequenceCommand.bind(ARENA_V2_CONFIG, repeat=5)(
        None, _logger(), handler
    )

    assert isinstance(command, SequenceCommand)
    assert command.config_path == ARENA_V2_CONFIG
    assert command.config_paths == [ARENA_V2_CONFIG]
    assert command.repeat == 5
    assert command.click_handler is handler
    assert command.stop_on_failure is True


def test_bind_list_runs_each_config_best_effort(tmp_path: Path):
    """Rewards / Daily Quests pass a list; one failed subflow must not abort
    the rest.
    """
    good = tmp_path / "good.yaml"
    good.write_text(MINI_SEQUENCE, encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "name: bad\nstart_node: only\nnodes:\n"
        "  only:\n    action: CLICK_IMAGE\n    target: missing.png\n",
        encoding="utf-8",
    )
    also_good = tmp_path / "also_good.yaml"
    also_good.write_text(MINI_SEQUENCE, encoding="utf-8")

    handler = FakeClickHandler(
        {
            "battleBTN.png": [True, True],
            "arenaBattle.png": [True, True],
            "missing.png": [False],
        }
    )
    command = SequenceCommand(
        None,
        _logger(),
        handler,
        [good, bad, also_good],
        grab_screen=_image,
        dumps_dir=tmp_path / "dumps",
        stop_on_failure=False,
    )
    command.execute()

    # good + also_good each clean up; bad dumps and cleans up too
    assert _methods(handler).count("back_to_bastion") == 3
    assert _dumps(tmp_path) == [".json", ".png"]
    clicks = [c.args[0] for c in handler.calls if c.method == "click_image"]
    assert clicks.count("battleBTN.png") == 2
    assert "missing.png" in clicks


def test_the_bound_arena_config_exists_and_validates():
    """Guards against registering a path that only resolves on someone's box."""
    config = load_config(ARENA_V2_CONFIG)
    assert config.start_node in config.nodes


# --- a normal run -----------------------------------------------------------


def test_a_completed_run_cleans_up_exactly_like_v1(tmp_path: Path):
    handler = _passing_handler()
    _command(tmp_path, handler).execute()

    assert _methods(handler)[-2:] == ["back_to_bastion", "delete_popup"]
    assert _dumps(tmp_path) == [], "a completed run must not leave a dump"


def test_repeat_runs_the_sequence_that_many_times(tmp_path: Path):
    """The counter lives on the caller, not in the YAML — Ticket 4, option 1."""
    handler = _passing_handler(attempts=3)
    _command(tmp_path, handler, repeat=3).execute()

    assert _methods(handler).count("back_to_bastion") == 3
    assert [c.args[0] for c in handler.calls if c.method == "click_image"] == [
        "battleBTN.png",
        "arenaBattle.png",
    ] * 3


# --- failure ----------------------------------------------------------------


def test_a_failed_attempt_dumps_and_skips_the_remaining_attempts(tmp_path: Path):
    # Attempt 1 completes; attempt 2 cannot find an opponent, and that node has
    # no on_failure edge, so the run aborts with the bot in an unknown state.
    handler = FakeClickHandler(
        {
            "battleBTN.png": [True, True, True],
            "arenaBattle.png": [True, False, True],
        }
    )
    _command(tmp_path, handler, repeat=3).execute()

    assert _methods(handler).count("back_to_bastion") == 2, (
        "the third attempt must not start — the previous one left the game "
        "somewhere the sequence does not know how to start from"
    )
    assert _dumps(tmp_path) == [".json", ".png"]


def test_the_dump_records_the_region_the_matcher_searched(tmp_path: Path):
    handler = FakeClickHandler({"battleBTN.png": [False]}, region=REGION)
    _command(tmp_path, handler).execute()

    dumps_dir = tmp_path / "dumps"
    context = json.loads(
        next(dumps_dir.glob("*.json")).read_text(encoding="utf-8")
    )
    assert context["region"] == list(REGION)
    assert context["failed_node"] == "open_battle_menu"


def test_a_full_screen_run_is_warned_about(tmp_path: Path, caplog):
    """The app builds ClickHandler with no region_provider, so an in-app run
    searches the whole desktop while `python -m engine.run` searches the game
    window. Until that gap is closed the log has to say which one happened.
    """
    with caplog.at_level(logging.WARNING, logger="test_sequence_command"):
        _command(tmp_path, _passing_handler()).execute()

    assert "FULL SCREEN" in caplog.text


def test_an_unloadable_config_is_logged_rather_than_raised(tmp_path: Path, caplog):
    handler = FakeClickHandler()
    command = _command(tmp_path, handler, config_path=tmp_path / "absent.yaml")

    with caplog.at_level(logging.ERROR, logger="test_sequence_command"):
        command.execute()

    assert "Could not load sequence" in caplog.text
    assert handler.calls == [], "a config that will not load must not move the mouse"


# --- cancellation -----------------------------------------------------------


def test_cancellation_propagates_out_of_execute(tmp_path: Path):
    """F2 sets cancel_flag on the app's ClickHandler, which raises from inside
    the click. Swallowing it here would start the next repeat attempt.
    """
    handler = _passing_handler(attempts=2)
    handler.raise_on["click_image"] = CancellationException("Task cancelled by user.")

    with pytest.raises(CancellationException):
        _command(tmp_path, handler, repeat=2).execute()

    assert _methods(handler).count("click_image") == 1
    assert "back_to_bastion" in _methods(handler), (
        "cleanup still has to run on a cancel — run_sequence recovers in a finally"
    )
    assert _dumps(tmp_path) == [], "a user cancel is not a crash worth dumping"
