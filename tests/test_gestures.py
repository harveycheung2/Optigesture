import unittest
import time
from gesture_detector import GestureDetector, GestureMode


class TestGestureDetector(unittest.TestCase):
    def setUp(self):
        self.detector = GestureDetector(
            pinch_click_threshold=0.05,
            pinch_release_threshold=0.07,
            drag_hold_delay=0.2,
            click_cooldown=0.1,
            back_hold_sec=0.2,
        )

    def _mock_landmarks(self, thumb_pos=(0.4, 0.4), index_pos=(0.45, 0.45), middle_pos=(0.7, 0.7)):
        # Provide at least 21 dummy landmarks
        landmarks = [{"nx": 0.0, "ny": 0.0, "nz": 0.0, "px": 0, "py": 0} for _ in range(21)]
        # Wrist at (0.5, 0.7)
        landmarks[0] = {"nx": 0.5, "ny": 0.7, "nz": 0.0, "px": 320, "py": 336}
        landmarks[4] = {"nx": thumb_pos[0], "ny": thumb_pos[1], "nz": 0.0, "px": int(thumb_pos[0]*640), "py": int(thumb_pos[1]*480)}
        # Default palm facing for Right hand: Index MCP(5) to the right of Pinky MCP(17)
        landmarks[5] = {"nx": 0.55, "ny": 0.4, "nz": 0.0, "px": 352, "py": 192}
        landmarks[8] = {"nx": index_pos[0], "ny": index_pos[1], "nz": 0.0, "px": int(index_pos[0]*640), "py": int(index_pos[1]*480)}
        landmarks[12] = {"nx": middle_pos[0], "ny": middle_pos[1], "nz": 0.0, "px": int(middle_pos[0]*640), "py": int(middle_pos[1]*480)}
        landmarks[17] = {"nx": 0.45, "ny": 0.45, "nz": 0.0, "px": 288, "py": 216}
        return landmarks

    def test_idle_when_no_landmarks(self):
        mode, info = self.detector.detect(None, {})
        self.assertEqual(mode, GestureMode.IDLE)

    def test_back_of_hand_clutch_pause(self):
        landmarks = self._mock_landmarks(index_pos=(0.55, 0.2))
        fingers = {"thumb": False, "index": True, "middle": False, "ring": False, "pinky": False}

        # 1. Palm facing camera -> MOVING
        mode, info = self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertFalse(info["is_back_of_hand"])
        self.assertEqual(mode, GestureMode.MOVING)

        # 2. Show Back of Hand (Index MCP 5 at 0.45, Pinky MCP 17 at 0.55)
        # Immediate check: timer starts, NOT yet paused (prevents accidental triggers)
        landmarks[5]["nx"] = 0.45
        landmarks[17]["nx"] = 0.55
        mode, info = self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertTrue(info["is_back_of_hand"])
        self.assertFalse(self.detector.manual_paused)
        self.assertEqual(mode, GestureMode.IDLE)
        self.assertLess(info["back_progress"], 1.0)

        # 3. Hold back of hand continuously for 0.25s (> back_hold_sec=0.2s) -> latches pause!
        time.sleep(0.25)
        mode, info = self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertTrue(info["back_toggled"])
        self.assertTrue(self.detector.manual_paused)
        self.assertEqual(mode, GestureMode.PAUSED)
        self.assertEqual(info["back_progress"], 1.0)

        # 4. Flip back to Palm -> DOES NOT UNPAUSE! (Button-only unpause requirement)
        landmarks[5]["nx"] = 0.55
        landmarks[17]["nx"] = 0.45
        mode, info = self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertTrue(self.detector.manual_paused)
        self.assertEqual(mode, GestureMode.PAUSED)

        # 5. User presses keyboard button [P] or [Space] -> Unpauses!
        self.detector.toggle_pause()
        self.assertFalse(self.detector.manual_paused)
        mode, info = self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertEqual(mode, GestureMode.MOVING)

    def test_back_of_hand_early_release_cancels_timer(self):
        landmarks = self._mock_landmarks()
        fingers = {"thumb": False, "index": True, "middle": False, "ring": False, "pinky": False}
        landmarks[5]["nx"] = 0.45
        landmarks[17]["nx"] = 0.55

        # Show back of hand briefly
        self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertGreater(self.detector.back_start_time, 0.0)

        # Flip back before timer expires
        landmarks[5]["nx"] = 0.55
        landmarks[17]["nx"] = 0.45
        mode, info = self.detector.detect(landmarks, fingers, handedness="Right")
        self.assertFalse(self.detector.manual_paused)
        self.assertEqual(self.detector.back_start_time, 0.0)

    def test_fist_scroll_flick_up_and_down(self):
        landmarks = self._mock_landmarks()
        fist_fingers = {"thumb": False, "index": False, "middle": False, "ring": False, "pinky": False}

        # Step 1: Initial fist detection (anchors previous knuckle y)
        mode, info = self.detector.detect(landmarks, fist_fingers)
        self.assertEqual(mode, GestureMode.SCROLLING)
        self.assertTrue(info["is_fist"])
        self.assertEqual(info["scroll_delta"], 0)

        # Step 2: Flick UP (knuckles move upwards towards y=0.0, ny decreases)
        for lm_idx in [5, 9, 13, 17]:
            landmarks[lm_idx]["ny"] -= 0.035
        mode, info = self.detector.detect(landmarks, fist_fingers)
        self.assertEqual(mode, GestureMode.SCROLLING)
        self.assertGreater(info["scroll_delta"], 0, "Flicking UP must produce positive scroll delta (Scroll UP)")
        self.assertEqual(info["scroll_direction"], "UP")

        # Step 3: Wait for recoil window to expire (0.50s > 0.45s)
        time.sleep(0.50)

        # Step 4: Flick DOWN (knuckles move downwards towards y=1.0, ny increases)
        for lm_idx in [5, 9, 13, 17]:
            landmarks[lm_idx]["ny"] += 0.040
        mode, info = self.detector.detect(landmarks, fist_fingers)
        self.assertEqual(mode, GestureMode.SCROLLING)
        self.assertLess(info["scroll_delta"], 0, "Flicking DOWN must produce negative scroll delta (Scroll DOWN)")
        self.assertEqual(info["scroll_direction"], "DOWN")

        # Step 5: Sensor noise within deadzone (< 0.003) produces zero scroll
        for lm_idx in [5, 9, 13, 17]:
            landmarks[lm_idx]["ny"] += 0.001
        mode, info = self.detector.detect(landmarks, fist_fingers)
        self.assertEqual(mode, GestureMode.SCROLLING)
        self.assertEqual(info["scroll_delta"], 0)

    def test_fist_scroll_recoil_return_stroke_is_suppressed(self):
        landmarks = self._mock_landmarks()
        fist_fingers = {"thumb": False, "index": False, "middle": False, "ring": False, "pinky": False}

        # Initial anchor
        self.detector.detect(landmarks, fist_fingers)

        # 1. Action 1: User flicks UP
        for lm_idx in [5, 9, 13, 17]:
            landmarks[lm_idx]["ny"] -= 0.030
        mode, info_up = self.detector.detect(landmarks, fist_fingers)
        self.assertGreater(info_up["scroll_delta"], 0, "Initial flick up must trigger scroll up")

        # 2. Hand recoils / returns back down to original position immediately (0.05s later)
        time.sleep(0.05)
        for lm_idx in [5, 9, 13, 17]:
            landmarks[lm_idx]["ny"] += 0.030
        mode, info_recoil = self.detector.detect(landmarks, fist_fingers)

        # CRITICAL USER REQUIREMENT: Return stroke must NOT trigger scroll down! Exactly 1 action!
        self.assertEqual(info_recoil["scroll_delta"], 0,
                         "Opposite return stroke during recoil window MUST be suppressed (0 scroll delta)")


    def test_pinch_click(self):
        # Very close thumb and index (< 0.05)
        landmarks = self._mock_landmarks(thumb_pos=(0.50, 0.50), index_pos=(0.52, 0.50))
        fingers = {"thumb": True, "index": True, "middle": False, "ring": False, "pinky": False}
        mode, info = self.detector.detect(landmarks, fingers)
        self.assertEqual(mode, GestureMode.CLICK)

        # Release pinch
        landmarks_far = self._mock_landmarks(thumb_pos=(0.30, 0.30), index_pos=(0.55, 0.55))
        mode, info = self.detector.detect(landmarks_far, fingers)
        self.assertTrue(info["just_clicked"])

    def test_drag_transition(self):
        # Pinch held longer than drag_hold_delay
        landmarks = self._mock_landmarks(thumb_pos=(0.50, 0.50), index_pos=(0.52, 0.50))
        fingers = {"thumb": True, "index": True, "middle": False, "ring": False, "pinky": False}
        self.detector.detect(landmarks, fingers)
        time.sleep(0.25)
        mode, info = self.detector.detect(landmarks, fingers)
        self.assertEqual(mode, GestureMode.DRAGGING)
        self.assertTrue(info["is_dragging"])

    def test_anchor_locking_during_pinch(self):
        # Step 1: user initiates pinch at (0.50, 0.50)
        initial_pos = (0.50, 0.50)
        landmarks = self._mock_landmarks(thumb_pos=(0.49, 0.50), index_pos=initial_pos)
        fingers = {"thumb": True, "index": True, "middle": False, "ring": False, "pinky": False}
        mode, info = self.detector.detect(landmarks, fingers)
        self.assertEqual(mode, GestureMode.CLICK)
        self.assertTrue(info["is_anchored"])
        self.assertEqual(info["pointer_pos"], initial_pos)

        # Step 2: during pinch, finger naturally twitches/drifts to (0.47, 0.51)
        drifted_pos = (0.47, 0.51)
        landmarks_drifted = self._mock_landmarks(thumb_pos=(0.46, 0.51), index_pos=drifted_pos)
        mode, info_drifted = self.detector.detect(landmarks_drifted, fingers)
        self.assertEqual(mode, GestureMode.CLICK)
        self.assertTrue(info_drifted["is_anchored"])
        # Pointer pos MUST remain anchored at initial_pos, rejecting the drift!
        self.assertEqual(info_drifted["pointer_pos"], initial_pos)

    def test_palm_scale_adaptation(self):
        detector_scale = GestureDetector(
            use_palm_scale=True,
            palm_pinch_click_ratio=0.30,
            palm_pinch_release_ratio=0.45,
        )
        landmarks = self._mock_landmarks(thumb_pos=(0.50, 0.50), index_pos=(0.55, 0.50))
        fingers = {"thumb": True, "index": True, "middle": False, "ring": False, "pinky": False}
        # With palm_scale 0.10: effective threshold = 0.03 (dist 0.05 is not a pinch)
        mode, info = detector_scale.detect(landmarks, fingers, palm_scale=0.10)
        self.assertEqual(mode, GestureMode.MOVING)

        # With palm_scale 0.25: effective threshold = 0.075 (dist 0.05 IS a pinch)
        mode, info = detector_scale.detect(landmarks, fingers, palm_scale=0.25)
        self.assertEqual(mode, GestureMode.CLICK)


