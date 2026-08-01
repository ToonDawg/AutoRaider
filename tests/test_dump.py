"""Crash dump tests — no game, no Windows, no display.

`grab_screen` is a synthetic PIL image throughout, so these run anywhere.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image

from engine.dump import write_crash_dump
from engine.models import Action, ActionNode, SequenceConfig
from engine.run import run_sequence
from engine.runner import Outcome, RunResult
from tests.fakes import FakeScreen

CONFIG_PATH = Path("configs") / "arena_v2.yaml"
REGION = (500, 200, 900, 600)


def _logger() -> logging.Logger:
    return logging.getLogger("test_dump")


def _image() -> Image.Image:
    return Image.new("RGB", (900, 600), "navy")


def _config() -> SequenceConfig:
    """A cut-down stand-in for the Arena graph: two clicks then an ESC."""
    return SequenceConfig(
        name="Arena - single classic battle",
        start_node="open_battle_menu",
        nodes={
            "open_battle_menu": ActionNode(
                action=Action.CLICK_IMAGE,
                target="battleBTN.png",
                on_success="select_opponent",
            ),
            "select_opponent": ActionNode(
                action=Action.CLICK_IMAGE,
                target="arenaBattle.png",
                note="Clicks the best single match.",
                on_success="leave",
                # on_failure omitted: a miss here means the bot is lost.
            ),
            "leave": ActionNode(
                action=Action.PRESS_KEY,
                target="esc",
                settle_seconds=0,
            ),
        },
    )


def _result(
    outcome: Outcome = Outcome.ABORTED,
    last_node: str = "select_opponent",
) -> RunResult:
    return RunResult(
        outcome=outcome,
        last_node=last_node,
        steps=2,
        visited=["open_battle_menu", "select_opponent"],
    )


def _write(tmp_path: Path, result: RunResult, **kwargs) -> Path | None:
    kwargs.setdefault("grab_screen", _image)
    kwargs.setdefault("region", REGION)
    kwargs.setdefault("logger", _logger())
    return write_crash_dump(
        _config(),
        result,
        CONFIG_PATH,
        tmp_path,
        kwargs.pop("grab_screen"),
        **kwargs,
    )


# --- PR 2.1: the generator ---------------------------------------------------


def test_aborted_run_writes_png_and_json_sharing_a_stem(tmp_path: Path):
    json_path = _write(tmp_path, _result())

    assert json_path is not None
    png_path = json_path.with_suffix(".png")
    assert png_path.is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [json_path.name, png_path.name]
    )

    context = json.loads(json_path.read_text(encoding="utf-8"))
    assert context["screenshot"] == png_path.name
    assert Image.open(png_path).size == (900, 600)


def test_json_records_the_failed_node_and_the_path_taken(tmp_path: Path):
    json_path = _write(tmp_path, _result())
    assert json_path is not None
    context = json.loads(json_path.read_text(encoding="utf-8"))

    assert context["outcome"] == "ABORTED"
    assert context["failed_node"] == "select_opponent"
    assert context["action"] == "CLICK_IMAGE"
    assert context["target"] == "arenaBattle.png"
    assert context["note"] == "Clicks the best single match."
    assert context["on_success"] == "leave"
    assert context["on_failure"] is None
    assert context["steps"] == 2
    assert context["visited"] == ["open_battle_menu", "select_opponent"]

    # Phase 3 rewrites the failed node in this file, so both are required.
    assert context["config_path"] == "configs/arena_v2.yaml"
    assert context["sequence_name"] == "Arena - single classic battle"
    assert context["region"] == [500, 200, 900, 600]


def test_completed_run_writes_nothing(tmp_path: Path):
    assert _write(tmp_path, _result(Outcome.COMPLETED, "leave")) is None
    assert list(tmp_path.iterdir()) == []


def test_step_limit_run_is_dumped(tmp_path: Path):
    json_path = _write(tmp_path, _result(Outcome.STEP_LIMIT))
    assert json_path is not None
    context = json.loads(json_path.read_text(encoding="utf-8"))
    assert context["outcome"] == "STEP_LIMIT"


def test_full_screen_capture_records_a_null_region(tmp_path: Path):
    json_path = _write(tmp_path, _result(), region=None)
    assert json_path is not None
    context = json.loads(json_path.read_text(encoding="utf-8"))
    assert context["region"] is None


def test_dumps_dir_is_created_if_missing(tmp_path: Path):
    dumps_dir = tmp_path / "logs" / "dumps"
    json_path = _write(dumps_dir, _result())
    assert json_path is not None
    assert json_path.parent == dumps_dir


def test_a_failing_capture_returns_none_and_logs(tmp_path: Path, caplog):
    def boom() -> Image.Image:
        raise OSError("screen grab failed")

    with caplog.at_level(logging.ERROR, logger="test_dump"):
        assert _write(tmp_path, _result(), grab_screen=boom) is None

    assert list(tmp_path.iterdir()) == []
    assert "Failed to write crash dump" in caplog.text
    assert "screen grab failed" in caplog.text


# --- PR 2.2: dump before recover --------------------------------------------


class RecordingRecovery:
    """Stands in for back_to_bastion() + delete_popup().

    Records what was on disk at the instant ESC spam would have started —
    which is the only thing that matters about the ordering.
    """

    def __init__(self, screen: FakeScreen, dumps_dir: Path) -> None:
        self.screen = screen
        self.dumps_dir = dumps_dir
        self.files_at_recovery: list[str] | None = None

    def __call__(self) -> None:
        self.files_at_recovery = (
            sorted(p.suffix for p in self.dumps_dir.iterdir())
            if self.dumps_dir.is_dir()
            else []
        )
        self.screen.press_key("esc", "back_to_bastion")


def _run(
    tmp_path: Path, screen: FakeScreen, **kwargs
) -> tuple[RunResult, RecordingRecovery]:
    recovery = RecordingRecovery(screen, tmp_path)
    kwargs.setdefault("grab_screen", _image)
    result = run_sequence(
        _config(),
        CONFIG_PATH,
        screen,
        _logger(),
        region=REGION,
        recover=recovery,
        dumps_dir=tmp_path,
        **kwargs,
    )
    return result, recovery


def test_dump_is_written_before_recovery_presses_escape(tmp_path: Path):
    # battleBTN clicks, arenaBattle does not -> ABORTED at select_opponent.
    screen = FakeScreen({"battleBTN.png": [True], "arenaBattle.png": [False]})
    result, recovery = _run(tmp_path, screen)

    assert result.outcome is Outcome.ABORTED
    assert recovery.files_at_recovery == [".json", ".png"], (
        "the dump must already be on disk when back_to_bastion() starts, "
        "or the screenshot will show the Bastion instead of the stuck screen"
    )
    assert ("press_key", ("esc",)) in [(c.method, c.args) for c in screen.calls]


def test_a_completed_run_recovers_without_dumping(tmp_path: Path):
    screen = FakeScreen({"battleBTN.png": [True], "arenaBattle.png": [True]})
    result, recovery = _run(tmp_path, screen)

    assert result.outcome is Outcome.COMPLETED
    assert recovery.files_at_recovery == []
    assert list(tmp_path.iterdir()) == []


def test_a_failed_dump_does_not_block_recovery(tmp_path: Path, caplog):
    def boom() -> Image.Image:
        raise OSError("no display")

    screen = FakeScreen({"battleBTN.png": [True], "arenaBattle.png": [False]})
    with caplog.at_level(logging.WARNING, logger="test_dump"):
        result, recovery = _run(tmp_path, screen, grab_screen=boom)

    assert result.outcome is Outcome.ABORTED
    assert recovery.files_at_recovery == []
    assert "No crash dump was written" in caplog.text


def test_recovery_failure_does_not_hide_the_result(tmp_path: Path, caplog):
    screen = FakeScreen({"battleBTN.png": [True], "arenaBattle.png": [False]})

    def recover() -> None:
        raise RuntimeError("ESC loop blew up")

    with caplog.at_level(logging.ERROR, logger="test_dump"):
        result = run_sequence(
            _config(),
            CONFIG_PATH,
            screen,
            _logger(),
            grab_screen=_image,
            region=REGION,
            recover=recover,
            dumps_dir=tmp_path,
        )

    assert result.outcome is Outcome.ABORTED
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".json", ".png"]
    assert "Cleanup (back_to_bastion / delete_popup) failed" in caplog.text
