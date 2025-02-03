import time
from utils.base_command import CommandBase

class ClassicArenaCommand(CommandBase):
    def __init__(self, app, logger, click_handler):
        super().__init__(app, logger, click_handler)
        self.classic_battles = 0
        
    def execute(self, count=100):
        self.logger.info("Starting daily classic arena battles task.")
        try:
            self.click_handler.delete_popup()
            self.classic_battles = 0

            # Navigate to the arena screen
            self._navigate_to_arena()

            # Initialize state
            fought_teams = set()

            # Define positions to check (top and bottom)
            positions = ["top", "bottom"]
            position_index = 0
            if self.click_handler._locate_image("arenaRefresh.png"):
                self.click_handler.click_image("arenaRefresh.png")
                self.logger.info("Arena refreshed. Retrying.")
                fought_teams.clear()

            while position_index < len(positions):
                is_bottom_position = (positions[position_index] == "bottom")
                if is_bottom_position:
                    self._scroll_to_reveal_teams()
                
                # Locate battle buttons and normalize coordinates
                battle_buttons = self.click_handler._locate_all_buttons("arenaBattle.png")
                self.logger.info(f"Detected battle buttons at positions: {battle_buttons}")

                if not battle_buttons and is_bottom_position:
                    self.logger.info("No teams available to fight at this position.")
                    
                    # Check for arena refresh
                    if self.click_handler._locate_image("arenaRefresh.png"):
                        self.click_handler.click_image("arenaRefresh.png")
                        self.logger.info("Arena refreshed. Retrying.")
                        fought_teams.clear()
                        position_index = 0  # Reset to check top again after refresh
                        continue
                    else:
                        self.logger.info("No refresh available. Exiting.")
                        break

                # Process each team for the current position
                for team_coords in battle_buttons:
                    if team_coords in fought_teams:
                        self.logger.info(f"Skipping already fought team at {team_coords}.")
                        continue

                    # Attempt to fight the team
                    if not self._fight_team(team_coords):
                        self.logger.info("No more Arena Coins. Finishing.")
                        return  # Exit the method entirely

                    # Mark team as fought
                    fought_teams.add(team_coords)
                    self.classic_battles += 1
                    
                    if is_bottom_position:
                        self._scroll_to_reveal_teams()

                    if self.classic_battles >= count:
                        self.logger.info(f"Fought {self.classic_battles} teams. Exiting as per count limit.")
                        return

                # Move to the next position after checking the current one
                position_index += 1

        except Exception as e:
            self.logger.error(f"Error during classic arena battles: {e}", exc_info=True)
        finally:
            self._cleanup_after_task()

    def _navigate_to_arena(self):
        """Navigates to the classic arena screen."""
        if self.click_handler.click_image("battleBTN.png", "Navigating to battle menu"):
            time.sleep(0.5)
        if self.click_handler.click_image("arenaTab.png", "Selecting arena tab"):
            time.sleep(0.5)
        if self.click_handler.click_image("classicArena.png", "Entering classic arena"):
            time.sleep(0.5)

    def _fight_team(self, team_coords):
        """Handles the logic for fighting a single team."""
        x, y = team_coords
        self.logger.info(f"Attempting to fight team at {team_coords}.")
        self.click_handler.click((x, y), "Selecting team for arena battle")
        time.sleep(3)
        
        if self.click_handler.click_image("arenaConfirm.png", "Confirming Arena Coin Refill"):
            self.click_handler.click((x, y), "Selecting team for arena battle")
            time.sleep(3)
        
        if self.click_handler.click_image("arenaStart.png", "Starting arena battle"):
            time.sleep(4)

        if self.click_handler._locate_image("ArenaRefillGems.png"):
            return False        

        self.click_handler.wait_for_image("tapToContinue.png", "Waiting for battle completion", timeout=120)

        while self.click_handler.click_image("tapToContinue.png", "Completing arena battle"):
            self.click_handler.press_key("esc", "Return to Arena")
            self.logger.info("Completed arena battle.")
            self.classic_battles += 1
            time.sleep(1)
        return True
            

    def _scroll_to_reveal_teams(self):
        """Scrolls the screen to reveal more teams."""
        self.logger.info("Swiping to reveal more teams.")
        self.click_handler.swipe_up()
        self.click_handler.swipe_down(30, 2)
        time.sleep(2)

    def _cleanup_after_task(self):
        """Cleans up after completing the task."""
        self.click_handler.back_to_bastion()
        self.click_handler.delete_popup()
        self.logger.info("Returned to bastion and cleared popups.")
