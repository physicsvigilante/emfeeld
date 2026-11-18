"""Pure, reusable presentation data: no renderer and no new field law."""
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from emfeeld import (InfiniteLine, InfinitePlane, PointSource, Scene,
                     SolidSphere, SphericalShell, Superposition, UniformField)
from emfeeld.fields import DomainError
from emfeeld.visualization import (VisualizationData, build_visualization,
                                   sample_values)


def _scene(*sources, particles=(), duration=2., samples=3):
    return Scene('neutral snapshot', Superposition(sources), particles,
                 duration, samples, (-2, 2, -2, 2, -2, 2))


def test_viz_data_samples_exact_fields_not_fictitious_surface_values():
    scene = _scene(PointSource('electric', 1e-9, (0, 0, 0)),
                   UniformField('electric', (1, -2, 3)))
    model = build_visualization(scene, resolution=5)
    assert isinstance(model, VisualizationData)
    assert vars(model.units) == dict(position="m", time="s", field="N/C", potential="V")
    assert model.potential.role == 'physical_potential_samples_on_display_slice'
    assert model.potential.points_m.shape == (5, 5, 3)
    assert model.potential.values.shape == (25,)
    # Independent direct query in documented x-fastest (Fortran) grid order.
    grid = model.potential.points_m
    direct_points = np.column_stack((grid[:, :, 0].ravel(order='F'),
                                     grid[:, :, 1].ravel(order='F'),
                                     grid[:, :, 2].ravel(order='F')))
    expected = sample_values(scene.model, direct_points, potential=True)
    np.testing.assert_array_equal(model.potential.values, expected)
    np.testing.assert_array_equal(model.field.vectors_SI,
                                  sample_values(scene.model, model.field.positions_m))
    assert model.field.arrow_length_m == pytest.approx(4 / 35)
    assert model.field.role.startswith('schematic_')
    assert np.linalg.norm(model.field.arrow_directions, axis=1) == pytest.approx(1)
    assert model.field.unit == 'N/C' and model.potential.unit == 'V'
    assert model.geometry[0].shape == 'point'
    assert model.geometry[0].role == 'schematic_marker'
    assert model.geometry[1].shape == 'none'
    assert model.has_uniform_source


def test_source_geometry_distinguishes_real_finite_and_infinite_extent():
    scene = _scene(SolidSphere('electric', 2e-9, (1, 0, 0), radius=.4),
                   SphericalShell('electric', 3e-9, (-1, 0, 0), radius=.6),
                   InfiniteLine('electric', 1e-10, direction=(0, 0, 1)),
                   InfinitePlane('electric', -1e-10, normal=(1, 0, 0)))
    model = build_visualization(scene, resolution=7)
    assert [(g.shape, g.role) for g in model.geometry] == [
        ('sphere', 'physical_extent'), ('shell', 'physical_extent'),
        ('line', 'truncated_infinite_source'), ('plane', 'truncated_infinite_source')]
    assert [g.radius_m for g in model.geometry[:2]] == [0.4, 0.6]
    assert model.geometry[2].direction == (0., 0., 1.)
    assert model.geometry[2].display_span_m == 4
    assert model.geometry[3].strength_unit == 'C/m²'
    assert not model.has_uniform_source


def test_undefined_samples_are_null_in_portable_json_not_zero_or_removed():
    scene = _scene(PointSource('electric', 1e-9, (0, 0, 0)))
    data = build_visualization(scene, resolution=5)
    assert np.isnan(data.potential.values).sum() == 1
    row = data.to_dict()
    assert row['visualization_version'] == 1
    assert row['potential']['sample_order'] == 'x_fastest_fortran'
    assert row['potential']['values'].count(None) == 1
    assert row['field']['schematic_arrows']['not_calibrated_field_lines'] is True
    assert row['units']['position'] == 'm'
    text = json.dumps(row, allow_nan=False)
    restored = json.loads(text)
    assert restored['potential']['values'].count(None) == 1
    assert restored['geometry'][0]['role'] == 'schematic_marker'


def test_recorded_paths_and_frames_copied_no_resimulation():
    path = np.array([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]])
    trajectories = (SimpleNamespace(position_m=path),)
    scene = _scene(UniformField('gravity', (0, 1, 0)))
    data = build_visualization(scene, resolution=5, recorded=trajectories)
    assert data.units.potential == 'J/kg' and data.units.field == 'm/s²'
    assert data.trajectories[0].marker_radius_m == pytest.approx(.1)
    assert data.trajectories[0].role == 'calculated_test_particle_trajectory_not_field_line'
    assert data.trajectories[0].marker_role.startswith('schematic_')
    assert [data.frame(i).time_s for i in range(3)] == [0., 1., 2.]
    assert data.frame(2).positions_m == ((2., 0., 0.),)
    path[1, :] = -123
    assert data.frame(1).positions_m == ((1., 0., 0.),)
    with pytest.raises(ValueError):
        data.trajectories[0].positions_m[0] = 1
    for bad in (-1, 3, 1.3, True):
        with pytest.raises(ValueError):data.frame(bad)
    assert len(data.to_dict()['trajectories']) == 1
    assert data.to_dict()['animation']['role'] == 'saved_trajectory_sample_display_only'


def test_static_visualization_needs_no_pyvista(monkeypatch):
    # A missing optional renderer cannot affect creation of the neutral data.
    monkeypatch.setitem(sys.modules, "pyvista", None)
    scene = _scene(UniformField("electric", (2, 0, 0)))
    built = build_visualization(scene, resolution=5)
    assert built.trajectories == ()
    assert built.missing_geometry == ()
    assert built.potential.values.shape == (25,)


def test_nested_and_flat_source_order_yield_same_presentation():
    a, b = SolidSphere('electric', 1e-9, center=(1, 0, 0)), UniformField('electric', (0, 0, 1))
    flat = _scene(a, b, a)
    nested = _scene(a, b, a)
    from dataclasses import replace
    nested = replace(nested, model=Superposition((Superposition((a, b)), Superposition((a,)))))
    va, vb = [build_visualization(sc, resolution=9) for sc in (flat, nested)]
    np.testing.assert_array_equal(va.potential.values, vb.potential.values)
    np.testing.assert_array_equal(va.field.vectors_SI, vb.field.vectors_SI)
    assert va.geometry == vb.geometry


def test_sampler_keeps_neighbors_when_one_point_is_undefined():
    class Singular:
        def field(self, p):
            if np.any(p[:, 0] == 0):
                raise DomainError('singular sample')
            return np.column_stack((p[:, 0], p[:, 0], p[:, 0]))
    points = np.array([[-1,0,0],[0,0,0],[1,0,0.]])
    result = sample_values(Singular(), points)
    assert np.isnan(result[1]).all()
    np.testing.assert_array_equal(result[0], [-1,-1,-1])
    np.testing.assert_array_equal(result[2], [1,1,1])


def test_unit_metadata_cannot_be_misrepresented_as_field_lines():
    data = build_visualization(_scene(UniformField('gravity', (3, 0, 0))), resolution=5)
    encoded = data.to_dict()
    assert encoded['field']['unit'] == 'm/s²'
    assert encoded['potential']['unit'] == 'J/kg'
    assert encoded['field']['role'] == 'schematic_field_direction_glyphs_not_field_lines'
    assert encoded['animation']['role'] == 'saved_trajectory_sample_display_only'
