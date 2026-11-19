"""Read-only renderer-neutral magnetic-loop display, never imports PyVista/VTK."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import numpy as np
from .wire_magnetism import WireState, sample_ampere_loop, _report_from_samples


def _immutable(a):
    v = np.ascontiguousarray(a, dtype=np.float64)
    return np.frombuffer(v.tobytes(), dtype=np.float64).reshape(v.shape)


@dataclass(frozen=True)
class WirePresentation:
    state: WireState
    loop_positions_m: np.ndarray
    tangent_unit: np.ndarray
    magnetic_field_T: np.ndarray
    arc_weights_m: np.ndarray
    loop_display_xyz: np.ndarray
    arrow_display_origins_xyz: np.ndarray
    arrow_display_vectors: np.ndarray
    wire_display_endpoints_xyz: np.ndarray
    report: object


def prepare(state: WireState):
    samples = sample_ampere_loop(state)
    physical_points = samples['points_m']
    unit = np.asarray(state.axis_direction)
    display_points = (physical_points - state.origin_m) / state.loop_radius_m
    field = samples['field_T']
    n = state.samples_per_loop
    idx = np.arange(0,n,max(1,n//12))
    magnitudes = np.linalg.norm(field[idx],axis=1)
    arrow_dirs = np.zeros((len(idx),3))
    nz = magnitudes > 0
    arrow_dirs[nz] = 0.42 * field[idx[nz]]/magnitudes[nz,None]
    # Schematic 4R-long wire segment, independent of physical wire length.
    wire_endpoints = np.vstack((-2.2*unit,2.2*unit))
    m = _report_from_samples(state, samples)
    m['arrow_display_scale_schematic'] = True
    # Viewers receive only detached read-only buffers and scalar physical report.
    return WirePresentation(state,_immutable(physical_points),_immutable(samples['tangents']),
        _immutable(field),_immutable(samples['arc_weights_m']),
        _immutable(display_points),_immutable(display_points[idx]),
        _immutable(arrow_dirs),_immutable(wire_endpoints),MappingProxyType(m))
