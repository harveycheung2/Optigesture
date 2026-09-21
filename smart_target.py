import time
import math
import threading
from typing import Dict, Optional, Tuple
import ctypes

from springs import Spring2D

try:
    import uiautomation as auto
    HAS_UIAUTOMATION = True
except ImportError:
    HAS_UIAUTOMATION = False


class SmartTargetAssistant:
    """
    Discovers nearby interactive buttons, tabs, links, and controls on Windows.
    Provides:
    1. Tab-Style Focus Ring Highlighting (visual frame around active control).
    2. Apple-Grade Spring Magnetic Snapping (critically damped smooth pull towards button center).
    Runs asynchronously in a background thread to prevent any camera / tracking lag.
    """

    INTERACTIVE_TYPES = {
        "ButtonControl", "TabItemControl", "HyperlinkControl", "MenuItemControl",
        "CheckBoxControl", "RadioButtonControl", "EditControl", "ListItemControl",
        "ComboBoxControl", "SplitButtonControl", "ToolBarControl"
    }

    def __init__(
        self,
        snap_radius: float = 45.0,
        snap_strength: float = 0.55,
        enable_snap: bool = True,
        enable_overlay: bool = True,
        spring_damping: float = 1.0,
        spring_response: float = 0.35,
    ):
        self.snap_radius = snap_radius
        self.snap_strength = snap_strength
        self.enable_snap = enable_snap
        self.enable_overlay = enable_overlay

        # Apple Fluid Spring for magnetic cursor settling
        self.spring = Spring2D(damping_ratio=spring_damping, response=spring_response)
        self.is_snapped = False
        self.last_snap_time = time.time()
        self.active_target_id = None

        self.last_query_time = 0.0
        self.query_interval = 0.06  # ~16 Hz check rate for UI elements

        self.current_target: Optional[Dict] = None
        self.latest_cursor_pos: Tuple[int, int] = (0, 0)
        self.lock = threading.Lock()

        self._running = True
        self._thread: Optional[threading.Thread] = None
        self._overlay_window = None

        if HAS_UIAUTOMATION:
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()

        if self.enable_overlay:
            self._init_overlay_thread()

    def _init_overlay_thread(self):
        """Initializes a transparent click-through focus overlay window on a background thread."""
        def overlay_worker():
            try:
                import tkinter as tk
                root = tk.Tk()
                root.overrideredirect(True)
                root.wm_attributes("-topmost", True)
                root.wm_attributes("-alpha", 0.85)

                # Configure click-through via Win32 extended window styles
                hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00000020 | 0x00080000)  # WS_EX_TRANSPARENT | WS_EX_LAYERED

                canvas = tk.Canvas(root, bg="#101018", highlightthickness=0)
                canvas.pack(fill="both", expand=True)

                root.geometry("1x1+-1000+-1000")  # Start offscreen
                self._overlay_window = (root, canvas)

                last_drawn_rect = None

                while self._running:
                    with self.lock:
                        target = self.current_target

                    if target and target.get("rect") and self.enable_overlay:
                        rect = target["rect"]  # (left, top, right, bottom)
                        l, t, r, b = rect
                        w = max(4, r - l)
                        h = max(4, b - t)

                        # Check if within snap radius to display focus ring
                        dist = target.get("distance", 999.0)
                        if dist <= self.snap_radius * 1.6:
                            if rect != last_drawn_rect:
                                root.geometry(f"{w+8}x{h+8}+{l-4}+{t-4}")
                                canvas.delete("all")
                                # Draw glowing focus rectangle (Tab-style focus ring)
                                canvas.create_rectangle(2, 2, w+6, h+6, outline="#00FFCC", width=3)
                                canvas.create_rectangle(0, 0, w+8, h+8, outline="#0088AA", width=1)
                                last_drawn_rect = rect
                        else:
                            if last_drawn_rect is not None:
                                root.geometry("1x1+-1000+-1000")
                                last_drawn_rect = None
                    else:
                        if last_drawn_rect is not None:
                            root.geometry("1x1+-1000+-1000")
                            last_drawn_rect = None

                    try:
                        root.update_idletasks()
                        root.update()
                    except Exception:
                        break
                    time.sleep(0.02)

                try:
                    root.withdraw()
                except Exception:
                    pass
            except Exception:
                pass

        try:
            t = threading.Thread(target=overlay_worker, daemon=True)
            t.start()
        except Exception:
            pass

    def update_cursor_position(self, screen_x: int, screen_y: int):
        """Updates the latest cursor position for the background inspector."""
        with self.lock:
            self.latest_cursor_pos = (screen_x, screen_y)

    def apply_magnetic_snap(
        self,
        screen_x: float,
        screen_y: float,
        curr_time: Optional[float] = None,
    ) -> Tuple[float, float, Optional[Dict]]:
        """
        Applies Apple-grade critically damped spring attraction towards the center of a nearby button/control.
        Returns: (snapped_x, snapped_y, target_info_dict)
        """
        now = curr_time if curr_time is not None else time.time()
        dt = max(0.001, min(0.10, now - self.last_snap_time))
        self.last_snap_time = now

        self.update_cursor_position(int(screen_x), int(screen_y))

        if not self.enable_snap:
            self.is_snapped = False
            self.active_target_id = None
            return screen_x, screen_y, None

        with self.lock:
            target = self.current_target

        if not target:
            if self.is_snapped:
                self.spring.set_target(screen_x, screen_y)
                snapped_x, snapped_y = self.spring.update(dt)
                if math.hypot(snapped_x - screen_x, snapped_y - screen_y) < 2.0:
                    self.is_snapped = False
                    self.active_target_id = None
                    return screen_x, screen_y, None
                return snapped_x, snapped_y, None
            return screen_x, screen_y, None

        center_x, center_y = target["center"]
        dist = target["distance"]

        if dist <= self.snap_radius:
            proximity_factor = 1.0 - (dist / self.snap_radius)
            # Quadratic tactile pull: soft entry at boundary, firm pull near button center
            pull = self.snap_strength * (proximity_factor ** 1.3)
            goal_x = screen_x + (center_x - screen_x) * pull
            goal_y = screen_y + (center_y - screen_y) * pull

            target_id = (target.get("name"), center_x, center_y)
            just_snapped = False
            if not self.is_snapped or self.active_target_id != target_id:
                just_snapped = True
                self.is_snapped = True
                self.active_target_id = target_id
                self.spring.reset(screen_x, screen_y)

            self.spring.set_target(goal_x, goal_y)
            snapped_x, snapped_y = self.spring.update(dt)

            target_copy = dict(target)
            target_copy["just_snapped"] = just_snapped
            target_copy["proximity"] = proximity_factor
            return snapped_x, snapped_y, target_copy

        if self.is_snapped:
            # Smooth spring release when cursor pulls away
            self.spring.set_target(screen_x, screen_y)
            snapped_x, snapped_y = self.spring.update(dt)
            if math.hypot(snapped_x - screen_x, snapped_y - screen_y) < 2.0:
                self.is_snapped = False
                self.active_target_id = None
                return screen_x, screen_y, target
            return snapped_x, snapped_y, target

        return screen_x, screen_y, target

    def _worker_loop(self):
        """Background thread worker querying Windows UI Automation."""
        while self._running:
            time.sleep(self.query_interval)
            with self.lock:
                cx, cy = self.latest_cursor_pos

            target = self._inspect_point(cx, cy)
            with self.lock:
                self.current_target = target

    def _inspect_point(self, x: int, y: int) -> Optional[Dict]:
        """Queries UI Automation control near point (x, y)."""
        if not HAS_UIAUTOMATION:
            return None

        try:
            ctrl = auto.ControlFromPoint(x, y)
            if not ctrl:
                return None

            # Walk up to find nearest interactive parent if needed
            active_ctrl = None
            curr = ctrl
            for _ in range(3):
                if not curr:
                    break
                type_name = getattr(curr, "ControlTypeName", "")
                if type_name in self.INTERACTIVE_TYPES:
                    active_ctrl = curr
                    break
                curr = curr.GetParentControl()

            if not active_ctrl:
                return None

            rect = active_ctrl.BoundingRectangle  # (left, top, right, bottom)
            if not rect:
                return None

            l, t, r, b = rect
            if (r - l) <= 0 or (b - t) <= 0:
                return None

            # Skip huge window backgrounds (e.g. desktop pane)
            if (r - l) > 1600 and (b - t) > 1000:
                return None

            center_x = (l + r) / 2.0
            center_y = (t + b) / 2.0

            # Distance from point (x, y) to rectangle boundary
            dx = max(l - x, 0, x - r)
            dy = max(t - y, 0, y - b)
            dist = math.hypot(dx, dy)

            name = active_ctrl.Name.strip() if active_ctrl.Name else ""
            ctrl_type = active_ctrl.ControlTypeName.replace("Control", "")

            return {
                "name": name if name else ctrl_type,
                "type": ctrl_type,
                "rect": (l, t, r, b),
                "center": (center_x, center_y),
                "distance": dist,
            }
        except Exception:
            return None

    def toggle_snap(self) -> bool:
        """Toggles magnetic snapping on/off."""
        self.enable_snap = not self.enable_snap
        return self.enable_snap

    def close(self):
        """Terminates background worker."""
        self._running = False
