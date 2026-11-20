"""One rigid, perfectly thin, one-turn rectangular loop in uniform static B.

Exact SI magnetic moment, torque, orientation energy, and four segment forces.
No external field solver, self-field, induction, motion or material physics.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import json
import math
from pathlib import Path

import numpy as np

VERSION = 1
TYPE = "ideal_rectangular_current_loop_uniform_B"
_KEYS = {"lesson_version", "lesson_type", "centre_m", "field_direction",
         "field_strength_T", "width_m", "height_m", "current_A", "tilt_deg"}


def _float_token(token: str) -> float:
    val = float(token)
    if not math.isfinite(val) or (val == 0 and Decimal(token) != 0):
        raise ValueError("rectangular-loop JSON number over/underflows binary64")
    return val


def _int_token(token: str) -> int:
    val = int(token)
    try:
        represented = float(val)
    except OverflowError as exc:
        raise ValueError("rectangular-loop JSON integer exceeds binary64") from exc
    if not math.isfinite(represented):
        raise ValueError("rectangular-loop JSON integer exceeds binary64")
    return val


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate rectangular-loop JSON key: " + k)
        result[k] = v
    return result


def _number(value, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(name + " must be a finite JSON real number, not bool")
    try:
        v = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(name + " cannot be represented as binary64") from exc
    if not math.isfinite(v):
        raise ValueError(name + " must be finite")
    return v


def _vector(value, name: str):
    if type(value) not in (list, tuple) or len(value) != 3:
        raise ValueError(name + " must be a three-vector")
    v = tuple(_number(x, name) for x in value)
    if any(abs(x) > 100.0 for x in v):
        raise ValueError(name + " outside bounded lesson coordinates")
    return v


@dataclass(frozen=True)
class RectangularLoopState:
    centre_m: tuple = (0.0, 0.0, 0.0)
    field_direction: tuple = (0.0, 0.0, 1.0)
    field_strength_T: float = 0.2
    width_m: float = 0.6
    height_m: float = 0.4
    current_A: float = 3.0
    tilt_deg: float = 45.0

    def __post_init__(self):
        centre = _vector(self.centre_m, "centre_m")
        direction = _vector(self.field_direction, "field_direction")
        length = math.hypot(*direction)
        if not 1e-8 <= length <= 100.0:
            raise ValueError("field_direction must resolve to a nonzero axis")
        # Preserve canonical binary64 normalized directions on reload. Otherwise
        # 1-ULP rounding drift makes original-source provenance inconsistent.
        if abs(length - 1.0) > math.ulp(1.0):
            direction = tuple(x / length for x in direction)
        if not all(math.isfinite(x) for x in direction):
            raise ValueError("field_direction not representable")
        field = _number(self.field_strength_T, "field_strength_T")
        if abs(field) > 10 or (field != 0 and abs(field) < 1e-6):
            raise ValueError("field_strength_T must be zero or 1e-6..10 T")
        width = _number(self.width_m, "width_m")
        height = _number(self.height_m, "height_m")
        if not 1e-3 <= width <= 10 or not 1e-3 <= height <= 10:
            raise ValueError("width_m/height_m must each be 0.001..10 m")
        current = _number(self.current_A, "current_A")
        if abs(current) > 1e4 or (current != 0 and abs(current) < 1e-6):
            raise ValueError("current_A must be zero or 1e-6..1e4 A")
        tilt = _number(self.tilt_deg, "tilt_deg")
        if not 0 <= tilt <= 180:
            raise ValueError("tilt_deg must be in 0..180 degrees")
        object.__setattr__(self, "centre_m", centre)
        object.__setattr__(self, "field_direction", direction)
        object.__setattr__(self, "field_strength_T", field)
        object.__setattr__(self, "width_m", width)
        object.__setattr__(self, "height_m", height)
        object.__setattr__(self, "current_A", current)
        object.__setattr__(self, "tilt_deg", tilt)

    def to_dict(self):
        return {"lesson_version": VERSION, "lesson_type": TYPE,
                "centre_m": list(self.centre_m),
                "field_direction": list(self.field_direction),
                "field_strength_T": self.field_strength_T,
                "width_m": self.width_m, "height_m": self.height_m,
                "current_A": self.current_A, "tilt_deg": self.tilt_deg}


def from_dict(obj):
    if type(obj) is not dict or set(obj) != _KEYS:
        raise ValueError("rectangular-loop lesson requires exactly declared keys")
    if type(obj["lesson_version"]) is not int or obj["lesson_version"] != VERSION:
        raise ValueError("unsupported rectangular-loop lesson_version")
    if type(obj["lesson_type"]) is not str or obj["lesson_type"] != TYPE:
        raise ValueError("unsupported rectangular-loop lesson_type")
    return RectangularLoopState(
        centre_m=obj["centre_m"], field_direction=obj["field_direction"],
        field_strength_T=obj["field_strength_T"], width_m=obj["width_m"],
        height_m=obj["height_m"], current_A=obj["current_A"],
        tilt_deg=obj["tilt_deg"])


def lesson_from_bytes(raw: bytes) -> RectangularLoopState:
    """Parse exact raw UTF-8 bytes with the same strict rules for files/receipts."""
    if type(raw) is not bytes:
        raise ValueError("original lesson source must be bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("original lesson source must be valid UTF-8") from exc
    obj = json.loads(text, parse_float=_float_token, parse_int=_int_token,
                     parse_constant=lambda s: (_ for _ in ()).throw(
                         ValueError("nonfinite JSON constant: " + s)),
                     object_pairs_hook=_pairs)
    return from_dict(obj)


def load_lesson(path) -> RectangularLoopState:
    return lesson_from_bytes(Path(path).read_bytes())


def orientation(state: RectangularLoopState):
    """Return (u,e1,e2) where e1 x e2 = u and u tilts from +field direction.

    e1 is the width tangent; e2 is the height tangent. Signed current follows
    the closed rectangle +e1, +e2, -e1, -e2. The angle is geometric, not the
    angle of magnetic moment when I<0 or signed B when field_strength_T<0.
    """
    d = np.asarray(state.field_direction, dtype=float)
    anchor = np.array((0., 1., 0.) if abs(d[2]) > .9 else (0., 0., 1.))
    swing = np.cross(anchor, d)
    swing = swing / np.linalg.norm(swing)
    e1 = np.cross(d, swing)
    e1 = e1 / np.linalg.norm(e1)
    theta = state.tilt_deg
    if theta == 0:
        sine, cosine = 0.0, 1.0
    elif theta == 90:
        sine, cosine = 1.0, 0.0
    elif theta == 180:
        sine, cosine = 0.0, -1.0
    else:
        sine, cosine = math.sin(math.radians(theta)), math.cos(math.radians(theta))
    u = cosine * d + sine * swing
    e2 = np.cross(u, e1)
    return u, e1, e2


def calculate(state: RectangularLoopState):
    """Physical SI arrays for one loop; never use display geometry for forces."""
    u, e1, e2 = orientation(state)
    a, b, I = state.width_m, state.height_m, state.current_A
    centre = np.asarray(state.centre_m)
    rel_corners = np.vstack((
        -a/2*e1 - b/2*e2,
        +a/2*e1 - b/2*e2,
        +a/2*e1 + b/2*e2,
        -a/2*e1 + b/2*e2
    ))
    corners = rel_corners + centre
    # Exact signed segment displacements; their sum is zero by construction,
    # without subtracting large translated world coordinates.
    edge_vectors = np.vstack((a*e1, b*e2, -a*e1, -b*e2))
    rel_midpoints = np.vstack((-b/2*e2, a/2*e1, b/2*e2, -a/2*e1))
    midpoints = rel_midpoints + centre
    B = state.field_strength_T * np.asarray(state.field_direction)
    m = (I * a * b) * u
    tau = np.cross(m, B)
    # Exactly parallel/antiparallel ideal configurations have zero torque;
    # normalizing arbitrary orientation vectors can otherwise leave 1-ULP
    # numerical cross-product residue at the endpoints.
    if state.tilt_deg in (0., 180.) or I == 0 or state.field_strength_T == 0:
        tau = np.zeros(3)
    U = -float(np.dot(m, B))
    if state.tilt_deg == 90 or I == 0 or state.field_strength_T == 0:
        U = 0.0
    forces = I * np.cross(edge_vectors, B)
    net_force = np.sum(forces, axis=0)
    segment_torque = np.sum(np.cross(rel_midpoints, forces), axis=0)
    arrays = dict(normal_unit=u, width_unit=e1, height_unit=e2,
                  loop_corners_m=corners, side_midpoints_m=midpoints,
                  edge_vectors_m=edge_vectors, field_B_T=B,
                  moment_A_m2=m, torque_N_m=tau, forces_N=forces,
                  net_force_N=net_force, segment_torque_N_m=segment_torque)
    if any(not np.isfinite(a).all() for a in arrays.values()) or not math.isfinite(U):
        raise ValueError("nonrepresentable rectangular-loop SI result")
    # A finite accepted one-turn loop with nonzero I must retain a resolvable
    # magnetic moment, and a nonzero field must be representable as B.
    if I != 0 and not np.any(m):
        raise ValueError("nonzero magnetic moment underflow")
    if state.field_strength_T != 0 and not np.any(B):
        raise ValueError("nonzero magnetic field underflow")
    return arrays, U


def measure(state: RectangularLoopState):
    arrays, U = calculate(state)
    return {"model": TYPE, "current_A": state.current_A,
            "width_m": state.width_m, "height_m": state.height_m,
            "area_m2": state.width_m * state.height_m,
            "tilt_positive_normal_to_reference_field_deg": state.tilt_deg,
            "signed_field_strength_T": state.field_strength_T,
            "field_B_xyz_T": arrays["field_B_T"].tolist(),
            "moment_xyz_A_m2": arrays["moment_A_m2"].tolist(),
            "torque_xyz_N_m": arrays["torque_N_m"].tolist(),
            "torque_magnitude_N_m": math.hypot(*arrays["torque_N_m"]),
            "orientation_potential_J": U,
            "net_force_xyz_N": arrays["net_force_N"].tolist(),
            "segment_torque_xyz_N_m": arrays["segment_torque_N_m"].tolist(),
            "one_turn_only": True,
            "uniform_external_field_only": True,
            "no_rotation_dynamics_or_induction": True}


def teaching_case(initial: RectangularLoopState, case: str):
    if case == "1":
        return replace(initial, tilt_deg=0.)
    if case == "2":
        return replace(initial, tilt_deg=90.)
    if case == "3":
        return replace(initial, tilt_deg=180.)
    if case == "4":
        return replace(initial, tilt_deg=90., current_A=-initial.current_A)
    if case == "5":
        return replace(initial, tilt_deg=90., current_A=0.)
    if case == "6":
        return replace(initial, tilt_deg=90., field_strength_T=0.)
    raise ValueError("rectangular-loop teaching case must be 1..6")
