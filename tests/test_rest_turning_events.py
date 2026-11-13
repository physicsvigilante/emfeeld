"""Opt-in later extrema from real rest, with no initial-state or time nudge."""
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
from numpy.testing import assert_allclose
import pytest

from emfeeld.fields import G, K
from emfeeld.observations import run_packet, packet_from_dict

ROOT = Path(__file__).resolve().parents[1]


def packet(kind='gravity', extremum='minimum'):
    # Both sphere interiors together give a=-(x-[2,0,0]); x=2+cos(t).
    strength = 500/G if kind == 'gravity' else -500/K
    source_key = 'mass_kg' if kind == 'gravity' else 'charge_C'
    field_key = 'field_m_s2' if kind == 'gravity' else 'field_N_C'
    return {'observation_schema_version':1,
        'scene':{'schema_version':1,'title':'rest launch; offset observation centre','kind':kind,
            'sources':[{'type':'solid_sphere',source_key:float(strength),'radius_m':10.,
                        'center_m':[x,0,0]} for x in (1.,3.)]
                      +[{'type':'uniform',field_key:[0,0,0]}],
            'particles':[{'mass_kg':1.,'charge_C':1.,'position_m':[3.,0.,0.],
                          'velocity_m_s':[0.,0.,0.]}],
            'duration_s':7.,'samples':2,'bounds_m':[-10,10,-10,10,-10,10]},
        'observations':[{'id':'later','type':'trajectory_event','particle_index':0,
            'condition':{'type':'radial_turning','center_m':[0.,0.,0.],'extremum':extremum},
            'initial_policy':'exclude_rest_launch',
            'occurrence':'first','max_step_s':0.05,'min_distance_m':1e-8,
            'min_radial_acceleration_m_s2':1e-8,
            'accuracy':{'time_atol_s':1e-7,'position_atol_m':1e-7,'velocity_atol_m_s':1e-7,
                        'radial_speed_atol_m_s':1e-8,'rtol':1e-8}}]}


def result(p): return run_packet(p)['results'][0]


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('extremum',['minimum','maximum','either'])
def test_harmonic_later_extremum_from_unchanged_rest(kind,extremum):
    p=packet(kind,extremum); before=deepcopy(p); r=result(p)
    assert r['status']=='ok',r
    maximum=extremum=='maximum'
    assert r['extremum']==('maximum' if maximum else 'minimum')
    s=r['state']; assert_allclose(s['time_s'],2*math.pi if maximum else math.pi,atol=1e-8,rtol=0)
    assert_allclose(s['distance_m'],3 if maximum else 1,atol=1e-9,rtol=0)
    assert_allclose(s['speed_m_s'],0,atol=1e-10,rtol=0)
    assert before==p
    assert r['diagnostics']['refinement']['passed'] and len(r['diagnostics']['passes'])==2
    for record in r['diagnostics']['passes']:
        launch=record['launch_exclusion']
        assert launch['time_s']==0 and launch['velocity_m_s']==[0,0,0]
        assert launch['position_m']==[3,0,0]
        assert_allclose(launch['radial_acceleration_m_s2'],-1,atol=1e-13)
    assert run_packet(p)['rest_launch_turning_contract']==1


def test_legacy_request_keeps_rejection():
    p=packet(); p['observations'][0].pop('initial_policy')
    assert result(p)['status']=='initial_condition_error'
    assert 'rest_launch_turning_contract' not in run_packet(p)


@pytest.mark.parametrize('velocity',[[1e-15,0,0],[0,1e-15,0],[0,1,0],[1,2,3]])
def test_nonzero_velocity_is_not_relabelled_rest(velocity):
    p=packet(); p['scene']['particles'][0]['velocity_m_s']=velocity
    r=result(p); assert r['status']=='initial_condition_error'
    assert r['error']['code']=='exact_rest_required'


@pytest.mark.parametrize('value',[None,True,1,'skip','reject',{},[]])
def test_invalid_policy_rejected_before_physics(value):
    p=packet(); p['observations'][0]['initial_policy']=value
    with pytest.raises(ValueError): packet_from_dict(p)


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_rest_uniform_acceleration_no_later_extremum(kind):
    p=packet(kind); key='field_m_s2' if kind=='gravity' else 'field_N_C'
    p['scene']['sources']=[{'type':'uniform',key:[1,0,0]}]
    r=result(p); assert r['status']=='no_event' and r['state'] is None


