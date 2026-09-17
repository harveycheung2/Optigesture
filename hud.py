import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from gesture_detector import GestureMode


class HUDOverlay:
    """
    Renders a modern, aesthetic sci-fi HUD on top of the webcam feed.
    Features:
    - Active cursor interaction zone with stylized corner reticles
    - Real-time gesture state badge with color-coded alerts
    - Dynamic pinch distance gauge with threshold mark
    - Crosshair on tracked index fingertip
    - Live FPS and shortcut helper bar
    """

    # Color Palette (BGR)
    COLOR_BG_DARK    = (20, 20, 25)
    COLOR_BORDER     = (60, 60, 75)
    COLOR_ACCENT_CYAN= (255, 230, 0)      # Cyan
    COLOR_GREEN      = (60, 220, 80)      # Emerald
    COLOR_MAGENTA    = (220, 50, 240)     # Magenta / Purple
    COLOR_ORANGE     = (30, 140, 255)     # Warm Orange
    COLOR_RED        = (60, 60, 240)      # Crimson Red
    COLOR_GRAY       = (160, 160, 170)
    COLOR_WHITE      = (245, 245, 250)

    MODE_COLORS = {
        GestureMode.IDLE: COLOR_GRAY,
        GestureMode.MOVING: COLOR_ACCENT_CYAN,
        GestureMode.CLICK: COLOR_GREEN,
        GestureMode.DRAGGING: COLOR_MAGENTA,
        GestureMode.SCROLLING: (0, 210, 255),
        GestureMode.PAUSED: COLOR_RED,
    }

    def __init__(self, frame_width: int, frame_height: int, margin_x: float, margin_y: float):
        self.w = frame_width
        self.h = frame_height
        self.margin_x = margin_x
        self.margin_y = margin_y
        self._update_bounds()
        self.show_details = True
        self.ripples: List[Dict] = []  # Active click animation ripples

    def set_margins(self, margin_x: float, margin_y: float):
        """Updates interaction box margins dynamically."""
        self.margin_x = max(0.05, min(0.40, margin_x))
        self.margin_y = max(0.05, min(0.40, margin_y))
        self._update_bounds()

    def _update_bounds(self):
        self.box_x1 = int(self.w * self.margin_x)
        self.box_y1 = int(self.h * self.margin_y)
        self.box_x2 = int(self.w * (1.0 - self.margin_x))
        self.box_y2 = int(self.h * (1.0 - self.margin_y))

    def trigger_click_ripple(self, x: int, y: int, color=(60, 220, 80)):
        """Triggers a ripple effect at specific pixel coordinate."""
        self.ripples.append({
            "x": x,
            "y": y,
            "radius": 6.0,
            "max_radius": 34.0,
            "color": color,
            "alpha": 1.0,
        })

    def toggle_details(self):
        self.show_details = not self.show_details

    def draw_rounded_rect(self, img, pt1, pt2, color, thickness=1, radius=8):
        """Draws a rectangle with rounded corners."""
        x1, y1 = pt1
        x2, y2 = pt2
        r = min(radius, abs(x2 - x1) // 2, abs(y2 - y1) // 2)

        # Straight segments
        cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness)
        cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness)
        cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness)
        cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness)

        # Arcs
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)

    def draw_corner_brackets(self, img, pt1, pt2, color, length=20, thickness=2):
        """Draws tech/sci-fi corner brackets around a bounding box."""
        x1, y1 = pt1
        x2, y2 = pt2
        # Top-left
        cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness)
        cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness)
        # Top-right
        cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness)
        # Bottom-left
        cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness)
        # Bottom-right
        cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness)

    def _render_screen_radar(
        self,
        frame,
        screen_coords: Tuple[int, int],
        screen_res: Tuple[int, int],
        focused_target: Optional[Dict] = None
    ):
        """Renders a real-time monitor radar preview showing cursor position and focused UI buttons."""
        sw, sh = screen_res
        cx, cy = screen_coords
        radar_w = 118
        radar_h = int(radar_w * (sh / max(1, sw)))
        rx1 = self.w - radar_w - 18
        ry1 = self.h - 58 - radar_h
        rx2 = rx1 + radar_w
        ry2 = ry1 + radar_h

        # Radar backdrop
        radar_bg = frame[ry1-4:ry2+4, rx1-4:rx2+4].copy()
        cv2.rectangle(frame, (rx1-4, ry1-18), (rx2+4, ry2+4), self.COLOR_BG_DARK, -1)
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (80, 80, 95), 1)

        # Title
        cv2.putText(frame, "SCREEN RADAR", (rx1, ry1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.32, self.COLOR_GRAY, 1, cv2.LINE_AA)

        # Draw focused UI element rectangle on radar if detected
        if focused_target and focused_target.get("rect"):
            tl, tt, tr, tb = focused_target["rect"]
            brx1 = int(rx1 + (tl / max(1, sw)) * radar_w)
            bry1 = int(ry1 + (tt / max(1, sh)) * radar_h)
            brx2 = int(rx1 + (tr / max(1, sw)) * radar_w)
            bry2 = int(ry1 + (tb / max(1, sh)) * radar_h)
            # Ensure minimum visible size on radar
            if brx2 - brx1 < 4: brx2 = brx1 + 4
            if bry2 - bry1 < 3: bry2 = bry1 + 3
            # Glowing focus box on minimap
            cv2.rectangle(frame, (brx1, bry1), (brx2, bry2), (0, 200, 255), 1)

        # Map screen coordinates to radar box
        cur_rx = int(rx1 + (cx / max(1, sw)) * radar_w)
        cur_ry = int(ry1 + (cy / max(1, sh)) * radar_h)
        cur_rx = max(rx1, min(rx2, cur_rx))
        cur_ry = max(ry1, min(ry2, cur_ry))

        # Crosshair lines inside radar
        cv2.line(frame, (cur_rx, ry1), (cur_rx, ry2), (40, 100, 150), 1)
        cv2.line(frame, (rx1, cur_ry), (rx2, cur_ry), (40, 100, 150), 1)
        # Radar cursor dot
        cv2.circle(frame, (cur_rx, cur_ry), 3, self.COLOR_ACCENT_CYAN, -1, cv2.LINE_AA)

    def render(
        self,
        frame,
        fps: float,
        mode: GestureMode,
        info: Dict,
        landmarks: Optional[List[Dict[str, float]]] = None,
        click_threshold: float = 0.045,
        screen_coords: Optional[Tuple[int, int]] = None,
        screen_res: Optional[Tuple[int, int]] = None,
        focused_target: Optional[Dict] = None,
    ):
        """Main HUD render pass."""
        h, w = frame.shape[:2]

        # 1. Interaction Zone Box (Subtle boundary with corner accents)
        box_color = self.COLOR_BORDER
        if mode in [GestureMode.MOVING, GestureMode.DRAGGING]:
            box_color = (120, 100, 40)
        elif mode == GestureMode.CLICK:
            box_color = (40, 160, 80)

        # Thin inner frame
        cv2.rectangle(frame, (self.box_x1, self.box_y1), (self.box_x2, self.box_y2), box_color, 1)
        self.draw_corner_brackets(frame, (self.box_x1, self.box_y1), (self.box_x2, self.box_y2), self.COLOR_ACCENT_CYAN, length=18, thickness=2)

        # Zone Label
        zone_info = f"ACTIVE ZONE [Margin: {int(self.margin_x*100)}%]"
        cv2.putText(frame, zone_info, (self.box_x1 + 8, self.box_y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, self.COLOR_GRAY, 1, cv2.LINE_AA)

        # 2. Tracked Pointer Reticle on Index Fingertip
        if landmarks and len(landmarks) > 8:
            idx = landmarks[8]
            px, py = idx["px"], idx["py"]
            mode_col = self.MODE_COLORS.get(mode, self.COLOR_ACCENT_CYAN)

            # Check if pointer is anchored (anti-drift locked)
            is_anchored = info.get("is_anchored", False)

            if is_anchored:
                # Distinct locked reticle
                cv2.circle(frame, (px, py), 15, self.COLOR_GREEN, 2, cv2.LINE_AA)
                cv2.circle(frame, (px, py), 4, self.COLOR_WHITE, -1, cv2.LINE_AA)
                # Corner bracket lock
                cv2.rectangle(frame, (px - 8, py - 8), (px + 8, py + 8), self.COLOR_GREEN, 1)
                cv2.putText(frame, "LOCKED", (px + 16, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.36, self.COLOR_GREEN, 1, cv2.LINE_AA)
            else:
                # Outer ring and center crosshair
                cv2.circle(frame, (px, py), 12, mode_col, 2, cv2.LINE_AA)
                cv2.circle(frame, (px, py), 3, self.COLOR_WHITE, -1, cv2.LINE_AA)
                cv2.line(frame, (px - 16, py), (px + 16, py), mode_col, 1)
                cv2.line(frame, (px, py - 16), (px, py + 16), mode_col, 1)

            # Line between thumb and index when approaching pinch
            thumb = landmarks[4]
            dist = info.get("index_thumb_dist", 1.0)
            eff_thresh = info.get("effective_threshold", click_threshold)
            if dist < (eff_thresh * 2.2):
                line_col = self.COLOR_GREEN if dist < eff_thresh else self.COLOR_ACCENT_CYAN
                cv2.line(frame, (thumb["px"], thumb["py"]), (idx["px"], idx["py"]), line_col, 2, cv2.LINE_AA)

        # 3. Render and advance active click ripples
        remaining_ripples = []
        for rip in self.ripples:
            cv2.circle(frame, (int(rip["x"]), int(rip["y"])), int(rip["radius"]), rip["color"], 2, cv2.LINE_AA)
            rip["radius"] += 4.5
            if rip["radius"] < rip["max_radius"]:
                remaining_ripples.append(rip)
        self.ripples = remaining_ripples

        if not self.show_details:
            return

        # 4. Top Banner: Mode Badge & FPS
        # Glassmorphism dark background strip
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (w - 10, 56), self.COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        # Active Mode Badge
        mode_str = mode.value
        mode_col = self.MODE_COLORS.get(mode, self.COLOR_GRAY)
        badge_w = 140
        badge_rect_p1 = (20, 18)
        badge_rect_p2 = (20 + badge_w, 48)
        self.draw_rounded_rect(frame, badge_rect_p1, badge_rect_p2, mode_col, thickness=2, radius=6)

        # Pulsing circle dot in badge
        cv2.circle(frame, (35, 33), 5, mode_col, -1, cv2.LINE_AA)
        cv2.putText(frame, mode_str, (48, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_WHITE, 1, cv2.LINE_AA)

        # FPS indicator
        fps_text = f"FPS: {int(round(fps))}"
        cv2.putText(frame, fps_text, (w - 110, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.52, self.COLOR_ACCENT_CYAN, 1, cv2.LINE_AA)

        # Title in banner center
        cv2.putText(frame, "AIR GESTURE MOUSE", (w // 2 - 80, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 210), 1, cv2.LINE_AA)

        # Tab Focus Banner if an interactive button/tab is targeted
        if focused_target:
            t_name = focused_target.get("name", "Button")[:16]
            t_type = focused_target.get("type", "Control")
            focus_text = f"TAB FOCUS: {t_name} ({t_type})"

            # Render neatly above Screen Radar in bottom right
            radar_h = int(118 * (screen_res[1] / max(1, screen_res[0]))) if screen_res else 66
            ry1 = h - 58 - radar_h
            pill_w = 205
            pill_h = 22
            pill_x1 = max(10, w - pill_w - 18)
            pill_y1 = max(60, ry1 - 36)
            pill_x2 = pill_x1 + pill_w
            pill_y2 = pill_y1 + pill_h

            cv2.rectangle(frame, (pill_x1, pill_y1), (pill_x2, pill_y2), self.COLOR_BG_DARK, -1)
            self.draw_rounded_rect(frame, (pill_x1, pill_y1), (pill_x2, pill_y2), (0, 230, 255), thickness=1, radius=4)
            cv2.circle(frame, (pill_x1 + 10, pill_y1 + 11), 3, (0, 255, 200), -1, cv2.LINE_AA)
            cv2.putText(frame, focus_text, (pill_x1 + 18, pill_y1 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (240, 250, 255), 1, cv2.LINE_AA)

        # 5. Screen Radar Minimap
        if screen_coords and screen_res:
            self._render_screen_radar(frame, screen_coords, screen_res, focused_target)

        # 6. Bottom Info Bar: Gesture Meter & Shortcuts
        bar_overlay = frame.copy()
        cv2.rectangle(bar_overlay, (10, h - 54), (w - 10, h - 10), self.COLOR_BG_DARK, -1)
        cv2.addWeighted(bar_overlay, 0.70, frame, 0.30, 0, frame)

        # 1. Fist Scrolling Active Indicator Card
        if mode == GestureMode.SCROLLING:
            card_w, card_h = 360, 58
            cx1 = (w - card_w) // 2
            cy1 = 68
            cx2 = cx1 + card_w
            cy2 = cy1 + card_h

            scroll_overlay = frame.copy()
            cv2.rectangle(scroll_overlay, (cx1, cy1), (cx2, cy2), self.COLOR_BG_DARK, -1)
            cv2.addWeighted(scroll_overlay, 0.85, frame, 0.15, 0, frame)

            scroll_col = (0, 210, 255)  # Gold
            self.draw_rounded_rect(frame, (cx1, cy1), (cx2, cy2), scroll_col, thickness=2, radius=8)

            direction = info.get("scroll_direction", "NONE")
            scroll_delta = info.get("scroll_delta", 0)

            # Circular indicator badge
            cv2.circle(frame, (cx1 + 28, cy1 + 29), 15, scroll_col, 1, cv2.LINE_AA)
            if direction == "UP":
                # Up arrow icon
                cv2.line(frame, (cx1 + 28, cy1 + 20), (cx1 + 21, cy1 + 27), scroll_col, 2, cv2.LINE_AA)
                cv2.line(frame, (cx1 + 28, cy1 + 20), (cx1 + 35, cy1 + 27), scroll_col, 2, cv2.LINE_AA)
                cv2.line(frame, (cx1 + 28, cy1 + 20), (cx1 + 28, cy1 + 38), scroll_col, 2, cv2.LINE_AA)
                status_str = f"SCROLL UP  (+{abs(scroll_delta)} steps)" if scroll_delta != 0 else "FIST FLICK UP"
            elif direction == "DOWN":
                # Down arrow icon
                cv2.line(frame, (cx1 + 28, cy1 + 38), (cx1 + 21, cy1 + 31), scroll_col, 2, cv2.LINE_AA)
                cv2.line(frame, (cx1 + 28, cy1 + 38), (cx1 + 35, cy1 + 31), scroll_col, 2, cv2.LINE_AA)
                cv2.line(frame, (cx1 + 28, cy1 + 20), (cx1 + 28, cy1 + 38), scroll_col, 2, cv2.LINE_AA)
                status_str = f"SCROLL DOWN  (-{abs(scroll_delta)} steps)" if scroll_delta != 0 else "FIST FLICK DOWN"
            else:
                cv2.circle(frame, (cx1 + 28, cy1 + 29), 5, scroll_col, -1, cv2.LINE_AA)
                status_str = "FIST SCROLL ACTIVE"

            cv2.putText(frame, status_str, (cx1 + 54, cy1 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.44, scroll_col, 1, cv2.LINE_AA)
            cv2.putText(frame, "^ Flick Up = Scroll Up  |  v Flick Down = Scroll Down", (cx1 + 54, cy1 + 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLOR_WHITE, 1, cv2.LINE_AA)

        # 2. Back-of-Hand 5-Second Hold Countdown Card
        elif info.get("is_back_of_hand") and mode != GestureMode.PAUSED:
            progress = info.get("back_progress", 0.0)
            remaining = info.get("back_remaining", 5.0)
            card_w, card_h = 370, 60
            cx1 = (w - card_w) // 2
            cy1 = 68
            cx2 = cx1 + card_w
            cy2 = cy1 + card_h

            back_overlay = frame.copy()
            cv2.rectangle(back_overlay, (cx1, cy1), (cx2, cy2), self.COLOR_BG_DARK, -1)
            cv2.addWeighted(back_overlay, 0.85, frame, 0.15, 0, frame)

            # Transition from Amber to Crimson as 5s completes
            bar_col = self.COLOR_ORANGE if progress < 0.65 else self.COLOR_RED
            self.draw_rounded_rect(frame, (cx1, cy1), (cx2, cy2), bar_col, thickness=2, radius=8)

            # Circular indicator
            cv2.circle(frame, (cx1 + 28, cy1 + 30), 14, bar_col, 2, cv2.LINE_AA)
            cv2.circle(frame, (cx1 + 28, cy1 + 30), 5, bar_col, -1, cv2.LINE_AA)

            # Charging progress bar
            pb_x1 = cx1 + 54
            pb_y1 = cy1 + 36
            pb_w = card_w - 74
            pb_h = 8
            cv2.rectangle(frame, (pb_x1, pb_y1), (pb_x1 + pb_w, pb_y1 + pb_h), (50, 50, 65), -1)
            fill_w = int(pb_w * progress)
            if fill_w > 0:
                cv2.rectangle(frame, (pb_x1, pb_y1), (pb_x1 + fill_w, pb_y1 + pb_h), bar_col, -1)

            cv2.putText(frame, f"HOLDING BACK OF HAND: {remaining:.1f}s TO PAUSE", (cx1 + 54, cy1 + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, bar_col, 1, cv2.LINE_AA)

        # 3. Persistent Paused Card
        elif mode == GestureMode.PAUSED:
            p_w, p_h = 410, 38
            px1 = (w - p_w) // 2
            py1 = 68
            px2 = px1 + p_w
            py2 = py1 + p_h
            p_overlay = frame.copy()
            cv2.rectangle(p_overlay, (px1, py1), (px2, py2), self.COLOR_BG_DARK, -1)
            cv2.addWeighted(p_overlay, 0.85, frame, 0.15, 0, frame)
            self.draw_rounded_rect(frame, (px1, py1), (px2, py2), self.COLOR_RED, thickness=2, radius=6)
            cv2.circle(frame, (px1 + 20, py1 + 19), 6, self.COLOR_RED, -1, cv2.LINE_AA)
            cv2.putText(frame, "PAUSED - Press [P] or [Space] on keyboard to Resume", (px1 + 34, py1 + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.37, self.COLOR_WHITE, 1, cv2.LINE_AA)

        # Dynamic Pinch Distance Meter
        pinch_dist = info.get("index_thumb_dist", 0.0)
        eff_thresh = info.get("effective_threshold", click_threshold)
        meter_x1 = 25
        meter_y1 = h - 35
        meter_w = 120
        meter_h = 10

        cv2.rectangle(frame, (meter_x1, meter_y1), (meter_x1 + meter_w, meter_y1 + meter_h), self.COLOR_BORDER, 1)
        # Fill proportion (inverted: 0 dist = full fill)
        max_meter_range = max(0.10, eff_thresh * 2.5)
        fill_ratio = max(0.0, min(1.0, 1.0 - (pinch_dist / max_meter_range)))
        fill_w = int(meter_w * fill_ratio)
        meter_col = self.COLOR_GREEN if pinch_dist < eff_thresh else self.COLOR_ACCENT_CYAN
        if fill_w > 0:
            cv2.rectangle(frame, (meter_x1 + 1, meter_y1 + 1), (meter_x1 + fill_w, meter_y1 + meter_h - 1), meter_col, -1)

        # Draw threshold marker on meter
        thresh_ratio = max(0.0, min(1.0, 1.0 - (eff_thresh / max_meter_range)))
        thresh_px = int(meter_x1 + thresh_ratio * meter_w)
        cv2.line(frame, (thresh_px, meter_y1 - 2), (thresh_px, meter_y1 + meter_h + 2), (0, 255, 255), 2)

        meter_label = f"PINCH [{'AUTO' if info.get('palm_scale') else 'FIXED'}]"
        cv2.putText(frame, meter_label, (meter_x1, meter_y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.34, self.COLOR_GRAY, 1, cv2.LINE_AA)

        # Shortcut Helper Text
        helper_text = "[P/Space] Resume | [Fist Flick] Scroll Up/Dn | [Hold Back 5s] Pause | [K] Calibrate | [Q] Quit"
        cv2.putText(frame, helper_text, (w - 490, h - 26), cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.COLOR_GRAY, 1, cv2.LINE_AA)
