from tkinter import Tk
from logging import Logger
import os
import platform
import subprocess
import time
from pathlib import Path
import threading
import pygetwindow as gw
import sys
from Modules.arena.DailyTenArenaCommand import ClassicArenaCommand
from Modules.arena.TagTeamArenaCommand import TagTeamArenaCommand
from Modules.clan_boss.ClanBossCommand import ClanBossCommand
from Modules.daily_quests.DailyQuests import DailyQuestsCommand
from Modules.daily_quests.RewardsCommand import RewardsCommand
from Modules.doom_tower.DoomTower import DoomTowerCommand
from Modules.dungeons.IronTwins import IronTwinsCommand
from Modules.faction_wars.FactionWars import FactionWarsCommand
from utils.base_command import CommandBase
from utils.command_factory import CommandFactory, CommandKeys
from utils.click_handler import ClickHandler

from utils.config_handler import ConfigHandler
from utils.scheduler import TaskScheduler


class AutoRaider:
    def __init__(self, tk_root: Tk, logger: Logger):
        self.tk_root = tk_root
        self.logger = logger
        self.click_handler = ClickHandler(logger)
        self.command_factory = CommandFactory(self, logger, self.click_handler)
        self.config_handler = ConfigHandler()
        self.steps = {}
        self.scheduler = TaskScheduler(self, logger)
        self.scheduler.start()

        # Register commands
        self.command_factory.register_command(CommandKeys.DAILY_QUESTS, "Daily Quests", DailyQuestsCommand)
        self.command_factory.register_command(CommandKeys.TAG_TEAM_ARENA, "Tag Team Arena", TagTeamArenaCommand)
        self.command_factory.register_command(CommandKeys.DAILY_TEN_CLASSIC_ARENA, "Classic Arena", ClassicArenaCommand)
        self.command_factory.register_command(CommandKeys.IRON_TWINS, "Iron Twins", IronTwinsCommand)
        self.command_factory.register_command(CommandKeys.DOOM_TOWER, "Doom Tower", DoomTowerCommand)
        self.command_factory.register_command(CommandKeys.CLANBOSS, "Clan Boss", ClanBossCommand)
        self.command_factory.register_command(CommandKeys.REWARDS, "Collect Rewards", RewardsCommand)
        self.command_factory.register_command(CommandKeys.FACTION_WARS, "Faction Wars", FactionWarsCommand)

        # Initialization steps
        self.os = self.check_os()
        self.asset_path = self.get_asset_path()
        self.raid_path = self.find_raid_path()

        game_windows = gw.getWindowsWithTitle("Raid: Shadow Legends")
        if game_windows:
            self.raid_window = game_windows[0]



    def check_os(self):
        try:
            operating_system = platform.system()
            if operating_system != "Windows":
                self.logger.error("Unsupported OS detected. This program only works on Windows.")
                sys.exit(1)
            self.logger.info(f"Operating system detected: {operating_system}")
            return operating_system
        except Exception as e:
            self.logger.error(f"Error checking OS: {e}")
            raise

    def get_asset_path(self):
        try:
            current_dir = Path(__file__).resolve().parent
            while True:
                asset_path = current_dir / "assets"
                if asset_path.exists():
                    self.logger.info(f"Assets folder found: {asset_path}")
                    return str(asset_path)

                # Move up one directory level
                new_dir = current_dir.parent
                if new_dir == current_dir:
                    self.logger.error("Assets folder not found.")
                    sys.exit(1)
                current_dir = new_dir
        except Exception as e:
            self.logger.error(f"Error finding assets path: {e}")
            raise

    def find_raid_path(self):
        try:
            appdata_local = os.getenv("LOCALAPPDATA")
            if not appdata_local:
                raise ValueError("LOCALAPPDATA environment variable not found")
            base_path = Path(appdata_local) / "PlariumPlay" / "StandAloneApps" / "raid-shadow-legends"

            # Recursively search for Raid.exe
            for root, dirs, files in os.walk(base_path, topdown=True):
                if "Raid.exe" in files:
                    raid_path = Path(root) / "Raid.exe"
                    self.logger.info(f"Raid executable found at: {raid_path}")
                    return str(raid_path)

            self.logger.error("Raid executable not found. Please ensure it is installed.")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Error finding Raid executable: {e}")
            raise

    def make_sure_raid_is_open(self):
        try:
            game_windows = gw.getWindowsWithTitle("Raid: Shadow Legends")
            if not game_windows:
                self.logger.info("Raid is not running. Attempting to open the game.")
                self.open_raid()
            else:
                self.logger.info("Raid is already running. Configuring the window.")
                self.configure_game_window()
        except Exception as e:
            self.logger.error(f"Error ensuring Raid is open: {e}")
            raise

    def open_raid(self):
        try:
            appdata_local = os.getenv("LOCALAPPDATA")
            if not appdata_local:
                raise ValueError("LOCALAPPDATA environment variable not found")
            plarium_play_path = Path(appdata_local) / "PlariumPlay" / "PlariumPlay.exe"
            subprocess.Popen(
                [
                    str(plarium_play_path),
                    "--args",
                    "-gameid=101",
                    "-tray-start",
                ]
            )
            self.logger.info("Opening Raid via PlariumPlay...")
            time.sleep(10)
            self.configure_game_window()
        except Exception as e:
            self.logger.error(f"Error opening Raid: {e}")
            raise

    def configure_game_window(self):
        try:
            game_windows = gw.getWindowsWithTitle("Raid: Shadow Legends")
            if not game_windows:
                self.logger.warning("Raid window not found. Skipping configuration.")
                return

            self.raid_window = game_windows[0]
            self.raid_window.restore()
            self.raid_window.resizeTo(900, 600)
            self.raid_window.moveTo(500, 200)
            self.raid_window.activate()
            
            self.logger.info("Raid window resized and centered successfully.")
        except Exception as e:
            self.logger.error(f"Error configuring game window: {e}")
            raise

    def actvate_game_window(self):
        try:
            self.raid_window.activate()
            self.logger.info("Raid window activated successfully.")
        except Exception as e:
            self.logger.error(f"Error configuring game window: {e}")
            raise
        
    def run_command(self, key):
        self.configure_game_window()
        command: CommandBase = self.command_factory.get_command(key)
        if command:
            self.click_handler.back_to_bastion()
            command.execute()

    def _process_commands(self, task_keys):
        """Process multiple commands sequentially"""
        for key in task_keys:
            if self.click_handler.cancel_flag:
                break
            self.run_command(key)

    def run_task(self, task_name: str, on_complete=None, on_error=None):
        """Execute all enabled commands for a given task name.
        
        Args:
            task_name: Name of the task to run
            on_complete: Optional callback when task completes successfully
            on_error: Optional callback when task encounters an error
        """
        if not task_name:
            self.logger.error("Task name is missing or invalid")
            if on_error:
                on_error("Task name is missing or invalid")
            return

        self.logger.info(f"Running task: {task_name}")
        self.click_handler.cancel_flag = False
        self.make_sure_raid_is_open()

        
        # Retrieve the entire "Tasks" section as a dictionary
        task_section = self.config_handler.read_setting(task_name, None)
        
        if not task_section:
            self.logger.error(f"Tasks section not found in configuration")
            if on_error:
                on_error("Task configuration not found")
            return

        task_commands = []
        # Collect enabled commands
        for command_key, enabled in task_section.items():
            if enabled.lower() == "true":
                task_commands.append(command_key)
        
        if task_commands:
            def run_task_commands():
                try:
                    self._process_commands(task_commands)
                    self.logger.info(f"All commands completed for task: {task_name}")
                    if on_complete:
                        self.tk_root.after(0, on_complete)
                except Exception as e:
                    self.logger.error(f"Error executing task {task_name}: {str(e)}")
                    if on_error:
                        self.tk_root.after(0, lambda: on_error(str(e)))
            
            # Run commands in background thread
            thread = threading.Thread(target=run_task_commands, daemon=True)
            thread.start()
        else:
            self.logger.warning(f"No enabled commands found for task: {task_name}")
            if on_error:
                on_error("No enabled commands found for task")


    def close_raid(self):
        """Close the Raid game window if it's open"""
        try:
            self.logger.info("Closing Raid window...")
            self.raid_window[0].close()
            self.raid_window.activate()
            time.sleep(2) 
            self.click_handler.click_image("OKbutton.PNG", "Close Window")

        except Exception as e:
            self.logger.error(f"Error closing Raid window: {e}")
            raise

    def shutdown(self):
        """Cleanup resources before exit"""
        if self.scheduler:
            self.scheduler.stop()
