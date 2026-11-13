"""Composable analytic field explorer; all public quantities use SI units."""
from .fields import (DomainError, PointSource, SolidSphere, SphericalShell,
                     InfiniteLine, InfinitePlane, UniformField, Superposition)
from .dynamics import Particle, Trajectory, integrate
from .integrals import line_contributions, sphere_flux
from .scene import Scene, load_scene, scene_from_dict

__all__ = ["DomainError", "PointSource", "SolidSphere", "SphericalShell", "InfiniteLine",
           "InfinitePlane", "UniformField", "Superposition", "Particle", "Trajectory",
           "integrate", "line_contributions", "sphere_flux", "Scene", "load_scene", "scene_from_dict"]
