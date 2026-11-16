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


def test_four_distinct_atomic_siblings_with_unchanged_root(tmp_path):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'].extend([_member(root,3,inv,analysis,view),
                            _member(root,4,inv,analysis,view)])
    request=write(tmp_path/'four.json',spec)
    before=store.read(root)[1]
    output=tmp_path/'four-output'
    r=run_ensemble(request,store_path=store.path,using=template,output=output)
    assert r['status']=='complete' and len(r['members'])==4
    assert all(x['decision']=='accepted' for x in r['members'])
    assert len(list((store.path/'revisions').iterdir()))==5
    assert store.read(root)[1]==before
    assert inspect_ensemble(output,store_path=store.path,using=template)==r


def test_accepted_revision_with_invalid_named_presentation_has_partial_native_run(tmp_path):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'][1]['presentation']['entity_order']=['left','right','probe','ghost']
    request=write(tmp_path/'invalid-display.json',spec)
    output=tmp_path/'invalid-display-out'
    result=run_ensemble(request,store_path=store.path,using=template,output=output)
    assert result['status']=='partial'
    assert result['members'][0]['status']=='complete'
    assert result['members'][1]['decision']=='accepted'
    assert result['members'][1]['status']=='partial'
    assert result['members'][1]['run_status']=='rejected'
    assert not (output/'member-02/comparison').exists()
    assert inspect_ensemble(output,store_path=store.path,using=template)==result


def test_valid_run_with_explicit_unmatched_baseline_observation_is_partial_not_zero(tmp_path):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'][1]['pairs'][0]['left_observation_id']='absent-parent'
    request=write(tmp_path/'absent.json',spec)
    output=tmp_path/'absent-out'
    result=run_ensemble(request,store_path=store.path,using=template,output=output)
    assert result['members'][0]['status']=='complete'
    assert result['members'][1]['decision']=='accepted'
    assert result['members'][1]['run_status']=='complete'
    assert result['members'][1]['comparison_status']=='partial'
    rows=decode((output/'member-02/comparison/result.json').read_bytes())['comparisons']
    assert rows[0]['status']=='unavailable' and rows[0]['code']=='unknown_operand'
    assert rows[0]['value'] is None
    assert inspect_ensemble(output,store_path=store.path,using=template)==result


def test_duplicate_added_physical_ids_across_siblings_fail_before_first_attempt(tmp_path):
    from test_atomic_revisions import add_particle
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    for member in spec['members']:
        member['proposal']['changes'][1]=add_particle('same-body')
    request=write(tmp_path/'reuse-body.json',spec)
    output=tmp_path/'refused-duplicate-body'
    with pytest.raises(RevisionError,match='may not reuse'):
        run_ensemble(request,store_path=store.path,using=template,output=output)
    assert not output.exists()
    assert len(list((store.path/'revisions').iterdir()))==1


def test_ensemble_output_cannot_alias_sealed_run_or_store(tmp_path):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    request=write(tmp_path/'protected.json',_spec(root,template,inv,analysis,view))
    from pathlib import Path
    for protected in (store.path,template):
        output=Path(protected)/'invented-ensemble'
        with pytest.raises((ValueError,FileExistsError)):
            run_ensemble(request,store_path=store.path,using=template,output=output)
        assert not output.exists()


# Independent R2 review-01 corrective regressions (original source head
# 38773a546d76616fe815eb302c418281bded7c1d). Preserve initial red logs.
@pytest.mark.parametrize(('section','mutation'),[
    ('analysis', 'unexpected_token'),
    ('investigation', 'unexpected_token'),
    ('presentation', 'unexpected_token'),
    ('observation', 'unexpected_token'),
    ('analysis_checks', 'unexpected_token'),
])
def test_r2_malformed_nested_grammar_preflight_has_zero_side_effects(tmp_path,section,mutation):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    member=spec['members'][0]
    if section=='observation':
        member['investigation']['observations'][0][mutation] = 1
    elif section=='analysis_checks':
        member['analysis']['checks']={'position_atol_m':1e-6, mutation:0}
    else:
        member[section][mutation]='malformed'
    request=write(tmp_path/'r2-malformed.json',spec)
    original_root=store.read(root)[1]
    out=tmp_path/'must-not-exist'
    with pytest.raises((ValueError,RevisionError)):
        run_ensemble(request,store_path=store.path,using=template,output=out)
    assert not out.exists()
    assert len(list((store.path/'revisions').iterdir()))==1
    assert not list((store.path/'proposals').iterdir())
    assert store.read(root)[1]==original_root


