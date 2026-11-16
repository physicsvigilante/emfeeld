"""Sealed cross-revision observation differences and adversarial evidence guards."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from emfeeld import model_runs
from emfeeld.model_revisions import ModelStore, RevisionError, encode, decode, put, sha256
from emfeeld.scenario_comparisons import compare, inspect, main
from test_model_revisions import imported, base_scene, proposal, revise, write, configs
from test_atomic_revisions import atomic, add_particle, remove, replace


POINT = [.3,.2,.1]
END = [.9,.4,.15]


def _obs(name, index, *, with_motion=True, point=POINT, endpoints=(POINT,END), particle='probe', selection=None):
    entries = [
        {'id':'E-'+name,'type':'field','position_m':deepcopy(point)},
        {'id':'dV-'+name,'type':'potential_difference',
         'from_m':deepcopy(endpoints[0]),'to_m':deepcopy(endpoints[1])},
    ]
    if with_motion:
        entries.append({'id':'position-'+name,'type':'trajectory_sample',
                        'particle_id':particle,'quantity':'position',
                        **(selection if selection is not None else {'sample_index':index})})
        entries.append({'id':'velocity-'+name,'type':'trajectory_sample',
                        'particle_id':particle,'quantity':'velocity',
                        **(selection if selection is not None else {'sample_index':index})})
    return entries


def _create_run(tmp,store,ref,name,*,idx=10,samples=21,point=POINT,endpoints=(POINT,END),mode='trajectory',particle='probe',selection=None):
    inv,ana,view=configs(ref,mode=mode)
    inv['id']=name+'-questions'
    inv['observations']=_obs(name,idx,with_motion=mode=='trajectory',point=point,
                             endpoints=endpoints,particle=particle,selection=selection)
    ana['id']=name+'-analysis'
    if mode=='trajectory':
        ana['samples']=samples
    view['id']=name+'-view'
    paths=[write(tmp/(name+'-'+kind+'.json'),obj) for kind,obj in zip(
        ('ref','inv','ana','view'),(ref,inv,ana,view))]
    out=tmp/name
    result=model_runs.execute(store.path,*paths,out,run_id=name)
    assert result['execution_complete'], result
    model_runs.inspect_run(out,expected_reference=ref)
    return out


def _spec(left,right,pairs=None):
    if pairs is None:
        pairs=[
            {'id':'vector','type':'field_vector','left_observation_id':'E-left','right_observation_id':'E-right'},
            {'id':'magnitude','type':'field_magnitude','left_observation_id':'E-left','right_observation_id':'E-right'},
            {'id':'potential','type':'potential_difference','left_observation_id':'dV-left','right_observation_id':'dV-right'},
            {'id':'position','type':'particle_position','particle_id':'probe','left_observation_id':'position-left','right_observation_id':'position-right'},
            {'id':'velocity','type':'particle_velocity','particle_id':'probe','left_observation_id':'velocity-left','right_observation_id':'velocity-right'},
        ]
    return {'comparison_version':1,'id':'comparisons','left_run_sha256':sha256((left/'run.json').read_bytes()),
            'right_run_sha256':sha256((right/'run.json').read_bytes()),'pairs':pairs}


def _case(tmp, *, mode='trajectory',lidx=10,ridx=20,l_samples=21,r_samples=41,lp=POINT,rp=POINT,lends=(POINT,END),rends=(POINT,END),l_selection=None,r_selection=None):
    store,ref=imported(tmp)
    d=revise(tmp,store,proposal(ref,ident='changed',rev='changed',value=-3e-9))
    assert d['status']=='accepted'
    left=_create_run(tmp,store,ref,'left',mode=mode,idx=lidx,samples=l_samples,point=lp,endpoints=lends,selection=l_selection)
    right=_create_run(tmp,store,d['reference'],'right',mode=mode,idx=ridx,samples=r_samples,point=rp,endpoints=rends,selection=r_selection)
    return store,ref,d['reference'],left,right


def _go(tmp,left,right,pairs=None,name='result'):
    spec=_spec(left,right,pairs)
    path=write(tmp/(name+'-spec.json'),spec)
    output=tmp/name
    result=compare(path,left=left,right=right,output=output)
    assert inspect(output,left=left,right=right)==result
    return result,output,path


def _reseal(path):
    put_path=path/'integrity.json'
    # A hostile writer can regenerate this unkeyed SHA manifest. The inspector
    # must rederive semantic truth from the two original native runs.
    put_path.write_bytes(encode({'files':model_runs._inventory(path)}))


def test_full_signed_comparison_with_different_sample_index_and_observation_names(tmp_path):
    store,root,child,left,right=_case(tmp_path)
    prior={p:p.read_bytes() for folder in (left,right) for p in folder.rglob('*') if p.is_file()}
    result,out,_=_go(tmp_path,left,right)
    assert result['status']=='complete' and len(result['comparisons'])==5
    rows={r['id']:r for r in result['comparisons']}
    assert all(x['status']=='ok' and x['error_bound'] is None for x in rows.values())
    assert rows['vector']['unit']=='N/C' and len(rows['vector']['value'])==3
    assert rows['magnitude']['unit']=='N/C'
    assert rows['potential']['unit']=='V'
    assert rows['position']['context']=={'particle_id':'probe','time_s':.5,
                                             'left_sample_index':10,'right_sample_index':20}
    a=rows['position']['operands']['left']['native_result']['value']
    b=rows['position']['operands']['right']['native_result']['value']
    np.testing.assert_allclose(rows['position']['value'],np.asarray(b)-np.asarray(a),atol=0,rtol=0)
    for path,raw in prior.items(): assert path.read_bytes()==raw
    assert store.read(root)[0]['entities']['right']==store.read(child)[0]['entities']['right']
    assert main(['inspect',str(out),'--left',str(left),'--right',str(right)])==0


def test_mismatch_world_point_endpoints_and_actual_saved_time_are_unavailable(tmp_path):
    store,root,child,left,right=_case(tmp_path,rp=[.31,.2,.1],rends=(END,POINT),ridx=10)
    result,_,_=_go(tmp_path,left,right)
    assert result['status']=='partial'
    outcomes={r['id']:r for r in result['comparisons']}
    assert outcomes['vector']['code']==outcomes['magnitude']['code']=='different_world_point'
    assert outcomes['potential']['code']=='endpoints_mismatch'
    assert outcomes['position']['code']==outcomes['velocity']['code']=='different_saved_time'
    assert all(r['value'] is None for r in result['comparisons'])


def test_same_actual_time_from_nearest_selector_is_allowed(tmp_path):
    store,root,child,left,right=_case(tmp_path,r_selection={
        'time_s':.501,'time_selection':'nearest','max_time_error_s':.002})
    row,_,_=_go(tmp_path,left,right)
    assert row['status']=='complete'
    motion=[r for r in row['comparisons'] if r['type'].startswith('particle_')]
    assert all(r['context']['time_s']==.5 for r in motion)


def test_pair_unknown_operand_with_valid_comparisons_is_partial(tmp_path):
    store,root,child,left,right=_case(tmp_path)
    pairs=[_spec(left,right)['pairs'][0], {'id':'added-only','type':'particle_position',
             'particle_id':'added','left_observation_id':'missing-baseline','right_observation_id':'position-right'}]
    result,_,_=_go(tmp_path,left,right,pairs)
    assert result['status']=='partial' and result['comparisons'][0]['status']=='ok'
    assert result['comparisons'][1]['code']=='unknown_operand'
    assert result['comparisons'][1]['value'] is None


def test_old_removed_particle_reindex_is_named_not_positional(tmp_path):
    scene=base_scene();extra={'mass_kg':1e-6,'charge_C':-1e-6,
                               'position_m':[-.2,.3,.1],'velocity_m_s':[0,0,.1]}
    scene['particles'].insert(0,extra)
    def assign(spec):spec['particle_ids']=['deleted','probe']
    store,root=imported(tmp_path,scene,mutate=assign)
    rev=atomic(root,[remove(store,root,'deleted','particle'),
                    replace('left',-1e-9,-3e-9)],ident='post-delete')
    child=revise(tmp_path,store,rev)['reference']
    left=_create_run(tmp_path,store,root,'left')
    right=_create_run(tmp_path,store,child,'right',idx=20,samples=41)
    result,_,_=_go(tmp_path,left,right)
    assert result['status']=='complete'
    l=json.loads((left/'mapping.json').read_text())['particles']['probe']
    r=json.loads((right/'mapping.json').read_text())['particles']['probe']
    assert (l,r)==(1,0)
    assert result['comparisons'][-1]['context']['particle_id']=='probe'


def test_missing_physical_body_does_not_alias_other_index(tmp_path):
    store,root=imported(tmp_path)
    change=atomic(root,[add_particle('added'),replace('left',-1e-9,-3e-9)],ident='add')
    child=revise(tmp_path,store,change)['reference']
    left=_create_run(tmp_path,store,root,'left')
    right=_create_run(tmp_path,store,child,'right')
    pairs=[{'id':'phantom','type':'particle_position','particle_id':'added',
            'left_observation_id':'position-left','right_observation_id':'position-right'}]
    result,_,_=_go(tmp_path,left,right,pairs)
    assert result['comparisons'][0]['code']=='particle_identity_mismatch'


def test_comparison_reversed_sides_changes_sign_with_correct_pins(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    pair=[_spec(left,right)['pairs'][0]]
    a,_,_=_go(tmp_path,left,right,pair,name='normal')
    b,_,_=_go(tmp_path,right,left,[{'id':'vector','type':'field_vector',
       'left_observation_id':'E-right','right_observation_id':'E-left'}],name='reverse')
    np.testing.assert_array_equal(a['comparisons'][0]['value'],
                                  -np.asarray(b['comparisons'][0]['value']))


@pytest.mark.parametrize('change',[
    lambda p:p.update(comparison_version=True),
    lambda p:p.update(comparison_version=1.0),
    lambda p:p.update(extra=0),
    lambda p:p.update(pairs=[]),
    lambda p:p.update(pairs=p['pairs']*17),
    lambda p:p['pairs'][0].update(unknown='extra'),
    lambda p:p['pairs'][0].update(type='undefined'),
    lambda p:p['pairs'][0].update(particle_id='probe'),
    lambda p:p['pairs'][0].update(left_observation_id='bad/id'),
    lambda p:p['pairs'].append(deepcopy(p['pairs'][0])),
    lambda p:p.update(left_run_sha256='0'*64),
    lambda p:p.update(right_run_sha256='Z'*64),
])
def test_bad_request_has_no_output(tmp_path,change):
    store,root,child,left,right=_case(tmp_path,mode='static')
    spec=_spec(left,right,[_spec(left,right)['pairs'][0]])
    change(spec)
    doc=write(tmp_path/'bad-spec.json',spec)
    output=tmp_path/'no-output'
    with pytest.raises((ValueError,RevisionError)):
        compare(doc,left=left,right=right,output=output)
    assert not output.exists()


def test_partial_and_rejected_source_runs_fail_preflight(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    broken=tmp_path/'broken';shutil.copytree(left,broken)
    summary=json.loads((broken/'summary.json').read_text());summary['status']='partial';summary['execution_complete']=False
    (broken/'summary.json').write_bytes(encode(summary));_reseal(broken)
    spec=_spec(broken,right,[_spec(left,right)['pairs'][0]])
    doc=write(tmp_path/'partial-spec.json',spec)
    with pytest.raises(RevisionError,match='complete'):
        compare(doc,left=broken,right=right,output=tmp_path/'fail')
    assert not (tmp_path/'fail').exists()


def test_cross_model_roots_and_same_revision_are_rejected(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    other_scene=base_scene();other_scene['sources'][0]['charge_C']=-7e-9
    other,oref=imported(tmp_path,scene=other_scene,name='other')
    different=_create_run(tmp_path,other,oref,'alien',mode='static')
    doc=write(tmp_path/'wrong-root.json',_spec(left,different,[_spec(left,right)['pairs'][0]]))
    with pytest.raises(RevisionError,match='root'):
        compare(doc,left=left,right=different,output=tmp_path/'wrong-root')
    a=write(tmp_path/'same-rev.json',_spec(left,left,[_spec(left,right)['pairs'][0]]))
    with pytest.raises(RevisionError,match='different revisions'):
        compare(a,left=left,right=left,output=tmp_path/'same-rev')


def test_software_and_runtime_identity_mismatch_refused(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    tampered=tmp_path/'altered-impl';shutil.copytree(right,tampered)
    run=json.loads((tampered/'run.json').read_text());run['implementation_sha256']['model_runs.py']='1'*64
    (tampered/'run.json').write_bytes(encode(run));_reseal(tampered)
    doc=write(tmp_path/'bad-impl.json',_spec(left,tampered,[_spec(left,right)['pairs'][0]]))
    with pytest.raises(RevisionError,match='different saved implementation'):
        compare(doc,left=left,right=tampered,output=tmp_path/'impl-refused')


def test_native_nested_integrity_break_even_if_outer_inventory_resealed(tmp_path):
    store,root,child,left,right=_case(tmp_path)
    tampered=tmp_path/'tampered';shutil.copytree(left,tampered)
    path=tampered/'native/checks.json';path.write_bytes(path.read_bytes()+b' ')
    _reseal(tampered)
    doc=write(tmp_path/'nested.json',_spec(tampered,right,[_spec(left,right)['pairs'][0]]))
    with pytest.raises(RevisionError,match='nested'):
        compare(doc,left=tampered,right=right,output=tmp_path/'refuse-nested')


def test_malicious_resign_native_report_sample_contradicts_saved_npz(tmp_path):
    store,root,child,left,right=_case(tmp_path)
    fake=tmp_path/'fake';shutil.copytree(right,fake)
    path=fake/'native/result.json';data=decode(path.read_bytes())
    row=next(x for x in data['results'] if x['id']=='position-right')
    row['value'][0] += .5
    path.write_bytes(encode(data))
    nested=fake/'native/integrity.json';files=decode(nested.read_bytes());files['files']['result.json']=sha256(path.read_bytes())
    nested.write_bytes(encode(files));_reseal(fake)
    doc=write(tmp_path/'incoherent.json',_spec(left,fake,[_spec(left,right)['pairs'][3]]))
    refused=tmp_path/'refuse-fake'
    with pytest.raises(RevisionError,match='NPZ'):
        compare(doc,left=left,right=fake,output=refused)
    assert not refused.exists()  # Invalid saved native evidence fails preflight.


def test_result_resealed_inconsistent_with_sources_fails_inspection(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    row,out,_=_go(tmp_path,left,right,[_spec(left,right)['pairs'][0]])
    report=decode((out/'result.json').read_bytes());report['comparisons'][0]['value'][0]+=1
    (out/'result.json').write_bytes(encode(report));_reseal(out)
    with pytest.raises(RevisionError,match='saved results'):
        inspect(out,left=left,right=right)


def test_output_alias_and_duplicate_output_refused(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    spec=write(tmp_path/'spec.json',_spec(left,right,[_spec(left,right)['pairs'][0]]))
    with pytest.raises(ValueError,match='outside'):
        compare(spec,left=left,right=right,output=left/'within')
    with pytest.raises(FileExistsError):
        compare(spec,left=left,right=right,output=left)
    result,out,_=_go(tmp_path,left,right,[_spec(left,right)['pairs'][0]])
    with pytest.raises(FileExistsError):
        compare(spec,left=left,right=right,output=out)


def test_unrequested_observations_and_legacy_compare_unchanged(tmp_path):
    store,root,child,left,right=_case(tmp_path)
    result,_,_=_go(tmp_path,left,right,[_spec(left,right)['pairs'][0]])
    assert result['status']=='complete'
    # Previous model_runs.compare_runs deliberately remains strict and refuses
    # differently authored named observations. No monkeypatch or old code edit.
    with pytest.raises(RevisionError,match='identical|world-coordinate'):
        model_runs.compare_runs(left,right)


def test_float64_overflow_has_typed_unavailable_not_infinity(tmp_path):
    scene={'schema_version':1,'title':'Very large but finite uniform field',
           'kind':'electric','sources':[{'type':'uniform','field_N_C':[-1e308,0.,0.]}],
           'bounds_m':[-1,1,-1,1,-1,1]}
    def assign(x):x.update(source_ids=['background'],particle_ids=[])
    store,root=imported(tmp_path,scene,mutate=assign)
    rev=proposal(root,ident='opposite',rev='opposite',target='background',role='source',
        prop='field_N_C',old=[-1e308,0.,0.],value=[1e308,0.,0.],category='external_input')
    d=revise(tmp_path,store,rev)
    assert d['status']=='accepted'
    a=_create_run(tmp_path,store,root,'left',mode='static',point=[0,0,0],endpoints=([0,0,0],[0,0,0]))
    b=_create_run(tmp_path,store,d['reference'],'right',mode='static',point=[0,0,0],endpoints=([0,0,0],[0,0,0]))
    rows=[_spec(a,b)['pairs'][0],_spec(a,b)['pairs'][1]]
    result,_,_=_go(tmp_path,a,b,rows)
    assert result['status']=='partial'
    assert result['comparisons'][0]['code']=='numeric_range'
    assert result['comparisons'][0]['value'] is None
    assert result['comparisons'][1]['status']=='ok' and result['comparisons'][1]['value']==0.


def test_sixteen_distinct_pairs_are_admitted(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    pairs=[{'id':f'field-{i}','type':'field_vector',
            'left_observation_id':'E-left','right_observation_id':'E-right'} for i in range(16)]
    row,_,_=_go(tmp_path,left,right,pairs)
    assert row['status']=='complete' and len(row['comparisons'])==16


def test_duplicate_json_key_and_nonfinite_token_fail_before_publication(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    example=_spec(left,right,[_spec(left,right)['pairs'][0]])
    doc=tmp_path/'duplicate.json'
    doc.write_text(encode(example).decode().replace('"comparison_version": 1,',
                       '"comparison_version": 1, "comparison_version": 1,',1))
    with pytest.raises(ValueError,match='duplicate'):
        compare(doc,left=left,right=right,output=tmp_path/'not-created')
    doc.write_text(encode(example).decode().replace('"comparison_version": 1,',
                       '"comparison_version": NaN,',1))
    with pytest.raises(ValueError,match='nonfinite'):
        compare(doc,left=left,right=right,output=tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()


def test_forged_complete_status_rejected_by_deterministic_inspector(tmp_path):
    store,root,child,left,right=_case(tmp_path,rp=[.35,.2,.1])
    row,out,_=_go(tmp_path,left,right,[_spec(left,right)['pairs'][0]])
    assert row['status']=='partial'
    saved=decode((out/'result.json').read_bytes())
    saved['status']='complete'
    (out/'result.json').write_bytes(encode(saved));_reseal(out)
    with pytest.raises(RevisionError,match='saved results'):
        inspect(out,left=left,right=right)


def test_malformed_check_metadata_and_wrong_report_coordinates_are_hard_failures(tmp_path):
    store,root,child,left,right=_case(tmp_path,mode='static')
    for tag,edit in (
        ('check',lambda r:r.update(check=None)),
        ('coordinate',lambda r:r.update(position_m=[9,8,7]))):
        fake=tmp_path/('fake-'+tag);shutil.copytree(right,fake)
        native=fake/'native/result.json';payload=decode(native.read_bytes())
        row=next(x for x in payload['results'] if x['id']=='E-right')
        edit(row)
        native.write_bytes(encode(payload));_reseal(fake)
        req=write(tmp_path/('fake-'+tag+'.json'),_spec(left,fake,[_spec(left,right)['pairs'][0]]))
        with pytest.raises(RevisionError,match='native result identity|field result location'):
            compare(req,left=left,right=fake,output=tmp_path/('not-'+tag))

def test_comparison_cannot_be_written_inside_an_append_only_model_store(tmp_path):
    store, root, child, left, right = _case(tmp_path, mode='static')
    spec=write(tmp_path/'store-protection.json',_spec(left,right,[_spec(left,right)['pairs'][0]]))
    protected=store.path/'user-comparison'
    baseline={p.relative_to(store.path).as_posix():p.read_bytes()
              for p in store.path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='outside model stores'):
        compare(spec,left=left,right=right,output=protected)
    assert not protected.exists()
    for rel,data in baseline.items():
        assert (store.path/rel).read_bytes()==data
