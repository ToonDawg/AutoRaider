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
    ) -> bool: ...

    def wait_for_image(
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
