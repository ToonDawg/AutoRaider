import time
import threading
import pytest
from utils.cancellation import CancellationToken
from utils.exceptions import CancellationException


def test_token_initial_state():
    token = CancellationToken()
    assert not token.is_cancelled
    token.raise_if_cancelled()  # Should not raise


def test_token_cancel_and_reset():
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled
    with pytest.raises(CancellationException):
        token.raise_if_cancelled()

    token.reset()
    assert not token.is_cancelled
    token.raise_if_cancelled()


def test_token_sleep_normal():
    token = CancellationToken()
    start = time.perf_counter()
    token.sleep(0.05)
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.04


def test_token_sleep_interrupts_instantly():
    token = CancellationToken()

    def cancel_after_delay():
        time.sleep(0.02)
        token.cancel()

    threading.Thread(target=cancel_after_delay, daemon=True).start()

    start = time.perf_counter()
    with pytest.raises(CancellationException):
        token.sleep(2.0)  # Would sleep 2s if not interrupted
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2, f"Expected instant wake-up, but took {elapsed:.2f}s"


def test_click_handler_cancel_flag_interrupts_sleep():
    import logging
    from utils.click_handler import ClickHandler

    handler = ClickHandler(logger=logging.getLogger("test"))
    assert not handler.cancel_flag

    def set_cancel_flag():
        time.sleep(0.02)
        handler.cancel_flag = True

    threading.Thread(target=set_cancel_flag, daemon=True).start()

    start = time.perf_counter()
    with pytest.raises(CancellationException):
        handler.sleep(5.0)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2, f"ClickHandler sleep was not interrupted instantly, took {elapsed:.2f}s"
    assert handler.cancel_flag

