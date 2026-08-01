"""Standalone entry point: python -m engine.run configs/arena_v2.yaml

Builds a real ClickHandler (Windows + game required) and walks the YAML.
Does not touch main.py, the GUI, the scheduler, or Modules/.

Live smoke run (PR 1.3 acceptance #4) is a Windows follow-up — this module
cannot be exercised on macOS.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pygetwindow as gw

from engine.runner import Outcome, SequenceRunner
from engine.validate import load_config
from utils.click_handler import ClickHandler
from utils.logger import setup_logger

GAME_TITLE = "Raid: Shadow Legends"


def _game_region() -> tuple[int, int, int, int] | None:
    windows = gw.getWindowsWithTitle(GAME_TITLE)
    if not windows:
        return None
    w = windows[0]
    return (w.left, w.top, w.width, w.height)


def main(argv: list[str] | None = None) -> int:
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
    # Also echo to stderr so a live run is visible without opening the log file.
    if not any(isinstance(h, __import__("logging").StreamHandler) for h in logger.handlers):
        import logging
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.INFO)
        console.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S")
        )
        logger.addHandler(console)

    try:
        config = load_config(args.config)
    except Exception as exc:
        logger.error("Failed to load config %s: %s", args.config, exc)
        return 1

    region_provider = None if args.full_screen else _game_region
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

    runner = SequenceRunner(config, click_handler, logger)
    result = None
    try:
        result = runner.run()
        logger.info(
            "Run finished: outcome=%s last_node=%s steps=%s visited=%s",
            result.outcome.value,
            result.last_node,
            result.steps,
            result.visited,
        )
    finally:
        try:
            click_handler.back_to_bastion()
            click_handler.delete_popup()
        except Exception:
            logger.exception("Cleanup (back_to_bastion / delete_popup) failed")

    if result is None:
        return 1
    return 0 if result.outcome is Outcome.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
