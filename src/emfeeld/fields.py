"""Static prescribed sources. SI everywhere; field = -gradient(potential)."""
from dataclasses import dataclass
from typing import Protocol
import numpy as np
from scipy.constants import G, epsilon_0

K = 1.0 / (4.0 * np.pi * epsilon_0)
KINDS = ("electric", "gravity")


class DomainError(ValueError):
    """An evaluation is undefined or its geometric side is numerically unresolved."""


def _gamma(operations):
    # Deliberately use eps (twice round-to-nearest unit roundoff). No metre floor.
    neps = operations * np.finfo(float).eps
    return neps / (1.0 - neps)


def _cross_magnitudes(a, b):
    """Absolute product sums for each component of a cross product."""
    return (a[..., [1, 2, 0]] * b[..., [2, 0, 1]]
            + a[..., [2, 0, 1]] * b[..., [1, 2, 0]])


def _reject_unresolved(distance, uncertainty, description):
    if (np.any(~np.isfinite(distance)) or np.any(~np.isfinite(uncertainty))
            or np.any(np.abs(distance) <= uncertainty)):
        raise DomainError(description + "; on boundary or numerically unresolved")


def scalar(value, name, *, positive=False):
    if isinstance(value, (bool, np.bool_)) or not np.isscalar(value):
        raise ValueError(f"{name} must be a finite real scalar")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real scalar") from exc
    if not np.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))
    return result


def vector(value, name):
    result = np.asarray(value, dtype=float)
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError(f"{name} must contain three finite components")
    return tuple(float(x) for x in result)


def positions(value):
    result = np.asarray(value, dtype=float)
    if result.ndim < 1 or result.shape[-1] != 3 or not np.isfinite(result).all():
        raise ValueError("positions must have shape (..., 3) and be finite")
    return result


def check_kind(kind):
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")


class Field(Protocol):
    kind: str
    trajectory_safe: bool

    def field(self, points): ...
    def potential(self, points): ...


@dataclass(frozen=True)
class Source:
    """strength: C/kg, C/m or kg/m for lines, C/m^2 or kg/m^2 for planes."""
    kind: str
    strength: float
    center: tuple = (0.0, 0.0, 0.0)
    trajectory_safe = True

    def __post_init__(self):
        check_kind(self.kind)
        strength = scalar(self.strength, "strength")
        if self.kind == "gravity" and strength < 0:
            raise ValueError("negative gravitational source mass/density is not supported")
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "center", vector(self.center, "center"))

    @property
    def coefficient(self):
        return (K if self.kind == "electric" else -G) * self.strength

    def displacement(self, points):
        return positions(points) - self.center

    def _displacement_with_error(self, points):
        p = positions(points)
        # Componentwise allowance for input-coordinate/subtraction roundoff.
        error = _gamma(2) * (np.abs(p) + np.abs(self.center))
        return p - self.center, error


@dataclass(frozen=True)
class PointSource(Source):
    def potential(self, points):
        d = self.displacement(points)
        r = np.linalg.norm(d, axis=-1)
        if not self.strength:
            return np.zeros_like(r)
        if np.any(r == 0):
            raise DomainError("point-source potential is singular at its center")
        return self.coefficient / r

    def field(self, points):
        d = self.displacement(points)
        r = np.linalg.norm(d, axis=-1)
        if not self.strength:
            return np.zeros_like(d)
        if np.any(r == 0):
            raise DomainError("point-source field is singular at its center")
        return self.coefficient * d / r[..., None] ** 3


@dataclass(frozen=True)
class SolidSphere(Source):
    """Uniform, prescribed volume density; no hard-surface collision implied."""
    radius: float = 1.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "radius", scalar(self.radius, "radius", positive=True))

    def potential(self, points):
        r = np.linalg.norm(self.displacement(points), axis=-1)
        inside = (3 - (r / self.radius) ** 2) / (2 * self.radius)
        outside = 1 / np.maximum(r, self.radius)
        return self.coefficient * np.where(r <= self.radius, inside, outside)

    def field(self, points):
        d = self.displacement(points)
        r = np.linalg.norm(d, axis=-1)
        return self.coefficient * d / np.maximum(r, self.radius)[..., None] ** 3


@dataclass(frozen=True)
class SphericalShell(SolidSphere):
    """Uniform thin shell. Field at the ideal sheet itself is not assigned."""
    trajectory_safe = False

    def potential(self, points):
        r = np.linalg.norm(self.displacement(points), axis=-1)
        return self.coefficient / np.maximum(r, self.radius)

    def field(self, points):
        d, error = self._displacement_with_error(points)
        r = np.linalg.norm(d, axis=-1)
        if self.strength:
            uncertainty = np.linalg.norm(error, axis=-1) + _gamma(8) * (r + self.radius)
            _reject_unresolved(r - self.radius, uncertainty,
                               "shell field has two one-sided limits at its surface")
        return np.where((r > self.radius)[..., None],
                        self.coefficient * d / np.maximum(r, self.radius)[..., None] ** 3,
                        0.0)


