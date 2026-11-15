"""Project-informed sweep transfer qualification using existing native public APIs.

The independently implemented reference checks live in verification/check_sweep_runs.py.
Cases are authored data, not problem-specific production dispatch.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from emfeeld.model_revisions import ModelStore, encode,decode,put,sha256
from emfeeld.model_runs import execute
from emfeeld.sweeps import run_sweep,inspect_sweep

CASE_DATA={
 'E1':{'source':'examples/marker_regression/E1.json','sources':['negative_line','axial_field'], 'particles':['test_charge'], 'mode':'trajectory','target':'negative_line','role':'source','property':'charge_per_m_C_m','category':'component_property','values':[-2.2e-11,-1.8e-11]},
 'G1':{'source':'examples/marker_regression/G1.json','sources':['source_A','source_B'], 'particles':['body_1','body_2'],'mode':'trajectory','target':'body_1','role':'particle','property':'velocity_m_s','category':'initial_condition','values':[[.14,.06,.04],[.10,.06,.04]]},
 'T1':{'source':'examples/structural_revisions/T1.json','sources':['shell','central_point'],'particles':[],'mode':'static','target':'central_point','role':'source','property':'charge_C','category':'component_property','values':[-4e-10,-6e-10]}
}
PROBES={'E1':[[1.2,.2,.8],[1.5,-.4,1.4]],'G1':[[.5,.7,.3],[.8,-.6,.3]],'T1':[[.4,.3,.2],[3,1,.5],[-1,-.4,.3]]}


def save(path, value):
    put(path,encode(value));return path


def unchanged(records):
    for path,digest in records.items():
        if not path.is_file() or sha256(path.read_bytes())!=digest:
            raise AssertionError(f'baseline artifact changed: {path}')


def frozen(folder):
    return {p:sha256(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}


def qualify(case, output):
    if case not in CASE_DATA:raise ValueError('unknown case')
    v=CASE_DATA[case]
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    raw=(ROOT/v['source']).read_bytes();put(output/'source.json',raw)
    scene=decode(raw)
    origin={'origin':'illustrative_choice','reason':'Frozen illustrative sweep case','evidence':'tools/qualify_sweeps.py; no original textbook givens'}
    assignment={'import_version':1,'model_id':f'sweep-model-{case}', 'revision_id':'root','source_sha256':sha256(raw),
        'source_ids':v['sources'],'particle_ids':v['particles'],'default_origin':origin,
        'interpretation':{'statement':scene['title'],'assumptions':['Fixed prescribed source distributions; independent nonrelativistic test bodies; no backreaction or collision handling'],
            'requirements':['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
            'unresolved':[],'scenario_intent':'illustrative_exploration'}}
    store,ref=ModelStore.import_legacy(output/'source.json',save(output/'import.json',assignment),output/'model')
    inv={'investigation_version':1,'id':'sweep-comparison','model_id':ref['model_id'],'observations':[]}
    for i,pos in enumerate(PROBES[case]):
        for q in ('field','potential'):
            inv['observations'].append({'id':f'{q}_{i}','type':q,'position_m':pos})
    ana={'analysis_version':1,'id':'sweep-resolution','mode':v['mode']}
    if v['mode']=='trajectory':
        ana.update(duration_s=scene['duration_s'],samples=scene['samples'],checks={
            'position_atol_m':1e-6,'velocity_atol_m_s':1e-7,'rtol':1e-7,'max_normalized_energy_drift':1e-7})
        for particle in v['particles']:
            for index in (0,scene['samples']//2,scene['samples']-1):
                for q in ('position','velocity','speed','kinetic_energy','potential_energy','total_energy'):
                    inv['observations'].append({'id':f'{particle}_{q}_{index}',
                        'type':'trajectory_sample','particle_id':particle,'quantity':q,'sample_index':index})
    view={'presentation_version':1,'id':'sweep-view','bounds_m':scene['bounds_m'],
          'entity_order':v['sources']+v['particles']}
    paths=[save(output/name,obj) for name,obj in [('parent.json',ref),('investigation.json',inv),('analysis.json',ana),('presentation.json',view)]]
    baseline=execute(store.path,*paths,output/'template',run_id=f'original-{case}')
    if not baseline['execution_complete']:raise AssertionError(('template failure',baseline))
    protected=frozen(output/'model')|frozen(output/'template')
    expected=store.read(ref)[0]['entities'][v['target']]['properties'][v['property']]
    spec={'sweep_version':1,'id':f'sweep-{case}', 'parent':ref,'target_id':v['target'],
          'expected_role':v['role'],'category':v['category'],'property':v['property'],
          'expected_value':expected,'values':v['values'],'scenario_intent':'teacher_hypothesis',
          'provenance':{'origin':'illustrative_choice','reason':'Deliberately vary exactly one physical property',
                        'evidence':f'Frozen qualification {case} author choices'}}
    result=run_sweep(save(output/'sweep.json',spec),store_path=store.path,
                     using=output/'template',output=output/'sweep')
    if result['status']!='complete':raise AssertionError(('incomplete sweep',result))
    inspect_sweep(output/'sweep');unchanged(protected)
    save(output/'qualification.json',{'case':case,'status':'complete','sweep_input_sha256':sha256((output/'sweep.json').read_bytes()),
        'root_and_template_preserved':True,'member_count':len(v['values']),
        'meaning':'same-author transfer, not an independent authoring benchmark'})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,choices=CASE_DATA)
    parser.add_argument('--output',required=True)
    a=parser.parse_args()
    summary=qualify(a.case,a.output)
    print(encode({'case':a.case,'status':summary['status'],'members':len(summary['members'])}).decode(),end='')
