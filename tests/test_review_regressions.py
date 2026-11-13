"""Additional diagnostics for candidate ded83f5; failures are intentional evidence.

Run from a full candidate checkout with PYTHONPATH=src. The geometry test uses
an explicitly limited spy backend, NOT PyVista or rendering qualification.
"""
from types import SimpleNamespace
import sys
import numpy as np
import pytest
from numpy.testing import assert_allclose
from emfeeld import (
    DomainError, InfiniteLine, InfinitePlane, SolidSphere, Superposition, Scene,
)
from emfeeld.fields import K, G
from emfeeld import viewer


@pytest.mark.parametrize("kind", ["electric", "gravity"])
@pytest.mark.parametrize("method", ["field", "potential"])
def test_oblique_line_axis_is_rejected(kind, method):
    source = InfiniteLine(kind, 1e-9, direction=(1, 1, 1))
    # The point is exactly on the authored axis, with modest integer coordinates.
    with pytest.raises(DomainError):
        getattr(source, method)((1, 1, 1))


@pytest.mark.parametrize("kind", ["electric", "gravity"])
def test_oblique_plane_surface_is_rejected(kind):
    source = InfinitePlane(kind, 1e-9, normal=(1, 3, 7))
    # Exact integer dot product: (7, 0, -1) . (1, 3, 7) = 0.
    with pytest.raises(DomainError):
        source.field((7, 0, -1))


@pytest.mark.parametrize("kind", ["electric", "gravity"])
@pytest.mark.parametrize("potential", [False, True])
def test_oblique_undefined_samples_become_nan(kind, potential):
    model = Superposition((InfiniteLine(kind, 1e-9, direction=(1, 1, 1)),))
    points = np.array([[1., 1., 1.], [1., -1., 0.]])
    samples = viewer.sample_values(model, points, potential=potential)
    assert np.isnan(samples[0]).all(), "undefined axis sample must not become a finite result"
    assert np.isfinite(samples[1]).all(), "valid neighbor must remain available"


@pytest.mark.parametrize("kind,c", [("electric", K * 1e-9), ("gravity", -G * 1e-9)])
def test_resolved_off_axis_line_values(kind, c):
    source = InfiniteLine(kind, 1e-9, direction=(1, 1, 1))
    d_perp = np.array([1., -1., 0.])
    expected_field = c * d_perp
    expected_potential = -2 * c * np.log(np.sqrt(2))
    for axial_distance in (0., 3., -7.):
        point = axial_distance * np.ones(3) + d_perp
        assert_allclose(source.field(point), expected_field, rtol=1e-13, atol=abs(c)*1e-13)
        assert_allclose(source.potential(point), expected_potential, rtol=1e-13, atol=abs(c)*1e-13)


@pytest.mark.parametrize("kind,c", [("electric", K * 1e-9), ("gravity", -G * 1e-9)])
def test_resolved_plane_sides(kind, c):
    n = np.array([1., 3., 7.])
    source = InfinitePlane(kind, 1e-9, normal=n)
    for sign in (-1, 1):
        point = np.array([7., 0., -1.]) + sign * 0.25 * n
        expected = sign * 2 * np.pi * c * n / np.linalg.norm(n)
        assert_allclose(source.field(point), expected, rtol=1e-13, atol=0)


@pytest.mark.parametrize("kind", ["electric", "gravity"])
def test_zero_strength_oblique_sources_remain_zero(kind):
    for source, p in (
        (InfiniteLine(kind, 0, direction=(1, 1, 1)), (1, 1, 1)),
        (InfinitePlane(kind, 0, normal=(1, 3, 7)), (7, 0, -1)),
    ):
        assert_allclose(source.field(p), [0, 0, 0], atol=0)
        assert source.potential(p) == 0


class _Grid(dict):
    def __init__(self, x, y, z):
        super().__init__()
        self.points = np.column_stack([a.ravel() for a in (x, y, z)])


class _PlotterSpy:
    def __init__(self, **kwargs):
        self.spheres = []

    def add_mesh(self, mesh, **kwargs):
        if isinstance(mesh, tuple) and mesh[0] == "sphere":
            self.spheres.append(mesh)

    def add_title(self, *args, **kwargs): pass
    def add_text(self, *args, **kwargs): pass
    def show_bounds(self, *args, **kwargs): pass
    def add_axes(self, *args, **kwargs): pass
    def view_isometric(self, *args, **kwargs): pass
    def reset_camera(self, *args, **kwargs): pass


def test_nested_composition_does_not_omit_source_geometry(monkeypatch):
    # Spy only on geometry dispatch; this is deliberately NOT a PyVista smoke test.
    fake_pyvista = SimpleNamespace(
        Plotter=_PlotterSpy, StructuredGrid=_Grid,
        Sphere=lambda **kwargs: ("sphere", kwargs),
    )
    monkeypatch.setitem(sys.modules, "pyvista", fake_pyvista)
    monkeypatch.setattr(viewer, "sample_values", lambda model, points, potential=False:
                        np.zeros(len(points) if potential else points.shape))
    sources = (SolidSphere("electric", 1e-9, radius=0.2),
               SolidSphere("electric", -2e-9, center=(1, 0, 0), radius=0.3))
    flat = Superposition(sources)
    nested = Superposition((Superposition(sources),))
    # Grouping preserves the actual physical calculation.
    assert_allclose(flat.field([2., 3., 4.]), nested.field([2., 3., 4.]))
    assert_allclose(flat.potential([2., 3., 4.]), nested.potential([2., 3., 4.]))
    def draw(model):
        scene = Scene("geometry dispatch", model, (), 1., 2, (-2., 2., -2., 2., -2., 2.))
        return viewer.make_plotter(scene, resolution=5, off_screen=True)
    flat_plot = draw(flat)
    nested_plot = draw(nested)
    assert len(flat_plot.spheres) == 2
    assert len(nested_plot.spheres) == len(flat_plot.spheres)
