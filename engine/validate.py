"""Validate a sequence YAML config: schema, assets, reachability.

Usage:
    python -m engine.validate configs/arena_v2.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML

from engine.models import SequenceConfig, missing_assets, unreachable_nodes


def load_config(path: Path) -> SequenceConfig:
    yaml = YAML(typ="safe")
    with path.open(encoding="utf-8") as f:
        data = yaml.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at the top level")
    return SequenceConfig.model_validate(data)


def _format_validation_error(exc: ValidationError) -> str:
    lines = ["Schema validation failed:"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)


def validate(path: Path, assets_dir: Path | None = None) -> int:
    """Validate *path*. Return 0 on success, 1 on failure."""
    if not path.is_file():
        print(f"error: config file not found: {path}", file=sys.stderr)
        return 1

    try:
        config = load_config(path)
    except ValidationError as exc:
        print(_format_validation_error(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: failed to load {path}: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    if assets_dir is None:
        # configs/<name>.yaml lives next to assets/ at the repo root.
        if path.parent.name == "configs":
            assets_dir = path.parent.parent / "assets"
        else:
            assets_dir = path.parent / "assets"

    missing = missing_assets(config, assets_dir)
    if missing:
        errors.append("Missing assets (case-sensitive match against assets/ listing):")
        for name in missing:
            errors.append(f"  - {name}")

    unreachable = unreachable_nodes(config)
    if unreachable:
        errors.append("Unreachable nodes (no path from start_node):")
        for name in unreachable:
            errors.append(f"  - {name}")

    print(f"Sequence: {config.name}")
    print(f"Start:    {config.start_node}")
    print(f"Nodes:    {len(config.nodes)}")
    print()
    print("Graph:")
    for key, node in config.nodes.items():
        mark = " *" if key == config.start_node else "  "
        print(
            f"{mark}{key}: {node.action.value}({node.target!r})"
            f"  ok->{node.on_success}  fail->{node.on_failure}"
        )

    if errors:
        print(file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1

    print()
    print("OK: schema valid, all assets present, all nodes reachable.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: python -m engine.validate <config.yaml>")
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    return validate(Path(argv[0]))


if __name__ == "__main__":
    sys.exit(main())