@pytest.mark.parametrize('numeric_location',['observation','proposal'])
def test_r2_json_numeric_exponent_overflow_must_fail_in_preflight(tmp_path,numeric_location):
    import json
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    if numeric_location=='observation':
        spec['members'][0]['investigation']['observations'][0]['position_m'][0]=123456789.0
        sentinel='123456789.0'
    else:
        spec['members'][0]['proposal']['changes'][0]['value']=123456789.0
        sentinel='123456789.0'
    serialized=json.dumps(spec,separators=(',',':'))
    assert serialized.count(sentinel)==1
    request=tmp_path/'r2-overflow.json'
    request.write_text(serialized.replace(sentinel,'1e400'))
    assert decode(request.read_bytes())['members'][0]  # Python parses 1e400 as float(inf)
    out=tmp_path/'overflow-output'
    with pytest.raises((ValueError,RevisionError),match='finite|nonfinite|float64|numeric'):
        run_ensemble(request,store_path=store.path,using=template,output=out)
    assert not out.exists()
    assert len(list((store.path/'revisions').iterdir()))==1
    assert not list((store.path/'proposals').iterdir())


@pytest.mark.parametrize('bad_second',[True,False])
def test_r2_inspector_binds_native_store_proposal_bytes_even_for_rejections(tmp_path,bad_second):
    store,root,template,report,output,spec=_run(tmp_path,bad_second=bad_second)
    target=spec['members'][1]['proposal']
    assert report['members'][1]['status']==('rejected' if bad_second else 'complete')
    path=store.path/'proposals'/sha256(target['proposal_id'].encode())/'proposal.json'
    original=path.read_bytes()
    assert sha256(original)==decode((store.path/'proposals'/sha256(target['proposal_id'].encode())/'decision.json').read_bytes())['proposal_sha256']
    # Whitespace-only drift preserves parsed semantics but violates the
    # recorded raw-byte decision receipt and must fail inspection.
    path.write_bytes(original + b' ')
    with pytest.raises(RevisionError,match='proposal'):
        inspect_ensemble(output,store_path=store.path,using=template)
    path.write_bytes(original)
    assert inspect_ensemble(output,store_path=store.path,using=template)==report


# Independent R2 review-02 cross-field preflight blocker on original head
# 5738fec0d22deb59d0f146dc75b8a9b33db64486.
def _r2_plane_event():
    return {'id':'cross-mode-event','type':'trajectory_event',
            'particle_id':'probe',
            'condition':{'type':'plane','point_m':[0,0,0],
                         'normal':[0,1,0],'direction':'either'},
            'occurrence':'first','max_step_s':0.1,
            'min_normal_speed_m_s':1e-7,
            'accuracy':{'time_atol_s':1e-5,'position_atol_m':1e-5,
                        'velocity_atol_m_s':1e-5,'rtol':1e-8}}


@pytest.mark.parametrize('motion', [
    {'id':'cross-mode-sample','type':'trajectory_sample',
     'particle_id':'probe','quantity':'position','sample_index':0},
    _r2_plane_event(),
],ids=['valid-index0-sample','complete-valid-plane-event'])
def test_r2_static_motion_grammar_refuses_before_sibling_acceptance(tmp_path,motion):
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    # Second member is the bad one: even the first valid sibling must not
    # publish a revision during the global schema preflight.
    assert spec['members'][0]['analysis']['mode']=='static'
    spec['members'][1]['analysis']={'analysis_version':1,
                                    'id':'variant-2-analysis','mode':'static'}
    spec['members'][1]['investigation']['observations'].append(deepcopy(motion))
    req=write(tmp_path/'cross-mode-spec.json',spec)
    before_store={p.relative_to(store.path).as_posix():p.read_bytes()
                  for p in store.path.rglob('*') if p.is_file()}
    before_native={p.relative_to(template).as_posix():p.read_bytes()
                   for p in template.rglob('*') if p.is_file()}
    out=tmp_path/'cross-mode-refused'
    with pytest.raises(RevisionError,match='trajectory|analysis') as exc:
        run_ensemble(req,store_path=store.path,using=template,output=out)
    assert exc.value.code=='unsupported_analysis'
    assert not out.exists()
    assert len(list((store.path/'revisions').iterdir()))==1
    assert not list((store.path/'proposals').iterdir())
    assert {p.relative_to(store.path).as_posix():p.read_bytes() for p in store.path.rglob('*') if p.is_file()}==before_store
    assert {p.relative_to(template).as_posix():p.read_bytes() for p in template.rglob('*') if p.is_file()}==before_native

