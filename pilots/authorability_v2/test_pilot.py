"""Cumulative guards for frozen-engine JSON authoring, not a blind-LLM score."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('authorability_v2_runner',HERE/'run_pilot.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)
CASES=pilot.load(HERE/'cases.json')['cases']
BY_ID={c['id']:c for c in CASES}
REFS=pilot.load(HERE/'references.json')['checks']

@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    out=tmp_path_factory.mktemp('authorability_v2')/'run'
    summary=pilot.run(out)
    return out,summary

@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_native_cli_expected_outcome(case,completed):
    _,summary=completed
    result=next(r for r in summary['cases'] if r['id']==case['id'])
    assert result['expected_outcome_verified'],result['issues']
    assert result['status']==('UNSUPPORTED' if case['role']=='limitation_control' else 'PASS')
    assert all(c['passed'] for c in result['checks'])

@pytest.mark.parametrize('case',[c for c in CASES if c['role']=='execution_target'],ids=[c['id'] for c in CASES if c['role']=='execution_target'])
def test_execution_inputs_are_packets_not_answer_scripts(case):
    packet=pilot.load(HERE/case['file'])
    assert set(packet)=={'observation_schema_version','scene','observations','notes'}
    assert packet['observation_schema_version']==1
    assert packet['scene']['schema_version']==1
    assert not any('expectation' in r for r in packet['observations'])
    assert case['file'].startswith('packets/') and case['file'].endswith('.json')

@pytest.mark.parametrize('case',[c for c in CASES if c['source_scene_reused']],ids=[c['id'] for c in CASES if c['source_scene_reused']])
def test_reused_scenes_not_silently_changed(case):
    packet=pilot.load(HERE/case['file'])
    assert packet['scene']==pilot.load(pilot.ROOT/case['source_scene_reused'])

@pytest.mark.parametrize('mutation',['no_event','bad_time','wrong_unit','missing_state','missing_refinement','wrong_shape'])
def test_judge_rejects_false_success(mutation,completed):
    folder,_=completed;ident='P04-uniform-motion';case=BY_ID[ident]
    report=pilot.load(folder/ident/'native.json')
    r=next(r for r in report['results'] if r['id']=='exit_plane')
    if mutation=='no_event':r['status']='no_event';r['state']=None
    elif mutation=='bad_time':r['state']['time_s']=100
    elif mutation=='wrong_unit':r['units']['time_s']='ms'
    elif mutation=='missing_state':r['state']=None
    elif mutation=='missing_refinement':r['diagnostics']['passes']=[]
    elif mutation=='wrong_shape':r['state']['position_m']=[[2.25,.675,0]]
    judged=pilot.assess(case,report,REFS[ident],0,'')
    assert not judged['expected_outcome_verified']
    assert judged['status']=='FAIL'

@pytest.mark.parametrize('actual,expected',[(True,1),([1],1),(1,[1]),([1,2],[1]),(float('nan'),0)])
def test_comparison_rejects_type_shape_or_nonfinite(actual,expected):
    assert not pilot.close(actual,expected,1e-7,1e-7)

def test_all_parent_files_frozen():
    assert pilot.freeze_check()['passed']
    assert pilot.freeze_check()['checked_local_files']==134

def test_supplied_microgram_mass_and_centimetres_preserved():
    p=pilot.load(HERE/BY_ID['P07-numerical-stop']['file'])['scene']['particles'][0]
    assert p['mass_kg']==2e-9 and p['charge_C']==1e-9
    assert p['position_m']==[.1,0,0] and p['velocity_m_s']==[-1,0,0]

def test_controls_are_not_counted_as_solved(completed):
    _,summary=completed
    assert summary['counts']=={'PASS':8,'UNSUPPORTED':2,'FAIL':0}
    assert summary['verified']
    assert sum(c['source'] is None for c in CASES if c['role']=='execution_target')==1

def test_guard_rejection_does_not_discard_valid_probe(completed):
    out,_=completed
    report=pilot.load(out/'L01-rest-turning/native.json')
    assert report['status']=='partial'
    assert report['results'][0]['state'] is None
    assert report['results'][1]['status']=='ok'
    assert report['results'][1]['value'] is not None

def test_failed_schema_has_no_fabricated_measurements(completed):
    out,_=completed
    assert not (out/'L02-ring/native.json').exists()
    assert "unsupported source type: 'ring'" in (out/'L02-ring/run.stderr').read_text()
