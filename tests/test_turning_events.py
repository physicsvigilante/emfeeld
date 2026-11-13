"""Local radial extrema: data authoring, separate references and honest failures."""
from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
from numpy.testing import assert_allclose
import pytest

from emfeeld.fields import G, K
from emfeeld.observations import run_packet, packet_from_dict, main


def packet(kind='gravity', extremum='minimum'):
    return {'observation_schema_version':1,
        'scene':{'schema_version':1,'title':'radial turning','kind':kind,
            'sources':[{'type':'uniform','field_m_s2' if kind=='gravity' else 'field_N_C':[0,0,0]}],
            'particles':[{'mass_kg':1,'charge_C':1,'position_m':[-2,1,0],'velocity_m_s':[1,0,0]}],
            'duration_s':5,'samples':2,'bounds_m':[-4,4,-4,4,-4,4]},
        'observations':[{'id':'turn','type':'trajectory_event','particle_index':0,
            'condition':{'type':'radial_turning','center_m':[0,0,0],'extremum':extremum},
            'occurrence':'first','max_step_s':0.05,'min_distance_m':1e-8,
            'min_radial_acceleration_m_s2':1e-8,
            'accuracy':{'time_atol_s':1e-7,'position_atol_m':1e-7,'velocity_atol_m_s':1e-7,
                        'radial_speed_atol_m_s':1e-8,'rtol':1e-8}}]}


def result(p): return run_packet(p)['results'][0]


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('extremum',['minimum','either'])
def test_free_flyby_minimum_is_not_a_stop(kind,extremum):
    p=packet(kind,extremum);r=result(p);assert r['status']=='ok'
    assert r['extremum']=='minimum'
    s=r['state'];assert_allclose(s['time_s'],2,atol=1e-12,rtol=0)
    assert_allclose(s['position_m'],[0,1,0],atol=1e-12)
    assert_allclose(s['velocity_m_s'],[1,0,0],atol=1e-12)
    assert_allclose([s['distance_m'],s['speed_m_s'],s['radial_acceleration_m_s2']],[1,1,1],atol=1e-12)
    assert abs(s['radial_speed_m_s'])<1e-12 and r['error_bound'] is None
    assert r['units']['distance_m']=='m'
    assert s['time_s'] not in np.linspace(0,5,2)
    p['scene']['samples']=301;assert result(p)['state']==s


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('extremum,sign,dist',[('minimum',1,1.5),('maximum',-1,2.5)])
def test_uniform_force_radial_reversal(kind,extremum,sign,dist):
    p=packet(kind,extremum);p['scene']['sources'][0]['field_m_s2' if kind=='gravity' else 'field_N_C']=[sign,0,0]
    p['scene']['particles'][0].update(position_m=[2,0,0],velocity_m_s=[-sign,0,0])
    r=result(p);assert r['status']=='ok' and r['extremum']==extremum
    assert_allclose(r['state']['time_s'],1,atol=1e-12)
    assert_allclose(r['state']['distance_m'],dist,atol=1e-12)
    assert_allclose(r['state']['speed_m_s'],0,atol=1e-12)
    assert_allclose(r['state']['radial_acceleration_m_s2'],sign,atol=1e-12)


@pytest.mark.parametrize('seed',range(5))
def test_free_geometry_translation_rotation_and_center(seed):
    p=packet();rng=np.random.default_rng(seed)
    center=rng.uniform(-10,10,3);u=rng.normal(size=3);u/=np.linalg.norm(u)
    v=rng.normal(size=3);v-=np.dot(v,u)*u;v/=np.linalg.norm(v)
    p['scene']['particles'][0].update(position_m=(center-2*u+0.7*v).tolist(),velocity_m_s=(1.3*u).tolist())
    p['observations'][0]['condition']['center_m']=center.tolist()
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],2/1.3,atol=1e-11)
    assert_allclose(r['state']['position_m'],center+0.7*v,atol=1e-11)
    assert_allclose(r['state']['radial_acceleration_m_s2'],1.3**2/0.7,atol=1e-11)


