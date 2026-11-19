"""Rigid electric dipole in a prescribed UNIFORM external field (Issue 50).

Static configurations only. No inertia, free rotation, polarization or radiation.
The finite-pair force/torque relations are exact in a uniform field; there is no
point-dipole far-field approximation. Existing source laws remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np

from .fields import DomainError, UniformField

_EPS = np.finfo(float).eps
_KEYS = {"lesson_version", "lesson_type", "charge_C", "positive_position_m",
         "negative_position_m", "external_field_N_C", "torque_origin_m"}


def number(value, name):
    """Strict real input; do not accept JSON booleans, strings or complex values."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite float64") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def vector(value, name):
    try:
        raw = np.asarray(value, dtype=object)
        if raw.shape != (3,):
            raise ValueError(f"{name} must be one three-vector")
        return tuple(number(v, name) for v in raw)
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real three-vector") from exc


def norm(v):
    return float(np.hypot.reduce(v))


def _product(a, b):
    result = float(a)*float(b)
    if a and b and result == 0:
        raise DomainError("a nonzero dipole component is below float64 range")
    return result


def _sum_products(pairs):
    """Three-term analytic arithmetic; exact-rational fallback only at cancellation.

    The fallback resolves product rounding, not physical dynamics or an extra
    field solver. It never snaps a small nonzero result to zero.
    """
    pairs = [(float(a),float(b)) for a,b in pairs]
    terms = [a*b for a,b in pairs]
    result = math.fsum(terms)
    scale = math.fsum(abs(x) for x in terms)
    if abs(result) <= 8*_EPS*scale or any(a and b and t == 0 for (a,b),t in zip(pairs,terms)):
        exact = sum((Fraction(a)*Fraction(b) for a,b in pairs), Fraction(0))
        result = float(exact)
        if exact and result == 0:
            raise DomainError("a nonzero dipole component is below float64 range")
    return result


def _cross(a, b):
    return np.array([_sum_products([(a[1],b[2]),(-a[2],b[1])]),
                     _sum_products([(a[2],b[0]),(-a[0],b[2])]),
                     _sum_products([(a[0],b[1]),(-a[1],b[0])])])


@dataclass(frozen=True)
class DipoleState:
    charge_C: float = 1e-9
    positive_position_m: tuple = (1., 2., 1.)
    negative_position_m: tuple = (0., 1., 0.)
    external_field_N_C: tuple = (2., 3., 0.)
    torque_origin_m: tuple = (0., 0., 0.)

    def __post_init__(self):
        q = number(self.charge_C, "charge_C")
        if q < 0 or (q and not 1e-30 <= q <= 1e-3):
            raise ValueError("charge_C is a magnitude: zero or 1e-30..1e-3 C")
        object.__setattr__(self, "charge_C", q)
        for name in ("positive_position_m", "negative_position_m",
                     "external_field_N_C", "torque_origin_m"):
            object.__setattr__(self, name, vector(getattr(self, name), name))
        for name in ("positive_position_m", "negative_position_m", "torque_origin_m"):
            if max(abs(x) for x in getattr(self, name)) > 1e6:
                raise ValueError("V1 position/origin coordinates must have |x_i| <= 1e6 m")
        length = self.separation_m
        if not 1e-9 <= length <= 1e3:
            raise ValueError("V1 separation must be 1e-9..1e3 m (even at zero charge)")
        # Subtraction of nearby, large world coordinates must resolve the pair.
        uncertainty = 64*_EPS*(norm(self.positive_position_m)+norm(self.negative_position_m))
        if length <= uncertainty:
            raise DomainError("dipole separation is numerically unresolved in world coordinates")
        magnitude = norm(self.external_field_N_C)
        if magnitude and not 1e-12 <= magnitude <= 1e9:
            raise ValueError("V1 nonzero uniform field magnitude must be 1e-12..1e9 N/C")

    @property
    def separation_vector_m(self):
        return np.asarray(self.positive_position_m) - np.asarray(self.negative_position_m)

    @property
    def separation_m(self):
        return norm(self.separation_vector_m)

    @property
    def center_m(self):
        return (np.asarray(self.positive_position_m)+np.asarray(self.negative_position_m))/2

    def to_dict(self):
        return {"lesson_version": 1, "lesson_type": "electric_dipole",
                "charge_C": self.charge_C,
                "positive_position_m": list(self.positive_position_m),
                "negative_position_m": list(self.negative_position_m),
                "external_field_N_C": list(self.external_field_N_C),
                "torque_origin_m": list(self.torque_origin_m)}


