import unittest
import numpy as np
from head_tracker import HeadTracker, NodState


class MockLandmark:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z


def create_mock_face_landmarks(forehead_z: float = 0.0, chin_z: float = 0.0):
    """Generates mock face landmarks with specified 3D depth for pitch estimation."""
    landmarks = [MockLandmark(0.5, 0.5, 0.0) for _ in range(478)]
    landmarks[HeadTracker.NOSE_TIP_LM] = MockLandmark(0.50, 0.50, 0.0)
    landmarks[HeadTracker.FOREHEAD_LM] = MockLandmark(0.50, 0.30, forehead_z)
    landmarks[HeadTracker.CHIN_LM] = MockLandmark(0.50, 0.70, chin_z)
    landmarks[HeadTracker.LEFT_EYE_LM] = MockLandmark(0.60, 0.45, 0.0)
    landmarks[HeadTracker.RIGHT_EYE_LM] = MockLandmark(0.40, 0.45, 0.0)
    return landmarks


def create_pitch_matrix(pitch_degrees: float) -> np.ndarray:
    """Creates a 4x4 transformation matrix with a given pitch rotation in degrees."""
    rad = np.radians(pitch_degrees)
    # Rotation around X axis:
    # [ 1,       0,        0, 0 ]
    # [ 0,  cos(θ),   sin(θ), 0 ]
    # [ 0, -sin(θ),   cos(θ), 0 ]
    # [ 0,       0,        0, 1 ]
    mat = np.eye(4, dtype=np.float32)
    mat[1, 1] = np.cos(rad)
    mat[1, 2] = np.sin(rad)
    mat[2, 1] = -np.sin(rad)
    mat[2, 2] = np.cos(rad)
    return mat


class TestHeadTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = HeadTracker(
            pitch_threshold=8.0,
            return_deadzone=3.0,
            recoil_window_sec=0.50,
            cooldown_sec=0.25,
            scroll_steps=4,
        )

    def test_initial_neutral_state(self):
        landmarks = create_mock_face_landmarks()
        matrix = create_pitch_matrix(0.0)
        res = self.tracker.update(landmarks, matrix, curr_time=1.0)

        self.assertTrue(res["has_face"])
        self.assertEqual(res["state"], NodState.NEUTRAL.value)
        self.assertEqual(res["scroll_delta"], 0)
        self.assertEqual(res["scroll_direction"], "NONE")

    def test_nod_down_and_return_scrolls_down(self):
        landmarks = create_mock_face_landmarks()

        # Step 1: Head at neutral
        matrix_neutral = create_pitch_matrix(0.0)
        self.tracker.update(landmarks, matrix_neutral, curr_time=1.0)

        # Step 2: Tilt head DOWN to -10 degrees (past -8.0 threshold)
        matrix_down = create_pitch_matrix(-10.0)
        res_down = self.tracker.update(landmarks, matrix_down, curr_time=1.1)
        self.assertEqual(res_down["state"], NodState.NOD_DOWN_ARMED.value)
        self.assertTrue(res_down["is_nod_down_armed"])
        self.assertEqual(res_down["scroll_delta"], 0, "No scroll should fire while still tilted down")

        # Step 3: Return head back to NEUTRAL (-2.0 degrees, within return deadzone)
        matrix_return = create_pitch_matrix(-2.0)
        res_return = self.tracker.update(landmarks, matrix_return, curr_time=1.2)

        self.assertEqual(res_return["scroll_delta"], -4, "Return to neutral must fire Scroll Down (-4)")
        self.assertEqual(res_return["scroll_direction"], "DOWN")
        self.assertEqual(res_return["state"], NodState.RECOIL_SUPPRESSION.value)

    def test_recoil_suppression_prevents_opposite_scroll_on_rebound(self):
        landmarks = create_mock_face_landmarks()

        # 1. Complete a nod down
        self.tracker.update(landmarks, create_pitch_matrix(0.0), curr_time=1.0)
        self.tracker.update(landmarks, create_pitch_matrix(-10.0), curr_time=1.1)
        res_trigger = self.tracker.update(landmarks, create_pitch_matrix(-1.5), curr_time=1.2)
        self.assertEqual(res_trigger["scroll_delta"], -4)

        # 2. Neck recoils/overshoots into UP tilt (+10.0 degrees) 0.15s later
        # MUST BE SUPPRESSED: Exactly 1 action per nod!
        res_rebound = self.tracker.update(landmarks, create_pitch_matrix(10.0), curr_time=1.35)
        self.assertEqual(res_rebound["scroll_delta"], 0, "Rebound tilt up during recoil window must be suppressed")
        self.assertEqual(res_rebound["scroll_direction"], "NONE")

        # 3. Even returning from rebound during recoil window must NOT trigger scroll
        res_rebound_return = self.tracker.update(landmarks, create_pitch_matrix(1.0), curr_time=1.45)
        self.assertEqual(res_rebound_return["scroll_delta"], 0)

    def test_nod_up_and_return_scrolls_up(self):
        landmarks = create_mock_face_landmarks()

        # Step 1: Head at neutral
        matrix_neutral = create_pitch_matrix(0.0)
        self.tracker.update(landmarks, matrix_neutral, curr_time=2.0)

        # Step 2: Tilt head UP to +10 degrees (past +8.0 threshold)
        matrix_up = create_pitch_matrix(10.0)
        res_up = self.tracker.update(landmarks, matrix_up, curr_time=2.1)
        self.assertEqual(res_up["state"], NodState.NOD_UP_ARMED.value)
        self.assertTrue(res_up["is_nod_up_armed"])
        self.assertEqual(res_up["scroll_delta"], 0, "No scroll should fire while still tilted up")

        # Step 3: Return head back to NEUTRAL (+2.0 degrees, within return deadzone)
        matrix_return = create_pitch_matrix(2.0)
        res_return = self.tracker.update(landmarks, matrix_return, curr_time=2.2)

        self.assertEqual(res_return["scroll_delta"], 4, "Return to neutral must fire Scroll Up (+4)")
        self.assertEqual(res_return["scroll_direction"], "UP")
        self.assertEqual(res_return["state"], NodState.RECOIL_SUPPRESSION.value)

    def test_recoil_suppression_prevents_down_scroll_on_up_nod_rebound(self):
        landmarks = create_mock_face_landmarks()

        # 1. Complete a nod up
        self.tracker.update(landmarks, create_pitch_matrix(0.0), curr_time=3.0)
        self.tracker.update(landmarks, create_pitch_matrix(10.0), curr_time=3.1)
        res_trigger = self.tracker.update(landmarks, create_pitch_matrix(1.5), curr_time=3.2)
        self.assertEqual(res_trigger["scroll_delta"], 4)

        # 2. Neck recoils/overshoots into DOWN tilt (-10.0 degrees) 0.15s later
        res_rebound = self.tracker.update(landmarks, create_pitch_matrix(-10.0), curr_time=3.35)
        self.assertEqual(res_rebound["scroll_delta"], 0, "Rebound tilt down during recoil window must be suppressed")
        self.assertEqual(res_rebound["scroll_direction"], "NONE")

    def test_draw_head_pose_does_not_crash(self):
        landmarks = create_mock_face_landmarks()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        info = {
            "relative_pitch": 5.0,
            "state": NodState.NOD_UP_ARMED.value,
        }
        self.tracker.draw_head_pose(frame, landmarks, info)
        self.assertTrue(np.any(frame > 0))


if __name__ == "__main__":
    unittest.main()
