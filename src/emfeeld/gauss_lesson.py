"""JEE Gaussian-surface geometry: prescribed point charges, no material surface.

Oriented solid angles give exact rectangular cube-face flux (up to float64
roundoff); sphere quadrature is independently sampled and is not normalized
to Gauss's law. Source-on-boundary cases have no value in V1.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

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
    mat = np.asarray(rotation, dtype=float)
    if mat.shape != (3, 3) or not np.isfinite(mat).all():
        raise ValueError("rotation must be finite 3x3")
    if not np.allclose(mat.T @ mat, np.eye(3), rtol=0, atol=1e-12):
        raise ValueError("rotation must be orthonormal")
    if not abs(np.linalg.det(mat) - 1.0) <= 1e-12:
        raise ValueError("rotation must preserve right-handed orientation")
    return mat


def _solid_angle_triangle(a, b, c):
    """Signed solid angle subtended at origin, outward vertex orientation."""
    na, nb, nc = (float(np.hypot.reduce(v)) for v in (a, b, c))
    triple = float(np.dot(a, np.cross(b, c)))
    denominator = (na * nb * nc + float(np.dot(a, b)) * nc
                   + float(np.dot(b, c)) * na + float(np.dot(c, a)) * nb)
    return 2.0 * math.atan2(triple, denominator)


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
        rot = _rotation(self.rotation)
        object.__setattr__(self, "center_m", tuple(c))
        object.__setattr__(self, "side_m", side)
        object.__setattr__(self, "rotation", tuple(tuple(float(v) for v in row) for row in rot))

    def _local(self, position):
        center = np.asarray(self.center_m)
        rot = np.asarray(self.rotation)
        # Coordinates in half-side units, for numerically stable solid angles.
        return (rot.T @ (np.asarray(position) - center)) / (self.side_m / 2)

    def _inside(self, charge):
        local = self._local(charge.position_m)
        if not np.isfinite(local).all() or np.any(np.abs(local) > 1e8):
            raise ValueError("charge is outside V1 geometric coordinate limits")
        gap = np.abs(local) - 1.0
        margin = 128 * _EPS * np.maximum(1., np.abs(local))
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
                angle = (_solid_angle_triangle(*rays[:3])
                         + _solid_angle_triangle(rays[0], rays[2], rays[3]))
                result.append(angle)
        return tuple(result)

    def flux(self, charges):
        """Return signed face flux and independent analytic enclosed total.

        The face integral is q*Omega/(4*pi*epsilon_0); neither it nor the
        individual face values are reconstructed from the Gauss-law total.
        """
        charges = _charges(charges)
        signed = np.zeros(6, dtype=float)
        enclosed = 0.
        for charge in charges:
            inside = self._inside(charge)
            if inside:
                enclosed += charge.charge_C
            angles = np.asarray(self.face_solid_angles(charge.position_m))
            signed += (charge.charge_C / (_FOUR_PI * epsilon_0)) * angles
        exact = enclosed / epsilon_0
        return {"face_names": _NAMES, "face_flux_N_m2_per_C": tuple(float(x) for x in signed),
                "sum_faces_N_m2_per_C": float(sum(signed)),
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
        object.__setattr__(self, "radius_m", radius)

    def _inside(self, charge):
        d = (np.asarray(charge.position_m) - np.asarray(self.center_m)) / self.radius_m
        r = float(np.hypot.reduce(d))
        if not math.isfinite(r) or r > 1e8:
            raise ValueError("charge is outside V1 geometric coordinate limits")
        if abs(r - 1) <= 128 * _EPS * max(1., r):
            raise DomainError("charge on sphere boundary or side numerically unresolved")
        return r < 1.

    def flux(self, charges, *, n_polar=24, n_azimuth=48):
        """Independent exact total versus existing unrenormalized sphere quadrature."""
        from .integrals import sphere_flux
        charges = _charges(charges)
        enclosed = sum(c.charge_C for c in charges if self._inside(c))
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
        p = np.asarray(points)
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
