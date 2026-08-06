"""Cancellation token utility for interruptible async / threaded tasks."""

from __future__ import annotations

import threading
from utils.exceptions import CancellationException


class CancellationToken:
    """Thread-safe cancellation token.

    Allows signaling cancellation across threads and provides interruptible
    sleep operations that wake up immediately when cancelled.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation."""
        self._event.set()

    def reset(self) -> None:
        """Reset cancellation signal."""
        self._event.clear()

    @property
    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        return self._event.is_set()

    def raise_if_cancelled(self, message: str = "Task cancelled by user.") -> None:
        """Raise CancellationException if cancellation was requested."""
        if self._event.is_set():
            raise CancellationException(message)

    def sleep(self, seconds: float) -> None:
        """Sleep for the specified number of seconds.

        Wakes up immediately and raises CancellationException if cancellation
        is requested before or during the sleep duration.
        """
        if seconds <= 0:
            self.raise_if_cancelled()
            return

        is_set = self._event.wait(timeout=seconds)
        if is_set:
            raise CancellationException("Task cancelled by user.")
