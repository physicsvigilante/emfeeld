"""JEE Gaussian-surface geometry: prescribed point charges, no material surface.

Oriented solid angles give exact rectangular cube-face flux (up to float64
roundoff); sphere quadrature is independently sampled and is not normalized
to Gauss's law. Source-on-boundary cases have no value in V1.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import json
from .numeric_tokens import finite_float
from pathlib import Path

import numpy as np
from scipy.constants import epsilon_0

from .fields import DomainError

_TWO_PI = 2.0 * math.pi
_FOUR_PI = 4.0 * math.pi
_EPS = np.finfo(float).eps
_NAMES = ("+x", "-x", "+y", "-y", "+z", "-z")


def _finite_vector(value, name):
    if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, dtype=object).flat):
        raise ValueError(f"{name} cannot contain booleans")
    try:
        raw = np.asarray(value)
        if raw.shape != (3,) or raw.dtype.kind not in "fiu":
            raise ValueError(f"{name} must be a real 3-vector")
        vec = np.asarray(raw, dtype=float)
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite 3-vector") from exc
    if not np.isfinite(vec).all():
        raise ValueError(f"{name} must be a finite 3-vector")
    return vec


def _finite_scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(f"{name} must be a finite real number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite real number")
    return number


@dataclass(frozen=True)
class HeldCharge:
    charge_C: float
    position_m: tuple[float, float, float]

    def __post_init__(self):
        q = _finite_scalar(self.charge_C, "charge_C")
        if q and not 1e-18 <= abs(q) <= 1e-3:
            raise ValueError("nonzero V1 charge magnitude must be 1e-18..1e-3 C")
        p = _finite_vector(self.position_m, "position_m")
        object.__setattr__(self, "charge_C", q)
        object.__setattr__(self, "position_m", tuple(float(v) for v in p))


def _charges(charges):
    if not isinstance(charges, (tuple, list)) or not 1 <= len(charges) <= 3:
        raise ValueError("V1 requires 1..3 held point charges")
    if not all(isinstance(c, HeldCharge) for c in charges):
        raise ValueError("charges must be HeldCharge instances")
    return tuple(charges)


def _rotation(rotation):
    try:
        raw = np.asarray(rotation)
        if (raw.dtype.kind not in "fiu" or any(isinstance(v, (bool, np.bool_))
                for v in np.asarray(rotation, dtype=object).flat)):
            raise ValueError("rotation must contain real numbers, not booleans or strings")
        mat = np.asarray(raw, dtype=float)
    except (TypeError, OverflowError) as exc:
        raise ValueError("rotation must be a finite real 3x3 matrix") from exc
    if mat.shape != (3, 3) or not np.isfinite(mat).all():
        raise ValueError("rotation must be finite 3x3")
    if np.max(np.abs(mat)) > 1 + 64 * _EPS:
        raise ValueError("rotation entries exceed unit-vector bounds")
    if not np.allclose(mat.T @ mat, np.eye(3), rtol=0, atol=64 * _EPS):
        raise ValueError("rotation must be orthonormal")
    if not abs(np.linalg.det(mat) - 1.0) <= 64 * _EPS:
        raise ValueError("rotation must preserve right-handed orientation")
    return mat


def _solid_angle_triangle(a, b, c, determinant):
    """Signed solid angle subtended at origin, outward vertex orientation."""
    na, nb, nc = (float(np.hypot.reduce(v)) for v in (a, b, c))
    denominator = math.fsum((na * nb * nc, float(np.dot(a, b)) * nc,
                             float(np.dot(b, c)) * na, float(np.dot(c, a)) * nb))
    return 2.0 * math.atan2(determinant, denominator)


def _center_bound(center, scale):
    # Bounded SI lesson, not arbitrary-scale geometry. Prevent collapsed meshes.
    if np.any(np.abs(center) > 1e6 * scale):
        raise ValueError("V1 requires |center coordinate| <= 1e6 surface radii/half-sides")


def _relative(position, center, scale):
    p = _finite_vector(position, "position_m")
    d = p - np.asarray(center)
    if np.any(np.abs(d) > 1e8 * scale):
        raise ValueError("charge is outside V1 geometric coordinate limits")
    return d / scale


def _boundary_margin(position, center, scale):
    # Include world-coordinate cancellation and rotation error, not only local ULPs.
    return 128 * _EPS * (1 + np.max(np.abs(position)) / scale
                         + np.max(np.abs(center)) / scale)


def _order(n_polar, n_azimuth):
    if (type(n_polar) is not int or not 2 <= n_polar <= 256
            or type(n_azimuth) is not int or not 2 <= n_azimuth <= 512):
        raise ValueError("V1 quadrature requires 2..256 polar and 2..512 azimuth samples")


@dataclass(frozen=True)
class GaussianCube:
    center_m: tuple[float, float, float] = (0., 0., 0.)
    side_m: float = 2.0
    rotation: tuple = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))

    def __post_init__(self):
        c = _finite_vector(self.center_m, "center_m")
        side = _finite_scalar(self.side_m, "side_m")
        if not 1e-6 <= side <= 1e3:
            raise ValueError("V1 cube side must be 1e-6..1e3 m")
        _center_bound(c, side / 2)
        rot = _rotation(self.rotation)
        object.__setattr__(self, "center_m", tuple(c))
        object.__setattr__(self, "side_m", side)
        object.__setattr__(self, "rotation", tuple(tuple(float(v) for v in row) for row in rot))

    def _local(self, position):
        center = np.asarray(self.center_m)
        rot = np.asarray(self.rotation)
        # Coordinates in half-side units, for numerically stable solid angles.
        return rot.T @ _relative(position, center, self.side_m / 2)

    def _inside(self, charge):
        local = self._local(charge.position_m)
        if not np.isfinite(local).all() or np.any(np.abs(local) > 1e8):
            raise ValueError("charge is outside V1 geometric coordinate limits")
        gap = np.abs(local) - 1.0
        margin = _boundary_margin(charge.position_m, self.center_m, self.side_m / 2)
        if np.any(gap > margin):
            return False
        if np.any(np.abs(gap) <= margin):
            raise DomainError("charge on cube boundary or side numerically unresolved")
        return True

    def face_solid_angles(self, position_m):
        """Signed outward solid angle of six closed cube faces, in steradians.

        Output face order: +x,-x,+y,-y,+z,-z in cube-local axes.
        """
        point = self._local(position_m)
        if not np.isfinite(point).all() or np.any(np.abs(point) > 1e8):
            raise ValueError("charge is outside V1 geometric coordinate limits")
        # Boundary refusal applies regardless of charge strength, including q=0.
        self._inside(HeldCharge(0., tuple(position_m)))
        result = []
        axes = np.eye(3)
        for axis in range(3):
            j, k = (axis + 1) % 3, (axis + 2) % 3
            for sign in (1., -1.):
                center = sign * axes[axis]
                u = axes[j]
                v = sign * axes[k]  # u cross v = outward normal
                vertices = [center - u - v, center + u - v,
                            center + u + v, center - u + v]
                rays = [p - point for p in vertices]
                distance = 1.0 - sign * point[axis]
                if distance == 0.0:
                    # Coplanar with this face but outside its rectangle; boundary
                    # points were already refused. E is exactly tangent here.
                    angle = 0.0
                elif abs(distance) < 1e-3:
                    # Rectangle antiderivative avoids cancellation close to an edge
                    # or the artificial diagonal used by triangle splitting.
                    x0, x1 = -1.0 - point[j], 1.0 - point[j]
                    y0, y1 = -1.0 - point[k], 1.0 - point[k]
                    def corner(x, y):
                        return math.atan2(x*y, abs(distance)*math.hypot(distance, x, y))
                    angle = math.copysign(1.0, distance) * math.fsum(
                        (corner(x0,y0), corner(x1,y1), -corner(x0,y1), -corner(x1,y0)))
                else:
                    # Exact geometric determinant = face triangle area factor *
                    # normal separation, avoiding a far-field cross-product loss.
                    det = 4.0 * distance
                    angle = (_solid_angle_triangle(*rays[:3], det)
                             + _solid_angle_triangle(rays[0], rays[2], rays[3], det))
                result.append(angle)
        return tuple(result)

    def flux(self, charges):
        """Return signed face flux and independent analytic enclosed total.

        The face integral is q*Omega/(4*pi*epsilon_0); neither it nor the
        individual face values are reconstructed from the Gauss-law total.
        """
        charges = _charges(charges)
        terms = []
        enclosed_terms = []
        for charge in charges:
            inside = self._inside(charge)
            if inside:
                enclosed_terms.append(charge.charge_C)
            angles = np.asarray(self.face_solid_angles(charge.position_m))
            terms.append((charge.charge_C / (_FOUR_PI * epsilon_0)) * angles)
        signed = [math.fsum(row[i] for row in terms) for i in range(6)]
        enclosed = math.fsum(enclosed_terms)
        exact = enclosed / epsilon_0
        return {"face_names": _NAMES, "face_flux_N_m2_per_C": tuple(float(x) for x in signed),
                "sum_faces_N_m2_per_C": math.fsum(signed),
                "exact_total_N_m2_per_C": float(exact),
                "enclosed_charge_C": float(enclosed),
                "unrenormalized": True}


@dataclass(frozen=True)
class GaussianSphere:
    center_m: tuple[float, float, float] = (0., 0., 0.)
    radius_m: float = 1.

    def __post_init__(self):
        c = _finite_vector(self.center_m, "center_m")
        radius = _finite_scalar(self.radius_m, "radius_m")
        if not 1e-6 <= radius <= 1e3:
            raise ValueError("V1 sphere radius must be 1e-6..1e3 m")
        object.__setattr__(self, "center_m", tuple(c))
        _center_bound(c, radius)
        object.__setattr__(self, "radius_m", radius)

    def _inside(self, charge):
        d = _relative(charge.position_m, self.center_m, self.radius_m)
        r = float(np.hypot.reduce(d))
        if not math.isfinite(r) or r > 1e8:
            raise ValueError("charge is outside V1 geometric coordinate limits")
        if abs(r - 1) <= _boundary_margin(charge.position_m, self.center_m, self.radius_m):
            raise DomainError("charge on sphere boundary or side numerically unresolved")
        return r < 1.

    def flux(self, charges, *, n_polar=24, n_azimuth=48):
        """Independent exact total versus existing unrenormalized sphere quadrature."""
        from .integrals import sphere_flux
        _order(n_polar, n_azimuth)
        charges = _charges(charges)
        enclosed = math.fsum(c.charge_C for c in charges if self._inside(c))
        model = _HeldCoulombField(charges)
        sampled = sphere_flux(model, self.center_m, self.radius_m,
                              n_polar=n_polar, n_azimuth=n_azimuth)
        exact = enclosed / epsilon_0
        return {"enclosed_charge_C": float(enclosed),
                "exact_total_N_m2_per_C": float(exact),
                "sampled_total_N_m2_per_C": sampled.total,
                "sampling_error_N_m2_per_C": sampled.total - exact,
                "n_polar": n_polar, "n_azimuth": n_azimuth,
                "unrenormalized": True}


class _HeldCoulombField:
    """Independent Coulomb evaluation solely at quadrature points."""
    def __init__(self, charges):
        self.charges = charges

    def field(self, points):
        try:
            p = np.asarray(points, dtype=float)
        except (TypeError, OverflowError) as exc:
            raise ValueError("points must be finite real vectors") from exc
        if p.ndim < 1 or p.shape[-1] != 3 or not np.isfinite(p).all():
            raise ValueError("points must be finite real vectors")
        result = np.zeros_like(p, dtype=float)
        for c in self.charges:
            if c.charge_C == 0.:
                continue
            displacement = p - np.asarray(c.position_m)
            distance = np.hypot.reduce(displacement, axis=-1)
            if np.any(distance == 0):
                raise DomainError("point charge coincides with a quadrature probe")
            result += c.charge_C / (_FOUR_PI * epsilon_0) * displacement / distance[..., None]**3
        if not np.isfinite(result).all():
            raise FloatingPointError("nonfinite Coulomb samples")
        return result


@dataclass(frozen=True)
class GaussState:
    """Immutable lesson state; a Gaussian surface is not a material object.

    Boundary positions are authorable for explicit undefined display. Only the
    measurement, not the geometry, refuses a singular closed-surface integral.
    """
    surface: GaussianCube | GaussianSphere = GaussianCube()
    charges: tuple = (HeldCharge(1e-9, (0., 0., 0.)),)

    def __post_init__(self):
        if type(self.surface) not in (GaussianCube, GaussianSphere):
            raise ValueError("surface must be a Gaussian cube or sphere")
        object.__setattr__(self, "charges", _charges(self.charges))
        for charge in self.charges:
            _relative(charge.position_m, self.surface.center_m, self.scale_m)

    @property
    def scale_m(self):
        return self.surface.side_m / 2 if isinstance(self.surface, GaussianCube) else self.surface.radius_m

    def to_dict(self):
        s = self.surface
        surface = {"type": "cube" if isinstance(s, GaussianCube) else "sphere",
                   "center_m": [float(v) for v in s.center_m]}
        if isinstance(s, GaussianCube):
            surface.update(side_m=s.side_m, rotation=[list(row) for row in s.rotation])
        else:
            surface["radius_m"] = s.radius_m
        return {"gauss_lesson_version": 1, "surface": surface,
                "charges": [{"charge_C": c.charge_C, "position_m": list(c.position_m)} for c in self.charges]}


def from_dict(data):
    if (not isinstance(data, dict) or set(data) != {"gauss_lesson_version", "surface", "charges"}
            or type(data["gauss_lesson_version"]) is not int or data["gauss_lesson_version"] != 1):
        raise ValueError("invalid Gauss lesson version or keys")
    s = data["surface"]
    if not isinstance(s, dict):
        raise ValueError("surface must be an object")
    if s.get("type") == "cube" and set(s) == {"type", "center_m", "side_m", "rotation"}:
        surface = GaussianCube(s["center_m"], s["side_m"], s["rotation"])
    elif s.get("type") == "sphere" and set(s) == {"type", "center_m", "radius_m"}:
        surface = GaussianSphere(s["center_m"], s["radius_m"])
    else:
        raise ValueError("unknown surface type or keys")
    charges = data["charges"]
    if not isinstance(charges, list) or not 1 <= len(charges) <= 3:
        raise ValueError("requires 1..3 held charges")
    if any(not isinstance(c, dict) or set(c) != {"charge_C", "position_m"} for c in charges):
        raise ValueError("unknown charge keys")
    return GaussState(surface, tuple(HeldCharge(**c) for c in charges))


def parse_lesson(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return from_dict(json.loads(raw, parse_float=finite_float, object_pairs_hook=unique))


def load_lesson(path):
    return parse_lesson(Path(path).read_bytes())


def measure(state, *, order=24):
    if not isinstance(state, GaussState):
        raise ValueError("measurement requires a validated GaussState")
    _order(order, 2 * order if type(order) is int else 0)
    try:
        if isinstance(state.surface, GaussianCube):
            result = state.surface.flux(state.charges)
        else:
            result = state.surface.flux(state.charges, n_polar=order, n_azimuth=2*order)
        return dict(result, status="available", gaussian_surface_is_material=False)
    except DomainError as exc:
        return {"status": "undefined_boundary", "reason": str(exc),
                "exact_total_N_m2_per_C": None, "enclosed_charge_C": None,
                "gaussian_surface_is_material": False}
