"""Numerical sums with individual contributions retained for later teaching UI."""
from dataclasses import dataclass
import numpy as np
from .fields import positions, scalar, vector


def line_contributions(model, vertices):
    """Midpoint approximations to field dot dl, one per straight segment.

    Their negative sum approximates the endpoint potential difference. This is
    not a quadrature error estimate: compare successively refined paths.
    """
    p = positions(vertices)
    if p.ndim != 2 or len(p) < 2:
        raise ValueError("path must have shape (N, 3), with N >= 2")
    return np.sum(model.field((p[:-1] + p[1:]) / 2) * np.diff(p, axis=0), axis=1)


@dataclass(frozen=True)
class FluxSum:
    positions_m: np.ndarray
    normals: np.ndarray
    area_weights_m2: np.ndarray
    contributions: np.ndarray

    @property
    def total(self):
        return float(self.contributions.sum())


def sphere_flux(model, center, radius_m, *, n_polar=24, n_azimuth=48):
    """Gauss-Legendre in cos(theta), periodic midpoint rule in phi.

    The positive weights are quadrature area weights, NOT geometric patch areas.
    Invalid source/surface intersections raise rather than silently removing flux.
    """
    c = np.array(vector(center, "center"))
    radius = scalar(radius_m, "radius_m", positive=True)
    for name, count in (("n_polar", n_polar), ("n_azimuth", n_azimuth)):
        if isinstance(count, bool) or not isinstance(count, int) or count < 2:
            raise ValueError(f"{name} must be an integer >= 2")
    mu, weights = np.polynomial.legendre.leggauss(n_polar)
    phi = (np.arange(n_azimuth) + 0.5) * 2 * np.pi / n_azimuth
    z, a = np.meshgrid(mu, phi, indexing="ij")
    xy = np.sqrt(1 - z * z)
    normals = np.stack((xy * np.cos(a), xy * np.sin(a), z), axis=-1).reshape(-1, 3)
    points = c + radius * normals
    areas = np.repeat(weights, n_azimuth) * radius**2 * 2 * np.pi / n_azimuth
    contributions = np.sum(model.field(points) * normals, axis=1) * areas
    return FluxSum(points, normals, areas, contributions)
