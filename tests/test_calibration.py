import unittest
from calibration import GestureCalibrator, CalibrationStep


class TestGestureCalibrator(unittest.TestCase):
    def setUp(self):
        self.calibrator = GestureCalibrator()

    def _mock_landmarks(self, thumb_pos=(0.4, 0.4), index_pos=(0.55, 0.4)):
        landmarks = [{"nx": 0.0, "ny": 0.0, "nz": 0.0, "px": 0, "py": 0} for _ in range(21)]
        landmarks[4] = {"nx": thumb_pos[0], "ny": thumb_pos[1], "nz": 0.0, "px": int(thumb_pos[0]*640), "py": int(thumb_pos[1]*480)}
        landmarks[8] = {"nx": index_pos[0], "ny": index_pos[1], "nz": 0.0, "px": int(index_pos[0]*640), "py": int(index_pos[1]*480)}
        return landmarks

    def test_initial_state(self):
        self.assertEqual(self.calibrator.step, CalibrationStep.NOT_STARTED)
        self.assertFalse(self.calibrator.is_active)

    def test_step_1_resting_hand(self):
        self.calibrator.start()
        self.assertEqual(self.calibrator.step, CalibrationStep.RESTING)
        self.assertTrue(self.calibrator.is_active)

        # Feed open hand frames (distance ~0.15)
        open_lm = self._mock_landmarks(thumb_pos=(0.40, 0.40), index_pos=(0.55, 0.40))
        fingers = {"index": True, "thumb": True}

        for _ in range(self.calibrator.FRAMES_REQUIRED):
            step, prog, msg = self.calibrator.update(open_lm, fingers, palm_scale=0.18)

        # Should transition to PINCH step
        self.assertEqual(self.calibrator.step, CalibrationStep.PINCH)

    def test_full_calibration_sequence(self):
        self.calibrator.start()

        open_lm = self._mock_landmarks(thumb_pos=(0.40, 0.40), index_pos=(0.55, 0.40))
        pinch_lm = self._mock_landmarks(thumb_pos=(0.50, 0.50), index_pos=(0.52, 0.50))
        fingers = {"index": True, "thumb": True}

        # Complete Step 1: Resting
        for _ in range(self.calibrator.FRAMES_REQUIRED):
            self.calibrator.update(open_lm, fingers, palm_scale=0.18)

        self.assertEqual(self.calibrator.step, CalibrationStep.PINCH)

        # Complete Step 2: Pinching
        for _ in range(self.calibrator.FRAMES_REQUIRED):
            self.calibrator.update(pinch_lm, fingers, palm_scale=0.18)

        self.assertEqual(self.calibrator.step, CalibrationStep.COMPLETE)
        self.assertFalse(self.calibrator.is_active)

        # Verify personalized threshold calculations
        self.assertGreater(self.calibrator.calibrated_click_thresh, 0.02)
        self.assertGreater(self.calibrator.calibrated_release_thresh, self.calibrator.calibrated_click_thresh)
        self.assertAlmostEqual(self.calibrator.calibrated_palm_scale, 0.18, places=2)


if __name__ == "__main__":
    unittest.main()
