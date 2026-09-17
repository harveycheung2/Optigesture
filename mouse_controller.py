import ctypes
from typing import Tuple

# Windows User32 API flags for mouse events
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_WHEEL      = 0x0800
WHEEL_DELTA            = 120


class WindowsMouseController:
    """
    Direct Windows OS mouse controller using ctypes.windll.user32 for high performance,
    low latency, and zero artificial delays.
    """
    def __init__(self):
        # Enable Per-Monitor DPI Awareness so GetSystemMetrics returns true native resolution (e.g. 2880x1620)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        self.user32 = ctypes.windll.user32
        self.screen_width = self.user32.GetSystemMetrics(0)
        self.screen_height = self.user32.GetSystemMetrics(1)
        self.is_left_down = False
        self.is_right_down = False

    def get_screen_size(self) -> Tuple[int, int]:
        return self.screen_width, self.screen_height

    def move_to(self, x: int, y: int):
        """Move OS cursor to absolute screen coordinates (x, y) with boundary clamping."""
        clamped_x = max(0, min(self.screen_width - 1, int(x)))
        clamped_y = max(0, min(self.screen_height - 1, int(y)))
        self.user32.SetCursorPos(clamped_x, clamped_y)

    def left_down(self):
        """Press and hold left mouse button (e.g. For dragging or start of click)."""
        if not self.is_left_down:
            self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            self.is_left_down = True

    def left_up(self):
        """Release left mouse button."""
        if self.is_left_down:
            self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_left_down = False

    def left_click(self):
        """Perform a complete single left click."""
        self.left_down()
        self.left_up()

    def right_down(self):
        """Press and hold right mouse button."""
        if not self.is_right_down:
            self.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            self.is_right_down = True

    def right_up(self):
        """Release right mouse button."""
        if self.is_right_down:
            self.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            self.is_right_down = False

    def right_click(self):
        """Perform a complete single right click."""
        self.right_down()
        self.right_up()

    def scroll(self, amount: int):
        """
        Scroll the mouse wheel.
        amount > 0: scroll up
        amount < 0: scroll down
        """
        raw_delta = int(amount * WHEEL_DELTA)
        self.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, raw_delta, 0)

    def release_all(self):
        """Safety release for any held mouse buttons."""
        if self.is_left_down:
            self.left_up()
        if self.is_right_down:
            self.right_up()
