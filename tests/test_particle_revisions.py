"""Additive particle structural lifecycle, independent probes and refusal tests."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from emfeeld import model_cli, model_runs
from emfeeld.model_revisions import ModelStore, encode, sha256, RevisionError
from test_model_revisions import (imported, write, revise, execute, configs,
                                  base_scene, proposal as property_proposal)
from test_model_cli import files


_DEFAULT_PARTICLE = object()

def addition(ref, *, ident='add-body', target='probe2', particle=_DEFAULT_PARTICLE):
    return {'proposal_version':2, 'proposal_id':ident, 'revision_id':ident,
            'parent':deepcopy(ref),'category':'structural_change','operation':'add_particle',
            'target_id':target,'expected_role':'particle',
            'scenario_intent':'teacher_hypothesis',
            'provenance':{'origin':'illustrative_choice','reason':'Test independent physical body',
                          'evidence':'Frozen particle V1 test, not original given'},
            'particle':particle if particle is not _DEFAULT_PARTICLE else {
                'mass_kg':2e-6,'charge_C':3e-7,'position_m':[.6,-.2,.2],
                'velocity_m_s':[.04,-.1,.15]}}


def removal(store, ref, *, ident='remove-body', target='probe'):
    p=addition(ref,ident=ident,target=target)
    p['operation']='remove_particle';p.pop('particle')
    p['expected_particle']=deepcopy(store.read(ref)[0]['entities'][target]['properties'])
    return p


def _originals_unchanged(folder, original):
    for name,raw in original.items():
        assert (folder/name).read_bytes()==raw, name


def test_add_particle_preserves_sources_older_parties_and_baseline(tmp_path):
    store,root=imported(tmp_path)
    initial=store.read(root)[0];snapshot=files(store.path)
    report,baseline=execute(tmp_path,store,root,name='baseline')
    oldrun=files(baseline)
    p=addition(root);d=revise(tmp_path,store,p)
    assert d['status']=='accepted' and d['numerical_work']=='not_run'
    new=store.read(d['reference'])[0]
    assert new['parent']==root and new['operation']==p
    assert new['source_order']==initial['source_order']
    assert new['particle_order']==['probe','probe2']
    assert new['entities']['probe']==initial['entities']['probe']
    assert all(new['entities'][s]==initial['entities'][s] for s in initial['source_order'])
    assert new['entities']['probe2']['role']=='particle'
    assert new['entities']['probe2']['properties']==p['particle']
    assert all(v['origin']=='illustrative_choice' for v in new['entities']['probe2']['provenance'].values())
    _originals_unchanged(store.path,snapshot)
    assert files(baseline)==oldrun and report['execution_complete']
    run,run_dir=execute(tmp_path,store,d['reference'],name='recomputed')
    assert run['execution_complete']
    oldmap=model_runs.inspect_run(baseline)[3]
    newmap=model_runs.inspect_run(run_dir)[3]
    assert oldmap['results'][0]['value']==newmap['results'][0]['value']  # field independent
    mapping=json.loads((run_dir/'mapping.json').read_text())
    assert mapping['particles']=={'probe':0,'probe2':1}
    with np.load(baseline/'native/trajectories.npz') as before, np.load(run_dir/'native/trajectories.npz') as after:
        for suffix in ('position_m','velocity_m_s'):
            np.testing.assert_allclose(before[f'p0_{suffix}'],after[f'p0_{suffix}'],atol=1e-12,rtol=1e-12)
        assert after['p1_position_m'].shape==(21,3)
    assert files(baseline)==oldrun


def test_removing_one_particle_reindexes_other_by_named_identity(tmp_path):
    scene=base_scene();second={'mass_kg':2e-6,'charge_C':-3e-7,
        'position_m':[1.,-.3,.1], 'velocity_m_s':[.02,.1,-.04]}
    scene['particles'].append(second)
    def assign(spec):spec['particle_ids']=['probe','other']
    store,root=imported(tmp_path,scene,mutate=assign)
    base_records=files(store.path)
    def two(inv,ana,pres):
        inv['observations'] += [{'id':'other_pos','type':'trajectory_sample',
                                 'particle_id':'other','quantity':'position','sample_index':10}]
        pres['entity_order']=['left','right','probe','other']
    bsum,baseline=execute(tmp_path,store,root,name='baseline',change=two)
    assert bsum['execution_complete']
    original_run=files(baseline)
    d=revise(tmp_path,store,removal(store,root,target='probe'))
    assert d['status']=='accepted'
    child=store.read(d['reference'])[0]
    assert child['particle_order']==['other']
    assert child['entities']['other']==store.read(root)[0]['entities']['other']
    assert child['source_order']==['left','right']
    bad,blocked=execute(tmp_path,store,d['reference'],name='blocked',change=two)
    assert bad['status']=='rejected' and not bad['execution_complete']
    assert 'display ordering' in bad['reason']
    def refers_deleted(inv,ana,pres):
        pres['entity_order']=['left','right','other']
        inv['observations'].append({'id':'deleted','type':'trajectory_sample','particle_id':'probe',
                                    'quantity':'position','sample_index':10})
    bad2,_=execute(tmp_path,store,d['reference'],name='missing-id',change=refers_deleted)
    assert bad2['status']=='rejected' and bad2['code']=='wrong_role'
    def valid(inv,ana,pres):
        pres['entity_order']=['left','right','other']
        inv['observations']=[{'id':'E','type':'field','position_m':[.3,.2,.1]},
              {'id':'V','type':'potential','position_m':[.3,.2,.1]},
              {'id':'other_pos','type':'trajectory_sample','particle_id':'other',
               'quantity':'position','sample_index':10}]
    good,recomputed=execute(tmp_path,store,d['reference'],name='valid',change=valid)
    assert good['execution_complete']
    assert json.loads((recomputed/'mapping.json').read_text())['particles']=={'other':0}
    with np.load(baseline/'native/trajectories.npz') as old, np.load(recomputed/'native/trajectories.npz') as new:
        for suffix in ('position_m','velocity_m_s','kinetic_J','potential_J'):
            np.testing.assert_allclose(old[f'p1_{suffix}'],new[f'p0_{suffix}'],atol=1e-12,rtol=1e-12)
    _originals_unchanged(store.path,base_records)
    assert files(baseline)==original_run


def test_remove_last_particle_keeps_static_sources_without_fictional_motion(tmp_path):
    store,root=imported(tmp_path)
    d=revise(tmp_path,store,removal(store,root))
    assert d['status']=='accepted'
    rev=store.read(d['reference'])[0];assert rev['particle_order']==[]
    assert set(rev['entities'])=={'left','right'}
    status,out=execute(tmp_path,store,d['reference'],mode='static',name='fields-only')
    assert status['execution_complete'] and status['mode']=='static'
    assert model_runs.inspect_run(out)[3]['results'][0]['status']=='ok'


def test_zero_gravity_charge_is_canonical_default_and_declared(tmp_path):
    scene=base_scene();scene['kind']='gravity'
    for s in scene['sources']:
        s['mass_kg']=2e9;s.pop('charge_C')
    scene['particles'][0].pop('charge_C')
    store,root=imported(tmp_path,scene)
    particle={'mass_kg':3.,'position_m':[.7,0,.5], 'velocity_m_s':[0,.03,.1]}
    p=addition(root,particle=particle)
    d=revise(tmp_path,store,p);assert d['status']=='accepted'
    props=store.read(d['reference'])[0]['entities']['probe2']
    assert props['properties']['charge_C']==0.
    assert props['provenance']['charge_C']['origin']=='source_convention'
    assert props['provenance']['mass_kg']['origin']=='illustrative_choice'
    remove=revise(tmp_path,store,removal(store,d['reference'],target='probe2'))
    assert remove['status']=='accepted'
    new=store.read(remove['reference'])[0]
    assert new['entities']==store.read(root)[0]['entities']


@pytest.mark.parametrize('bad',[
    {'mass_kg':0.,'charge_C':1e-6,'position_m':[1,0,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':-1.,'charge_C':1e-6,'position_m':[1,0,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':True,'charge_C':1e-6,'position_m':[1,0,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':1e-6,'position_m':[1,0,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':1e-6,'charge_C':True,'position_m':[1,0,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':1e-6,'charge_C':1e-6,'position_m':[1,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':1e-6,'charge_C':1e-6,'position_m':[False,0,0],'velocity_m_s':[0,0,0]},
    {'mass_kg':1e-6,'charge_C':1e-6,'position_m':[1,0,0],'velocity_m_s':[0,0,'nan']},
    {'mass_kg':1e-6,'charge_C':1e-6,'position_m':[1,0,0],'velocity_m_s':[0,0,0], 'radius_m':1.},
    [],None,
])
def test_invalid_additions_recorded_without_accepted_revision(tmp_path,bad):
    store,root=imported(tmp_path)
    old=files(store.path)
    p=addition(root,particle=bad)
    d=revise(tmp_path,store,p)
    assert d['status']=='rejected'
    assert len(list((store.path/'revisions').iterdir()))==1
    _originals_unchanged(store.path,old)
    assert (store.path/'proposals'/sha256(p['proposal_id'].encode())/'decision.json').is_file()


@pytest.mark.parametrize('bad',[-1.,1e-9,True,'1e-9'])
def test_new_gravity_particle_never_activates_electric_charge(tmp_path,bad):
    scene=base_scene();scene['kind']='gravity'
    for s in scene['sources']:s.pop('charge_C');s['mass_kg']=1e9
    scene['particles'][0].pop('charge_C')
    store,root=imported(tmp_path,scene)
    p=addition(root,particle={'mass_kg':1., 'charge_C':bad,
                              'position_m':[1.,0,0], 'velocity_m_s':[0,0,0]})
    d=revise(tmp_path,store,p)
    assert d['status']=='rejected'


@pytest.mark.parametrize('change,code',[
    ({'target_id':'probe'},'identity_conflict'),
    ({'target_id':'left'},'identity_conflict'),
    ({'expected_role':'source'},'unsupported_change'),
    ({'category':'boundary_condition'},'unsupported_change'),
    ({'operation':'replace_particle'},'unsupported_change'),
    ({'proposal_version':3},'invalid_proposal'),
])
def test_identity_role_category_invalidity(tmp_path,change,code):
    store,root=imported(tmp_path)
    p=addition(root);p.update(change)
    d=revise(tmp_path,store,p)
    assert d['status']=='rejected' and d['code']==code


def test_never_reuse_removed_or_sibling_identity(tmp_path):
    store,root=imported(tmp_path)
    add=revise(tmp_path,store,addition(root))
    removed=revise(tmp_path,store,removal(store,add['reference'],target='probe2'))
    assert removed['status']=='accepted'
    for label,ref in [('old',removed['reference']),('sibling',root)]:
        p=addition(ref,ident=label,target='probe2')
        assert revise(tmp_path,store,p)['code']=='identity_conflict'
    assert revise(tmp_path,store,addition(root,ident='other',target='distinct'))['status']=='accepted'


@pytest.mark.parametrize('change,code',[
    ({'target_id':'missing'},'unknown_target'),
    ({'target_id':'left'},'wrong_role'),
    ({'expected_particle':{}},'old_value_mismatch'),
    ({'expected_role':'source'},'unsupported_change'),
    ({'operation':'remove_source'},'invalid_proposal'),
])
def test_removal_refuses_wrong_entity_or_mismatched_snapshot(tmp_path,change,code):
    store,root=imported(tmp_path)
    p=removal(store,root);p.update(change)
    d=revise(tmp_path,store,p)
    assert d['status']=='rejected' and d['code']==code


def test_stale_parent_duplicate_revision_and_busy_history(tmp_path):
    store,root=imported(tmp_path)
    p=addition(root);p['parent']['sha256']='0'*64
    assert revise(tmp_path,store,p)['code']=='stale_parent'
    add=revise(tmp_path,store,addition(root,ident='ok'))
    p=addition(root,ident='dup');p['revision_id']='ok'
    assert revise(tmp_path,store,p)['code']=='identity_conflict'
    (store.path/'structural-write.lock').write_text('retained busy marker')
    assert revise(tmp_path,store,addition(root,ident='busy'))['code']=='store_busy'
    assert (store.path/'structural-write.lock').read_text()=='retained busy marker'
    (store.path/'structural-write.lock').unlink()
    store._directory('interrupted').mkdir()
    assert revise(tmp_path,store,addition(root,ident='incomplete'))['code']=='incomplete_history'


def test_computed_receipt_on_survivor_cannot_dangle_from_removed_particle(tmp_path):
    scene=base_scene()
    scene['particles'].append({'mass_kg':2e-6,'charge_C':1e-7,
        'position_m':[.9,0,0], 'velocity_m_s':[0,0,.1]})
    def assign(spec):
        spec['particle_ids']=['probe','dependent']
        spec['computed_inputs']=[{'target_id':'dependent','property':'velocity_m_s',
          'provenance':{'origin':'computed_result','reason':'Test receipt','evidence':'Test-only witness'},
          'receipt':{'computation_id':'dependent-launch','method':'Test-only hypothetical computed launch',
             'unit':'m/s','inputs':[{'target_id':'probe','property':'mass_kg','value':1e-6}],
             'output':{'target_id':'dependent','property':'velocity_m_s','value':[0,0,.1]},
             'check':{'passed':True,'method':'Test fixture evidence', 'evidence':'Not a physics proof'}}}]
    store,root=imported(tmp_path,scene,mutate=assign)
    old=files(store.path)
    d=revise(tmp_path,store,removal(store,root,target='probe'))
    assert d['status']=='rejected' and d['code']=='dependent_particle'
    assert 'dependent.velocity_m_s' in d['reason']
    _originals_unchanged(store.path,old)
    # Removing the dependent input itself does not make its own receipt dangle.
    ok=revise(tmp_path,store,removal(store,root,ident='remove-dependent',target='dependent'))
    assert ok['status']=='accepted'


def test_independent_body_membership_does_not_stale_unrelated_computed_launch(tmp_path):
    scene=base_scene()
    def assign(spec):
        spec['computed_inputs']=[{'target_id':'probe','property':'velocity_m_s',
            'provenance':{'origin':'computed_result','reason':'Test input','evidence':'test fixture'},
            'receipt':{'computation_id':'initial-launch','method':'illustrative fixture',
            'unit':'m/s','inputs':[{'target_id':'left','property':'charge_C','value':-1e-9}],
            'output':{'target_id':'probe','property':'velocity_m_s','value':[0,.1,0]},
            'check':{'passed':True,'method':'fixture record','evidence':'test-only'}}}]
    store,root=imported(tmp_path,scene,mutate=assign)
    d=revise(tmp_path,store,addition(root))
    assert d['status']=='accepted'
    child=store.read(d['reference'])[0]
    assert child['stale_dependencies']==[] and child['entities']['probe']==store.read(root)[0]['entities']['probe']
    report,_=execute(tmp_path,store,d['reference'],name='motion')
    assert report['execution_complete']
    gone=revise(tmp_path,store,removal(store,d['reference'],target='probe2'))
    assert gone['status']=='accepted'
    assert store.read(gone['reference'])[0]['stale_dependencies']==[]


def test_old_v1_and_source_structural_proposals_remain_compatible(tmp_path):
    store,root=imported(tmp_path)
    p=property_proposal(root,ident='property',rev='prop-variant')
    assert revise(tmp_path,store,p)['status']=='accepted'
    from test_structural_revisions import addition as add_source
    assert revise(tmp_path,store,add_source(root,ident='source',target='third-source'))['status']=='accepted'


def test_native_apply_and_explicit_presentation_correction(tmp_path):
    store,root=imported(tmp_path)
    def order(inv,ana,pres):pres['entity_order']=['left','right','probe']
    report,baseline=execute(tmp_path,store,root,name='baseline',change=order)
    before=files(baseline)
    p=write(tmp_path/'particle.json',addition(root))
    result=model_cli.apply_revision(p,store_path=store.path,using=baseline,output=tmp_path/'blocked')
    assert result['decision']['status']=='accepted' and result['status']=='incomplete'
    assert result['calculation']['status']=='rejected'
    assert 'display ordering' in result['calculation']['reason']
    # New independent descendant of the untouched original root.
    p2=write(tmp_path/'particle2.json',addition(root,ident='second',target='second-particle'))
    view=configs(root)[2];view['entity_order']=['left','right','probe','second-particle']
    pres=write(tmp_path/'revised-view.json',view)
    result=model_cli.apply_revision(p2,store_path=store.path,using=baseline,
         output=tmp_path/'success',presentation_path=pres)
    assert result['status']=='complete' and result['calculation']['execution_complete']
    assert (tmp_path/'success/inputs/presentation.json').read_bytes()==pres.read_bytes()
    assert (tmp_path/'success/inputs/investigation.json').read_bytes()==before['investigation.json']
    assert files(baseline)==before
    rootref=result['decision']['reference']
    _,child,_,report=model_runs.inspect_run(tmp_path/'success/run',expected_reference=rootref)
    assert child['particle_order']==['probe','second-particle'] and report['results'][0]['status']=='ok'


def test_real_native_cli_can_add_particle_without_special_commands(tmp_path):
    store,root=imported(tmp_path)
    report,baseline=execute(tmp_path,store,root,name='baseline')
    prop=write(tmp_path/'source-proposal.json',addition(root))
    env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
    result=subprocess.run([sys.executable,'-m','emfeeld','model','apply',str(prop),'--store',str(store.path),
         '--using',str(baseline),'--output',str(tmp_path/'cli')],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='complete'

@pytest.mark.parametrize('bad_origin',['computed_result','unknown'])
def test_particle_insertion_never_promotes_unchecked_or_unknown_inputs(tmp_path,bad_origin):
    store,root=imported(tmp_path)
    p=addition(root,ident='bad-origin');p['provenance']['origin']=bad_origin
    d=revise(tmp_path,store,p)
    assert d['status']=='rejected' and d['code'] in ('invalid_proposal','unsupported_provenance')
    assert store.reference('root')==root


def test_nonfinite_json_is_rejected_before_any_attempt(tmp_path):
    store,root=imported(tmp_path)
    before=files(store.path)
    p=addition(root)
    for bad in ('NaN','Infinity','1e999'):
        data=json.dumps(p).replace('2e-06',bad,1)
        path=tmp_path/f'bad-{bad}.json';path.write_text(data)
        if bad == '1e999':
            # JSON exponent overflow decodes as a Python float infinity.
            # It is rejected by the existing scene parser as a retained
            # proposal attempt, not accepted as a new physical revision.
            decision=store.revise(path)
            assert decision['status']=='rejected'
            assert len(list((store.path/'revisions').iterdir()))==1
        else:
            # Nonstandard JSON constants are rejected during strict decode.
            with pytest.raises(ValueError):store.revise(path)
        _originals_unchanged(store.path,before)


def test_reusing_source_id_from_removed_ancestor_is_blocked(tmp_path):
    store,root=imported(tmp_path)
    from test_structural_revisions import removal as remove_source
    # The source is removed in one descendant, but its ID remains reserved.
    d=revise(tmp_path,store,remove_source(store,root,ident='remove-source',target='right'))
    assert d['status']=='accepted'
    bad=revise(tmp_path,store,addition(d['reference'],ident='reuse-source',target='right'))
    assert bad['status']=='rejected' and bad['code']=='identity_conflict'


def test_removal_drops_only_stale_flags_owned_by_that_particle(tmp_path):
    scene=base_scene();scene['particles'].append({'mass_kg':1e-6,'charge_C':1e-6,
        'position_m':[1.,0,0], 'velocity_m_s':[0,.02,0]})
    from test_model_revisions import computed_receipt
    def assign(spec):
        spec['particle_ids']=['probe','survivor']
        spec['computed_inputs']=[{'target_id':'probe','property':'velocity_m_s',
            'provenance':{'origin':'computed_result','reason':'Test receipt','evidence':'Fixture'},
            'receipt':computed_receipt()}]
    store,root=imported(tmp_path,scene,mutate=assign)
    edit=property_proposal(root,ident='change-source',rev='changed',value=-3e-9)
    revised=revise(tmp_path,store,edit)
    assert revised['status']=='accepted'
    before=store.read(revised['reference'])[0]
    assert before['stale_dependencies']==[{'target_id':'probe','property':'velocity_m_s'}]
    removed=revise(tmp_path,store,removal(store,revised['reference'],target='probe'))
    assert removed['status']=='accepted'
    new=store.read(removed['reference'])[0]
    assert new['stale_dependencies']==[] and 'survivor' in new['entities']
    summary,_=execute(tmp_path,store,removed['reference'],mode='static',name='static-no-stale')
    assert summary['execution_complete']


def test_duplicate_and_pending_proposal_ids_are_never_silently_reused(tmp_path):
    store,root=imported(tmp_path)
    p=addition(root,ident='once')
    first=revise(tmp_path,store,p)
    assert first['status']=='accepted'
    original=files(store.path)
    with pytest.raises(FileExistsError):revise(tmp_path,store,p)
    _originals_unchanged(store.path,original)
