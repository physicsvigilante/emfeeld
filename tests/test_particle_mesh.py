"""Polygonal particle contract. Recording backend is not rendering evidence."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from emfeeld import Scene, Superposition, UniformField, load_scene
from emfeeld.viewer import make_plotter
from test_viewer_presentation import backend

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scale', [1e-9, 1.0, 1e11])
def test_local_mesh_actor_transform_across_scales(backend, scale):
    positions = np.array([[2., 3., 4.], [3., 4., 5.], [4., 5., 6.]]) * scale
    original = positions.copy()
    scene = SimpleNamespace(title='Display transform', bounds_m=(-8*scale, 8*scale)*3,
        model=Superposition((UniformField('gravity',(0,0,0)),)),
        duration_s=2, samples=3,
        trajectories=lambda: (SimpleNamespace(position_m=positions),))
    plot = make_plotter(scene, resolution=5)
    actor = plot.actors['particle_0']
    sphere = actor.mapper.dataset
    assert sphere.sphere_options['radius'] == 1.0
    assert sphere.sphere_options['center'] == (0.,0.,0.)
    assert actor.scale == (0.025 * 16 * scale,) * 3
    assert not actor.use_bounds
    for i in (0,1,2,0):
        plot._emfeeld_playback.seek(i)
        np.testing.assert_array_equal(actor.position, positions[i])
        assert actor.mapper.dataset is sphere
    np.testing.assert_array_equal(original,positions)


@pytest.mark.parametrize('case', ['E1', 'G1'])
def test_all_saved_positions_and_actor_identities_without_reintegration(backend, monkeypatch, case):
    scene = load_scene(ROOT/'examples/marker_regression'/f'{case}.json')
    trajectories = scene.trajectories()
    keys = ('time_s','position_m','velocity_m_s','kinetic_J','potential_J')
    frozen = [{key:getattr(t,key).copy() for key in keys} for t in trajectories]
    probes = np.array([[1.4,1.1,0.3], [2.,1.,0.5]])
    field, potential = scene.model.field(probes),scene.model.potential(probes)
    def forbidden(*args,**kwargs):
        raise AssertionError('Recorded viewer attempted reintegration')
    monkeypatch.setattr(Scene,'trajectories',forbidden)
    plot = make_plotter(scene,recorded=trajectories,resolution=5)
    actors = [plot.actors[f'particle_{i}'] for i in range(len(trajectories))]
    assert len({id(a) for a in actors}) == len(trajectories)
    meshes = [a.mapper.dataset for a in actors]
    for index,time in enumerate(trajectories[0].time_s):
        plot._emfeeld_playback.seek(float(time))
        assert plot._emfeeld_playback.state.index == index
        for j,(actor,t) in enumerate(zip(actors,trajectories)):
            assert actor is plot.actors[f'particle_{j}']
            assert actor.mapper.dataset is meshes[j]
            np.testing.assert_array_equal(actor.position,t.position_m[index])
    for t,old in zip(trajectories,frozen):
        for key in keys:np.testing.assert_array_equal(getattr(t,key),old[key])
    np.testing.assert_array_equal(scene.model.field(probes),field)
    np.testing.assert_array_equal(scene.model.potential(probes),potential)
    assert plot.bounds_options['bounds'] == scene.bounds_m
