"""ScreenActions implementation that replays a scripted list of screenshots.

Matching uses pyscreeze.locate at confidence 0.8 — the same matcher and
threshold the live bot uses — pointed at files instead of the screen.

wait_for_image polls FORWARD through the list (time passes, the screen
changes) but does not advance past a successful match, so a subsequent
CLICK_IMAGE of the same target can still find it.
"""

from __future__ import annotations

from pathlib import Path

import pyscreeze

from utils.constants import DEFAULT_CONFIDENCE


class ScreenshotScreen:
    def __init__(
        self,
        screenshots: list[Path],
        assets_dir: Path,
        confidence: float = DEFAULT_CONFIDENCE,
    ) -> None:
        if not screenshots:
            raise ValueError("ScreenshotScreen needs at least one screenshot")
        self.screenshots = list(screenshots)
        self.assets_dir = assets_dir
        self.confidence = confidence
        self.index = 0
        self.calls: list[tuple[str, str]] = []

    @property
    def current(self) -> Path | None:
        if self.index >= len(self.screenshots):
            return None
        return self.screenshots[self.index]

    def _locate(self, image_name: str) -> bool:
        haystack = self.current
        if haystack is None:
            return False
        needle = self.assets_dir / image_name
        try:
            box = pyscreeze.locate(
                str(needle), str(haystack), confidence=self.confidence
            )
            return box is not None
        except Exception:
            return False

    def _advance(self) -> None:
        if self.index < len(self.screenshots):
            self.index += 1

    def click_image(
        self,
        image_name: str,
        description: str = "",
        retries: int = 1,
        delay: int = 1,
    ) -> bool:
        self.calls.append(("click_image", image_name))
        if self._locate(image_name):
            self._advance()
            return True
        return False

    def wait_for_image(
        self,
        image_name: str,
        description: str = "",
        timeout: int = 30,
        check_interval: int = 2,
    ) -> bool:
        """Poll forward until the image appears or screenshots are exhausted.

        On a match, stay on that screenshot (do not advance) so a following
        CLICK_IMAGE of the same target can still succeed.
        """
        self.calls.append(("wait_for_image", image_name))
        # timeout/check_interval are ignored — each screenshot is one "tick".
        while self.current is not None:
            if self._locate(image_name):
                return True
            self._advance()
        return False

    def is_image_present(self, image_name: str, description: str = "") -> bool:
        self.calls.append(("is_image_present", image_name))
        return self._locate(image_name)

    def press_key(self, key: str, description: str = "") -> None:
        self.calls.append(("press_key", key))
