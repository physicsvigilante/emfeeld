"""Optional PyVista adapter for the renderer-neutral general scene presentation.

All samples/source geometry/particle paths are prepared by visualization.py;
this module only maps the data and the display-only playback controller to VTK.
Specialized JEE lessons are deliberately independent and unchanged.
"""
import numpy as np

from .playback import PlaybackState, PlaybackController
from .visualization import build_visualization, sample_values


def make_plotter(scene, *, resolution=41, off_screen=False, replay_seconds=12.0,
                 recorded=None, potential_clim=None, study_label=None):
    """Return a PyVista plotter preserving the legacy general viewer behavior.

    Space toggles replay; Home restarts paused; Left/Right step saved samples.
    Physical paths are NOT field lines. Marker radius, field arrow length,
    infinite-source patches and potential slice opacity are display-only.
    """
    if recorded is not None:
        from .study import validate_recorded
        validate_recorded(scene, recorded)
    if potential_clim is not None:
        c = np.asarray(potential_clim, dtype=float)
        if c.shape != (2,) or not np.isfinite(c).all() or c[0] >= c[1]:
            raise ValueError("potential_clim must be two finite increasing values")
    try:
        import pyvista as pv
    except ImportError as exc:
        raise RuntimeError('3D viewer requires: python -m pip install -e ".[view]"') from exc
    if type(resolution) is not int or not 5 <= resolution <= 101:
        raise ValueError("resolution must be an integer from 5 through 101")
    replay = PlaybackState(scene.duration_s, scene.samples, replay_seconds=replay_seconds)
    # Pass the public sampler explicitly to retain its historical patch point.
    data = build_visualization(scene, resolution=resolution, recorded=recorded,
                               sampler=sample_values)
    return render_pyvista(data, pv, replay=replay, off_screen=off_screen,
                          potential_clim=potential_clim, study_label=study_label,
                          recorded=recorded is not None)