@pytest.mark.parametrize('field',[[0,0,0],[0,1,0],[1e-10,0,0]])
def test_equilibrium_transverse_or_unresolved_departure_rejected(field):
    p=packet();p['scene']['sources']=[{'type':'uniform','field_m_s2':field}]
    r=result(p);assert r['status']=='initial_condition_error'
    assert r['error']['code']=='rest_departure_unresolved'


@pytest.mark.parametrize('center',[[3,0,0],[3+1e-10,0,0]])
def test_initial_observation_centre_rejected(center):
    p=packet();p['observations'][0]['condition']['center_m']=center
    assert result(p)['status']=='initial_condition_error'


@pytest.mark.parametrize('extremum',['minimum','either'])
def test_detected_centre_root_is_not_smooth_minimum(extremum):
    p=packet(extremum=extremum)
    p['observations'][0]['condition']['center_m']=[2,0,0]
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


def test_later_maximum_across_defined_field_observation_centre():
    p=packet(extremum='maximum');p['observations'][0]['condition']['center_m']=[2,0,0]
    r=result(p); assert r['status']=='ok',r
    assert_allclose(r['state']['time_s'],math.pi,atol=1e-8)
    assert_allclose(r['state']['distance_m'],1,atol=1e-9)


@pytest.mark.parametrize('seed',range(4))
def test_rotation_translation_covariance(seed):
    p=packet();rng=np.random.default_rng(seed)
    rotation,_=np.linalg.qr(rng.normal(size=(3,3))); shift=rng.uniform(-3,3,3)
    for source in p['scene']['sources']:
        if source['type']=='solid_sphere':
            source['center_m']=(rotation@source['center_m']+shift).tolist()
    p['scene']['particles'][0]['position_m']=(rotation@np.array([3,0,0])+shift).tolist()
    p['observations'][0]['condition']['center_m']=shift.tolist()
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],math.pi,atol=1e-8)
    assert_allclose(r['state']['position_m'],rotation@np.array([1,0,0])+shift,atol=1e-8)


def test_historical_control_and_longer_horizon_are_explicit():
    original=json.loads((ROOT/'pilots/authorability_v2/controls/L01-rest-turning.json').read_text())
    before=deepcopy(original)
    assert result(original)['status']=='initial_condition_error'
    short=deepcopy(original);short['observations'][0]['initial_policy']='exclude_rest_launch'
    assert result(short)['status']=='no_event'
    long=deepcopy(short);long['scene']['duration_s']=70
    r=result(long);assert r['status']=='ok',r
    assert_allclose(r['state']['time_s'],54.64027838771211,atol=1e-5,rtol=0)
    assert_allclose(r['state']['position_m'],[0,-math.sqrt(3),0],atol=1e-7,rtol=0)
    assert original==before
    assert long['scene']['particles']==original['scene']['particles']
    assert long['scene']['sources']==original['scene']['sources']


def test_sample_count_does_not_set_event_time():
    p=packet();s=result(p)['state'];p['scene']['samples']=1001
    assert result(p)['state']==s


def test_invalid_request_validation_does_not_integrate(monkeypatch):
    from emfeeld import rest_turning_events
    monkeypatch.setattr(rest_turning_events,'solve_ivp',lambda *a,**k:pytest.fail('unexpected solve'))
    p=packet();p['observations'].append(dict(p['observations'][0],id='bad',min_distance_m=-1))
    with pytest.raises(ValueError):run_packet(p)


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('extremum',['minimum','maximum','either'])
def test_launch_is_initial_minimum_not_counted(kind,extremum):
    p=packet(kind,extremum);p['scene']['particles'][0]['position_m']=[1,0,0]
    r=result(p);assert r['status']=='ok',r
    minimum=extremum=='minimum'
    assert r['extremum']==('minimum' if minimum else 'maximum')
    assert_allclose(r['state']['time_s'],2*math.pi if minimum else math.pi,atol=1e-8)
    assert_allclose(r['state']['distance_m'],1 if minimum else 3,atol=1e-9)


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_later_radial_minimum_from_rest_need_not_be_a_stop(kind):
    p=packet(kind);key='field_m_s2' if kind=='gravity' else 'field_N_C'
    p['scene']['sources']=[{'type':'uniform',key:[1,0,0]}]
    p['scene']['particles'][0]['position_m']=[-2,1,0]
    r=result(p);assert r['status']=='ok',r
    for name,value in [('time_s',2),('distance_m',1),('speed_m_s',2),('radial_acceleration_m_s2',4)]:
        assert_allclose(r['state'][name],value,atol=1e-11,rtol=0)
    assert_allclose(r['state']['position_m'],[0,1,0],atol=1e-11)
    assert_allclose(r['state']['velocity_m_s'],[2,0,0],atol=1e-11)


