"""Exact vacuum B of a single ideal circular filament, on its axis only.

No off-axis field, material response, finite wire thickness, or induction.
All physical distances are metres and field components are tesla.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import json
import math
from pathlib import Path

import numpy as np
from scipy.constants import mu_0

VERSION = 1
TYPE = "ideal_circular_current_loop_axis"
_KEYS = {"lesson_version", "lesson_type", "centre_m", "normal_direction",
         "current_A", "radius_m", "probe_z_m", "samples_per_loop"}


def _float_token(token: str) -> float:
    value = float(token)
    if not math.isfinite(value) or (value == 0 and Decimal(token) != 0):
        raise ValueError("loop JSON float64 overflow/underflow: " + token)
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate loop JSON key: " + key)
        result[key] = value
    return result


def _number(value, name):
    if type(value) not in (int, float):
        raise ValueError(name + " must be a real number (not bool)")
    try:
        value = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(name + " is not representable") from exc
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return value


def _vector(value, name):
    if type(value) not in (tuple, list) or len(value) != 3:
        raise ValueError(name + " must contain three numbers")
    values = tuple(_number(x, name) for x in value)
    if any(abs(x) > 100.0 for x in values):
        raise ValueError(name + " outside bounded lesson coordinates")
    return values


@dataclass(frozen=True)
class CircularLoopState:
    centre_m: tuple = (0.0, 0.0, 0.0)
    normal_direction: tuple = (0.0, 0.0, 1.0)
    current_A: float = 5.0
    radius_m: float = 0.20
    probe_z_m: float = 0.0
    samples_per_loop: int = 72

    def __post_init__(self):
        centre = _vector(self.centre_m, "centre_m")
        normal = _vector(self.normal_direction, "normal_direction")
        length = math.hypot(*normal)
        if not 1e-8 <= length <= 100.0:
            raise ValueError("normal_direction must resolve to nonzero direction")
        normal = tuple(x / length for x in normal)
        if not all(math.isfinite(x) for x in normal):
            raise ValueError("normal_direction not representable")
        current = _number(self.current_A, "current_A")
        if abs(current) > 1e4 or (current != 0 and abs(current) < 1e-6):
            raise ValueError("current_A must be zero or 1e-6..1e4 A")
        radius = _number(self.radius_m, "radius_m")
        if not 1e-3 <= radius <= 100.0:
            raise ValueError("radius_m must be 1e-3..100 m")
        z = _number(self.probe_z_m, "probe_z_m")
        if abs(z) > 100.0:
            raise ValueError("probe_z_m must be within +/-100 m")
        if type(self.samples_per_loop) is not int or not 24 <= self.samples_per_loop <= 192:
            raise ValueError("samples_per_loop must be integer 24..192")
        object.__setattr__(self, "centre_m", centre)
        object.__setattr__(self, "normal_direction", normal)
        object.__setattr__(self, "current_A", current)
        object.__setattr__(self, "radius_m", radius)
        object.__setattr__(self, "probe_z_m", z)

    def to_dict(self):
        return {"lesson_version": VERSION, "lesson_type": TYPE,
                "centre_m": list(self.centre_m),
                "normal_direction": list(self.normal_direction),
                "current_A": self.current_A, "radius_m": self.radius_m,
                "probe_z_m": self.probe_z_m,
                "samples_per_loop": self.samples_per_loop}


def from_dict(obj):
    if type(obj) is not dict or set(obj) != _KEYS:
        raise ValueError("circular loop lesson requires exactly declared keys")
    if type(obj["lesson_version"]) is not int or obj["lesson_version"] != VERSION:
        raise ValueError("unsupported lesson_version")
    if type(obj["lesson_type"]) is not str or obj["lesson_type"] != TYPE:
        raise ValueError("unsupported lesson_type")
    return CircularLoopState(centre_m=obj["centre_m"],
                             normal_direction=obj["normal_direction"],
                             current_A=obj["current_A"], radius_m=obj["radius_m"],
                             probe_z_m=obj["probe_z_m"],
                             samples_per_loop=obj["samples_per_loop"])


def lesson_from_bytes(source_bytes: bytes):
    """Validate the EXACT original UTF-8 JSON bytes, with load_lesson rules.

    This is also the snapshot input-provenance preflight; never trust a caller's
    separately supplied state or a SHA-256 digest in place of strict parsing.
    """
    if type(source_bytes) is not bytes:
        raise ValueError("circular-loop source must be raw UTF-8 bytes")
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("circular-loop source must be valid UTF-8") from exc
    obj = json.loads(source_text,
                     parse_float=_float_token,
                     parse_int=_float_or_integer_token,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + x)),
                     object_pairs_hook=_pairs)
    return from_dict(obj)


def load_lesson(path):
    return lesson_from_bytes(Path(path).read_bytes())


def _float_or_integer_token(token):
    # Preserve small ordinary integer types (version, samples); refuse float64
    # underflow/overflow for potentially large physical integer tokens.
    value = int(token)
    try:
        represented = float(value)
    except OverflowError as exc:
        raise ValueError("loop integer outside float64 range") from exc
    if not math.isfinite(represented):
        raise ValueError("loop integer outside float64 range")
    return value


def basis(state: CircularLoopState):
    """Return right-handed u,e1,e2, with e1 cross e2 == u."""
    u = np.asarray(state.normal_direction, dtype=float)
    anchor = np.asarray((0., 1., 0.) if abs(u[2]) > 0.9 else (0., 0., 1.))
    e1 = np.cross(anchor, u)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    return u, e1, e2


def axis_field(state: CircularLoopState, z_m=None):
    """Exact on-axis vector B(z) in tesla; z measured along positive u.

    Deliberately accepts an axial scalar only. Arbitrary Cartesian probes must
    use field_at_point, which rejects off-axis points.
    """
    z = state.probe_z_m if z_m is None else _number(z_m, "z_m")
    if abs(z) > 100.0:
        raise ValueError("axis probe outside lesson domain")
    if state.current_A == 0:
        return np.zeros(3, dtype=float)
    radius = state.radius_m
    # hypot avoids needless intermediate overflow and preserves representability.
    denom = math.hypot(radius, z) ** 3
    scalar = mu_0 * state.current_A * radius * radius / (2.0 * denom)
    if not math.isfinite(scalar) or scalar == 0:
        raise ValueError("nonrepresentable nonzero axial magnetic field")
    field = scalar * np.asarray(state.normal_direction, dtype=float)
    if not np.isfinite(field).all() or not np.any(field):
        raise ValueError("nonrepresentable B components")
    return field


def _cartesian_probe(point_m):
    """Strict public Cartesian probe; reject bool/object before NumPy coercion."""
    if isinstance(point_m, np.ndarray):
        if point_m.shape != (3,) or point_m.dtype.kind not in "fiu":
            raise ValueError("point_m must contain three real non-Boolean numbers")
        point = np.asarray(point_m, dtype=float)
    elif type(point_m) in (list, tuple) and len(point_m) == 3:
        # A computed physical point often carries np.float64 or np.int64
        # coordinates. They are valid real probes, unlike strict JSON state
        # values; test raw Booleans BEFORE array coercion.
        if any(isinstance(v, (bool, np.bool_)) or
               not isinstance(v, (int, float, np.integer, np.floating))
               for v in point_m):
            raise ValueError("point_m must contain three real non-Boolean numbers")
        try:
            point = np.asarray(point_m, dtype=float)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("point_m components not representable") from exc
    else:
        raise ValueError("point_m must contain three real non-Boolean numbers")
    # A valid centre and axial displacement may each reach +/-100 m.
    if not np.isfinite(point).all() or np.any(np.abs(point) > 200.0):
        raise ValueError("point_m outside finite Cartesian lesson domain")
    return point


def field_at_point(state: CircularLoopState, point_m):
    """Only on-axis Cartesian probes; no off-axis field approximation.

    For rotated normals, a point constructed as centre+z*u may have unavoidable
    floating-point rounding. Admit such a point ONLY when it can be recreated
    from an axial coordinate to within two float64 ULPs per coordinate.
    Coordinates perpendicular to an EXACTLY axis-aligned normal must match the
    centre exactly (zero tolerance), even if their difference is very small.
    This is a tight representation boundary, not a physical off-axis region.
    Prefer axis_field(state, z) with explicit axial z when that is available.
    """
    point = _cartesian_probe(point_m)
    centre = np.asarray(state.centre_m, dtype=float)
    u = np.asarray(state.normal_direction, dtype=float)
    displacement = point - centre

    fixed = (u == 0.)
    if np.any(point[fixed] != centre[fixed]):
        raise ValueError("off-axis circular-loop field not implemented")

    candidates = []
    for i in range(3):
        if fixed[i]:
            continue
        z = float(displacement[i] / u[i])
        if not math.isfinite(z) or abs(z) > 100.0:
            continue
        predicted = centre + z*u
        scale = np.maximum(np.maximum(np.abs(point), np.abs(centre)), np.abs(z*u))
        allowed = 2.0*np.spacing(scale)
        allowed[fixed] = 0.0
        delta = np.abs(predicted - point)
        if np.all(delta <= allowed):
            # Prefer the best-resolved axial coordinate; this avoids dividing
            # by a nearly-zero component of an oblique normal.
            resolution = abs(displacement[i]) / max(math.ulp(max(abs(float(point[i])),
                        abs(float(centre[i])), abs(float(z*u[i])))), math.ulp(0.0))
            candidates.append((resolution, z))
    if not candidates:
        raise ValueError("off-axis circular-loop field not implemented")
    return axis_field(state, max(candidates)[1])


def measure(state: CircularLoopState):
    centre = axis_field(state, 0.0)
    probe = axis_field(state)
    u = np.asarray(state.normal_direction)
    return {"model": TYPE, "radius_m": state.radius_m,
            "current_A": state.current_A, "probe_z_m": state.probe_z_m,
            "centre_signed_B_T": float(np.dot(centre, u)),
            "probe_signed_B_T": float(np.dot(probe, u)),
            "centre_B_xyz_T": centre.tolist(), "probe_B_xyz_T": probe.tolist(),
            "axis_only": True, "wire_thickness_schematic": True}


def teaching_case(initial: CircularLoopState, key):
    """Three teacher cases compare fields at the CENTRE, independent of probe."""
    if key == "1":
        return replace(initial, probe_z_m=0.0)
    if key == "2":
        return replace(initial, probe_z_m=0.0, current_A=-initial.current_A)
    if key == "3":
        return replace(initial, probe_z_m=0.0, radius_m=2 * initial.radius_m)
    raise ValueError("circular-loop case must be 1, 2 or 3")