# R1 convenience: verified selection of an existing sealed native run for viewing.
def _files_now(root):
    return {p.relative_to(root).as_posix():p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize(('choice','expected'),[
    ('baseline','baseline'),
    ('variant-1','member-01/run'),
    ('variant-2','member-02/run'),
])
def test_verified_ensemble_view_selects_only_saved_native_runs(tmp_path,monkeypatch,choice,expected):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path)
    recorded=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:recorded.append((run,kw)))
    before={label:_files_now(folder) for label,folder in [('store',store.path),('template',template),('ensemble',out)]}
    kwargs={'baseline':True} if choice=='baseline' else {'member_id':choice}
    result=view_ensemble(out,store_path=store.path,using=template,**kwargs)
    assert result['status']=='complete'
    assert result['selection']==('baseline' if choice=='baseline' else 'member:'+choice)
    assert result['selection_kind']==('fresh_baseline' if choice=='baseline' else 'member')
    assert result['member_id']==(None if choice=='baseline' else choice)
    assert result['run_path']==expected
    assert result['run_integrity_sha256']==sha256((out/expected/'integrity.json').read_bytes())
    assert result['ensemble_id']==report['id']
    assert 'not teacher acceptance' in result['presentation']
    assert 'physical transition' in result['meaning']
    assert recorded==[(out/expected,{'sample_index':0,'screenshot_directory':None})]
    assert {label:_files_now(folder) for label,folder in [('store',store.path),('template',template),('ensemble',out)]}==before


def test_verified_ensemble_view_allows_complete_native_member_with_partial_comparison(tmp_path,monkeypatch):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'][1]['pairs'][0]['left_observation_id']='missing-baseline-observation'
    req=write(tmp_path/'partial-comparison.json',spec)
    out=tmp_path/'partial-comparison-ensemble'
    report=run_ensemble(req,store_path=store.path,using=template,output=out)
    assert report['status']=='partial'
    assert report['members'][1]['run_status']=='complete'
    assert report['members'][1]['comparison_status']=='partial'
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:called.append(run))
    result=view_ensemble(out,store_path=store.path,using=template,member_id='variant-2')
    assert result['ensemble_status']=='partial'
    assert called==[out/'member-02/run']


def test_verified_ensemble_view_rejects_physically_rejected_member_but_keeps_accepted_sibling(tmp_path,monkeypatch):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path,bad_second=True)
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:called.append(run))
    with pytest.raises(RevisionError,match='complete native run') as err:
        view_ensemble(out,store_path=store.path,using=template,member_id='variant-2')
    assert err.value.code=='preview_unavailable'
    assert called==[]
    row=view_ensemble(out,store_path=store.path,using=template,member_id='variant-1')
    assert row['ensemble_status']=='partial' and row['status']=='complete'
    assert called==[out/'member-01/run']


@pytest.mark.parametrize('cause',['unknown','missing_selector','double_selector','invalid_sample','static_sample'])
def test_verified_ensemble_view_invalid_selection_refuses_without_render(tmp_path,monkeypatch,cause):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path)
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:called.append(run))
    kwargs={
        'unknown':{'member_id':'not-a-real-member'},
        'missing_selector':{},
        'double_selector':{'baseline':True,'member_id':'variant-1'},
        'invalid_sample':{'baseline':True,'sample_index':-1},
        'static_sample':{'baseline':True,'sample_index':1},
    }[cause]
    with pytest.raises((RevisionError,ValueError)):
        view_ensemble(out,store_path=store.path,using=template,**kwargs)
    assert called==[]


