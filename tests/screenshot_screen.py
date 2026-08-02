"""ScreenActions implementation that replays a scripted list of screenshots.

Matching uses pyscreeze.locate at confidence 0.8 — the same matcher and
threshold the live bot uses — pointed at files instead of the screen.

wait_for_image polls FORWARD through the list (time passes, the screen
changes) but does not advance past a successful match, so a subsequent
CLICK_IMAGE of the same target can still find it.

Anything that changes the screen advances the list: a click that matched, a
swipe, a click_point, and any key press. A click that matched nothing does
not, because it did not happen.

wait_until_disappears polls forward until the image is gone (or screenshots
are exhausted). On disappearance it stays on that screenshot so a following
action can still see it.
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
        match: str = "best",
        offset: tuple[int, int] = (0, 0),
    ) -> bool:
        # match/offset are ignored in replay: we only care whether the template
        # is present on the current frame. Pixel-perfect multi-match selection
        # needs live locateAll, which FakeScreen covers in unit tests.
        del match, offset
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
        del timeout, check_interval
        self.calls.append(("wait_for_image", image_name))
        while self.current is not None:
            if self._locate(image_name):
                return True
            self._advance()
        return False

    def wait_until_disappears(
        self,
        image_name: str,
        description: str = "",
        timeout: int = 30,
        check_interval: int = 2,
    ) -> bool:
        """Poll forward until the image is gone, or screenshots run out."""
        del timeout, check_interval
        self.calls.append(("wait_until_disappears", image_name))
        while self.current is not None:
            if not self._locate(image_name):
                return True
            self._advance()
        return False

    def is_image_present(self, image_name: str, description: str = "") -> bool:
        self.calls.append(("is_image_present", image_name))
        return self._locate(image_name)

    def press_key(self, key: str, description: str = "") -> None:
        self.calls.append(("press_key", key))
        # ESC navigates, so the screen behind it changes.
        self._advance()

    def swipe(
        self,
        direction: str,
        description: str = "",
        distance: int = 400,
        duration: float = 0.5,
        origin_x: int | None = None,
        origin_y: int | None = None,
    ) -> None:
        del distance, duration, origin_x, origin_y
        self.calls.append(("swipe", direction))
        self._advance()

    def click_point(self, x: int, y: int, description: str = "") -> None:
        self.calls.append(("click_point", f"{x},{y}"))
        self._advance()
