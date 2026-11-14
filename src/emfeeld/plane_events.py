"""Transverse plane observations using the shared native event machinery.

M2A request semantics, result objects and plane arithmetic remain unchanged.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.integrate import solve_ivp
from .event_core import EventIssue, LIMITS, UNITS, SurfaceEvents, _state, search

DIRECTIONS = {'positive': 1, 'negative': -1, 'either': 0}


@dataclass(frozen=True)
class PlaneRequest:
    id: str
    particle_index: int
    point_m: tuple[float, ...]
    normal: tuple[float, ...]
    direction: str
    max_step_s: float
    min_normal_speed_m_s: float
    time_atol_s: float
    position_atol_m: float
    velocity_atol_m_s: float
    rtol: float
    type: str = 'trajectory_event'

    @property
    def min_crossing_speed_m_s(self):
        return self.min_normal_speed_m_s

    def key(self):
        # Exact validated geometry/settings; ids do not change the calculation.
        return tuple(v for k, v in vars(self).items() if k not in ('id', 'type'))


def separation(position, point, normal):
    """Signed distance and a conservative float64 coordinate/dot-product allowance."""
    p, o, n = np.asarray(position), np.asarray(point), np.asarray(normal)
    d = p - o
    s = float(np.dot(d, n))
    eps = np.finfo(float).eps
    allowance = float(16 * eps * np.sum(np.abs(d * n))
                      + 2 * eps * np.sum((np.abs(p) + np.abs(o)) * np.abs(n)))
    if not math.isfinite(s) or not math.isfinite(allowance):
        raise FloatingPointError('nonfinite plane separation or coordinate uncertainty')
    return s, allowance


class PlaneSurface:
    kind, label, speed_label = 'plane', 'plane', 'normal'
    residual_key, speed_key = 'signed_plane_residual_m', 'normal_speed_m_s'
    limits = LIMITS

    def __init__(self, request):
        self.request = request
        self.direction = DIRECTIONS[request.direction]

    def separation(self, position):
        return separation(position, self.request.point_m, self.request.normal)

    def normal_speed(self, state):
        return float(np.dot(state[3:], self.request.normal))

    def condition(self):
        return dict(type='plane', point_m=list(self.request.point_m),
                    normal=list(self.request.normal), direction=self.request.direction)


def _search(scene, request, refined):
    return search(scene, request, refined, PlaneSurface(request), solve_ivp)


class PlaneEvents(SurfaceEvents):
    def surface(self, request):
        return PlaneSurface(request)

    def search(self, request, refined):
        return _search(self.scene, request, refined)
