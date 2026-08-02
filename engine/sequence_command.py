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
from collections.abc import Sequence
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
IRON_TWINS_V2_CONFIG = Path("configs") / "iron_twins_v2.yaml"
TAG_TEAM_V2_CONFIG = Path("configs") / "tag_team_arena_v2.yaml"
FACTION_WARS_V2_CONFIG = Path("configs") / "faction_wars_v2.yaml"
CLAN_BOSS_V2_CONFIG = Path("configs") / "clan_boss_v2.yaml"
DOOM_TOWER_V2_CONFIG = Path("configs") / "doom_tower_v2.yaml"

# Rewards / Daily Quests are lists of small subflow configs.
REWARDS_V2_CONFIGS: list[Path] = [
    Path("configs") / "rewards" / "market_v2.yaml",
    Path("configs") / "rewards" / "clan_v2.yaml",
    Path("configs") / "rewards" / "gem_mine_v2.yaml",
    Path("configs") / "rewards" / "guardian_ring_v2.yaml",
    Path("configs") / "rewards" / "quest_claims_v2.yaml",
    Path("configs") / "rewards" / "shop_v2.yaml",
    Path("configs") / "rewards" / "timed_rewards_v2.yaml",
    Path("configs") / "rewards" / "inbox_v2.yaml",
]
DAILY_QUESTS_V2_CONFIGS: list[Path] = [
    Path("configs") / "daily_quests" / "campaign_v2.yaml",
    Path("configs") / "daily_quests" / "summon_v2.yaml",
    Path("configs") / "daily_quests" / "tavern_v2.yaml",
    ARENA_V2_CONFIG,
]

#: Section in `config.ini` holding the v2 task checkboxes. Deliberately absent
#: from `SelectionItems`, so the scheduler — which resolves a schedule's name to
#: a config section — has no way to reach a v2 command on a timer.
V2_TASKS_SECTION = "V2 Tasks"


class SequenceCommand(CommandBase):
    """Runs one or more YAML sequences. Knows nothing about which."""

    def __init__(
        self,
        app: "AutoRaider",
        logger: logging.Logger,
        click_handler: Any,
        config_path: Path | Sequence[Path],
        repeat: int = 1,
        *,
        grab_screen: Callable[[], Image] | None = None,
        dumps_dir: Path = DUMPS_DIR,
        stop_on_failure: bool = True,
    ) -> None:
        super().__init__(app, logger, click_handler)
        if isinstance(config_path, Path):
            self.config_paths: list[Path] = [config_path]
        else:
            self.config_paths = list(config_path)
        if not self.config_paths:
            raise ValueError("SequenceCommand needs at least one config path")
        # Back-compat for tests / callers that read the singular attribute.
        self.config_path = self.config_paths[0]
        self.repeat = repeat
        self._grab_screen = grab_screen
        self._dumps_dir = dumps_dir
        # Single-config defaults to stop-on-failure (preserve Arena behaviour).
        # Multi-config defaults to best-effort so one bad subflow does not
        # abort Rewards / Daily Quests.
        self.stop_on_failure = stop_on_failure

    @classmethod
    def bind(
        cls,
        config_path: Path | Sequence[Path],
        repeat: int = 1,
        *,
        stop_on_failure: bool | None = None,
    ) -> Callable[..., "SequenceCommand"]:
        """Freeze the sequence so `CommandFactory` can keep constructing every
        command with the same three arguments. Registering the result needs no
        change to the factory, and therefore no risk to the v1 commands.

        Pass a list of paths for composite tasks (Rewards, Daily Quests). Each
        subflow then runs best-effort: a failure dumps and the next config
        still starts.
        """
        paths: Path | list[Path]
        if isinstance(config_path, Path):
            paths = config_path
            sof = True if stop_on_failure is None else stop_on_failure
        else:
            paths = list(config_path)
            sof = False if stop_on_failure is None else stop_on_failure
        return functools.partial(
            cls, config_path=paths, repeat=repeat, stop_on_failure=sof
        )

    def execute(self) -> None:
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

        for config_path in self.config_paths:
            if not self._run_one_config(config_path, grab_screen, region):
                if self.stop_on_failure:
                    return

    def _run_one_config(
        self,
        config_path: Path,
        grab_screen: Callable[[], Image],
        region: tuple[int, int, int, int] | None,
    ) -> bool:
        """Run ``repeat`` attempts of one config. Returns True if every attempt
        COMPLETED; False if one aborted (caller decides whether to continue).
        """
        try:
            config = load_config(config_path)
        except Exception:
            self.logger.exception("Could not load sequence %s", config_path)
            return False

        for attempt in range(1, self.repeat + 1):
            self.logger.info(
                "Running sequence %r from %s — attempt %s of %s",
                config.name,
                config_path,
                attempt,
                self.repeat,
            )
            try:
                result = run_sequence(
                    config,
                    config_path,
                    self.click_handler,
                    self.logger,
                    grab_screen=grab_screen,
                    region=region,
                    recover=self._cleanup_after_task,
                    dumps_dir=self._dumps_dir,
                )
            except CancellationException:
                self.logger.info(
                    "Cancelled by the user during attempt %s of %s.",
                    attempt,
                    self.repeat,
                )
                raise

            if result.outcome is not Outcome.COMPLETED:
                self.logger.warning(
                    "Stopping attempts for %s after attempt %s of %s: %s at "
                    "node %r. Crash dump under %s.",
                    config_path,
                    attempt,
                    self.repeat,
                    result.outcome.value,
                    result.last_node,
                    self._dumps_dir,
                )
                return False
        return True

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


def is_sequence_command(command_class: Any) -> bool:
    """True if `CommandFactory` would build a `SequenceCommand` from this entry.

    Registration goes through `bind`, so the registry holds a `functools.partial`
    wrapping the class rather than the class itself.
    """
    target = getattr(command_class, "func", command_class)
    return isinstance(target, type) and issubclass(target, SequenceCommand)