@pytest.mark.parametrize('target',['ensemble','store','template','existing','symlink_alias'])
def test_verified_ensemble_view_rejects_protected_screenshot_destination(tmp_path,monkeypatch,target):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path)
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:called.append(run))
    if target=='ensemble': destination=out/'screens'
    elif target=='store':destination=store.path/'screens'
    elif target=='template':destination=template/'screens'
    elif target=='existing':
        destination=tmp_path/'screens';destination.mkdir()
    else:
        symlink=tmp_path/'out-alias';symlink.symlink_to(out,target_is_directory=True)
        destination=symlink/'screens'
    with pytest.raises((ValueError,FileExistsError)):
        view_ensemble(out,store_path=store.path,using=template,baseline=True,
                      screenshot_output=destination)
    assert called==[]
    assert destination.exists() is (target=='existing')


def test_verified_ensemble_view_external_screenshot_delegates_to_existing_viewer(tmp_path,monkeypatch):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path)
    seen=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:seen.append((run,kw)))
    dest=tmp_path/'new-screens'
    result=view_ensemble(out,store_path=store.path,using=template,
                         member_id='variant-1',screenshot_output=dest)
    assert result['status']=='complete'
    assert seen==[(out/'member-01/run',{'sample_index':0,'screenshot_directory':dest})]
    assert not dest.exists()  # Fake did not render or write; real native viewer owns it.


@pytest.mark.parametrize('tamper',['output','store','template'])
def test_verified_ensemble_view_refuses_tampered_evidence_before_viewer(tmp_path,monkeypatch,tamper):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path)
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:called.append(run))
    if tamper=='output':path=out/'member-01/decision.json'
    elif tamper=='template':path=template/'run.json'
    else:
        proposal_id=spec['members'][0]['proposal']['proposal_id']
        path=store.path/'proposals'/sha256(proposal_id.encode())/'proposal.json'
    old=path.read_bytes()
    path.write_bytes(old+b' ')
    with pytest.raises((RevisionError,ValueError)):
        view_ensemble(out,store_path=store.path,using=template,member_id='variant-1')
    assert called==[]
    assert path.read_bytes()==old+b' '


def test_verified_ensemble_view_member_named_baseline_is_unambiguous(tmp_path,monkeypatch):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'][0]['id']='baseline'  # Legitimate member name, not special CLI token.
    req=write(tmp_path/'baseline-name.json',spec)
    out=tmp_path/'baseline-name-out'
    report=run_ensemble(req,store_path=store.path,using=template,output=out)
    assert report['status']=='complete'
    seen=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:seen.append(run))
    view_ensemble(out,store_path=store.path,using=template,baseline=True)
    view_ensemble(out,store_path=store.path,using=template,member_id='baseline')
    assert seen==[out/'baseline',out/'member-01/run']


def test_verified_ensemble_view_cli_requires_explicit_selector_and_preserves_other_commands(tmp_path,monkeypatch,capsys):
    from emfeeld import scenario_ensembles as module
    store,root,template,report,out,spec=_run(tmp_path)
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda run,**kw:called.append(run))
    common=[str(out),'--store',str(store.path),'--using',str(template)]
    assert module.main(['view',*common,'--member','variant-1'])==0
    assert decode(capsys.readouterr().out.encode())['selection']=='member:variant-1'
    assert called==[out/'member-01/run']
    assert module.main(['view',*common])==2
    assert 'select exactly one' in capsys.readouterr().err
    assert module.main(['inspect',*common,'--member','variant-1'])==2
    assert 'does not accept view selection' in capsys.readouterr().err
    assert module.main(['inspect',*common])==0
    assert decode(capsys.readouterr().out.encode())==report


