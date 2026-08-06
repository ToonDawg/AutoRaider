"""ScreenActions protocol — the seam between the runner and the real world.

ClickHandler already satisfies this structurally. Tests use FakeScreen /
ScreenshotScreen instead. engine/models.py, engine/runner.py and this module
must never import pyautogui.
"""

from __future__ import annotations

from typing import Protocol


class ScreenActions(Protocol):
    def click_image(
        self,
        image_name: str,
        description: str = "",
        retries: int = 1,
        delay: int = 1,
        match: str = "best",
        offset: tuple[int, int] = (0, 0),
        ignore_points: list[tuple[int, int]] | None = None,
    ) -> bool | tuple[int, int]: ...

    def wait_for_image(
        self,
        image_name: str,
        description: str = "",
        timeout: int = 30,
        check_interval: int = 2,
    ) -> bool: ...

    def wait_until_disappears(
        self,
        image_name: str,
        description: str = "",
        timeout: int = 30,
        check_interval: int = 2,
    ) -> bool: ...

    def is_image_present(
        self,
        image_name: str,
        description: str = "",
    ) -> bool: ...

    def press_key(
        self,
        key: str,
        description: str = "",
    ) -> None: ...

    def swipe(
        self,
        direction: str,
        description: str = "",
        distance: int = 400,
        duration: float = 0.5,
        origin_x: int | None = None,
        origin_y: int | None = None,
    ) -> None: ...

    def click_point(
        self,
        x: int,
        y: int,
        description: str = "",
    ) -> None: ...
