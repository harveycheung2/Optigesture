import time
import math
from enum import Enum
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


class CalibrationStep(Enum):
    NOT_STARTED = "NOT_STARTED"
    RESTING = "RESTING"       # Step 1: Natural resting hand
    PINCH = "PINCH"           # Step 2: Pinch click action
    COMPLETE = "COMPLETE"     # Calibration finished


class GestureCalibrator:
    """
    Guides the user through an interactive 2-step calibration process:
    1. Measure natural resting hand: open finger distances & baseline palm scale.
    2. Measure personal pinch action: thumb-to-index pinch contact distance.
    Computes custom, personalized click and release thresholds.
    """

    FRAMES_REQUIRED = 30  # ~1 second of steady hand data per step

    def __init__(self):
        self.step = CalibrationStep.NOT_STARTED
        self.resting_samples: List[float] = []
        self.palm_samples: List[float] = []
        self.pinch_samples: List[float] = []

        self.calibrated_click_thresh: float = 0.045
        self.calibrated_release_thresh: float = 0.065
        self.calibrated_palm_scale: float = 0.15

        self.step_start_time = 0.0
        self.is_active = False

    def start(self):
        """Starts the calibration wizard from Step 1."""
        self.step = CalibrationStep.RESTING
        self.resting_samples.clear()
        self.palm_samples.clear()
        self.pinch_samples.clear()
        self.step_start_time = time.time()
        self.is_active = True

    def cancel(self):
        """Cancels calibration and exits."""
        self.is_active = False
        self.step = CalibrationStep.NOT_STARTED

    def update(
        self,
        landmarks: Optional[List[Dict[str, float]]],
        finger_states: Dict[str, bool],
        palm_scale: float
    ) -> Tuple[CalibrationStep, float, str]:
        """
        Processes current frame and updates sampling progress.
        Returns: (current_step, progress_0_to_1, status_message)
        """
        if not self.is_active:
            return self.step, 0.0, ""

        if not landmarks or len(landmarks) < 21:
            msg = "Place your hand in camera view..."
            prog = len(self.resting_samples) / self.FRAMES_REQUIRED if self.step == CalibrationStep.RESTING else len(self.pinch_samples) / self.FRAMES_REQUIRED
            return self.step, prog, msg

        thumb = landmarks[4]
        index = landmarks[8]
        dist = math.hypot(thumb["nx"] - index["nx"], thumb["ny"] - index["ny"])

        # STEP 1: RESTING HAND
        if self.step == CalibrationStep.RESTING:
            # Check that hand is somewhat open (index finger extended)
            if finger_states.get("index", False) and dist > 0.06:
                self.resting_samples.append(dist)
                self.palm_samples.append(palm_scale)
            msg = "STEP 1/2: Hold natural resting hand in view..."
            progress = len(self.resting_samples) / float(self.FRAMES_REQUIRED)

            if len(self.resting_samples) >= self.FRAMES_REQUIRED:
                self.step = CalibrationStep.PINCH
                self.step_start_time = time.time()
                self.pinch_samples.clear()
                msg = "STEP 1 Complete! Now prepare to pinch..."
                return self.step, 1.0, msg

            return self.step, progress, msg

        # STEP 2: PINCH CLICK
        elif self.step == CalibrationStep.PINCH:
            # Sample when fingers are drawn close
            if dist < 0.10:
                self.pinch_samples.append(dist)
            msg = "STEP 2/2: Pinch thumb and index together (Click)..."
            progress = len(self.pinch_samples) / float(self.FRAMES_REQUIRED)

            if len(self.pinch_samples) >= self.FRAMES_REQUIRED:
                self._compute_results()
                self.step = CalibrationStep.COMPLETE
                self.is_active = False
                msg = f"CALIBRATED! Click Thresh: {self.calibrated_click_thresh:.3f}"
                return self.step, 1.0, msg

            return self.step, progress, msg

        return self.step, 1.0, "Calibration Complete!"

    def _compute_results(self):
        """Calculates personalized thresholds based on collected samples."""
        avg_rest = float(np.mean(self.resting_samples)) if self.resting_samples else 0.12
        avg_pinch = float(np.mean(self.pinch_samples)) if self.pinch_samples else 0.03
        avg_palm = float(np.mean(self.palm_samples)) if self.palm_samples else 0.16

        # Click threshold lies comfortably between minimum pinch and relaxed state
        click_thresh = (avg_pinch * 0.65) + (avg_rest * 0.35)
        # Clamp to realistic bounds
        self.calibrated_click_thresh = max(0.025, min(0.080, click_thresh))
        self.calibrated_release_thresh = max(self.calibrated_click_thresh + 0.015, min(0.110, click_thresh * 1.35))
        self.calibrated_palm_scale = max(0.08, min(0.30, avg_palm))

    def render_overlay(self, frame, progress: float, message: str):
        """Renders an aesthetic sci-fi calibration wizard overlay on the video frame."""
        h, w = frame.shape[:2]

        # Darkened modal card in center of screen
        card_w, card_h = 460, 160
        cx, cy = w // 2, h // 2
        x1, y1 = cx - card_w // 2, cy - card_h // 2
        x2, y2 = x1 + card_w, y1 + card_h

        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (20, 20, 28), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Border & Corner brackets
        border_col = (0, 230, 255) if self.step == CalibrationStep.RESTING else (60, 220, 80)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 60, 75), 1)

        length = 16
        for corner in [(x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)]:
            px, py, dx, dy = corner
            cv2.line(frame, (px, py), (px + dx * length, py), border_col, 2)
            cv2.line(frame, (px, py), (px, py + dy * length), border_col, 2)

        # Title
        title = "HAND GESTURE CALIBRATION"
        cv2.putText(frame, title, (x1 + 20, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # Step Indicator
        step_label = f"STEP {1 if self.step == CalibrationStep.RESTING else 2} OF 2"
        cv2.putText(frame, step_label, (x2 - 110, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, border_col, 1, cv2.LINE_AA)

        # Subtitle Instruction message
        cv2.putText(frame, message, (x1 + 20, y1 + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (220, 220, 230), 1, cv2.LINE_AA)

        # Progress Bar
        bar_x1 = x1 + 20
        bar_y1 = y1 + 95
        bar_w = card_w - 40
        bar_h = 14

        cv2.rectangle(frame, (bar_x1, bar_y1), (bar_x1 + bar_w, bar_y1 + bar_h), (50, 50, 65), 1)
        fill_w = int(bar_w * max(0.0, min(1.0, progress)))
        if fill_w > 0:
            cv2.rectangle(frame, (bar_x1 + 1, bar_y1 + 1), (bar_x1 + fill_w, bar_y1 + bar_h - 1), border_col, -1)

        # Skip / Shortcut text
        hint = "[Space] Skip with defaults  |  [Esc] Cancel"
        cv2.putText(frame, hint, (x1 + 20, y1 + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 140, 150), 1, cv2.LINE_AA)
