"""Authoring guards; these tests do not relabel the known flux limitation as solved."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from emfeeld import scene_from_dict

HERE=Path(__file__).resolve().parent
PACKET=json.loads((HERE/'cases.json').read_text())
CASES={c['id']:c for c in PACKET['cases']}
spec=importlib.util.spec_from_file_location('pilot_observations',HERE/'run_pilot.py')
observations=importlib.util.module_from_spec(spec);spec.loader.exec_module(observations)


@pytest.mark.parametrize('case',PACKET['cases'],ids=lambda c:c['id'])
def test_authored_scene_identity_and_schema(case):
    path=HERE/case['scene']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==case['scene_sha256']
    data=json.loads(path.read_text()); scene=scene_from_dict(data)
    assert scene.model.kind=='electric'
    assert case['parameter_provenance'] and case['interpretation_notes']
    assert case['authoring_attempt']==1
    assert case['pdf_page_start']<=case['pdf_page_end']
    if scene.particles:assert scene.model.trajectory_safe


@pytest.mark.parametrize('cid,mutation',[
    ('SC-55','unit_error'),('SC-35','sheet_sign'),('SC-96','corner_sign'),
    ('SC-122','equal_charges_not_densities'),('NUM-31','positive_cavity'),('SC-99','positive_test_charge'),
])
def test_observations_reject_wrong_physical_authoring(cid,mutation):
    case=CASES[cid];raw=deepcopy(json.loads((HERE/case['scene']).read_text()))
    if mutation=='unit_error':raw['sources'][0]['charge_C']*=1e3
    elif mutation=='sheet_sign':raw['sources'][1]['charge_per_m2_C_m2']*=-1
    elif mutation=='corner_sign':raw['sources'][2]['charge_C']*=-1
    elif mutation=='equal_charges_not_densities':
        for s in raw['sources']:s['charge_C']=case['parameters']['total_charge_C']/2
    elif mutation=='positive_cavity':raw['sources'][1]['charge_C']*=-1
    elif mutation=='positive_test_charge':raw['particles'][0]['charge_C']*=-1
    scene=scene_from_dict(raw);result={'checks':[]}
    observations.CHECKS[cid](scene,case['parameters'],scene.trajectories(),result)
    assert any(c['required'] and not c['passed'] for c in result['checks'])


def test_all_available_parent_files_remain_frozen():
    assert len(observations.frozen())==34
