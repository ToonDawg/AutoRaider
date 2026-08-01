"""Adapter: run a YAML sequence as an ordinary v1 app command.

This is the bridge between the v2 engine and the running application —
`CommandBase`, the command factory, the GUI task list and the scheduler. It
holds no game logic and no knowledge of which sequence it is running; the
config path is bound at registration time.

The module must stay importable on any OS (no pyautogui, no pygetwindow, no
`app`), so the engine test suite keeps running on macOS with no game. The
`click_handler` it is handed at runtime is the application's own, which is
what makes F2 work: the GUI sets `cancel_flag` on that same object.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PIL.Image import Image

from engine.dump import DUMPS_DIR
from engine.run import run_sequence, screen_grabber
from engine.runner import Outcome
from engine.validate import load_config
from utils.base_command import CommandBase
from utils.exceptions import CancellationException

if TYPE_CHECKING:
    from app.pyAutoRaid import AutoRaider

ARENA_V2_CONFIG = Path("configs") / "arena_v2.yaml"


class SequenceCommand(CommandBase):
    """Runs a YAML sequence. Knows nothing about which sequence it is running."""

    def __init__(
        self,
        app: "AutoRaider",
        logger: logging.Logger,
        click_handler: Any,
        config_path: Path,
        repeat: int = 1,
        *,
        grab_screen: Callable[[], Image] | None = None,
        dumps_dir: Path = DUMPS_DIR,
    ) -> None:
        super().__init__(app, logger, click_handler)
        self.config_path = config_path
        self.repeat = repeat
        self._grab_screen = grab_screen
        self._dumps_dir = dumps_dir

    @classmethod
    def bind(
        cls, config_path: Path, repeat: int = 1
    ) -> Callable[..., "SequenceCommand"]:
        """Freeze the sequence so `CommandFactory` can keep constructing every
        command with the same three arguments. Registering the result needs no
        change to the factory, and therefore no risk to the v1 commands.
        """
        return functools.partial(cls, config_path=config_path, repeat=repeat)

    def execute(self) -> None:
        try:
            config = load_config(self.config_path)
        except Exception:
            self.logger.exception("Could not load sequence %s", self.config_path)
            return

        # Resolved once, so every attempt, every dump bbox and the line logged
        # here all agree on what the matcher was looking at.
        region = self.click_handler.region
        if region is None:
            self.logger.warning(
                "Region: FULL SCREEN. The app builds ClickHandler without a "
                "region_provider, so an in-app v2 run is not window-scoped the "
                "way `python -m engine.run` is."
            )
        else:
            self.logger.info(
                "Region: left=%s top=%s width=%s height=%s", *region
            )
        grab_screen = self._grab_screen or screen_grabber(region)

        for attempt in range(1, self.repeat + 1):
            self.logger.info(
                "Running sequence %r from %s — attempt %s of %s",
                config.name,
                self.config_path,
                attempt,
                self.repeat,
            )
            try:
                result = run_sequence(
                    config,
                    self.config_path,
                    self.click_handler,
                    self.logger,
                    grab_screen=grab_screen,
                    region=region,
                    recover=self._cleanup_after_task,
                    dumps_dir=self._dumps_dir,
                )
            except CancellationException:
                # Must not be swallowed: F2 is the only way to stop a live run,
                # and swallowing it here would start the next attempt.
                self.logger.info(
                    "Cancelled by the user during attempt %s of %s.",
                    attempt,
                    self.repeat,
                )
                raise

            if result.outcome is not Outcome.COMPLETED:
                self.logger.warning(
                    "Stopping after attempt %s of %s: %s at node %r. "
                    "The bot's state is unknown, so the remaining attempts are "
                    "skipped; the crash dump under %s is the input to the HITL tool.",
                    attempt,
                    self.repeat,
                    result.outcome.value,
                    result.last_node,
                    self._dumps_dir,
                )
                return

    def _cleanup_after_task(self) -> None:
        """Identical to v1's `ClassicArenaCommand._cleanup_after_task`, so a v2
        run leaves the game exactly where a v1 run would.
        """
        try:
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
            self.logger.info("Returned to bastion and cleared popups.")
        except Exception as e:
            self.logger.error("Error during cleanup: %s", e)
