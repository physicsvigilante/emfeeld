"""Real E1/G1 polygonal-marker regression: no mock renderer or silent skips."""
from pathlib import Path
import numpy as np
import pytest

from emfeeld.scene import Scene, load_scene
from emfeeld.viewer import make_plotter
from test_particle_visibility_runtime import magenta_region
from test_playback_runtime import key, tick

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('case', ['E1','G1'])
@pytest.mark.parametrize('camera', ['iso','xy'])
def test_polygonal_markers_all_samples_controls_and_pixels(case,camera,monkeypatch,tmp_path):
    scene=load_scene(ROOT/'examples/marker_regression'/f'{case}.json')
    ts=scene.trajectories()
    keys=('time_s','position_m','velocity_m_s','kinetic_J','potential_J')
    frozen=[{k:getattr(t,k).copy() for k in keys} for t in ts]
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('unexpected reintegration'))
    p=make_plotter(scene,recorded=ts,off_screen=True)
    try:
        if camera=='xy':p.view_xy()
        p.show(auto_close=False,interactive=False)
        ctrl=p._emfeeld_playback
        actors=[p.actors[f'particle_{i}'] for i in range(len(ts))]
        local_points=[a.mapper.dataset.points.copy() for a in actors]
        for actor in actors:
            assert actor.mapper.dataset.GetNumberOfPolys()>0
            assert actor.mapper.dataset.GetNumberOfVerts()==0
            assert actor.prop.GetRepresentation()==2
            assert not actor.use_bounds
        for index,time in enumerate(ts[0].time_s):
            ctrl.seek(float(time))
            assert ctrl.state.index==index
            for i,(a,t) in enumerate(zip(actors,ts)):
                assert a is p.actors[f'particle_{i}']
                np.testing.assert_array_equal(a.position,t.position_m[index])
                np.testing.assert_array_equal(a.mapper.dataset.points,local_points[i])
        def check(index):
            assert ctrl.state.index==index
            for a,t in zip(actors,ts):np.testing.assert_array_equal(a.position,t.position_m[index])
        clock=[0.];ctrl._clock=lambda:clock[0]
        key(p,'Home');check(0)
        key(p,'Right');check(1)
        key(p,'Left');check(0)
        key(p,'space');assert ctrl.state.playing
        clock[0]=ctrl.state.replay_seconds/2;tick(p);check(scene.samples//2)
        key(p,'space');assert not ctrl.state.playing
        key(p,'Home');check(0)
        for index in (0,scene.samples//2,scene.samples-1):
            slider=ctrl.slider
            slider.GetRepresentation().SetValue(float(ts[0].time_s[index]))
            slider.InvokeEvent('EndInteractionEvent');check(index)
            image=p.screenshot(str(tmp_path/f'{case}_{camera}_{index:03d}.png'))
            for i,t in enumerate(ts):
                pixels,_=magenta_region(p,image,t.position_m[index])
                assert pixels>=80,(case,camera,index,i,pixels)
            np.testing.assert_array_equal(p.renderer.cube_axes_actor.bounds,scene.bounds_m)
        # Keep particles and paths only, then verify the midpoint again.
        for name,actor in p.actors.items():
            if hasattr(actor,'mapper') and hasattr(actor.mapper,'dataset'):
                if not name.startswith(('particle_','trajectory_')):actor.visibility=False
        ctrl.seek(float(ts[0].time_s[scene.samples//2]))
        image=p.screenshot(str(tmp_path/f'{case}_{camera}_declutter.png'))
        for t in ts:
            pixels,_=magenta_region(p,image,t.position_m[scene.samples//2])
            assert pixels>=80
        for t,saved in zip(ts,frozen):
            for k in keys:np.testing.assert_array_equal(getattr(t,k),saved[k])
    finally:p.close()
