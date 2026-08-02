"""Unit tests for SequenceRunner — no game, no Windows, no screenshots."""

from __future__ import annotations

import logging

import pytest

from engine.models import Action, ActionNode, SequenceConfig
from engine.runner import Outcome, SequenceRunner
from tests.fakes import FakeScreen
from utils.exceptions import CancellationException


def _logger() -> logging.Logger:
    return logging.getLogger("test_runner")


def _runner(config: SequenceConfig, screen: FakeScreen, **kwargs) -> SequenceRunner:
    sleeps: list[float] = []
    kwargs.setdefault("sleep", sleeps.append)
    runner = SequenceRunner(config, screen, _logger(), **kwargs)
    runner._recorded_sleeps = sleeps  # type: ignore[attr-defined]
    return runner


def test_linear_happy_path_visits_in_order():
    config = SequenceConfig(
        name="happy",
        start_node="a",
        nodes={
            "a": ActionNode(
                action=Action.CLICK_IMAGE,
                target="a.png",
                on_success="b",
            ),
            "b": ActionNode(
                action=Action.CLICK_IMAGE,
                target="b.png",
                on_success="c",
            ),
            "c": ActionNode(
                action=Action.PRESS_KEY,
                target="esc",
                settle_seconds=2,
            ),
        },
    )
    screen = FakeScreen({"a.png": [True], "b.png": [True]})
    result = _runner(config, screen).run()
    assert result.outcome is Outcome.COMPLETED
    assert result.visited == ["a", "b", "c"]
    assert result.last_node == "c"
    assert result.steps == 3


def test_failing_node_follows_on_failure():
    config = SequenceConfig(
        name="fail-branch",
        start_node="try",
        nodes={
            "try": ActionNode(
                action=Action.CLICK_IMAGE,
                target="missing.png",
                on_success="ok",
                on_failure="recover",
            ),
            "ok": ActionNode(action=Action.PRESS_KEY, target="esc"),
            "recover": ActionNode(action=Action.PRESS_KEY, target="esc"),
        },
    )
    screen = FakeScreen({"missing.png": [False]})
    result = _runner(config, screen).run()
    assert result.outcome is Outcome.COMPLETED
    assert result.visited == ["try", "recover"]


def test_null_on_failure_returns_aborted():
    config = SequenceConfig(
        name="abort",
        start_node="only",
        nodes={
            "only": ActionNode(
                action=Action.CLICK_IMAGE,
                target="gone.png",
                # on_failure defaults to None
            ),
        },
    )
    screen = FakeScreen({"gone.png": [False]})
    result = _runner(config, screen).run()
    assert result.outcome is Outcome.ABORTED
    assert result.last_node == "only"
    assert result.visited == ["only"]


def test_cancellation_exception_propagates():
    config = SequenceConfig(
        name="cancel",
        start_node="click",
        nodes={
            "click": ActionNode(
                action=Action.CLICK_IMAGE,
                target="x.png",
                on_failure="fallback",
            ),
            "fallback": ActionNode(action=Action.PRESS_KEY, target="esc"),
        },
    )
    screen = FakeScreen()
    screen.raise_on["click_image"] = CancellationException("user cancel")
    with pytest.raises(CancellationException):
        _runner(config, screen).run()


def test_arbitrary_exception_logged_and_follows_on_failure():
    config = SequenceConfig(
        name="boom",
        start_node="click",
        nodes={
            "click": ActionNode(
                action=Action.CLICK_IMAGE,
                target="x.png",
                on_failure="fallback",
            ),
            "fallback": ActionNode(action=Action.PRESS_KEY, target="esc"),
        },
    )
    screen = FakeScreen()
    screen.raise_on["click_image"] = RuntimeError("pyautogui failsafe")
    result = _runner(config, screen).run()
    assert result.outcome is Outcome.COMPLETED
    assert result.visited == ["click", "fallback"]


