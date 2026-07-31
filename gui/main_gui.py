import customtkinter as ctk
from app.pyAutoRaid import AutoRaider
from utils.config_handler import ConfigHandler
from utils.text_handler import TextHandler
from gui.tasks_tab import TasksTab
from gui.scheduling_tab import SchedulingTab
import logging
from typing import Dict, Any
import pystray
from PIL import Image
from pathlib import Path

import threading

class MainGUI:
    def __init__(self, root: ctk.CTk, py_auto_raid_instance: AutoRaider):
        self.py_auto_raid = py_auto_raid_instance
        self.config_handler = ConfigHandler()
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.checkbox_vars: Dict[Any, ctk.BooleanVar] = {}
        self.root.minsize(660, 500)

        self._setup_window()
        self._create_tabs()
        self._setup_logging()
        self._bind_shortcuts()
        self._setup_tray_icon()
        self._create_minimize_button()

    def _setup_window(self) -> None:
        self.root.title("PyAutoRaid Task Selector")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.tray_icon = None

    def _create_minimize_button(self) -> None:
        # Create a frame to hold both buttons
        button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Minimize button (left)
        self.minimize_button = ctk.CTkButton(
            button_frame, 
            text="Minimize to Tray", 
            command=self.minimize_to_tray, 
            width=120
        )
        self.minimize_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        # Cancel button (right)
        self.cancel_button = ctk.CTkButton(
            button_frame, 
            text="Cancel (F2)", 
            command=self.cancel_manual_run,
            width=120,
            fg_color="#CC3D3D",
            hover_color="#A83232"
        )
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _setup_tray_icon(self) -> None:
         # Load the icon - using the RaidShard icon
        icon_path = Path("assets") / "RaidShard.ico"
        if not icon_path.exists():
            icon_path = Path(__file__).resolve().parent.parent / "assets" / "RaidShard.ico"

        if icon_path.exists():
            image = Image.open(icon_path)
        else:
            image = Image.new('RGB', (64, 64), 'white')

        # Create a menu for the system tray icon
        menu = (
            pystray.MenuItem("Restore", self.restore_from_tray),
            pystray.MenuItem("Exit", self.exit_from_tray),
        )
        self.tray_icon = pystray.Icon("PyAutoRaid", image, "PyAutoRaid", menu)

    def on_window_close(self, event=None) -> None:
        print("on_window_close called - window close button pressed")
        self.minimize_to_tray()
        return "break"

    def minimize_to_tray(self) -> None:
        print("minimize_to_tray called")
        if self.tray_icon:
            self.root.withdraw()
            threading.Thread(target=self.tray_icon.run).start()

    def restore_from_tray(self, tray_icon=None) -> None:
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)
        self.root.after(0, lambda: self.root.wm_state('normal'))

    def exit_from_tray(self, tray_icon=None) -> None:
        if self.tray_icon:
            self.tray_icon.stop()
        self.close_app()

    def _create_tabs(self) -> None:
        self.tab_view = ctk.CTkTabview(self.root)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Tasks Tab
        self.tasks_tab = self.tab_view.add("Tasks")
        self.tasks_tab_instance = TasksTab(self.tasks_tab, self.py_auto_raid, self.config_handler)

        # Assign log_text for logging setup
        self.log_text = self.tasks_tab_instance.log_text

        # Scheduling Tab
        self.scheduling_tab = self.tab_view.add("Scheduling")
        self.scheduling_tab_instance = SchedulingTab(self.scheduling_tab, self.config_handler, self.py_auto_raid)

    def _setup_logging(self) -> None:
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
        )
        self.py_auto_raid.logger.addHandler(text_handler)
        self.py_auto_raid.logger.setLevel(logging.INFO)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<F5>", lambda event: self.close_app())
        self.root.bind("<F2>", lambda event: self.cancel_manual_run())

    def cancel_manual_run(self) -> None:
        self.py_auto_raid.logger.info("Cancelling manual run...")
        if hasattr(self.py_auto_raid, 'click_handler'):
            self.py_auto_raid.click_handler.cancel_flag = True
            self.py_auto_raid.logger.info("Cancel flag set. Task will stop at next safe point.")

    def close_app(self) -> None:
        self.py_auto_raid.logger.info("Application closed by F5 key.")
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
