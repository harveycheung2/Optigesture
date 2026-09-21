import math
import os
import time
import urllib.request
from enum import Enum
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
import mediapipe as mp
from filters import OneEuroFilter


class NodState(Enum):
    NEUTRAL = "NEUTRAL"
    NOD_DOWN_ARMED = "NOD_DOWN_ARMED"
    NOD_UP_ARMED = "NOD_UP_ARMED"
    RECOIL_SUPPRESSION = "RECOIL_SUPPRESSION"


class HeadTracker:
    """
    Tracks head pose and pitch angle using MediaPipe FaceLandmarker.
    Implements a robust nod gesture state machine:
    - Tilt head down & return to neutral -> triggers SCROLL DOWN.
    - Tilt head up & return to neutral -> triggers SCROLL UP.
    - Opposite-direction recoil window suppresses rebound overshoots.
    """

    FOREHEAD_LM = 10
    NOSE_TIP_LM = 1
    CHIN_LM = 152
    LEFT_EYE_LM = 33
    RIGHT_EYE_LM = 263

    def __init__(
        self,
        model_path: Optional[str] = None,
        pitch_threshold: float = 8.5,
        return_deadzone: float = 3.5,
        recoil_window_sec: float = 0.60,
        cooldown_sec: float = 0.35,
        scroll_steps: int = 4,
    ):
        self.pitch_threshold = pitch_threshold
        self.return_deadzone = return_deadzone
        self.recoil_window_sec = recoil_window_sec
        self.cooldown_sec = cooldown_sec
        self.scroll_steps = scroll_steps

        # Pitch tracking and calibration
        self.neutral_pitch = 0.0
        self.is_calibrated = False
        self.current_pitch = 0.0
        self.relative_pitch = 0.0

        # One-Euro filter to remove landmark sensor noise on pitch (responsive to quick nods)
        self.pitch_filter = OneEuroFilter(min_cutoff=1.5, beta=0.5, d_cutoff=1.0)

        # State machine
        self.state = NodState.NEUTRAL
        self.arm_time = 0.0
        self.recoil_suppress_dir: Optional[str] = None
        self.recoil_end_time = 0.0
        self.cooldown_end_time = 0.0

        # Initialize MediaPipe Task FaceLandmarker
        if model_path is None:
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_landmarker.task")

        if not os.path.exists(model_path):
            print(f"[HeadTracker] Model not found at {model_path}, downloading...")
            url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            urllib.request.urlretrieve(url, model_path)
            print("[HeadTracker] Model downloaded successfully.")

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)
        self.last_timestamp_ms = 0
        self.latest_face_landmarks = None

    def reset_state(self):
        """Resets gesture state machine to neutral."""
        self.state = NodState.NEUTRAL
        self.arm_time = 0.0
        self.recoil_suppress_dir = None
        self.recoil_end_time = 0.0
        self.cooldown_end_time = 0.0

    def calibrate_neutral(self):
        """Calibrates neutral pitch to the current head pitch."""
        self.neutral_pitch = self.current_pitch
        self.is_calibrated = True
        self.reset_state()
        print(f"[HeadTracker] Calibrated neutral pitch to: {self.neutral_pitch:.1f} deg")

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: Optional[int] = None):
        """Processes video frame and extracts face landmarks and transformation matrix."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        if timestamp_ms <= self.last_timestamp_ms:
            timestamp_ms = self.last_timestamp_ms + 1
        self.last_timestamp_ms = timestamp_ms

        result = self.detector.detect_for_video(mp_image, timestamp_ms)
        self.latest_face_landmarks = None
        matrix = None

        if result and result.face_landmarks and len(result.face_landmarks) > 0:
            self.latest_face_landmarks = result.face_landmarks[0]
            if result.facial_transformation_matrixes and len(result.facial_transformation_matrixes) > 0:
                matrix = np.array(result.facial_transformation_matrixes[0])

        return self.latest_face_landmarks, matrix

    def compute_pitch(self, face_landmarks, matrix: Optional[np.ndarray], curr_time: float) -> float:
        """
        Computes head pitch in degrees (positive = tilted up, negative = tilted down).
        Uses facial transformation matrix if available, falling back to 3D facial landmarks.
        """
        pitch_deg = 0.0

        if matrix is not None and matrix.size >= 16:
            mat = matrix.reshape((4, 4))
            # Rotation matrix R: pitch is rotation around X-axis
            r21 = mat[2, 1]
            r22 = mat[2, 2]
            pitch_deg = -math.degrees(math.atan2(r21, r22))
        elif face_landmarks and len(face_landmarks) > 152:
            forehead = face_landmarks[self.FOREHEAD_LM]
            chin = face_landmarks[self.CHIN_LM]
            dy = chin.y - forehead.y
            dz = chin.z - forehead.z
            pitch_deg = math.degrees(math.atan2(dz, dy))

        # Smooth pitch with 1€ filter
        filtered_pitch = self.pitch_filter.filter(pitch_deg, timestamp=curr_time)
        self.current_pitch = filtered_pitch

        # Auto-calibrate neutral baseline on first acquisition
        if not self.is_calibrated:
            self.neutral_pitch = filtered_pitch
            self.is_calibrated = True

        # Slowly adapt neutral baseline when head is resting still
        rel = filtered_pitch - self.neutral_pitch
        if abs(rel) < self.return_deadzone:
            self.neutral_pitch = (0.98 * self.neutral_pitch) + (0.02 * filtered_pitch)

        self.relative_pitch = filtered_pitch - self.neutral_pitch
        return self.relative_pitch

    def update(
        self,
        face_landmarks,
        matrix: Optional[np.ndarray],
        curr_time: Optional[float] = None,
    ) -> Dict:
        """
        Updates head tracking and gesture state machine.
        Returns dictionary with scroll_delta, scroll_direction, relative_pitch, and state.
        """
        if curr_time is None:
            curr_time = time.time()

        result = {
            "has_face": False,
            "relative_pitch": 0.0,
            "current_pitch": 0.0,
            "scroll_delta": 0,
            "scroll_direction": "NONE",
            "state": self.state.value,
            "is_nod_down_armed": (self.state == NodState.NOD_DOWN_ARMED),
            "is_nod_up_armed": (self.state == NodState.NOD_UP_ARMED),
        }

        if face_landmarks is None:
            self.reset_state()
            return result

        result["has_face"] = True
        rel_pitch = self.compute_pitch(face_landmarks, matrix, curr_time)
        result["relative_pitch"] = rel_pitch
        result["current_pitch"] = self.current_pitch

        # -------------------------------------------------------------------
        # NOD GESTURE STATE MACHINE WITH RECOIL SUPPRESSION
        # -------------------------------------------------------------------

        # Check if currently in recoil suppression window
        if self.state == NodState.RECOIL_SUPPRESSION:
            if curr_time < self.recoil_end_time:
                # Still within recoil suppression window: strictly ignore recoil movement
                result["state"] = self.state.value
                return result
            else:
                # Recoil window has elapsed: return to neutral once head settles
                if abs(rel_pitch) < self.return_deadzone * 1.3:
                    self.state = NodState.NEUTRAL
                    self.recoil_suppress_dir = None
                result["state"] = self.state.value
                return result

        # Check if in cooldown between same-direction gestures
        if curr_time < self.cooldown_end_time:
            result["state"] = self.state.value
            return result

        # 1. Neutral State: evaluate nod initiation
        if self.state == NodState.NEUTRAL:
            if rel_pitch <= -self.pitch_threshold:
                # Tilted DOWN past threshold: arm nod down
                self.state = NodState.NOD_DOWN_ARMED
                self.arm_time = curr_time
            elif rel_pitch >= self.pitch_threshold:
                # Tilted UP past threshold: arm nod up
                self.state = NodState.NOD_UP_ARMED
                self.arm_time = curr_time

        # 2. Nod Down Armed: head tilted down, waiting for return stroke
        elif self.state == NodState.NOD_DOWN_ARMED:
            # Check for timeout (gesture abandoned if held down > 1.8s)
            if curr_time - self.arm_time > 1.8:
                self.reset_state()
            elif rel_pitch >= -self.return_deadzone:
                # RETURN TO NEUTRAL ACHIEVED -> Trigger SCROLL DOWN!
                result["scroll_delta"] = -self.scroll_steps
                result["scroll_direction"] = "DOWN"

                # Enter recoil suppression: suppress upward rebound from triggering scroll up
                self.state = NodState.RECOIL_SUPPRESSION
                self.recoil_suppress_dir = "UP"
                self.recoil_end_time = curr_time + self.recoil_window_sec
                self.cooldown_end_time = curr_time + self.cooldown_sec

        # 3. Nod Up Armed: head tilted up, waiting for return stroke
        elif self.state == NodState.NOD_UP_ARMED:
            # Check for timeout (gesture abandoned if held up > 1.8s)
            if curr_time - self.arm_time > 1.8:
                self.reset_state()
            elif rel_pitch <= self.return_deadzone:
                # RETURN TO NEUTRAL ACHIEVED -> Trigger SCROLL UP!
                result["scroll_delta"] = self.scroll_steps
                result["scroll_direction"] = "UP"

                # Enter recoil suppression: suppress downward rebound from triggering scroll down
                self.state = NodState.RECOIL_SUPPRESSION
                self.recoil_suppress_dir = "DOWN"
                self.recoil_end_time = curr_time + self.recoil_window_sec
                self.cooldown_end_time = curr_time + self.cooldown_sec

        result["state"] = self.state.value
        result["is_nod_down_armed"] = (self.state == NodState.NOD_DOWN_ARMED)
        result["is_nod_up_armed"] = (self.state == NodState.NOD_UP_ARMED)
        return result

    def draw_head_pose(self, frame: np.ndarray, face_landmarks, info: Dict):
        """Renders subtle head orientation reticle and pitch meter on camera feed."""
        if face_landmarks is None or len(face_landmarks) < 153:
            return

        h, w, _ = frame.shape
        nose = face_landmarks[self.NOSE_TIP_LM]
        nx, ny = int(nose.x * w), int(nose.y * h)

        rel_pitch = info.get("relative_pitch", 0.0)
        state_str = info.get("state", "NEUTRAL")

        # Visual reticle around nose center
        color = (0, 230, 255)  # Cyan default
        if state_str == NodState.NOD_DOWN_ARMED.value:
            color = (0, 180, 255)  # Amber
        elif state_str == NodState.NOD_UP_ARMED.value:
            color = (50, 240, 100)  # Emerald
        elif state_str == NodState.RECOIL_SUPPRESSION.value:
            color = (180, 180, 180)  # Muted gray

        # Reticle circle and pitch vector line
        cv2.circle(frame, (nx, ny), 14, color, 1, cv2.LINE_AA)
        cv2.circle(frame, (nx, ny), 3, (255, 255, 255), -1, cv2.LINE_AA)

        # Pitch displacement vector: pitch > 0 (up) draws arrow up, pitch < 0 (down) draws arrow down
        vector_len = int(np.clip(rel_pitch * 2.2, -35, 35))
        cv2.line(frame, (nx, ny), (nx, ny - vector_len), color, 2, cv2.LINE_AA)
