"""Live renderer bridge: the neutral snapshot is what the general viewer draws."""
from pathlib import Path
import numpy as np
import pyvista as pv

from emfeeld.scene import Scene, load_scene
from emfeeld.viewer import make_plotter, render_pyvista
from emfeeld.visualization import build_visualization

ROOT = Path(__file__).resolve().parents[1]


def test_neutral_grid_matches_real_vtk_point_order_and_values():
    scene = load_scene(ROOT/'examples'/'electric_sphere.json')
    visual = build_visualization(scene, resolution=11)
    a = visual.potential.points_m
    native = pv.StructuredGrid(a[:,:,0], a[:,:,1], a[:,:,2])
    np.testing.assert_array_equal(native.points,
        np.column_stack((a[:,:,0].ravel(order='F'), a[:,:,1].ravel(order='F'),
                         a[:,:,2].ravel(order='F'))))
    # The scalar data are real model evaluations, not normalized drawing values.
    np.testing.assert_array_equal(visual.potential.values,
                                  scene.model.potential(native.points))


def test_renderer_uses_prepared_data_without_reconsulting_sources(monkeypatch):
    scene = load_scene(ROOT/'examples'/'electric_sphere.json')
    paths = scene.trajectories()
    visual = build_visualization(scene, resolution=9, recorded=paths)

    def forbidden(*args, **kwargs):
        raise AssertionError('Renderer must not resimulate or evaluate physical sources')
    from emfeeld.fields import SolidSphere, PointSource
    monkeypatch.setattr(Scene, 'trajectories', forbidden)
    monkeypatch.setattr(SolidSphere, 'field', forbidden)
    monkeypatch.setattr(SolidSphere, 'potential', forbidden)
    monkeypatch.setattr(PointSource, 'field', forbidden)
    monkeypatch.setattr(PointSource, 'potential', forbidden)

    plot = render_pyvista(visual, off_screen=True, recorded=True)
    try:
        assert set(plot.scalar_bars.keys()) == {'Potential [V]'}
        plot.show(auto_close=False, interactive=False)
        marker = plot.actors['particle_0']
        slider = plot._emfeeld_playback.slider
        for i in (0, len(paths[0].position_m)//2, len(paths[0].position_m)-1):
            slider.GetRepresentation().SetValue(visual.frame(i).time_s)
            slider.InvokeEvent('EndInteractionEvent')
            np.testing.assert_array_equal(marker.position, paths[0].position_m[i])
        arr = [actor.mapper.dataset for actor in plot.renderer.actors.values()
               if hasattr(actor, 'mapper') and hasattr(actor.mapper, 'dataset')]
        native = next(m for m in arr if 'potential' in m.array_names)
        np.testing.assert_array_equal(native['potential'], visual.potential.values)
    finally:
        plot.close()


def test_existing_general_viewer_semantics_with_neutral_adapter():
    scene = load_scene(ROOT/'examples'/'line_plane_fields.json')
    plot = make_plotter(scene, resolution=9, off_screen=True)
    try:
        assert set(plot.scalar_bars.keys()) == {'Potential [V]'}
        assert 'truncated' in build_visualization(scene, resolution=9).annotations[-1].text.lower()
        np.testing.assert_array_equal(plot.renderer.cube_axes_actor.bounds, scene.bounds_m)
        image = plot.screenshot(return_img=True)
        assert image.ndim == 3 and image.std() > 1
    finally:
        plot.close()
