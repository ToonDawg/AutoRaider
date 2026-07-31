import time
import pyautogui
import pyscreeze
import sys
from pathlib import Path
from typing import Optional, List, Tuple, Any
from utils.exceptions import CancellationException
from utils.constants import (
    CENTER_X, CENTER_Y, DEFAULT_SWIPE_DISTANCE, 
    DEFAULT_SWIPE_DURATION, DEFAULT_CONFIDENCE,
    DEFAULT_WAIT_TIMEOUT, DEFAULT_WAIT_INTERVAL
)
from utils.ocr_handler import OCRHandler

class ClickHandler:
    """A reusable class for handling click-related logic in an auto-clicker app."""

    def __init__(self, logger: Any):
        """
        Initialize the ClickHandler.

        Args:
            logger (logging.Logger): Logger instance for logging actions and errors.
        """
        self.logger = logger
        self.steps: dict[str, str] = {}
        self.asset_path: Optional[Path] = self.get_asset_path()
        self.cancel_flag: bool = False
        self.ocr_handler = OCRHandler(logger)

    def _get_image_path(self, image_name: str) -> str:
        """Helper method to construct the full path for an image."""
        if not self.asset_path:
            return image_name
        return str(self.asset_path / image_name)

    def _locate_image(self, image_name: str, description: str = "") -> Optional[pyautogui.Point | pyautogui.Box]:
        """
        Locate an image on the screen.

        Args:
            image_name (str): Name of the image file to locate.
            description (str): Description for logging purposes.

        Returns:
            pyautogui.Box or None: The location of the image if found, otherwise None
        """
        image_path = self._get_image_path(image_name)
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=DEFAULT_CONFIDENCE)
            if location:
                self.logger.debug(f"Located {description} at: {location}.")
            else:
                self.logger.debug(f"Could not locate {description}.")
            return location
        except (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException):
            self.logger.debug(f"Could not locate {description}.")
            return None
        
    def wait_for_image(self, image_name: str, description: str = "", timeout: int = DEFAULT_WAIT_TIMEOUT, check_interval: int = DEFAULT_WAIT_INTERVAL) -> bool:
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
          
    def click_image(self, image_name: str, description: str = "", retries: int = 1, delay: int = 1) -> bool:
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
        
    def wait_until_disappears(self, image_name: str, description: str = "", timeout: int = DEFAULT_WAIT_TIMEOUT, check_interval: int = DEFAULT_WAIT_INTERVAL) -> bool:
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
            if not pyautogui.locateOnScreen(image_path, confidence=DEFAULT_CONFIDENCE):
                self.logger.info(f"{description} has disappeared from the screen.")
                return True

            self.logger.info(f"Waiting for {description} to disappear...")
            time.sleep(check_interval)

        self.logger.error(f"{description} did not disappear after {timeout} seconds.")
        return False

    def is_multi_battle_active(self) -> bool:
        """Check if a multi-battle or loading screen is active."""
        
        return any(
            self._locate_image(image, "Checking for multi battle")
            for image in ["inBattle.png", "turnOffMultiBattle.png", "loadingScreen.png"]
        )
        
    def is_battle_active(self) -> bool:
        """Check if a battle or loading screen is active."""
        
        return any(
            self._locate_image(image, "Checking for battle")
            for image in ["inBattle.png", "loadingScreen.png"]
        )

    def wait_for_multi_battle_completion(self) -> bool:
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
            
    def wait_for_battle_completion(self) -> bool:
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
        
    def swipe_left(self, distance: int = DEFAULT_SWIPE_DISTANCE, duration: float = DEFAULT_SWIPE_DURATION) -> None:
        """
        Swipe the screen to the left.

        Args:
            distance (int): The distance to swipe in pixels (default is 600).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """

        self.logger.info(f"Swiping left by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(CENTER_X, CENTER_Y)
        pyautogui.dragRel(-distance, 0, duration=duration)
        time.sleep(1)  # Add a small delay

    def swipe_right(self, distance: int = DEFAULT_SWIPE_DISTANCE, duration: float = DEFAULT_SWIPE_DURATION) -> None:
        """
        Swipe the screen to the right.

        Args:
            distance (int): The distance to swipe in pixels (default is 600).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """
        

        self.logger.info(f"Swiping right by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(CENTER_X, CENTER_Y)
        pyautogui.dragRel(distance, 0, duration=duration)
        time.sleep(1)

    def swipe_up(self, distance: int = 400, duration: float = DEFAULT_SWIPE_DURATION, moveFromX: int = CENTER_X, moveFromY: int = CENTER_Y) -> None:
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

    def swipe_down(self, distance: int = 400, duration: float = DEFAULT_SWIPE_DURATION) -> None:
        """
        Swipe the screen downwards.

        Args:
            distance (int): The distance to swipe in pixels (default is 400).
            duration (float): The duration of the swipe in seconds (default is 0.5).
        """

        self.logger.info(f"Swiping down by {distance} pixels over {duration} seconds.")
        pyautogui.moveTo(CENTER_X, CENTER_Y)
        pyautogui.dragRel(0, distance, duration=duration)
        time.sleep(1)
        
    def delete_popup(self) -> None:
        self.logger.info("Attempting to close any pop-up ads.")
        if not self.asset_path:
            return
        exit_add_image = str(self.asset_path / "exitAdd.png")
        self.logger.debug(f"Looking for exitAdd.png at: {exit_add_image}")
        max_attempts = 5
        attempts = 0
        while attempts < max_attempts:
            try:
                location = pyautogui.locateOnScreen(exit_add_image, confidence=DEFAULT_CONFIDENCE)
                if location:
                    adx, ady = pyautogui.center(location)
                    pyautogui.click(adx, ady)
                    time.sleep(4)
                    attempts += 1
                    self.logger.debug(f"Closed a pop-up ad. Attempt {attempts}.")
                else:
                    self.logger.info("No pop-up ads found.")
                    break  # Exit the loop since no ad is found
            except (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException):
                break
            except Exception as e:
                self.logger.error(f"Unexpected error when closing pop-up ad: {e}")
                break  # Exit the loop or handle as needed
        if attempts >= max_attempts:
            self.logger.warning("Reached maximum attempts to close pop-up ads.")
        else:
            self.logger.info("No pop-up ads found or all ads closed.")

    def click(self, coordinates: Tuple[int, int], description: str = "") -> None:
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
        except pyautogui.FailSafeException as e:
            self.logger.error(f"FailSafe triggered clicking at {coordinates}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error clicking at {coordinates}: {e}")
            raise

    def back_to_bastion(self) -> None:
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


            
    def press_key(self, key: str, description: str = "") -> None:
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
        except pyautogui.FailSafeException as e:
            self.logger.error(f"FailSafe triggered pressing key '{key}': {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error pressing key '{key}': {e}")
            raise
    def _locate_all_buttons(self, image_name: str) -> List[pyautogui.Point]:
        """Finds all visible battle buttons on the screen and returns their centers."""
        image_path = self._get_image_path(image_name)
        try:
            return [pyautogui.center(btn) for btn in pyautogui.locateAllOnScreen(image_path, confidence=DEFAULT_CONFIDENCE)]
        except (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException):
            return []

    def get_asset_path(self) -> Optional[Path]:
        try:
            # Start with the directory of the current script
            current_dir = Path(__file__).resolve().parent
            while True:
                # Construct the path to the assets folder
                asset_path_candidate = current_dir / 'assets'

                # Check if the assets path exists
                if asset_path_candidate.exists() and asset_path_candidate.is_dir():
                    self.steps["Asset_path"] = "True"
                    self.logger.info(f"Assets folder found at {asset_path_candidate}")
                    return asset_path_candidate

                # Move up one directory level
                new_dir = current_dir.parent
                if new_dir == current_dir:
                    # We are at the root directory and didn't find the assets folder
                    self.logger.error("Assets folder not found.")
                    self.steps["Asset_path"] = "False"
                    if getattr(self, 'folders_for_exe', lambda: True)() == False:
                        self.logger.error("Could not find the assets folder. This folder contains all of the images needed for this program to use. It must be in the same folder as this program.")
                        sys.exit(1)
                    return None
                else:
                    current_dir = new_dir
        except Exception as e:
            self.logger.error(f"Error in get_asset_path: {e}")
            sys.exit(1)
            
    def text_on_screen_contains(self, target_text: str, region: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """
        Checks if the target text is present on the screen using OCR.
        
        Args:
            target_text (str): The text to search for on the screen.
            region (tuple): The region to capture (left, top, width, height). Default is the full screen.
        
        Returns:
            bool: True if the target text is found, False otherwise.
        """
        return self.ocr_handler.text_on_screen_contains(target_text, region)
    
    def scroll_to_top(self) -> None:
        """Scroll to the top of the Doom Tower screen."""
        self.logger.info("Scrolling to the top of the Doom Tower screen.")
        for _ in range(3):  # Adjust range based on screen length
            self.swipe_down()  # Scroll up
            time.sleep(.3)