# Independent R1 review-01 F1: the selected three roots are not the only
# sealed evidence that a screenshot must preserve. Each other root here is
# independently constructed, then kept byte-identical on the refused view.
@pytest.mark.parametrize('foreign_kind', [
    'native_run', 'member_run', 'ensemble', 'model_store',
    'comparison', 'symlinked_native_run',
])
def test_r1_view_screenshot_refuses_unrelated_sealed_evidence(tmp_path, monkeypatch, foreign_kind):
    from emfeeld.scenario_ensembles import view_ensemble
    selected_home=tmp_path/'selected'
    selected_home.mkdir()
    store,root,template,report,out,spec=_run(selected_home)
    foreign_home=tmp_path/'foreign'
    foreign_home.mkdir()
    other_store,other_root,other_template,other_report,other_out,other_spec=_run(foreign_home)
    roots={'native_run':other_template,
           'member_run':other_out/'member-01/run',
           'ensemble':other_out,
           'model_store':other_store.path,
           'comparison':other_out/'member-01/comparison'}
    if foreign_kind == 'symlinked_native_run':
        alias=tmp_path/'foreign-run-alias'
        alias.symlink_to(other_template,target_is_directory=True)
        protected=alias
    else:
        protected=roots[foreign_kind]
    destination=protected/'new-screens'
    before={key:_files_now(path) for key,path in (
        ('selected_store',store.path),('selected_template',template),
        ('selected_ensemble',out),('foreign_store',other_store.path),
        ('foreign_template',other_template),('foreign_ensemble',other_out))}
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda *args,**kwargs:called.append(args))
    with pytest.raises(ValueError,match='saved evidence|model stores'):
        view_ensemble(out,store_path=store.path,using=template,baseline=True,
                      screenshot_output=destination)
    assert not called
    assert not destination.exists()
    after={key:_files_now(path) for key,path in (
        ('selected_store',store.path),('selected_template',template),
        ('selected_ensemble',out),('foreign_store',other_store.path),
        ('foreign_template',other_template),('foreign_ensemble',other_out))}
    assert after==before
    assert model_runs.inspect_run(other_template)[2]['execution_complete']
    assert inspect_ensemble(other_out,store_path=other_store.path,using=other_template)==other_report


def test_r1_view_screenshot_refuses_unsealed_started_ensemble(tmp_path,monkeypatch):
    from emfeeld.scenario_ensembles import view_ensemble
    store,root,template,report,out,spec=_run(tmp_path)
    pending=tmp_path/'unsealed-attempt'
    (pending/'inputs').mkdir(parents=True)
    (pending/'started.json').write_bytes(b'{}')
    (pending/'inputs/ensemble.json').write_bytes(b'{}')
    dest=pending/'screens'
    called=[]
    monkeypatch.setattr(model_runs,'present_run',lambda *a,**kw:called.append(a))
    with pytest.raises(ValueError,match='saved evidence'):
        view_ensemble(out,store_path=store.path,using=template,baseline=True,
                      screenshot_output=dest)
    assert not dest.exists() and not called


def test_r1_baseline_named_member_has_distinct_saved_id_and_cli_binding(tmp_path,monkeypatch,capsys):
    from emfeeld import scenario_ensembles as module
    from emfeeld.scenario_ensembles import _run_id
    from emfeeld.model_revisions import identifier
    # Include maximum valid ID lengths: generated IDs must never violate the
    # native 64-character identifier grammar for fully legitimate inputs.
    assert len(_run_id('e'*25,'m'*25))==62
    assert identifier(_run_id('e'*25,'m'*25))==_run_id('e'*25,'m'*25)
    assert _run_id('e'*25)!=_run_id('e'*25,'baseline')
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'] += [_member(root,3,inv,analysis,view),
                        _member(root,4,inv,analysis,view)]
    spec['members'][2]['id']='baseline'
    request=write(tmp_path/'four-member-request.json',spec)
    out=tmp_path/'four-member-ensemble'
    report=run_ensemble(request,store_path=store.path,using=template,output=out)
    assert report['status']=='complete'
    calls=[]
    monkeypatch.setattr(model_runs,'present_run',lambda path,**kw:calls.append(path))
    common=[str(out),'--store',str(store.path),'--using',str(template)]
    assert module.main(['view',*common,'--baseline'])==0
    base=decode(capsys.readouterr().out.encode())
    assert module.main(['view',*common,'--member','baseline'])==0
    member=decode(capsys.readouterr().out.encode())
    assert calls==[out/'baseline',out/'member-03/run']
    assert base['selection']=='baseline' and base['selection_kind']=='fresh_baseline'
    assert base['member_id'] is None and base['run_path']=='baseline'
    assert member['selection']=='member:baseline' and member['selection_kind']=='member'
    assert member['member_id']=='baseline' and member['run_path']=='member-03/run'
    assert base['reference']==report['parent']
    assert member['reference']==report['members'][2]['reference']
    assert base['reference']!=member['reference']
    assert base['run_id']!=member['run_id']
    assert base['run_integrity_sha256']==sha256((out/'baseline/integrity.json').read_bytes())
    assert member['run_integrity_sha256']==sha256((out/'member-03/run/integrity.json').read_bytes())
    assert base['run_integrity_sha256']!=member['run_integrity_sha256']
    assert inspect_ensemble(out,store_path=store.path,using=template)==report


