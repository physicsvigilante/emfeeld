"""Versioned sampled energy balance for static prescribed-field trajectories.

No force evaluation, integration, reference shift, or automatic tolerance change.
The resolution estimate concerns stored float64 energies, not field/solver accuracy.
"""
from __future__ import annotations

import math
import numpy as np

ENERGY_DIAGNOSTIC_VERSION = 2
MEANING = (
    'Sampled (K-K0)+(U-U0), scaled by max(max(K), max(abs(U-U0))). '
    'Gauge-neutral in exact arithmetic; finite-precision resolution is separate. '
    'Not a trajectory error bound, independent verification, or event-completeness proof.'
)


def energy_balance(kinetic_J, potential_J) -> dict:
    """Return finite, JSON-safe energy diagnostics; do not apply a pass threshold.

    S = max(max_i K_i, max_i |U_i-U_0|), R = max_i |(K_i-K_0)+(U_i-U_0)|.
    S=0 means no resolved energy exchange, NOT automatic trajectory verification.
    Eight float64 ulps at the largest stored energy give a conservative resolution
    indicator, not a rigorous bound on evaluating the potential. It is not added
    to the residual tolerance. An unresolved ratio is None, never a false zero.
    """
    k = np.asarray(kinetic_J, dtype=float)
    u = np.asarray(potential_J, dtype=float)
    if k.ndim != 1 or len(k) < 2 or u.shape != k.shape:
        raise FloatingPointError('energy balance requires matching 1D saved arrays')
    if not np.isfinite(k).all() or not np.isfinite(u).all() or np.any(k < 0):
        raise FloatingPointError('energy balance requires finite energies and nonnegative kinetic energy')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        dk, du = k - k[0], u - u[0]
        residual = float(np.max(np.abs(dk + du)))
        scale = float(max(float(np.max(k)), float(np.max(np.abs(du)))))
        largest = float(max(float(np.max(k)), float(np.max(np.abs(u)))))
        resolution = float(8. * np.spacing(largest))
    if not all(math.isfinite(x) for x in (residual, scale, resolution)):
        raise FloatingPointError('energy balance is unresolved at this float64 magnitude')
    normalized = residual / scale if scale > 0 else 0.
    resolution_ratio = resolution / scale if scale > 0 else None
    if resolution_ratio is not None and not math.isfinite(resolution_ratio):
        resolution_ratio = None
    return dict(version=ENERGY_DIAGNOSTIC_VERSION, max_residual_J=residual,
                scale_J=scale, normalized_residual=normalized,
                resolution_J=resolution, resolution_ratio=resolution_ratio,
                zero_exchange=(scale == 0.), meaning=MEANING)


def check_energy_balance(trajectory, tolerance: float, *, stationary_zero_force=False) -> dict:
    """Apply unchanged authored dimensionless tolerance; never relax it for roundoff.

    Zero-scale acceptance requires an additional caller-established exact stationary
    zero-force condition. Otherwise it is unresolved, not a conservation success.
    """
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('energy tolerance must be a finite positive number')
    result = energy_balance(trajectory.kinetic_J, trajectory.potential_J)
    if result['zero_exchange']:
        stationary = (stationary_zero_force
                      and np.all(trajectory.velocity_m_s == 0)
                      and np.all(trajectory.position_m == trajectory.position_m[0]))
        status = 'stationary_zero_exchange' if stationary else 'unresolved_zero_scale'
        passed = bool(stationary)
    elif result['resolution_ratio'] is None or result['resolution_ratio'] > tolerance:
        status, passed = 'unresolved_precision', False
    elif result['normalized_residual'] > tolerance:
        status, passed = 'energy_residual_exceeded', False
    else:
        status, passed = 'within_tolerance', True
    return dict(result, tolerance=tolerance, absolute_tolerance_J=0.,
                status=status, passed=passed)
