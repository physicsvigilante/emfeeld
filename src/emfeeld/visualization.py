"""Renderer-neutral snapshot of one general EMFEELD scene.

Physical samples remain in SI; drawing sizes, truncated infinite sources and
field direction glyphs are explicitly schematic. This module imports neither
PyVista nor VTK, and never changes any physical source or trajectory.

Not a new source-authoring or evidence schema: a second renderer may consume
``VisualizationData`` or the explicitly versioned, JSON-compatible ``to_dict``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import warnings

import numpy as np

from .fields import (DomainError, PointSource, SolidSphere, SphericalShell,
                     InfiniteLine, InfinitePlane, UniformField, iter_sources)


def sample_values(model, points, *, potential=False):
    """Preserve undefined samples as NaN, without discarding valid neighbors.

    Exactly the general viewer's historical DomainError-bisection sampler;
    simulation measurements and source field laws are not changed.
    """
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("sampling points must have shape (N, 3)")
    result = np.full(len(points) if potential else points.shape, np.nan)
    evaluate = model.potential if potential else model.field

    def fill(start, end):
        if start == end:
            return
        try:
            result[start:end] = evaluate(points[start:end])
        except DomainError:
            if end - start > 1:
                middle = (start + end) // 2
                fill(start, middle)
                fill(middle, end)
    fill(0, len(points))
    return result


def _array(values):
    """A detached read-only float64 snapshot, never a view of solver output."""
    a = np.array(values, dtype=float, copy=True)
    a.setflags(write=False)
    return a


def _json_array(values):
    """JSON has no NaN: undefined field probes are explicit null values."""
    a = np.asarray(values)
    if a.ndim == 0:
        return float(a) if np.isfinite(a) else None
    return [_json_array(row) for row in a]


@dataclass(frozen=True)
class Units:
    position: str
    time: str
    field: str
    potential: str


@dataclass(frozen=True)
class SourceGeometry:
    id: str
    shape: str             # point, sphere, shell, line, plane, none
    role: str              # physical_extent, schematic_marker, truncated_infinite, no_shape
    center_m: tuple
    radius_m: float | None = None
    direction: tuple | None = None
    display_span_m: float | None = None
    strength_SI: float | None = None
    strength_unit: str | None = None
    field_vector_SI: tuple | None = None


@dataclass(frozen=True)
class PotentialGrid:
    """Physical scalar samples on an XY slice, not a material surface.

    Grid arrays are indexed (x, y). Samples follow VTK's column-major
    StructuredGrid point order, documented here rather than coupled to VTK.
    """
    points_m: np.ndarray           # (nx, ny, 3)
    values: np.ndarray             # flattened with x changing fastest
    unit: str
    role: str = "physical_potential_samples_on_display_slice"


@dataclass(frozen=True)
class FieldSamples:
    positions_m: np.ndarray        # (N, 3), physical probes
    vectors_SI: np.ndarray         # (N, 3), real fields; NaN means undefined
    unit: str
    arrow_origins_m: np.ndarray    # valid nonzero physical samples only
    arrow_directions: np.ndarray  # unit directions, NOT field magnitudes
    arrow_length_m: float         # schematic constant display length
    role: str = "schematic_field_direction_glyphs_not_field_lines"


@dataclass(frozen=True)
class TrajectoryVisual:
    id: str
    positions_m: np.ndarray
    marker_radius_m: float       # schematic screen legibility, not a particle radius
    role: str = "calculated_test_particle_trajectory_not_field_line"
    marker_role: str = "schematic_particle_marker_not_physical_size_or_charge_sign"


@dataclass(frozen=True)
class Annotation:
    id: str
    text: str
    role: str = "display_annotation"


@dataclass(frozen=True)
class VisualizationFrame:
    """One saved physical sample selected for display (not a new integration)."""
    index: int
    time_s: float
    positions_m: tuple[tuple[float, float, float], ...]
    role: str = "saved_trajectory_sample_display_only"


@dataclass(frozen=True)
class VisualizationData:
    title: str
    bounds_m: tuple
    units: Units
    potential: PotentialGrid
    field: FieldSamples
    geometry: tuple[SourceGeometry, ...]
    trajectories: tuple[TrajectoryVisual, ...]
    annotations: tuple[Annotation, ...]
    duration_s: float
    samples: int
    has_uniform_source: bool
    missing_geometry: tuple[str, ...]
    moving_slice: bool

    def frame(self, index: int) -> VisualizationFrame:
        """A renderer-independent animation state; no interpolation or solving."""
        if type(index) is not int or not 0 <= index < self.samples:
            raise ValueError("frame index outside saved sample range")
        positions = tuple(tuple(float(v) for v in path.positions_m[index])
                          for path in self.trajectories)
        return VisualizationFrame(index, self.duration_s * (index / (self.samples - 1)),
                                  positions)

    def to_dict(self) -> dict:
        """Portable JSON-compatible V1 snapshot; undefined samples become null.

        Intended for a *future* consumer; not a simulation authoring packet.
        Physical fields and schematic glyphs have separate keys and meanings.
        """
        return {
            "visualization_version": 1, "title": self.title,
            "bounds_m": list(self.bounds_m), "units": vars(self.units),
            "potential": {"role": self.potential.role, "unit": self.potential.unit,
                          "points_m": _json_array(self.potential.points_m),
                          "values": _json_array(self.potential.values),
                          "sample_order": "x_fastest_fortran"},
            "field": {"role": self.field.role, "unit": self.field.unit,
                      "positions_m": _json_array(self.field.positions_m),
                      "vectors_SI": _json_array(self.field.vectors_SI),
                      "schematic_arrows": {
                          "origins_m": _json_array(self.field.arrow_origins_m),
                          "unit_directions": _json_array(self.field.arrow_directions),
                          "display_length_m": self.field.arrow_length_m,
                          "not_calibrated_field_lines": True}},
            "geometry": [vars(g) for g in self.geometry],
            "trajectories": [{"id": p.id, "role": p.role,
                              "positions_m": _json_array(p.positions_m),
                              "marker_radius_m": p.marker_radius_m,
                              "marker_role": p.marker_role} for p in self.trajectories],
            "annotations": [vars(a) for a in self.annotations],
            "animation": {"duration_s": self.duration_s, "samples": self.samples,
                          "time_unit": "s", "role": "saved_trajectory_sample_display_only"},
            "has_uniform_source": self.has_uniform_source,
            "missing_geometry": list(self.missing_geometry),
            "moving_slice": self.moving_slice,
        }


def _source_geometry(source, index, span, kind):
    center = tuple(source.origin if isinstance(source, UniformField) else
                   getattr(source, "center", (0., 0., 0.)))
    sid = f"source_{index}"
    if isinstance(source, SolidSphere):
        shape = "shell" if isinstance(source, SphericalShell) else "sphere"
        return SourceGeometry(sid, shape, "physical_extent", center,
                              radius_m=float(source.radius), strength_SI=source.strength,
                              strength_unit="C" if kind == "electric" else "kg")
    if isinstance(source, PointSource):
        return SourceGeometry(sid, "point", "schematic_marker", center,
                              strength_SI=source.strength,
                              strength_unit="C" if kind == "electric" else "kg")
    if isinstance(source, InfiniteLine):
        return SourceGeometry(sid, "line", "truncated_infinite_source", center,
                              direction=tuple(source.direction), display_span_m=span,
                              strength_SI=source.strength,
                              strength_unit="C/m" if kind == "electric" else "kg/m")
    if isinstance(source, InfinitePlane):
        return SourceGeometry(sid, "plane", "truncated_infinite_source", center,
                              direction=tuple(source.normal), display_span_m=span,
                              strength_SI=source.strength,
                              strength_unit="C/m²" if kind == "electric" else "kg/m²")
    if isinstance(source, UniformField):
        return SourceGeometry(sid, "none", "uniform_field_has_no_source_shape", center,
                              field_vector_SI=tuple(source.value))
    return None


def build_visualization(scene, *, resolution=41, recorded=None,
                        sampler: Callable = sample_values) -> VisualizationData:
    """Physics/scene → inert data; requires NumPy only, never PyVista/VTK.

    This samples *the existing* analytic model and uses existing saved or
    already-integrated trajectories. No dynamics, field law or value is changed.
    """
    if type(resolution) is not int or not 5 <= resolution <= 101:
        raise ValueError("resolution must be an integer from 5 through 101")
    kind = scene.model.kind
    bounds = tuple(scene.bounds_m)
    a = np.asarray(bounds, dtype=float)
    lower, upper = a[::2], a[1::2]
    center = (lower + upper) / 2
    span = float(np.max(upper - lower))
    units = Units("m", "s", "N/C" if kind == "electric" else "m/s²",
                  "V" if kind == "electric" else "J/kg")

    x, y = np.meshgrid(np.linspace(lower[0], upper[0], resolution),
                       np.linspace(lower[1], upper[1], resolution), indexing="ij")
    z = np.full_like(x, center[2])
    grid_points = np.stack((x, y, z), axis=-1)
    # PyVista/VTK StructuredGrid flattens x, y, z with x fastest (Fortran).
    flat_grid = np.column_stack((x.ravel(order="F"), y.ravel(order="F"), z.ravel(order="F")))
    scalar_samples = sampler(scene.model, flat_grid, potential=True)
    potential = PotentialGrid(_array(grid_points), _array(scalar_samples), units.potential)

    axes = [np.linspace(v0, v1, 7) for v0, v1 in zip(lower, upper)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    field_vectors = sampler(scene.model, points)
    norm = np.linalg.norm(field_vectors, axis=1)
    valid = np.isfinite(field_vectors).all(axis=1) & (norm > 0)
    field = FieldSamples(_array(points), _array(field_vectors), units.field,
                         _array(points[valid]), _array(field_vectors[valid] / norm[valid, None]),
                         span / 35)

    geometries = []
    missing = set()
    has_uniform = False
    for i, source in enumerate(iter_sources(scene.model)):
        geo = _source_geometry(source, i, span, kind)
        if geo is None:
            name = type(source).__name__
            missing.add(name)
            warnings.warn(f"No geometry adapter for {name}; its field and potential are still included.",
                          RuntimeWarning, stacklevel=2)
        else:
            if geo.shape == "none":
                has_uniform = True
            geometries.append(geo)

    values = scene.trajectories() if recorded is None else recorded
    trajectories = tuple(TrajectoryVisual(f"particle_{i}", _array(t.position_m), 0.025 * span)
                         for i, t in enumerate(values))
    notes = []
    if trajectories:
        notes.extend((
            Annotation("particle_key", "Magenta: test particles\n"
                       "Schematic sphere; not physical size.\n"
                       "Colour is not charge sign.\n"
                       "Black: calculated paths\n"
                       "(not field lines)."),
            Annotation("playback_help", "Space: play / pause\nHome: restart paused\n"
                       "Left / Right: one sample\n\nDisplay time, not physical time"),
        ))
    geometry_note = "\nUniform fields have no source shape." if has_uniform else ""
    if missing:
        geometry_note += "\nGeometry not drawn for: " + ", ".join(sorted(missing)) + "."
    notes.append(Annotation("geometry_key",
                            "Arrows: direction only (equal lengths). Coordinates: metres.\n"
                            "Point/particle markers schematic; line/plane renderings truncated.\n"
                            "Potential references differ by source; no collisions or backreaction."
                            + geometry_note))

    return VisualizationData(scene.title, bounds, units, potential, field,
                             tuple(geometries), trajectories, tuple(notes),
                             scene.duration_s, scene.samples, has_uniform,
                             tuple(sorted(missing)),
                             bool(getattr(scene, "particles", ())) or bool(recorded))