# Read-only V1 measurement readout: no independent numerical relation or solver.
def test_verified_measurements_exact_sealed_values_and_zero_writes(tmp_path):
    from emfeeld.scenario_ensembles import read_ensemble_measurements
    store,root,template,report,out,spec=_run(tmp_path)
    before={label:_files_now(folder) for label,folder in
            [('store',store.path),('template',template),('ensemble',out)]}
    result=read_ensemble_measurements(out,store_path=store.path,using=template)
    assert result['status']=='complete'
    assert result['selection']=='all_members'
    assert result['parent']==root and result['source_run_sha256']==spec['source_run_sha256']
    assert [x['id'] for x in result['members']]==['variant-1','variant-2']
    for i,row in enumerate(result['members'],1):
        folder=out/f'member-{i:02d}/comparison'
        sealed=decode((folder/'result.json').read_bytes())
        assert row['status']=='complete' and row['decision']=='accepted'
        assert row['comparison_status']=='complete'
        assert row['evidence']['result_sha256']==sha256((folder/'result.json').read_bytes())
        assert row['evidence']['request_sha256']==sha256((folder/'request.json').read_bytes())
        assert row['evidence']['integrity_sha256']==sha256((folder/'integrity.json').read_bytes())
        assert len(row['measurements'])==len(sealed['comparisons'])==2
        for projection,original in zip(row['measurements'],sealed['comparisons']):
            for key,value in projection.items():
                assert value==original.get(key)
            assert projection['status']=='ok'
            assert projection['value']==original['value']
            assert projection['unit']==original['unit']
            assert projection['type']==original['type']
    assert {label:_files_now(folder) for label,folder in
            [('store',store.path),('template',template),('ensemble',out)]}==before


def test_verified_measurements_member_named_baseline_is_exact_filtered_member(tmp_path):
    from emfeeld.scenario_ensembles import read_ensemble_measurements
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'].extend([_member(root,3,inv,analysis,view),
                            _member(root,4,inv,analysis,view)])
    spec['members'][2]['id']='baseline'
    out=tmp_path/'four-ensemble'
    run_ensemble(write(tmp_path/'four-measurements.json',spec),store_path=store.path,
                 using=template,output=out)
    all_result=read_ensemble_measurements(out,store_path=store.path,using=template)
    selected=read_ensemble_measurements(out,store_path=store.path,
                                        using=template,member_id='baseline')
    assert len(all_result['members'])==4
    assert selected['selection']=='member:baseline'
    assert selected['members']==[all_result['members'][2]]
    assert selected['members'][0]['index']==3
    assert selected['members'][0]['reference'] != root
    assert selected['baseline']['reference']==root


def test_verified_measurements_partial_comparison_keeps_native_unit_and_no_fake_zero(tmp_path):
    from emfeeld.scenario_ensembles import read_ensemble_measurements
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'][1]['pairs'][0]['left_observation_id']='missing-parent'
    out=tmp_path/'partial-measurements'
    saved=run_ensemble(write(tmp_path/'partial-measurements.json',spec),
                       store_path=store.path,using=template,output=out)
    assert saved['status']=='partial'
    result=read_ensemble_measurements(out,store_path=store.path,using=template)
    assert result['status']=='partial'
    assert result['members'][0]['status']=='complete'
    second=result['members'][1]
    assert second['run_status']=='complete'
    assert second['status']=='partial' and second['comparison_status']=='partial'
    original=decode((out/'member-02/comparison/result.json').read_bytes())['comparisons']
    assert [x['status'] for x in second['measurements']]==[x['status'] for x in original]
    missing=next(x for x in second['measurements'] if x['status']=='unavailable')
    assert missing['code']=='unknown_operand'
    assert missing['value'] is None  # Never silently replace unavailable with zero.
    assert missing['reason']==next(x for x in original if x['status']=='unavailable')['reason']
    assert any(x['status']=='ok' for x in second['measurements'])
    assert 'physical transition' in result['meaning']


