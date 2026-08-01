"""Pure repair helpers for crash dumps — no tkinter, no CustomTkinter.

Load a dump, crop a fresh target from its screenshot, rewrite the failed
node's ``target`` in the YAML with ruamel, and validate. The GUI in
hitl.app is a thin view over these functions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from ruamel.yaml import YAML

from engine.models import missing_assets
from engine.validate import load_config

logger = logging.getLogger(__name__)

# Selections smaller than this on either side are rejected — they produce
# templates that cannot match at confidence 0.8 and are almost always a
# click-without-drag.
MIN_CROP_SIDE = 4

_STEM_FORMAT = "%Y%m%d-%H%M%S"


@dataclass(frozen=True)
class CrashDump:
    """A dump JSON plus its sibling PNG, with the parsed context."""

    json_path: Path
    png_path: Path
    context: dict[str, Any]

    @property
    def failed_node(self) -> str:
        return str(self.context["failed_node"])

    @property
    def config_path(self) -> Path:
        return Path(self.context["config_path"])

    @property
    def target(self) -> str | None:
        value = self.context.get("target")
        return str(value) if value is not None else None


class RepairError(Exception):
    """Raised when a dump cannot be loaded or a repair cannot be applied."""


def load_dump(json_path: Path) -> CrashDump:
    """Load a dump JSON and resolve its sibling PNG.

    ``write_crash_dump`` never orphans a JSON without a PNG, but humans do
    copy files in and out of ``logs/dumps/``, so a missing PNG is an error
    rather than a crash later in the pipeline.
    """
    json_path = Path(json_path)
    if not json_path.is_file():
        raise RepairError(f"dump JSON not found: {json_path}")

    try:
        context = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RepairError(f"dump JSON is not valid JSON: {json_path}") from exc

    if not isinstance(context, dict):
        raise RepairError(f"dump JSON must be an object: {json_path}")

    screenshot_name = context.get("screenshot")
    if not screenshot_name:
        raise RepairError(f"dump JSON has no 'screenshot' field: {json_path}")

    png_path = json_path.with_name(str(screenshot_name))
    if not png_path.is_file():
        raise RepairError(
            f"dump PNG missing for {json_path.name}: expected {png_path.name}"
        )

    if "failed_node" not in context or "config_path" not in context:
        raise RepairError(
            f"dump JSON is missing failed_node or config_path: {json_path}"
        )

    return CrashDump(json_path=json_path, png_path=png_path, context=context)


def crop_target(
    image_path: Path,
    box: tuple[int, int, int, int],
    node_name: str,
    out_dir: Path,
    now: datetime | None = None,
) -> Path:
    """Crop ``box`` (left, top, width, height) from the screenshot and save it.

    Filename is ``<node_name>_<YYYYMMDD-HHMMSS>.png``. Returns the written path.
    Raises ``RepairError`` for a zero-area or absurdly small selection.
    """
    left, top, width, height = box
    if width < MIN_CROP_SIDE or height < MIN_CROP_SIDE:
        raise RepairError(
            f"selection too small ({width}x{height}); "
            f"need at least {MIN_CROP_SIDE}x{MIN_CROP_SIDE}"
        )

    stamp = (now or datetime.now()).strftime(_STEM_FORMAT)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{node_name}_{stamp}.png"

    with Image.open(image_path) as image:
        crop = image.crop((left, top, left + width, top + height))
        crop.save(out_path)

    logger.info("Saved crop %s (%sx%s)", out_path, width, height)
    return out_path


def _round_trip_yaml() -> YAML:
    """ruamel settings that keep arena_v2.yaml's formatting byte-stable.

    Without ``width=4096``, long ``note:`` lines re-wrap. Without the null
    representer, ``on_success: null`` degrades to ``on_success:``. Either
    alone makes a one-line-diff repair impossible.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.representer.add_representer(
        type(None),
        lambda representer, _data: representer.represent_scalar(
            "tag:yaml.org,2002:null", "null"
        ),
    )
    return yaml


def _default_assets_dir(config_path: Path) -> Path:
    if config_path.parent.name == "configs":
        return config_path.parent.parent / "assets"
    return config_path.parent / "assets"


def validate_config(
    config_path: Path,
    assets_dir: Path | None = None,
) -> list[str]:
    """Return a list of validation error strings (empty means OK)."""
    config_path = Path(config_path)
    errors: list[str] = []
    try:
        config = load_config(config_path)
    except Exception as exc:
        return [f"failed to load {config_path}: {exc}"]

    resolved = assets_dir if assets_dir is not None else _default_assets_dir(config_path)
    missing = missing_assets(config, resolved)
    if missing:
        errors.append(
            "Missing assets (case-sensitive match against assets/ listing): "
            + ", ".join(missing)
        )
    return errors


def rewrite_target(
    config_path: Path,
    node_name: str,
    new_target: str,
    assets_dir: Path | None = None,
) -> str:
    """Set ``nodes[node_name].target`` to ``new_target`` and validate.

    Reads the original file text first. On validation failure, restores that
    text verbatim — never a re-serialisation of the parse tree — and raises
    ``RepairError``. Returns the previous target value on success.
    """
    config_path = Path(config_path)
    if not config_path.is_file():
        raise RepairError(f"config not found: {config_path}")

    original_text = config_path.read_text(encoding="utf-8")
    yaml = _round_trip_yaml()
    data = yaml.load(original_text)

    if not isinstance(data, dict) or "nodes" not in data:
        raise RepairError(f"config has no nodes mapping: {config_path}")
    nodes = data["nodes"]
    if node_name not in nodes:
        raise RepairError(f"node {node_name!r} not in {config_path}")

    node = nodes[node_name]
    old_target = node.get("target")
    node["target"] = new_target

    # Write first, then validate. On failure, restore the original bytes.
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)

    errors = validate_config(config_path, assets_dir=assets_dir)
    if errors:
        config_path.write_text(original_text, encoding="utf-8")
        raise RepairError(
            f"repair of {node_name!r} failed validation; "
            f"config restored: {'; '.join(errors)}"
        )

    logger.info(
        "Rewrote %s node %s: %r -> %r",
        config_path,
        node_name,
        old_target,
        new_target,
    )
    return str(old_target) if old_target is not None else ""
