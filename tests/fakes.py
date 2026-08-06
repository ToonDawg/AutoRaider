"""Hand-written ScreenActions fake for engine unit tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallRecord:
    method: str
    args: tuple
    kwargs: dict


class FakeScreen:
    """Scripted ScreenActions double."""

    def __init__(self, results: dict[str, list[bool]] | None = None) -> None:
        self.results = {k: list(v) for k, v in (results or {}).items()}
        self.calls: list[CallRecord] = []
        self.raise_on: dict[str, BaseException] = {}

    def _record(self, method: str, args: tuple, kwargs: dict) -> None:
        self.calls.append(CallRecord(method, args, kwargs))
        if method in self.raise_on:
            raise self.raise_on[method]

    def _next(self, image_name: str) -> bool:
        queue = self.results.get(image_name)
        return queue.pop(0) if queue else False

    def click_image(
        self,
        image_name: str,
        description: str = "",
        retries: int = 1,
        delay: int = 1,
        match: str = "best",
        offset: tuple[int, int] = (0, 0),
        ignore_points: list[tuple[int, int]] | None = None,
    ) -> bool | tuple[int, int]:
        self._record(
            "click_image",
            (image_name,),
            {
                "description": description,
                "retries": retries,
                "delay": delay,
                "match": match,
                "offset": offset,
                "ignore_points": ignore_points,
            },
        )
        return self._next(image_name)

    def wait_for_image(
        self,
        image_name: str,
        description: str = "",
        timeout: int = 30,
        check_interval: int = 2,
    ) -> bool:
        self._record(
            "wait_for_image",
            (image_name,),
            {
                "description": description,
                "timeout": timeout,
                "check_interval": check_interval,
            },
        )
        return self._next(image_name)

    def wait_until_disappears(
        self,
        image_name: str,
        description: str = "",
        timeout: int = 30,
        check_interval: int = 2,
    ) -> bool:
        self._record(
            "wait_until_disappears",
            (image_name,),
            {
                "description": description,
                "timeout": timeout,
                "check_interval": check_interval,
            },
        )
        return self._next(image_name)

    def is_image_present(self, image_name: str, description: str = "") -> bool:
        self._record("is_image_present", (image_name,), {"description": description})
        return self._next(image_name)

    def press_key(self, key: str, description: str = "") -> None:
        self._record("press_key", (key,), {"description": description})

    def swipe(
        self,
        direction: str,
        description: str = "",
        distance: int = 400,
        duration: float = 0.5,
        origin_x: int | None = None,
        origin_y: int | None = None,
    ) -> None:
        self._record(
            "swipe",
            (direction,),
            {
                "description": description,
                "distance": distance,
                "duration": duration,
                "origin_x": origin_x,
                "origin_y": origin_y,
            },
        )

    def click_point(self, x: int, y: int, description: str = "") -> None:
        self._record("click_point", (x, y), {"description": description})


class FakeClickHandler(FakeScreen):
    """FakeScreen plus the parts of ClickHandler that are not in ScreenActions.

    `SequenceCommand` reaches past the protocol for `region` and for the two
    cleanup calls, so a double for it needs more than a plain FakeScreen.
    """

    def __init__(
        self,
        results: dict[str, list[bool]] | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> None:
        super().__init__(results)
        self.region = region

    def back_to_bastion(self) -> None:
        self._record("back_to_bastion", (), {})

    def delete_popup(self) -> None:
        self._record("delete_popup", (), {})
