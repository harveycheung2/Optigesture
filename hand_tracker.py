import math
import os
import urllib.request
from typing import List, Tuple, Optional, Dict
import cv2
import mediapipe as mp


class HandTracker:
    """
    Wraps MediaPipe Hands to detect 21 3D hand landmarks, finger states (up/down),
    and normalized Euclidean distances between key landmarks.
    Supports MediaPipe 1.0+ Task API as well as legacy mp.solutions API.
    """

    # Landmark indices for convenience
    WRIST = 0
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_TIP = 20

    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),        # Index
        (5, 9), (9, 10), (10, 11), (11, 12),    # Middle
        (9, 13), (13, 14), (14, 15), (15, 16),  # Ring
        (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)  # Pinky
    ]

    def __init__(
        self,
        max_hands: int = 1,
        detection_confidence: float = 0.75,
        tracking_confidence: float = 0.75
    ):
        self.use_legacy = hasattr(mp, "solutions") and hasattr(mp.solutions, "hands")

        if self.use_legacy:
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_hands,
                min_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence,
            )
            self.mp_draw = mp.solutions.drawing_utils
            self.draw_spec_points = self.mp_draw.DrawingSpec(color=(0, 255, 200), thickness=2, circle_radius=3)
            self.draw_spec_lines = self.mp_draw.DrawingSpec(color=(255, 180, 0), thickness=2)
        else:
            # MediaPipe 1.0+ Task Vision API
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
            if not os.path.exists(model_path):
                print(f"Downloading hand_landmarker model to {model_path}...")
                url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
                urllib.request.urlretrieve(url, model_path)

            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=max_hands,
                min_hand_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence,
            )
            self.detector = vision.HandLandmarker.create_from_options(options)
            self.last_timestamp_ms = 0

    def process_frame(self, frame_bgr, timestamp_ms: Optional[int] = None):
        """Processes a BGR image frame and returns MediaPipe results with temporal tracking."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        if self.use_legacy:
            frame_rgb.flags.writeable = False
            results = self.hands.process(frame_rgb)
            frame_rgb.flags.writeable = True
            return results
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            if timestamp_ms is None:
                import time
                timestamp_ms = int(time.time() * 1000)
            if timestamp_ms <= self.last_timestamp_ms:
                timestamp_ms = self.last_timestamp_ms + 1
            self.last_timestamp_ms = timestamp_ms
            return self.detector.detect_for_video(mp_image, timestamp_ms)

    def get_landmarks(self, results, frame_shape: Tuple[int, int, int]) -> Optional[List[Dict[str, float]]]:
        """
        Extracts landmarks for the primary hand.
        Returns a list of dicts with normalized (nx, ny, nz) and pixel (px, py) coordinates.
        """
        if results is None:
            return None

        if self.use_legacy:
            if not getattr(results, "multi_hand_landmarks", None):
                return None
            raw_landmarks = results.multi_hand_landmarks[0].landmark
        else:
            if not getattr(results, "hand_landmarks", None):
                return None
            raw_landmarks = results.hand_landmarks[0]

        h, w, _ = frame_shape
        landmarks = []

        for lm in raw_landmarks:
            landmarks.append({
                "nx": lm.x,
                "ny": lm.y,
                "nz": lm.z,
                "px": int(lm.x * w),
                "py": int(lm.y * h),
            })
        return landmarks

    def _is_finger_extended(self, landmarks: List[Dict[str, float]], tip_idx: int, pip_idx: int, mcp_idx: int) -> bool:
        """
        Rotation-invariant check for finger extension.
        Works upright, tilted, horizontal, and downward.
        """
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]
        wrist = landmarks[self.WRIST]

        dist_tip_wrist = math.hypot(tip["nx"] - wrist["nx"], tip["ny"] - wrist["ny"])
        dist_pip_wrist = math.hypot(pip["nx"] - wrist["nx"], pip["ny"] - wrist["ny"])
        dist_tip_mcp = math.hypot(tip["nx"] - mcp["nx"], tip["ny"] - mcp["ny"])
        dist_pip_mcp = math.hypot(pip["nx"] - mcp["nx"], pip["ny"] - mcp["ny"])

        # Upright condition (classic vertical alignment)
        upright = tip["ny"] < pip["ny"]
        # Rotation-invariant radial distance condition
        radial = (dist_tip_wrist > dist_pip_wrist * 1.10) and (dist_tip_mcp > dist_pip_mcp * 1.15)

        return upright or radial

    def get_palm_scale(self, landmarks: List[Dict[str, float]]) -> float:
        """
        Computes the scale of the palm in normalized coordinate space.
        Uses distance between index MCP (5) and pinky MCP (17), with wrist fallback.
        Ensures distance-invariant gesture thresholds.
        """
        if not landmarks or len(landmarks) < 21:
            return 0.15

        scale = math.hypot(
            landmarks[self.INDEX_MCP]["nx"] - landmarks[self.PINKY_MCP]["nx"],
            landmarks[self.INDEX_MCP]["ny"] - landmarks[self.PINKY_MCP]["ny"]
        )
        if scale > 0.02:
            return scale

        # Fallback to wrist-to-middle-MCP distance
        return max(0.05, math.hypot(
            landmarks[self.WRIST]["nx"] - landmarks[self.MIDDLE_MCP]["nx"],
            landmarks[self.WRIST]["ny"] - landmarks[self.MIDDLE_MCP]["ny"]
        ))

    def get_finger_states(self, landmarks: List[Dict[str, float]]) -> Dict[str, bool]:
        """
        Determines whether each of the 5 fingers is extended ('up') or curled ('down').
        Returns: {'thumb': bool, 'index': bool, 'middle': bool, 'ring': bool, 'pinky': bool}
        """
        if not landmarks or len(landmarks) < 21:
            return {f: False for f in ["thumb", "index", "middle", "ring", "pinky"]}

        fingers = {}

        # Thumb: Compare tip distance from thumb MCP and index MCP
        thumb_tip = landmarks[self.THUMB_TIP]
        thumb_ip = landmarks[self.THUMB_TIP - 1]
        thumb_mcp = landmarks[self.THUMB_TIP - 2]
        dist_tip_mcp = math.hypot(thumb_tip["nx"] - thumb_mcp["nx"], thumb_tip["ny"] - thumb_mcp["ny"])
        dist_ip_mcp = math.hypot(thumb_ip["nx"] - thumb_mcp["nx"], thumb_ip["ny"] - thumb_mcp["ny"])
        fingers["thumb"] = dist_tip_mcp > (dist_ip_mcp * 1.1)

        # 4 Fingers: rotation-invariant extension check
        fingers["index"] = self._is_finger_extended(landmarks, self.INDEX_TIP, self.INDEX_PIP, self.INDEX_MCP)
        fingers["middle"] = self._is_finger_extended(landmarks, self.MIDDLE_TIP, self.MIDDLE_PIP, self.MIDDLE_MCP)
        fingers["ring"] = self._is_finger_extended(landmarks, self.RING_TIP, self.RING_PIP, self.RING_MCP)
        fingers["pinky"] = self._is_finger_extended(landmarks, self.PINKY_TIP, self.PINKY_PIP, self.PINKY_MCP)

        return fingers

    def get_handedness(self, results) -> str:
        """
        Extracts hand classification ('Left' or 'Right').
        Defaults to 'Right' if unclassified.
        """
        if results is None:
            return "Right"
        if self.use_legacy:
            if getattr(results, "multi_handedness", None) and len(results.multi_handedness) > 0:
                return results.multi_handedness[0].classification[0].label
        else:
            if getattr(results, "handedness", None) and len(results.handedness) > 0:
                if len(results.handedness[0]) > 0:
                    return results.handedness[0][0].category_name
        return "Right"

    def is_back_of_hand(
        self,
        landmarks: List[Dict[str, float]],
        handedness: str = "Right",
        deadzone: float = 0.003
    ) -> Tuple[bool, float]:
        """
        Determines whether the back of the hand is facing the camera.
        Uses 2D signed cross product of palm vectors (Wrist->IndexMCP x Wrist->PinkyMCP)
        modulated by handedness.
        Returns: (is_back_of_hand, palm_facing_score)
          palm_facing_score > deadzone  -> Palm facing camera (Active)
          palm_facing_score < -deadzone -> Back of hand facing camera (Paused)
        """
        if not landmarks or len(landmarks) < 21:
            return False, 0.0

        w = landmarks[self.WRIST]
        i_mcp = landmarks[self.INDEX_MCP]
        p_mcp = landmarks[self.PINKY_MCP]

        dx1 = i_mcp["nx"] - w["nx"]
        dy1 = i_mcp["ny"] - w["ny"]
        dx2 = p_mcp["nx"] - w["nx"]
        dy2 = p_mcp["ny"] - w["ny"]

        cross_2d = dx1 * dy2 - dy1 * dx2
        # In mirrored webcam: Left palm has cross > 0, Right palm has cross < 0
        sign = 1.0 if handedness == "Left" else -1.0
        palm_score = cross_2d * sign

        is_back = palm_score < -deadzone
        return is_back, palm_score

    def distance_between(self, lm_a: Dict[str, float], lm_b: Dict[str, float], use_pixel: bool = False) -> float:
        """Calculates Euclidean distance between two landmarks in normalized or pixel space."""
        if use_pixel:
            return math.hypot(lm_a["px"] - lm_b["px"], lm_a["py"] - lm_b["py"])
        return math.hypot(lm_a["nx"] - lm_b["nx"], lm_a["ny"] - lm_b["ny"])

    def draw_skeleton(self, frame_bgr, results):
        """Draws hand connections and points with customized styling."""
        if results is None:
            return

        if self.use_legacy:
            if getattr(results, "multi_hand_landmarks", None):
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(
                        frame_bgr,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        self.draw_spec_points,
                        self.draw_spec_lines
                    )
        else:
            if getattr(results, "hand_landmarks", None):
                h, w = frame_bgr.shape[:2]
                for hand in results.hand_landmarks:
                    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand]
                    for p1, p2 in self.HAND_CONNECTIONS:
                        if p1 < len(pts) and p2 < len(pts):
                            cv2.line(frame_bgr, pts[p1], pts[p2], (255, 180, 0), 2, cv2.LINE_AA)
                    for pt in pts:
                        cv2.circle(frame_bgr, pt, 3, (0, 255, 200), -1, cv2.LINE_AA)
