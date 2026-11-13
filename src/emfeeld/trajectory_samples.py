"""Saved-sample selection and per-packet trajectory reuse; no graphics or events.

This module calls the existing integrator with the scene's existing settings. It
never interpolates or fits states, changes source physics, or detects crossings.
JSON request validation lives at the observations packet boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from .dynamics import integrate
from .fields import DomainError
from .scene import Scene

QUANTITIES = {
    'time': ('s', ()),
    'position': ('m', (3,)),
    'velocity': ('m/s', (3,)),
    'speed': ('m/s', ()),
    'kinetic_energy': ('J', ()),
    'potential_energy': ('J', ()),
    'total_energy': ('J', ()),
}
SOLVER_SETTINGS = {'rtol': 1e-10, 'position_atol_m': 1e-9, 'velocity_atol_m_s': 1e-9}


@dataclass(frozen=True)
class SampleRequest:
    particle_index: int
    quantity: str
    sample_index: int | None = None
    time_s: float | None = None
    time_selection: str | None = None
    max_time_error_s: float | None = None

    def selector(self) -> dict:
        if self.sample_index is not None:
            return {'sample_index': self.sample_index}
        selector = {'time_s': self.time_s, 'time_selection': self.time_selection}
        if self.max_time_error_s is not None:
            selector['max_time_error_s'] = self.max_time_error_s
        return selector


def _failure(status: str, code: str, message: str) -> dict:
    return {'status': status, 'value': None, 'error': {'code': code, 'message': message}}


class TrajectorySamples:
    """A fresh instance is used per packet; a referenced particle is solved once.

    Known solver failures are cached too. Unrequested particles are never solved.
    Input references/selectors must already have passed packet validation.
    """
    def __init__(self, scene: Scene):
        self.scene = scene
        self.runs: dict[str, dict[str, Any]] = {}
        self._cache: dict[int, tuple[Any, dict]] = {}
        self._grid_failure = None
        self.times = np.linspace(0., scene.duration_s, scene.samples)
        self.max_step_s = scene.duration_s / 200
        if (not np.isfinite(self.times).all() or np.any(np.diff(self.times) <= 0)
                or not math.isfinite(self.max_step_s) or self.max_step_s <= 0):
            self._grid_failure = _failure('numerical_error', 'unresolvable_time_grid',
                'Saved times or maximum step are not representable at this float64 scale.')

    def _select(self, request: SampleRequest) -> tuple[int | None, dict | None]:
        if request.sample_index is not None:
            return request.sample_index, None
        t = request.time_s
        right = int(np.searchsorted(self.times, t))
        if right < len(self.times) and self.times[right] == t:
            return right, None
        if request.time_selection == 'exact':
            return None, _failure('selection_error', 'time_not_saved',
                'Requested time is not exactly a saved float64 time. Use a sample_index '
                'or explicitly request nearest with max_time_error_s; no interpolation occurred.')
        candidates = [i for i in (right - 1, right) if 0 <= i < len(self.times)]
        # Candidate order and the secondary key make exact ties choose the earlier sample.
        index = min(candidates, key=lambda i: (abs(float(self.times[i]) - t), i))
        offset = float(self.times[index]) - t
        if abs(offset) > request.max_time_error_s:
            failure = _failure('selection_error', 'time_tolerance_exceeded',
                'Nearest saved sample exceeds the explicitly permitted time difference.')
            failure['error'].update(nearest_sample_index=index,
                                    nearest_time_s=float(self.times[index]), time_offset_s=offset)
            return None, failure
        return index, None

    def _trajectory(self, particle_index: int) -> tuple[Any, dict]:
        if particle_index in self._cache:
            return self._cache[particle_index]
        particle = self.scene.particles[particle_index]
        info = {'particle_index': particle_index,
                'particle_reference': f'scene.particles[{particle_index}]',
                'particle': {'mass_kg': particle.mass_kg, 'charge_C': particle.charge_C,
                    'position_m': list(particle.position_m), 'velocity_m_s': list(particle.velocity_m_s)},
                'integration_attempted': False, 'status': 'pending',
                'solver': {'method': 'DOP853', **SOLVER_SETTINGS, 'max_step_s': self.max_step_s},
                'diagnostic_meaning': 'energy drift is an observation, not a trajectory error bound; '
                                      'its normalization depends on the potential reference'}
        trajectory = None
        if not self.scene.model.trajectory_safe:
            info.update(_failure('unsupported_trajectory', 'trajectory_not_qualified',
                'Trajectories containing shell/plane sources remain unqualified; static probes are available.'))
        else:
            info['integration_attempted'] = True
            try:
                with np.errstate(over='raise', divide='raise', invalid='raise'):
                    trajectory = integrate(self.scene.model, particle, self.times,
                                           **SOLVER_SETTINGS, max_step_s=self.max_step_s)
                    self._check_trajectory(trajectory)
                    drift = float(trajectory.max_energy_drift_J)
                    normalized = float(trajectory.normalized_energy_drift)
                    if not math.isfinite(drift) or not math.isfinite(normalized):
                        raise FloatingPointError('trajectory energy diagnostics are nonfinite')
                    info.update(status='ok', samples=len(self.times), evaluations=trajectory.evaluations,
                                start_time_s=float(self.times[0]), end_time_s=float(self.times[-1]),
                                max_energy_drift_J=drift, normalized_energy_drift=normalized)
            except DomainError as exc:
                info.update(_failure('domain_error', 'undefined_or_unresolved_trajectory', str(exc)))
            except (FloatingPointError, OverflowError) as exc:
                info.update(_failure('numerical_error', 'nonfinite_or_invalid_trajectory', str(exc)))
            except RuntimeError as exc:
                # The existing solver predates typed solver exceptions. Only its
                # documented failure messages are converted; programming bugs propagate.
                text = str(exc)
                if text.startswith('trajectory integration failed:'):
                    info.update(_failure('integration_error', 'solver_failed', text))
                elif (text == 'trajectory integration produced nonfinite state values'
                      or text.startswith('trajectory energies are nonfinite;')):
                    info.update(_failure('numerical_error', 'nonfinite_or_invalid_trajectory', text))
                else:
                    raise
        if info['status'] != 'ok':
            trajectory = None  # Never return partial or suspect arrays as a saved trajectory.
        self.runs[str(particle_index)] = info
        self._cache[particle_index] = trajectory, info
        return trajectory, info

    def _check_trajectory(self, trajectory) -> None:
        sizes = {'time_s': (len(self.times),), 'position_m': (len(self.times), 3),
                 'velocity_m_s': (len(self.times), 3), 'kinetic_J': (len(self.times),),
                 'potential_J': (len(self.times),)}
        for name, shape in sizes.items():
            a = np.asarray(getattr(trajectory, name))
            if a.shape != shape or not np.isfinite(a).all():
                raise FloatingPointError(f'{name}: invalid saved array shape or nonfinite data')
        if not np.array_equal(trajectory.time_s, self.times):
            raise FloatingPointError('solver returned times different from the requested saved grid')
        if type(trajectory.evaluations) is not int or trajectory.evaluations < 0:
            raise FloatingPointError('invalid solver evaluation count')

    def observe(self, request: SampleRequest) -> dict:
        """Return one measurement, with actual saved time and explicit selection policy."""
        unit, shape = QUANTITIES[request.quantity]
        result = {'quantity': request.quantity, 'particle_index': request.particle_index,
                  'particle_reference': f'scene.particles[{request.particle_index}]',
                  'unit': unit, 'value': None, 'status': 'ok', 'error_bound': None,
                  'method': 'saved_trajectory_sample', 'selection': request.selector()}
        if self._grid_failure is not None:
            return dict(result, **self._grid_failure)
        index, failure = self._select(request)
        if failure is not None:
            return dict(result, **failure)
        trajectory, info = self._trajectory(request.particle_index)
        result['diagnostics_key'] = str(request.particle_index)
        if info['status'] != 'ok':
            return dict(result, status=info['status'], error=dict(info['error']))
        result.update(sample_index=index, time_s=float(trajectory.time_s[index]),
                      time_offset_s=None if request.sample_index is not None else
                                    float(trajectory.time_s[index]) - request.time_s)
        try:
            with np.errstate(over='raise', divide='raise', invalid='raise'):
                if request.quantity == 'time':
                    value = trajectory.time_s[index]
                elif request.quantity == 'speed':
                    value = np.hypot.reduce(trajectory.velocity_m_s[index])
                elif request.quantity == 'total_energy':
                    value = trajectory.kinetic_J[index] + trajectory.potential_J[index]
                else:
                    name = {'position':'position_m', 'velocity':'velocity_m_s',
                            'kinetic_energy':'kinetic_J', 'potential_energy':'potential_J'}[request.quantity]
                    value = getattr(trajectory, name)[index]
                a = np.asarray(value, dtype=float)
                if a.shape != shape or not np.isfinite(a).all():
                    raise FloatingPointError('nonfinite or invalid sample measurement')
                result['value'] = a.tolist()
        except (FloatingPointError, OverflowError) as exc:
            result.update(_failure('numerical_error', 'invalid_sample_measurement', str(exc)))
        return result
