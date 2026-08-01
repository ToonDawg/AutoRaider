"""Pydantic models for declarative sequence configs."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator


class Action(StrEnum):
    CLICK_IMAGE = "CLICK_IMAGE"
    WAIT_FOR_IMAGE = "WAIT_FOR_IMAGE"
    IMAGE_PRESENT = "IMAGE_PRESENT"
    PRESS_KEY = "PRESS_KEY"


_IMAGE_ACTIONS = {Action.CLICK_IMAGE, Action.WAIT_FOR_IMAGE, Action.IMAGE_PRESENT}


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

    Compares against an actual directory listing rather than Path.exists(),
    because macOS and Windows filesystems are case-insensitive and would
    silently accept a case-mismatched filename.
    """
    names = {p.name for p in assets_dir.iterdir()} if assets_dir.is_dir() else set()
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
