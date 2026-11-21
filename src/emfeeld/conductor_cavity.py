"""Bounded, static spherical-conductor lesson; NOT a general conductor source.

One held point charge, concentric spherical cavity/outer boundary, vacuum and no
external sources. Image charges are an analytic device in the cavity only.
Display curves are field-line traces, never particle trajectories.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from .numeric_tokens import finite_float
import math
from pathlib import Path

import numpy as np
from scipy.constants import epsilon_0

from .fields import DomainError

K = 1.0 / (4 * math.pi * epsilon_0)
MAX_OFFSET = 0.9  # explicit V1 display/model admission, not a changed field law
KEYS = {'lesson_version', 'inner_radius_m', 'outer_radius_m', 'charge_C',
        'charge_position_m', 'mode', 'conductor_charge_C'}


def _number(value, name):
    if type(value) not in (int, float):
        raise ValueError(f'{name} must be a finite JSON number')
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{name} must be finite float64') from exc
    if not math.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def _vectors(value, name):
    try:
        if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, dtype=object).flat):
            raise ValueError(f'{name} must not contain booleans')
        raw = np.asarray(value)
        if raw.dtype.kind not in 'fiu' or raw.ndim < 1 or raw.shape[-1] != 3:
            raise ValueError(f'{name} must contain finite real three-vectors')
        arr = np.asarray(raw, dtype=float)
    except (OverflowError, TypeError) as exc:
        raise ValueError(f'{name} must contain finite real three-vectors') from exc
    if not np.isfinite(arr).all():
        raise ValueError(f'{name} must contain finite real three-vectors')
    return arr


def _norm(v):
    return np.hypot.reduce(v, axis=-1)


@dataclass(frozen=True)
class ConductorCavity:
    inner_radius_m: float = 1.0
    outer_radius_m: float = 1.25
    charge_C: float = 1e-9
    charge_position_m: tuple = (0.5, 0.0, 0.0)
    mode: str = 'isolated'
    conductor_charge_C: float = 0.0

    def __post_init__(self):
        for name in ('inner_radius_m', 'outer_radius_m', 'charge_C', 'conductor_charge_C'):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        r, b = self.inner_radius_m, self.outer_radius_m
        if not 1e-6 <= r <= 1e3 or not 1.01 <= b / r <= 5:
            raise ValueError('V1 requires 1e-6 <= R <= 1e3 m and 1.01 <= B/R <= 5')
        for q in (self.charge_C, self.conductor_charge_C):
            if q and not 1e-18 <= abs(q) <= 1e-3:
                raise ValueError('V1 nonzero charges must be between 1e-18 and 1e-3 C in magnitude')
        a = _vectors(self.charge_position_m, 'charge_position_m')
        if a.shape != (3,) or float(_norm(a / r)) > MAX_OFFSET:
            raise ValueError('V1 requires a single charge with |position|/R <= 0.9')
        object.__setattr__(self, 'charge_position_m', tuple(float(x) for x in a))
        if type(self.mode) is not str or self.mode not in ('isolated', 'grounded'):
            raise ValueError('mode must be isolated or grounded')
        if self.mode == 'grounded' and self.conductor_charge_C != 0:
            raise ValueError('grounded mode cannot also prescribe conductor net charge Q')

    @property
    def outer_charge_C(self):
        return self.conductor_charge_C + self.charge_C if self.mode == 'isolated' else 0.0

    @property
    def conductor_potential_V(self):
        return K * self.outer_charge_C / self.outer_radius_m

    def to_dict(self):
        return dict(lesson_version=1, inner_radius_m=self.inner_radius_m,
                    outer_radius_m=self.outer_radius_m, charge_C=self.charge_C,
                    charge_position_m=list(self.charge_position_m), mode=self.mode,
                    conductor_charge_C=self.conductor_charge_C)

    def _points(self, points):
        y = _vectors(points, 'points') / self.inner_radius_m
        if np.any(np.abs(y) > 1e6):
            raise ValueError('V1 probes are limited to |coordinate| <= 1e6 R')
        return y

    def _cavity_terms(self, y):
        """Dimensionless image solution, stable also at a=0 (image at infinity).

        D = |t*y - a_hat|. Potential = kq/R (1/|y-v| - 1/D).
        No image with huge strength/position is constructed for small t.
        """
        v = np.asarray(self.charge_position_m) / self.inner_radius_m
        t = float(_norm(v))
        displacement = y - v
        s = _norm(displacement)
        if self.charge_C and np.any(s <= 128 * np.finfo(float).eps):
            raise DomainError('point-charge location is singular or numerically unresolved')
        axis = v / t if t else np.array([1.0, 0.0, 0.0])
        image_distance = _norm(t * y - axis)
        return displacement, s, image_distance, v, t

    def _cavity_shape_field(self, y):
        d, s, h, v, t = self._cavity_terms(y)
        return d / s[..., None] ** 3 + (v - t*t*y) / h[..., None] ** 3

    def field(self, points):
        """Piecewise physical E in N/C; no single value at a charged surface."""
        y = self._points(points)
        shape = y.shape
        y = y.reshape(-1, 3)
        r = _norm(y)
        b = self.outer_radius_m / self.inner_radius_m
        eps = 64 * np.finfo(float).eps * np.maximum(1.0, r)
        if ((self.charge_C and np.any(np.abs(r-1) <= eps)) or
                (self.outer_charge_C and np.any(np.abs(r-b) <= eps))):
            raise DomainError('charged conductor surface has distinct one-sided fields')
        result = np.zeros_like(y)
        inner, outer = r < 1, r > b
        if self.charge_C and np.any(inner):
            result[inner] = (K * self.charge_C / self.inner_radius_m**2
                             * self._cavity_shape_field(y[inner]))
        if self.outer_charge_C and np.any(outer):
            result[outer] = (K * self.outer_charge_C / self.inner_radius_m**2
                             * (y[outer] / r[outer, None]**3))
        if not np.isfinite(result).all():
            raise FloatingPointError('nonfinite conductor-cavity field')
        return result.reshape(shape)

    def potential(self, points):
        """Physical V, zero at infinity; continuous at both conductor surfaces."""
        y = self._points(points)
        shape = y.shape[:-1]
        y = y.reshape(-1, 3)
        r = _norm(y)
        b = self.outer_radius_m / self.inner_radius_m
        result = np.full(len(y), self.conductor_potential_V)
        inner, outer = r < 1, r > b
        if self.charge_C and np.any(inner):
            _, s, h, _, _ = self._cavity_terms(y[inner])
            result[inner] += K * self.charge_C / self.inner_radius_m * (1/s - 1/h)
        if np.any(outer):
            result[outer] = K * self.outer_charge_C / (self.inner_radius_m * r[outer])
        if not np.isfinite(result).all():
            raise FloatingPointError('nonfinite conductor-cavity potential')
        return result.reshape(shape)

    def inner_density(self, directions):
        """Actual inner surface density in C/m^2, on unit radial directions."""
        n = _vectors(directions, 'directions')
        if not np.all(np.abs(_norm(n)-1) <= 2e-12):
            raise ValueError('surface directions must be unit vectors')
        v = np.asarray(self.charge_position_m) / self.inner_radius_m
        t = float(_norm(v))
        return (-self.charge_C / (4*math.pi*self.inner_radius_m**2)
                * (1-t*t) / _norm(n-v)**3)

    @property
    def outer_density_C_m2(self):
        return self.outer_charge_C / (4*math.pi*self.outer_radius_m**2)

    def summary(self):
        return {
            'model': 'one held point charge in a concentric spherical conductor; no exterior charges',
            'mode': self.mode, 'inner_total_C': -self.charge_C,
            'outer_total_C': self.outer_charge_C,
            'conductor_total_C': self.outer_charge_C - self.charge_C,
            'conductor_potential_V': self.conductor_potential_V,
            'metal_field_N_C': [0.0, 0.0, 0.0],
            'cavity_field_generally_nonzero': bool(self.charge_C),
            'equilibria_not_charge_motion': True,
            'image_charge_is_mathematical_only': True,
            'full_physical_shell_despite_display_cutaway': True,
        }


def from_dict(data):
    if type(data) is not dict or set(data) != KEYS:
        raise ValueError('lesson must be an object with exactly the V1 lesson keys')
    if type(data['lesson_version']) is not int or data['lesson_version'] != 1:
        raise ValueError('lesson_version must be integer 1')
    return ConductorCavity(**{k: v for k, v in data.items() if k != 'lesson_version'})


def load_lesson(path):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise ValueError(f'duplicate key: {k}')
            d[k] = v
        return d
    raw = Path(path).read_bytes()
    if len(raw) > 65536:
        raise ValueError('lesson input exceeds 64 KiB')
    return from_dict(json.loads(raw.decode('utf-8'), parse_float=finite_float, object_pairs_hook=pairs))


def spherical_quadrature(model, order=32):
    """Unrenormalized numerical surface integral, separate from exact -q."""
    if type(order) is not int or not 4 <= order <= 256:
        raise ValueError('quadrature order must be an integer in [4,256]')
    mu, w = np.polynomial.legendre.leggauss(order)
    phi = (np.arange(2*order)+0.5) * math.pi/order
    radial = np.sqrt(1-mu*mu)
    # Align the polar quadrature axis to the charge displacement. This resolves
    # the sharply varying nearest-wall cap without renormalizing sampled charge.
    axis = np.asarray(model.charge_position_m) / model.inner_radius_m
    length = float(_norm(axis))
    ez = axis / length if length else np.array([0.0, 0.0, 1.0])
    ref = np.eye(3)[int(np.argmin(np.abs(ez)))]
    ex = np.cross(ez, ref); ex /= float(_norm(ex))
    ey = np.cross(ez, ex)
    n = (radial[:, None, None]*np.cos(phi)[None, :, None]*ex
         + radial[:, None, None]*np.sin(phi)[None, :, None]*ey
         + mu[:, None, None]*ez)
    weights = np.broadcast_to(w[:, None]*math.pi/order*model.inner_radius_m**2,
                              n.shape[:-1])
    sigma = model.inner_density(n)
    total = float(np.sum(sigma*weights))
    return {'order': order, 'sample_count': 2*order*order, 'total_C': total,
            'exact_total_C': -model.charge_C, 'error_C': total+model.charge_C,
            'renormalized': False}


def seed_directions(count):
    if type(count) is not int or not 4 <= count <= 128:
        raise ValueError('field-line count must be an integer in [4,128]')
    j = np.arange(count)
    z = 1 - 2*(j+0.5)/count
    phi = j * math.pi*(3-math.sqrt(5))
    return np.column_stack((np.sqrt(1-z*z)*np.cos(phi),
                            np.sqrt(1-z*z)*np.sin(phi), z))


def trace_cavity_lines(model, count=32, step=0.025, max_steps=1200):
    """Bounded RK4 traces of E direction; display sampling, NOT time dynamics.

    Trace charge-to-wall geometry; reverse arrays for q<0 so arrows follow E.
    Stop short of the actual source/surface; never evaluate in the metal.
    Counts/spacing of seeds are illustrative, not calibrated electric flux.
    """
    directions = seed_directions(count)
    step = _number(step, 'step')
    if not 0.001 <= step <= 0.05 or type(max_steps) is not int or not 1 <= max_steps <= 4000:
        raise ValueError('step must be in [0.001,0.05] R; max_steps in [1,4000]')
    if model.charge_C == 0:
        return []
    a = np.asarray(model.charge_position_m) / model.inner_radius_m
    seed_radius = min(0.025, (1-float(_norm(a)))*0.08)
    current = a + seed_radius*directions
    paths = [[p.copy()] for p in current]
    active = np.ones(count, dtype=bool)
    statuses = ['step_limit'] * count

    def unit(points):
        e = model._cavity_shape_field(points)
        mag = _norm(e)
        if np.any(mag == 0) or not np.isfinite(e).all():
            raise FloatingPointError('unresolved field direction in display tracing')
        return e / mag[:, None]

    for _ in range(max_steps):
        ids = np.flatnonzero(active)
        if not len(ids):
            break
        p = current[ids]
        wall = 1-_norm(p)
        finished = wall <= 1e-4
        for i in ids[finished]:
            active[i] = False
            statuses[i] = 'inner_surface_approached'
        ids, p, wall = ids[~finished], p[~finished], wall[~finished]
        if not len(ids):
            continue
        h = np.minimum(step, np.minimum(wall*0.35, _norm(p-a)*0.35))[:, None]
        k1 = unit(p)
        k2 = unit(p+h*k1/2)
        k3 = unit(p+h*k2/2)
        k4 = unit(p+h*k3)
        nxt = p+h*(k1+2*k2+2*k3+k4)/6
        if np.any(_norm(nxt) >= 1):
            raise FloatingPointError('display trace escaped cavity')
        current[ids] = nxt
        for i, point in zip(ids, nxt):
            paths[i].append(point.copy())
    result = []
    for path, status in zip(paths, statuses):
        points = np.asarray(path)*model.inner_radius_m
        if model.charge_C < 0:
            points = points[::-1].copy()
        result.append({'points_m': points, 'termination': status,
                       'follows_electric_field': True, 'is_particle_trajectory': False})
    return result
