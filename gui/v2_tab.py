"""The v2 engine's task list.

One checkbox per YAML-driven command, run through the same `run_task` path the
Tasks tab uses — so the app's shared `ClickHandler`, the background thread and
the F2 cancel all behave identically. The v2 keys live in their own config
section rather than in a `SelectionItems` preset, which is what keeps them off
the scheduler.
"""

import customtkinter as ctk
from typing import Any, Dict

from app.pyAutoRaid import AutoRaider
from engine.sequence_command import V2_TASKS_SECTION, is_sequence_command
from utils.config_handler import ConfigHandler


class V2Tab:
    def __init__(self, parent, config_handler: ConfigHandler, py_auto_raid: AutoRaider):
        self.parent = parent
        self.config_handler = config_handler
        self.py_auto_raid = py_auto_raid
        self.checkbox_vars: Dict[Any, ctk.BooleanVar] = {}

        self.parent.grid_columnconfigure(0, weight=1)

        self._create_widgets()

    def _v2_commands(self) -> list[tuple[Any, str]]:
        registry = self.py_auto_raid.command_factory.registry
        return [
            (key, info["display_name"])
            for key, info in registry.items()
            if is_sequence_command(info["command_class"])
        ]

    def _create_widgets(self) -> None:
        ctk.CTkLabel(
            self.parent,
            text="V2 Engine Tasks",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            self.parent,
            text=(
                "Configuration-driven tasks. These run manually only — they are "
                "not available to the scheduler."
            ),
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        commands = self._v2_commands()
        if not commands:
            ctk.CTkLabel(
                self.parent,
                text="No v2 tasks are registered yet.",
                font=ctk.CTkFont(size=13),
            ).grid(row=2, column=0, padx=20, pady=10, sticky="w")
            return

        saved_states = self.config_handler.read_setting(V2_TASKS_SECTION, None) or {}
        for i, (command_key, display_name) in enumerate(commands):
            var = ctk.BooleanVar(value=saved_states.get(command_key.value) == "True")
            self.checkbox_vars[command_key] = var
            ctk.CTkCheckBox(
                self.parent,
                text=display_name,
                variable=var,
                command=lambda key=command_key, v=var: self.checkbox_callback(key, v),
            ).grid(row=i + 2, column=0, padx=20, pady=5, sticky="w")

        run_button = ctk.CTkButton(
            self.parent,
            text="Run Selected",
            command=self.run_selected,
            fg_color="#2FA572",
            hover_color="#207A4F",
        )
        run_button.grid(row=len(commands) + 2, column=0, padx=20, pady=20, sticky="w")

    def checkbox_callback(self, command_key: Any, var: ctk.BooleanVar) -> None:
        self.config_handler.update_setting(
            V2_TASKS_SECTION, command_key.value, str(var.get())
        )
        self.py_auto_raid.logger.info(
            f"V2 task {command_key.value} updated to {var.get()}."
        )

    def run_selected(self) -> None:
        if not any(var.get() for var in self.checkbox_vars.values()):
            self.py_auto_raid.logger.warning("No v2 tasks selected.")
            return

        self.py_auto_raid.logger.info("V2 manual run triggered.")
        self.py_auto_raid.run_task(V2_TASKS_SECTION)
