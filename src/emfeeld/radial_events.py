"""First detected transverse crossings of a fixed-radius observation sphere.

This is measurement geometry, not a charged shell, a material surface, or an
assumption of central-force motion. It works with supported source compositions.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .event_core import EventIssue, SurfaceEvents, search

DIRECTIONS = {'outward': 1, 'inward': -1, 'either': 0}
LIMITS = ('First detected transverse radial root only; multiple crossings within a solver step '
          'can be missed, including entry and exit through a small sphere during one step. '
          'Refinement is not a completeness proof. Tangencies, circular-on-surface motion, '
          'turning points and closest approach are not qualified. No collision or feedback; '
          'shell/plane-source dynamics remain unsupported.')


@dataclass(frozen=True)
class RadialRequest:
    id: str
    particle_index: int
    center_m: tuple[float, ...]
    radius_m: float
    direction: str
    max_step_s: float
    min_radial_speed_m_s: float
    time_atol_s: float
    position_atol_m: float
    velocity_atol_m_s: float
    rtol: float
    type: str = 'trajectory_event'

    @property
    def min_crossing_speed_m_s(self):
        return self.min_radial_speed_m_s

    def key(self):
        return tuple(v for k, v in vars(self).items() if k not in ('id', 'type'))


def separation(position, center, radius):
    """norm(position-center)-R, plus a conservative coordinate/norm allowance.

    No length floor, squared-distance overflow, spatial softening or geometric
    snapping. The allowance is a float64 filter, not an adaptive exact predicate.
    """
    p, c = np.asarray(position, dtype=float), np.asarray(center, dtype=float)
    d = p - c
    distance = float(np.hypot.reduce(d))
    residual = distance - radius
    eps = np.finfo(float).eps
    uncertainty = float(2 * eps * np.hypot.reduce(np.abs(p) + np.abs(c))
                        + 8 * eps * (distance + radius))
    if not math.isfinite(residual) or not math.isfinite(uncertainty):
        raise FloatingPointError('nonfinite radial separation or coordinate uncertainty')
    return residual, uncertainty


class RadialSurface:
    kind, label, speed_label = 'radial', 'sphere', 'radial'
    residual_key, speed_key = 'signed_radial_residual_m', 'radial_speed_m_s'
    limits = LIMITS

    def __init__(self, request):
        self.request = request
        self.direction = DIRECTIONS[request.direction]

    def separation(self, position):
        return separation(position, self.request.center_m, self.request.radius_m)

    def normal_speed(self, state):
        d = np.asarray(state[:3]) - self.request.center_m
        distance = float(np.hypot.reduce(d))
        _, uncertainty = self.separation(state[:3])
        if distance <= uncertainty:
            raise EventIssue('ambiguous_event', 'radial_direction_unresolved',
                             'The radial direction at the detected root is numerically unresolved.')
        # Requested radius is positive; never normalize the zero vector at the centre.
        return float(np.dot(d / distance, state[3:]))

    def condition(self):
        return dict(type='radial', center_m=list(self.request.center_m),
                    radius_m=self.request.radius_m, direction=self.request.direction)


def _search(scene, request, refined):
    return search(scene, request, refined, RadialSurface(request), solve_ivp)


class RadialEvents(SurfaceEvents):
    def surface(self, request):
        return RadialSurface(request)

    def search(self, request, refined):
        return _search(self.scene, request, refined)
