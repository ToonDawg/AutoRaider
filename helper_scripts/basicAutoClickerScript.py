import os
import time
import pyautogui
import logging
import pygetwindow
from utils.click_handler import ClickHandler

logging.basicConfig(
    level=logging.DEBUG,  # Set the minimum logging level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("PyAutoRaid.log"), 
        logging.StreamHandler()               
    ]
)
logger = logging.getLogger(__name__)
class App:
    def __init__(self, asset_path):
        self.asset_path = asset_path

    def delete_popup(self):
        logger.info("Simulating popup deletion.")

    def back_to_bastion(self):
        try:
            logger.info("Navigating back to Bastion.")
            close_LO = None
            max_attempts = 3
            attempts = 0
            go_back_image = os.path.join(self.asset_path, "goBack.png")
            lightning_offer_text_image = os.path.join(self.asset_path, "lightningOfferText.png")
            while attempts < max_attempts:
                if pyautogui.locateOnScreen(lightning_offer_text_image, confidence=0.7):
                    close_LO = os.path.join(self.asset_path, "closeLO.png")
                while pyautogui.locateOnScreen(go_back_image, confidence=0.7):
                    bastionx, bastiony = pyautogui.locateCenterOnScreen(
                        go_back_image, confidence=0.7
                    )
                    pyautogui.click(bastionx, bastiony)
                    time.sleep(2)
                    if close_LO:
                        if pyautogui.locateOnScreen(close_LO, confidence=0.7):
                            bastionx, bastiony = pyautogui.locateCenterOnScreen(
                                close_LO, confidence=0.7
                            )
                            pyautogui.click(bastionx, bastiony)
                            time.sleep(2)
                    logger.info("Successfully navigated back to Bastion.")
                return
            else:
                attempts += 1
                logger.debug(f"goBack.png not found. Attempt {attempts}/{max_attempts}. Retrying...")
                time.sleep(1)
            logger.warning("Failed to navigate back to Bastion after several attempts.")
        except Exception as e:
            logger.error(f"Error in back_to_bastion: {e}")


class DailyQuestsCommand(CommandBase):
    def execute(self):
        try:
            self.logger.info("Starting Clan Boss task.")

            # Static name to look for
            target_name = "RedolentRythm"

            # Image paths
            battle_btn_image = "battleBTN.png"
            clan_boss_image = "CB.png"
            ultra_nightmare_image = "ultraNightmare.png"
            nightmare_image = "nightmare.png"
            no_key_image = "CBnokey.png"
            battle_image = "CBbattle.png"
            start_battle_image = "CBstart.png"

            # Navigate to battle screen
            self.click_handler.click_image(battle_btn_image, "Battle button")
            self.click_handler.click_image(clan_boss_image, "Clan Boss option")

            # Check Ultra Nightmare and Nightmare difficulties
            for difficulty_image in [ultra_nightmare_image, nightmare_image]:
                self.logger.info(f"Checking difficulty: {difficulty_image.split('.')[0]}")
                if not self.click_handler._locate_image(difficulty_image, f"Difficulty {difficulty_image.split('.')[0]} found"):
                    self.logger.warning(f"Difficulty {difficulty_image.split('.')[0]} not available.")
                    continue

                self.click_handler.click_image(difficulty_image, f"Selecting {difficulty_image.split('.')[0]} difficulty")
                time.sleep(1)

                # Scroll through results on the left-hand side
                found_name = self._search_for_name(target_name)
                if found_name:
                    self.logger.info(f"Target name '{target_name}' found in results for {difficulty_image.split('.')[0]}.")
                    return f"Clan Boss already fought for {difficulty_image.split('.')[0]}."

                self.logger.info(f"Target name '{target_name}' not found. Proceeding to battle.")
                if self._start_battle(no_key_image, battle_image, start_battle_image):
                    self.logger.info(f"Battle started for {difficulty_image.split('.')[0]}.")
                    return f"Clan Boss battle started for {difficulty_image.split('.')[0]}."
                else:
                    self.logger.warning(f"No keys available for {difficulty_image.split('.')[0]}.")

            self.logger.info("All Clan Boss difficulties checked. No battles started.")
            return "No Clan Boss battles started."

        except Exception as e:
            self.logger.error(f"Error in ClanBossCommand: {e}", exc_info=True)
            self.click_handler.back_to_bastion()

    def _search_for_name(self, target_name):
        """Scrolls through the left-hand side results looking for the target name."""
        for _ in range(5):  # Arbitrary limit to avoid infinite scrolling
            # Check OCR for the target name in the visible area
            found_name = self.click_handler.text_on_screen_contains(target_name, region=(50, 200, 300, 800))  # Adjust region as needed
            if found_name:
                return True
            self.logger.info("Name not found. Scrolling down.")
            self.click_handler.swipe(0, -200, duration=1)
        return False

    def _start_battle(self, no_key_image, battle_image, start_battle_image):
        """Handles the battle start logic."""
        # Check if the battle button is available
        if not self.click_handler._locate_image(battle_image, "Battle button found"):
            return False

        self.click_handler.click_image(battle_image, "Battle button")
        time.sleep(2)

        # Check for no keys
        if self.click_handler._locate_image(no_key_image, "No key image found"):
            self.logger.warning("No keys available for battle.")
            return False

        # Start the battle
        self.click_handler.click_image(start_battle_image, "Start battle button")
        time.sleep(1)
        return True

# Main logic to run the command
if __name__ == "__main__":
    # Provide the path to the folder containing the image assets
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    asset_path = os.path.join(current_dir, 'assets')
    app = App(asset_path)
    command = DailyQuestsCommand(app, logger, ClickHandler(logger))
    win_list = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")
    win_list[0].activate()
    time.sleep(2)

    command.execute()
    
