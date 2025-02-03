import os
import time
import pyautogui
from utils.base_command import CommandBase

class IronTwinsCommand(CommandBase):
    def execute(self):
        try:
            self.logger.info("Starting Iron Twinstask.")

            # Define image paths
            battle_btn_image = os.path.join(self.app.asset_path, "battleBTN.png")
            dungeons_image = os.path.join(self.app.asset_path, "dungeons.png")
            iron_twins_image = os.path.join(self.app.asset_path, "ironTwinsDungeon.png")
            iron_twins_stage_15_image = os.path.join(self.app.asset_path, "ironTwinsStage15.png")
            multi_battle_image = os.path.join(self.app.asset_path, "multiBattleButton.png")
            start_stage_multi_battle_image = os.path.join(self.app.asset_path, "startMultiBattle.png")
            
            self.logger.info("Attempting to close any existing pop-ups.")
            self.click_handler.delete_popup()

            # Navigate to battle screen
            self.click_handler.click_image(battle_btn_image, "Battle button")

            # Navigate to Dungeons
            self.click_handler.click_image(dungeons_image, "Dungeons button")

            # Open Iron Twins dungeon
            self.click_handler.click_image(iron_twins_image, "Iron Twins dungeon button")

            # Select Stage 15
            while pyautogui.locateOnScreen(iron_twins_stage_15_image, confidence=0.8):
                buttons = list(pyautogui.locateAllOnScreen(iron_twins_stage_15_image, confidence=0.8))
                if buttons:
                    # Find the button with the largest y-coordinate
                    bottom_button = max(buttons, key=lambda b: b.top)
                    bottom_x, bottom_y = pyautogui.center(bottom_button)
                    
                    # Click the battle button
                    pyautogui.click(bottom_x, bottom_y)
                    self.logger.info(f"Clicked on the highest stage Battle button at coordinates: ({bottom_x}, {bottom_y}).")
                    time.sleep(1)

                    # Check if the battle button is still visible
                    if pyautogui.locateOnScreen(iron_twins_stage_15_image, confidence=0.8):
                        self.logger.warning("Battle button is still visible. Pressing escape to go back.")
                        pyautogui.press("esc")
                        time.sleep(1)
                    break
                else:
                    self.logger.warning("No Battle button found.")
                    break
            # Start Multi Battle
            while pyautogui.locateOnScreen(multi_battle_image, confidence=0.8):
                self.logger.info("Multi-battle option detected. Starting multi-battle.")
                x, y = pyautogui.locateCenterOnScreen(multi_battle_image, confidence=0.8)
                pyautogui.click(x, y)
                time.sleep(1)
                x, y = pyautogui.locateCenterOnScreen(start_stage_multi_battle_image, confidence=0.8)
                pyautogui.click(x, y)                
                time.sleep(10)

            
            # Wait for battle to complete.
            self.click_handler.wait_for_multi_battle_completion()
            self.click_handler.back_to_bastion()
                
            self.logger.info("Iron Twins task completed successfully.")
        except Exception as e:
            self.logger.error(f"Error in IronTwinsCommand: {e}", exc_info=True)
            self.click_handler.back_to_bastion()