def orbit_packet(kind='gravity', extremum='minimum'):
    p=packet(kind,extremum);key='charge_C' if kind=='electric' else 'mass_kg'
    p['scene']['sources']=[{'type':'point',key:1/K if kind=='electric' else 1/G}]
    p['scene']['particles'][0].update(charge_C=-1,position_m=[-1,-np.sqrt(3),0],velocity_m_s=[1/np.sqrt(2),0,0])
    p['scene']['duration_s']=35
    rotation=np.array([[1.,2.,2.],[-2.,2.,-1.],[-2.,-1.,2.]])/3
    for k in ('position_m','velocity_m_s'):
        p['scene']['particles'][0][k]=(rotation@p['scene']['particles'][0][k]).tolist()
    return p,rotation


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('extremum',['minimum','maximum','either'])
def test_inclined_kepler_extrema(kind,extremum):
    p,rot=orbit_packet(kind,extremum);r=result(p);assert r['status']=='ok'
    maximum=extremum=='maximum';E=3*np.pi if maximum else 2*np.pi;n=1/np.sqrt(8)
    time=(E-(3*np.pi/2+0.5))/n
    distance=3 if maximum else 1
    velocity=[0,-np.sqrt(1/6),0] if maximum else [0,np.sqrt(1.5),0]
    position=[-3,0,0] if maximum else [1,0,0]
    assert_allclose(r['state']['time_s'],time,atol=1e-8)
    assert_allclose(r['state']['distance_m'],distance,atol=1e-9)
    assert_allclose(r['state']['position_m'],rot@position,atol=1e-8)
    assert_allclose(r['state']['velocity_m_s'],rot@velocity,atol=1e-8)
    assert_allclose(r['state']['total_energy_J'],-0.25,atol=1e-10)
    assert_allclose(r['state']['radial_acceleration_m_s2'],-1/18 if maximum else 0.5,atol=1e-9)


def test_repulsive_point_true_stop():
    p=packet('electric');p['scene']['sources']=[{'type':'point','charge_C':1/K}]
    p['scene']['particles'][0].update(position_m=[2,0,0],velocity_m_s=[-1,0,0])
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],1+np.arcsinh(1)/np.sqrt(2),atol=1e-9)
    assert_allclose(r['state']['distance_m'],1,atol=1e-9)
    assert_allclose(r['state']['speed_m_s'],0,atol=1e-10)


def test_penetration_turns_inside_solid_sphere():
    from scipy.integrate import quad
    p=packet('electric');p['scene']['sources']=[{'type':'solid_sphere','radius_m':1,'charge_C':1/K}]
    p['scene']['particles'][0].update(position_m=[2,0,0],velocity_m_s=[-float(np.sqrt(1.75)),0,0])
    r=result(p);assert r['status']=='ok'
    expected=quad(lambda x:1/np.sqrt(2.75-2/x),1,2,epsabs=1e-12)[0]+np.arctanh(np.sqrt(0.75))
    assert_allclose(r['state']['time_s'],expected,atol=5e-8)
    assert_allclose(r['state']['distance_m'],0.5,atol=5e-8)
    assert_allclose(r['state']['total_energy_J'],1.375,atol=5e-8)


@pytest.mark.parametrize('kind',['gravity','electric'])
@pytest.mark.parametrize('extremum',['minimum','maximum'])
def test_unfamiliar_overlap_and_uniform_field(kind,extremum):
    p=packet(kind,extremum);key='mass_kg' if kind=='gravity' else 'charge_C'
    strength=500/G if kind=='gravity' else -500/K
    p['scene']['sources']=[{'type':'solid_sphere',key:strength,'radius_m':10,'center_m':[x,0,0]} for x in (-1,1)]
    p['scene']['sources'].append({'type':'uniform','field_m_s2' if kind=='gravity' else 'field_N_C':[0,0.25,0]})
    theta=np.pi/4;c=np.array([0.,0.25,0]);position=c+[2*np.cos(theta),np.sin(theta),0]
    velocity=[-2*np.sin(theta),np.cos(theta),0]
    p['scene']['particles'][0].update(position_m=position.tolist(),velocity_m_s=np.asarray(velocity).tolist())
    p['scene']['duration_s']=25;p['observations'][0]['condition']['center_m']=c.tolist()
    r=result(p);assert r['status']=='ok';maximum=extremum=='maximum'
    assert_allclose(r['state']['time_s'],3*np.pi/4 if maximum else np.pi/4,atol=1e-9)
    assert_allclose(r['state']['distance_m'],2 if maximum else 1,atol=1e-9)
    assert_allclose(r['state']['speed_m_s'],1 if maximum else 2,atol=1e-9)


@pytest.mark.parametrize('position,velocity',[
    ([1,0,0],[0,1,0]), ([1,0,0],[0,0,0]),([1,0,0],[1e-12,1,0]),([0,0,0],[1,0,0])])
