"""Crash dump writer: a screenshot plus a JSON context file for a failed run.

Called from engine/run.py once the runner has returned, never from inside
SequenceRunner — the runner stays I/O-free so it can be tested against a fake.

`grab_screen` is injected so unit tests can hand in a synthetic PIL image and
never touch the display.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from engine.models import SequenceConfig
from engine.runner import Outcome, RunResult

if TYPE_CHECKING:
    from PIL.Image import Image

DUMPS_DIR = Path("logs") / "dumps"

_STEM_FORMAT = "%Y-%m-%d_%H-%M-%S"


def write_crash_dump(
    config: SequenceConfig,
    result: RunResult,
    config_path: Path,
    dumps_dir: Path,
    grab_screen: Callable[[], Image],
    *,
    region: tuple[int, int, int, int] | None = None,
    logger: logging.Logger | None = None,
) -> Path | None:
    """Write <timestamp>.png and <timestamp>.json. Returns the JSON path.

    Returns None if the run completed successfully or if dumping failed for
    any reason: a dump is evidence, and failing to collect it must never take
    down the run or block recovery to the Bastion.

    `region` is the search region the screenshot covers, recorded verbatim in
    the JSON. None means the capture was the whole desktop (the --full-screen
    case, or a game window that could not be found).
    """
    log = logger or logging.getLogger(__name__)

    if result.outcome is Outcome.COMPLETED:
        return None

    try:
        # Capture first: everything after this is local file I/O, and a failed
        # capture should leave no half-written dump behind.
        image = grab_screen()
        stamp = datetime.now().replace(microsecond=0)
        stem = stamp.strftime(_STEM_FORMAT)

        dumps_dir.mkdir(parents=True, exist_ok=True)
        png_path = dumps_dir / f"{stem}.png"
        json_path = dumps_dir / f"{stem}.json"
        image.save(png_path)

        # last_node is always a config key in practice. Tolerate a mismatch
        # rather than losing the visited path, which is the useful part.
        node = config.nodes.get(result.last_node)
        context = {
            "timestamp": stamp.isoformat(),
            "outcome": result.outcome.value,
            "config_path": config_path.as_posix(),
            "sequence_name": config.name,
            "failed_node": result.last_node,
            "action": node.action.value if node else None,
            "target": node.target if node else None,
            "note": node.note if node else None,
            "on_success": node.on_success if node else None,
            "on_failure": node.on_failure if node else None,
            "steps": result.steps,
            "visited": result.visited,
            "screenshot": png_path.name,
            "region": list(region) if region is not None else None,
        }
        json_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")

        log.info("Crash dump written: %s", json_path)
        return json_path
    except Exception:
        log.exception("Failed to write crash dump for %s run", result.outcome.value)
        return None
