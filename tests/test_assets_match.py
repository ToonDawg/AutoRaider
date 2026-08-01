"""Confirm every Arena image target still matches a delivered capture."""

from __future__ import annotations

from pathlib import Path

import pytest
import pyscreeze
from PIL import Image

from engine.models import Action
from engine.validate import load_config
from utils.constants import DEFAULT_CONFIDENCE

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "assets"
SHOTS = REPO / "tests" / "screenshots"
CONFIG = REPO / "configs" / "arena_v2.yaml"

# Targets that cannot be verified until their captures arrive.
# Keep these named and loud — do not silently drop them from the list.
BLOCKED_BY_MISSING_CAPTURE = {
    "exitAdd.png": "02_bastion_ad.png (capture 02 not delivered)",
    "ArenaRefillGems.png": "10_out_of_tokens.png (capture 10 not delivered)",
}


def _screenshots() -> list[Path]:
    return sorted(SHOTS.glob("*.png"))


def _image_targets() -> list[str]:
    config = load_config(CONFIG)
    targets: list[str] = []
    for node in config.nodes.values():
        if node.action in (Action.CLICK_IMAGE, Action.WAIT_FOR_IMAGE, Action.IMAGE_PRESENT):
            if node.target not in targets:
                targets.append(node.target)
    return targets


def test_every_screenshot_is_900x600():
    shots = _screenshots()
    assert shots, "no screenshots in tests/screenshots/"
    bad = []
    for path in shots:
        size = Image.open(path).size
        if size != (900, 600):
            bad.append(f"{path.name}: {size}")
    assert not bad, (
        "Captures must be exactly 900x600 (game-window crops). "
        "Non-100% Windows display scaling produces other sizes — "
        "do not resize; report the scaling percentage instead.\n"
        + "\n".join(bad)
    )


@pytest.mark.parametrize("target", _image_targets())
def test_target_matches_at_least_one_screenshot(target: str):
    if target in BLOCKED_BY_MISSING_CAPTURE:
        pytest.skip(
            f"{target} cannot be verified — missing capture: "
            f"{BLOCKED_BY_MISSING_CAPTURE[target]}"
        )

    needle = ASSETS / target
    assert needle.is_file(), f"asset missing: {target}"

    hits: list[str] = []
    for shot in _screenshots():
        try:
            box = pyscreeze.locate(
                str(needle), str(shot), confidence=DEFAULT_CONFIDENCE
            )
            if box is not None:
                hits.append(shot.name)
        except Exception:
            continue

    assert hits, (
        f"{target} was not found in any delivered screenshot at "
        f"confidence={DEFAULT_CONFIDENCE}. The asset crop is likely stale."
    )