def render_pyvista(data, pv=None, *, replay=None, off_screen=False,
                   potential_clim=None, study_label=None, recorded=False):
    """Render a prepared VisualizationData, with no model/solver access.

    A future renderer consumes the *same* data, not any VTK mesh or callbacks.
    All source-type dispatch has already occurred in the neutral adapter.
    """
    if pv is None:
        import pyvista as pv
    if replay is None:
        replay = PlaybackState(data.duration_s, data.samples)

    class PlaybackPlotter(pv.Plotter):
        def close(self):
            controller = getattr(self, "_emfeeld_playback", None)
            if controller is not None:
                controller.close()
            super().close()

    bounds = np.array(data.bounds_m)
    lower, upper = bounds[::2], bounds[1::2]
    center = (lower + upper) / 2
    span = float(np.max(upper - lower))
    plot = PlaybackPlotter(off_screen=off_screen, window_size=(1200, 850))
    plot.add_title(data.title if study_label is None else f"{data.title} | {study_label}", font_size=12)

    grid = data.potential.points_m
    plane = pv.StructuredGrid(grid[:, :, 0], grid[:, :, 1], grid[:, :, 2])
    plane["potential"] = data.potential.values
    if np.isfinite(plane["potential"]).any():
        plot.add_mesh(plane, scalars="potential",
                      opacity=0.35 if data.moving_slice else 0.7, nan_opacity=0,
                      **({"clim": potential_clim} if potential_clim is not None else {}),
                      scalar_bar_args={"title": f"Potential [{data.units.potential}]",
                                       "position_x": 0.86, "position_y": 0.25,
                                       "width": 0.12, "height": 0.50, "vertical": True,
                                       "title_font_size": 12, "label_font_size": 10,
                                       "fmt": "%.3g"})

    if len(data.field.arrow_origins_m):
        cloud = pv.PolyData(data.field.arrow_origins_m)
        cloud["direction"] = data.field.arrow_directions
        arrows = cloud.glyph(orient="direction", scale=False, factor=data.field.arrow_length_m)
        # Equal-length schematic arrows; no unearned scalar color legend.
        plot.add_mesh(arrows, color="dimgray", show_scalar_bar=False)

    for object_data in data.geometry:
        shape = object_data.shape
        if shape in ("sphere", "shell"):
            mesh = pv.Sphere(radius=object_data.radius_m, center=object_data.center_m)
            plot.add_mesh(mesh, opacity=0.18, color="lightgray", show_scalar_bar=False,
                          style="wireframe" if shape == "shell" else "surface")
        elif shape == "point":
            plot.add_points(np.array([object_data.center_m]), point_size=14,
                            color="dimgray", render_points_as_spheres=True,
                            show_scalar_bar=False)
        elif shape == "line":
            c, a = np.array(object_data.center_m), np.array(object_data.direction)
            plot.add_mesh(pv.Line(c - object_data.display_span_m * a,
                                  c + object_data.display_span_m * a), line_width=4,
                          color="dimgray", show_scalar_bar=False)
        elif shape == "plane":
            plot.add_mesh(pv.Plane(center=object_data.center_m,
                                   direction=object_data.direction,
                                   i_size=object_data.display_span_m,
                                   j_size=object_data.display_span_m), opacity=0.12,
                          color="lightgray", show_scalar_bar=False)
        # A uniform field has no source shape; unknown geometry is omitted.

    markers = []
    for index, path in enumerate(data.trajectories):
        plot.add_mesh(pv.lines_from_points(path.positions_m), line_width=3,
                      color="black", show_scalar_bar=False, name=f"trajectory_{index}")
        # Local polygonal marker, positioned using VTK actor transform; not size/charge.
        marker = pv.Sphere(radius=1.0, center=(0., 0., 0.),
                           theta_resolution=24, phi_resolution=24)
        actor = plot.add_mesh(marker, color="magenta", lighting=False,
                              style="surface", show_scalar_bar=False,
                              pickable=False, name=f"particle_{index}")
        actor.scale = (path.marker_radius_m,) * 3
        actor.position = tuple(path.positions_m[0])
        actor.use_bounds = False
        markers.append(actor)

    labels = {note.id: note.text for note in data.annotations}
    if data.trajectories:
        plot.add_text(labels["particle_key"], position=(0.02, 0.54),
                      viewport=True, name="particle_key", font_size=9)
        time_label = plot.add_text("Sample time: 0 s", position=(0.02, 0.88),
                                   viewport=True, name="time", font_size=10)
        status_label = plot.add_text("Paused", position=(0.02, 0.83),
                                     viewport=True, name="playback_status", font_size=10)
        help_text = labels["playback_help"].replace(
            "\n\nDisplay time, not physical time",
            f"\n\nFull interval replay: {replay.replay_seconds:g} s\nDisplay time, not physical time")
        plot.add_text(help_text, position=(0.02, 0.67), viewport=True,
                      name="playback_help", font_size=9)

        def display(state):
            frame = data.frame(state.index)
            for marker, position in zip(markers, frame.positions_m):
                marker.position = position
            # In-place updates preserve authored axes exactly during playback.
            time_label.input = f"Sample time: {state.time_s:.6g} s"
            status_label.input = ("Playing" if state.playing else
                                  "Finished" if state.progress >= 1 else "Paused")

        controller = PlaybackController(plot, replay, display)
        plot._emfeeld_playback = controller
        controller.slider = plot.add_slider_widget(
            controller.seek, (0, data.duration_s), value=0,
            title="Time [s]", pointa=(0.35, 0.88), pointb=(0.75, 0.88),
            style="modern", slider_width=0.015, tube_width=0.003,
            title_height=0.025, fmt="%.3g")
        controller.slider.AddObserver("StartInteractionEvent", controller.pause)

    plot.add_text(labels["geometry_key"], position="lower_left", font_size=9)
    plot.show_bounds(bounds=data.bounds_m, xtitle="x [m]", ytitle="y [m]", ztitle="z [m]",
                     location="outer", fmt="%.2g", font_size=10,
                     n_xlabels=3, n_ylabels=3, n_zlabels=3,
                     use_2d=False, use_3d_text=False)
    plot.add_axes()
    plot.view_isometric()
    if not recorded:
        plot.reset_camera()
    else:
        plot.camera_position = (tuple(center + 2 * span), tuple(center), (0., 0., 1.))
    plot.camera.zoom(0.74)
    return plot
