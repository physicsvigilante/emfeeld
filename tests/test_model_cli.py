"""Native convenience integration, without a second revision or physics implementation."""
from copy import deepcopy
from pathlib import Path
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from emfeeld import cli, model_cli as workflow, model_runs
from emfeeld.model_revisions import ModelStore, RevisionError, encode, decode, sha256
from test_model_revisions import imported, proposal, execute, write, base_scene


def prepared(tmp_path, *, mode='trajectory', scene=None, change=None):
    store, ref = imported(tmp_path, scene)
    _, prior = execute(tmp_path, store, ref, mode=mode, change=change, name='prior')
    path = write(tmp_path/'revision.json', proposal(ref))
    return store, ref, prior, path


def apply(tmp_path, setup, **kwargs):
    store, _, prior, path = setup
    return workflow.apply_revision(path, store_path=store.path, using=prior,
                                   output=tmp_path/'attempt', run_id='new-run', **kwargs)


def files(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def test_applies_native_revision_and_captures_exact_reused_settings(tmp_path):
    setup = prepared(tmp_path); store, root, prior, path = setup
    before = files(prior); original = store.read(root)[1]
    result = apply(tmp_path, setup)
    assert result['status'] == 'complete'
    assert result['decision']['status'] == 'accepted'
    assert result['calculation']['execution_complete']
    assert store.read(root)[1] == original and files(prior) == before
    new = store.read(result['decision']['reference'])[0]
    assert new['parent'] == root
    assert new['entities']['left']['properties']['charge_C'] == -2e-9
    assert new['entities']['right'] == store.read(root)[0]['entities']['right']
    out = tmp_path/'attempt'
    assert (out/'inputs/proposal.json').read_bytes() == path.read_bytes()
    for name in workflow.SETTINGS:
        assert (out/'inputs'/name).read_bytes() == before[name]
        assert (out/'run'/name).read_bytes() == before[name]
    run, _, summary, native = model_runs.inspect_run(out/'run')
    assert run['reference'] == result['decision']['reference']
    assert summary['execution_complete'] and native['status'] == 'ok'
    assert (out/'REPORT.md').is_file()
    assert result['settings_from']['reuse'].startswith('settings only')


def test_revision_result_agrees_with_separate_interior_harmonic_solution(tmp_path):
    setup=prepared(tmp_path); result=apply(tmp_path, setup)
    run_path=tmp_path/'attempt/run'; _, rev, _, native=model_runs.inspect_run(run_path)
    from scipy.constants import epsilon_0
    k=1/(4*np.pi*epsilon_0)
    p=rev['entities']['probe']['properties']; ratio=p['charge_C']/p['mass_kg']
    sources=[rev['entities'][name]['properties'] for name in rev['source_order']]
    weights=np.array([-ratio*k*s['charge_C']/s['radius_m']**3 for s in sources])
    centres=np.array([s['center_m'] for s in sources]); omega=np.sqrt(weights.sum())
    equilibrium=(weights[:,None]*centres).sum(axis=0)/weights.sum()
    from emfeeld.study import load_recorded
    _, (trajectory,)=load_recorded(run_path/'native')
    t=trajectory.time_s[:,None]; r0=np.array(p['position_m']); v0=np.array(p['velocity_m_s'])
    reference=equilibrium+(r0-equilibrium)*np.cos(omega*t)+v0/omega*np.sin(omega*t)
    for s in sources:assert np.all(np.linalg.norm(reference-s['center_m'],axis=1)<s['radius_m'])
    np.testing.assert_allclose(trajectory.position_m,reference,rtol=1e-9,atol=1e-9)


def test_chaining_uses_exact_new_parent_and_reuses_prior_run_settings(tmp_path):
    setup=prepared(tmp_path); first=apply(tmp_path,setup)
    second=proposal(first['decision']['reference'], ident='second', rev='second',
                    target='probe', role='particle', category='initial_condition',
                    prop='velocity_m_s', old=[0,.1,0], value=[0,.2,.1])
    path=write(tmp_path/'second.json',second)
    result=workflow.apply_revision(path, store_path=setup[0].path, using=tmp_path/'attempt/run',
                                  output=tmp_path/'second-attempt')
    assert result['status']=='complete'
    revision,_=setup[0].read(result['decision']['reference'])
    assert revision['parent']==first['decision']['reference']
    assert revision['entities']['left']['properties']['charge_C']==-2e-9
    assert revision['entities']['probe']['properties']['velocity_m_s']==[0,.2,.1]


@pytest.mark.parametrize('case', ['stale_parent','wrong_old','no_op','wrong_role','unsupported_change'])
def test_rejected_changes_never_execute_or_open_viewer(tmp_path,monkeypatch,case):
    setup=prepared(tmp_path); data=decode(setup[3].read_bytes())
    if case=='stale_parent':data['parent']['sha256']='0'*64
    elif case=='wrong_old':data['expected_value']=-99
    elif case=='no_op':data['value']=data['expected_value']
    elif case=='wrong_role':data['expected_role']='particle'
    else:data['category']='boundary_condition'
    write(setup[3],data); before=setup[0].read(setup[1])[1]
    monkeypatch.setattr(model_runs,'execute',lambda *a,**k:pytest.fail('must not calculate'))
    monkeypatch.setattr(model_runs,'present_run',lambda *a,**k:pytest.fail('must not view'))
    result=apply(tmp_path,setup,view=True)
    assert result['status'] in ('rejected','no_op')
    assert not (tmp_path/'attempt/run').exists()
    assert (tmp_path/'attempt/outcome.json').is_file()
    assert setup[0].read(setup[1])[1]==before


def test_existing_output_rejected_before_store_mutation(tmp_path):
    setup=prepared(tmp_path); before=files(setup[0].path)
    (tmp_path/'attempt').mkdir(); (tmp_path/'attempt/existing').write_text('retained')
    with pytest.raises(FileExistsError):apply(tmp_path,setup)
    assert files(setup[0].path)==before
    assert (tmp_path/'attempt/existing').read_text()=='retained'


@pytest.mark.parametrize('protected', ['store','prior'])
def test_output_cannot_taint_store_or_existing_run(tmp_path,protected):
    store,root,prior,path=prepared(tmp_path)
    parent=store.path if protected=='store' else prior
    before=files(parent)
    with pytest.raises(ValueError,match='outside'):
        workflow.apply_revision(path,store_path=store.path,using=prior,output=parent/'new')
    assert files(parent)==before


def test_wrong_model_settings_rejected_without_publishing_revision(tmp_path):
    setup=prepared(tmp_path); other=tmp_path/'other';other.mkdir()
    # Same physical facts, different exact root ID and provenance.
    def change(spec):spec['model_id']='other-model'
    store,ref=imported(other,mutate=change);_,prior=execute(other,store,ref)
    before=files(setup[0].path)
    with pytest.raises(RevisionError,match='another model root'):
        workflow.apply_revision(setup[3],store_path=setup[0].path,using=prior,output=tmp_path/'bad')
    assert files(setup[0].path)==before and not (tmp_path/'bad').exists()


def test_tampered_template_cannot_supply_settings(tmp_path):
    setup=prepared(tmp_path);before=files(setup[0].path)
    p=setup[2]/'analysis.json';p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(RevisionError,match='inventory|bytes'):apply(tmp_path,setup)
    assert files(setup[0].path)==before and not (tmp_path/'attempt').exists()


def test_captured_proposal_not_reread_after_parent_preflight(tmp_path,monkeypatch):
    setup=prepared(tmp_path);raw=setup[3].read_bytes();old=ModelStore.revise
    def mutate_source(self, captured):
        changed=decode(raw);changed['value']=-100
        setup[3].write_bytes(encode(changed))
        return old(self,captured)
    monkeypatch.setattr(ModelStore,'revise',mutate_source)
    result=apply(tmp_path,setup)
    assert result['status']=='complete'
    assert (tmp_path/'attempt/inputs/proposal.json').read_bytes()==raw
    assert setup[0].read(result['decision']['reference'])[0]['entities']['left']['properties']['charge_C']==-2e-9


def test_unexpected_backend_error_retains_started_attempt_and_accepted_revision(tmp_path,monkeypatch):
    setup=prepared(tmp_path)
    def broken(*a,**k):raise RuntimeError('injected unexpected backend error')
    monkeypatch.setattr(model_runs,'execute',broken)
    with pytest.raises(RuntimeError,match='unexpected backend'):apply(tmp_path,setup)
    out=tmp_path/'attempt'
    assert (out/'started.json').exists() and (out/'decision.json').exists()
    assert not (out/'outcome.json').exists()
    assert setup[0].reference('variant')['revision_id']=='variant'


def test_view_failure_does_not_change_completed_calculation(tmp_path,monkeypatch):
    setup=prepared(tmp_path)
    def broken(*a,**k):raise RuntimeError('injected missing graphics context')
    monkeypatch.setattr(model_runs,'present_run',broken)
    result=apply(tmp_path,setup,view=True)
    assert result['status']=='presentation_failed'
    assert result['calculation']['execution_complete']
    assert model_runs.inspect_run(tmp_path/'attempt/run')[2]['execution_complete']
    assert result['presentation']['reason'].startswith('injected')


def test_desktop_view_receives_new_recorded_run_only_after_success(tmp_path,monkeypatch):
    setup=prepared(tmp_path);calls=[]
    def opened(path,**kwargs):
        assert model_runs.inspect_run(path)[2]['execution_complete']
        calls.append((Path(path),kwargs))
    monkeypatch.setattr(model_runs,'present_run',opened)
    result=apply(tmp_path,setup,view=True)
    assert result['status']=='complete' and result['presentation']['status']=='opened_and_closed'
    assert calls==[(tmp_path/'attempt/run',{'sample_index':0,'screenshot_directory':None})]


def test_no_event_preserved_and_blocks_automatic_view(tmp_path,monkeypatch):
    def change(inv,analysis,view):
        inv['observations']=[{'id':'cross','type':'trajectory_event','particle_id':'probe',
            'condition':{'type':'plane','point_m':[1000,0,0],'normal':[1,0,0],'direction':'either'},
            'occurrence':'first','max_step_s':.02,'min_normal_speed_m_s':1e-7,
            'accuracy':{'time_atol_s':1e-6,'position_atol_m':1e-6,'velocity_atol_m_s':1e-6,'rtol':1e-7}}]
    setup=prepared(tmp_path,change=change)
    monkeypatch.setattr(model_runs,'present_run',lambda *a,**k:pytest.fail('no-event is not a successful requested measurement'))
    result=apply(tmp_path,setup,view=True)
    assert result['status']=='incomplete'
    assert result['calculation']['unfulfilled_requests']=={'cross':'no_event'}


def test_failed_expectation_retained_and_blocks_view(tmp_path,monkeypatch):
    def change(inv,analysis,view):inv['observations'][0]['expectation']={'value':[1e30]*3,'atol':0,'rtol':0}
    setup=prepared(tmp_path,change=change)
    monkeypatch.setattr(model_runs,'present_run',lambda *a,**k:pytest.fail('must not view'))
    result=apply(tmp_path,setup,view=True)
    assert result['status']=='incomplete'
    assert result['calculation']['unfulfilled_requests']['E']=='reference_mismatch'


def test_construction_valid_singular_launch_retains_unrelated_measurements(tmp_path,monkeypatch):
    scene=base_scene();scene['sources'][0]={'type':'point','charge_C':-1e-12,'center_m':[-.2,0,0]}
    setup=prepared(tmp_path,scene=scene)
    write(setup[3],proposal(setup[1],target='probe',role='particle',category='initial_condition',
        prop='position_m',old=[.3,.2,.1],value=[-.2,0,0]))
    monkeypatch.setattr(model_runs,'present_run',lambda *a,**k:pytest.fail('must not view'))
    result=apply(tmp_path,setup,view=True)
    assert result['decision']['status']=='accepted' and result['status']=='incomplete'
    assert result['calculation']['request_statuses']['E']=='ok'
    assert result['calculation']['request_statuses']['r']=='domain_error'


def test_static_analysis_does_not_invent_motion_for_requested_view(tmp_path,monkeypatch):
    setup=prepared(tmp_path,mode='static')
    import emfeeld.trajectory_samples as samples
    monkeypatch.setattr(samples,'integrate',lambda *a,**k:pytest.fail('static query must not integrate'))
    monkeypatch.setattr(model_runs,'present_run',lambda *a,**k:pytest.fail('no recorded motion exists'))
    result=apply(tmp_path,setup,view=True)
    assert result['status']=='presentation_unavailable' and result['calculation']['execution_complete']


@pytest.mark.parametrize('options', [{'view':True,'render':True}, {'sample_index':-1},
                                     {'sample_index':1}, {'render':True,'sample_index':99},
                                     {'render':True,'sample_index':True}])
def test_bad_presentation_arguments_do_not_consume_revision(tmp_path,options):
    setup=prepared(tmp_path);before=files(setup[0].path)
    with pytest.raises(ValueError):apply(tmp_path,setup,**options)
    assert files(setup[0].path)==before and not (tmp_path/'attempt').exists()


def test_portable_helper_store_is_not_silently_upgraded(tmp_path):
    setup=prepared(tmp_path);portable=tmp_path/'portable';portable.mkdir()
    with pytest.raises(ValueError,match='explicit import'):
        workflow.apply_revision(setup[3],store_path=portable,using=setup[2],output=tmp_path/'attempt')
    assert not (tmp_path/'attempt').exists() and not list(portable.iterdir())


def test_cli_dispatch_and_success_exit_code(tmp_path,capsys):
    setup=prepared(tmp_path)
    assert cli.main(['model','apply',str(setup[3]),'--store',str(setup[0].path),
        '--using',str(setup[2]),'--output',str(tmp_path/'attempt')])==0
    assert json.loads(capsys.readouterr().out)['status']=='complete'
    assert cli.main(['model','reference','root','--store',str(setup[0].path)])==0
    assert json.loads(capsys.readouterr().out)==setup[1]
    # Existing command stays unchanged.
    assert cli.main(['validate',str(tmp_path/'store.source.json')])==0
    assert json.loads(capsys.readouterr().out)['valid_schema']


def test_cli_nonzero_status_for_rejection_and_input_error(tmp_path,capsys):
    setup=prepared(tmp_path);data=decode(setup[3].read_bytes());data['expected_value']=-999;write(setup[3],data)
    args=['model','apply',str(setup[3]),'--store',str(setup[0].path),'--using',str(setup[2]),'--output',str(tmp_path/'attempt')]
    assert cli.main(args)==1
    assert json.loads(capsys.readouterr().out)['status']=='rejected'
    assert cli.main(args)==2
    assert 'new directory' in capsys.readouterr().err


def test_headless_native_help_does_not_import_pyvista():
    code="from emfeeld import cli; import sys\ntry: cli.main(['model','--help'])\nexcept SystemExit as e: assert e.code==0\nassert 'pyvista' not in sys.modules"
    subprocess.run([sys.executable,'-c',code],check=True,timeout=15)


def test_module_entrypoint(tmp_path):
    setup=prepared(tmp_path)
    result=subprocess.run([sys.executable,'-m','emfeeld','model','apply',str(setup[3]),
        '--store',str(setup[0].path),'--using',str(setup[2]),'--output',str(tmp_path/'attempt')],
        text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='complete'
