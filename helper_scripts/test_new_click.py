import random
import win32gui
import win32api
import win32con
import keyboard
import time

# Specify the name of the game window
game_window_title = "Raid: Shadow Legends"

def get_window_handle(window_title):
    """Get the handle of a specified window."""
    return win32gui.FindWindow(None, window_title)

import ctypes
from ctypes import wintypes

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.ULONG)
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT)
    ]

def click_in_window(hwnd, x, y):
    """Simulate a human-like click at (x, y) using low-level input events."""
    try:
        # Get window rect without activating
        rect = win32gui.GetWindowRect(hwnd)
        win_x, win_y = rect[0], rect[1]
        
        # Add small random offset to click position
        x_jitter = x + random.randint(-2, 2)
        y_jitter = y + random.randint(-2, 2)
        
        # Calculate absolute coordinates
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        abs_x = int(((win_x + x_jitter) / screen_w) * 65535)
        abs_y = int(((win_y + y_jitter) / screen_h) * 65535)
        
        # Create input sequence
        inputs = [
            (abs_x, abs_y, win32con.MOUSEEVENTF_MOVE | win32con.MOUSEEVENTF_ABSOLUTE),
            (0, 0, win32con.MOUSEEVENTF_LEFTDOWN),
            (0, 0, win32con.MOUSEEVENTF_LEFTUP)
        ]
        
        # Execute with random timing
        for dx, dy, flags in inputs:
            input_struct = INPUT()
            input_struct.type = win32con.INPUT_MOUSE
            input_struct.mi = MOUSEINPUT(dx, dy, 0, flags, 0, 0)
            win32api.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))
            time.sleep(random.uniform(0.01, 0.05))
            
        # Add random post-click delay
        time.sleep(random.uniform(0.02, 0.1))
            
    except Exception as e:
        print(f"Click error: {e}")

if __name__ == "__main__":
    hwnd = get_window_handle(game_window_title)
    
    if not hwnd:
        print(f"Could not find a window with the title '{game_window_title}'.")
        exit(1)

    print("Press 'space' to click in the game window.")
    print("Press 'esc' to exit.")

    while True:
        try:
            if keyboard.is_pressed("space"):
                # Example: Click near the center of the window (100, 100 offset from top-left)
                click_in_window(hwnd, 100, 100)
                print("Clicked in the game window.")
                time.sleep(0.2)  # Prevent rapid-fire clicks

            if keyboard.is_pressed("esc"):
                print("Exiting script.")
                break
        except Exception as e:
            print(f"Error: {e}")
            break
