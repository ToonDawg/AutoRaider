"""
OCR (Optical Character Recognition) utility for AutoRaider.
Extracts text checking functionality to its own module.
"""

from typing import Optional, Tuple
import pytesseract
from PIL import ImageGrab
import logging

class OCRHandler:
    """Handles text recognition on the screen."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def text_on_screen_contains(self, target_text: str, region: Optional[Tuple[int, int, int, int]] = None) -> bool:
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
                self.logger.debug(f"Found text '{target_text}' on screen.")
                return True
                
            return False
        except pytesseract.TesseractError as e:
            self.logger.error(f"Tesseract OCR Error in text_on_screen_contains: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error in text_on_screen_contains: {e}")
            return False
