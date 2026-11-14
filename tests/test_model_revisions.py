"""Prospective identity/revision contract exercised without apparatus-specific dispatch."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from emfeeld.model_revisions import (ModelStore, RevisionError, encode, decode, sha256,
                                     validate_snapshot, derive)
from emfeeld import model_runs as runs

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    path.write_bytes(encode(data)); return path


def base_scene():
    return {'schema_version': 1, 'title': 'Reusable system', 'kind': 'electric',
            'sources': [{'type': 'solid_sphere', 'charge_C': -1e-9, 'radius_m': 2., 'center_m': [-.2, 0, 0]},
                        {'type': 'solid_sphere', 'charge_C': -2e-9, 'radius_m': 2., 'center_m': [.2, 0, 0]}],
            'particles': [{'mass_kg': 1e-6, 'charge_C': 1e-6, 'position_m': [.3, .2, .1], 'velocity_m_s': [0, .1, 0]}],
            'duration_s': 1., 'samples': 21, 'bounds_m': [-3, 3, -3, 3, -3, 3]}


def assignment(raw, source_ids=None, particle_ids=None):
    return {'import_version': 1, 'model_id': 'model', 'revision_id': 'root', 'source_sha256': sha256(raw),
            'source_ids': source_ids or ['left', 'right'], 'particle_ids': particle_ids if particle_ids is not None else ['probe'],
            'default_origin': {'origin': 'illustrative_choice', 'reason': 'Declared qualification instance', 'evidence': 'Test fixture, not textbook givens'},
            'interpretation': {'statement': 'Explore this supported physical system.',
                'assumptions': ['Prescribed fixed sources, independent nonrelativistic test particle.'],
                'requirements': ['fixed_prescribed_sources', 'independent_nonrelativistic_test_particles'],
                'unresolved': [], 'scenario_intent': 'illustrative_exploration'}}


def imported(tmp_path, scene=None, mutate=None, name='store'):
    raw = encode(scene or base_scene()); spec = assignment(raw)
    if mutate: mutate(spec)
    source = tmp_path/(name+'.source.json'); source.write_bytes(raw)
    mapped = write(tmp_path/(name+'.import.json'), spec)
    store, ref = ModelStore.import_legacy(source, mapped, tmp_path/name)
    return store, ref


def proposal(ref, *, ident='change', rev='variant', target='left', prop='charge_C',
             old=-1e-9, value=-2e-9, role='source', category='component_property'):
    return {'proposal_version': 1, 'proposal_id': ident, 'parent': ref, 'revision_id': rev,
            'category': category, 'target_id': target, 'expected_role': role, 'property': prop,
            'expected_value': old, 'value': value, 'scenario_intent': 'teacher_hypothesis',
            'provenance': {'origin': 'illustrative_choice', 'reason': 'Teacher hypothesis', 'evidence': 'Explicit classroom scenario'}}


def revise(tmp_path, store, p):
    return store.revise(write(tmp_path/(p['proposal_id']+'.proposal.json'), p))


def configs(ref, *, mode='trajectory'):
    inv = {'investigation_version': 1, 'id': 'probe-motion', 'model_id': ref['model_id'],
           'observations': [{'id': 'E', 'type': 'field', 'position_m': [.3, .2, .1]},
                            {'id': 'V', 'type': 'potential', 'position_m': [.3, .2, .1]}]}
    analysis = {'analysis_version': 1, 'id': 'one-second', 'mode': mode}
    if mode == 'trajectory':
        inv['observations'] += [{'id': 'r', 'type': 'trajectory_sample', 'particle_id': 'probe', 'quantity': 'position', 'sample_index': 10}]
        analysis.update(duration_s=1., samples=21, checks={'position_atol_m': 1e-7, 'velocity_atol_m_s': 1e-7,
                         'rtol': 1e-8, 'max_normalized_energy_drift': 1e-7})
    view = {'presentation_version': 1, 'id': 'view', 'bounds_m': [-3, 3, -3, 3, -3, 3]}
    return inv, analysis, view


def execute(tmp_path, store, ref, *, mode='trajectory', change=None, name='run'):
    inv, analysis, view = configs(ref, mode=mode)
    if change: change(inv, analysis, view)
    paths = [write(tmp_path/(name+'.'+k+'.json'), v) for k, v in zip(('ref','inv','analysis','view'),(ref,inv,analysis,view))]
    output = tmp_path/name
    summary = runs.execute(store.path, *paths, output, run_id=name)
    return summary, output


def test_id01_identical_sources_remain_distinct(tmp_path):
    scene = base_scene(); scene['sources'][1] = deepcopy(scene['sources'][0])
    store, ref = imported(tmp_path,scene); root,_=store.read(ref)
    assert root['source_order']==['left','right'] and len(root['entities'])==3
    d=revise(tmp_path,store,proposal(ref)); assert d['status']=='accepted'
    variant,_=store.read(d['reference'])
    assert variant['entities']['right']['properties']['charge_C']==-1e-9


def test_id02_reordered_presentation_preserves_named_edit_and_mapping(tmp_path):
    store,ref=imported(tmp_path);d=revise(tmp_path,store,proposal(ref));v,_=store.read(d['reference'])
    inv,a,p=configs(ref);p['entity_order']=['probe','right','left']
    packet,mapping=runs.lower(v,inv,a,p)
    assert mapping['sources']=={'left':0,'right':1}
    assert packet['scene']['sources'][0]['charge_C']==-2e-9


@pytest.mark.parametrize('target,role', [('absent','source'),('probe','source'),('left','particle')])
def test_id03_wrong_role_or_missing_id(tmp_path,target,role):
    s,r=imported(tmp_path); d=revise(tmp_path,s,proposal(r,target=target,role=role))
    assert d['status']=='rejected'


def test_id03_duplicate_ids_are_rejected_at_import(tmp_path):
    with pytest.raises(RevisionError,match='duplicate'):
        imported(tmp_path,mutate=lambda x:x.update(source_ids=['left','left']))


def test_id04_reordered_source_bytes_cannot_reuse_assignment(tmp_path):
    raw=encode(base_scene());spec=assignment(raw);scene=base_scene();scene['sources'].reverse()
    source=write(tmp_path/'source.json',scene);mapped=write(tmp_path/'ids.json',spec)
    with pytest.raises(RevisionError,match='original source bytes'):
        ModelStore.import_legacy(source,mapped,tmp_path/'store')
    assert not (tmp_path/'store').exists()


def test_rev01_siblings_and_rev04_revert_preserve_lineage(tmp_path):
    s,r=imported(tmp_path);original=s.read(r)[1]
    a=revise(tmp_path,s,proposal(r,ident='a',rev='a'))
    b=revise(tmp_path,s,proposal(r,ident='b',rev='b',value=-3e-9))
    c=revise(tmp_path,s,proposal(a['reference'],ident='back',rev='back',old=-2e-9,value=-1e-9))
    assert all(x['status']=='accepted' for x in (a,b,c))
    assert s.read(a['reference'])[0]['parent']==s.read(b['reference'])[0]['parent']==r
    assert s.read(c['reference'])[0]['parent']==a['reference']
    assert s.read(r)[1]==original


def test_rev02_stale_hash_even_when_scalar_matches(tmp_path):
    s,r=imported(tmp_path);p=proposal(r);p['parent']['sha256']='0'*64
    assert revise(tmp_path,s,p)['code']=='stale_parent'


def test_rev03_duplicate_revision_and_output_preservation(tmp_path):
    s,r=imported(tmp_path); a=revise(tmp_path,s,proposal(r));snapshot=s.read(a['reference'])[1]
    b=revise(tmp_path,s,proposal(r,ident='different',value=-3e-9))
    assert b['code']=='identity_conflict' and s.read(a['reference'])[1]==snapshot
    _,out=execute(tmp_path,s,r)
    with pytest.raises(FileExistsError):execute(tmp_path,s,r)
    assert runs.inspect_run(out)[2]['execution_complete']


@pytest.mark.parametrize('prop,old,new,category,target,role', [
    ('charge_C',-1e-9,0.,'component_property','left','source'),
    ('radius_m',2.,2.5,'component_property','left','source'),
    ('center_m',[-.2,0,0],[-.4,.1,.2],'component_property','left','source'),
    ('mass_kg',1e-6,2e-6,'component_property','probe','particle'),
    ('charge_C',1e-6,-1e-6,'component_property','probe','particle'),
    ('velocity_m_s',[0,.1,0],[.1,.2,.3],'initial_condition','probe','particle'),
    ('position_m',[.3,.2,.1],[.5,.1,0],'initial_condition','probe','particle')])
def test_edit01_edit02_single_typed_property(tmp_path,prop,old,new,category,target,role):
    s,r=imported(tmp_path);root=s.read(r)[0]
    d=revise(tmp_path,s,proposal(r,prop=prop,old=old,value=new,category=category,target=target,role=role))
    assert d['status']=='accepted'
    v=s.read(d['reference'])[0]
    v['entities'][target]['properties'][prop]=old
    assert {k:x['properties'] for k,x in v['entities'].items()}=={k:x['properties'] for k,x in root['entities'].items()}
    assert s.read(d['reference'])[0]['interpretation']['scenario_intent']=='teacher_hypothesis'


def test_edit03_uniform_input_is_a_new_constant_scenario(tmp_path):
    scene=base_scene();scene['sources']=[{'type':'uniform','field_N_C':[0,1,0]}]
    s,r=imported(tmp_path,scene,mutate=lambda x:x.update(source_ids=['background']))
    d=revise(tmp_path,s,proposal(r,target='background',prop='field_N_C',old=[0,1,0],value=[1,2,3],category='external_input'))
    assert d['status']=='accepted'
    v=s.read(d['reference'])[0]; inv,a,p=configs(r)
    assert runs.lower(v,inv,a,p)[0]['scene']['sources'][0]['field_N_C']==[1,2,3]


@pytest.mark.parametrize('prop,value,category', [('radius_m',0,'component_property'),('charge_C',True,'component_property'),
    ('center_m',[1,2],'component_property'),('center_m',[True,0,0],'component_property'),
    ('type','conducting_sphere','structural_change'),('origin_m',[1,0,0],'gauge_change'),
    ('radius_m',3,'keep_density'),('grounded',True,'boundary_condition'),
    ('field_N_C','sin(t)','waveform'),('rtol',1e-8,'numerical_guess')])
def test_edit04_05_06_invalid_or_unsupported_retained(tmp_path,prop,value,category):
    s,r=imported(tmp_path);raw=s.read(r)[1];root=s.read(r)[0]
    old=root['entities']['left']['properties'].get(prop)
    d=revise(tmp_path,s,proposal(r,prop=prop,old=old,value=value,category=category))
    assert d['status']=='rejected' and s.read(r)[1]==raw
    assert len(list((s.path/'proposals').glob('*/decision.json')))==1


@pytest.mark.parametrize('target,prop,old,new', [('left','mass_kg',1e10,-1),('probe','mass_kg',1,0),('probe','charge_C',0.,1)])
def test_gravity_validity_and_ineffective_charge_edits(tmp_path,target,prop,old,new):
    scene=base_scene();scene['kind']='gravity'
    for x in scene['sources']:x['mass_kg']=1e10;x.pop('charge_C')
    scene['particles'][0]['mass_kg']=1;scene['particles'][0].pop('charge_C')
    s,r=imported(tmp_path,scene)
    d=revise(tmp_path,s,proposal(r,target=target,role='source' if target=='left' else 'particle',prop=prop,old=old,value=new))
    assert d['status']=='rejected'


def test_noop_and_boolean_old_values(tmp_path):
    s,r=imported(tmp_path)
    assert revise(tmp_path,s,proposal(r,value=-1e-9))['status']=='no_op'
    p=proposal(r,ident='bool',target='probe',role='particle',prop='mass_kg',old=True,value=2)
    assert revise(tmp_path,s,p)['code']=='old_value_mismatch'


def test_query01_02_new_investigation_and_analysis_not_physical_revision(tmp_path):
    s,r=imported(tmp_path);raw=s.read(r)[1]
    a,pa=execute(tmp_path,s,r,mode='static',name='static')
    b,pb=execute(tmp_path,s,r,name='motion')
    c,pc=execute(tmp_path,s,r,change=lambda i,a,p:a.update(id='shorter',duration_s=.5),name='shorter')
    assert all(x['execution_complete'] for x in (a,b,c))
    assert s.read(r)[1]==raw and len(list((s.path/'revisions').iterdir()))==1
    assert runs.inspect_run(pa)[0]['reference']==runs.inspect_run(pc)[0]['reference']==r
    assert runs.compare_runs(pb,pc)['measurements'][2]['comparison']=='different_sample_times'


def test_query03_world_probe_remains_fixed(tmp_path):
    s,r=imported(tmp_path)
    d=revise(tmp_path,s,proposal(r,prop='center_m',old=[-.2,0,0],value=[-.8,0,0]))
    i,a,p=configs(r);root=s.read(r)[0];v=s.read(d['reference'])[0]
    assert runs.lower(root,i,a,p)[0]['observations']==runs.lower(v,i,a,p)[0]['observations']


def test_qual01_valid_baseline_singular_revised_launch(tmp_path):
    scene=base_scene();scene['sources'][0]={'type':'point','charge_C':1e-12,'center_m':[10,0,0]}
    s,r=imported(tmp_path,scene)
    d=revise(tmp_path,s,proposal(r,target='probe',role='particle',category='initial_condition',prop='position_m',old=[.3,.2,.1],value=[10,0,0]))
    assert d['status']=='accepted' # construction validity != trajectory admissibility
    baseline,_=execute(tmp_path,s,r,name='good')
    revised,out=execute(tmp_path,s,d['reference'],name='singular')
    assert baseline['execution_complete'] and not revised['execution_complete']
    assert revised['request_statuses']['E']=='ok' and revised['request_statuses']['r']=='domain_error'
    assert not revised['render_ready']


def turning_request():
    return {'id':'turn','type':'trajectory_event','particle_id':'probe',
            'condition':{'type':'radial_turning','center_m':[0,0,0],'extremum':'minimum'},
            'occurrence':'first','max_step_s':.01,'min_distance_m':1e-7,'min_radial_acceleration_m_s2':1e-7,
            'accuracy':{'time_atol_s':1e-6,'position_atol_m':1e-6,'velocity_atol_m_s':1e-6,'radial_speed_atol_m_s':1e-7,'rtol':1e-7}}


def test_qual02_rest_request_does_not_change_launch(tmp_path):
    scene=base_scene();scene['particles'][0]['velocity_m_s']=[0,0,0]
    s,r=imported(tmp_path,scene)
    def alter(i,a,p):i['observations']=[i['observations'][0],turning_request()]
    report,out=execute(tmp_path,s,r,change=alter)
    assert report['request_statuses']['E']=='ok'
    assert report['request_statuses']['turn']=='initial_condition_error'
    assert runs.inspect_run(out)[1]['entities']['probe']['properties']['velocity_m_s']==[0,0,0]


def test_qual03_static_support_is_not_motion_support(tmp_path):
    scene=base_scene();scene['sources'][0]['type']='shell'
    s,r=imported(tmp_path,scene)
    report,_=execute(tmp_path,s,r)
    assert report['request_statuses']['E']=='ok' and report['request_statuses']['r']=='unsupported_trajectory'
    assert not report['execution_complete']


def computed_receipt():
    return {'computation_id':'launch-design','method':'Explicit illustrative choice with recorded check', 'unit':'m/s',
            'inputs':[{'target_id':'left','property':'charge_C','value':-1e-9}],
            'output':{'target_id':'probe','property':'velocity_m_s','value':[0,.1,0]},
            'check':{'passed':True,'method':'fixture receipt for dependency invalidation, not a physical proof', 'evidence':'test-only evidence'}}


def test_qual04_changed_dependency_blocks_affected_analysis_only(tmp_path):
    def spec(x):
        x['computed_inputs']=[{'target_id':'probe','property':'velocity_m_s',
            'provenance':{'origin':'computed_result','reason':'Dependency test','evidence':'Recorded calculation'},'receipt':computed_receipt()}]
    s,r=imported(tmp_path,mutate=spec)
    d=revise(tmp_path,s,proposal(r));v,_=s.read(d['reference'])
    assert v['stale_dependencies']==[{'target_id':'probe','property':'velocity_m_s'}]
    report,_=execute(tmp_path,s,d['reference'],name='motion')
    static,_=execute(tmp_path,s,d['reference'],mode='static',name='field')
    assert report['status']=='rejected' and report['code']=='stale_computation'
    assert static['execution_complete']


@pytest.mark.parametrize('affects,mode,complete', [('appearance','static',True),('trajectory','static',True),('trajectory','trajectory',False),('all','static',False)])
def test_qual05_unknowns_do_not_invent_values_or_require_appearance(tmp_path,affects,mode,complete):
    s,r=imported(tmp_path,mutate=lambda x:x['interpretation'].update(unresolved=[{'description':'Unspecified fact','affects':affects}]))
    report,_=execute(tmp_path,s,r,mode=mode)
    assert report['execution_complete']==complete


def test_qual06_fidelity_not_automatically_certified(tmp_path):
    s,r=imported(tmp_path)
    report,_=execute(tmp_path,s,r,mode='static')
    assert 'not automatically' in report['evaluation']['interpretation_fidelity']
    def decl(x):x['interpretation']['requirements'].append('conductor_polarization')
    s2,r2=imported(tmp_path,mutate=decl,name='conductor')
    report,_=execute(tmp_path,s2,r2,mode='static',name='blocked')
    assert report['code']=='unsupported_physics'


def test_run01_saved_root_after_revision_and_run02_misattachment(tmp_path):
    s,r=imported(tmp_path);_,out=execute(tmp_path,s,r,name='root-run')
    d=revise(tmp_path,s,proposal(r));execute(tmp_path,s,d['reference'],name='variant-run')
    assert runs.inspect_run(out,expected_reference=r)[0]['reference']==r
    with pytest.raises(RevisionError,match='differs'):runs.inspect_run(out,expected_reference=d['reference'])
    # Alter the bytes of a result without updating the binding; same shapes are insufficient.
    p=out/'native/trajectories.npz';p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(RevisionError,match='inventory'):runs.inspect_run(out)


def test_run02_whole_native_directory_swap_still_rejected(tmp_path):
    import shutil
    s,r=imported(tmp_path);_,out=execute(tmp_path,s,r,name='a')
    d=revise(tmp_path,s,proposal(r));_,other=execute(tmp_path,s,d['reference'],name='b')
    shutil.rmtree(out/'native');shutil.copytree(other/'native',out/'native')
    # Even a regenerated outer transfer manifest cannot disguise the packet/revision mismatch.
    (out/'integrity.json').write_bytes(encode({'files':runs._inventory(out)}))
    with pytest.raises(RevisionError,match='another revision'):runs.inspect_run(out)


def test_initial_condition_variants_match_independent_harmonic_solution(tmp_path):
    s,r=imported(tmp_path)
    proposals=[proposal(r),proposal(r,ident='launch',rev='launch',category='initial_condition',target='probe',role='particle',prop='velocity_m_s',old=[0,.1,0],value=[.1,.2,.15])]
    from scipy.constants import epsilon_0
    for ix,p in enumerate(proposals):
        d=revise(tmp_path,s,p);report,out=execute(tmp_path,s,d['reference'],name='run'+str(ix))
        assert report['execution_complete']
        scene,(t,)=runs.study.load_recorded(out/'native')
        w=np.array([-x.strength/(4*np.pi*epsilon_0*x.radius**3) for x in scene.model.sources])
        omega=np.sqrt(w.sum());equilibrium=(w[:,None]*np.array([x.center for x in scene.model.sources])).sum(axis=0)/w.sum()
        p0=scene.particles[0];time=t.time_s[:,None]
        expected=equilibrium+(np.array(p0.position_m)-equilibrium)*np.cos(omega*time)+np.array(p0.velocity_m_s)/omega*np.sin(omega*time)
        np.testing.assert_allclose(t.position_m,expected,atol=1e-8,rtol=1e-8)


def test_cmp01_events_or_no_detection_not_same_time(tmp_path):
    s,r=imported(tmp_path)
    def altered(i,a,p):
        i['observations']=[{'id':'cross','type':'trajectory_event','particle_id':'probe',
             'condition':{'type':'plane','point_m':[100,0,0],'normal':[1,0,0],'direction':'either'},
             'occurrence':'first','max_step_s':.01,'min_normal_speed_m_s':1e-7,
             'accuracy':{'time_atol_s':1e-6,'position_atol_m':1e-6,'velocity_atol_m_s':1e-6,'rtol':1e-7}}]
    _,left=execute(tmp_path,s,r,change=altered,name='left')
    d=revise(tmp_path,s,proposal(r));_,right=execute(tmp_path,s,d['reference'],change=altered,name='right')
    comparison=runs.compare_runs(left,right)
    assert comparison['measurements'][0]['comparison']=='not_available'


def test_cmp02_sweep_not_implemented_rejected_not_silently_iterated(tmp_path):
    s,r=imported(tmp_path)
    p=proposal(r,category='parameter_sweep',value=[-1e-9,-2e-9])
    assert revise(tmp_path,s,p)['code']=='unsupported_change'


def test_cli_import_reference_and_static_run(tmp_path,capsys):
    source=write(tmp_path/'source.json',base_scene());spec=write(tmp_path/'import.json',assignment(source.read_bytes()))
    assert runs.main(['import',str(source),'--assignment',str(spec),'--store',str(tmp_path/'store')])==0
    root=json.loads(capsys.readouterr().out)
    assert runs.main(['reference','root','--store',str(tmp_path/'store')])==0
    assert json.loads(capsys.readouterr().out)==root


def test_static_run_never_integrates_and_analysis_is_not_model_edit(tmp_path,monkeypatch):
    s,r=imported(tmp_path)
    import emfeeld.trajectory_samples as t
    monkeypatch.setattr(t,'integrate',lambda *a,**k:pytest.fail('static query integrated'))
    assert execute(tmp_path,s,r,mode='static')[0]['execution_complete']
    assert revise(tmp_path,s,proposal(r,category='initial_condition',prop='max_step_s',old=0,value=.1))['code']=='unsupported_change'


def test_computation_receipts_require_correct_units(tmp_path):
    def corrupt(x):
        receipt=computed_receipt();receipt['unit']='kg'
        x['computed_inputs']=[{'target_id':'probe','property':'velocity_m_s',
            'provenance':{'origin':'computed_result','reason':'Test','evidence':'Test'},'receipt':receipt}]
    with pytest.raises(RevisionError,match='unit'):imported(tmp_path,mutate=corrupt)


def test_failed_reference_is_unfulfilled_not_successful_request(tmp_path):
    s,r=imported(tmp_path)
    def altered(i,a,p):i['observations'][0]['expectation']={'value':[999,999,999],'atol':0,'rtol':0}
    report,out=execute(tmp_path,s,r,mode='static',change=altered)
    assert report['unfulfilled_requests']['E']=='reference_mismatch'
    assert not report['execution_complete'] and report['request_statuses']['V']=='ok'


def test_unexpected_backend_error_is_not_relabelled_unsupported(tmp_path,monkeypatch):
    s,r=imported(tmp_path)
    def broken(*a,**k):raise ValueError('injected programming defect')
    monkeypatch.setattr(runs.study,'_capture',broken)
    with pytest.raises(ValueError,match='programming defect'):execute(tmp_path,s,r)
    assert decode((tmp_path/'run/run.json').read_bytes())['status']=='pending'
    assert not (tmp_path/'run/integrity.json').exists()


@pytest.mark.parametrize('ids', [['CON','aux'],['Sun','sun']])
def test_physical_ids_are_independent_of_windows_filename_rules(tmp_path,ids):
    s,r=imported(tmp_path,mutate=lambda x:x.update(source_ids=ids))
    assert s.read(r)[0]['source_order']==ids
    p=proposal(r,target=ids[0]);d=revise(tmp_path,s,p)
    assert d['status']=='accepted'


@pytest.mark.parametrize('value', [True, [], 'latest', None])
def test_no_implicit_or_malformed_parent_reference(tmp_path,value):
    s,r=imported(tmp_path);p=proposal(r);p['parent']=value
    assert revise(tmp_path,s,p)['status']=='rejected'


def test_missing_required_numeric_input_is_not_silently_filled(tmp_path):
    scene=base_scene();del scene['sources'][0]['radius_m']
    source=write(tmp_path/'incomplete.json',scene);raw=source.read_bytes()
    spec=write(tmp_path/'ids.json',assignment(raw))
    with pytest.raises(ValueError):ModelStore.import_legacy(source,spec,tmp_path/'store')
    assert source.read_bytes()==raw and not (tmp_path/'store').exists()


def test_static_particle_free_model_captures_no_dynamics(tmp_path,monkeypatch):
    scene=base_scene();scene['particles']=[]
    s,r=imported(tmp_path,scene,mutate=lambda x:x.update(particle_ids=[]))
    import emfeeld.trajectory_samples as t
    monkeypatch.setattr(t,'integrate',lambda *a,**k:pytest.fail('static field integrated'))
    report,out=execute(tmp_path,s,r,mode='static')
    assert report['execution_complete'] and report['render_ready']
    assert runs.study.load_recorded(out/'native')[1]==()


@pytest.mark.parametrize('kind', ['electric','gravity'])
@pytest.mark.parametrize('typ,key,props,old,new', [
    ('line','direction',{'reference_radius_m':1.},[0,0,1],[0,1,0]),
    ('plane','normal',{},[0,0,1],[1,0,0])])
def test_direction_and_normal_edits_use_existing_domain_validators(tmp_path,kind,typ,key,props,old,new):
    scene=base_scene();scene['kind']=kind;scene['particles']=[]
    strength=('charge_per_m_C_m' if kind=='electric' else 'mass_per_m_kg_m') if typ=='line' else ('charge_per_m2_C_m2' if kind=='electric' else 'mass_per_m2_kg_m2')
    scene['sources']=[{'type':typ,strength:1e-9 if kind=='electric' else 1e10,**props}]
    s,r=imported(tmp_path,scene,mutate=lambda x:x.update(source_ids=['source'],particle_ids=[]))
    d=revise(tmp_path,s,proposal(r,target='source',prop=key,old=old,value=new))
    assert d['status']=='accepted'
    report,_=execute(tmp_path,s,d['reference'],mode='static')
    assert report['execution_complete']


def test_cmp01_distinct_event_times_are_not_subtracted(tmp_path):
    scene=base_scene();scene['sources']=[{'type':'uniform','field_N_C':[1,0,0],'origin_m':[-1,0,0]}]
    scene['particles'][0].update(position_m=[0,0,0],velocity_m_s=[0,0,0])
    s,r=imported(tmp_path,scene,mutate=lambda x:x.update(source_ids=['background']))
    def events(i,a,p):
        a['duration_s']=2.
        i['observations']=[{'id':'cross','type':'trajectory_event','particle_id':'probe',
             'condition':{'type':'plane','point_m':[1,0,0],'normal':[1,0,0],'direction':'positive'},
             'occurrence':'first','max_step_s':.01,'min_normal_speed_m_s':1e-7,
             'accuracy':{'time_atol_s':1e-6,'position_atol_m':1e-6,'velocity_atol_m_s':1e-6,'rtol':1e-7}}]
    _,a=execute(tmp_path,s,r,change=events,name='event-a')
    d=revise(tmp_path,s,proposal(r,target='background',prop='field_N_C',old=[1,0,0],value=[2,0,0],category='external_input'))
    _,b=execute(tmp_path,s,d['reference'],change=events,name='event-b')
    row=runs.compare_runs(a,b)['measurements'][0]
    assert row['comparison']=='separate_event_states_not_equal_times'
    assert row['baseline']['time_s']==pytest.approx(np.sqrt(2),abs=1e-7)
    assert row['variant']['time_s']==pytest.approx(1,abs=1e-7)
