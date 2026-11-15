"""Investigation sweep contract: native reuse, exact comparison and failure history."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from emfeeld import model_runs
from emfeeld.model_revisions import ModelStore, RevisionError, encode,put,sha256,decode
from emfeeld.sweeps import run_sweep,inspect_sweep,_member_id


def file(path,obj):
    put(path,encode(obj));return path


def inventory(folder):
    return {p.relative_to(folder).as_posix():sha256(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}


def setup_case(tmp, *, kind='electric', mode='static'):
    if kind=='electric':
        sources=[{'type':'point','charge_C':1e-9,'center_m':[0.,0.,0.]},
                 {'type':'uniform','field_N_C':[0.,0.,.02]}]
        particle={'charge_C':1e-6,'mass_kg':1e-5,'position_m':[1.,0.,0.], 'velocity_m_s':[0.,.05,0.]}
    else:
        sources=[{'type':'point','mass_kg':2e10,'center_m':[0.,0.,0.]},
                 {'type':'uniform','field_m_s2':[0.,0.,-.01]}]
        particle={'mass_kg':1.,'position_m':[1.,0.,0.], 'velocity_m_s':[0.,.1,0.]}
    scene={'schema_version':1,'title':'Sweep bounded test', 'kind':kind,
        'sources':sources,'particles':[particle], 'duration_s':1.0,'samples':21,
        'bounds_m':[-3,3,-3,3,-3,3]}
    raw=encode(scene);put(tmp/'scene.json',raw)
    assignment={'import_version':1,'model_id':'sweep-test','revision_id':'root','source_sha256':sha256(raw),
        'source_ids':['point','background'],'particle_ids':['body'],
        'default_origin':{'origin':'illustrative_choice','reason':'deliberate example','evidence':'test fixture'},
        'interpretation':{'statement':'Prescribed fields','assumptions':['fixed prescribed sources'],
           'requirements':['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
           'unresolved':[],'scenario_intent':'illustrative_exploration'}}
    store,ref=ModelStore.import_legacy(tmp/'scene.json',file(tmp/'assignment.json',assignment),tmp/'store')
    inv={'investigation_version':1,'id':'common','model_id':ref['model_id'],
         'observations':[{'id':'field','type':'field','position_m':[1.,0.,0.]},
                         {'id':'potential','type':'potential','position_m':[1.,0.,0.]}]}
    ana={'analysis_version':1,'id':'analysis','mode':mode}
    if mode=='trajectory':
        inv['observations'].extend([{'id':f'p{i}','type':'trajectory_sample',
                                  'particle_id':'body','quantity':'position','sample_index':i}
                                 for i in (0,10,20)])
        ana.update(duration_s=1.,samples=21,checks={
            'position_atol_m':1e-6,'velocity_atol_m_s':1e-7,
            'rtol':1e-7,'max_normalized_energy_drift':1e-7})
    presentation={'presentation_version':1,'id':'view','bounds_m':[-3,3,-3,3,-3,3],
                  'entity_order':['point','background','body']}
    paths=[file(tmp/n,v) for n,v in [('root.json',ref),('inv.json',inv),('ana.json',ana),('view.json',presentation)]]
    summary=model_runs.execute(store.path,*paths,tmp/'base',run_id='root-run')
    assert summary['execution_complete'],summary
    prop='charge_C' if kind=='electric' else 'mass_kg'
    old=1e-9 if kind=='electric' else 2e10
    values=[2e-9,3e-9] if kind=='electric' else [3e10,4e10]
    spec={'sweep_version':1,'id':'various','parent':ref,
        'target_id':'point','expected_role':'source','category':'component_property',
        'property':prop,'expected_value':old,'values':values,'scenario_intent':'teacher_hypothesis',
        'provenance':{'origin':'illustrative_choice','reason':'Study controlled change','evidence':'Test hypothesis'}}
    return store,ref,spec


def go(tmp,store,spec,name='sweep-output'):
    # Preserve a literal overflowing JSON exponent rather than encoding infinity.
    payload = file(tmp/(name+'.spec.json'),spec) if not any(isinstance(x,float) and not np.isfinite(x) for x in spec.get('values',[])) else (tmp/(name+'.spec.json'))
    if not payload.exists(): payload.write_text(encode({**spec,'values':[2e-9]}).decode().replace('2e-09','1e999'))
    return run_sweep(payload,store_path=store.path,
                     using=tmp/'base',output=tmp/name)


@pytest.mark.parametrize('kind,mode', [('electric','static'),('electric','trajectory'),('gravity','static'),('gravity','trajectory')])
def test_native_single_property_transfer_preserves_model_and_baseline(tmp_path,kind,mode):
    store,ref,spec=setup_case(tmp_path,kind=kind,mode=mode)
    parent=inventory(store.path);sealed=inventory(tmp_path/'base')
    report=go(tmp_path,store,spec)
    assert report['status']=='complete'
    assert len(report['members'])==2 and all(x['status']=='complete' for x in report['members'])
    assert inventory(tmp_path/'base')==sealed
    for name,digest in parent.items():assert sha256((store.path/name).read_bytes())==digest
    assert report['baseline']['reference']==ref
    assert inspect_sweep(tmp_path/'sweep-output')==report
    for m in report['members']:
        child,_=store.read(m['reference']);old=store.read(ref)[0]
        assert child['parent']==ref
        assert child['entities']['background']==old['entities']['background']
        assert child['entities']['body']==old['entities']['body']
        assert child['entities']['point']['properties'][spec['property']]==m['value']
        compared=decode((tmp_path/'sweep-output'/m['comparison_path']).read_bytes())
        assert compared['left_revision']==ref and compared['right_revision']==m['reference']
        assert all(row['comparison']=='variant_minus_baseline' for row in compared['measurements'])
        if mode=='trajectory':
            rows=[r for r in compared['measurements'] if r['id']=='p20']
            assert len(rows)==1 and rows[0]['time_s']==1.


def test_existing_rejected_member_does_not_prevent_valid_following_member(tmp_path):
    store,ref,spec=setup_case(tmp_path,kind='gravity')
    spec['values']=[-1.,3e10]
    report=go(tmp_path,store,spec)
    assert report['status']=='partial'
    assert [m['status'] for m in report['members']]==['rejected','complete']
    assert report['members'][0]['reference'] is None
    assert report['members'][1]['reference'] is not None
    assert inspect_sweep(tmp_path/'sweep-output')==report
    directory=store.path/'proposals'/sha256(_member_id(spec['id'],1).encode())
    assert decode((directory/'decision.json').read_bytes())['status']=='rejected'


def test_valid_construction_can_have_failed_numerical_member_without_touching_baseline(tmp_path):
    store,ref,spec=setup_case(tmp_path,mode='trajectory')
    spec.update(target_id='body',expected_role='particle',category='initial_condition',
                property='position_m',expected_value=[1.,0.,0.],values=[[0.,0.,0.],[1.1,0.,0.]])
    baseline=inventory(tmp_path/'base')
    report=go(tmp_path,store,spec)
    assert report['status']=='partial',report
    assert report['members'][0]['decision']=='accepted'
    assert report['members'][0]['status']=='partial'
    assert report['members'][1]['status']=='complete'
    assert inventory(tmp_path/'base')==baseline
    assert inspect_sweep(tmp_path/'sweep-output')==report


@pytest.mark.parametrize('edit',[
    lambda x:x.update(sweep_version=True),
    lambda x:x.update(id='x'*40),
    lambda x:x.update(values=[]),
    lambda x:x.update(values=[float(i+2)*1e-9 for i in range(9)]),
    lambda x:x.update(values=[1e-9]),
    lambda x:x.update(values=[2e-9,2e-9]),
    lambda x:x.update(values=['2e-9']),
    lambda x:x.update(values=[True]),
    lambda x:x.update(values=[float('inf')]),
    lambda x:x.update(expected_role='particle'),
    lambda x:x.update(expected_value=1e-7),
    lambda x:x.update(target_id='missing'),
    lambda x:x.update(provenance={'origin':'computed_result','reason':'x','evidence':'y'}),
    lambda x:x.update(scenario_intent='source_interpretation'),
    lambda x:x.update(unknown='extra'),
])
def test_invalid_specs_do_not_create_attempts_or_store_entries(tmp_path,edit):
    store,ref,spec=setup_case(tmp_path)
    before=inventory(store.path)
    edit(spec)
    with pytest.raises((ValueError,RevisionError)):
        go(tmp_path,store,spec)
    assert not (tmp_path/'sweep-output').exists()
    assert inventory(store.path)==before


def test_wrong_template_exact_revision_does_not_create_sweep(tmp_path):
    store,ref,spec=setup_case(tmp_path)
    wrong=deepcopy(spec);wrong['parent']['sha256']='0'*64
    with pytest.raises(RevisionError):go(tmp_path,store,wrong)
    assert not (tmp_path/'sweep-output').exists()


def test_collision_and_existing_output_refused_without_mutation(tmp_path):
    store,_,spec=setup_case(tmp_path)
    report=go(tmp_path,store,spec)
    old=inventory(store.path);snapshot=inventory(tmp_path/'sweep-output')
    with pytest.raises(FileExistsError):go(tmp_path,store,spec)
    with pytest.raises(RevisionError,match='already reserved'):
        go(tmp_path,store,spec,name='other-out')
    assert inventory(store.path)==old
    assert inventory(tmp_path/'sweep-output')==snapshot


def test_no_output_alias_store_or_template(tmp_path):
    store,_,spec=setup_case(tmp_path)
    path=file(tmp_path/'sweep.json',spec)
    for dest in (store.path/'nested',tmp_path/'base'/'nested'):
        with pytest.raises(ValueError):
            run_sweep(path,store_path=store.path,using=tmp_path/'base',output=dest)


def test_detect_tampering_in_sweep_and_sealed_member(tmp_path):
    store,_,spec=setup_case(tmp_path)
    go(tmp_path,store,spec)
    root=tmp_path/'sweep-output'
    assert inspect_sweep(root)['status']=='complete'
    path=root/'member-01'/'comparison.json'
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(RevisionError,match='(changed|inventory)'):
        inspect_sweep(root)


def test_modified_template_is_rejected_without_mutating_store(tmp_path):
    store,_,spec=setup_case(tmp_path)
    template=tmp_path/'base'/'analysis.json';template.write_bytes(template.read_bytes()+b' ')
    old=inventory(store.path)
    with pytest.raises(RevisionError,match='(changed|inventory)'):
        go(tmp_path,store,spec)
    assert inventory(store.path)==old
    assert not (tmp_path/'sweep-output').exists()
