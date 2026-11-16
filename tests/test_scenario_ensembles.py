"""Bounded scenario ensembles: native reuse, exact parent, failures and integrity."""
from copy import deepcopy

import pytest

from emfeeld import model_runs
from emfeeld.model_revisions import RevisionError, decode, encode, sha256
from emfeeld.scenario_ensembles import run_ensemble,inspect_ensemble,validate_spec
from test_model_revisions import imported,configs,write
from test_atomic_revisions import atomic,replace


def _native_root(tmp,store,ref):
    inv,analysis,view=configs(ref,mode='static')
    inv['id']='baseline-questions'
    inv['observations']=[
        {'id':'field-parent','type':'field','position_m':[.3,.2,.1]},
        {'id':'step-parent','type':'potential_difference',
         'from_m':[.3,.2,.1],'to_m':[.7,.4,.1]},
    ]
    view['entity_order']=['left','right','probe']
    paths=[write(tmp/('root-'+k+'.json'),v) for k,v in zip(
        ('ref','investigation','analysis','presentation'),(ref,inv,analysis,view))]
    output=tmp/'source-run'
    s=model_runs.execute(store.path,*paths,output,run_id='template')
    assert s['execution_complete'],s
    return output,inv,analysis,view


def _member(parent,index,inv,analysis,view,*,bad=False):
    ident=f'variant-{index}'
    proposal=atomic(parent,[
        replace('left',-1e-9,-(index+2)*1e-9),
        replace('right',-2e-9,-(index+3)*1e-9 if not bad else 0,
                prop='charge_C' if not bad else 'nonexistent'),
    ],ident=ident)
    question=deepcopy(inv)
    question['id']=ident+'-questions'
    question['observations']=[
        {'id':ident+'-field','type':'field','position_m':[.3,.2,.1]},
        {'id':ident+'-step','type':'potential_difference',
         'from_m':[.3,.2,.1],'to_m':[.7,.4,.1]},
    ]
    ana=deepcopy(analysis);ana['id']=ident+'-analysis'
    pres=deepcopy(view);pres['id']=ident+'-presentation'
    return {'id':ident,'proposal':proposal,'investigation':question,
            'analysis':ana,'presentation':pres,
            'pairs':[
                {'id':'signed-field','type':'field_vector',
                 'left_observation_id':'field-parent',
                 'right_observation_id':ident+'-field'},
                {'id':'ordered-step','type':'potential_difference',
                 'left_observation_id':'step-parent',
                 'right_observation_id':ident+'-step'},
            ]}


def _spec(root,template,inv,analysis,view,*,bad_second=False):
    return {'ensemble_version':1,'id':'two-hypotheses',
            'parent':root,
            'source_run_sha256':sha256((template/'run.json').read_bytes()),
            'members':[
                _member(root,1,inv,analysis,view),
                _member(root,2,inv,analysis,view,bad=bad_second),
            ]}


def _run(tmp,*,bad_second=False):
    store,root=imported(tmp)
    template,inv,analysis,view=_native_root(tmp,store,root)
    spec=_spec(root,template,inv,analysis,view,bad_second=bad_second)
    path=write(tmp/'ensemble.json',spec)
    old_root=store.read(root)[1]
    old_template={p.relative_to(template).as_posix():p.read_bytes()
                  for p in template.rglob('*') if p.is_file()}
    output=tmp/'ensemble-output'
    report=run_ensemble(path,store_path=store.path,using=template,output=output)
    assert inspect_ensemble(output,store_path=store.path,using=template)==report
    assert store.read(root)[1]==old_root
    for name,data in old_template.items():
        assert (template/name).read_bytes()==data
    return store,root,template,report,output,spec


def _reseal(out):
    from emfeeld.scenario_ensembles import _inventory
    (out/'integrity.json').write_bytes(encode({'files':_inventory(out)}))


