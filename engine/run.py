"""Standalone entry point: python -m engine.run configs/arena_v2.yaml

Builds a real ClickHandler (Windows + game required) and walks the YAML.
Does not touch main.py, the GUI, the scheduler, or Modules/.

`main()` is Windows-only. `run_sequence()` — which owns the load-bearing
dump-before-recover ordering — is not, and is unit tested on any OS. It and
`screen_grabber()` are shared with `engine.sequence_command`, so the CLI and
the in-app adapter cannot drift apart on dump ordering or capture geometry.

Live smoke run (PR 1.3 acceptance #4) is a Windows follow-up.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable

from PIL import ImageGrab
from PIL.Image import Image

from engine.dump import DUMPS_DIR, write_crash_dump
from engine.models import SequenceConfig
from engine.runner import Outcome, RunResult, SequenceRunner
from engine.screen import ScreenActions
from engine.validate import load_config
from utils.logger import setup_logger

GAME_TITLE = "Raid: Shadow Legends"


def run_sequence(
    config: SequenceConfig,
    config_path: Path,
    screen: ScreenActions,
    logger: logging.Logger,
    *,
    grab_screen: Callable[[], Image],
    region: tuple[int, int, int, int] | None,
    recover: Callable[[], None],
    dumps_dir: Path = DUMPS_DIR,
) -> RunResult:
    """Walk the sequence, dump on failure, then recover.

    The ordering is the point: `recover` spams ESC until it reaches the Bastion,
    so a dump taken afterwards would be a picture of the Bastion. `finally`
    guarantees recovery still happens if the run raises — a GUI cancel, say —
    in which case the exception propagates and there is no dump.
    """
    try:
        result = SequenceRunner(config, screen, logger).run()
        logger.info(
            "Run finished: outcome=%s last_node=%s steps=%s visited=%s",
            result.outcome.value,
            result.last_node,
            result.steps,
            result.visited,
        )
        if result.outcome is not Outcome.COMPLETED:
            dump_path = write_crash_dump(
                config,
                result,
                config_path,
                dumps_dir,
                grab_screen,
                region=region,
                logger=logger,
            )
            if dump_path is None:
                logger.warning(
                    "No crash dump was written for a %s run — evidence is lost.",
                    result.outcome.value,
                )
        return result
    finally:
        try:
            recover()
        except Exception:
            logger.exception("Cleanup (back_to_bastion / delete_popup) failed")


def screen_grabber(
    region: tuple[int, int, int, int] | None,
) -> Callable[[], Image]:
    """Capture the region the matcher was searching, so a dump shows exactly
    the haystack that failed. Falls back to the whole desktop when there is no
    region.
    """

    def grab() -> Image:
        if region is None:
            return ImageGrab.grab()
        left, top, width, height = region
        return ImageGrab.grab(bbox=(left, top, left + width, top + height))

    return grab


def _add_console_handler(logger: logging.Logger) -> None:
    """Echo to stderr so a live run is visible without opening the log file."""
    if any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        return
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S")
    )
    logger.addHandler(console)


def main(argv: list[str] | None = None) -> int:
    # Imported here, not at module scope: pygetwindow and pyautogui (via
    # ClickHandler) are unavailable on macOS, and tests import this module to
    # exercise run_sequence.
    import pygetwindow as gw

    from utils.click_handler import ClickHandler

    def game_region() -> tuple[int, int, int, int] | None:
        windows = gw.getWindowsWithTitle(GAME_TITLE)
        if not windows:
            return None
        w = windows[0]
        return (w.left, w.top, w.width, w.height)

    parser = argparse.ArgumentParser(
        description="Run a declarative AutoRaider sequence from YAML."
    )
    parser.add_argument("config", type=Path, help="Path to sequence YAML")
    parser.add_argument(
        "--full-screen",
        action="store_true",
        help="Search the whole desktop instead of the game window region "
             "(isolates region bugs from engine bugs on a live run).",
    )
    args = parser.parse_args(argv)

    logger = setup_logger()
    _add_console_handler(logger)

    try:
        config = load_config(args.config)
    except Exception as exc:
        logger.error("Failed to load config %s: %s", args.config, exc)
        return 1

    region_provider = None if args.full_screen else game_region
    click_handler = ClickHandler(logger, region_provider=region_provider)

    resolved = click_handler.region
    if args.full_screen:
        logger.info("Region: FULL SCREEN (--full-screen)")
    elif resolved is None:
        logger.warning(
            "Region: could not find window titled %r — searching full screen. "
            "Is the game open?",
            GAME_TITLE,
        )
    else:
        left, top, width, height = resolved
        logger.info("Region: left=%s top=%s width=%s height=%s", left, top, width, height)
        if (width, height) != (900, 600):
            logger.warning(
                "Expected game window 900x600, got %sx%s — matching may fail.",
                width,
                height,
            )

    def recover() -> None:
        click_handler.back_to_bastion()
        click_handler.delete_popup()

    # Resolved once, so the dump's bbox, the region in its JSON, and the region
    # logged above all agree.
    result = run_sequence(
        config,
        args.config,
        click_handler,
        logger,
        grab_screen=screen_grabber(resolved),
        region=resolved,
        recover=recover,
    )

    return 0 if result.outcome is Outcome.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
