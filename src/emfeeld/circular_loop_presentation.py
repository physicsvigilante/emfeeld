"""Renderer-independent, immutable physical and schematic circular-loop data."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import numpy as np

from .circular_loop_magnetism import CircularLoopState, axis_field, basis, measure


def _readonly(values):
    arr = np.ascontiguousarray(values, dtype=np.float64)
    return np.frombuffer(arr.tobytes(), dtype=np.float64).reshape(arr.shape)


@dataclass(frozen=True)
class CircularLoopPresentation:
    state: CircularLoopState
    loop_positions_m: np.ndarray
    positive_current_tangent: np.ndarray
    field_probe_T: np.ndarray
    field_centre_T: np.ndarray
    loop_display_xyz: np.ndarray
    probe_display_xyz: np.ndarray
    current_arrow_display_xyz: np.ndarray
    field_arrow_display_xyz: np.ndarray
    display_reference_radius_m: float
    loop_radius_display_reference_units: float
    report: object


def prepare(state: CircularLoopState, *, display_reference_radius_m=None) -> CircularLoopPresentation:
    """Visual geometry is in units of a reference radius, never used for SI B."""
    reference = state.radius_m if display_reference_radius_m is None else display_reference_radius_m
    if type(reference) not in (int, float) or not np.isfinite(reference) or not 1e-3 <= reference <= 100:
        raise ValueError("display reference radius must be finite and inside lesson domain")
    scale = state.radius_m / reference
    u, e1, e2 = basis(state)
    phi = np.linspace(0.0, 2.0*np.pi, state.samples_per_loop, endpoint=False)
    circle = np.cos(phi)[:, None]*e1 + np.sin(phi)[:, None]*e2
    tangent = -np.sin(phi)[:, None]*e1 + np.cos(phi)[:, None]*e2
    points = np.asarray(state.centre_m)[None, :] + state.radius_m*circle
    centre_field = axis_field(state, 0.0)
    probe_field = axis_field(state)
    # Display uses dimensionless coordinates and constant glyph sizes: never
    # interpreted as SI field strengths, even when radius is edited.
    probe_display = (state.probe_z_m / reference)*u
    current_sign = np.sign(state.current_A)
    current_arrow = 0.5*current_sign*tangent[0] if current_sign else np.zeros(3)
    probe_sign = np.sign(np.dot(probe_field, u))
    field_arrow = 0.7*probe_sign*u if probe_sign else np.zeros(3)
    return CircularLoopPresentation(
        state, _readonly(points), _readonly(tangent),
        _readonly(probe_field), _readonly(centre_field),
        _readonly(circle*scale), _readonly(probe_display),
        _readonly(current_arrow), _readonly(field_arrow),
        float(reference), float(scale), MappingProxyType(measure(state)))