def test_gravitational_test_mass_changes_energy_not_motion():
    p=packet();p['scene']['particles'].append(deepcopy(p['scene']['particles'][0]))
    p['scene']['particles'][1]['mass_kg']=3
    p['observations'].append(dict(p['observations'][0],id='heavy',particle_index=1))
    a,b=run_packet(p)['results'];assert a['status']==b['status']=='ok'
    for k in ('time_s','position_m','velocity_m_s','distance_m'):
        assert a['state'][k]==b['state'][k]
    assert_allclose(b['state']['potential_J'],3*a['state']['potential_J'],atol=1e-12)


def test_electric_motion_uses_charge_over_mass():
    p=packet('electric');p['scene']['particles'][0]['mass_kg']=4
    p['scene']['duration_s']=13
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],2*math.pi,atol=1e-8)


@pytest.mark.parametrize('extremum',['minimum','maximum'])
def test_event_state_with_larger_cap_refines_without_nudging(extremum):
    p=packet(extremum=extremum);p['observations'][0]['max_step_s']=0.35
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],math.pi if extremum=='minimum' else 2*math.pi,atol=1e-8)
    assert r['diagnostics']['integration_attempts']==2


def test_native_solver_receives_exact_launch_and_no_warmup(monkeypatch):
    from emfeeld import rest_turning_events
    solve=rest_turning_events.solve_ivp;calls=[];values=[]
    def checked(rhs,span,y0,**kwargs):
        calls.append((span,y0.copy(),kwargs))
        assert span==(0.,7.) and np.array_equal(y0,[3,0,0,0,0,0])
        event=kwargs['events'];assert event.terminal is True and event.direction==1
        assert_allclose(event(0.,y0),-1,atol=1e-13)
        t=1e-6;exact=np.array([2+math.cos(t),0,0,-math.sin(t),0,0])
        values.append(event(t,exact))
        assert 't_eval' not in kwargs
        return solve(rhs,span,y0,**kwargs)
    monkeypatch.setattr(rest_turning_events,'solve_ivp',checked)
    p=packet();p['observations'].append(dict(p['observations'][0],id='duplicate'))
    rows=run_packet(p)['results'];assert len(calls)==2 and rows[0]['state']==rows[1]['state']
    assert calls[1][2]['max_step']==calls[0][2]['max_step']/2
    assert calls[1][2]['rtol']==calls[0][2]['rtol']/10
    assert_allclose(values,[-1,-1],atol=1e-11)
    rows[0]['state']['position_m'][0]=123;assert rows[1]['state']['position_m'][0]!=123


def test_cache_distinguishes_new_policy_from_legacy_and_is_packet_local(monkeypatch):
    from emfeeld import rest_turning_events,turning_events
    solve=rest_turning_events.solve_ivp;calls=[]
    def counted(*a,**k):calls.append(1);return solve(*a,**k)
    monkeypatch.setattr(rest_turning_events,'solve_ivp',counted)
    monkeypatch.setattr(turning_events,'solve_ivp',lambda *a,**k:pytest.fail('legacy must reject before solve'))
    p=packet();old=deepcopy(p['observations'][0]);old.pop('initial_policy');old['id']='old'
    p['observations'].insert(0,old)
    rows=run_packet(p)['results'];assert [r['status'] for r in rows]==['initial_condition_error','ok']
    assert len(calls)==2;run_packet(packet());assert len(calls)==4


