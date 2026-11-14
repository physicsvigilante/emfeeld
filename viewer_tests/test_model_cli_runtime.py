"""Real recorded rendering through the native convenience command."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from emfeeld import cli, model_cli, model_runs
from emfeeld.model_revisions import decode
from emfeeld.scene import Scene

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_fixtures',ROOT/'tests/test_model_revisions.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def setup(tmp_path):
    store,root=f.imported(tmp_path);_,prior=f.execute(tmp_path,store,root,name='prior')
    path=f.write(tmp_path/'revision.json',f.proposal(root))
    return store,root,prior,path


def test_native_apply_snapshot_uses_new_recorded_arrays_without_reintegration(tmp_path,monkeypatch):
    store,root,prior,path=setup(tmp_path)
    original_execute=model_runs.execute
    def execute(*args,**kwargs):
        result=original_execute(*args,**kwargs)
        monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('viewer recalculated trajectory'))
        monkeypatch.setattr(model_runs.study,'integrate',lambda *a,**k:pytest.fail('viewer recalculated trajectory'))
        return result
    monkeypatch.setattr(model_runs,'execute',execute)
    out=tmp_path/'apply'
    result=model_cli.apply_revision(path,store_path=store.path,using=prior,output=out,render=True,sample_index=10,run_id='native-render')
    assert result['status']=='complete' and result['presentation']['status']=='rendered'
    receipt=decode((out/'presentation/presentation.json').read_bytes())
    assert receipt['reference']==result['decision']['reference'] and receipt['time_s']==.5
    assert receipt['run_id']=='native-render'
    import pyvista as pv
    image=pv.read_texture(str(out/'presentation/frame.png')).to_array()
    assert image.shape[:2]==(850,1200) and np.std(image)>1
    assert model_runs.inspect_run(out/'run')[2]['execution_complete']


def test_cli_render_roundtrip_from_paths_with_spaces(tmp_path,capsys):
    parent=tmp_path/'teaching folder';parent.mkdir()
    store,root,prior,path=setup(parent);out=parent/'recorded new run'
    assert cli.main(['model','apply',str(path),'--store',str(store.path),'--using',str(prior),
        '--output',str(out),'--render','--sample-index','10'])==0
    assert (out/'presentation/frame.png').stat().st_size>1000
    assert model_runs.inspect_run(out/'run')[2]['execution_complete']


def test_existing_recorded_view_can_reopen_after_apply_without_resolving_latest(tmp_path,monkeypatch):
    store,root,prior,path=setup(tmp_path);out=tmp_path/'apply'
    result=model_cli.apply_revision(path,store_path=store.path,using=prior,output=out)
    monkeypatch.setattr(Scene,'trajectories',lambda *a:pytest.fail('reintegration'))
    monkeypatch.setattr(model_runs.study,'integrate',lambda *a,**k:pytest.fail('reintegration'))
    assert cli.main(['model','view',str(out/'run'),'--sample-index','10','--output',str(tmp_path/'reopened')])==0
    assert decode((tmp_path/'reopened/presentation.json').read_bytes())['reference']==result['decision']['reference']
