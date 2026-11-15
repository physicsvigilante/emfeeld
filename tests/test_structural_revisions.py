"""Structural lifecycle/analysis admission; historical v1 tests remain unchanged."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from emfeeld import model_cli, model_runs, structural_revisions
from emfeeld.model_revisions import ModelStore, encode, sha256
from test_model_revisions import (imported, write, revise, execute, configs,
    proposal as property_proposal, computed_receipt)
from test_model_cli import files


def addition(ref, ident='add', target='extra', source=None):
    return {'proposal_version': 2, 'proposal_id': ident, 'parent': deepcopy(ref),
        'revision_id': ident, 'category': 'structural_change', 'operation': 'add_source',
        'target_id': target, 'expected_role': 'source', 'scenario_intent': 'teacher_hypothesis',
        'provenance': {'origin': 'illustrative_choice', 'reason': 'Explicit hypothetical source',
                       'evidence': 'Prospective structural revision qualification'},
        'source': source if source is not None else {'type': 'uniform', 'field_N_C': [0., 0., .1]}}


def removal(store, ref, ident='remove', target='right'):
    p = addition(ref, ident, target)
    p['operation'] = 'remove_source'; p.pop('source')
    p['expected_source'] = deepcopy(store.read(ref)[0]['entities'][target]['properties'])
    return p


def computed_store(path):
    def spec(data):
        data['computed_inputs'] = [{'target_id': 'probe', 'property': 'velocity_m_s',
            'provenance': {'origin': 'computed_result', 'reason': 'Dependency fixture',
                           'evidence': 'Recorded illustrative computation'}, 'receipt': computed_receipt()}]
    return imported(path, mutate=spec)


@pytest.mark.parametrize('operation', ['add_source', 'remove_source'])
def test_preserve_parent_unrelated_entities_and_originals(tmp_path, operation):
    store, root = imported(tmp_path); before = files(store.path); old = store.read(root)[0]
    p = addition(root) if operation == 'add_source' else removal(store, root)
    decision = revise(tmp_path, store, p)
    assert decision['status'] == 'accepted' and decision['qualification'] == 'construction_only'
    assert decision['numerical_work'] == 'not_run'
    new = store.read(decision['reference'])[0]
    assert new['parent'] == root and new['operation'] == p
    for name, raw in before.items(): assert (store.path/name).read_bytes() == raw
    for key, row in old['entities'].items():
        if key != p['target_id']: assert new['entities'][key] == row
    assert new['particle_order'] == old['particle_order']
    assert new['source_order'] == (['left', 'right', 'extra'] if operation == 'add_source' else ['left'])
    if operation == 'add_source':
        assert new['entities']['extra']['properties']['origin_m'] == [0,0,0]
        assert new['entities']['extra']['provenance']['origin_m']['origin'] == 'source_convention'
    assert not (store.path/'structural-write.lock').exists()


@pytest.mark.parametrize('target', ['left', 'right', 'probe'])
def test_existing_identity_collision(tmp_path, target):
    store, root = imported(tmp_path)
    assert revise(tmp_path, store, addition(root,target=target))['code'] == 'identity_conflict'


def test_reuse_after_removal_and_sibling_addition_is_rejected(tmp_path):
    store, root = imported(tmp_path)
    add = revise(tmp_path, store, addition(root))
    removed = revise(tmp_path, store, removal(store, add['reference'], target='extra'))
    assert removed['status'] == 'accepted'
    for name, parent in [('sibling', root), ('descendant', removed['reference'])]:
        decision = revise(tmp_path, store, addition(parent, ident=name))
        assert decision['code'] == 'identity_conflict'
    # A new explicitly distinct ID for equal geometry is not silently deduplicated.
    assert revise(tmp_path, store, addition(root,ident='new',target='other'))['status'] == 'accepted'


@pytest.mark.parametrize('source', [
    {'type':'point','charge_C':True}, {'type':'point','charge_C':'1e-9'},
    {'type':'point','mass_kg':1}, {'type':'solid_sphere','charge_C':1e-9,'radius_m':0},
    {'type':'line','charge_per_m_C_m':1e-11},
    {'type':'line','charge_per_m_C_m':1e-11,'reference_radius_m':1,'direction':[0,0,0]},
    {'type':'plane','charge_per_m2_C_m2':1e-11,'normal':[0,0]},
    {'type':'conducting_sphere','charge_C':1e-9}, {'type':'uniform','field_N_C':[1,2]},
    {'type':'point','charge_C':1e-9,'kind':'gravity'},
    {'type':'point','charge_C':1e-9,'center_m':[False,0,0]}, [], None,
])
def test_invalid_added_source_is_retained_not_published(tmp_path, source):
    store, root = imported(tmp_path); before = store.read(root)[1]
    p = addition(root); p['source'] = source
    d = revise(tmp_path, store, p)
    assert d['status'] == 'rejected' and store.read(root)[1] == before
    assert len(list((store.path/'revisions').iterdir())) == 1
    assert len(list((store.path/'proposals').glob('*/decision.json'))) == 1


@pytest.mark.parametrize('change,code', [
    ({'target_id':'missing'},'unknown_target'),
    ({'target_id':'probe'},'wrong_role'),
    ({'expected_source':{}},'old_value_mismatch'),
    ({'operation':'replace_source'},'unsupported_change'),
    ({'operation':'add_particle'},'unsupported_change'),
    ({'expected_role':'particle'},'unsupported_change'),
    ({'category':'boundary_condition'},'unsupported_change'),
])
def test_invalid_structural_operations(tmp_path, change, code):
    store, root = imported(tmp_path); p = removal(store,root); p.update(change)
    assert revise(tmp_path,store,p)['code'] == code


def test_stale_parent_duplicate_revision_and_last_source(tmp_path):
    store, root = imported(tmp_path)
    p=addition(root,ident='stale');p['parent']['sha256']='0'*64
    assert revise(tmp_path,store,p)['code']=='stale_parent'
    d=revise(tmp_path,store,removal(store,root))
    assert d['status']=='accepted'
    p=removal(store,d['reference'],ident='last',target='left')
    assert revise(tmp_path,store,p)['code']=='last_source'
    p=addition(root,ident='other');p['revision_id']='remove'
    assert revise(tmp_path,store,p)['code']=='identity_conflict'


def test_removed_source_dependencies_are_not_stripped_or_rebound(tmp_path):
    store, root = computed_store(tmp_path); original=store.read(root)[1]
    d=revise(tmp_path,store,removal(store,root,target='left'))
    assert d['code']=='dependent_source' and 'probe.velocity_m_s' in d['reason']
    assert store.read(root)[1]==original


@pytest.mark.parametrize('action', ['addition','unreferenced_removal'])
def test_structure_conservatively_invalidates_computed_inputs(tmp_path,action):
    store,root=computed_store(tmp_path);old=store.read(root)[0]
    p=addition(root) if action=='addition' else removal(store,root)
    d=revise(tmp_path,store,p);assert d['status']=='accepted'
    new=store.read(d['reference'])[0]
    assert new['entities']['probe']==old['entities']['probe']
    assert new['stale_dependencies']==[{'target_id':'probe','property':'velocity_m_s'}]
    motion,_=execute(tmp_path,store,d['reference'],name='motion')
    static,_=execute(tmp_path,store,d['reference'],mode='static',name='static')
    assert motion['code']=='stale_computation' and static['execution_complete']


@pytest.mark.parametrize('cause,code', [('busy','store_busy'),('incomplete','incomplete_history')])
def test_blocked_store_does_not_overwrite_or_bypass_history(tmp_path,cause,code):
    store,root=imported(tmp_path)
    if cause=='busy': (store.path/'structural-write.lock').write_text('retained crash evidence')
    else: store._directory('interrupted').mkdir()
    assert revise(tmp_path,store,addition(root))['code']==code
    if cause=='busy':assert (store.path/'structural-write.lock').read_text()=='retained crash evidence'


def test_publication_failure_and_duplicate_attempt_are_not_success(tmp_path,monkeypatch):
    store,root=imported(tmp_path)
    def fail(candidate):
        store._directory(candidate['revision_id']).mkdir()
        raise OSError('injected write failure')
    monkeypatch.setattr(store,'_publish',fail)
    p=write(tmp_path/'proposal.json',addition(root))
    with pytest.raises(OSError,match='injected'):store.revise(p)
    attempt=store.path/'proposals'/sha256(b'add')
    assert (attempt/'pending.json').exists() and not (attempt/'decision.json').exists()
    assert not (store.path/'structural-write.lock').exists()
    with pytest.raises(FileExistsError):store.revise(p)


def test_property_edits_still_work_after_structure(tmp_path):
    store,root=imported(tmp_path)
    d=revise(tmp_path,store,addition(root))
    p=property_proposal(d['reference'],ident='property',rev='property',target='extra',
        prop='field_N_C',old=[0,0,.1],value=[0,0,.2],category='external_input')
    child=revise(tmp_path,store,p);assert child['status']=='accepted'
    assert store.read(child['reference'])[0]['entities']['extra']['properties']['field_N_C']==[0,0,.2]


@pytest.mark.parametrize('source', [
    {'type':'shell','charge_C':1e-9,'radius_m':1},
    {'type':'plane','charge_per_m2_C_m2':1e-11},
])
def test_static_assembly_does_not_enable_unqualified_motion(tmp_path,source):
    store,root=imported(tmp_path);d=revise(tmp_path,store,addition(root,source=source))
    assert d['status']=='accepted'
    static,_=execute(tmp_path,store,d['reference'],mode='static',name='static')
    motion,_=execute(tmp_path,store,d['reference'],name='motion')
    assert static['execution_complete'] and not motion['execution_complete']
    assert motion['request_statuses']['r']=='unsupported_trajectory'


def test_singular_added_source_fails_run_not_baseline(tmp_path):
    store,root=imported(tmp_path)
    good,baseline=execute(tmp_path,store,root,name='baseline');before=files(baseline)
    d=revise(tmp_path,store,addition(root,source={'type':'point','charge_C':1e-9,'center_m':[.3,.2,.1]}))
    assert d['status']=='accepted'
    bad,_=execute(tmp_path,store,d['reference'],name='singular')
    assert good['execution_complete'] and not bad['execution_complete']
    assert bad['request_statuses']['r']=='domain_error' and files(baseline)==before


def test_apply_reuses_compatible_requests_but_never_previous_results(tmp_path):
    store,root=imported(tmp_path);_,baseline=execute(tmp_path,store,root,name='baseline')
    before=files(baseline);p=write(tmp_path/'add.json',addition(root))
    out=tmp_path/'apply'
    result=model_cli.apply_revision(p,store_path=store.path,using=baseline,output=out)
    assert result['status']=='complete' and files(baseline)==before
    run,rev,summary,native=model_runs.inspect_run(out/'run')
    assert run['reference']==result['decision']['reference'] and summary['execution_complete']
    assert (out/'run/investigation.json').read_bytes()==before['investigation.json']
    assert (out/'run/native/packet.json').read_bytes()!=before['native/packet.json']
    old=model_runs.inspect_run(baseline)[3]
    assert native['results'][0]['value'] != old['results'][0]['value']
    mapping=json.loads((out/'run/mapping.json').read_text())
    assert mapping['sources']=={'left':0,'right':1,'extra':2} and mapping['particles']=={'probe':0}


def test_explicit_presentation_override_and_retained_incompatible_attempt(tmp_path):
    store,root=imported(tmp_path)
    def ordered(inv,ana,pres):pres['entity_order']=['left','right','probe']
    _,baseline=execute(tmp_path,store,root,change=ordered,name='baseline')
    before=files(baseline)
    p=write(tmp_path/'add.json',addition(root))
    result=model_cli.apply_revision(p,store_path=store.path,using=baseline,output=tmp_path/'rejected-analysis')
    assert result['decision']['status']=='accepted' and result['status']=='incomplete'
    assert result['calculation']['status']=='rejected'
    assert 'display ordering' in result['calculation']['reason']
    _,_,presentation=configs(root);presentation['entity_order']=['probe','right','left','second']
    replacement=write(tmp_path/'presentation.json',presentation)
    p=write(tmp_path/'second.json',addition(root,ident='second',target='second'))
    result=model_cli.apply_revision(p,store_path=store.path,using=baseline,output=tmp_path/'explicit',presentation_path=replacement)
    assert result['status']=='complete' and files(baseline)==before
    binding=result['settings_from']
    assert binding['settings_sha256']['presentation.json']==sha256(before['presentation.json'])
    assert binding['explicit_overrides']['presentation.json']['sha256']==sha256(replacement.read_bytes())
    assert (tmp_path/'explicit/inputs/presentation.json').read_bytes()==replacement.read_bytes()


def test_real_cli_version2_and_presentation_flag(tmp_path):
    store,root=imported(tmp_path);_,prior=execute(tmp_path,store,root,name='prior')
    prop=write(tmp_path/'p.json',addition(root));pres=write(tmp_path/'view.json',configs(root)[2])
    env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
    result=subprocess.run([sys.executable,'-m','emfeeld','model','apply',str(prop),'--store',str(store.path),
        '--using',str(prior),'--output',str(tmp_path/'cli'),'--presentation',str(pres)],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='complete'


@pytest.mark.parametrize('kind', ['electric','gravity'])
@pytest.mark.parametrize('source_type', ['point','solid_sphere','shell','line','plane','uniform'])
def test_all_existing_source_types_use_shared_admission(tmp_path,kind,source_type):
    from test_model_revisions import base_scene
    scene=base_scene()
    if kind=='gravity':
        scene['kind']='gravity'
        for s in scene['sources']:s.pop('charge_C');s['mass_kg']=1e9
        scene['particles'][0].pop('charge_C')
    store,root=imported(tmp_path,scene)
    strength='charge_C' if kind=='electric' else 'mass_kg'
    value=1e-11 if kind=='electric' else 1e8
    source={'type':source_type, strength:value}
    if source_type in ('solid_sphere','shell'):source['radius_m']=1.
    if source_type=='line':
        source.pop(strength);source['charge_per_m_C_m' if kind=='electric' else 'mass_per_m_kg_m']=value
        source['reference_radius_m']=1.
    if source_type=='plane':
        source.pop(strength);source['charge_per_m2_C_m2' if kind=='electric' else 'mass_per_m2_kg_m2']=value
    if source_type=='uniform':source={'type':'uniform','field_N_C' if kind=='electric' else 'field_m_s2':[.1,0,0]}
    d=revise(tmp_path,store,addition(root,source=source));assert d['status']=='accepted'
    report,_=execute(tmp_path,store,d['reference'],mode='static',name='static')
    assert report['execution_complete']
    removed=revise(tmp_path,store,removal(store,d['reference'],target='extra'))
    assert removed['status']=='accepted'
    assert store.read(removed['reference'])[0]['entities']==store.read(root)[0]['entities']


@pytest.mark.parametrize('origin', ['computed_result','unknown'])
def test_addition_does_not_invent_computed_or_unknown_facts(tmp_path,origin):
    store,root=imported(tmp_path);p=addition(root);p['provenance']['origin']=origin
    assert revise(tmp_path,store,p)['status']=='rejected'


def test_nonfinite_source_rejected_before_mutation(tmp_path):
    store,root=imported(tmp_path);p=addition(root);raw=json.dumps(p).replace('0.1','NaN')
    path=tmp_path/'bad.json';path.write_text(raw)
    before=files(store.path)
    with pytest.raises(ValueError,match='nonfinite'):store.revise(path)
    assert files(store.path)==before


def test_corrupt_sibling_blocks_identity_admission(tmp_path):
    store,root=imported(tmp_path);d=revise(tmp_path,store,addition(root))
    path=store._directory(d['reference']['revision_id'])/'revision.json'
    path.write_bytes(path.read_bytes()+b' ')
    d=revise(tmp_path,store,addition(root,ident='second',target='second'))
    assert d['code']=='stale_parent'
