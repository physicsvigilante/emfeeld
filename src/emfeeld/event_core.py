"""Shared native terminal-search, refinement, diagnostics and caching machinery.

Condition adapters supply measurement geometry and state-dependent predicates. No apparatus/source-specific dispatch,
physical forces, saved-frame search, or inference of mathematical completeness.
Plane and radial entry points retain their own solver/search bindings for testing.
"""
from __future__ import annotations
from copy import deepcopy
import math
import numpy as np
from .fields import DomainError
from .trajectory_samples import SOLVER_SETTINGS

UNITS = {'time_s': 's', 'position_m': 'm', 'velocity_m_s': 'm/s',
         'speed_m_s': 'm/s', 'kinetic_J': 'J', 'potential_J': 'J', 'total_energy_J': 'J'}
LIMITS = ('First detected transverse root only; multiple crossings within a solver step '
          'can be missed. Step refinement is not a proof of completeness. Tangencies '
          'are not qualified. No collision, source-surface crossing, or feedback is modeled.')


class EventIssue(Exception):
    """A known physical/numerical limitation, not an unexpected programming error."""
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


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


def search(scene, request, refined, surface, solve):
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

    state_dependent = getattr(surface, 'state_dependent', False)

    def event(_t, state):
        if hasattr(surface, 'event_value_at_time'):
            return surface.event_value_at_time(_t, state)
        return surface.event_value(state) if state_dependent else surface.separation(state[:3])[0]
    event.terminal = True
    event.direction = surface.direction
    try:
        solution = solve(rhs, (0., scene.duration_s), initial, method='DOP853',
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
        if state_dependent:
            record.update(surface.measurement(states[0], model, particle))
        else:
            distance, uncertainty = surface.separation(states[0][:3])
            speed = surface.normal_speed(states[0])
            if not math.isfinite(speed):
                raise FloatingPointError(f'nonfinite {surface.speed_label} speed')
            record.update({surface.residual_key: distance, 'coordinate_uncertainty_m': uncertainty,
                           surface.speed_key: speed})
    else:
        if solution.status != 0 or solution.t[-1] != scene.duration_s:
            raise FloatingPointError('search ended without an event or completed horizon')
        if state_dependent:
            record.update(surface.measurement(solution.y[:, -1], model, particle))
        else:
            distance, uncertainty = surface.separation(solution.y[:3, -1])
            record.update(endpoint_separation_m=distance, coordinate_uncertainty_m=uncertainty)
    return record


class SurfaceEvents:
    """Packet-local exact-request cache, separate from the saved-sample cache."""
    def __init__(self, scene):
        self.scene, self._cache = scene, {}

    def surface(self, request):
        """Return a condition adapter; it never modifies the physical model."""
        raise NotImplementedError

    def search(self, request, refined):
        raise NotImplementedError

    def observe(self, request) -> dict:
        key = request.key()
        if key not in self._cache:
            self._cache[key] = self._evaluate(request)
        return deepcopy(self._cache[key])

    def _evaluate(self, request):
        surface = self.surface(request)
        result = dict(status='ok', state=None, units=dict(UNITS), error_bound=None,
            method=f'native_DOP853_terminal_{surface.kind}_event_with_refinement',
            particle_index=request.particle_index,
            particle_reference=f'scene.particles[{request.particle_index}]',
            condition=surface.condition(),
            occurrence='first', search_interval_s=[0., self.scene.duration_s],
            diagnostics={'passes': [], 'integration_attempts': 0, 'detection_limits': surface.limits})
        state_dependent = getattr(surface, 'state_dependent', False)
        if state_dependent:
            result['units'].update(surface.extra_units)
        diag = result['diagnostics']
        particle, model = self.scene.particles[request.particle_index], self.scene.model
        try:
            with np.errstate(over='raise', divide='raise', invalid='raise'):
                if not model.trajectory_safe:
                    raise EventIssue('unsupported_trajectory', 'trajectory_not_qualified',
                                     f'Shell/plane source dynamics remain unqualified. An observation {surface.label} is not a source.')
                initial = np.array((*particle.position_m, *particle.velocity_m_s))
                initial_energy = _state(model, particle, 0., initial)
                if state_dependent:
                    surface.validate_initial(initial)
                else:
                    s, uncertainty = surface.separation(initial[:3])
                    if abs(s) <= uncertainty:
                        raise EventIssue('initial_condition_error', f'initial_on_or_unresolved_{surface.label}',
                            f'Launch is on the {surface.label} or its side is numerically unresolved; no later first crossing is defined here.')
                for refined in (False, True):
                    diag['integration_attempts'] += 1
                    diag['passes'].append(self.search(request, refined))
                a, b = diag['passes']
                if a['status'] != b['status']:
                    raise EventIssue('convergence_error', 'event_presence_disagrees',
                                     'Base and refined searches disagree on whether an event was detected.')
                if state_dependent:
                    surface.validate_passes(a, b)
                if a['status'] == 'no_event':
                    if not state_dependent and any(abs(p['endpoint_separation_m']) <= request.position_atol_m
                           + p['coordinate_uncertainty_m'] for p in (a, b)):
                        raise EventIssue('ambiguous_event', f'endpoint_near_{surface.label}',
                                         f'No detected root, but the horizon ends near the {surface.label} within the requested tolerance.')
                    result['status'] = 'no_event'
                    diag['refinement'] = dict(passed=True, meaning='No root detected at either step cap; not an absence proof.')
                    return result
                for p in (() if state_dependent else (a, b)):
                    if p['coordinate_uncertainty_m'] > request.position_atol_m:
                        raise EventIssue('ambiguous_event', f'{surface.label}_resolution_insufficient',
                                         f'Coordinate roundoff alone exceeds the requested absolute {surface.label} resolution.')
                    if abs(p[surface.residual_key]) > request.position_atol_m:
                        raise EventIssue('convergence_error', f'{surface.label}_residual_exceeded',
                                         f'Located root does not meet the requested absolute {surface.label} residual tolerance.')
                    speed = p[surface.speed_key]
                    if (abs(speed) <= request.min_crossing_speed_m_s or
                            surface.direction * speed < 0):
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
                if state_dependent:
                    surface.finish(result, final, b)
                else:
                    diag.update({surface.speed_key: b[surface.speed_key],
                                 surface.residual_key: b[surface.residual_key]})
                    result['state'] = dict(final)
                diag.update(energy_change_J=drift, normalized_energy_change=abs(drift)/scale,
                            energy_diagnostic_meaning='Initial-to-event difference only; potential-reference dependent, not an error bound.')
        except EventIssue as exc:
            result.update(status=exc.status, state=None, error=dict(code=exc.code,message=str(exc)))
        except DomainError as exc:
            result.update(status='domain_error', state=None,
                          error=dict(code='undefined_or_unresolved_trajectory',message=str(exc)))
        except (FloatingPointError, OverflowError) as exc:
            result.update(status='numerical_error', state=None,
                          error=dict(code='nonfinite_or_invalid_event',message=str(exc)))
        return result
