"""Renderer-neutral Gauss lesson samples; no PyVista/VTK and no new field law.

All coordinates are SI. Surface tessellation is for drawing/probing, not flux
integration: the unchanged gauss_lesson.measure owns the physical flux report.
A controller prepares a result after a physical edit; renderers only read it.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

import numpy as np
from scipy.constants import epsilon_0

from .gauss_lesson import GaussState, GaussianCube, GaussianSphere, _HeldCoulombField, measure

FACE_NAMES = ('+x', '-x', '+y', '-y', '+z', '-z')
SAMPLING_CAUTION_FRACTION = 0.01  # Attention only, not a physical tolerance.


def _readonly(values, dtype=float):
    """Detached immutable storage (even setflags(write=True) cannot expose a writer)."""
    a = np.ascontiguousarray(values, dtype=dtype)
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


def sampling_caution(state, report):
    """Preserve the existing V1 display-only discrepancy warning exactly."""
    if not isinstance(state.surface, GaussianSphere) or report['status'] != 'available':
        return None
    scale = math.fsum(abs(c.charge_C) for c in state.charges) / epsilon_0
    discrepancy = abs(report['sampling_error_N_m2_per_C'])
    threshold = SAMPLING_CAUTION_FRACTION * scale
    return {'large_discrepancy': discrepancy > threshold,
            'absolute_discrepancy_N_m2_per_C': discrepancy,
            'charge_flux_scale_N_m2_per_C': scale,
            'attention_threshold_N_m2_per_C': threshold,
            'threshold_fraction': SAMPLING_CAUTION_FRACTION,
            'is_accuracy_certificate': False}


@dataclass(frozen=True, eq=False)
class SurfaceGeometry:
    points_m: np.ndarray
    cells: np.ndarray  # rows of [count, vertex IDs ...], triangles or quads
    probes_m: np.ndarray
    outward_normals: np.ndarray
    face_indices: np.ndarray  # cube-local 0..5; -1 for sphere
    outline_points_m: np.ndarray
    outline_edges: np.ndarray
    face_centers_m: np.ndarray
    face_normals: np.ndarray


def build_surface(state, *, resolution=12):
    """Closed cube/sphere with outward winding and probes on the analytic surface.

    Cube vertices/probes retain the V1 ordering/arithmetic. Sphere connectivity
    retains longitude/latitude triangles, but uses float64 analytic angles rather
    than VTK's float32 point generator. This is a declared display-only change;
    neither the physical sphere quadrature nor exact total is derived from it.
    """
    if not isinstance(state, GaussState):
        raise ValueError('requires a validated GaussState')
    if type(resolution) is not int or not 4 <= resolution <= 40:
        raise ValueError('display resolution must be an integer in [4,40]')
    s, scale = state.surface, state.scale_m
    center = np.asarray(s.center_m)
    outline, edges, face_centers, face_normals = (np.empty((0, 3)), np.empty((0, 2), int),
                                               np.empty((0, 3)), np.empty((0, 3)))
    if isinstance(s, GaussianCube):
        vertices, normals = [], []
        edge, axes = np.linspace(-1., 1., resolution + 1), np.eye(3)
        for axis in range(3):
            for sign in (1., -1.):
                n = sign * axes[axis]
                u, v = axes[(axis + 1) % 3], sign * axes[(axis + 2) % 3]
                for a, b in zip(edge[:-1], edge[1:]):
                    for c, d in zip(edge[:-1], edge[1:]):
                        vertices.extend([n+a*u+c*v, n+b*u+c*v, n+b*u+d*v, n+a*u+d*v])
                        normals.append(n)
        rotation = np.asarray(s.rotation)
        points = center + scale * (np.asarray(vertices) @ rotation.T)
        cells = np.c_[np.full(len(normals), 4), np.arange(len(points)).reshape(-1, 4)]
        probes = points.reshape(-1, 4, 3).mean(axis=1)
        normals = np.asarray(normals) @ rotation.T
        face_indices = np.repeat(np.arange(6), resolution ** 2)
        corners = np.array([[x, y, z] for x in (-1., 1.) for y in (-1., 1.) for z in (-1., 1.)])
        edges = np.array([(i, j) for i in range(8) for j in range(i+1, 8)
                          if np.count_nonzero(corners[i] != corners[j]) == 1])
        outline = center + scale * (corners @ rotation.T)
        face_normals = np.array([sign*np.eye(3)[axis] for axis in range(3)
                                 for sign in (1., -1.)]) @ rotation.T
        face_centers = center + scale * face_normals
    else:
        nt, npolar = 3 * resolution, 2 * resolution
        ring = npolar - 2
        vertices = [(0., 0., 1.), (0., 0., -1.)]
        for i in range(nt):
            theta = 2 * math.pi * i / nt
            for j in range(1, npolar - 1):
                phi = math.pi * j / (npolar - 1)
                vertices.append((math.sin(phi)*math.cos(theta), math.sin(phi)*math.sin(theta), math.cos(phi)))
        unit = np.array(vertices)
        unit /= np.linalg.norm(unit, axis=1)[:, None]
        triangles = [(2+i*ring, 2+((i+1) % nt)*ring, 0) for i in range(nt)]
        triangles += [(1+(i+1)*ring, 1, 1+(((i+1) % nt)+1)*ring) for i in range(nt)]
        for i in range(nt):
            for j in range(ring - 1):
                a, b = 2+i*ring+j, 2+((i+1) % nt)*ring+j
                triangles.extend(((a, a+1, b+1), (a, b+1, b)))
        triangles = np.asarray(triangles, dtype=int)
        cells = np.c_[np.full(len(triangles), 3), triangles]
        normals = unit[triangles].mean(axis=1)
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        probes = center + scale * normals
        points = center + scale * unit
        face_indices = np.full(len(cells), -1)
    return SurfaceGeometry(_readonly(points), _readonly(cells, int), _readonly(probes),
                           _readonly(normals), _readonly(face_indices, int),
                           _readonly(outline), _readonly(edges, int),
                           _readonly(face_centers), _readonly(face_normals))


@dataclass(frozen=True, eq=False)
class GaussPresentation:
    state: GaussState
    resolution: int
    order: int
    surface: SurfaceGeometry
    report: Mapping
    field_N_C: np.ndarray | None
    normal_field_N_C: np.ndarray | None
    color_limits_N_C: tuple | None
    caution: Mapping | None


def build_presentation(state, *, resolution=12, order=24):
    """Prepare an immutable snapshot using only the already qualified physics."""
    report = measure(state, order=order)
    geometry = build_surface(state, resolution=resolution)
    fields = normal = limits = None
    if report['status'] == 'available':
        fields = _HeldCoulombField(state.charges).field(geometry.probes_m)
        normal = np.einsum('ij,ij->i', fields, geometry.outward_normals)
        peak = max(float(np.max(np.abs(normal))), 1e-30)
        limits = (-peak, peak)
        fields, normal = _readonly(fields), _readonly(normal)
    caution = sampling_caution(state, report)
    return GaussPresentation(state, resolution, order, geometry, MappingProxyType(report),
                             fields, normal, limits,
                             None if caution is None else MappingProxyType(caution))


class PresentationCache:
    """One immutable result: display-only changes cannot invalidate physical data."""
    def __init__(self):
        self._value = None
        self.build_count = 0

    def get(self, state, *, resolution=12, order=24):
        previous = self._value
        # Check scalar types before equality: True == 1 and 12.0 == 12.
        if type(resolution) is not int or type(order) is not int:
            raise ValueError('resolution and order must be integers')
        if (previous is None or previous.state != state or previous.resolution != resolution
                or previous.order != order):
            proposed = build_presentation(state, resolution=resolution, order=order)
            self._value = proposed  # Commit only after complete successful preparation.
            self.build_count += 1
        return self._value
