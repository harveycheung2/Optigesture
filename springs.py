"""
Apple Fluid Spring Physics Engine and Rubber-Banding for OptiGesture.

Implements Apple's WWDC 'Designing Fluid Interfaces' motion physics:
1. Analytical spring solver with damping_ratio and response parameters.
2. Continuous velocity handoff on interruption (zero brick-wall discontinuities).
3. Apple's exponential rubber-banding formula for soft boundary resistance.
"""

import math
from typing import Tuple, Optional


def rubberband(overshoot: float, dimension: float, constant: float = 0.55) -> float:
    """
    Apple's progressive resistance rubber-banding function.
    Resists progressively when dragged past a boundary instead of hard-stopping.

    Args:
        overshoot: Distance past the boundary (positive or negative).
        dimension: Width or height of the bounded region.
        constant: Elastic stiffness coefficient (Apple default: 0.55).

    Returns:
        Damped displacement past the boundary.
    """
    if dimension <= 0.0 or abs(overshoot) < 1e-6:
        return 0.0
    sign = 1.0 if overshoot >= 0.0 else -1.0
    abs_over = abs(overshoot)
    return sign * (abs_over * dimension * constant) / (dimension + constant * abs_over)


class Spring1D:
    """
    1D Analytical Spring conforming to Apple's design parameters:
    - damping_ratio: 1.0 for critically damped (no overshoot), <1.0 for momentum bounce.
    - response: Duration in seconds to reach the target in the absence of damping.
    """

    def __init__(self, initial_value: float = 0.0, damping_ratio: float = 1.0, response: float = 0.35):
        self.value = float(initial_value)
        self.target = float(initial_value)
        self.velocity = 0.0
        self.damping_ratio = max(0.01, float(damping_ratio))
        self.response = max(0.01, float(response))

    def reset(self, value: float = 0.0, velocity: float = 0.0):
        """Resets spring immediately to target value with given velocity."""
        self.value = float(value)
        self.target = float(value)
        self.velocity = float(velocity)

    def set_target(self, target: float, initial_velocity: Optional[float] = None):
        """Sets a new target. Preserves current velocity unless initial_velocity is provided."""
        self.target = float(target)
        if initial_velocity is not None:
            self.velocity = float(initial_velocity)

    def update(self, dt: float) -> float:
        """
        Advances spring physics by dt seconds using closed-form analytical equations.
        Guarantees unconditional numerical stability regardless of frame rate.
        """
        if dt <= 0.0:
            return self.value

        # Cap dt to avoid large jumps during window pauses
        dt = min(dt, 0.10)

        omega_0 = (2.0 * math.pi) / self.response
        zeta = self.damping_ratio
        x0 = self.value - self.target
        v0 = self.velocity

        # Nearly settled check
        if abs(x0) < 1e-4 and abs(v0) < 1e-4:
            self.value = self.target
            self.velocity = 0.0
            return self.value

        if abs(zeta - 1.0) < 1e-4:
            # 1. Critically damped (zeta == 1.0)
            c1 = x0
            c2 = v0 + omega_0 * x0
            decay = math.exp(-omega_0 * dt)
            x_t = (c1 + c2 * dt) * decay
            v_t = (c2 - omega_0 * (c1 + c2 * dt)) * decay
        elif zeta < 1.0:
            # 2. Underdamped with bounce (zeta < 1.0)
            omega_d = omega_0 * math.sqrt(1.0 - zeta * zeta)
            decay = math.exp(-zeta * omega_0 * dt)
            c1 = x0
            c2 = (v0 + zeta * omega_0 * x0) / omega_d
            cos_term = math.cos(omega_d * dt)
            sin_term = math.sin(omega_d * dt)
            x_t = decay * (c1 * cos_term + c2 * sin_term)
            v_t = decay * (
                (c2 * omega_d - zeta * omega_0 * c1) * cos_term
                - (c1 * omega_d + zeta * omega_0 * c2) * sin_term
            )
        else:
            # 3. Overdamped (zeta > 1.0)
            gamma = omega_0 * math.sqrt(zeta * zeta - 1.0)
            r1 = -zeta * omega_0 + gamma
            r2 = -zeta * omega_0 - gamma
            c2 = (v0 - r1 * x0) / (r2 - r1)
            c1 = x0 - c2
            x_t = c1 * math.exp(r1 * dt) + c2 * math.exp(r2 * dt)
            v_t = c1 * r1 * math.exp(r1 * dt) + c2 * r2 * math.exp(r2 * dt)

        self.value = self.target + x_t
        self.velocity = v_t
        return self.value


class Spring2D:
    """
    2D Spring decomposed into independent X and Y springs.
    Prevents diagonal desynchronization when velocities differ across axes.
    """

    def __init__(
        self,
        initial_x: float = 0.0,
        initial_y: float = 0.0,
        damping_ratio: float = 1.0,
        response: float = 0.35,
    ):
        self.spring_x = Spring1D(initial_x, damping_ratio=damping_ratio, response=response)
        self.spring_y = Spring1D(initial_y, damping_ratio=damping_ratio, response=response)

    def reset(self, x: float = 0.0, y: float = 0.0, vx: float = 0.0, vy: float = 0.0):
        """Resets both axes."""
        self.spring_x.reset(x, vx)
        self.spring_y.reset(y, vy)

    def set_target(
        self,
        target_x: float,
        target_y: float,
        initial_vx: Optional[float] = None,
        initial_vy: Optional[float] = None,
    ):
        """Sets target coordinates for both axes."""
        self.spring_x.set_target(target_x, initial_vx)
        self.spring_y.set_target(target_y, initial_vy)

    def update(self, dt: float) -> Tuple[float, float]:
        """Advances both spring axes by dt."""
        x = self.spring_x.update(dt)
        y = self.spring_y.update(dt)
        return x, y

    @property
    def value(self) -> Tuple[float, float]:
        return self.spring_x.value, self.spring_y.value

    @property
    def velocity(self) -> Tuple[float, float]:
        return self.spring_x.velocity, self.spring_y.velocity
