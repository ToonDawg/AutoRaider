import time
from utils.base_command import CommandBase
import numpy as np

class FactionWarsCommand(CommandBase):
    def move_to_faction_position(self, direction):
        """Moves to the left or right to reveal factions."""
        self.logger.info(f"Swiping all the way to the {direction}.")
        if direction == "right":
            self.click_handler.swipe_left(550,1)

        elif direction == "left":
            self.click_handler.swipe_right(1400, 1)
        time.sleep(1)

    def execute(self):
        try:
            self.logger.info("Starting Faction Wars task.")
            
            # Collect rewards if bought something from the shop.
            

            # Close popups and navigate to Faction Wars
            self.logger.info("Attempting to close any existing pop-ups.")
            self.click_handler.delete_popup()

            self.click_handler.click_image("battleBTN.png", "Battle button")
            self.click_handler.click_image("factionWars.png", "Faction Wars option")
            directions = ["right", "left"]

            # Process factions for both directions
            for direction in directions:
                self.move_to_faction_position(direction)
                self.logger.info(f"Processing direction: {direction}")

                # Get all locations of keys.
                FwLocations = self.click_handler._locate_all_buttons("FactionWarBanner.png")
                FwLocations = self.filter_duplicates(FwLocations)

                if not FwLocations:
                    self.logger.warning(f"No locations found for direction: {direction}")
                    continue

                self.logger.info(f"Found {len(FwLocations)} faction locations: {FwLocations}")

                # Loop through locations.
                for location in FwLocations:
                    x, y = location
                    self.logger.debug(f"Attempting to select faction at location: {location}")
                    
                    # Click on the bottom-most stage button
                    self.click_handler.click((x + 50, y + 50), "Clicking Faction")
                    time.sleep(1)

                    # Start stage
                    self.logger.info(f"Starting stage for location: {location}")
                    self.start_stage()
                    time.sleep(5)

                    # Wait for multi-battle completion
                    self.logger.info(f"Waiting for multi-battle completion for direction: {direction}")
                    self.click_handler.wait_for_multi_battle_completion()

                    # Return to faction selection
                    self.return_to_faction_selection(direction)
                    self.logger.info(f"Returned to faction selection for direction: {direction}")

            self.click_handler.back_to_bastion()
            self.logger.info("Faction Wars task completed successfully.")

        except Exception as e:
            self.logger.error(f"Error in FactionWarsCommand: {e}", exc_info=True)
            self.click_handler.back_to_bastion()

    def start_stage(self):
        """Starts a stage and handles multi-battle logic."""
        # Start stage
        while self.click_handler._locate_image("stageStart.png", "Stage Start Button"):
            self.logger.info("Stage Start Button detected. Preparing to select stage.")
            buttons = self.click_handler._locate_all_buttons("stageStart.png")
            if buttons:
                bottom_button = max(buttons, key=lambda b: b[1]) 
                bottom_x, bottom_y = bottom_button

                # Click on the bottom-most stage button
                self.click_handler.click((bottom_x, bottom_y), "Clicking bottom-most stage button")
                time.sleep(1)

                if self.click_handler._locate_image("stageStart.png", "Stage Start Button"):
                    self.logger.warning("Battle button still visible. Pressing ESC to go back.")
                    self.click_handler.press_key("esc", "Escape to cancel stage")
                    time.sleep(1)


        # Start multi-battle
        if self.click_handler._locate_image("multiBattleButton.png", "Multi-battle button detected"):
            self.click_handler.click_image("multiBattleButton.png", "Multi-battle button")
            self.click_handler.click_image("startMultiBattle.png", "Start Multi-battle")
            time.sleep(2)

    def return_to_faction_selection(self, direction):
        """Returns to faction selection after battle completion."""
        if self.click_handler._locate_image("multiBattleComplete.png", "Multi-battle Complete"):
            self.logger.info("Exiting multi-battle to faction selection.")
            self.app.actvate_game_window()
            while not self.click_handler.wait_for_image("factionWarsScreen.png", "FW screen", 1):
                self.click_handler.press_key("esc", "Pressing ESC to exit battle")

            # Move back to the correct faction position
            self.move_to_faction_position(direction)
            
    def filter_duplicates(self, locations, threshold=50):
        filtered = []
        for loc in locations:
            if not any(np.linalg.norm(np.array(loc) - np.array(existing)) < threshold for existing in filtered):
                filtered.append(loc)
        return filtered