def test_stationary_or_center_launch_is_explicit(position,velocity):
    p=packet();p['scene']['particles'][0].update(position_m=position,velocity_m_s=np.asarray(velocity).tolist())
    r=result(p);assert r['status']=='initial_condition_error' and r['state'] is None
    assert r['diagnostics']['integration_attempts']==0


def test_passage_through_center_is_not_a_smooth_turning_point():
    p=packet();p['scene']['particles'][0]['position_m']=[-2,0,0]
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


def test_distance_resolution_rejection():
    p=packet();p['observations'][0]['min_distance_m']=1.1
    r=result(p);assert r['status']=='ambiguous_event'


def test_flat_turn_is_not_certified():
    p=packet();p['observations'][0]['min_radial_acceleration_m_s2']=2
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


def test_absence_and_wrong_kind():
    p=packet(extremum='maximum');r=run_packet(p)
    assert r['status']=='ok' and r['counts']['no_events']==1
    assert r['results'][0]['state'] is None


@pytest.mark.parametrize('mutate',[
    lambda r:r['condition'].update(type='turning'),lambda r:r['condition'].update(extremum='global_minimum'),
    lambda r:r['condition'].update(extremum=[]),lambda r:r['condition'].update(radius_m=1),
    lambda r:r['condition'].update(direction='inward'),lambda r:r['condition'].update(center_m=[0,0]),
    lambda r:r['condition'].update(center_m=[True,0,0]),lambda r:r['condition'].pop('extremum'),
    lambda r:r.update(min_distance_m=0),lambda r:r.update(min_distance_m=-1),
    lambda r:r.update(min_distance_m=True),lambda r:r.update(min_distance_m='1'),
    lambda r:r.update(min_distance_m=float('nan')),lambda r:r.pop('min_distance_m'),
    lambda r:r.update(min_radial_acceleration_m_s2=0),lambda r:r.update(min_radial_acceleration_m_s2=True),
    lambda r:r.update(min_radial_acceleration_m_s2=float('inf')),lambda r:r.pop('min_radial_acceleration_m_s2'),
    lambda r:r.update(min_radial_speed_m_s=1e-6),lambda r:r.update(occurrence='last'),
    lambda r:r.update(particle_index=True),lambda r:r.update(particle_index=-1),
    lambda r:r.update(particle_index=1),lambda r:r.update(max_step_s=1e-8),
    lambda r:r.update(max_step_s=6),lambda r:r.update(max_step_s=0),
    lambda r:r['accuracy'].update(radial_speed_atol_m_s=0),lambda r:r['accuracy'].pop('radial_speed_atol_m_s'),
    lambda r:r['accuracy'].update(rtol=-1),lambda r:r['accuracy'].update(time_atol_s='1'),
    lambda r:r['accuracy'].update(velocity_atol_m_s=False),lambda r:r['accuracy'].update(position_atol_m=float('inf')),
])
def test_strict_turning_request(mutate):
    p=packet();mutate(p['observations'][0])
    with pytest.raises(ValueError):packet_from_dict(p)


def test_cli_roundtrip(tmp_path,capsys):
    p=tmp_path/'p.json';o=tmp_path/'r.json';p.write_text(json.dumps(packet()))
    assert main([str(p),'--validate-only'])==0;assert json.loads(capsys.readouterr().out)['valid_schema']
    assert main([str(p),'--output',str(o)])==0
    assert json.loads(capsys.readouterr().out)==json.loads(o.read_text())


def test_actual_degenerate_quartic_minimum_is_not_accepted():
    p=packet();p['scene']['sources'][0]['field_m_s2']=[0,-1,0]
    p['scene']['particles'][0].update(position_m=[-1,0.5,0],velocity_m_s=[1,1,0])
    # r^2 = 1 + (t-1)^4/4, hence r''(1)=0, despite nonzero total speed.
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


def test_first_local_minimum_is_not_claimed_global():
    p=packet();p['scene']['sources'][0]['field_m_s2']=[0,2,0]
    p['scene']['particles'][0].update(position_m=[-3,6.1,0],velocity_m_s=[1,-5.7,0])
    p['scene']['duration_s']=6
    roots=np.sort(np.roots([2,0.9,-2.91,-0.6]))
    distances=np.hypot(roots, roots**2+0.3*roots-2)
    r=result(p);assert r['status']=='ok' and distances[0]>distances[-1]
    assert_allclose(r['state']['time_s'],3+roots[0],atol=1e-10)
    assert_allclose(r['state']['distance_m'],distances[0],atol=1e-10)


def test_horizon_near_stationarity_without_root_is_ambiguous():
    p=packet();p['scene']['duration_s']=2-1e-10
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


