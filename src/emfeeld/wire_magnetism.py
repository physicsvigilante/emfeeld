"""JEE Magnetostatics V1: one ideal infinitely long, perfectly thin DC wire.

Static vacuum B field and a coaxial Ampere circle only. No finite-wire end
field, Lorentz dynamics, magnetic material, induced currents, or scalar potential.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np
from scipy.constants import mu_0

VERSION = 1
TYPE = 'ideal_infinite_straight_current_wire'
_KEYS = {'lesson_version', 'lesson_type', 'origin_m', 'axis_direction',
         'current_A', 'loop_radius_m', 'samples_per_loop'}


def _float_token(token: str) -> float:
    val = float(token)
    # JSON has already validated the grammar. Inspect the significand rather
    # than parsing an exponent that may exceed even Decimal's range.
    if not math.isfinite(val) or (val == 0 and any(
            c in '123456789' for c in token.lower().partition('e')[0])):
        raise ValueError('magnetic wire JSON number not representable as float64: ' + token)
    return val


def _number(value, name):
    if type(value) not in (int, float):
        raise ValueError(name + ' must be a finite JSON number, not bool or string')
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(name + ' is not representable as a number') from exc
    if not math.isfinite(v):
        raise ValueError(name + ' must be finite')
    return v


def _vec(value, name, limit):
    if type(value) not in (list, tuple) or len(value) != 3:
        raise ValueError(name + ' must be a three-vector')
    a = tuple(_number(x, name) for x in value)
    if any(abs(x) > limit for x in a):
        raise ValueError(name + ' outside bounded lesson domain')
    return a


def _no_duplicate_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate JSON key: ' + k)
        result[k] = v
    return result


class WireAxisError(ValueError):
    """The ideal current-bearing wire has no resolved field at this point."""


@dataclass(frozen=True)
class InfiniteStraightWire:
    origin_m: tuple = (0.0, 0.0, 0.0)
    axis_direction: tuple = (0.0, 0.0, 1.0)
    current_A: float = 5.0

    def __post_init__(self):
        origin = _vec(self.origin_m, 'origin_m', 100.0)
        axis = _vec(self.axis_direction, 'axis_direction', 100.0)
        length = math.hypot(*axis)
        if not 1e-8 <= length <= 100.0:
            raise ValueError('axis_direction must be a resolved nonzero vector')
        # A normalized binary64 vector can have a norm one ulp from unity.
        # Preserve that representation when reloading a serialized state.
        normalized = axis if abs(length - 1.) <= math.ulp(1.) else tuple(v / length for v in axis)
        if any(v and abs(n) < np.finfo(float).tiny and
               abs(n / v * length - 1.) > 8 * np.finfo(float).eps
               for v, n in zip(axis, normalized)):
            raise ValueError('axis_direction component cannot be resolved after normalization')
        axis = normalized
        I = _number(self.current_A, 'current_A')
        if abs(I) > 1e4 or (I != 0 and abs(I) < 1e-6):
            raise ValueError('current_A must be zero or 1e-6..1e4 A in magnitude')
        object.__setattr__(self, 'origin_m', origin)
        object.__setattr__(self, 'axis_direction', axis)
        object.__setattr__(self, 'current_A', I)

    def field_at(self, position_m):
        return magnetic_field(self, position_m)


@dataclass(frozen=True)
class WireState(InfiniteStraightWire):
    loop_radius_m: float = 0.2
    samples_per_loop: int = 48

    def __post_init__(self):
        super().__post_init__()
        R = _number(self.loop_radius_m, 'loop_radius_m')
        if not 1e-3 <= R <= 100.0:
            raise ValueError('loop_radius_m must be 1e-3..100 m')
        if type(self.samples_per_loop) is not int or not 12 <= self.samples_per_loop <= 192:
            raise ValueError('samples_per_loop must be an integer in 12..192')
        object.__setattr__(self, 'loop_radius_m', R)

    def to_dict(self):
        return {'lesson_version': VERSION, 'lesson_type': TYPE,
                'origin_m': list(self.origin_m),
                'axis_direction': list(self.axis_direction),
                'current_A': self.current_A,
                'loop_radius_m': self.loop_radius_m,
                'samples_per_loop': self.samples_per_loop}


def from_dict(data):
    if type(data) is not dict or (set(data) != _KEYS):
        raise ValueError('wire lesson requires exactly the declared keys')
    if type(data['lesson_version']) is not int or data['lesson_version'] != VERSION:
        raise ValueError('unsupported wire lesson_version')
    if data['lesson_type'] != TYPE:
        raise ValueError('unsupported wire lesson_type')
    return WireState(origin_m=data['origin_m'], axis_direction=data['axis_direction'],
                     current_A=data['current_A'], loop_radius_m=data['loop_radius_m'],
                     samples_per_loop=data['samples_per_loop'])


def load_lesson(path):
    return parse_lesson(Path(path).read_bytes())


def parse_lesson(raw):
    obj = json.loads(raw.decode('utf-8'),
                     parse_float=_float_token,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + x)),
                     object_pairs_hook=_no_duplicate_pairs)
    return from_dict(obj)


def basis(state: WireState):
    """Right-handed u, e1, e2; e1 cross e2 = u."""
    u = np.asarray(state.axis_direction, dtype=float)
    anchor = np.asarray((0., 1., 0.) if abs(u[2]) > .9 else (0., 0., 1.))
    e1 = np.cross(anchor, u)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    return u, e1, e2


def _contains_raw_bool(value):
    """Reject Python/NumPy booleans before NumPy upcasts mixed vectors.

    An existing integer ndarray cannot reveal whether its maker previously
    converted a boolean; this protects the direct public probe entry point.
    """
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, np.ndarray):
        if value.dtype.kind == 'b':
            return True
        if value.dtype.kind == 'O':
            return any(_contains_raw_bool(item) for item in value.flat)
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_raw_bool(item) for item in value)
    return False


def magnetic_field(state: InfiniteStraightWire, points_m):
    """Field B in tesla at physical points, not a visualization arrow.

    Singular at current-bearing ideal wire axis, including numerically
    unresolved near-axis displacement. Zero current returns exactly zero.
    """
    if _contains_raw_bool(points_m):
        raise ValueError('magnetic field probes must not contain booleans')
    raw = np.asarray(points_m)
    if raw.dtype.kind not in 'fiu':
        raise ValueError('magnetic field probes must be real numeric vectors')
    points = np.asarray(points_m, dtype=float)
    if points.ndim < 1 or points.shape[-1] != 3 or not np.isfinite(points).all():
        raise ValueError('magnetic probes must be finite three-vectors')
    if np.max(np.abs(points)) > 1e5:
        raise ValueError('magnetic probe outside bounded coordinate range')
    if state.current_A == 0:
        return np.zeros(points.shape, dtype=float)
    # B = (mu0 I / 2pi) |u| (u x d) / |u x d|Â². Keep the determinants
    # and division exact for the represented coordinates: components smaller
    # than intermediate float64 range can survive in the final SI vector.
    ux, uy, uz = map(Fraction, state.axis_direction)
    origin = tuple(map(Fraction, state.origin_m))
    origin_norm = Fraction(math.hypot(*state.origin_m))
    axis_norm = Fraction(math.hypot(*state.axis_direction))
    coefficient = Fraction(mu_0 * state.current_A / (2 * math.pi)) * axis_norm
    resolution = Fraction(64 * math.ulp(1.0)) * axis_norm
    field = np.empty(points.shape, dtype=float)
    for point, vector in zip(points.reshape(-1, 3), field.reshape(-1, 3)):
        dx, dy, dz = (Fraction(float(x)) - o for x, o in zip(point, origin))
        cross = (uy*dz - uz*dy, uz*dx - ux*dz, ux*dy - uy*dx)
        squared = sum(x*x for x in cross)
        uncertainty = resolution * (Fraction(math.hypot(*point)) + origin_norm)
        if squared <= uncertainty**2:
            raise WireAxisError('magnetic field undefined on or numerically unresolved near ideal wire axis')
        try:
            for index, x in enumerate(cross):
                component = coefficient * x / squared
                value = float(component)
                if component and abs(value) < np.finfo(float).tiny and abs(
                        Fraction(value) / component - 1) > 8 * math.ulp(1.0):
                    raise ValueError('nonzero magnetic field component lost precision')
                vector[index] = value
        except OverflowError as exc:
            raise ValueError('nonrepresentable magnetic field') from exc
    return field


def sample_ampere_loop(state: WireState):
    """Physical samples on continuous circle, with oriented tangent/arc weights.

    Samples are equally spaced for the actual analytic tangent line integral;
    the line *drawing* may use straight segments, but isn't used for physics.
    """
    u,e1,e2 = basis(state)
    phi = 2*math.pi*np.arange(state.samples_per_loop, dtype=float)/state.samples_per_loop
    direction = np.cos(phi)[:, None]*e1 + np.sin(phi)[:, None]*e2
    tangent = -np.sin(phi)[:, None]*e1 + np.cos(phi)[:, None]*e2
    points = np.asarray(state.origin_m)[None,:] + state.loop_radius_m*direction
    B = magnetic_field(state, points)
    weights = np.full(len(phi), 2*math.pi*state.loop_radius_m/len(phi))
    signed_tangent_B = np.einsum('ij,ij->i', B, tangent)
    circulation = float(np.sum(signed_tangent_B * weights))
    expected = mu_0 * state.current_A
    # Expose independent exact expression, never normalize sampled values to it.
    return {'points_m': points, 'tangents': tangent, 'field_T': B,
            'arc_weights_m': weights, 'signed_tangent_T': signed_tangent_B,
            'sampled_circulation_T_m': circulation,
            'ampere_expected_T_m': expected}


def _report_from_samples(state: WireState, data):
    """All physical SI report formulas belong to this analytic model layer."""
    return {
        'model': TYPE,
        'current_A': state.current_A,
        'loop_radius_m': state.loop_radius_m,
        'field_magnitude_T': abs(mu_0*state.current_A/(2*math.pi*state.loop_radius_m)),
        'signed_tangent_field_T': mu_0*state.current_A/(2*math.pi*state.loop_radius_m),
        'sampled_ampere_circulation_T_m': data['sampled_circulation_T_m'],
        'expected_mu0_I_T_m': data['ampere_expected_T_m'],
        'field_lines_circle_for_one_infinite_wire': True,
        'drawn_wire_is_truncated_schematic': True,
        'no_finite_wire_field_or_magnetic_force': True,
    }


def measure(state: WireState):
    """Complete physics report computed from a single circle sample set."""
    return _report_from_samples(state, sample_ampere_loop(state))


def teaching_case(initial: WireState, key):
    if key == '1':return initial
    if key == '2':return replace(initial,loop_radius_m=2*initial.loop_radius_m)
    if key == '3':return replace(initial,current_A=-initial.current_A)
    if key == '4':return replace(initial,current_A=0)
    raise ValueError('wire teaching case must be 1, 2, 3 or 4')
