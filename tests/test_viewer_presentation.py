"""Presentation configuration regressions; recording backend, not real rendering."""
from types import SimpleNamespace
import sys
import numpy as np
import pytest
from emfeeld import InfiniteLine, InfinitePlane, Scene, Superposition, UniformField
from emfeeld import viewer


class Grid(dict):
    def __init__(self, x, y, z):
        self.points = np.column_stack([a.ravel() for a in (x, y, z)])


class Recorder:
    def __init__(self, **kwargs):
        self.meshes, self.notes, self.sliders = [], [], []
        self.zoom_factors = []
        self.text_actors = {}
        self.camera = SimpleNamespace(zoom=self.zoom_factors.append)

    def add_mesh(self, mesh, **kwargs): self.meshes.append((mesh, kwargs))
    def add_text(self, text, **kwargs):
        self.notes.append((text, kwargs))
        actor = SimpleNamespace(input=text)
        if 'name' in kwargs:
            self.text_actors[kwargs['name']] = actor
        return actor
    def add_key_event(self, *args): pass
    def render(self): pass
    def add_title(self, *args, **kwargs): pass
    def show_bounds(self, **kwargs): self.bounds_options = kwargs
    def add_axes(self): pass
    def view_isometric(self): pass
    def reset_camera(self): pass
    def add_slider_widget(self, callback, rng, **kwargs):
        self.sliders.append((callback, rng, kwargs))
        callback(kwargs['value'])
        return SimpleNamespace(AddObserver=lambda *args: None,
             GetRepresentation=lambda: SimpleNamespace(SetValue=lambda value: None))


@pytest.fixture
def backend(monkeypatch):
    fake = SimpleNamespace(
        Plotter=Recorder, StructuredGrid=Grid,
        PolyData=lambda points: SimpleNamespace(points=points),
        lines_from_points=lambda points: ('trajectory', points),
        Line=lambda *args: ('line', args), Plane=lambda **kwargs: ('plane', kwargs))
    monkeypatch.setitem(sys.modules, 'pyvista', fake)
    monkeypatch.setattr(viewer, 'sample_values', lambda model, points, potential=False:
                        np.zeros(len(points) if potential else points.shape))


def test_only_potential_requests_scalar_coloring(backend):
    scene = Scene('neutral geometry', Superposition((InfiniteLine('electric', 1e-9),
                  InfinitePlane('electric', 1e-9))), (), 1, 2, (-2, 2, -2, 2, -2, 2))
    plot = viewer.make_plotter(scene, resolution=5)
    assert plot.meshes[0][1]['scalars'] == 'potential'
    assert plot.meshes[0][1]['scalar_bar_args']['title'] == 'Potential [V]'
    geometry = plot.meshes[1:]
    assert len(geometry) == 2
    for _, options in geometry:
        assert options['color'] is not None
        assert options['show_scalar_bar'] is False


def test_astronomical_axes_keep_si_with_compact_outer_labels(backend):
    bounds = (-3e11, 3e11, -3e11, 3e11, -3e11, 3e11)
    scene = Scene('SI coordinates', Superposition((UniformField('gravity', (0, 0, 0)),)),
                  (), 1, 2, bounds)
    options = viewer.make_plotter(scene, resolution=5).bounds_options
    assert options['bounds'] == bounds
    assert options['location'] == 'outer'
    assert options['xtitle'] == 'x [m]'
    for value in bounds:
        assert len(options['fmt'] % value) <= 8
    assert options['n_xlabels'] == options['n_ylabels'] == options['n_zlabels'] == 3


def test_time_controls_do_not_use_title_band(backend):
    positions = np.array([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]])
    scene = SimpleNamespace(title='time', bounds_m=(-3, 3, -3, 3, -3, 3),
             model=Superposition((UniformField('gravity', (0, 0, 0)),)),
             duration_s=2, samples=3,
             trajectories=lambda: (SimpleNamespace(position_m=positions),))
    plot = viewer.make_plotter(scene, resolution=5)
    callback, _, options = plot.sliders[0]
    assert options['pointa'][1] == options['pointb'][1] < 0.90
    assert options['slider_width'] < 0.02
    assert options['fmt'] == '%.3g'
    for time in (0, 1, 2):
        callback(time)
        marker = [m for m, _ in plot.meshes if isinstance(m, SimpleNamespace)][0]
        np.testing.assert_array_equal(marker.points, positions[time:time + 1])
    time_options = [kw for _, kw in plot.notes if kw.get('name') == 'time']
    assert all(kw['viewport'] and kw['position'][1] < 0.90 for kw in time_options)
    assert len(time_options) == 1  # Slider updates must not replace the text actor.
    assert plot.text_actors['time'].input == 'Sample time: 2 s'


def test_layout_reserves_camera_and_legend_space(backend):
    scene = Scene('layout', Superposition((UniformField('gravity', (1, 0, 0)),)),
                  (), 1, 2, (-3, 3, -3, 3, -3, 3))
    plot = viewer.make_plotter(scene, resolution=5)
    assert len(plot.zoom_factors) == 1
    assert 0.65 <= plot.zoom_factors[0] <= 0.8
    legend = plot.meshes[0][1]['scalar_bar_args']
    assert legend['vertical'] is True
    assert legend['position_x'] >= 0.85
    assert legend['position_x'] + legend['width'] <= 1
    assert 0.2 <= legend['position_y'] < 0.3
    assert legend['position_y'] + legend['height'] <= 0.8
    assert plot.bounds_options['use_2d'] is False
    assert plot.bounds_options['use_3d_text'] is False


def test_layout_does_not_modify_field_potential_or_units(backend):
    field = UniformField('gravity', (1, 2, 3), origin=(4, 5, 6))
    scene = Scene('display only', Superposition((field,)), (), 1, 2,
                  (-3e11, 3e11, -3e11, 3e11, -3e11, 3e11))
    points = np.array([[7., 8., 9.], [1e11, 2e11, -1e11]])
    before = scene.model.field(points), scene.model.potential(points)
    plot = viewer.make_plotter(scene, resolution=5)
    np.testing.assert_array_equal(scene.model.field(points), before[0])
    np.testing.assert_array_equal(scene.model.potential(points), before[1])
    assert plot.bounds_options['bounds'] == scene.bounds_m
    assert plot.bounds_options['xtitle'] == 'x [m]'
