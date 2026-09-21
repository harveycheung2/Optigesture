import time
import math
from enum import Enum
from typing import Dict, List, Optional, Tuple


class GestureMode(Enum):
    IDLE = "IDLE"             # No active control
    MOVING = "MOVING"         # Pointer tracking active (index finger pointing)
    CLICK = "CLICK"           # Quick pinch left-click (zero-drift anchor)
    DRAGGING = "DRAGGING"     # Held pinch click & drag
    PAUSED = "PAUSED"         # Paused (only unpaused by keyboard button)


class GestureDetector:
    """
    Focused, high-precision gesture detector:
    - Index pointing for fluid cursor tracking
    - Zero-drift pinch left click & hold-to-drag
    - Back-of-hand 5-second continuous hold to pause (unpause exclusively via keyboard button)
    - V-sign (peace sign) 1.5-second continuous hold to toggle head nod scroll
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
        v_sign_hold_sec: float = 1.5,
        open_palm_hold_sec: Optional[float] = None,
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

        # V-Sign Hold to Toggle Head Scroll parameters
        self.v_sign_hold_sec = v_sign_hold_sec if open_palm_hold_sec is None else open_palm_hold_sec
        self.open_palm_hold_sec = self.v_sign_hold_sec  # Alias for backward compatibility
        self.v_sign_start_time = 0.0
        self.open_palm_start_time = 0.0
        self.v_sign_latched = False
        self.open_palm_latched = False

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
            self.v_sign_start_time = 0.0
            self.v_sign_latched = False
            self.open_palm_start_time = 0.0
            self.open_palm_latched = False
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
            "is_v_sign": False,
            "v_sign_progress": 0.0,
            "v_sign_duration": 0.0,
            "v_sign_remaining": self.v_sign_hold_sec,
            "v_sign_toggled": False,
            "is_open_palm": False,
            "open_palm_progress": 0.0,
            "open_palm_duration": 0.0,
            "open_palm_remaining": self.v_sign_hold_sec,
            "open_palm_toggled": False,
        }

        if not landmarks or len(landmarks) < 21:
            self._reset_pinch()
            self.back_start_time = 0.0
            self.v_sign_start_time = 0.0
            self.v_sign_latched = False
            self.open_palm_start_time = 0.0
            self.open_palm_latched = False
            if self.manual_paused:
                return GestureMode.PAUSED, info
            self.current_mode = GestureMode.IDLE
            return GestureMode.IDLE, info

        # If manually paused, stay paused until user presses keyboard button
        if self.manual_paused:
            self._reset_pinch()
            self.v_sign_start_time = 0.0
            self.v_sign_latched = False
            self.open_palm_start_time = 0.0
            self.open_palm_latched = False
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

        # -------------------------------------------------------------------
        # 1. BACK-OF-HAND 5-SECOND CONTINUOUS HOLD TO PAUSE
        # -------------------------------------------------------------------
        is_back = (palm_score < -self.palm_orientation_deadzone)

        if is_back:
            self._reset_pinch()
            self.v_sign_start_time = 0.0
            self.v_sign_latched = False
            self.open_palm_start_time = 0.0
            self.open_palm_latched = False
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
        # 2. V-SIGN 1.5-SECOND CONTINUOUS HOLD TO TOGGLE HEAD SCROLL
        # -------------------------------------------------------------------
        # V-sign / Peace sign: Index & Middle extended, Ring & Pinky curled down, palm facing forward
        index_extended = finger_states.get("index", False)
        middle_extended = finger_states.get("middle", False)
        ring_curled = not finger_states.get("ring", False)
        pinky_curled = not finger_states.get("pinky", False)
        facing_forward = (palm_score > self.palm_orientation_deadzone)
        is_v_sign = facing_forward and index_extended and middle_extended and ring_curled and pinky_curled

        if is_v_sign:
            self._reset_pinch()
            info["is_v_sign"] = True
            info["is_open_palm"] = True

            if not self.v_sign_latched:
                if self.v_sign_start_time == 0.0:
                    self.v_sign_start_time = now
                    self.open_palm_start_time = now

                v_duration = now - self.v_sign_start_time
                info["v_sign_duration"] = v_duration
                info["v_sign_progress"] = min(1.0, v_duration / self.v_sign_hold_sec)
                info["v_sign_remaining"] = max(0.0, self.v_sign_hold_sec - v_duration)
                info["open_palm_duration"] = v_duration
                info["open_palm_progress"] = info["v_sign_progress"]
                info["open_palm_remaining"] = info["v_sign_remaining"]

                if v_duration >= self.v_sign_hold_sec:
                    self.v_sign_latched = True
                    self.open_palm_latched = True
                    info["v_sign_toggled"] = True
                    info["open_palm_toggled"] = True
                    info["v_sign_progress"] = 1.0
                    info["v_sign_remaining"] = 0.0
                    info["open_palm_progress"] = 1.0
                    info["open_palm_remaining"] = 0.0
            else:
                info["v_sign_progress"] = 1.0
                info["v_sign_remaining"] = 0.0
                info["open_palm_progress"] = 1.0
                info["open_palm_remaining"] = 0.0

            # While holding V-sign, freeze cursor to avoid jumping
            self.current_mode = GestureMode.IDLE
            return GestureMode.IDLE, info

        else:
            # Not showing V-sign: reset 1.5s timer and unlatch
            self.v_sign_start_time = 0.0
            self.v_sign_latched = False
            self.open_palm_start_time = 0.0
            self.open_palm_latched = False

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