@dataclass(frozen=True)
class InfiniteLine(Source):
    direction: tuple = (0.0, 0.0, 1.0)
    reference_radius: float = 1.0

    def __post_init__(self):
        super().__post_init__()
        a = np.array(vector(self.direction, "direction"))
        length = np.linalg.norm(a)
        if not np.isfinite(length) or length == 0:
            raise ValueError("direction must have a finite nonzero length")
        object.__setattr__(self, "direction", tuple(a / length))
        object.__setattr__(self, "reference_radius",
                           scalar(self.reference_radius, "reference_radius", positive=True))

    def _geometry(self, points):
        d, error = self._displacement_with_error(points)
        a = np.array(self.direction)
        cross = np.cross(d, a)
        # Cross products avoid subtracting two nearly equal axial projections.
        # Budget includes direction normalization and cross-product arithmetic.
        cross_error = (_gamma(16) * _cross_magnitudes(np.abs(d), np.abs(a))
                       + _cross_magnitudes(error, np.abs(a)))
        a2 = np.dot(a, a)
        rho = np.linalg.norm(cross, axis=-1) / np.sqrt(a2)
        uncertainty = (np.linalg.norm(cross_error, axis=-1) / np.sqrt(a2)
                       + _gamma(4) * rho)
        perpendicular = np.cross(a, cross) / a2
        return perpendicular, rho, uncertainty

    def perpendicular(self, points):
        return self._geometry(points)[0]

    def potential(self, points):
        if not self.strength:
            return np.zeros(positions(points).shape[:-1])
        _, rho, uncertainty = self._geometry(points)
        _reject_unresolved(rho, uncertainty, "line-source potential is singular on its axis")
        return -2 * self.coefficient * np.log(rho / self.reference_radius)

    def field(self, points):
        if not self.strength:
            return np.zeros_like(positions(points))
        d, rho, uncertainty = self._geometry(points)
        _reject_unresolved(rho, uncertainty, "line-source field is singular on its axis")
        return 2 * self.coefficient * d / rho[..., None] ** 2


@dataclass(frozen=True)
class InfinitePlane(Source):
    normal: tuple = (0.0, 0.0, 1.0)
    trajectory_safe = False

    def __post_init__(self):
        super().__post_init__()
        n = np.array(vector(self.normal, "normal"))
        length = np.linalg.norm(n)
        if not np.isfinite(length) or length == 0:
            raise ValueError("normal must have a finite nonzero length")
        object.__setattr__(self, "normal", tuple(n / length))

    def distance(self, points):
        return np.sum(self.displacement(points) * self.normal, axis=-1)

    def potential(self, points):
        return -2 * np.pi * self.coefficient * np.abs(self.distance(points))

    def field(self, points):
        delta, error = self._displacement_with_error(points)
        n = np.array(self.normal)
        d = np.sum(delta * n, axis=-1)
        if self.strength:
            uncertainty = (_gamma(16) * np.sum(np.abs(delta * n), axis=-1)
                           + np.sum(error * np.abs(n), axis=-1))
            _reject_unresolved(d, uncertainty,
                               "plane field has two one-sided limits on its surface")
        return 2 * np.pi * self.coefficient * np.sign(d)[..., None] * n


@dataclass(frozen=True)
class UniformField:
    kind: str
    value: tuple
    origin: tuple = (0.0, 0.0, 0.0)
    trajectory_safe = True

    def __post_init__(self):
        check_kind(self.kind)
        object.__setattr__(self, "value", vector(self.value, "value"))
        object.__setattr__(self, "origin", vector(self.origin, "origin"))

    def field(self, points):
        return np.broadcast_to(self.value, positions(points).shape).copy()

    def potential(self, points):
        return -np.sum((positions(points) - self.origin) * self.value, axis=-1)


@dataclass(frozen=True)
class Superposition:
    """No apparatus profiles: compose any nonempty collection of one physical kind."""
    sources: tuple

    def __post_init__(self):
        sources = tuple(self.sources)
        if not sources:
            raise ValueError("superposition needs at least one source")
        check_kind(sources[0].kind)
        if any(s.kind != sources[0].kind for s in sources):
            raise ValueError("electric and gravitational potentials have different units")
        object.__setattr__(self, "sources", sources)

    @property
    def kind(self):
        return self.sources[0].kind

    @property
    def trajectory_safe(self):
        return all(s.trajectory_safe for s in self.sources)

    def field(self, points):
        p = positions(points)
        return sum((s.field(p) for s in self.sources), np.zeros_like(p))

    def potential(self, points):
        p = positions(points)
        return sum((s.potential(p) for s in self.sources), np.zeros(p.shape[:-1]))


def iter_sources(model):
    """Yield composition leaves in authored order, retaining repeated references."""
    if isinstance(model, Superposition):
        for source in model.sources:
            yield from iter_sources(source)
    else:
        yield model
