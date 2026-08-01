import customtkinter as ctk
from typing import Any

from app.pyAutoRaid import AutoRaider
from utils.config_handler import ConfigHandler


class V2Tab:
    def __init__(self, parent, config_handler: ConfigHandler, py_auto_raid: AutoRaider):
        self.parent = parent
        self.config_handler = config_handler
        self.py_auto_raid = py_auto_raid

        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_columnconfigure(1, weight=1)

        self._create_widgets()

    def _create_widgets(self):
        # Title
        title_label = ctk.CTkLabel(
            self.parent,
            text="V2 Engine Settings",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="w")

        # Arena Repeats
        arena_repeats_label = ctk.CTkLabel(
            self.parent,
            text="Classic Arena (v2) Repeats:",
            font=ctk.CTkFont(size=14)
        )
        arena_repeats_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        # Fetch current value from config
        current_repeats = self.config_handler.read_setting("V2_Settings", "arena_repeats", "1")

        self.arena_repeats_var = ctk.StringVar(value=current_repeats)
        self.arena_repeats_entry = ctk.CTkEntry(
            self.parent,
            textvariable=self.arena_repeats_var,
            width=100
        )
        self.arena_repeats_entry.grid(row=1, column=1, padx=20, pady=10, sticky="w")
        
        # Save Button
        save_button = ctk.CTkButton(
            self.parent,
            text="Save Settings",
            command=self.save_settings,
            fg_color="#2FA572",
            hover_color="#207A4F",
        )
        save_button.grid(row=2, column=0, columnspan=2, padx=20, pady=20, sticky="w")

    def save_settings(self):
        repeats = self.arena_repeats_var.get()
        if not repeats.isdigit() or int(repeats) < 1:
            repeats = "1"
            self.arena_repeats_var.set(repeats)
        
        self.config_handler.update_setting("V2_Settings", "arena_repeats", repeats)
        self.py_auto_raid.logger.info(f"V2 Arena repeats saved as {repeats}")