class TestHandTrackerRotation(unittest.TestCase):
    def test_rotation_invariant_finger_state(self):
        from hand_tracker import HandTracker
        # Build 21 landmarks pointing horizontally to the right
        # Wrist at (0.2, 0.5), index MCP at (0.35, 0.5), index PIP at (0.45, 0.5), index tip at (0.6, 0.5)
        # ny values are identical (0.5), meaning old ny < pip_ny vertical check would fail
        landmarks = [{"nx": 0.2, "ny": 0.5, "nz": 0.0, "px": 128, "py": 240} for _ in range(21)]
        landmarks[0] = {"nx": 0.20, "ny": 0.50, "nz": 0.0, "px": 128, "py": 240}   # WRIST
        landmarks[5] = {"nx": 0.35, "ny": 0.50, "nz": 0.0, "px": 224, "py": 240}   # INDEX_MCP
        landmarks[6] = {"nx": 0.45, "ny": 0.50, "nz": 0.0, "px": 288, "py": 240}   # INDEX_PIP
        landmarks[8] = {"nx": 0.60, "ny": 0.50, "nz": 0.0, "px": 384, "py": 240}   # INDEX_TIP
        # Curl middle finger: tip close to wrist/mcp
        landmarks[9] = {"nx": 0.35, "ny": 0.55, "nz": 0.0, "px": 224, "py": 264}   # MIDDLE_MCP
        landmarks[10] = {"nx": 0.45, "ny": 0.55, "nz": 0.0, "px": 288, "py": 264}  # MIDDLE_PIP
        landmarks[12] = {"nx": 0.30, "ny": 0.55, "nz": 0.0, "px": 192, "py": 264}  # MIDDLE_TIP (curled)
        # Pinky MCP for palm scale
        landmarks[17] = {"nx": 0.35, "ny": 0.65, "nz": 0.0, "px": 224, "py": 312}

        tracker = HandTracker()
        states = tracker.get_finger_states(landmarks)
        self.assertTrue(states["index"])
        self.assertFalse(states["middle"])

        scale = tracker.get_palm_scale(landmarks)
        self.assertAlmostEqual(scale, 0.15, places=2)


if __name__ == "__main__":
    unittest.main()
