"""Recorded revision/run binding and presentation-only changes using real VTK."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from emfeeld import model_runs as runs
from emfeeld.model_revisions import decode, encode
from emfeeld.scene import Scene

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('revision_fixtures',ROOT/'tests/test_model_revisions.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def test_run03_presentation_changes_no_new_revision_or_integration(tmp_path,monkeypatch):
    store,ref=f.imported(tmp_path);_,out=f.execute(tmp_path,store,ref)
    original=store.read(ref)[1]; inventory=(out/'integrity.json').read_bytes()
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('reintegration'))
    monkeypatch.setattr(runs.study,'integrate',lambda *a,**k:pytest.fail('reintegration'))
    p=f.configs(ref)[2]
    p.update(id='another-view',replay_seconds=20.,camera=[[7,5,4],[0,0,0],[0,0,1]],entity_order=['probe','right','left'])
    path=f.write(tmp_path/'presentation-new.json',p)
    target=tmp_path/'new-presentation'
    runs.present_run(out,presentation_path=path,sample_index=10,screenshot_directory=target)
    manifest=decode((target/'presentation.json').read_bytes())
    assert manifest['reference']==ref and manifest['sample_index']==10 and manifest['time_s']==.5
    assert store.read(ref)[1]==original and (out/'integrity.json').read_bytes()==inventory
    import pyvista as pv
    image=pv.read_texture(str(target/'frame.png')).to_array()
    assert image.shape[:2]==(850,1200) and np.std(image)>1


def test_run01_old_root_view_after_new_revision_keeps_identity(tmp_path,monkeypatch):
    store,ref=f.imported(tmp_path);_,out=f.execute(tmp_path,store,ref,name='root-run')
    d=f.revise(tmp_path,store,f.proposal(ref));f.execute(tmp_path,store,d['reference'],name='child-run')
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('reintegration'))
    monkeypatch.setattr(runs.study,'integrate',lambda *a,**k:pytest.fail('reintegration'))
    runs.present_run(out,screenshot_directory=tmp_path/'root-view')
    assert decode((tmp_path/'root-view/presentation.json').read_bytes())['reference']==ref


def test_no_render_into_sealed_evidence_and_static_mode_not_motion(tmp_path):
    store,ref=f.imported(tmp_path);_,out=f.execute(tmp_path,store,ref)
    with pytest.raises(ValueError,match='outside'):runs.present_run(out,screenshot_directory=out/'image')
    _,static=f.execute(tmp_path,store,ref,mode='static',name='static')
    with pytest.raises(ValueError,match='no complete'):runs.present_run(static,screenshot_directory=tmp_path/'static-view')


def test_invalid_display_does_not_modify_model(tmp_path):
    store,ref=f.imported(tmp_path);_,out=f.execute(tmp_path,store,ref)
    data=f.configs(ref)[2];data['camera']=[[0,0,0],[0,0,0],[0,0,1]]
    with pytest.raises(ValueError,match='resolved'):
        runs.present_run(out,presentation_path=f.write(tmp_path/'bad-display.json',data),screenshot_directory=tmp_path/'bad')


def test_static_sources_are_visible_without_invented_motion(tmp_path,monkeypatch):
    scene=f.base_scene();scene['particles']=[]
    store,ref=f.imported(tmp_path,scene,mutate=lambda x:x.update(particle_ids=[]))
    _,out=f.execute(tmp_path,store,ref,mode='static')
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('reintegration'))
    monkeypatch.setattr(runs.study,'integrate',lambda *a,**k:pytest.fail('reintegration'))
    runs.present_run(out,screenshot_directory=tmp_path/'static-field')
    assert decode((tmp_path/'static-field/presentation.json').read_bytes())['time_s'] is None
    with pytest.raises(ValueError,match='no physical sample'):
        runs.present_run(out,sample_index=1,screenshot_directory=tmp_path/'fake-motion')