def test_two_atomic_sibling_hypotheses_recompute_sealed_native_baseline(tmp_path):
    store,root,template,report,output,spec=_run(tmp_path)
    assert report['status']=='complete'
    assert report['baseline']['execution_complete']
    assert len(report['members'])==2
    assert all(x['decision']=='accepted' and x['status']=='complete'
               for x in report['members'])
    assert len(list((store.path/'revisions').iterdir()))==3
    assert report['members'][0]['reference']!=report['members'][1]['reference']
    for i in (1,2):
        folder=output/f'member-{i:02d}'
        result=decode((folder/'comparison/result.json').read_bytes())
        assert result['status']=='complete'
        assert len(result['comparisons'])==2
        assert all(x['status']=='ok' for x in result['comparisons'])
    assert (output/'baseline/run.json').read_bytes()!=(template/'run.json').read_bytes()


def test_second_rejected_v3_member_preserves_first_and_partial_ensemble(tmp_path):
    store,root,template,report,output,spec=_run(tmp_path,bad_second=True)
    assert report['status']=='partial'
    assert report['members'][0]['status']=='complete'
    assert report['members'][1]['status']=='rejected'
    assert report['members'][1]['decision']=='rejected'
    assert not (output/'member-02/run').exists()
    assert len(list((store.path/'revisions').iterdir()))==2
    assert (output/'member-02/decision.json').exists()


@pytest.mark.parametrize('mutation',[
    lambda s:s.update(ensemble_version=True),
    lambda s:s.update(ensemble_version=1.0),
    lambda s:s.update(extra=True),
    lambda s:s.update(members=[]),
    lambda s:s.update(members=s['members']*3),
    lambda s:s['members'][1].update(id=s['members'][0]['id']),
    lambda s:s['members'][1]['proposal'].update(proposal_id=s['members'][0]['proposal']['proposal_id']),
    lambda s:s['members'][1]['proposal'].update(revision_id=s['members'][0]['proposal']['revision_id']),
    lambda s:s['members'][0]['proposal'].update(proposal_version=2),
    lambda s:s['members'][0]['proposal']['parent'].update(sha256='0'*64),
    lambda s:s.update(source_run_sha256='0'*64),
    lambda s:s['members'][0]['pairs'].append(deepcopy(s['members'][0]['pairs'][0])),
])
def test_malformed_ensemble_preflight_never_creates_output_or_revision(tmp_path,mutation):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    mutation(spec)
    path=write(tmp_path/'bad-ensemble.json',spec)
    output=tmp_path/'not-created'
    with pytest.raises((ValueError,RevisionError)):
        run_ensemble(path,store_path=store.path,using=template,output=output)
    assert not output.exists()
    assert len(list((store.path/'revisions').iterdir()))==1


def test_same_store_source_run_and_path_aliases_are_refused(tmp_path):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    path=write(tmp_path/'case.json',_spec(root,template,inv,analysis,view))
    for output in (template/'inside',store.path/'inside'):
        with pytest.raises((ValueError,FileExistsError)):
            run_ensemble(path,store_path=store.path,using=template,output=output)
        assert not output.exists()


def test_inspector_rederives_status_even_when_output_manifest_is_resigned(tmp_path):
    store,root,template,report,output,spec=_run(tmp_path)
    doc=decode((output/'summary.json').read_bytes())
    doc['members'][1]['status']='partial'
    doc['status']='partial'
    (output/'summary.json').write_bytes(encode(doc))
    _reseal(output)
    with pytest.raises(RevisionError,match='summary completion'):
        inspect_ensemble(output,store_path=store.path,using=template)


def test_reusing_accepted_ensemble_member_identity_fails_before_new_output(tmp_path):
    store,root,template,report,output,spec=_run(tmp_path)
    request=write(tmp_path/'repeat.json',spec)
    with pytest.raises(RevisionError,match='already reserved'):
        run_ensemble(request,store_path=store.path,using=template,output=tmp_path/'repeat')
    assert not (tmp_path/'repeat').exists()
