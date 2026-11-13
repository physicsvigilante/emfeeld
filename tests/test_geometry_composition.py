"""R2: real composition + a recording backend; NOT rendering qualification."""
from types import SimpleNamespace
import sys
import warnings
import numpy as np
from numpy.testing import assert_allclose
import pytest
from emfeeld import (PointSource, SolidSphere, SphericalShell, InfiniteLine,
                     InfinitePlane, UniformField, Superposition, Scene)
from emfeeld.fields import iter_sources
from emfeeld import viewer


def freeze(value):
    if isinstance(value, dict):
        return tuple((k, freeze(v)) for k, v in value.items())
    if isinstance(value, (tuple, list, np.ndarray)):
        return tuple(freeze(v) for v in value)
    return value


class Grid(dict):
    def __init__(self, x, y, z):
        self.points = np.column_stack([a.ravel() for a in (x, y, z)])


class PlotterSpy:
    def __init__(self, **kwargs):
        self.geometry, self.notes = [], []

    def add_mesh(self, mesh, **kwargs):
        if isinstance(mesh, tuple):
            self.geometry.append((mesh, freeze(kwargs)))

    def add_points(self, points, **kwargs):
        self.geometry.append((('point', freeze(points)), freeze(kwargs)))

    def add_text(self, text, **kwargs): self.notes.append(text)
    def add_title(self, *args, **kwargs): pass
    def show_bounds(self, *args, **kwargs): pass
    def add_axes(self, *args, **kwargs): pass
    def view_isometric(self, *args, **kwargs): pass
    def reset_camera(self, *args, **kwargs): pass


@pytest.fixture
def backend(monkeypatch):
    fake = SimpleNamespace(
        Plotter=PlotterSpy, StructuredGrid=Grid,
        Sphere=lambda **kw: ('sphere', freeze(kw)),
        Line=lambda start, end: ('line', freeze(start), freeze(end)),
        Plane=lambda **kw: ('plane', freeze(kw)))
    monkeypatch.setitem(sys.modules, 'pyvista', fake)
    monkeypatch.setattr(viewer, 'sample_values', lambda model, points, potential=False:
                        np.zeros(len(points) if potential else points.shape))


def draw(model):
    scene = Scene('nested geometry', model, (), 1., 2, (-2., 2., -2., 2., -2., 2.))
    return viewer.make_plotter(scene, resolution=5, off_screen=True)


def leaves():
    return (SolidSphere('electric', 1e-9, center=(1, 0, 0), radius=.4),
            SphericalShell('electric', -1e-9, center=(0, 1, 0), radius=.6),
            InfiniteLine('electric', 1e-10, direction=(1, 2, 3)),
            InfinitePlane('electric', 1e-11, normal=(1, 3, 7)),
            PointSource('electric', -1e-9, center=(1, 1, 1)),
            UniformField('electric', (1, 2, 3)))


def test_iterator_preserves_order_identity_and_repeated_references():
    sources = leaves()
    model = Superposition((Superposition(sources[:2]), sources[2],
                           Superposition((sources[3], Superposition(sources[4:]), sources[0]))))
    expected = (*sources, sources[0])
    assert all(a is b for a, b in zip(iter_sources(model), expected))
    assert len(tuple(iter_sources(model))) == len(expected)
    assert tuple(iter_sources(sources[0])) == (sources[0],)


def test_flat_and_nested_all_builtin_geometry_are_identical(backend):
    sources = leaves()
    flat = Superposition((*sources, sources[0]))
    nested = Superposition((Superposition(sources[:2]), sources[2],
                            Superposition((sources[3], Superposition(sources[4:]), sources[0]))))
    points = np.array([[4., 5., 6.], [-2., 1., 3.]])
    assert_allclose(flat.field(points), nested.field(points), rtol=1e-14)
    assert_allclose(flat.potential(points), nested.potential(points), rtol=1e-14)
    with warnings.catch_warnings(record=True) as seen:
        a, b = draw(flat), draw(nested)
    assert not seen
    assert len(a.geometry) == 6  # Five shapes, plus the repeated sphere.
    assert b.geometry == a.geometry  # Includes positions, radii, orientation and styles.
    assert any('Uniform fields have no source shape.' in text for text in b.notes)


def test_unknown_geometry_is_disclosed_without_dropping_physics(backend):
    class CustomField:
        kind = 'electric'
        trajectory_safe = True

        def field(self, points):
            return np.broadcast_to([2., 0., 0.], np.shape(points)).copy()

        def potential(self, points):
            return -2 * np.asarray(points)[..., 0]

    sphere = SolidSphere('electric', 1e-9)
    custom = CustomField()
    model = Superposition((Superposition((sphere, custom)),))
    point = np.array([2., 3., 4.])
    assert_allclose(model.field(point), sphere.field(point) + [2, 0, 0])
    assert_allclose(model.potential(point), sphere.potential(point) - 4)
    with pytest.warns(RuntimeWarning, match='No geometry adapter for CustomField'):
        plot = draw(model)
    assert len(plot.geometry) == 1
    assert any('Geometry not drawn for: CustomField.' in note for note in plot.notes)
