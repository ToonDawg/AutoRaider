from enum import Enum
import customtkinter as ctk
from typing import Dict, Any
from PIL import Image

from app.pyAutoRaid import AutoRaider
from utils.config_handler import ConfigHandler


class TasksTab:
    def __init__(self, parent, py_auto_raid: AutoRaider, config_handler: ConfigHandler):
        self.parent = parent
        self.py_auto_raid = py_auto_raid
        self.config_handler = config_handler
        self.checkbox_vars: Dict[Any, ctk.BooleanVar] = {}
        self.log_text = None
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)
        raw_items = self.config_handler.read_setting("SelectionItems", "items") or "['Tasks']"
        if isinstance(raw_items, str):
            self.selection_items = [item.strip().strip("'") for item in raw_items.strip("[]").split(',')]
        elif isinstance(raw_items, list):
            self.selection_items = raw_items
        else:
            self.selection_items = ["Tasks"]

        self._setup_select_deselect_checkbox()
        self._setup_selection_menu()
        self._create_task_checkboxes()
        self._create_action_buttons()
        self._create_log_textbox()
        
        # Load initial states for the first selection
        if self.selection_items:
            self.update_selection(self.selection_items[0])

    def _setup_select_deselect_checkbox(self) -> None:
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)
        self.select_deselect_var = ctk.BooleanVar(value=False)
        self.select_deselect_checkbox = ctk.CTkCheckBox(
            self.parent,
            text="All",
            variable=self.select_deselect_var,
            command=self.toggle_select_deselect_all,
        )
        self.select_deselect_checkbox.grid(row=0, column=3, padx=10, pady=5, sticky="w")

    def toggle_select_deselect_all(self) -> None:
        value = self.select_deselect_var.get()
        self._set_all_checkboxes(value)
        current_selection = self.selection_var.get()
        if current_selection and current_selection != "Select":
            for config_key, var in self.checkbox_vars.items():
                self.config_handler.update_setting(current_selection, config_key.value, str(var.get()))
            self.config_handler.save_config()
            self.py_auto_raid.logger.info(f"All checkbox states saved to config for {current_selection}.")
        self.py_auto_raid.logger.info(f"All checkboxes set to {'selected' if value else 'deselected'}.")

    def _setup_selection_menu(self) -> None:
        self.selection_var = ctk.StringVar(value=self.selection_items[0])
        self.selection_menu = ctk.CTkOptionMenu(
            self.parent,
            values=self.selection_items,
            variable=self.selection_var,
            command=self.update_selection,
        )
        self.selection_menu.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

        # Action buttons
        buttons_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        buttons_frame.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.add_button = ctk.CTkButton(
            buttons_frame,
            text="Add",
            command=self._open_add_dialog,
            width=80,
            corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.add_button.pack(side="left", padx=(0, 10))

        self.remove_button = ctk.CTkButton(
            buttons_frame,
            text="Remove", 
            command=self._remove_item,
            width=80,
            fg_color="#CC3D3D",
            hover_color="#A83232",
            corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.remove_button.pack(side="left")

    def _create_task_checkboxes(self) -> None:
        for i, (command_key, display_name) in enumerate(self.py_auto_raid.command_factory.get_display_names()):
            initial_value = False
            var = ctk.BooleanVar(value=initial_value)
            self.checkbox_vars[command_key] = var

            ctk.CTkCheckBox(
                self.parent,
                text=display_name,
                variable=var,
                command=lambda key=command_key, v=var: self.checkbox_callback(key, v)
            ).grid(row=(i // 4) + 1, column=i % 4, padx=10, pady=5, sticky="w")

    def _create_action_buttons(self) -> None:
        button_row = (len(self.checkbox_vars) // 4) + 2

        manual_run_button = ctk.CTkButton(
            self.parent,
            text="Manual Run",
            command=self.manual_run,
            fg_color="#2FA572",
            hover_color="#207A4F",
        )
        manual_run_button.grid(row=button_row, column=0, padx=10, pady=(10, 0), sticky="w")

        quit_all_button = ctk.CTkButton(
            self.parent,
            text="Quit All",
            command=self.quit_all
        )
        quit_all_button.grid(row=button_row, column=3, padx=10, pady=(10, 0), sticky="w")

    def _create_log_textbox(self) -> None:
        self.log_text = ctk.CTkTextbox(
            self.parent,
            wrap="word",
            state="disabled",
            width=400,
            height=200
        )
        self.log_text.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=10, pady=10)

    def update_selection(self, selection: str) -> None:
        if selection in ("Select All", "Deselect"):
            self._set_all_checkboxes(selection == "Select All")
        else:
            # Load and apply saved states for the selection
            saved_states = self.config_handler.read_setting(selection, None) or {}
            for key, var in self.checkbox_vars.items():
                if key.value in saved_states:
                    var.set(saved_states[key.value] == "True")
        self.py_auto_raid.logger.info(f"Selection updated: {selection}")

    def _set_all_checkboxes(self, value: bool) -> None:
        for var in self.checkbox_vars.values():
            var.set(value)

    def checkbox_callback(self, config_key: Any, var: ctk.BooleanVar) -> None:
        self.py_auto_raid.logger.info(f"Task {config_key.value} updated to {var.get()}.")
        # Persist the state only for the current selection
        current_selection = self.selection_var.get()
        if current_selection and current_selection != "Select":
            self.config_handler.update_setting(current_selection, config_key.value, str(var.get()))

    def manual_run(self) -> None:
        self.py_auto_raid.logger.info("Manual Run Triggered.")
        selected_tasks = self.selection_var.get()
        self.py_auto_raid.run_task(selected_tasks)

    def quit_all(self) -> None:
        self.py_auto_raid.logger.info("Quitting Application.")
        self.parent.quit()


    def _open_add_dialog(self) -> None:
        dialog = ctk.CTkInputDialog(
            text="Enter new item name:",
            title="Add Item",
            button_fg_color="#2FA572"
        )
        item = dialog.get_input()
        if item and item.strip():
            self.add_selection_item(item.strip())

    def _remove_item(self) -> None:
        item = self.selection_var.get()
        if item and item in self.selection_items:
            self.remove_selection_item(item)

    def add_selection_item(self, item: str) -> None:
        if item not in self.selection_items:
            current_states = {k.value: str(v.get()) for k, v in self.checkbox_vars.items()}
            for setting_key, setting_value in current_states.items():
                self.config_handler.update_setting(item, setting_key, setting_value)
            self.selection_items.append(item)
            self.selection_menu.configure(values=self.selection_items)
            self.config_handler.update_setting("SelectionItems", "items", self.selection_items)
            self.config_handler.save_config()
            self.py_auto_raid.logger.info(f"Added selection item: {item}")

    def remove_selection_item(self, item: str) -> None:
        if item in self.selection_items:
            self.selection_items.remove(item)
            self.selection_menu.configure(values=self.selection_items)
            self.config_handler.update_setting("SelectionItems", "items", self.selection_items)
            self.config_handler.delete_section(item)

            if self.selection_var.get() == item:
                if self.selection_items:
                    self.selection_var.set(self.selection_items[0])
                    self.update_selection(self.selection_items[0])
                else:
                    self.selection_var.set("Select")
                    self._set_all_checkboxes(False)  # Clear all checkboxes if no items remain

            self.py_auto_raid.logger.info(f"Removed selection item: {item}")
