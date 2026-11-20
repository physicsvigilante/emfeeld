"""Immutable renderer-neutral SI and schematic view data for rectangular-loop torque.

All physical vectors are taken from the analytic model. No PyVista/VTK imports.
No glyph scale, camera location or mesh geometry contributes to SI quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .rectangular_loop_torque import RectangularLoopState, calculate, measure


def _readonly(value):
    v = np.ascontiguousarray(value, dtype=np.float64)
    return np.frombuffer(v.tobytes(), dtype=np.float64).reshape(v.shape)


def _direction_glyph(v, length, *, threshold=0.0):
    mag = float(np.linalg.norm(v))
    if mag <= threshold:
        return np.zeros(3, dtype=float)
    return length * np.asarray(v) / mag


@dataclass(frozen=True)
class TorquePresentation:
    state: RectangularLoopState
    loop_corners_m: np.ndarray
    side_midpoints_m: np.ndarray
    edge_vectors_m: np.ndarray
    normal_unit: np.ndarray
    field_B_T: np.ndarray
    magnetic_moment_A_m2: np.ndarray
    torque_N_m: np.ndarray
    segment_forces_N: np.ndarray
    loop_display_xyz: np.ndarray
    side_force_origins_display_xyz: np.ndarray
    side_force_vectors_display_xyz: np.ndarray
    current_direction_display_xyz: np.ndarray
    positive_normal_display_xyz: np.ndarray
    field_B_direction_display_xyz: np.ndarray
    magnetic_moment_display_xyz: np.ndarray
    torque_direction_display_xyz: np.ndarray
    reference_length_m: float
    report: object


def prepare(state: RectangularLoopState, *, reference_length_m=None):
    if not isinstance(state, RectangularLoopState):
        raise ValueError("requires validated RectangularLoopState")
    reference = max(state.width_m, state.height_m) if reference_length_m is None else reference_length_m
    if type(reference) not in (int, float) or not np.isfinite(reference) or not .001 <= reference <= 10:
        raise ValueError("display reference must be a finite initial dimension")
    physical, _ = calculate(state)
    corners = physical["loop_corners_m"]
    midpoints = physical["side_midpoints_m"]
    centre = np.asarray(state.centre_m)
    forces = physical["forces_N"]
    max_force = float(np.max(np.linalg.norm(forces, axis=1)))
    # Do not draw residual numerical glyphs along a segment parallel to B.
    floor = 64 * np.finfo(float).eps * max_force
    force_glyphs = np.asarray([
        _direction_glyph(f, .37, threshold=floor) for f in forces
    ])
    B = physical["field_B_T"]
    m = physical["moment_A_m2"]
    torque = physical["torque_N_m"]
    current_direction = (np.sign(state.current_A) * physical["width_unit"] * .44
                         if state.current_A else np.zeros(3))
    si_report = measure(state)
    for key in ("field_B_xyz_T", "moment_xyz_A_m2", "torque_xyz_N_m",
                "net_force_xyz_N", "segment_torque_xyz_N_m"):
        si_report[key] = tuple(si_report[key])
    return TorquePresentation(
        state,
        _readonly(corners), _readonly(midpoints), _readonly(physical["edge_vectors_m"]),
        _readonly(physical["normal_unit"]), _readonly(B), _readonly(m),
        _readonly(torque), _readonly(forces),
        _readonly((corners - centre) / reference),
        _readonly((midpoints - centre) / reference),
        _readonly(force_glyphs), _readonly(current_direction),
        _readonly(.46 * physical["normal_unit"]),
        _readonly(_direction_glyph(B, .85)),
        _readonly(_direction_glyph(m, .68)),
        _readonly(_direction_glyph(torque, .73)),
        float(reference),
        MappingProxyType(si_report)
    )
