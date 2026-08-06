"""Dumb sequence runner — walks a YAML graph via ScreenActions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from engine.models import Action, ActionNode, SequenceConfig
from engine.screen import ScreenActions
from utils.exceptions import CancellationException


class Outcome(StrEnum):
    COMPLETED = "COMPLETED"  # ran off a null on_success — sequence finished
    ABORTED = "ABORTED"  # ran off a null on_failure — the bot is lost
    STEP_LIMIT = "STEP_LIMIT"  # exceeded max_steps — probably a cycle with no exit


@dataclass
class RunResult:
    outcome: Outcome
    last_node: str
    steps: int
    visited: list[str]


class SequenceRunner:
    def __init__(
        self,
        config: SequenceConfig,
        screen: ScreenActions,
        logger: logging.Logger,
        max_steps: int = 200,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.screen = screen
        self.logger = logger
        self.max_steps = max_steps
        self._sleep = sleep

    def run(self) -> RunResult:
        current = self.config.start_node
        visited: list[str] = []
        self._clicked_points: list[tuple[int, int]] = []

        for step in range(1, self.max_steps + 1):
            if getattr(self.screen, "cancel_flag", False):
                raise CancellationException("Task cancelled by user.")

            node = self.config.nodes[current]
            visited.append(current)
            self.logger.info(
                "Step %s: %s — %s(%s)",
                step,
                current,
                node.action.value,
                node.target,
            )

            try:
                ok = self._execute(node)
                if ok and node.clear_visited:
                    self._clicked_points.clear()
            except CancellationException:
                raise
            except Exception:
                self.logger.exception("Node %s raised", current)
                ok = False

            next_key = node.on_success if ok else node.on_failure
            if next_key is None:
                outcome = Outcome.COMPLETED if ok else Outcome.ABORTED
                return RunResult(outcome, current, step, visited)
            current = next_key

        return RunResult(Outcome.STEP_LIMIT, current, self.max_steps, visited)

    def _execute(self, node: ActionNode) -> bool:
        note = node.note or node.target

        if node.action is Action.CLICK_IMAGE:
            result = self.screen.click_image(
                node.target,
                description=note,
                retries=node.retries,
                delay=node.settle_seconds,
                match=node.match.value,
                offset=node.offset,
                ignore_points=self._clicked_points if node.ignore_visited else None,
            )
            if result:
                if isinstance(result, tuple) and node.ignore_visited:
                    self._clicked_points.append(result)
                return True
            return False

        if node.action is Action.WAIT_FOR_IMAGE:
            return self.screen.wait_for_image(
                node.target,
                description=note,
                timeout=node.timeout_seconds,
                check_interval=node.check_interval_seconds,
            )

        if node.action is Action.WAIT_UNTIL_DISAPPEARS:
            return self.screen.wait_until_disappears(
                node.target,
                description=note,
                timeout=node.timeout_seconds,
                check_interval=node.check_interval_seconds,
            )

        if node.action is Action.IMAGE_PRESENT:
            return self.screen.is_image_present(node.target, description=note)

        if node.action is Action.PRESS_KEY:
            self.screen.press_key(node.target, description=note)
            self._sleep(node.settle_seconds)
            return True

        if node.action is Action.SWIPE:
            self.screen.swipe(
                node.target,
                description=note,
                distance=node.distance,
                duration=node.duration,
                origin_x=node.origin_x,
                origin_y=node.origin_y,
            )
            self._sleep(node.settle_seconds)
            return True

        if node.action is Action.CLICK_POINT:
            assert node.x is not None and node.y is not None  # validated
            self.screen.click_point(node.x, node.y, description=note)
            self._sleep(node.settle_seconds)
            return True

        # Unreachable while Action is a closed StrEnum, but keep a clear failure.
        raise ValueError(f"Unhandled action: {node.action!r}")
