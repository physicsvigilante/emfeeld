"""Static prescribed sources. SI everywhere; field = -gradient(potential)."""
from dataclasses import dataclass
from typing import Protocol
import numpy as np
from scipy.constants import G, epsilon_0

K = 1.0 / (4.0 * np.pi * epsilon_0)
KINDS = ("electric", "gravity")


class DomainError(ValueError):
    """A field or potential was requested where this idealization is undefined."""


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
        d = self.displacement(points)
        r = np.linalg.norm(d, axis=-1)
        if self.strength and np.any(r == self.radius):
            raise DomainError("shell field has two one-sided limits at its surface")
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

    def perpendicular(self, points):
        d = self.displacement(points)
        a = np.array(self.direction)
        return d - np.sum(d * a, axis=-1)[..., None] * a

    def potential(self, points):
        rho = np.linalg.norm(self.perpendicular(points), axis=-1)
        if not self.strength:
            return np.zeros_like(rho)
        if np.any(rho == 0):
            raise DomainError("line-source potential is singular on its axis")
        return -2 * self.coefficient * np.log(rho / self.reference_radius)

    def field(self, points):
        d = self.perpendicular(points)
        rho = np.linalg.norm(d, axis=-1)
        if not self.strength:
            return np.zeros_like(d)
        if np.any(rho == 0):
            raise DomainError("line-source field is singular on its axis")
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
        d = self.distance(points)
        if self.strength and np.any(d == 0):
            raise DomainError("plane field has two one-sided limits on its surface")
        return 2 * np.pi * self.coefficient * np.sign(d)[..., None] * np.array(self.normal)


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