@pytest.mark.parametrize('key',['position_atol_m','radial_speed_atol_m_s'])
def test_unattainable_roundoff_resolution(key):
    p=packet();p['observations'][0]['accuracy'][key]=1e-25
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


def test_large_coordinate_geometry_unresolved():
    p=packet();p['scene']['particles'][0]['position_m']=[1e16+2,0,0]
    p['observations'][0]['condition']['center_m']=[1e16,0,0]
    assert result(p)['status']=='initial_condition_error'


@pytest.mark.parametrize('source',[{'type':'shell','mass_kg':1,'radius_m':1},
                                  {'type':'plane','mass_per_m2_kg_m2':1}])
def test_unsupported_source_dynamics_remain_rejected(source):
    p=packet();p['scene']['sources']=[source]
    p['observations'].append({'id':'probe','type':'potential','position_m':[2,0,0]})
    rows=run_packet(p)['results'];assert [r['status'] for r in rows]==['unsupported_trajectory','ok']


def test_singular_particle_failure_does_not_discard_another_particle():
    p,_=orbit_packet();p['scene']['particles'].append(deepcopy(p['scene']['particles'][0]))
    p['scene']['particles'][0]['position_m']=[0,0,0]
    other=deepcopy(p['observations'][0]);other.update(id='valid',particle_index=1)
    p['observations']+=[other,{'id':'probe','type':'potential','position_m':[1,0,0]}]
    assert [r['status'] for r in run_packet(p)['results']]==['domain_error','ok','ok']


def test_exact_duplicates_share_searches_not_mutable_results(monkeypatch):
    from emfeeld import turning_events
    calls=[];solve=turning_events.solve_ivp
    def counted(*a,**k):calls.append(k);return solve(*a,**k)
    monkeypatch.setattr(turning_events,'solve_ivp',counted)
    p=packet();p['observations'].append(dict(p['observations'][0],id='again'))
    rows=run_packet(p)['results'];assert len(calls)==2 and rows[0]['state']==rows[1]['state']
    rows[0]['state']['position_m'][0]=123;assert rows[1]['state']['position_m'][0]!=123
    assert calls[0]['events'].terminal is True and calls[0]['events'].direction==1
    assert 't_eval' not in calls[0] and calls[1]['max_step']==calls[0]['max_step']/2
    assert calls[1]['rtol']==calls[0]['rtol']/10


def test_cache_covers_settings_center_kind_particle_and_is_packet_local(monkeypatch):
    from emfeeld import turning_events
    calls=[];solve=turning_events.solve_ivp
    def counted(*a,**k):calls.append(k);return solve(*a,**k)
    monkeypatch.setattr(turning_events,'solve_ivp',counted)
    p=packet();p['scene']['particles'].append(deepcopy(p['scene']['particles'][0]))
    for i,key in enumerate(['center','extremum','particle','distance','acceleration','accuracy','step']):
        r=deepcopy(p['observations'][0]);r['id']=f'other{i}'
        if key=='center':r['condition']['center_m']=[0.1,0,0]
        if key=='extremum':r['condition']['extremum']='maximum'
        if key=='particle':r['particle_index']=1
        if key=='distance':r['min_distance_m']=1e-6
        if key=='acceleration':r['min_radial_acceleration_m_s2']=1e-7
        if key=='accuracy':r['accuracy']['radial_speed_atol_m_s']=2e-8
        if key=='step':r['max_step_s']=0.1
        p['observations'].append(r)
    assert all(r['status'] in ('ok','no_event') for r in run_packet(p)['results'])
    assert len(calls)==16;run_packet(packet());assert len(calls)==18


