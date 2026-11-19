"""Physics/data/display boundaries: no renderer import, no substituted flux law."""
from dataclasses import replace
import os
import subprocess
import sys

import numpy as np
import pytest
from emfeeld.gauss_lesson import GaussState, GaussianCube, GaussianSphere, HeldCharge, measure, _HeldCoulombField
from emfeeld.gauss_presentation import build_presentation, build_surface, PresentationCache


@pytest.mark.parametrize('surface', [GaussianCube(), GaussianSphere(),
    GaussianCube((2., -3., 1.), 3., ((0., -1., 0.), (1., 0., 0.), (0., 0., 1.)))])
@pytest.mark.parametrize('x', [0., .6, 1., 1.0001, 2.])
@pytest.mark.parametrize('q', [1e-9, -1e-9])
def test_report_is_exact_unchanged_physics_and_samples_are_actual(surface, x, q):
    position = np.array(surface.center_m) + np.array([x, 0., 0.]) * (surface.side_m/2 if isinstance(surface, GaussianCube) else surface.radius_m)
    state = GaussState(surface, (HeldCharge(q, tuple(position)),))
    before = state.to_dict()
    result = build_presentation(state, resolution=6)
    assert dict(result.report) == measure(state)
    assert state.to_dict() == before
    if result.report['status'] == 'available':
        expected = _HeldCoulombField(state.charges).field(result.surface.probes_m)
        np.testing.assert_array_equal(result.field_N_C, expected)
        np.testing.assert_array_equal(result.normal_field_N_C,
            np.einsum('ij,ij->i', expected, result.surface.outward_normals))
    else:
        assert result.field_N_C is result.normal_field_N_C is result.color_limits_N_C is result.caution is None


@pytest.mark.parametrize('surface', [GaussianCube(), GaussianSphere()])
@pytest.mark.parametrize('resolution', [4, 6, 12, 40])
def test_closed_winding_actual_surface_and_nondegenerate_cells(surface, resolution):
    state = GaussState(surface)
    g = build_surface(state, resolution=resolution)
    verts = g.points_m[g.cells[:, 1:]]
    cross = np.cross(verts[:, 1]-verts[:, 0], verts[:, 2]-verts[:, 0])
    assert np.all(np.sum(cross*g.outward_normals, axis=1) > 0)
    np.testing.assert_allclose(np.linalg.norm(g.outward_normals, axis=1), 1, atol=3e-16)
    if isinstance(surface, GaussianCube):
        np.testing.assert_array_equal(g.face_indices, np.repeat(np.arange(6), resolution**2))
        np.testing.assert_array_equal(np.max(np.abs(g.probes_m), axis=1), 1)
    else:
        np.testing.assert_allclose(np.linalg.norm(g.probes_m, axis=1), 1, atol=3e-16)
        assert np.all(g.face_indices == -1) and len(g.outline_edges) == 0
        # Every mesh edge belongs to two triangles, including the seam and poles.
        edges = {}
        for tri in g.cells[:, 1:]:
            for a, b in zip(tri, np.roll(tri, -1)):
                pair = tuple(sorted((int(a), int(b))))
                edges[pair] = edges.get(pair, 0) + 1
        assert set(edges.values()) == {2}


def test_immutable_arrays_report_and_independent_snapshots():
    data = build_presentation(GaussState())
    for array in [data.field_N_C, data.normal_field_N_C, *vars(data.surface).values()]:
        assert not array.flags.writeable
        with pytest.raises(ValueError): array.setflags(write=True)
    with pytest.raises(TypeError): data.report['exact_total_N_m2_per_C'] = 0
    other = build_presentation(GaussState())
    assert not np.shares_memory(data.field_N_C, other.field_N_C)


def test_cache_reuses_only_same_physical_state_and_samples(monkeypatch):
    import emfeeld.gauss_presentation as module
    cache = PresentationCache()
    state = GaussState()
    p = cache.get(state)
    def forbidden(*a, **k): raise AssertionError('physics called on unchanged state')
    with monkeypatch.context() as m:
        m.setattr(module, 'measure', forbidden)
        m.setattr(module._HeldCoulombField, 'field', forbidden)
        assert cache.get(replace(state)) is p
    changed = replace(state, charges=(HeldCharge(1e-9, (.4, 0, 0)),))
    assert cache.get(changed) is not p and cache.build_count == 2
    assert cache.get(changed, order=48).order == 48 and cache.build_count == 3
    assert cache.get(changed, order=48, resolution=6).resolution == 6 and cache.build_count == 4
    before = cache._value
    with pytest.raises(ValueError): cache.get(changed, order=True)
    with pytest.raises(ValueError): cache.get(changed, resolution=12.)
    assert cache._value is before


def test_boundary_clears_then_valid_recovers():
    cache = PresentationCache()
    data = cache.get(GaussState())
    boundary = GaussState(charges=(HeldCharge(1e-9, (1, 0, 0)),))
    refused = cache.get(boundary)
    assert refused.report['status'] == 'undefined_boundary' and refused.field_N_C is None
    recovered = cache.get(GaussState())
    np.testing.assert_array_equal(recovered.field_N_C, data.field_N_C)


@pytest.mark.parametrize('resolution', [True, 3, 41, 12., '12'])
def test_resolution_refused(resolution):
    with pytest.raises(ValueError): build_surface(GaussState(), resolution=resolution)


def test_headless_pipeline_has_no_graphics_import():
    code = '''
import builtins
original = builtins.__import__
def guarded(name, *a, **k):
    if name.split('.')[0] in ('pyvista', 'vtk', 'vtkmodules'):
        raise AssertionError('graphics import: ' + name)
    return original(name, *a, **k)
builtins.__import__ = guarded
from emfeeld.gauss_lesson import GaussState, GaussianSphere
from emfeeld.gauss_presentation import build_presentation
for state in (GaussState(), GaussState(surface=GaussianSphere())):
    assert build_presentation(state).report['status'] == 'available'
'''
    subprocess.run([sys.executable, '-W', 'error', '-c', code], check=True)
