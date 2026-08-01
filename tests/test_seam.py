"""Structural guards for the ScreenActions seam."""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
from pathlib import Path

from engine.screen import ScreenActions

REPO_ROOT = Path(__file__).resolve().parents[1]
CLICK_HANDLER_PATH = REPO_ROOT / "utils" / "click_handler.py"

# Methods that must stay signature-compatible with ScreenActions.
_PROTOCOL_METHODS = (
    "click_image",
    "wait_for_image",
    "is_image_present",
    "press_key",
)


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return env


def test_engine_runner_does_not_import_pyautogui():
    """Import purity must run in a subprocess so stubbed sys.modules
    from other tests cannot poison the assertion.
    """
    code = (
        "import sys\n"
        "import engine.runner  # noqa: F401\n"
        "assert 'pyautogui' not in sys.modules, sorted(sys.modules)\n"
        "assert 'pyscreeze' not in sys.modules, sorted(sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_engine_models_and_screen_do_not_import_pyautogui():
    code = (
        "import sys\n"
        "import engine.models  # noqa: F401\n"
        "import engine.screen  # noqa: F401\n"
        "assert 'pyautogui' not in sys.modules\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_engine_run_is_importable_without_windows_deps():
    """engine.run owns the dump-before-recover ordering, so it has to be
    importable off Windows. Its pygetwindow / ClickHandler imports live inside
    main() for exactly that reason.
    """
    code = (
        "import sys\n"
        "import engine.run  # noqa: F401\n"
        "assert 'pyautogui' not in sys.modules\n"
        "assert 'pygetwindow' not in sys.modules\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _param_names(func_def: ast.FunctionDef) -> list[str]:
    names = [a.arg for a in func_def.args.args]
    if names and names[0] == "self":
        names = names[1:]
    return names


def test_click_handler_methods_match_screen_actions_protocol():
    """AST-parse ClickHandler so this test never needs pyautogui installed."""
    source = CLICK_HANDLER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    class_def = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "ClickHandler"
    )
    methods = {
        n.name: n
        for n in class_def.body
        if isinstance(n, ast.FunctionDef)
    }

    for name in _PROTOCOL_METHODS:
        assert name in methods, f"ClickHandler is missing {name}()"

    for name in _PROTOCOL_METHODS:
        protocol_fn = getattr(ScreenActions, name)
        protocol_params = [
            p.name
            for p in inspect.signature(protocol_fn).parameters.values()
            if p.name != "self"
        ]
        handler_params = _param_names(methods[name])
        assert handler_params == protocol_params, (
            f"{name}: ClickHandler params {handler_params} "
            f"!= ScreenActions params {protocol_params}"
        )


def test_click_handler_has_region_provider_and_is_image_present():
    source = CLICK_HANDLER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_def = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "ClickHandler"
    )
    names = {
        n.name for n in class_def.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "is_image_present" in names
    assert "region" in names

    init = next(
        n for n in class_def.body
        if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    assert "region_provider" in _param_names(init)