@pytest.mark.parametrize('variant',['center','extremum','particle','step','acceleration','distance','tolerance'])
def test_unique_request_cache_keys(variant,monkeypatch):
    from emfeeld import rest_turning_events
    original=rest_turning_events.solve_ivp;calls=[]
    def counted(*a,**k):calls.append(1);return original(*a,**k)
    monkeypatch.setattr(rest_turning_events,'solve_ivp',counted)
    p=packet();p['scene']['particles'].append(deepcopy(p['scene']['particles'][0]))
    r=deepcopy(p['observations'][0]);r['id']='other'
    if variant=='center':r['condition']['center_m']=[0,1,0]
    if variant=='extremum':r['condition']['extremum']='maximum'
    if variant=='particle':r['particle_index']=1
    if variant=='step':r['max_step_s']=0.1
    if variant=='acceleration':r['min_radial_acceleration_m_s2']=1e-7
    if variant=='distance':r['min_distance_m']=1e-7
    if variant=='tolerance':r['accuracy']['time_atol_s']=2e-7
    p['observations'].append(r)
    assert all(r['status']=='ok' for r in run_packet(p)['results'])
    assert len(calls)==4


def test_invalid_rest_launch_does_not_discard_other_measurements():
    p=packet();p['scene']['particles'].append(deepcopy(p['scene']['particles'][0]))
    p['scene']['particles'][0]['velocity_m_s']=[1e-12,0,0]
    p['observations'] += [dict(p['observations'][0],id='valid',particle_index=1),
        {'id':'v0','type':'trajectory_sample','particle_index':1,'sample_index':0,'quantity':'speed'},
        {'id':'probe','type':'potential','position_m':[3,0,0]}]
    report=run_packet(p);assert report['status']=='partial'
    assert [r['status'] for r in report['results']]==['initial_condition_error','ok','ok','ok']
    assert report['results'][2]['value']==0


@pytest.mark.parametrize('source',[{'type':'shell','mass_kg':1,'radius_m':1},
                                   {'type':'plane','mass_per_m2_kg_m2':1}])
def test_physical_discontinuous_sources_stay_rejected(source):
    p=packet();p['scene']['sources']=[source]
    assert result(p)['status']=='unsupported_trajectory'


def test_singular_launch_is_not_a_measurement_centre_transit():
    p=packet();p['scene']['sources']=[{'type':'point','mass_kg':1,'center_m':[3,0,0]}]
    assert result(p)['status']=='domain_error'


def test_initial_small_coordinate_accuracy_is_explicit_failure():
    p=packet();p['observations'][0]['accuracy']['position_atol_m']=1e-25
    r=result(p);assert r['status']=='initial_condition_error'
    assert r['error']['code']=='rest_launch_geometry_unresolved'


def test_positive_root_with_unresolved_time_is_rejected_not_skipped():
    p=packet();p['observations'][0]['accuracy']['time_atol_s']=4
    r=result(p);assert r['status']=='ambiguous_event'
    assert r['error']['code']=='event_time_unresolved_from_launch'


@pytest.mark.parametrize('fault',['presence','time','position','velocity','residual','flat','classification'])
def test_bad_refinements_are_not_accepted_or_retried(monkeypatch,fault):
    from emfeeld import rest_turning_events
    original=rest_turning_events._search;calls=[]
    def changed(scene,request,refined):
        calls.append(refined);r=original(scene,request,refined)
        if refined:
            if fault=='presence':r['status']='no_event'
            if fault=='time':r['state']['time_s']+=0.1
            if fault=='position':r['state']['position_m'][0]+=1
            if fault=='velocity':r['state']['velocity_m_s'][0]+=1
            if fault=='residual':r['radial_speed_m_s']=1
            if fault=='flat':r['radial_acceleration_m_s2']=0
            if fault=='classification':r['extremum']='maximum'
        return r
    monkeypatch.setattr(rest_turning_events,'_search',changed)
    r=result(packet());assert r['status'] in ('ambiguous_event','convergence_error')
    assert r['state'] is None and calls==[False,True]


@pytest.mark.parametrize('exception',[ValueError('f(a) and f(b) must have different signs'),
                                      RuntimeError('Failed to converge after 100 iterations.')])
