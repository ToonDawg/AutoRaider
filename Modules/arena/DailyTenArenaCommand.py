import time
import pyautogui
import pyscreeze
from typing import Any, Optional, List, Tuple
from utils.base_command import CommandBase

class ClassicArenaCommand(CommandBase):
    def __init__(self, app: Any, logger: Any, click_handler: Any):
        super().__init__(app, logger, click_handler)
        self.classic_battles = 0
        
    def execute(self, count: int = 100) -> None:
        self.logger.info("Starting daily classic arena battles task.")
        try:
            self.click_handler.delete_popup()
            self.classic_battles = 0

            # Navigate to the arena screen
            self._navigate_to_arena()

            # Clean state machine instead of manipulating indexes
            while self.classic_battles < count:
                
                # 1. Fight teams at the TOP of the list
                self._process_visible_teams()
                if self.classic_battles >= count:
                    break
                
                # 2. Scroll and fight teams at the BOTTOM of the list
                self._scroll_to_reveal_teams()
                self._process_visible_teams()
                if self.classic_battles >= count:
                    break

                # 3. Exhausted both top and bottom. Try to refresh.
                if self._safe_locate("arenaRefresh.png"):
                    self.logger.info("Arena refresh available. Clicking it.")
                    self._safe_click("arenaRefresh.png", "Refreshing arena")
                    time.sleep(2) # Give UI a moment to load new teams
                    continue # Loops back to the top of the 'while' loop
                else:
                    self.logger.info("No refresh available and all teams fought. Exiting.")
                    break

        except Exception as e:
            self.logger.error(f"Critical error during classic arena battles: {e}", exc_info=True)
        finally:
            self._cleanup_after_task()


    def _process_visible_teams(self) -> None:
        """Finds all battle buttons on screen and fights them."""
        # Using a safe wrapper to prevent crashes if no buttons are found
        battle_buttons = self._safe_locate_all("arenaBattle.png")
        self.logger.info(f"Detected {len(battle_buttons)} battle buttons.")

        for team_coords in battle_buttons:
            success = self._fight_team(team_coords)
            
            if success:
                self.classic_battles += 1
                self.logger.info(f"Battles completed: {self.classic_battles}")
            elif success is False:
                # If _fight_team returns explicitly False, we are out of coins.
                self.logger.info("Out of Arena Coins. Stopping processing.")
                # Setting count high forces the main loop to exit
                self.classic_battles = 999 
                return


    def _navigate_to_arena(self) -> None:
        """Navigates to the classic arena screen."""
        # Safely click through the menu, allowing slight pauses for UI transitions
        self._safe_click("battleBTN.png", "Navigating to battle menu")
        time.sleep(1)
        self._safe_click("arenaTab.png", "Selecting arena tab")
        time.sleep(1)
        self._safe_click("classicArena.png", "Entering classic arena")
        time.sleep(2) # Longer wait for the actual arena to load


    def _fight_team(self, team_coords: Tuple[int, int]) -> Optional[bool]:
        """Handles the logic for fighting a single team. Returns True if successful, False if out of coins."""
        x, y = team_coords
        self.logger.info(f"Attempting to fight team at ({x}, {y}).")
        
        try:
            self.click_handler.click((x, y), "Selecting team")
            time.sleep(1.5) # Wait for team screen to slide in
            
            # Handle potential Gem Refill popup
            if self._safe_locate("ArenaRefillGems.png"):
                self.logger.info("Refill Gems popup detected! Out of arena tokens.")
                self.click_handler.press_key("esc", "Close Refill window")
                return False 
            
            # Start the battle
            if not self._safe_click("arenaStart.png", "Starting arena battle"):
                self.logger.warning("Could not find the Start Battle button. Skipping team.")
                self.click_handler.press_key("esc", "Back out of team view")
                return None # None means we skipped it, but we aren't out of tokens

            # Dynamic Wait: Wait up to 120 seconds for the battle to finish
            if self.click_handler.wait_for_image("tapToContinue.png", "Waiting for battle completion", timeout=120):
                self._safe_click("tapToContinue.png", "Completing arena battle")
                time.sleep(1)
                self.click_handler.press_key("esc", "Return to Arena list")
                self.logger.info("Completed arena battle successfully.")
                time.sleep(2) # Give the UI time to fade back to the list
                return True
            else:
                self.logger.warning("Battle timed out (took over 120 seconds).")
                self.click_handler.press_key("esc", "Attempting to exit hung battle")
                return None

        except Exception as e:
            self.logger.error(f"Failed interacting with team at {team_coords}: {e}")
            self.click_handler.press_key("esc", "Attempting recovery")
            return None


    def _scroll_to_reveal_teams(self) -> None:
        """Scrolls the screen to reveal more teams."""
        self.logger.info("Swiping down to reveal more teams.")
        # Ensure your cursor is in the middle of the screen before scrolling!
        self.click_handler.swipe_up()
        self.click_handler.swipe_down(30, 2)
        time.sleep(2)


    def _cleanup_after_task(self) -> None:
        """Cleans up after completing the task."""
        # Wrap this in a try/except so if bastion fails, the bot doesn't completely die
        try:
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
            self.logger.info("Returned to bastion and cleared popups.")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    # ==========================================
    # HELPER METHODS FOR EXCEPTION HANDLING
    # ==========================================

    def _safe_locate(self, image_name: str) -> Optional[pyautogui.Box]:
        """Wrapper to safely catch PyAutoGUI/PyScreeze ImageNotFoundExceptions."""
        try:
            return self.click_handler._locate_image(image_name)
        except (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException):
            return None

    def _safe_locate_all(self, image_name: str) -> List[pyautogui.Point]:
        """Wrapper to safely catch PyAutoGUI/PyScreeze ImageNotFoundExceptions for lists."""
        try:
            return self.click_handler._locate_all_buttons(image_name)
        except (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException):
            return []

    def _safe_click(self, image_name: str, description: str = "") -> bool:
        """Wrapper to safely click an image without crashing if missing."""
        try:
            return self.click_handler.click_image(image_name, description)
        except (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException):
            self.logger.debug(f"Could not find image to click: {image_name}")
            return False