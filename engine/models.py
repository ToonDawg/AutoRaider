"""Pydantic models for declarative sequence configs."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator


class Action(StrEnum):
    CLICK_IMAGE = "CLICK_IMAGE"
    WAIT_FOR_IMAGE = "WAIT_FOR_IMAGE"
    WAIT_UNTIL_DISAPPEARS = "WAIT_UNTIL_DISAPPEARS"
    IMAGE_PRESENT = "IMAGE_PRESENT"
    PRESS_KEY = "PRESS_KEY"
    SWIPE = "SWIPE"
    CLICK_POINT = "CLICK_POINT"


class MatchPolicy(StrEnum):
    """Which locateAll hit CLICK_IMAGE should use when several match."""

    BEST = "best"  # first / highest-confidence (locateOnScreen behaviour)
    BOTTOM = "bottom"  # largest y — Stage 15, bottom-most stage start
    TOP = "top"  # smallest y


_IMAGE_ACTIONS = {
    Action.CLICK_IMAGE,
    Action.WAIT_FOR_IMAGE,
    Action.WAIT_UNTIL_DISAPPEARS,
    Action.IMAGE_PRESENT,
}

_SWIPE_DIRECTIONS = frozenset({"up", "down", "left", "right"})


class ActionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action
    target: str
    timeout_seconds: int = 30
    check_interval_seconds: int = 2
    settle_seconds: int = 1
    retries: int = 1
    note: str | None = None
    on_success: str | None = None
    on_failure: str | None = None

    # Iteration helper (engine tracks clicked coords and skips them if true)
    ignore_visited: bool = False
    clear_visited: bool = False

    # CLICK_IMAGE multi-match selection
    match: MatchPolicy = MatchPolicy.BEST
    offset: tuple[int, int] = (0, 0)

    # SWIPE extras (target is the direction)
    distance: int = 400
    duration: float = 0.5
    origin_x: int | None = None
    origin_y: int | None = None

    # CLICK_POINT — target is unused; coordinates are window-relative when a
    # region is set, otherwise absolute desktop pixels (same as v1).
    x: int | None = None
    y: int | None = None

    @model_validator(mode="after")
    def _action_specific_fields(self) -> ActionNode:
        if self.action is Action.SWIPE and self.target not in _SWIPE_DIRECTIONS:
            raise ValueError(
                f"SWIPE target must be one of {sorted(_SWIPE_DIRECTIONS)}, "
                f"got {self.target!r}"
            )
        if self.action is Action.CLICK_POINT:
            if self.x is None or self.y is None:
                raise ValueError("CLICK_POINT requires x and y")
        return self


class SequenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    start_node: str
    nodes: dict[str, ActionNode]

    @model_validator(mode="after")
    def _edges_point_at_real_nodes(self) -> SequenceConfig:
        if self.start_node not in self.nodes:
            raise ValueError(f"start_node {self.start_node!r} is not a defined node")
        for key, node in self.nodes.items():
            for edge in ("on_success", "on_failure"):
                dest = getattr(node, edge)
                if dest is not None and dest not in self.nodes:
                    raise ValueError(
                        f"node {key!r}.{edge} points at unknown node {dest!r}"
                    )
        return self


def missing_assets(config: SequenceConfig, assets_dir: Path) -> list[str]:
    """Return targets of image actions that have no matching file in assets/.

    Walks assets/ recursively and compares against posix-relative paths
    (e.g. ``arenaBattle.png``, ``dynamic/foo.png``) rather than Path.exists(),
    because macOS and Windows filesystems are case-insensitive and would
    silently accept a case-mismatched filename. ``as_posix()`` keeps the
    comparison stable on Windows where ``str(Path)`` would use backslashes.
    """
    names = (
        {
            p.relative_to(assets_dir).as_posix()
            for p in assets_dir.rglob("*")
            if p.is_file()
        }
        if assets_dir.is_dir()
        else set()
    )
    missing: list[str] = []
    for node in config.nodes.values():
        if node.action not in _IMAGE_ACTIONS:
            continue
        if node.target not in names:
            missing.append(node.target)
    return sorted(set(missing))


def unreachable_nodes(config: SequenceConfig) -> list[str]:
    """Return node keys not reachable by following edges from start_node."""
    reachable: set[str] = set()
    stack = [config.start_node]
    while stack:
        key = stack.pop()
        if key in reachable:
            continue
        reachable.add(key)
        node = config.nodes[key]
        for edge in (node.on_success, node.on_failure):
            if edge is not None and edge not in reachable:
                stack.append(edge)
    return sorted(set(config.nodes) - reachable)