def test_root_finder_failures_preserve_local_failure(monkeypatch,exception):
    from emfeeld import rest_turning_events
    def fail(*a,**k):raise exception
    monkeypatch.setattr(rest_turning_events,'solve_ivp',fail)
    r=result(packet());assert r['status']=='numerical_error' and r['state'] is None


def test_programming_errors_are_not_silenced(monkeypatch):
    from emfeeld import rest_turning_events
    def fail(*a,**k):raise RuntimeError('test programming bug')
    monkeypatch.setattr(rest_turning_events,'solve_ivp',fail)
    with pytest.raises(RuntimeError,match='programming bug'):run_packet(packet())


def test_failed_solve_is_not_no_event_and_is_cached(monkeypatch):
    from emfeeld import rest_turning_events
    from types import SimpleNamespace
    calls=[]
    def fail(*a,**k):calls.append(1);return SimpleNamespace(success=False,message='synthetic failure')
    monkeypatch.setattr(rest_turning_events,'solve_ivp',fail)
    p=packet();p['observations'].append(dict(p['observations'][0],id='duplicate'))
    rows=run_packet(p)['results'];assert all(r['status']=='integration_error' for r in rows)
    assert len(calls)==1


def test_time_predicate_finite_checks_and_initialisation():
    from emfeeld.rest_turning_events import RestTurningCondition
    scene,requests=packet_from_dict(packet());c=RestTurningCondition(requests[0],scene.model,scene.particles[0])
    with pytest.raises(RuntimeError):c.event_value_at_time(1,[3,0,0,0,0,0])
    c.validate_initial([3,0,0,0,0,0])
    for t in (float('nan'),float('inf'),-1):
        with pytest.raises(FloatingPointError):c.event_value_at_time(t,[3,0,0,0,0,0])
    with pytest.raises(FloatingPointError):c.event_value_at_time(1,[3,0,0])
    with pytest.raises(FloatingPointError):c.event_value_at_time(1,[3,0,0,float('inf'),0,0])


def test_rest_policy_not_accepted_for_static_or_other_event_types():
    p=packet();p['observations']=[{'id':'bad','type':'potential','position_m':[1,0,0],
                                 'initial_policy':'exclude_rest_launch'}]
    with pytest.raises(ValueError):packet_from_dict(p)
    p=packet();p['observations'][0]['condition']={'type':'plane','point_m':[0,0,0],
                                                'normal':[1,0,0],'direction':'either'}
    with pytest.raises(ValueError):packet_from_dict(p)


def test_cli_packet_round_trip(tmp_path,capsys):
    from emfeeld.observations import main
    p=tmp_path/'packet.json';p.write_text(json.dumps(packet()));out=tmp_path/'result.json'
    assert main([str(p),'--validate-only'])==0;assert json.loads(capsys.readouterr().out)['valid_schema']
    assert main([str(p),'--output',str(out)])==0
    assert json.loads(capsys.readouterr().out)==json.loads(out.read_text())


def test_headless_observation_import_does_not_load_viewer():
    import subprocess,sys,os
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
    p=subprocess.run([sys.executable,'-c',
        'import sys; from emfeeld.observations import run_packet; assert "pyvista" not in sys.modules; assert "emfeeld.viewer" not in sys.modules'],
        capture_output=True,text=True,env=env)
    assert p.returncode==0,p.stderr


EXAMPLES=ROOT/'examples/rest_turning'
@pytest.mark.parametrize('entry',json.loads((EXAMPLES/'manifest.json').read_text())['packets'],ids=lambda e:e['file'])
def test_authored_rest_launch_packets(entry):
    report=run_packet(json.loads((EXAMPLES/entry['file']).read_text()))
    assert (0 if report['status']=='ok' else 1)==entry['cli_exit']
    assert len(report['results'])==len(entry['expected_results'])
    for r,e in zip(report['results'],entry['expected_results']):
        assert (r['id'],r['status'])==(e['id'],e['status'])
        for key,value in e.get('state',{}).items():
            assert_allclose(r['state'][key],value,atol=e.get('atols',{}).get(key,e['atol']),rtol=e['rtol'])
        if 'value' in e:assert_allclose(r['value'],e['value'],atol=1e-10,rtol=1e-10)
        if 'unit' in e:assert r['unit']==e['unit']
