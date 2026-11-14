"""Real renderer tests for recorded-run presentation; no extra physical solve."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from emfeeld import study
from emfeeld.scene import Scene
from emfeeld.viewer import make_plotter

ROOT=Path(__file__).resolve().parents[1]


def prepared(tmp_path):
    path=ROOT/'examples/studies/electric.json'
    out=tmp_path/'study'
    study.run_study(path,out)
    return out


def test_recorded_render_and_slider_do_not_integrate(tmp_path,monkeypatch):
    out=prepared(tmp_path)
    scene,trajectories=study.load_recorded(out/'baseline')
    before=trajectories[0].position_m.copy()
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('viewer reintegrated'))
    monkeypatch.setattr(study,'integrate',lambda *a,**k:pytest.fail('study reintegrated'))
    plot=make_plotter(scene,recorded=trajectories,potential_clim=(-30,0),study_label='baseline',off_screen=True)
    try:
        plot.show(auto_close=False)
        plot._emfeeld_playback.seek(.5)
        assert plot._emfeeld_playback.state.index==50
        image=plot.screenshot(str(tmp_path/'recorded.png'))
        assert image.shape[:2]==(850,1200)
        assert np.std(image)>1
        assert (tmp_path/'recorded.png').stat().st_size>1000
    finally:plot.close()
    assert np.array_equal(before,trajectories[0].position_m)


def test_two_views_share_range_and_camera_and_expose_configuration(tmp_path,monkeypatch):
    out=prepared(tmp_path)
    records,clim=study._view_data(out)
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('viewer reintegrated'))
    cameras=[];ranges=[]
    for name,(scene,trajectories) in zip(study.CONFIGURATIONS,records):
        p=make_plotter(scene,recorded=trajectories,potential_clim=clim,study_label=name,off_screen=True)
        try:
            p.show(auto_close=False)
            cameras.append(np.asarray([p.camera.GetPosition(), p.camera.GetFocalPoint(), p.camera.GetViewUp()]))
            ranges.append(tuple(p.scalar_bars['Potential [V]'].GetLookupTable().GetRange()))
        finally:p.close()
    np.testing.assert_allclose(cameras[0],cameras[1],atol=0,rtol=0)
    assert ranges[0]==ranges[1]==clim
    assert clim[0]<clim[1]


def test_full_capture_makes_six_frames_without_solving(tmp_path,monkeypatch):
    out=prepared(tmp_path)
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('viewer reintegrated'))
    monkeypatch.setattr(study,'integrate',lambda *a,**k:pytest.fail('study reintegrated'))
    result=study.render_study(out)
    assert result['status']=='rendered_not_teacher_accepted'
    assert len(result['frames'])==6
    assert sorted(set(x['time_s'] for x in result['frames']))==[0,.5,1]
    for frame in result['frames']:
        assert study.digest((out/frame['file']).read_bytes())==frame['sha256']


def test_swapped_complete_configuration_is_not_accepted(tmp_path):
    out=prepared(tmp_path)
    import shutil
    shutil.rmtree(out/'variant');shutil.copytree(out/'baseline',out/'variant')
    with pytest.raises(ValueError,match='single change'):study._view_data(out)


def test_incomplete_or_corrupt_arrays_fail_before_viewer(tmp_path,monkeypatch):
    out=prepared(tmp_path);scene,ts=study.load_recorded(out/'baseline')
    bad=deepcopy(ts);bad[0].position_m[0,0]+=1
    with pytest.raises(ValueError,match='initial conditions'):make_plotter(scene,recorded=bad,off_screen=True)
    with pytest.raises(ValueError,match='complete trajectories'):make_plotter(scene,recorded=(None,),off_screen=True)
    with pytest.raises(ValueError,match='potential_clim'):make_plotter(scene,recorded=ts,potential_clim=[0,0],off_screen=True)
