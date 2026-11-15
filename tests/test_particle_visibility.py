"""Presentation contract using the pre-existing recording backend, not a render."""
from types import SimpleNamespace

import numpy as np

from emfeeld import Superposition, UniformField
from emfeeld.viewer import make_plotter
from test_viewer_presentation import backend  # existing pytest recording fixture


def test_marker_style_does_not_encode_charge_or_change_saved_positions(backend):
    positions = [np.array([[0.,0.,0.],[1.,0.,0.],[2.,0.,0.]]),
                 np.array([[0.,1.,0.],[1.,2.,0.],[2.,3.,0.]])]
    old = [r.copy() for r in positions]
    scene = SimpleNamespace(title='display markers',bounds_m=(-3,3,-3,3,-3,3),
                            model=Superposition((UniformField('gravity',(0,0,0)),)),
                            duration_s=2,samples=3,particles=(object(),object()),
                            trajectories=lambda: tuple(SimpleNamespace(position_m=r) for r in positions))
    p = make_plotter(scene,resolution=5)
    by_name = {kw.get('name'): (mesh,kw) for mesh,kw in p.meshes if kw.get('name')}
    assert p.meshes[0][1]['opacity'] == 0.35
    assert {'particle_0','particle_1','trajectory_0','trajectory_1'} <= set(by_name)
    for i in range(2):
        mesh,opts=by_name[f'particle_{i}']
        assert opts['color']=='magenta' and opts['style']=='surface'
        assert 'point_size' not in opts and 'render_points_as_spheres' not in opts
        assert mesh.sphere_options['radius'] == 1.0
        actor = p.actors[f'particle_{i}']
        assert actor.scale == (0.025 * 6,) * 3
        assert actor.use_bounds is False
        assert opts['lighting'] is False and opts['show_scalar_bar'] is False
        assert by_name[f'trajectory_{i}'][1]['color']=='black'
    for index in (0,2,1,0):
        p._emfeeld_playback.seek(index)
        for i,r in enumerate(positions):
            np.testing.assert_array_equal(p.actors[f'particle_{i}'].position,r[index])
            np.testing.assert_array_equal(r,old[i])
    assert 'not charge sign' in p.text_actors['particle_key'].input
    assert 'not field lines' in p.text_actors['particle_key'].input
