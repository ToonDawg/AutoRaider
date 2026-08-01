"""Tests for engine.models schema validation and asset checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.models import Action, ActionNode, SequenceConfig, missing_assets


def _node(**kwargs) -> dict:
    base = {
        "action": "CLICK_IMAGE",
        "target": "battleBTN.png",
        "on_success": None,
        "on_failure": None,
    }
    base.update(kwargs)
    return base


def _config(nodes: dict, start: str = "a") -> SequenceConfig:
    return SequenceConfig(name="test", start_node=start, nodes=nodes)


def test_valid_config_round_trips():
    raw = {
        "name": "demo",
        "start_node": "click",
        "nodes": {
            "click": {
                "action": "CLICK_IMAGE",
                "target": "battleBTN.png",
                "on_success": "wait",
            },
            "wait": {
                "action": "WAIT_FOR_IMAGE",
                "target": "tapToContinue.png",
                "timeout_seconds": 120,
            },
        },
    }
    config = SequenceConfig.model_validate(raw)
    assert config.name == "demo"
    assert config.start_node == "click"
    assert config.nodes["click"].action is Action.CLICK_IMAGE
    assert config.nodes["click"].on_success == "wait"
    assert config.nodes["wait"].on_success is None
    assert config.nodes["wait"].timeout_seconds == 120
    # Round-trip through dump/validate
    again = SequenceConfig.model_validate(config.model_dump())
    assert again == config


def test_unknown_start_node_rejected():
    with pytest.raises(ValidationError, match="start_node"):
        _config({"a": ActionNode.model_validate(_node())}, start="missing")


def test_edge_pointing_at_missing_node_rejected():
    with pytest.raises(ValidationError, match="on_success"):
        _config(
            {
                "a": ActionNode.model_validate(
                    _node(on_success="nowhere")
                )
            }
        )


def test_unknown_action_type_rejected():
    with pytest.raises(ValidationError):
        ActionNode.model_validate(_node(action="CLIK_IMAGE"))


def test_unknown_field_name_rejected():
    with pytest.raises(ValidationError):
        ActionNode.model_validate(_node(on_sucess="a"))


def test_edge_defaults_are_none():
    node = ActionNode(action=Action.PRESS_KEY, target="esc")
    assert node.on_success is None
    assert node.on_failure is None


def test_missing_assets_case_sensitive(tmp_path: Path):
    (tmp_path / "battleBTN.png").write_bytes(b"x")
    (tmp_path / "tapToContinue.png").write_bytes(b"x")

    config = _config(
        {
            "a": ActionNode(
                action=Action.CLICK_IMAGE,
                target="battleBTN.png",
                on_success="b",
            ),
            "b": ActionNode(
                action=Action.WAIT_FOR_IMAGE,
                # Wrong case — Path.exists() would pass on macOS/Windows
                target="taptocontinue.png",
            ),
            "c": ActionNode(
                action=Action.PRESS_KEY,
                target="esc",
            ),
        }
    )
    missing = missing_assets(config, tmp_path)
    assert missing == ["taptocontinue.png"]


def test_missing_assets_skips_press_key(tmp_path: Path):
    config = _config(
        {"a": ActionNode(action=Action.PRESS_KEY, target="esc")}
    )
    assert missing_assets(config, tmp_path) == []


def test_missing_assets_finds_subdirectory_targets(tmp_path: Path):
    (tmp_path / "battleBTN.png").write_bytes(b"x")
    dynamic = tmp_path / "dynamic"
    dynamic.mkdir()
    (dynamic / "foo.png").write_bytes(b"x")

    config = _config(
        {
            "a": ActionNode(
                action=Action.CLICK_IMAGE,
                target="battleBTN.png",
                on_success="b",
            ),
            "b": ActionNode(
                action=Action.CLICK_IMAGE,
                target="dynamic/foo.png",
                on_success="c",
            ),
            "c": ActionNode(
                action=Action.CLICK_IMAGE,
                target="dynamic/missing.png",
            ),
        }
    )
    assert missing_assets(config, tmp_path) == ["dynamic/missing.png"]
