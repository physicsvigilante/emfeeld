from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from numpy.testing import assert_allclose
from emfeeld import scene_from_dict, load_scene, PointSource, SphericalShell
from emfeeld.cli import main, run_scene
from emfeeld.viewer import sample_values

ROOT=Path(__file__).resolve().parents[1]
BASE={'schema_version':1,'title':'test','kind':'electric','sources':[{'type':'point','charge_C':1e-9}],
      'bounds_m':[-2,2,-2,2,-2,2]}


@pytest.mark.parametrize('path',sorted((ROOT/'examples').glob('*.json')),ids=lambda x:x.stem)
def test_examples_execute(path):
    scene=load_scene(path)
    trajectories,summary=run_scene(scene)
    assert summary['source_count'] == len(scene.model.sources)
    for trajectory in trajectories:
        assert len(trajectory.time_s)==scene.samples
        assert np.isfinite(trajectory.position_m).all()
        assert trajectory.normalized_energy_drift < 1e-6


@pytest.mark.parametrize('key,value', [('schema_version',True),('schema_version',2),('kind','bad'),
    ('title',''),('sources',[]),('samples',2.5),('bounds_m',[-1,-1,-1,1,-1,1]),('duration_s',0),('particles',{})])
def test_scene_validation(key,value):
    data=deepcopy(BASE);data[key]=value
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_unknown_keys_and_units_rejected():
    for edit in [{'schema_version':1,'typo':1}, {'sources':[{'type':'point','mass_kg':1}]},
                 {'sources':[{'type':'solid_sphere','charge_C':1}]},
                 {'sources':[{'type':'line','charge_per_m_C_m':1}]},
                 {'sources':[{'type':'conductor','charge_C':1}]}]:
        data=deepcopy(BASE);data.update(edit)
        with pytest.raises(ValueError):
            scene_from_dict(data)


def test_duplicate_json_key_rejected(tmp_path):
    path=tmp_path/'bad.json';path.write_text('{"title":"a","title":"b"}')
    with pytest.raises(ValueError,match='duplicate'):
        load_scene(path)


def test_scene_composition_authoring_without_core_edits():
    data=deepcopy(BASE)
    data['sources']=[{'type':'solid_sphere','charge_C':(i+1)*1e-10,'radius_m':0.3,
                     'center_m':[i,0,0]} for i in range(12)]
    scene=scene_from_dict(data)
    p=np.array([2,3,4])
    assert_allclose(scene.model.field(p),sum(s.field(p) for s in scene.model.sources))


def test_cli_validation_run_roundtrip(tmp_path,capsys):
    example=ROOT/'examples'/'ideal_sun.json'; out=tmp_path/'result.npz'
    assert main(['validate',str(example)])==0
    assert json.loads(capsys.readouterr().out)['valid_schema']
    assert main(['run',str(example),'--output',str(out)])==0
    summary=json.loads(capsys.readouterr().out)
    assert summary['trajectory_count']==2
    with np.load(out,allow_pickle=False) as data:
        assert data['particle_0_position_m'].shape==(1001,3)
        assert json.loads(str(data['summary_json']))==summary
        assert json.loads(str(data['scene_json']))['kind']=='gravity'


def test_cli_bad_file_returns_error(tmp_path,capsys):
    path=tmp_path/'bad.json';path.write_text('{"bad":1}')
    assert main(['run',str(path)])==2
    assert 'emfeeld:' in capsys.readouterr().err


def test_viewer_sampling_preserves_holes_and_scalar_potential():
    point=PointSource('electric',1)
    positions=np.array([[0,0,0],[1,0,0],[2,0,0]])
    fields=sample_values(point,positions)
    assert np.isnan(fields[0]).all()
    assert_allclose(fields[1:],point.field(positions[1:]))
    potentials=sample_values(point,positions,potential=True)
    assert np.isnan(potentials[0])
    assert_allclose(potentials[1:],point.potential(positions[1:]))
    shell=SphericalShell('electric',1)
    assert np.isnan(sample_values(shell,positions)[1]).all()
    assert np.isfinite(sample_values(shell,positions,potential=True)).all()
