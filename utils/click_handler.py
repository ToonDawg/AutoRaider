import time
import pyautogui
import os
import sys
import pytesseract
from PIL import ImageGrab
from utils.exceptions import CancellationException

class ClickHandler:
    """A reusable class for handling click-related logic in an auto-clicker app."""

    def __init__(self, logger):
        """
        Initialize the ClickHandler.

        Args:
            logger (logging.Logger): Logger instance for logging actions and errors.
            asset_path (str): Base path where the image assets are stored.
        """
        self.logger = logger
        self.steps = {}
        self.asset_path = self.get_asset_path()
        self.cancel_flag = False

    def _get_image_path(self, image_name):
        """Helper method to construct the full path for an image."""
        return os.path.join(self.asset_path, image_name)

    def _locate_image(self, image_name, description=""):
        """
        Locate an image on the screen.

        Args:
            image_name (str): Name of the image file to locate.
            description (str): Description for logging purposes.

        Returns:
            pyautogui.Box or None: The location of the image if found, otherwise None
        """
        image_path = self._get_image_path(image_name)
        location = pyautogui.locateOnScreen(image_path, confidence=0.8)
        if location:
             self.logger.debug(f"Located {description} at: {location}.")
        else:
             self.logger.debug(f"Could not locate {description}.")
        return location
        
    def wait_for_image(self, image_name, description="", timeout=30, check_interval=2):
        """
        Wait until an image appears on the screen.

        Args:
            image_name (str): Name of the image file to locate.
            description (str): Description for logging purposes.
            timeout (int): Maximum time to wait (in seconds).
            check_interval (int): Time to wait between checks (in seconds)
        Returns:
            bool: True if image appeared, False if timeout
        """
        if self.cancel_flag:
            self.logger.info("Task cancellation requested during wait_for_image.")
            raise CancellationException("Task cancelled by user.")

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.cancel_flag:
                self.logger.info("Task cancellation requested during wait_for_image.")
                raise CancellationException("Task cancelled by user.")
            if self._locate_image(image_name, description) :
                self.logger.info(f"{description} has appeared on the screen.")
                return True
            self.logger.info(f"Waiting for {description} to appear...")
            time.sleep(check_interval)
        self.logger.error(f"{description} did not appear after {timeout} seconds.")
        return False
          
    def click_image(self, image_name, description="", retries=1, delay=1):
        """
        Locate an image on the screen and click it.

        Args:
            image_name (str): Name of the image file to locate.
            description (str): Description for logging purposes.
            retries (int): Number of retries if the image is not found.
            delay (int): Delay (in seconds) between retries.

        Returns:
            bool: True if the image was found and clicked, False otherwise.
        """
        if self.cancel_flag:
            self.logger.info("Task cancellation requested during click_image.")
            raise CancellationException("Task cancelled by user.")
            
        for attempt in range(retries):
            if self.cancel_flag:
                self.logger.info("Task cancellation requested during click_image.")
                raise CancellationException("Task cancelled by user.")
            location = self._locate_image(image_name, description)
            if location:
                x, y = pyautogui.center(location)
                pyautogui.click(x, y)
                self.logger.info(f"Clicked on {description} at ({x}, {y}).")
                time.sleep(delay)
                return True

            self.logger.warning(f"{description} not found. Retrying ({attempt + 1}/{retries})...")
            time.sleep(delay)

        self.logger.error(f"Failed to click on {description} after {retries} retries.")
        return False
        
    def wait_until_disappears(self, image_name, description="", timeout=30, check_interval=2):
        """
        Wait until an image disappears from the screen.

        Args:
            image_name (str): Name of the image file to locate.
            description (str): Description for logging purposes.
            timeout (int): Maximum time to wait (in seconds).
            check_interval (int): Time to wait between checks

        Returns:
            bool: True if the image disappeared, False if timeout was reached.
        """
        if self.cancel_flag:
            self.logger.info("Task cancellation requested during wait_until_disappears.")
            raise CancellationException("Task cancelled by user.")

        image_path = self._get_image_path(image_name)
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.cancel_flag:
                self.logger.info("Task cancellation requested during wait_until_disappears.")
                raise CancellationException("Task cancelled by user.")
            if not pyautogui.locateOnScreen(image_path, confidence=0.8):
                self.logger.info(f"{description} has disappeared from the screen.")
                return True

            self.logger.info(f"Waiting for {description} to disappear...")
            time.sleep(check_interval)

        self.logger.error(f"{description} did not disappear after {timeout} seconds.")
        return False

    def is_multi_battle_active(self):
        """Check if a multi-battle or loading screen is active."""
        
        return any(
            self._locate_image(image, "Checking for multi battle")
            for image in ["inBattle.png", "turnOffMultiBattle.png", "loadingScreen.png", "inBattle.png", "turnOffMultiBattle.png", "loadingScreen.png"] # Wanted to do retries for the weird minor states it can be found on. But whatever.
        )
        
    def is_battle_active(self):
        """Check if a battle or loading screen is active."""
        
        return any(
            self._locate_image(image, "Checking for battle")
            for image in ["inBattle.png", "loadingScreen.png"]
        )

    def wait_for_multi_battle_completion(self):
        """Wait until the multi-battle is complete."""
        time.sleep(5)

        if not self.is_multi_battle_active():
            self.logger.info("No active multi-battle detected.")
            return True

        while True:
            if self.is_multi_battle_active():
                self.logger.info("Battle is ongoing or loading screen detected. Waiting for results...")
                time.sleep(10)
                continue

            if self._locate_image("multiBattleComplete.png", "multi-battle complete image"):
                self.logger.info("Multi-battle is complete.")
                return True
            
            self.logger.warning("Unexpected state: No in-battle or complete image detected. Retrying...")
            time.sleep(2)
            
    def wait_for_battle_completion(self):
        """Wait until the battle is complete.""" 
        if not self.is_multi_battle_active():
            self.logger.info("No active battle detected.")
            return True

        while True:
            if self.is_battle_active():
                self.logger.info("Battle is ongoing or loading screen detected. Waiting for results...")
                time.sleep(10)
                continue

            if self._locate_image("bastion.png", "battle complete image"):
                self.logger.info("Battle is complete.")
                return True
            
            self.logger.warning("Unexpected state: No in-battle or complete image detected. Retrying...")
            time.sleep(2)
        
    def swipe_left(self, distance=600, duration=0.3):
        """
        Swipe the screen to the left.

        Args:
            distance (int): The distance to swipe in pixels (default is 600).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """

        self.logger.info(f"Swiping left by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(960, 540)
        pyautogui.dragRel(-distance, 0, duration=duration)
        time.sleep(1)  # Add a small delay

    def swipe_right(self, distance=600, duration=0.3):
        """
        Swipe the screen to the right.

        Args:
            distance (int): The distance to swipe in pixels (default is 600).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """
        

        self.logger.info(f"Swiping right by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(960, 540)
        pyautogui.dragRel(distance, 0, duration=duration)
        time.sleep(1)

    def swipe_up(self, distance=400, duration=0.3, moveFromX=960, moveFromY=540):
        """
        Swipe the screen upwards.

        Args:
            distance (int): The distance to swipe in pixels (default is 400).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """

        self.logger.info(f"Swiping up by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(moveFromX, moveFromY)
        pyautogui.dragRel(0, -distance, duration=duration)
        time.sleep(1)

    def swipe_down(self, distance=400, duration=0.3):
        """
        Swipe the screen downwards.

        Args:
            distance (int): The distance to swipe in pixels (default is 400).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """

        self.logger.info(f"Swiping down by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(960, 540)
        pyautogui.dragRel(0, distance, duration=duration)
        time.sleep(1)
        
    def delete_popup(self):
        self.logger.info("Attempting to close any pop-up ads.")
        exit_add_image = os.path.join(self.asset_path, "exitAdd.png")
        self.logger.debug(f"Looking for exitAdd.png at: {exit_add_image}")
        max_attempts = 5
        attempts = 0
        while attempts < max_attempts:
            try:
                location = pyautogui.locateOnScreen(exit_add_image, confidence=0.8)
                if location:
                    adx, ady = pyautogui.center(location)
                    pyautogui.click(adx, ady)
                    time.sleep(4)
                    attempts += 1
                    self.logger.debug(f"Closed a pop-up ad. Attempt {attempts}.")
                else:
                    self.logger.info("No pop-up ads found.")
                    break  # Exit the loop since no ad is found
            except Exception as e:
                break  # Exit the loop or handle as needed
        if attempts >= max_attempts:
            self.logger.warning("Reached maximum attempts to close pop-up ads.")
        else:
            self.logger.info("No pop-up ads found or all ads closed.")

    def click(self, coordinates, description=""):
        """
        Clicks at the given screen coordinates.

        :param coordinates: A tuple (x, y) representing the screen coordinates to click.
        :param description: Optional description for logging the action.
        """
        try:
            if description:
                self.logger.info(f"Clicking at {coordinates}: {description}")
            else:
                self.logger.info(f"Clicking at {coordinates}")
            
            # Move the mouse to the coordinates and click
            pyautogui.moveTo(coordinates[0], coordinates[1])
            pyautogui.click()
        except Exception as e:
            self.logger.error(f"Error clicking at {coordinates}: {e}")
            raise

    def back_to_bastion(self):
        try:
            self.logger.info("Navigating back to Bastion.")
            
            # Paths for images
            quit_game_image = "quitGame.png"
            lightning_offer_text_image = "lightningOfferClose.png"
            go_back = "goBack.png"
            
            while True:
                # Press ESC to attempt navigation
                self.press_key("esc", "Pressing ESC key to navigate back.")
                time.sleep(.5)

                # Look for Lightning Offer popup and handle it
                if self._locate_image(lightning_offer_text_image, "Lightning Offer detected"):
                    self.click_image(lightning_offer_text_image, "Clicking Lightning Offer popup")
                    time.sleep(.5)
                
                # Check for the Quit Game screen
                if self._locate_image(quit_game_image, "Quit Game detected"):
                    self.logger.info("Quit Game screen found. Pressing ESC one more time to confirm.")
                    self.press_key("esc", "Pressing ESC key to confirm.")
                    time.sleep(.5)

                    # Confirm we're back in Bastion by checking there is no close image
                    if not self._locate_image(go_back):
                        self.logger.info("Successfully navigated back to Bastion.")
                        return

                # Log progress if no critical conditions are met
                self.logger.info("No Quit Game or Battle screen detected. Continuing ESC loop.")

        except Exception as e:
            self.logger.error(f"Error in back_to_bastion: {e}", exc_info=True)


            
    def press_key(self, key, description=""):
        """
        Simulates a key press.

        :param key: The key to press (e.g., "esc", "enter", "i", etc.).
        :param description: Optional description for logging the action.
        """
        try:
            if description:
                self.logger.info(f"Pressing key '{key}': {description}")
            else:
                self.logger.info(f"Pressing key '{key}'")

            # Simulate key press
            pyautogui.press(key)
        except Exception as e:
            self.logger.error(f"Error pressing key '{key}': {e}")
            raise
    def _locate_all_buttons(self, image_name):
        """Finds all visible battle buttons on the screen and returns their centers."""
        image_path = self._get_image_path(image_name)
        return [pyautogui.center(btn) for btn in pyautogui.locateAllOnScreen(image_path, confidence=0.8)]

    def get_asset_path(self):
        try:
            # Start with the directory of the current script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            while True:
                # Construct the path to the assets folder
                self.asset_path = os.path.join(current_dir, 'assets')

                # Check if the assets path exists
                if os.path.exists(self.asset_path):
                    self.steps["Asset_path"] = "True"
                    self.logger.info(f"Assets folder found at {self.asset_path}")
                    return self.asset_path

                # Move up one directory level
                new_dir = os.path.dirname(current_dir)
                if new_dir == current_dir:
                    # We are at the root directory and didn't find the assets folder
                    self.logger.error("Assets folder not found.")
                    self.steps["Asset_path"] = "False"
                    if self.folders_for_exe() == False:
                        self.logging.error("Could not find the assets folder. This folder contains all of the images needed for this program to use. It must be in the same folder as this program.")
                        sys.exit(1)
                    return None
                else:
                    current_dir = new_dir
        except Exception as e:
            self.logger.error(f"Error in get_asset_path: {e}")
            sys.exit(1)
            
    def text_on_screen_contains(self, target_text, region=None):
        """
        Checks if the target text is present on the screen using OCR.
        
        Args:
            target_text (str): The text to search for on the screen.
            region (tuple): The region to capture (left, top, width, height). Default is the full screen.
        
        Returns:
            bool: True if the target text is found, False otherwise.
        """
        try:
            # Capture the screen or the specified region
            screen = ImageGrab.grab(bbox=region) if region else ImageGrab.grab()

            # Perform OCR on the captured screen
            ocr_result = pytesseract.image_to_string(screen)

            # Check if the target text exists in the OCR result
            if target_text.lower() in ocr_result.lower():
                return True
            return False
        except Exception as e:
            print(f"Error in text_on_screen_contains: {e}")
            return False
    
    def scroll_to_top(self):
        """Scroll to the top of the Doom Tower screen."""
        self.logger.info("Scrolling to the top of the Doom Tower screen.")
        for _ in range(3):  # Adjust range based on screen length
            self.swipe_down()  # Scroll up
            time.sleep(.3)