@pytest.mark.parametrize('kind',['rejected_revision','partial_native'])
def test_verified_measurements_preserve_unattempted_comparison_reason(tmp_path,kind):
    from emfeeld.scenario_ensembles import read_ensemble_measurements
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view,bad_second=(kind=='rejected_revision'))
    if kind=='partial_native':
        spec['members'][1]['presentation']['entity_order'].append('ghost')
    out=tmp_path/'unavailable-readout'
    report=run_ensemble(write(tmp_path/'unavailable-readout.json',spec),
                        store_path=store.path,using=template,output=out)
    assert report['status']=='partial'
    result=read_ensemble_measurements(out,store_path=store.path,using=template)
    first,second=result['members']
    assert first['status']=='complete' and first['measurements']
    assert second['status'] in ('rejected','partial')
    assert second['measurements']==[] and second['evidence'] is None
    assert second['comparison_status'] is None and second['reason']
    assert second['decision']==('rejected' if kind=='rejected_revision' else 'accepted')


@pytest.mark.parametrize('which',['summary','comparison','store_proposal','template','run_input'])
def test_verified_measurements_fail_closed_on_tampered_original_evidence(tmp_path,which):
    from emfeeld.scenario_ensembles import read_ensemble_measurements
    store,root,template,report,out,spec=_run(tmp_path)
    if which=='summary': path=out/'summary.json'
    elif which=='comparison':path=out/'member-02/comparison/result.json'
    elif which=='template':path=template/'run.json'
    elif which=='run_input':path=out/'member-01/run/investigation.json'
    else:
        proposal_id=spec['members'][0]['proposal']['proposal_id']
        path=store.path/'proposals'/sha256(proposal_id.encode())/'proposal.json'
    old=path.read_bytes()
    path.write_bytes(old+b' ')
    before={label:_files_now(folder) for label,folder in
            [('store',store.path),('template',template),('ensemble',out)]}
    with pytest.raises((ValueError,RevisionError)):
        read_ensemble_measurements(out,store_path=store.path,using=template,
                                   member_id='variant-2')
    assert {label:_files_now(folder) for label,folder in
            [('store',store.path),('template',template),('ensemble',out)]}==before


@pytest.mark.parametrize('bad_id',['ghost','',123,True,False])
def test_verified_measurements_unknown_member_filter_refuses_without_writes(tmp_path,bad_id):
    from emfeeld.scenario_ensembles import read_ensemble_measurements
    store,root,template,report,out,spec=_run(tmp_path)
    before=_files_now(out)
    with pytest.raises((ValueError,RevisionError)):
        read_ensemble_measurements(out,store_path=store.path,using=template,
                                   member_id=bad_id)
    assert _files_now(out)==before


def test_verified_measurements_cli_global_partial_and_declared_member_flags(tmp_path,capsys):
    from emfeeld import scenario_ensembles as module
    store,root=imported(tmp_path)
    template,inv,analysis,view=_native_root(tmp_path,store,root)
    spec=_spec(root,template,inv,analysis,view)
    spec['members'][1]['pairs'][0]['left_observation_id']='not-in-parent'
    out=tmp_path/'cli-measurements'
    report=run_ensemble(write(tmp_path/'cli-measurements.json',spec),
                        store_path=store.path,using=template,output=out)
    assert report['status']=='partial'
    common=[str(out),'--store',str(store.path),'--using',str(template)]
    before=_files_now(out)
    assert module.main(['measurements',*common,'--member','variant-1'])==1
    result=decode(capsys.readouterr().out.encode())
    assert result['status']=='partial'  # Full ensemble, not falsely filtered to complete.
    assert result['selection']=='member:variant-1'
    assert len(result['members'])==1 and result['members'][0]['status']=='complete'
    assert result['members'][0]['measurements']
    for args in (['--output',str(tmp_path/'writes')],['--baseline'],['--sample-index','0']):
        assert module.main(['measurements',*common,*args])==2
        assert 'accepts only' in capsys.readouterr().err
    assert module.main(['inspect',*common])==1
    assert decode(capsys.readouterr().out.encode())==report
    assert not (tmp_path/'writes').exists()
    assert _files_now(out)==before


