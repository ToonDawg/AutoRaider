class CancellationException(Exception):
    """Custom exception raised when a task is cancelled."""
    pass

class AutomationError(Exception):
    """Base exception for automation-related errors."""
    pass

class ImageNotFoundError(AutomationError):
    """Raised when an expected image cannot be found on screen."""
    pass

class OCRError(AutomationError):
    """Raised when text recognition fails."""
    pass
