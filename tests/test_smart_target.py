import unittest
from smart_target import SmartTargetAssistant


class TestSmartTargetAssistant(unittest.TestCase):
    def setUp(self):
        # Disable desktop overlay for headless unit testing
        self.assistant = SmartTargetAssistant(
            snap_radius=50.0,
            snap_strength=0.60,
            enable_snap=True,
            enable_overlay=False,
        )

    def tearDown(self):
        self.assistant.close()

    def test_magnetic_snap_near_target(self):
        # Simulate a mock target at center (500, 300) with 60x30 button
        mock_target = {
            "name": "Submit",
            "type": "Button",
            "rect": (470, 285, 530, 315),
            "center": (500.0, 300.0),
            "distance": 20.0,  # Within 50px snap radius
        }

        with self.assistant.lock:
            self.assistant.current_target = mock_target

        # Cursor at (460, 280)
        cursor_x, cursor_y = 460.0, 280.0
        snapped_x, snapped_y, target = self.assistant.apply_magnetic_snap(cursor_x, cursor_y)

        # Snapped point should be pulled closer towards (500, 300)
        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "Submit")
        self.assertGreater(snapped_x, cursor_x)
        self.assertGreater(snapped_y, cursor_y)

    def test_no_snap_beyond_radius(self):
        mock_target = {
            "name": "Cancel",
            "type": "Button",
            "rect": (100, 100, 150, 130),
            "center": (125.0, 115.0),
            "distance": 85.0,  # Beyond 50px snap radius
        }

        with self.assistant.lock:
            self.assistant.current_target = mock_target

        cursor_x, cursor_y = 210.0, 200.0
        snapped_x, snapped_y, target = self.assistant.apply_magnetic_snap(cursor_x, cursor_y)

        # Should NOT snap coordinates when outside radius
        self.assertEqual(snapped_x, cursor_x)
        self.assertEqual(snapped_y, cursor_y)

    def test_toggle_snap(self):
        initial = self.assistant.enable_snap
        toggled = self.assistant.toggle_snap()
        self.assertEqual(toggled, not initial)
        restored = self.assistant.toggle_snap()
        self.assertEqual(restored, initial)


if __name__ == "__main__":
    unittest.main()