def test_verified_measurements_refuses_changed_result_after_inspection(tmp_path,monkeypatch):
    from emfeeld import scenario_ensembles as module
    store,root,template,report,out,spec=_run(tmp_path)
    target=out/'member-01/comparison/result.json'
    before_store=_files_now(store.path)
    real_inspect=module.scenario_comparisons.inspect
    calls=[]
    def changed_after_inspection(folder,**kwargs):
        result=real_inspect(folder,**kwargs)
        if folder==target.parent:
            calls.append(folder)
            if len(calls)==2:  # once inside ensemble inspect, once for readout
                target.write_bytes(target.read_bytes()+b' ')
        return result
    monkeypatch.setattr(module.scenario_comparisons,'inspect',changed_after_inspection)
    with pytest.raises(RevisionError,match='changed during readout'):
        module.read_ensemble_measurements(out,store_path=store.path,using=template)
    assert _files_now(store.path)==before_store
    assert target.read_bytes().endswith(b' ')


@pytest.mark.parametrize('window', ['after_ensemble_inspect', 'after_comparison_inspect'])
def test_r1_original_ensemble_seal_binds_comparison_integrity_during_readout(tmp_path, monkeypatch, window):
    """Reviewer B1: whitespace-only late integrity drift must not forge a receipt."""
    from emfeeld import scenario_ensembles as module
    store, root, template, report, out, spec = _run(tmp_path)
    target = out/'member-02/comparison/integrity.json'
    relative = target.relative_to(out).as_posix()
    original = target.read_bytes()
    seal = decode((out/'integrity.json').read_bytes())
    assert seal['files'][relative] == sha256(original)
    assert module.inspect_ensemble(out, store_path=store.path, using=template) == report
    before_store = _files_now(store.path)
    before_template = _files_now(template)
    before_out = _files_now(out)
    changed = []
    if window == 'after_ensemble_inspect':
        real_inspect = module.inspect_ensemble
        def later_inspect(*args, **kwargs):
            result = real_inspect(*args, **kwargs)
            if not changed:
                target.write_bytes(original + b' ')
                changed.append('after_ensemble_inspect')
            return result
        monkeypatch.setattr(module, 'inspect_ensemble', later_inspect)
    else:
        real_cmp_inspect = module.scenario_comparisons.inspect
        calls = []
        def later_comparison(folder, **kwargs):
            result = real_cmp_inspect(folder, **kwargs)
            if folder == target.parent:
                calls.append(folder)
                if len(calls) == 2:
                    target.write_bytes(original + b' ')
                    changed.append('after_comparison_inspect')
            return result
        monkeypatch.setattr(module.scenario_comparisons, 'inspect', later_comparison)
    with pytest.raises(RevisionError, match='integrity|changed during readout') as exc:
        module.read_ensemble_measurements(out, store_path=store.path,
                                          using=template, member_id='variant-2')
    assert exc.value.code in ('comparison_integrity', 'ensemble_integrity')
    assert changed == [window]
    assert target.read_bytes() == original + b' '
    assert _files_now(store.path) == before_store
    assert _files_now(template) == before_template
    assert {**before_out, relative: original + b' '} == _files_now(out)


def test_r1_readout_refuses_changed_outer_seal_after_original_inspection(tmp_path, monkeypatch):
    """The manifest used for exact receipts cannot change after its preflight."""
    from emfeeld import scenario_ensembles as module
    store, root, template, report, out, spec = _run(tmp_path)
    target = out/'integrity.json'
    original = target.read_bytes()
    before_store = _files_now(store.path)
    before_template = _files_now(template)
    before_out = _files_now(out)
    real_inspect = module.inspect_ensemble
    calls = []
    def changed_after_inspection(*args, **kwargs):
        saved = real_inspect(*args, **kwargs)
        target.write_bytes(original + b' ')
        calls.append('modified_ensemble_seal_after_preflight')
        return saved
    monkeypatch.setattr(module, 'inspect_ensemble', changed_after_inspection)
    with pytest.raises(RevisionError, match='ensemble inventory changed during readout') as exc:
        module.read_ensemble_measurements(out, store_path=store.path,
                                          using=template, member_id='variant-1')
    assert exc.value.code == 'ensemble_integrity'
    assert calls == ['modified_ensemble_seal_after_preflight']
    assert _files_now(store.path) == before_store
    assert _files_now(template) == before_template
    assert {**before_out, 'integrity.json': original + b' '} == _files_now(out)
