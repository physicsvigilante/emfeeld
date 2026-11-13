"""Optional PyVista desktop preview. Physics never depends on this sampling grid."""
import warnings
import numpy as np
from .fields import (DomainError, PointSource, SolidSphere, SphericalShell,
                     InfiniteLine, InfinitePlane, UniformField, iter_sources)


def sample_values(model, points, *, potential=False):
    """Preserve undefined samples as NaN, without discarding valid neighbors."""
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


def make_plotter(scene, *, resolution=41, off_screen=False):
    """Return a plotter with sources, field directions, potential slice and time scrubber.

    This initial preview has no field lines, integral animation, or autoplay.
    Point/particle markers have schematic screen sizes. Line/plane patches are
    explicitly finite renderings of infinite sources, not physical boundaries.
    """
    try:
        import pyvista as pv
    except ImportError as exc:
        raise RuntimeError('3D viewer requires: python -m pip install -e ".[view]"') from exc
    if type(resolution) is not int or not 5 <= resolution <= 101:
        raise ValueError("resolution must be an integer from 5 through 101")
    bounds = np.array(scene.bounds_m)
    lower, upper = bounds[::2], bounds[1::2]
    center = (lower + upper) / 2
    span = float(np.max(upper - lower))
    plot = pv.Plotter(off_screen=off_screen, window_size=(1200, 850))
    plot.add_title(scene.title, font_size=14)
    unit = "V" if scene.model.kind == "electric" else "J/kg"
    x, y = np.meshgrid(np.linspace(lower[0], upper[0], resolution),
                       np.linspace(lower[1], upper[1], resolution), indexing="ij")
    z = np.full_like(x, center[2])
    plane = pv.StructuredGrid(x, y, z)
    plane["potential"] = sample_values(scene.model, plane.points, potential=True)
    if np.isfinite(plane["potential"]).any():
        plot.add_mesh(plane, scalars="potential", opacity=0.7, nan_opacity=0,
                      scalar_bar_args={"title": f"Potential [{unit}]"})
    axes = [np.linspace(a, b, 7) for a, b in zip(lower, upper)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    field = sample_values(scene.model, points)
    norm = np.linalg.norm(field, axis=1)
    valid = np.isfinite(field).all(axis=1) & (norm > 0)
    if valid.any():
        cloud = pv.PolyData(points[valid])
        cloud["direction"] = field[valid] / norm[valid, None]
        arrows = cloud.glyph(orient="direction", scale=False, factor=span / 35)
        plot.add_mesh(arrows, show_scalar_bar=False)
    missing_geometry = set()
    has_uniform = False
    for source in iter_sources(scene.model):
        if isinstance(source, SolidSphere):
            mesh = pv.Sphere(radius=source.radius, center=source.center)
            plot.add_mesh(mesh, opacity=0.18,
                          style="wireframe" if isinstance(source, SphericalShell) else "surface")
        elif isinstance(source, PointSource):
            plot.add_points(np.array([source.center]), point_size=14, render_points_as_spheres=True)
        elif isinstance(source, InfiniteLine):
            c, a = np.array(source.center), np.array(source.direction)
            plot.add_mesh(pv.Line(c - span * a, c + span * a), line_width=4)
        elif isinstance(source, InfinitePlane):
            plot.add_mesh(pv.Plane(center=source.center, direction=source.normal,
                                   i_size=span, j_size=span), opacity=0.12)
        elif isinstance(source, UniformField):
            has_uniform = True  # A uniform field intentionally has no source shape.
        else:
            name = type(source).__name__
            missing_geometry.add(name)
            warnings.warn(f"No geometry adapter for {name}; its field and potential are still included.",
                          RuntimeWarning, stacklevel=2)
    trajectories = scene.trajectories()
    markers = []
    for trajectory in trajectories:
        plot.add_mesh(pv.lines_from_points(trajectory.position_m), line_width=3)
        marker = pv.PolyData(trajectory.position_m[:1].copy())
        plot.add_mesh(marker, point_size=14, render_points_as_spheres=True)
        markers.append(marker)

    def scrub(time):
        index = int(np.clip(round(time / scene.duration_s * (scene.samples - 1)),
                            0, scene.samples - 1))
        for marker, trajectory in zip(markers, trajectories):
            marker.points = trajectory.position_m[index:index + 1].copy()
        plot.add_text(f"Sample time: {index * scene.duration_s / (scene.samples - 1):.6g} s",
                      position="upper_left", name="time", font_size=10)
    if trajectories:
        plot.add_slider_widget(scrub, (0, scene.duration_s), value=0,
                               title="Time [s]", pointa=(0.25, 0.9), pointb=(0.75, 0.9))
    geometry_note = "\nUniform fields have no source shape." if has_uniform else ""
    if missing_geometry:
        geometry_note += "\nGeometry not drawn for: " + ", ".join(sorted(missing_geometry)) + "."
    plot.add_text("Arrows: direction only (equal lengths). Coordinates: metres.\n"
                  "Point/particle markers schematic; line/plane renderings truncated.\n"
                  "Potential references differ by source; no collisions or backreaction."
                  + geometry_note, position="lower_left", font_size=9)
    plot.show_bounds(bounds=scene.bounds_m, xtitle="x [m]", ytitle="y [m]", ztitle="z [m]")
    plot.add_axes()
    plot.view_isometric()
    plot.reset_camera()
    return plot
