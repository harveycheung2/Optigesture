import unittest
from filters import AdaptiveEMAFilter, LandmarkSmoother, OneEuroFilter, OneEuroFilter2D, PointerBallistics


class TestFilters(unittest.TestCase):
    def test_filter_initialization(self):
        f = AdaptiveEMAFilter()
        x, y = f.filter(100.0, 200.0)
        self.assertEqual(x, 100)
        self.assertEqual(y, 200)

    def test_deadzone_suppression(self):
        f = AdaptiveEMAFilter(deadzone_px=5.0)
        f.filter(500.0, 500.0)
        # Movement less than 5px should be suppressed
        x2, y2 = f.filter(502.0, 501.0)
        self.assertEqual(x2, 500)
        self.assertEqual(y2, 500)

    def test_adaptive_smoothing(self):
        f = AdaptiveEMAFilter(base_alpha=0.5, deadzone_px=1.0)
        f.filter(0.0, 0.0)
        x, y = f.filter(100.0, 100.0)
        self.assertGreater(x, 0)
        self.assertLess(x, 100)

    def test_one_euro_filter_stability_at_low_speed(self):
        # 1€ filter: small jitter at rest should be aggressively smoothed
        oef = OneEuroFilter(min_cutoff=1.0, beta=0.01)
        t0 = 100.0
        val0 = oef.filter(500.0, timestamp=t0)
        self.assertEqual(val0, 500.0)

        # Micro-jitter of 0.5px
        val1 = oef.filter(500.5, timestamp=t0 + 0.033)
        # Should heavily damp the micro-jitter
        self.assertLess(abs(val1 - 500.0), 0.3)

    def test_one_euro_filter_responsiveness_at_high_speed(self):
        # Fast motion: beta increases cutoff to eliminate lag
        oef = OneEuroFilter(min_cutoff=1.0, beta=0.1)
        t0 = 100.0
        oef.filter(0.0, timestamp=t0)
        # Fast jump across screen in 33ms (speed ~6000 px/s)
        val = oef.filter(200.0, timestamp=t0 + 0.033)
        # Filter should respond strongly with minimal lag
        self.assertGreater(val, 100.0)

    def test_one_euro_filter_2d(self):
        f2d = OneEuroFilter2D(min_cutoff=1.2, beta=0.04)
        x, y = f2d.filter(1440.0, 810.0, timestamp=1.0)
        self.assertEqual(x, 1440)
        self.assertEqual(y, 810)

        x2, y2 = f2d.filter(1441.0, 810.5, timestamp=1.033)
        self.assertIsInstance(x2, int)
        self.assertIsInstance(y2, int)

    def test_pointer_ballistics_precision_vs_speed(self):
        pb = PointerBallistics(precision_speed_px_s=100.0, max_speed_px_s=500.0, max_gain=2.0)
        # Initial point
        pb.accelerate(100.0, 100.0, timestamp=1.0)

        # 1. Slow precision motion: 2px in 0.033s -> speed ~60 px/s (< 100 px/s)
        ax1, ay1 = pb.accelerate(102.0, 100.0, timestamp=1.033)
        # Gain should be 1.0 (linear precision)
        self.assertAlmostEqual(ax1, 102.0, places=1)

        # 2. Fast sweep motion: 30px in 0.033s -> speed ~900 px/s (> max_speed)
        ax2, ay2 = pb.accelerate(132.0, 100.0, timestamp=1.066)
        # Gain should reach ~2.0, accelerating output displacement beyond 30px
        delta = ax2 - ax1
        self.assertGreater(delta, 35.0)

    def test_landmark_smoother(self):
        ls = LandmarkSmoother(alpha=0.5)
        x1, y1 = ls.smooth(8, 0.5, 0.5)
        self.assertAlmostEqual(x1, 0.5)
        self.assertAlmostEqual(y1, 0.5)

        x2, y2 = ls.smooth(8, 0.7, 0.7)
        self.assertAlmostEqual(x2, 0.6)
        self.assertAlmostEqual(y2, 0.6)


if __name__ == "__main__":
    unittest.main()
