"""First detected nondegenerate radial extremum about a fixed authored centre.

The root is radial velocity, not total speed. This observes a local minimum or
maximum; it does not find a global minimum, a collision, or a minimum launch speed.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .event_core import EventIssue, SurfaceEvents, search
from .radial_events import separation

EXTREMA = {'minimum': 1, 'maximum': -1, 'either': 0}
LIMITS = ('First detected nondegenerate radial-velocity root only, not global closest approach. '
          'Multiple roots within a step may be missed; refinement is not a completeness proof. '
          'Initial stationarity, circular motion, degenerate extrema and centre passage are '
          'unqualified. Minimum-distance/acceleration thresholds reject measurements; they '
          'do not soften fields or define collisions. No source feedback.')


@dataclass(frozen=True)
class TurningRequest:
    id: str
    particle_index: int
    center_m: tuple[float, ...]
    extremum: str
    max_step_s: float
    min_distance_m: float
    min_radial_acceleration_m_s2: float
    time_atol_s: float
    position_atol_m: float
    velocity_atol_m_s: float
    radial_speed_atol_m_s: float
    rtol: float
    type: str = 'trajectory_event'

    def key(self):
        return tuple(v for k, v in vars(self).items() if k not in ('id', 'type'))


class TurningCondition:
    """State-predicate adapter for the shared terminal-search/refinement core."""
    state_dependent = True
    kind, label = 'radial_turning', 'radial_turning_condition'
    limits = LIMITS
    extra_units = {'distance_m':'m', 'radial_speed_m_s':'m/s',
                   'radial_acceleration_m_s2':'m/s^2'}

    def __init__(self, request):
        self.request = request
        self.direction = EXTREMA[request.extremum]

    def condition(self):
        return dict(type='radial_turning', center_m=list(self.request.center_m),
                    extremum=self.request.extremum)

    def kinematics(self, state):
        y = np.asarray(state, dtype=float)
        if y.shape != (6,) or not np.isfinite(y).all():
            raise FloatingPointError('invalid state in radial-turning predicate')
        r, dr = separation(y[:3], self.request.center_m, 0.)
        if r <= self.request.min_distance_m + dr:
            raise EventIssue('ambiguous_event', 'turning_center_unresolved',
                             'Distance is within the authored minimum or coordinate uncertainty; smooth radial turning is undefined here.')
        n = (y[:3] - self.request.center_m) / r
        speed = float(np.hypot.reduce(y[3:]))
        vr = float(np.dot(n, y[3:]))
        # Conservative arithmetic/direction allowance, not a trajectory error bound.
        dn = 2 * dr / (r - dr)
        dvr = 16 * np.finfo(float).eps * float(np.sum(np.abs(n*y[3:]))) + dn * speed
        if not all(math.isfinite(x) for x in (speed, vr, dn, dvr)):
            raise FloatingPointError('nonfinite turning kinematics')
        return r, dr, n, speed, vr, dn, dvr

    def event_value(self, state):
        return self.kinematics(state)[4]

    def validate_initial(self, state):
        try:
            *_, vr, _dn, dvr = self.kinematics(state)
        except EventIssue as exc:
            raise EventIssue('initial_condition_error', exc.code, str(exc)) from exc
        if abs(vr) <= self.request.radial_speed_atol_m_s + dvr:
            raise EventIssue('initial_condition_error', 'initial_radial_stationarity',
                             'Launch radial velocity is zero or unresolved at the requested tolerance; this contract does not skip an initial turning point.')

    def measurement(self, state, model, particle):
        r, dr, n, speed, vr, dn, dvr = self.kinematics(state)
        field = np.asarray(model.field(state[:3]), dtype=float)
        if field.shape != (3,) or not np.isfinite(field).all():
            raise FloatingPointError('invalid field in turning classification')
        factor = particle.charge_C / particle.mass_kg if model.kind == 'electric' else 1.
        acceleration = factor * field
        vt = np.asarray(state[3:]) - vr*n
        curvature = float(np.dot(vt, vt) / r)
        ar = float(np.dot(n, acceleration) + curvature)
        scale = speed*speed/r
        dar = (64*np.finfo(float).eps*(float(np.sum(np.abs(n*acceleration)))+scale)
               + dn*(float(np.hypot.reduce(acceleration))+8*scale) + 8*dr/r*scale)
        if not math.isfinite(ar) or not math.isfinite(dar):
            raise FloatingPointError('nonfinite radial acceleration or roundoff allowance')
        return dict(distance_m=r, coordinate_uncertainty_m=dr, radial_speed_m_s=vr,
                    radial_speed_roundoff_m_s=dvr, radial_acceleration_m_s2=ar,
                    radial_acceleration_roundoff_m_s2=dar,
                    extremum='minimum' if ar > 0 else 'maximum' if ar < 0 else 'degenerate')

    def validate_passes(self, a, b):
        req = self.request
        if a['status'] == 'no_event':
            if any(abs(p['radial_speed_m_s']) <= req.radial_speed_atol_m_s
                   + p['radial_speed_roundoff_m_s'] for p in (a,b)):
                raise EventIssue('ambiguous_event', 'endpoint_near_radial_stationarity',
                                 'No root detected, but horizon radial velocity is unresolved at the requested tolerance.')
            return
        for p in (a,b):
            if (p['coordinate_uncertainty_m'] > req.position_atol_m or
                    p['radial_speed_roundoff_m_s'] > req.radial_speed_atol_m_s):
                raise EventIssue('ambiguous_event', 'turning_resolution_insufficient',
                                 'Coordinate/direction roundoff exceeds requested turning resolution.')
            if abs(p['radial_speed_m_s']) > req.radial_speed_atol_m_s:
                raise EventIssue('convergence_error', 'radial_speed_residual_exceeded',
                                 'Located root has excessive residual radial speed.')
            ar = p['radial_acceleration_m_s2']
            if abs(ar) <= req.min_radial_acceleration_m_s2 + p['radial_acceleration_roundoff_m_s2']:
                raise EventIssue('ambiguous_event', 'degenerate_or_unresolved_turning',
                                 'Radial acceleration is too small or numerically unresolved for a simple extremum.')
            if self.direction*ar < 0:
                raise EventIssue('ambiguous_event', 'turning_direction_inconsistent',
                                 'Derivative sign does not match the requested minimum/maximum.')
        if a['extremum'] != b['extremum']:
            raise EventIssue('convergence_error', 'turning_classification_disagrees',
                             'Base and refined searches disagree on minimum versus maximum.')

    def finish(self, result, final, record):
        result['extremum'] = record['extremum']
        result['state'] = {**final, **{k:record[k] for k in self.extra_units}}
        result['diagnostics'].update({k:record[k] for k in
            (*self.extra_units, 'coordinate_uncertainty_m', 'radial_speed_roundoff_m_s',
             'radial_acceleration_roundoff_m_s2')})
        result['diagnostics']['classification'] = (
            'Sign of d(radial_speed)/dt = n dot acceleration + tangential_speed^2/distance; '
            'nonzero within authored threshold and arithmetic allowance. Local only.')


def _search(scene, request, refined):
    return search(scene, request, refined, TurningCondition(request), solve_ivp)


class TurningEvents(SurfaceEvents):
    def surface(self, request):
        return TurningCondition(request)

    def search(self, request, refined):
        return _search(self.scene, request, refined)