def test_mixed_requests_preserve_input_and_use_separate_caches(monkeypatch):
    from emfeeld import turning_events,radial_events,plane_events,trajectory_samples
    counts={k:0 for k in ('turn','radial','plane','sample')}
    for name,module,attr in [('turn',turning_events,'solve_ivp'),('radial',radial_events,'solve_ivp'),
                             ('plane',plane_events,'solve_ivp'),('sample',trajectory_samples,'integrate')]:
        original=getattr(module,attr)
        def counted(*a,_key=name,_original=original,**k):counts[_key]+=1;return _original(*a,**k)
        monkeypatch.setattr(module,attr,counted)
    p=packet();base=deepcopy(p['observations'][0]);base.pop('min_distance_m');base.pop('min_radial_acceleration_m_s2')
    base['accuracy'].pop('radial_speed_atol_m_s')
    radial=deepcopy(base);radial.update(id='radial',min_radial_speed_m_s=1e-6,
        condition={'type':'radial','center_m':[0,0,0],'radius_m':1.5,'direction':'inward'})
    plane=deepcopy(base);plane.update(id='plane',min_normal_speed_m_s=1e-6,
        condition={'type':'plane','point_m':[0,0,0],'normal':[1,0,0],'direction':'positive'})
    p['observations']+=[plane,radial,{'id':'sample','type':'trajectory_sample','particle_index':0,
        'sample_index':0,'quantity':'speed'},{'id':'probe','type':'potential','position_m':[0,0,0]}]
    before=deepcopy(p);report=run_packet(p);assert before==p
    assert all(r['status']=='ok' for r in report['results'])
    assert counts=={'turn':2,'radial':2,'plane':2,'sample':1}
    assert report['radial_turning_contract']==1
    assert [r['id'] for r in report['results']]==[r['id'] for r in p['observations']]


def test_validation_happens_before_physics(monkeypatch):
    from emfeeld import turning_events
    monkeypatch.setattr(turning_events,'solve_ivp',lambda *a,**k:pytest.fail('unexpected solve'))
    p=packet();p['observations'].append(dict(p['observations'][0],id='bad',min_distance_m=-1))
    with pytest.raises(ValueError):run_packet(p)


@pytest.mark.parametrize('fault',['presence','time','position','velocity','residual','roundoff','flat','direction','classification'])
def test_refinement_failures_do_not_return_accepted_states(monkeypatch,fault):
    from emfeeld import turning_events
    original=turning_events._search
    def damaged(scene,request,refined):
        r=original(scene,request,refined)
        if refined:
            if fault=='presence':r['status']='no_event'
            if fault=='time':r['state']['time_s']+=0.1
            if fault=='position':r['state']['position_m'][0]+=1
            if fault=='velocity':r['state']['velocity_m_s'][0]+=1
            if fault=='residual':r['radial_speed_m_s']=1
            if fault=='roundoff':r['radial_speed_roundoff_m_s']=1
            if fault=='flat':r['radial_acceleration_m_s2']=0
            if fault=='direction':r['radial_acceleration_m_s2']=-1
            if fault=='classification':r['extremum']='maximum'
        return r
    monkeypatch.setattr(turning_events,'_search',damaged)
    r=result(packet());assert r['status'] in ('ambiguous_event','convergence_error') and r['state'] is None


@pytest.mark.parametrize('exception',[ValueError('f(a) and f(b) must have different signs'),
                                      RuntimeError('Failed to converge after 100 iterations.')])
def test_known_root_failure_is_local(monkeypatch,exception):
    from emfeeld import turning_events
    def fail(*a,**k):raise exception
    monkeypatch.setattr(turning_events,'solve_ivp',fail)
    r=result(packet());assert r['status']=='numerical_error' and r['state'] is None


def test_unexpected_error_propagates(monkeypatch):
    from emfeeld import turning_events
    def fail(*a,**k):raise RuntimeError('synthetic programmer error')
    monkeypatch.setattr(turning_events,'solve_ivp',fail)
    with pytest.raises(RuntimeError,match='programmer'):run_packet(packet())


def test_solver_failure_not_no_event_and_cached(monkeypatch):
    from emfeeld import turning_events
    calls=[]
    def fail(*a,**k):calls.append(1);return SimpleNamespace(success=False,message='synthetic failure')
    monkeypatch.setattr(turning_events,'solve_ivp',fail)
    p=packet();p['observations'].append(dict(p['observations'][0],id='again'))
    assert all(r['status']=='integration_error' for r in run_packet(p)['results']) and len(calls)==1


from pathlib import Path
EXAMPLES=Path(__file__).resolve().parents[1]/'examples'/'turning_events'
@pytest.mark.parametrize('entry',json.loads((EXAMPLES/'manifest.json').read_text())['packets'],ids=lambda e:e['file'])
def test_authored_example_packets(entry):
    report=run_packet(json.loads((EXAMPLES/entry['file']).read_text()))
    assert (0 if report['status']=='ok' else 1)==entry['cli_exit']
    assert len(report['results'])==len(entry['expected_results'])
    for r,e in zip(report['results'],entry['expected_results']):
        assert (r['id'],r['status'])==(e['id'],e['status'])
        if 'extremum' in e:assert r['extremum']==e['extremum']
        for name,value in e.get('state',{}).items():
            assert_allclose(r['state'][name],value,atol=e['atol'],rtol=e['rtol'])
