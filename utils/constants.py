"""
Constants used across the AutoRaider automation.
"""

from typing import Tuple

# Screen resolution constants (default expected resolution)
SCREEN_WIDTH: int = 1920
SCREEN_HEIGHT: int = 1080

# Common Coordinates
CENTER_X: int = 960
CENTER_Y: int = 540
CENTER_COORD: Tuple[int, int] = (CENTER_X, CENTER_Y)

# Swipe parameters
DEFAULT_SWIPE_DISTANCE: int = 600
DEFAULT_SWIPE_DURATION: float = 0.3

# Image confidence
DEFAULT_CONFIDENCE: float = 0.8

# Timeouts and Intervals
DEFAULT_WAIT_TIMEOUT: int = 30
DEFAULT_WAIT_INTERVAL: int = 2
