"""R52-A/B: direction-only glyphs and standalone saved-frame admission."""
from dataclasses import replace
import math
from types import SimpleNamespace
import warnings

import numpy as np
import pytest

from emfeeld.scene import Scene, scene_from_dict
from emfeeld.visualization import build_visualization


def uniform_scene(vector=(1., 0., 0.), *, moving=False):
    packet = {
        'schema_version': 1, 'title': 'boundary regression', 'kind': 'gravity',
        'sources': [{'type': 'uniform', 'field_m_s2': list(vector)}],
        'bounds_m': [-.25, .25, -.25, .25, -.25, .25],
        'duration_s': 1., 'samples': 5,
    }
    if moving:
        packet['particles'] = [{'mass_kg': 1., 'position_m': [0., 0., 0.],
                                'velocity_m_s': [.1, 0., 0.]}]
    return scene_from_dict(packet)


@pytest.mark.parametrize('vector,expected', [
    ((1e200, 0., 0.), (1., 0., 0.)),
    ((1e-200, 0., 0.), (1., 0., 0.)),
    ((3e200, -4e200, 12e200), (3/13, -4/13, 12/13)),
    ((3e-200, -4e-200, 12e-200), (3/13, -4/13, 12/13)),
    ((1.5e308, -1.5e308, 1.5e308), tuple(v/math.sqrt(3) for v in (1, -1, 1))),
    ((5e-324, 1e-323, -1.5e-323), tuple(v/math.sqrt(14) for v in (1, 2, -3))),
    ((1e-160, -1e-160, 1e-160), tuple(v/math.sqrt(3) for v in (1, -1, 1))),
])
def test_finite_nonzero_fields_keep_343_unit_directions_and_raw_values(vector, expected):
    scene = uniform_scene(vector)
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        data = build_visualization(scene, resolution=5)
    assert data.field.arrow_directions.shape == (343, 3)
    np.testing.assert_array_equal(data.field.vectors_SI, np.tile(vector, (343, 1)))
    np.testing.assert_array_equal(data.field.arrow_origins_m, data.field.positions_m)
    np.testing.assert_allclose(data.field.arrow_directions,
                               np.tile(expected, (343, 1)), rtol=5e-16, atol=0.)
    np.testing.assert_allclose(np.linalg.norm(data.field.arrow_directions, axis=1),
                               1., rtol=5e-16, atol=0.)
    exported = data.to_dict()['field']
    np.testing.assert_array_equal(exported['vectors_SI'], data.field.vectors_SI)
    np.testing.assert_array_equal(exported['schematic_arrows']['unit_directions'],
                                  data.field.arrow_directions)
    grid = data.potential.points_m
    points = np.column_stack([grid[:, :, i].ravel(order='F') for i in range(3)])
    np.testing.assert_array_equal(data.potential.values, scene.model.potential(points))


def test_normal_scale_directions_preserve_legacy_arithmetic_exactly():
    data = build_visualization(uniform_scene((3., -4., 12.)), resolution=5)
    raw = data.field.vectors_SI
    np.testing.assert_array_equal(data.field.arrow_directions,
                                  raw / np.linalg.norm(raw, axis=1)[:, None])


def test_mixed_magnitudes_zero_and_undefined_keep_corresponding_origins():
    raw = np.zeros((343, 3))
    raw[:5] = [[1e200, 0., 0.], [0., -1e-200, 0.],
               [3., 4., 0.], [np.nan, 1., 0.], [np.inf, 0., 0.]]

    def sampler(model, points, *, potential=False):
        return np.zeros(len(points)) if potential else raw

    with warnings.catch_warnings():
        warnings.simplefilter('error')
        data = build_visualization(uniform_scene(), resolution=5, sampler=sampler)
    np.testing.assert_array_equal(data.field.vectors_SI, raw)
    np.testing.assert_array_equal(data.field.arrow_origins_m, data.field.positions_m[:3])
    np.testing.assert_array_equal(data.field.arrow_directions,
                                  [[1., 0., 0.], [0., -1., 0.], [.6, .8, 0.]])
    assert data.to_dict()['field']['vectors_SI'][3][0] is None
    assert data.to_dict()['field']['vectors_SI'][4][0] is None


def test_coherently_truncated_real_trajectory_refused_before_sampling(monkeypatch):
    scene = uniform_scene((0., 0., 0.), moving=True)
    path = scene.trajectories()[0]
    fields = ('time_s', 'position_m', 'velocity_m_s', 'kinetic_J', 'potential_J')
    short = replace(path, **{name: getattr(path, name)[:2] for name in fields})

    def forbidden(*args, **kwargs):
        raise AssertionError('invalid saved positions must fail before sampling or solving')

    monkeypatch.setattr(Scene, 'trajectories', forbidden)
    with pytest.raises(ValueError, match='position'):
        build_visualization(scene, resolution=5, recorded=(short,), sampler=forbidden)


@pytest.mark.parametrize('positions', [
    np.zeros((0, 3)), np.zeros((2, 3)), np.zeros((6, 3)), np.zeros((5, 2)),
    np.zeros(15), None, np.full((5, 3), np.nan), np.full((5, 3), np.inf),
    np.ones((5, 3), dtype=complex), np.ones((5, 3), dtype=bool),
    np.full((5, 3), '1'),
])
def test_invalid_saved_positions_are_early_typed_refusals(positions):
    def forbidden(*args, **kwargs):
        raise AssertionError('no model evaluation before all supplied paths are validated')
    records = (SimpleNamespace(position_m=np.zeros((5, 3))),
               SimpleNamespace(position_m=positions))
    with pytest.raises(ValueError, match='position'):
        build_visualization(uniform_scene(), resolution=5, recorded=records, sampler=forbidden)


def test_missing_saved_position_attribute_refused():
    with pytest.raises(ValueError, match='position'):
        build_visualization(uniform_scene(), resolution=5, recorded=(object(),))


def test_valid_real_recording_keeps_all_frames_and_never_resimulates(monkeypatch):
    scene = uniform_scene((0., 0., 0.), moving=True)
    paths = scene.trajectories()
    expected = paths[0].position_m.copy()

    def forbidden(*args, **kwargs):
        raise AssertionError('saved playback must not solve again')

    monkeypatch.setattr(Scene, 'trajectories', forbidden)
    data = build_visualization(scene, resolution=5, recorded=paths)
    for index in range(scene.samples):
        np.testing.assert_array_equal(data.frame(index).positions_m, expected[index:index+1])
        assert data.frame(index).time_s == paths[0].time_s[index]
    np.testing.assert_array_equal(data.to_dict()['trajectories'][0]['positions_m'], expected)
    paths[0].position_m[:] = 99.
    np.testing.assert_array_equal(data.trajectories[0].positions_m, expected)
    assert not data.trajectories[0].positions_m.flags.writeable


def test_empty_static_recording_stays_valid():
    data = build_visualization(uniform_scene(), resolution=5, recorded=())
    assert data.frame(4).positions_m == ()
    assert not data.moving_slice
