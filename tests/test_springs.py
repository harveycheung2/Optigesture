import unittest
import math
from springs import Spring1D, Spring2D, rubberband


class TestSpringPhysics(unittest.TestCase):
    def test_critically_damped_spring_settles_without_overshoot(self):
        # damping_ratio = 1.0 (critically damped)
        spring = Spring1D(initial_value=0.0, damping_ratio=1.0, response=0.30)
        spring.set_target(100.0)

        dt = 0.016  # ~60 FPS
        max_val = 0.0
        for _ in range(60):  # Simulate ~1 second
            val = spring.update(dt)
            max_val = max(max_val, val)

        # Critically damped spring should monotonically approach target and never exceed it
        self.assertLessEqual(max_val, 100.001, "Critically damped spring must not overshoot target")
        self.assertAlmostEqual(spring.value, 100.0, delta=0.5, msg="Spring should settle near 100.0 after 1s")

    def test_underdamped_spring_has_controlled_bounce(self):
        # damping_ratio = 0.70 (momentum bounce)
        spring = Spring1D(initial_value=0.0, damping_ratio=0.70, response=0.25)
        spring.set_target(100.0)

        dt = 0.016
        max_val = 0.0
        for _ in range(30):
            val = spring.update(dt)
            max_val = max(max_val, val)

        # Underdamped spring should have slight momentum overshoot
        self.assertGreater(max_val, 100.0, "Underdamped spring must have slight momentum overshoot")
        self.assertLess(max_val, 115.0, "Overshoot must remain gentle and controlled")

    def test_velocity_handoff_on_interruption(self):
        # Spring is moving forward towards 100, then retargeted to 0 while mid-motion
        spring = Spring1D(initial_value=0.0, damping_ratio=1.0, response=0.40)
        spring.set_target(100.0)

        # Advance 5 frames (building positive velocity)
        for _ in range(5):
            spring.update(0.016)

        vel_before = spring.velocity
        self.assertGreater(vel_before, 0.0, "Spring should be moving positively")

        # Interrupted and redirected back to 0.0
        spring.set_target(0.0)
        # Verify velocity is preserved (no brick-wall stop)
        self.assertAlmostEqual(spring.velocity, vel_before, delta=1e-3, msg="Velocity must be preserved upon retargeting")

    def test_spring_2d_axes_are_independent(self):
        spring2d = Spring2D(initial_x=0.0, initial_y=0.0, damping_ratio=1.0, response=0.30)
        spring2d.set_target(50.0, 200.0)

        dt = 0.016
        for _ in range(40):
            x, y = spring2d.update(dt)

        self.assertAlmostEqual(x, 50.0, delta=1.0)
        self.assertAlmostEqual(y, 200.0, delta=1.0)

    def test_rubberband_progressive_resistance(self):
        dimension = 100.0
        # 1. Zero overshoot -> zero resistance displacement
        self.assertEqual(rubberband(0.0, dimension), 0.0)

        # 2. Small overshoot -> follows closely
        small_disp = rubberband(5.0, dimension, constant=0.55)
        self.assertGreater(small_disp, 0.0)
        self.assertLess(small_disp, 5.0)

        # 3. Large overshoot -> resisted progressively
        large_disp = rubberband(100.0, dimension, constant=0.55)
        self.assertLess(large_disp, 50.0, "Large overshoot must experience strong progressive resistance")

        # 4. Monotonicity: larger overshoot produces larger displacement, but decelerates
        huge_disp = rubberband(200.0, dimension, constant=0.55)
        self.assertGreater(huge_disp, large_disp)
        # Marginal gain from 100 to 200 is less than from 0 to 100
        gain_1 = large_disp - 0.0
        gain_2 = huge_disp - large_disp
        self.assertLess(gain_2, gain_1, "Rubber-banding must be concave (progressive resistance)")

        # 5. Negative overshoot is symmetric
        neg_disp = rubberband(-50.0, dimension, constant=0.55)
        pos_disp = rubberband(50.0, dimension, constant=0.55)
        self.assertAlmostEqual(neg_disp, -pos_disp, places=5)


if __name__ == "__main__":
    unittest.main()
