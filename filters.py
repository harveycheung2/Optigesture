import math
import time
from typing import Tuple, Optional, Dict


class LowPassFilter:
    """Standard 1st-order low-pass filter with exponential smoothing."""
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.s: Optional[float] = None

    def reset(self):
        self.s = None

    def filter(self, val: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.s is None:
            self.s = val
            return val
        self.s = self.alpha * val + (1.0 - self.alpha) * self.s
        return self.s


class OneEuroFilter:
    """
    1€ Filter (One Euro Filter) - Casiez et al., ACM CHI 2012.
    Dynamically balances zero jitter at low speeds with zero lag at high speeds.
    """
    def __init__(
        self,
        min_cutoff: float = 1.2,
        beta: float = 0.05,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.prev_time: Optional[float] = None
        self.prev_val: Optional[float] = None

    def reset(self):
        self.x_filter.reset()
        self.dx_filter.reset()
        self.prev_time = None
        self.prev_val = None

    @staticmethod
    def _alpha(rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate if rate > 0 else 0.016
        return 1.0 / (1.0 + tau / te)

    def filter(self, val: float, timestamp: Optional[float] = None) -> float:
        if timestamp is None:
            timestamp = time.time()

        if self.prev_time is None:
            self.prev_time = timestamp
            self.prev_val = val
            return self.x_filter.filter(val, 1.0)

        dt = timestamp - self.prev_time
        self.prev_time = timestamp

        # Guard against zero or negative dt
        rate = 1.0 / dt if dt > 1e-4 else 60.0

        # 1. Compute and filter velocity (derivative)
        dx = (val - self.prev_val) * rate if self.prev_val is not None else 0.0
        self.prev_val = val
        edx = self.dx_filter.filter(dx, self._alpha(rate, self.d_cutoff))

        # 2. Dynamic cutoff frequency based on speed
        cutoff = self.min_cutoff + self.beta * abs(edx)

        # 3. Filter signal with adaptive cutoff
        return self.x_filter.filter(val, self._alpha(rate, cutoff))


class OneEuroFilter2D:
    """Dual-axis 2D One Euro Filter for cursor screen coordinates."""
    def __init__(
        self,
        min_cutoff: float = 1.2,
        beta: float = 0.04,
        d_cutoff: float = 1.0,
    ):
        self.fx = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        self.fy = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

    def reset(self):
        self.fx.reset()
        self.fy.reset()

    def filter(self, x: float, y: float, timestamp: Optional[float] = None) -> Tuple[int, int]:
        sx = self.fx.filter(x, timestamp)
        sy = self.fy.filter(y, timestamp)
        return int(round(sx)), int(round(sy))


class PointerBallistics:
    """
    Non-linear pointer acceleration curves (similar to OS mouse acceleration).
    - Slow wrist motions: 1.0x fine precision for small buttons/tabs.
    - Fast wrist motions: 1.6x - 2.2x dynamic gain to traverse full 4K/3K screens effortlessly.
    """
    def __init__(
        self,
        precision_speed_px_s: float = 90.0,
        max_speed_px_s: float = 550.0,
        max_gain: float = 2.1,
    ):
        self.precision_speed = precision_speed_px_s
        self.max_speed = max_speed_px_s
        self.max_gain = max_gain

        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None
        self.last_time: Optional[float] = None
        self.acc_x: Optional[float] = None
        self.acc_y: Optional[float] = None

    def reset(self):
        self.last_x = None
        self.last_y = None
        self.last_time = None
        self.acc_x = None
        self.acc_y = None

    def accelerate(self, raw_x: float, raw_y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if timestamp is None:
            timestamp = time.time()

        if self.last_x is None or self.last_time is None:
            self.last_x = raw_x
            self.last_y = raw_y
            self.last_time = timestamp
            self.acc_x = raw_x
            self.acc_y = raw_y
            return raw_x, raw_y

        dt = timestamp - self.last_time
        self.last_time = timestamp

        if dt <= 1e-4:
            return self.acc_x, self.acc_y

        dx = raw_x - self.last_x
        dy = raw_y - self.last_y
        self.last_x = raw_x
        self.last_y = raw_y

        speed = math.hypot(dx, dy) / dt

        # Calculate non-linear gain factor
        if speed <= self.precision_speed:
            gain = 1.0
        else:
            ratio = min(1.0, (speed - self.precision_speed) / (self.max_speed - self.precision_speed))
            # Smooth quadratic acceleration curve
            gain = 1.0 + (self.max_gain - 1.0) * (ratio ** 1.4)

        self.acc_x += dx * gain
        self.acc_y += dy * gain

        return self.acc_x, self.acc_y


class LandmarkSmoother:
    """
    Stage 1 Landmark Pre-Filter: Smoothes raw 2D landmark coordinates in camera space
    (0.0 - 1.0) before coordinate transformation to remove camera sensor quantization noise.
    """
    def __init__(self, alpha: float = 0.65):
        self.alpha = alpha
        self.landmarks: Dict[int, Tuple[float, float]] = {}

    def smooth(self, landmark_id: int, x: float, y: float) -> Tuple[float, float]:
        if landmark_id not in self.landmarks:
            self.landmarks[landmark_id] = (x, y)
            return x, y

        prev_x, prev_y = self.landmarks[landmark_id]
        sx = prev_x + self.alpha * (x - prev_x)
        sy = prev_y + self.alpha * (y - prev_y)
        self.landmarks[landmark_id] = (sx, sy)
        return sx, sy

    def reset(self):
        self.landmarks.clear()


class AdaptiveEMAFilter:
    """
    Backward-compatible Adaptive Exponential Moving Average (EMA) Filter.
    """
    def __init__(
        self,
        base_alpha: float = 0.65,
        min_alpha: float = 0.20,
        max_alpha: float = 0.95,
        deadzone_px: float = 3.0,
        velocity_scale: float = 0.05,
    ):
        self.base_alpha = base_alpha
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.deadzone_px = deadzone_px
        self.velocity_scale = velocity_scale

        self.prev_x: Optional[float] = None
        self.prev_y: Optional[float] = None

    def reset(self):
        self.prev_x = None
        self.prev_y = None

    def filter(self, target_x: float, target_y: float) -> Tuple[int, int]:
        if self.prev_x is None or self.prev_y is None:
            self.prev_x = target_x
            self.prev_y = target_y
            return int(round(target_x)), int(round(target_y))

        dx = target_x - self.prev_x
        dy = target_y - self.prev_y
        dist = math.hypot(dx, dy)

        if dist < self.deadzone_px:
            return int(round(self.prev_x)), int(round(self.prev_y))

        alpha = self.base_alpha + (dist * self.velocity_scale)
        alpha = max(self.min_alpha, min(self.max_alpha, alpha))

        smooth_x = self.prev_x + alpha * dx
        smooth_y = self.prev_y + alpha * dy

        self.prev_x = smooth_x
        self.prev_y = smooth_y

        return int(round(smooth_x)), int(round(smooth_y))
