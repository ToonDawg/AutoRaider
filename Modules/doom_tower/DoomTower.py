import time
import pyautogui
from utils.base_command import CommandBase
from utils.click_handler import ClickHandler

class DoomTowerCommand(CommandBase):
    def __init__(self, app, logger, click_handler):
        super().__init__(app, logger, click_handler)
        self.boss_positions = [(1260, 530), (950, 530)]

    def execute(self):
        """Main execution method for the Doom Tower task."""
        try:
            self.logger.info("Starting Doom Tower task.")
            self.click_handler.delete_popup()

            # Navigate to Doom Tower
            if not self.navigate_to_doom_tower():
                self.logger.error("Failed to navigate to Doom Tower. Exiting task.")
                return

            # # Check and handle difficulties
            self.handle_difficulties()
            self.use_silver_keys()

            self.click_handler.back_to_bastion()
            self.logger.info("Doom Tower task completed successfully.")
        except Exception as e:
            self.logger.error(f"Error in DoomTowerCommand: {e}", exc_info=True)
            self.click_handler.back_to_bastion()

    def navigate_to_doom_tower(self):
        """Navigate to the Doom Tower screen."""
        if not self.click_handler.click_image("battleBTN.png", "Battle button"):
            return False
        self.click_handler.swipe_left()
        return self.click_handler.click_image("doomTower.png", "Doom Tower button")

    def handle_difficulties(self):
        """Handle both difficulties (Hard and Normal)."""
        for difficulty in ["Hard", "Normal"]:
            self.logger.info(f"Switching to {difficulty} difficulty.")
            self.switch_difficulty(difficulty)
            time.sleep(3)
            
            # Check if difficulty is complete
            if self.is_difficulty_complete(difficulty):
                self.logger.info(f"{difficulty} difficulty is complete.")
                continue

            # Complete battles and handle boss stages
            self.complete_doom_tower_battles()

    def switch_difficulty(self, difficulty):
        """Switch between Normal and Hard difficulties."""
        # Confirm we are on the Doom Tower screen
        if not self.click_handler.wait_for_image("doomTowerScreen.png", "Doom Tower screen", timeout=5):
            self.logger.error("Not on the Doom Tower screen. Cannot switch difficulty.")
            return False

        self.logger.info(f"Switching to {difficulty} difficulty.")

        # Click the drop-down menu
        pyautogui.click(600, 750) 
        time.sleep(1)

        # Select the difficulty based on coordinates
        if difficulty == "Normal":
            pyautogui.click(600, 650)  
        elif difficulty == "Hard":
            pyautogui.click(600, 710)  
        else:
            self.logger.error(f"Invalid difficulty: {difficulty}")
            return False

        time.sleep(1)
        return True


    def is_difficulty_complete(self, difficulty):
        """Check if the current difficulty is complete."""
        if self.click_handler.wait_for_image("doomTowerNextStage.png", "Found Next Wave Stage", timeout=1):
                return False
        
        for i in range(5):
            # Check for Wave 119 completion
            if self.click_handler.wait_for_image("wave119Complete.png", "Wave 119 Complete", timeout=.5):
                return True
            
            if self.click_handler.wait_for_image("doomTowerLockedStage.png", "Found a Locked Stage. Difficulty not Complete", timeout=.5):
                return False

            # # Check for shard (Sacred for Hard, Void for Normal) Still need to get Hard 120 Prize screenshot
            shard_image = "sacredShardDT120.png" if difficulty == "Hard" else "voidShardDT120.png"
            if not self.click_handler.wait_for_image(shard_image, f"{difficulty} completion shard", timeout=.5):
                return False
            self.click_handler.swipe_down()

        return True

    def handle_wave(self):
        """Handle a wave battle in the Doom Tower."""
        self.logger.info("Checking for wave stage to battle.")
        
        # Check if wave is available
        if not self.click_handler.wait_for_image("doomTowerNextStage.png", "Next Stage button", timeout=5):
            self.logger.info("No wave stages available.")
            return False

        # Click the next stage
        if not self.click_handler.click_image("doomTowerNextStage.png", "Next Stage button"):
            self.logger.warning("Failed to click on the next wave stage.")
            return False

        # Click start battle
        if not self.click_handler.click_image("doomTowerStartBattle.png", "Start Battle button"):
            self.logger.info("Not enough keys to start wave battle. Exiting.")
            return False

        # Wait for battle completion
        self.logger.info("Wave battle started. Waiting for completion.")
        if not self.click_handler.wait_for_multi_battle_completion():
            self.logger.warning("Wave battle did not complete as expected.")
            self.return_to_DT_screen()
            return False
        
        self.return_to_DT_screen()
        self.logger.info("Wave battle completed successfully.")
        return True


    def handle_boss(self):
        """Handle a boss battle in the Doom Tower."""
        self.logger.info("Attempting to handle a boss battle.")

        # Click to navigate to the boss stage
        pyautogui.click(1260, 530)  # Right side for boss battles
        time.sleep(1)
        pyautogui.click(950, 530)  # Boss stage at level 120 (coordinates may vary)
        time.sleep(1)

        # Click start battle
        if not self.click_handler.click_image("doomTowerStartBattle.png", "Start Battle button"):
            self.logger.info("Not enough keys to start boss battle.")
            return False

        # Wait for battle completion
        self.logger.info("Boss battle started. Waiting for completion.")
        if not self.click_handler.wait_for_battle_completion():
            self.logger.warning("Boss battle did not complete as expected.")
            self.return_to_DT_screen()
            return False

        self.logger.info("Boss battle completed successfully.")
        self.return_to_DT_screen()
        return True


    def complete_doom_tower_battles(self):
        """Complete Doom Tower battles by alternating between waves and bosses."""
        last_battled = None  # None, "Wave", or "Boss"

        for i in range(3):
            if last_battled != "Wave" and self.handle_wave():
                last_battled = "Wave"
                continue 

            if last_battled != "Boss" and self.handle_boss():
                last_battled = "Boss"
                continue 

            # If neither wave nor boss could be handled, exit
            self.logger.info("No battles left or no keys available. Exiting loop.")
            break

        self.logger.info("All available gold keys have been used or no stages left to battle.")

    def use_silver_keys(self):
        """Use Silver Keys to run multi-battles on previously completed bosses."""
        self.logger.info("Using Silver Keys on completed bosses.")

        # Switch to Hard difficulty
        if not self.switch_difficulty("Hard"):
            self.logger.error("Failed to switch to Hard difficulty for Silver Keys.")
            return

        # Check boss positions for multi-battles
        for position in self.boss_positions:
            pyautogui.click(*position)  # Click on the boss position
            time.sleep(1)

            if self.click_handler.wait_for_image("multiBattleButton.png", "Multi-battle button", timeout=2):
                self.logger.info(f"Starting multi-battle on boss position at {position}.")
                if self.click_handler.click_image("multiBattleButton.png", "Multi-battle button"):
                    self.click_handler.click_image("startMultiBattle.png", "Start Multi-battle button")
                    self.logger.info("Multi-battle started. Waiting for completion.")
                    if self.click_handler.wait_for_multi_battle_completion():
                        self.logger.info("Multi-battle completed successfully.")
                        return
                else:
                    self.logger.warning("Failed to start multi-battle.")
            else:
                self.logger.warning(f"No multi-battle available at boss position {position}.")

        self.logger.info("No available bosses to use Silver Keys on.")
        
    def return_to_DT_screen(self):
        while not self.click_handler._locate_image("doomTowerScreen.png", "Doom Tower Screen"):
            self.click_handler.press_key("esc", "Going Back")
            if self.click_handler._locate_image("battleBTN.png", "Bastion"):
                self.navigate_to_doom_tower()
                