def measure(state):
    """External forces in N, dipole moment in C m, torque in N m and energy in J.

    Torque is evaluated as q*(r_plus-r_minus) cross E, avoiding cancellation of
    large origin-dependent terms. Net force vanishes independently of origin.
    U excludes the constant mutual energy of the rigid pair and is zero when
    the moment is perpendicular to E. Small nonzero torques are not set to zero.
    """
    if not isinstance(state, DipoleState):
        raise ValueError("requires a validated DipoleState")
    q = state.charge_C
    d = state.separation_vector_m
    field = UniformField("electric", state.external_field_N_C)
    forces = q*field.field([state.positive_position_m, state.negative_position_m])
    forces[1] *= -1
    p = np.array([_product(q,x) for x in d])
    e = np.asarray(state.external_field_N_C)
    cross = _cross(d, e) if q else np.zeros(3)
    tau = np.array([_product(q,x) for x in cross])
    energy = -_product(q,_sum_products(zip(d,e))) if q else 0.
    if any(q and x and f == 0 for x,f in zip(e,forces[0])):
        raise DomainError("a nonzero force component is below float64 range")
    em = norm(e)
    angle = None
    equilibrium = "no_preferred_orientation"
    if q and em:
        sine = norm(cross)
        cosine = _sum_products(zip(d,e))
        angle = math.degrees(math.atan2(sine, cosine))
        # Only exactly vanishing computed torque receives an equilibrium label.
        # Near-collinear cases retain their actual angle and nonzero torque.
        equilibrium = ("stable_parallel" if cosine > 0 else "unstable_antiparallel"
                       ) if norm(tau) == 0 else "not_equilibrium"
    data = {"status": "available", "dipole_moment_C_m": p.tolist(),
            "positive_force_N": forces[0].tolist(), "negative_force_N": forces[1].tolist(),
            "net_external_force_N": (forces[0]+forces[1]).tolist(),
            "torque_N_m": tau.tolist(), "torque_origin_m": list(state.torque_origin_m),
            "external_orientation_energy_J": float(energy),
            "separation_m": state.separation_m, "angle_deg": angle,
            "angle_available": angle is not None, "equilibrium": equilibrium,
            "uniform_external_field": True, "static_configuration": True,
            "includes_mutual_energy": False, "time_dynamics": False,
            "torque_method": "q * (r_positive-r_negative) cross E; origin-independent couple",
            "energy_reference": "zero at perpendicular orientation; mutual energy omitted"}
    if not all(np.isfinite(x).all() for x in (p, forces, tau, energy)):
        raise FloatingPointError("nonfinite dipole measurement")
    return data


def orientation_work(initial, final):
    """Quasistatic external work for a reorientation at fixed q, length and E.

    A floating-point length match (256 eps relative) allows roundoff in rotations;
    it is not a physical solver tolerance. Changes of charge, field or separation
    are not silently reinterpreted as rotation work. Translation in uniform E
    and a change of torque origin do not affect this work.
    """
    if not isinstance(initial, DipoleState) or not isinstance(final, DipoleState):
        raise ValueError("requires two validated DipoleState objects")
    compatible = (initial.charge_C == final.charge_C
                  and initial.external_field_N_C == final.external_field_N_C
                  and math.isclose(initial.separation_m, final.separation_m,
                                   rel_tol=256*_EPS, abs_tol=0.))
    if not compatible:
        return {"status": "unavailable_changed_constraints", "external_work_J": None,
                "field_work_J": None, "reason": "rotation work requires fixed charge, separation and E"}
    # Difference before dot product avoids cancellation of large energy references.
    delta = final.separation_vector_m-initial.separation_vector_m
    work = (0. if initial.charge_C == 0 else
            -_product(initial.charge_C, _sum_products(zip(delta,initial.external_field_N_C))))
    return {"status": "available", "external_work_J": float(work), "field_work_J": float(-work),
            "quasistatic": True, "dynamic_motion_solved": False}


def from_dict(data):
    if not isinstance(data, dict) or set(data) != _KEYS:
        raise ValueError("requires exactly the electric-dipole V1 keys")
    if type(data["lesson_version"]) is not int or data["lesson_version"] != 1:
        raise ValueError("lesson_version must be integer 1")
    if data["lesson_type"] != "electric_dipole":
        raise ValueError("lesson_type must be electric_dipole")
    return DipoleState(**{k: data[k] for k in _KEYS-{"lesson_version","lesson_type"}})


def parse_lesson(raw):
    if not isinstance(raw, (bytes, str)):
        raise ValueError("authored input must be bytes or text")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def nonfinite(token):
        raise ValueError(f"nonfinite JSON token: {token}")
    try:
        return from_dict(json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid dipole lesson JSON") from exc


def load_lesson(path):
    return parse_lesson(Path(path).read_bytes())
