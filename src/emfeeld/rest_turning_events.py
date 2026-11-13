"""Opt-in later radial extrema from an exactly stationary initial state.

Remove the launch root algebraically, not by perturbing the state, skipping time,
or adding a warm-up solve. The default turning-event adapter remains unchanged.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .event_core import EventIssue, SurfaceEvents, search
from .turning_events import TurningCondition, TurningRequest

POLICY = 'exclude_rest_launch'
LIMITS = (
    'First detected positive-time nondegenerate local radial extremum from exact rest; '
    'not global closest approach or minimum launch speed. Only the t=0 root is excluded '
    'algebraically; initial state and integration interval are unchanged. A defined-field '
    'passage through the observation centre can precede a later maximum, but a detected '
    'centre root is not a smooth extremum and is rejected. Multiple roots per step may '
    'be missed; two-pass agreement is not completeness and no_event is not absence proof. '
    'Zero/unresolved initial radial acceleration, nonzero initial velocity, and source '
    'singularities remain unsupported. No physical force clipping or feedback.')


@dataclass(frozen=True)
class RestTurningRequest(TurningRequest):
    initial_policy: str = POLICY


class RestTurningCondition(TurningCondition):
    """Time-dependent root with a removable zero at launch along the trajectory."""
    kind, label = 'radial_turning_from_rest', 'rest_launch_turning_condition'
    limits = LIMITS

    def __init__(self, request, model, particle):
        super().__init__(request)
        self.model, self.particle = model, particle
        self.launch = None

    def validate_initial(self, state):
        y = np.asarray(state, dtype=float)
        if y.shape != (6,) or not np.isfinite(y).all():
            raise FloatingPointError('invalid exact-rest initial state')
        # "Rest" is an authored exact condition, not a velocity tolerance.
        if np.any(y[3:] != 0.):
            raise EventIssue('initial_condition_error', 'exact_rest_required',
                             'exclude_rest_launch requires every initial velocity component to equal zero; no near-rest coercion is applied.')
        try:
            record = self.measurement(y, self.model, self.particle)
        except EventIssue as exc:
            raise EventIssue('initial_condition_error', exc.code, str(exc)) from exc
        if record['coordinate_uncertainty_m'] > self.request.position_atol_m:
            raise EventIssue('initial_condition_error', 'rest_launch_geometry_unresolved',
                             'Initial coordinate uncertainty exceeds the requested absolute position resolution.')
        ar = record['radial_acceleration_m_s2']
        if abs(ar) <= (self.request.min_radial_acceleration_m_s2
                       + record['radial_acceleration_roundoff_m_s2']):
            raise EventIssue('initial_condition_error', 'rest_departure_unresolved',
                             'Initial radial acceleration is zero, too small, or unresolved; a simple departing rest root is not established.')
        self.launch = dict(time_s=0., position_m=y[:3].tolist(), velocity_m_s=y[3:].tolist(),
            distance_m=record['distance_m'], radial_acceleration_m_s2=ar,
            radial_acceleration_roundoff_m_s2=record['radial_acceleration_roundoff_m_s2'],
            initial_root_excluded=True, skipped_time_s=0., state_perturbed=False,
            predicate='dot(position-center,velocity)/(initial_distance*time) for time>0; initial_radial_acceleration at time=0')

    def event_value_at_time(self, time, state):
        if self.launch is None:
            raise RuntimeError('rest launch must be validated before event evaluation')
        if not math.isfinite(time) or time < 0:
            raise FloatingPointError('invalid time in rest-launch event')
        y = np.asarray(state, dtype=float)
        if y.shape != (6,) or not np.isfinite(y).all():
            raise FloatingPointError('invalid state in rest-launch event')
        if time == 0.:
            return self.launch['radial_acceleration_m_s2']
        # On the true trajectory d.v = r0*ar0*t + O(t^2). Its positive-time
        # roots/directions are those of radial velocity for r>0. Unlike d/r,
        # this numerator is defined at a measurement centre with a smooth field.
        scaled_d = (y[:3] - self.request.center_m) / self.launch['distance_m']
        value = float(np.dot(scaled_d, y[3:]) / time)
        if not math.isfinite(value):
            raise FloatingPointError('nonfinite launch-deflated event value')
        return value

    def validate_passes(self, a, b):
        super().validate_passes(a, b)
        if a['status'] == 'event' and any(
                p['state']['time_s'] <= self.request.time_atol_s for p in (a, b)):
            raise EventIssue('ambiguous_event', 'event_time_unresolved_from_launch',
                             'Detected positive-time root is within the authored absolute time resolution of launch; no later isolated event certified.')

    def finish(self, result, final, record):
        super().finish(result, final, record)
        result['diagnostics']['launch_exclusion'] = dict(record['launch_exclusion'])


def _search(scene, request, refined):
    particle = scene.particles[request.particle_index]
    condition = RestTurningCondition(request, scene.model, particle)
    initial = np.array((*particle.position_m, *particle.velocity_m_s))
    condition.validate_initial(initial)
    record = search(scene, request, refined, condition, solve_ivp)
    record['launch_exclusion'] = dict(condition.launch)
    return record


class RestTurningEvents(SurfaceEvents):
    """Separate packet-local cache; exact duplicate requests share both searches."""
    def surface(self, request):
        return RestTurningCondition(request, self.scene.model,
                                    self.scene.particles[request.particle_index])

    def search(self, request, refined):
        return _search(self.scene, request, refined)

    def _evaluate(self, request):
        result = super()._evaluate(request)
        result['initial_policy'] = POLICY
        return result
