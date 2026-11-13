"""Bounded, transverse plane-crossing observations using native DOP853 events.

This optional adapter leaves dynamics.integrate and saved trajectories unchanged.
It uses the same qE/m or g equation, with a terminal event and a separate refined
run. Two agreeing searches are numerical evidence, NOT a completeness proof.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .fields import DomainError
from .trajectory_samples import SOLVER_SETTINGS

DIRECTIONS = {'positive': 1, 'negative': -1, 'either': 0}
UNITS = {'time_s': 's', 'position_m': 'm', 'velocity_m_s': 'm/s',
         'speed_m_s': 'm/s', 'kinetic_J': 'J', 'potential_J': 'J', 'total_energy_J': 'J'}
LIMITS = ('First detected transverse root only; multiple crossings within a solver step '
          'can be missed. Step refinement is not a proof of completeness. Tangencies '
          'are not qualified. No collision, source-surface crossing, or feedback is modeled.')


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

    def key(self):
        # Exact validated geometry/settings; ids do not change the calculation.
        return tuple(v for k, v in vars(self).items() if k not in ('id', 'type'))


class EventIssue(Exception):
    """A known physical/numerical limitation, not an unexpected programming error."""
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


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


def _state(model, particle, time, state):
    y = np.asarray(state, dtype=float)
    if y.shape != (6,) or not np.isfinite(y).all() or not math.isfinite(time):
        raise FloatingPointError('invalid event state or time')
    coupling = particle.charge_C if model.kind == 'electric' else particle.mass_kg
    kinetic = float(0.5 * particle.mass_kg * np.dot(y[3:], y[3:]))
    potential_value = np.asarray(model.potential(y[:3]))
    if potential_value.shape != ():
        raise FloatingPointError('potential must be scalar at event position')
    potential = float(coupling * potential_value)
    speed = float(np.hypot.reduce(y[3:]))
    if not all(math.isfinite(v) for v in (kinetic, potential, kinetic + potential, speed)):
        raise FloatingPointError('nonfinite event energy or speed')
    return dict(time_s=float(time), position_m=y[:3].tolist(), velocity_m_s=y[3:].tolist(),
                speed_m_s=speed, kinetic_J=kinetic, potential_J=potential,
                total_energy_J=kinetic + potential)


def _search(scene, request, refined):
    model, particle = scene.model, scene.particles[request.particle_index]
    initial = np.array((*particle.position_m, *particle.velocity_m_s))
    scale = 0.1 if refined else 1.0
    settings = {k: v * scale for k, v in SOLVER_SETTINGS.items()}
    cap = request.max_step_s / (2 if refined else 1)
    factor = particle.charge_C / particle.mass_kg if model.kind == 'electric' else 1.0
    calls = 0

    def rhs(_t, state):
        nonlocal calls
        calls += 1
        if calls > 500000:
            raise EventIssue('integration_error', 'evaluation_budget_exceeded',
                             'Event search exceeded 500000 field evaluations; no result certified.')
        field = np.asarray(model.field(state[:3]), dtype=float)
        if field.shape != (3,) or not np.isfinite(field).all():
            raise FloatingPointError('invalid field during event integration')
        return np.concatenate((state[3:], factor * field))

    def event(_t, state):
        return separation(state[:3], request.point_m, request.normal)[0]
    event.terminal = True
    event.direction = DIRECTIONS[request.direction]
    try:
        solution = solve_ivp(rhs, (0., scene.duration_s), initial, method='DOP853',
            rtol=settings['rtol'], atol=[settings['position_atol_m']] * 3
            + [settings['velocity_atol_m_s']] * 3, max_step=cap, events=event)
    except (ValueError, RuntimeError) as exc:
        # Only known root-finder failures are observations; programming errors propagate.
        if (str(exc) == 'f(a) and f(b) must have different signs' or
                str(exc).startswith('Failed to converge after ')):
            raise EventIssue('numerical_error', 'event_root_failure', str(exc)) from exc
        raise
    if not solution.success:
        raise EventIssue('integration_error', 'solver_failed', str(solution.message))
    if (np.ndim(solution.y) != 2 or solution.y.shape[0] != 6 or len(solution.t) == 0
            or solution.y.shape[1] != len(solution.t) or not np.isfinite(solution.y).all()
            or not np.isfinite(solution.t).all()):
        raise FloatingPointError('invalid native solver output')
    times, states = solution.t_events[0], solution.y_events[0]
    if len(times) > 1 or (len(times) and np.shape(states) != (1, 6)):
        raise FloatingPointError('invalid terminal-event output')
    record = dict(status='event' if len(times) else 'no_event', method='DOP853',
                  max_step_s=cap, **settings, evaluations=int(solution.nfev),
                  accepted_steps=len(solution.t)-1, end_time_s=float(solution.t[-1]))
    if len(times):
        t = float(times[0])
        if not 0 < t <= scene.duration_s:
            raise EventIssue('ambiguous_event', 'event_at_time_boundary',
                             'Event is not strictly after launch within the declared interval.')
        record['state'] = _state(model, particle, t, states[0])
        distance, uncertainty = separation(states[0][:3], request.point_m, request.normal)
        speed = float(np.dot(states[0][3:], request.normal))
        if not math.isfinite(speed):
            raise FloatingPointError('nonfinite normal speed')
        record.update(signed_plane_residual_m=distance, coordinate_uncertainty_m=uncertainty,
                      normal_speed_m_s=speed)
    else:
        if solution.status != 0 or solution.t[-1] != scene.duration_s:
            raise FloatingPointError('search ended without an event or completed horizon')
        distance, uncertainty = separation(solution.y[:3, -1], request.point_m, request.normal)
        record.update(endpoint_separation_m=distance, coordinate_uncertainty_m=uncertainty)
    return record


class PlaneEvents:
    """Packet-local exact-request cache, separate from the saved-sample cache."""
    def __init__(self, scene):
        self.scene, self._cache = scene, {}

    def observe(self, request: PlaneRequest) -> dict:
        key = request.key()
        if key not in self._cache:
            self._cache[key] = self._evaluate(request)
        return deepcopy(self._cache[key])

    def _evaluate(self, request):
        result = dict(status='ok', state=None, units=dict(UNITS), error_bound=None,
            method='native_DOP853_terminal_plane_event_with_refinement',
            particle_index=request.particle_index,
            particle_reference=f'scene.particles[{request.particle_index}]',
            condition=dict(type='plane', point_m=list(request.point_m),
                           normal=list(request.normal), direction=request.direction),
            occurrence='first', search_interval_s=[0., self.scene.duration_s],
            diagnostics={'passes': [], 'integration_attempts': 0, 'detection_limits': LIMITS})
        diag = result['diagnostics']
        particle, model = self.scene.particles[request.particle_index], self.scene.model
        try:
            with np.errstate(over='raise', divide='raise', invalid='raise'):
                if not model.trajectory_safe:
                    raise EventIssue('unsupported_trajectory', 'trajectory_not_qualified',
                                     'Shell/plane source dynamics remain unqualified. An observation plane is not a source.')
                initial = np.array((*particle.position_m, *particle.velocity_m_s))
                initial_energy = _state(model, particle, 0., initial)
                s, uncertainty = separation(initial[:3], request.point_m, request.normal)
                if abs(s) <= uncertainty:
                    raise EventIssue('initial_condition_error', 'initial_on_or_unresolved_plane',
                        'Launch is on the plane or its side is numerically unresolved; no later first crossing is defined here.')
                for refined in (False, True):
                    diag['integration_attempts'] += 1
                    diag['passes'].append(_search(self.scene, request, refined))
                a, b = diag['passes']
                if a['status'] != b['status']:
                    raise EventIssue('convergence_error', 'event_presence_disagrees',
                                     'Base and refined searches disagree on whether an event was detected.')
                if a['status'] == 'no_event':
                    if any(abs(p['endpoint_separation_m']) <= request.position_atol_m
                           + p['coordinate_uncertainty_m'] for p in (a, b)):
                        raise EventIssue('ambiguous_event', 'endpoint_near_plane',
                                         'No detected root, but the horizon ends near the plane within the requested tolerance.')
                    result['status'] = 'no_event'
                    diag['refinement'] = dict(passed=True, meaning='No root detected at either step cap; not an absence proof.')
                    return result
                for p in (a, b):
                    if p['coordinate_uncertainty_m'] > request.position_atol_m:
                        raise EventIssue('ambiguous_event', 'plane_resolution_insufficient',
                                         'Coordinate roundoff alone exceeds the requested absolute plane resolution.')
                    if abs(p['signed_plane_residual_m']) > request.position_atol_m:
                        raise EventIssue('convergence_error', 'plane_residual_exceeded',
                                         'Located root does not meet the requested absolute plane residual tolerance.')
                    speed = p['normal_speed_m_s']
                    if (abs(speed) <= request.min_normal_speed_m_s or
                            DIRECTIONS[request.direction] * speed < 0):
                        raise EventIssue('ambiguous_event', 'nontransverse_or_wrong_direction',
                                         'Detected root is too slow/grazing or has the wrong velocity direction.')
                differences, passed = {}, True
                for name, atol in [('time_s', request.time_atol_s),
                                   ('position_m', request.position_atol_m),
                                   ('velocity_m_s', request.velocity_atol_m_s)]:
                    x, y = np.asarray(a['state'][name]), np.asarray(b['state'][name])
                    difference = np.abs(x-y)
                    limit = atol + request.rtol * np.maximum(np.abs(x),np.abs(y))
                    differences[name] = difference.tolist()
                    passed = passed and bool(np.all(difference <= limit))
                diag['refinement'] = dict(passed=passed, absolute_differences=differences,
                    tolerances=dict(time_atol_s=request.time_atol_s, position_atol_m=request.position_atol_m,
                                    velocity_atol_m_s=request.velocity_atol_m_s, rtol=request.rtol),
                    meaning='Agreement of two runs, not a certified error bound or first-root completeness proof.')
                if not passed:
                    raise EventIssue('convergence_error', 'refinement_tolerance_exceeded',
                                     'Event time or state changed beyond authored comparison tolerances.')
                final = b['state']
                drift = final['total_energy_J'] - initial_energy['total_energy_J']
                scale = max(abs(initial_energy['total_energy_J']),initial_energy['kinetic_J'],
                            abs(initial_energy['potential_J']),np.finfo(float).tiny)
                if not math.isfinite(drift/scale):
                    raise FloatingPointError('nonfinite energy diagnostic')
                diag.update(normal_speed_m_s=b['normal_speed_m_s'],
                            signed_plane_residual_m=b['signed_plane_residual_m'],
                            energy_change_J=drift, normalized_energy_change=abs(drift)/scale,
                            energy_diagnostic_meaning='Initial-to-event difference only; potential-reference dependent, not an error bound.')
                result['state'] = dict(final)
        except EventIssue as exc:
            result.update(status=exc.status, state=None, error=dict(code=exc.code,message=str(exc)))
        except DomainError as exc:
            result.update(status='domain_error', state=None,
                          error=dict(code='undefined_or_unresolved_trajectory',message=str(exc)))
        except (FloatingPointError, OverflowError) as exc:
            result.update(status='numerical_error', state=None,
                          error=dict(code='nonfinite_or_invalid_event',message=str(exc)))
        return result
