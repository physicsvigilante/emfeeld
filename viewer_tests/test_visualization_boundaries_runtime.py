"""Actual PyVista consumes corrected unit directions, never physical magnitudes."""
import numpy as np
import pyvista as pv
import pytest

from emfeeld.scene import scene_from_dict
from emfeeld.viewer import render_pyvista
from emfeeld.visualization import build_visualization


def scene(value):
    return scene_from_dict({
        'schema_version': 1, 'title': 'extreme field display', 'kind': 'gravity',
        'sources': [{'type': 'uniform', 'field_m_s2': [value, 0., 0.]}],
        'bounds_m': [-.25, .25, -.25, .25, -.25, .25],
    })


def arrow_mesh(plot):
    meshes = [actor.mapper.dataset for actor in plot.renderer.actors.values()
              if isinstance(actor, pv.Actor) and hasattr(actor.mapper, 'dataset')]
    return next(mesh for mesh in meshes if isinstance(mesh, pv.PolyData)
                and 'potential' not in mesh.array_names and mesh.n_points > 0)


@pytest.mark.parametrize('magnitude', [1e200, 1e-200])
def test_extreme_directions_make_same_real_glyph_geometry_as_unit_field(magnitude):
    normal_data = build_visualization(scene(1.), resolution=5)
    extreme_data = build_visualization(scene(magnitude), resolution=5)
    reference = render_pyvista(normal_data, off_screen=True)
    actual = None
    try:
        actual = render_pyvista(extreme_data, off_screen=True)
        a, b = arrow_mesh(reference), arrow_mesh(actual)
        assert a.n_points == b.n_points and a.n_cells == b.n_cells
        np.testing.assert_array_equal(a.points, b.points)
        np.testing.assert_array_equal(a.faces, b.faces)
        actual.show(auto_close=False, interactive=False)
        image = actual.screenshot(return_img=True)
        assert image.shape[:2] == (850, 1200) and image.std() > 1.
        np.testing.assert_array_equal(extreme_data.field.vectors_SI,
                                      np.tile([magnitude, 0., 0.], (343, 1)))
        assert set(actual.scalar_bars.keys()) == {'Potential [J/kg]'}
    finally:
        if actual is not None:
            actual.close()
        reference.close()