def test_cycle_terminates_with_step_limit():
    config = SequenceConfig(
        name="cycle",
        start_node="a",
        nodes={
            "a": ActionNode(
                action=Action.PRESS_KEY,
                target="esc",
                on_success="b",
            ),
            "b": ActionNode(
                action=Action.PRESS_KEY,
                target="esc",
                on_success="a",
            ),
        },
    )
    result = _runner(config, FakeScreen(), max_steps=5).run()
    assert result.outcome is Outcome.STEP_LIMIT
    assert result.steps == 5
    assert len(result.visited) == 5


def test_image_present_branches_without_clicking():
    config = SequenceConfig(
        name="present",
        start_node="check",
        nodes={
            "check": ActionNode(
                action=Action.IMAGE_PRESENT,
                target="gems.png",
                on_success="leave",
                on_failure="fight",
            ),
            "leave": ActionNode(action=Action.PRESS_KEY, target="esc"),
            "fight": ActionNode(action=Action.CLICK_IMAGE, target="start.png"),
        },
    )
    # Present -> leave
    screen = FakeScreen({"gems.png": [True]})
    result = _runner(config, screen).run()
    assert result.visited == ["check", "leave"]
    assert all(c.method != "click_image" for c in screen.calls)

    # Absent -> fight
    screen2 = FakeScreen({"gems.png": [False], "start.png": [True]})
    result2 = _runner(config, screen2).run()
    assert result2.visited == ["check", "fight"]
    assert screen2.calls[0].method == "is_image_present"


def test_node_fields_reach_handler_kwargs():
    config = SequenceConfig(
        name="plumbing",
        start_node="click",
        nodes={
            "click": ActionNode(
                action=Action.CLICK_IMAGE,
                target="btn.png",
                retries=3,
                settle_seconds=7,
                match="bottom",
                offset=(50, 50),
                on_success="wait",
            ),
            "wait": ActionNode(
                action=Action.WAIT_FOR_IMAGE,
                target="done.png",
                timeout_seconds=45,
                check_interval_seconds=5,
                on_success="gone",
            ),
            "gone": ActionNode(
                action=Action.WAIT_UNTIL_DISAPPEARS,
                target="spinner.png",
                timeout_seconds=60,
                check_interval_seconds=3,
                on_success="swipe",
            ),
            "swipe": ActionNode(
                action=Action.SWIPE,
                target="up",
                distance=200,
                duration=0.8,
                origin_x=600,
                settle_seconds=0,
                on_success="point",
            ),
            "point": ActionNode(
                action=Action.CLICK_POINT,
                target="hotspot",
                x=100,
                y=200,
                settle_seconds=0,
            ),
        },
    )
    screen = FakeScreen(
        {"btn.png": [True], "done.png": [True], "spinner.png": [True]}
    )
    result = _runner(config, screen).run()
    assert result.outcome is Outcome.COMPLETED

    click = screen.calls[0]
    assert click.method == "click_image"
    assert click.kwargs["retries"] == 3
    assert click.kwargs["delay"] == 7
    assert click.kwargs["match"] == "bottom"
    assert click.kwargs["offset"] == (50, 50)

    wait = screen.calls[1]
    assert wait.method == "wait_for_image"
    assert wait.kwargs["timeout"] == 45

    gone = screen.calls[2]
    assert gone.method == "wait_until_disappears"
    assert gone.kwargs["timeout"] == 60

    swipe = screen.calls[3]
    assert swipe.method == "swipe"
    assert swipe.args == ("up",)
    assert swipe.kwargs["distance"] == 200
    assert swipe.kwargs["origin_x"] == 600

    point = screen.calls[4]
    assert point.method == "click_point"
    assert point.args == (100, 200)


def test_swipe_rejects_bad_direction():
    with pytest.raises(Exception):
        ActionNode(action=Action.SWIPE, target="diagonal")


def test_click_point_requires_coordinates():
    with pytest.raises(Exception):
        ActionNode(action=Action.CLICK_POINT, target="x")

