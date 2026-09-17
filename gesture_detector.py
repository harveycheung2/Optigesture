import time
import math
from enum import Enum
from typing import Dict, List, Optional, Tuple


class GestureMode(Enum):
    IDLE = "IDLE"             # No active control
    MOVING = "MOVING"         # Pointer tracking active (index finger pointing)
    CLICK = "CLICK"           # Quick pinch left-click (zero-drift anchor)
    DRAGGING = "DRAGGING"     # Held pinch click & drag
    SCROLLING = "SCROLLING"   # Fist scroll (knuckles to screen: flick up/down)
    PAUSED = "PAUSED"         # Paused (only unpaused by keyboard button)


class GestureDetector:
    """
    Focused, high-precision gesture detector:
    - Index pointing for fluid cursor tracking
    - Zero-drift pinch left click & hold-to-drag
    - Fist with knuckles facing screen for vertical scrolling (flick up/down)
    - Back-of-hand 5-second continuous hold to pause (unpause exclusively via keyboard button)
    """
    def __init__(
        self,
        pinch_click_threshold: float = 0.045,
        pinch_release_threshold: float = 0.065,
        drag_hold_delay: float = 0.35,
        click_cooldown: float = 0.25,
        back_hold_sec: float = 5.0,
        palm_orientation_deadzone: float = 0.003,
        use_palm_scale: bool = True,
        palm_pinch_click_ratio: float = 0.28,
        palm_pinch_release_ratio: float = 0.40,
        anchor_on_pinch: bool = True,
        fist_scroll_steps: int = 4,
        fist_scroll_flick_threshold: float = 0.011,
        fist_scroll_recoil_window_sec: float = 0.45,
        fist_scroll_cooldown_sec: float = 0.22,
        fist_scroll_deadzone: float = 0.003,
        **kwargs,
    ):
        self.pinch_click_threshold = pinch_click_threshold
        self.pinch_release_threshold = pinch_release_threshold
        self.drag_hold_delay = drag_hold_delay
        self.click_cooldown = click_cooldown
        self.back_hold_sec = back_hold_sec
        self.palm_orientation_deadzone = palm_orientation_deadzone
        self.use_palm_scale = use_palm_scale
        self.palm_pinch_click_ratio = palm_pinch_click_ratio
        self.palm_pinch_release_ratio = palm_pinch_release_ratio
        self.anchor_on_pinch = anchor_on_pinch

        # Fist Scrolling parameters & Recoil State Machine
        self.fist_scroll_steps = fist_scroll_steps
        self.fist_scroll_flick_threshold = fist_scroll_flick_threshold
        self.fist_scroll_recoil_window_sec = fist_scroll_recoil_window_sec
        self.fist_scroll_cooldown_sec = fist_scroll_cooldown_sec
        self.fist_scroll_deadzone = fist_scroll_deadzone

        self.prev_knuckle_y: Optional[float] = None
        self.last_flick_dir: Optional[str] = None
        self.last_flick_time: float = 0.0

        self.current_mode = GestureMode.IDLE
        self.is_pinching = False
        self.pinch_start_time = 0.0
        self.is_dragging = False
        self.anchor_pointer_pos: Optional[Tuple[float, float]] = None

        self.last_left_click_time = 0.0
        self.back_start_time = 0.0
        self.manual_paused = False

    def toggle_pause(self) -> bool:
        """Toggles pause state via keyboard button."""
        self.manual_paused = not self.manual_paused
        if self.manual_paused:
            self.current_mode = GestureMode.PAUSED
        else:
            self.current_mode = GestureMode.IDLE
            self.back_start_time = 0.0
            self.prev_knuckle_y = None
            self.last_flick_dir = None
            self.last_flick_time = 0.0
        return self.manual_paused

    def detect(
        self,
        landmarks: Optional[List[Dict[str, float]]],
        finger_states: Dict[str, bool],
        palm_scale: float = 0.15,
        handedness: str = "Right",
    ) -> Tuple[GestureMode, Dict]:
        """
        Evaluates current hand state and outputs gesture mode and action details.
        Returns: (GestureMode, info_dict)
        """
        now = time.time()

        # Compute adaptive thresholds based on hand scale if enabled
        if self.use_palm_scale and palm_scale > 0.02:
            click_thresh = palm_scale * self.palm_pinch_click_ratio
            release_thresh = palm_scale * self.palm_pinch_release_ratio
        else:
            click_thresh = self.pinch_click_threshold
            release_thresh = self.pinch_release_threshold

        info = {
            "index_thumb_dist": 0.0,
            "is_dragging": self.is_dragging,
            "just_clicked": False,
            "pointer_pos": None,
            "is_anchored": False,
            "palm_scale": palm_scale,
            "effective_threshold": click_thresh,
            "click_pos": None,
            "is_back_of_hand": False,
            "palm_score": 0.0,
            "back_progress": 0.0,
            "back_duration": 0.0,
            "back_remaining": self.back_hold_sec,
            "back_toggled": False,
            "is_fist": False,
            "scroll_delta": 0,
            "scroll_direction": "NONE",
            "fist_delta_y": 0.0,
        }

        if not landmarks or len(landmarks) < 21:
            self._reset_pinch()
            self.back_start_time = 0.0
            self.prev_knuckle_y = None
            self.last_flick_dir = None
            self.last_flick_time = 0.0
            if self.manual_paused:
                return GestureMode.PAUSED, info
            self.current_mode = GestureMode.IDLE
            return GestureMode.IDLE, info

        # If manually paused, stay paused until user presses keyboard button
        if self.manual_paused:
            self._reset_pinch()
            self.prev_knuckle_y = None
            self.last_flick_dir = None
            self.last_flick_time = 0.0
            return GestureMode.PAUSED, info

        # Compute Palm Orientation (signed 2D cross product of wrist->index and wrist->pinky)
        w_lm = landmarks[0]
        i_mcp = landmarks[5]
        p_mcp = landmarks[17]
        dx1 = i_mcp["nx"] - w_lm["nx"]
        dy1 = i_mcp["ny"] - w_lm["ny"]
        dx2 = p_mcp["nx"] - w_lm["nx"]
        dy2 = p_mcp["ny"] - w_lm["ny"]
        cross_2d = dx1 * dy2 - dy1 * dx2
        h_sign = 1.0 if handedness == "Left" else -1.0
        palm_score = cross_2d * h_sign
        info["palm_score"] = palm_score

        # Check for fist (all four non-thumb fingers curled down)
        is_fist = not any(finger_states.get(f, False) for f in ["index", "middle", "ring", "pinky"])

        # -------------------------------------------------------------------
        # 1. FIST SCROLLING (Knuckles to screen: Flick Up = Scroll Up, Flick Down = Scroll Down)
        # -------------------------------------------------------------------
        if is_fist:
            self._reset_pinch()
            self.back_start_time = 0.0  # Reset back-of-hand timer when in fist
            info["is_fist"] = True

            # Track 4-knuckle centroid (MCP landmarks 5, 9, 13, 17) for robust vertical motion
            knuckle_y = (landmarks[5]["ny"] + landmarks[9]["ny"] + landmarks[13]["ny"] + landmarks[17]["ny"]) / 4.0
            knuckle_x = (landmarks[5]["nx"] + landmarks[9]["nx"] + landmarks[13]["nx"] + landmarks[17]["nx"]) / 4.0
            info["pointer_pos"] = (knuckle_x, knuckle_y)

            scroll_delta = 0

            if self.prev_knuckle_y is not None:
                delta_y = knuckle_y - self.prev_knuckle_y
                info["fist_delta_y"] = delta_y
                time_since_flick = now - self.last_flick_time

                # Check for explosive flick impulse
                # ny decreases when moving UP (delta_y < 0) -> scroll UP (positive delta)
                # ny increases when moving DOWN (delta_y > 0) -> scroll DOWN (negative delta)
                if abs(delta_y) >= self.fist_scroll_flick_threshold:
                    flick_candidate = "UP" if delta_y < 0 else "DOWN"

                    # RECOIL SUPPRESSION:
                    # When returning to original neutral position after a flick, the hand naturally moves
                    # in the opposite direction. If an opposite flick occurred recently (< recoil_window),
                    # this return motion is strictly SUPPRESSED so only 1 action triggers!
                    if self.last_flick_dir is not None and time_since_flick < self.fist_scroll_recoil_window_sec:
                        if flick_candidate != self.last_flick_dir:
                            # Suppress return stroke completely!
                            pass
                        else:
                            # Same direction: allow consecutive flick if debounce cooldown has passed
                            if time_since_flick >= self.fist_scroll_cooldown_sec:
                                impulse_mult = max(1.0, abs(delta_y) / self.fist_scroll_flick_threshold)
                                steps = int(round(self.fist_scroll_steps * impulse_mult))
                                scroll_delta = steps if flick_candidate == "UP" else -steps
                                self.last_flick_dir = flick_candidate
                                self.last_flick_time = now
                    else:
                        # Decisive flick from neutral resting position!
                        impulse_mult = max(1.0, abs(delta_y) / self.fist_scroll_flick_threshold)
                        steps = int(round(self.fist_scroll_steps * impulse_mult))
                        scroll_delta = steps if flick_candidate == "UP" else -steps
                        self.last_flick_dir = flick_candidate
                        self.last_flick_time = now
                else:
                    # Gradual motion or resting: check if recoil window has elapsed
                    if time_since_flick >= self.fist_scroll_recoil_window_sec:
                        if abs(delta_y) < self.fist_scroll_deadzone:
                            self.last_flick_dir = None

                # For HUD display: sustain visual direction confirmation
                if scroll_delta != 0:
                    info["scroll_direction"] = "UP" if scroll_delta > 0 else "DOWN"
                elif self.last_flick_dir is not None and (now - self.last_flick_time) < 0.40:
                    info["scroll_direction"] = self.last_flick_dir
                else:
                    info["scroll_direction"] = "NONE"

            self.prev_knuckle_y = knuckle_y
            info["scroll_delta"] = scroll_delta

            self.current_mode = GestureMode.SCROLLING
            return GestureMode.SCROLLING, info

        else:
            # Hand is not a fist: reset fist scroll tracking
            self.prev_knuckle_y = None
            self.last_flick_dir = None
            self.last_flick_time = 0.0

        # -------------------------------------------------------------------
        # 2. BACK-OF-HAND 5-SECOND CONTINUOUS HOLD TO PAUSE
        # -------------------------------------------------------------------
        is_back = (palm_score < -self.palm_orientation_deadzone)

        if is_back:
            self._reset_pinch()
            info["is_back_of_hand"] = True

            if self.back_start_time == 0.0:
                self.back_start_time = now

            back_duration = now - self.back_start_time
            info["back_duration"] = back_duration
            info["back_progress"] = min(1.0, back_duration / self.back_hold_sec)
            info["back_remaining"] = max(0.0, self.back_hold_sec - back_duration)

            if back_duration >= self.back_hold_sec:
                # Continuous 5-second hold completed: latch pause!
                self.manual_paused = True
                info["back_toggled"] = True
                info["back_progress"] = 1.0
                info["back_remaining"] = 0.0
                self.current_mode = GestureMode.PAUSED
                return GestureMode.PAUSED, info
            else:
                # Timer in progress: do NOT pause yet, stay IDLE to prevent cursor jumping
                self.current_mode = GestureMode.IDLE
                return GestureMode.IDLE, info

        else:
            # Not showing back of hand: reset 5s timer
            self.back_start_time = 0.0

        # -------------------------------------------------------------------
        # 3. PINCH CLICK & HOLD-TO-DRAG (Index & Thumb)
        # -------------------------------------------------------------------
        thumb = landmarks[4]
        index = landmarks[8]

        index_thumb_dist = math.hypot(thumb["nx"] - index["nx"], thumb["ny"] - index["ny"])
        info["index_thumb_dist"] = index_thumb_dist

        current_tip_pos = (index["nx"], index["ny"])
        info["pointer_pos"] = current_tip_pos

        if index_thumb_dist < click_thresh:
            if not self.is_pinching:
                self.is_pinching = True
                self.pinch_start_time = now
                self.anchor_pointer_pos = current_tip_pos

            pinch_duration = now - self.pinch_start_time
            if pinch_duration >= self.drag_hold_delay:
                self.is_dragging = True
                self.current_mode = GestureMode.DRAGGING
                info["is_dragging"] = True
                info["is_anchored"] = False
                info["pointer_pos"] = current_tip_pos
                return GestureMode.DRAGGING, info
            else:
                self.current_mode = GestureMode.CLICK
                if self.anchor_on_pinch and self.anchor_pointer_pos:
                    info["pointer_pos"] = self.anchor_pointer_pos
                    info["is_anchored"] = True
                return GestureMode.CLICK, info

        elif index_thumb_dist > release_thresh:
            if self.is_pinching:
                pinch_duration = now - self.pinch_start_time
                if not self.is_dragging and pinch_duration < self.drag_hold_delay:
                    if now - self.last_left_click_time > self.click_cooldown:
                        info["just_clicked"] = True
                        info["click_pos"] = self.anchor_pointer_pos or current_tip_pos
                        self.last_left_click_time = now

                self._reset_pinch()

        # -------------------------------------------------------------------
        # 4. NORMAL POINTER MOVEMENT (Index finger extended)
        # -------------------------------------------------------------------
        if finger_states.get("index", False):
            self.current_mode = GestureMode.MOVING
            return GestureMode.MOVING, info

        self.current_mode = GestureMode.IDLE
        return GestureMode.IDLE, info

    def _reset_pinch(self):
        self.is_pinching = False
        self.is_dragging = False
        self.pinch_start_time = 0.0
        self.anchor_pointer_pos = None

