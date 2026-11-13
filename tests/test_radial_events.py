"""Radial event authoring: analytic states, geometry, and explicit limitations."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from numpy.testing import assert_allclose
import pytest

from emfeeld.observations import run_packet, packet_from_dict, main
from emfeeld.fields import G, K


def packet(kind='gravity', direction='inward'):
    return {'observation_schema_version': 1,
        'scene': {'schema_version': 1, 'title': 'radial crossing', 'kind': kind,
            'sources': [{'type': 'uniform', 'field_m_s2' if kind == 'gravity' else 'field_N_C': [0,0,0]}],
            'particles': [{'mass_kg': 2, 'charge_C': -4, 'position_m': [-2,0.3,0.4], 'velocity_m_s': [1,0,0]}],
            'duration_s': 5, 'samples': 2, 'bounds_m': [-3,3,-3,3,-3,3]},
        'observations': [{'id': 'cross', 'type': 'trajectory_event', 'particle_index': 0,
            'condition': {'type':'radial', 'center_m':[0,0,0], 'radius_m':1, 'direction':direction},
            'occurrence':'first', 'max_step_s':0.05, 'min_radial_speed_m_s':1e-6,
            'accuracy': {'time_atol_s':1e-7, 'position_atol_m':1e-7, 'velocity_atol_m_s':1e-7, 'rtol':1e-7}}]}


def result(p): return run_packet(p)['results'][0]


@pytest.mark.parametrize('kind', ['electric','gravity'])
@pytest.mark.parametrize('direction,sign', [('inward',-1), ('outward',1), ('either',-1)])
def test_free_off_axis_crossing(kind, direction, sign):
    p=packet(kind,direction); r=result(p)
    assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],2+sign*np.sqrt(0.75),atol=1e-12,rtol=0)
    assert_allclose(r['state']['position_m'],[sign*np.sqrt(0.75),0.3,0.4],atol=1e-12)
    assert_allclose(r['state']['velocity_m_s'],[1,0,0],atol=1e-12)
    assert_allclose(r['state']['speed_m_s'],1,atol=1e-12)
    assert_allclose(r['state']['kinetic_J'],1,atol=1e-12)
    assert_allclose(r['diagnostics']['radial_speed_m_s'],sign*np.sqrt(0.75),atol=1e-12)
    assert abs(r['diagnostics']['signed_radial_residual_m'])<1e-12
    assert r['error_bound'] is None
    assert r['state']['time_s'] not in np.linspace(0,5,2)
    p['scene']['samples']=1001
    assert result(p)['state']==r['state']  # not frame selection


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_uniform_acceleration_and_inside_launch(kind):
    p=packet(kind,'outward'); key='field_N_C' if kind=='electric' else 'field_m_s2'
    p['scene']['sources'][0][key]=[-1,0,0] if kind=='electric' else [2,0,0]
    p['scene']['particles'][0].update(position_m=[0,0,0],velocity_m_s=[0,0,0])
    r=result(p); assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],1,atol=1e-10)
    assert_allclose(r['state']['velocity_m_s'],[2,0,0],atol=1e-10)
    assert_allclose(r['state']['total_energy_J'],0,atol=1e-10)


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('direction,expected',[('inward',np.pi/3),('outward',2*np.pi/3),('either',np.pi/3)])
def test_first_directional_crossing_repeated_harmonic_motion(kind,direction,expected):
    p=packet(kind,direction)
    p['scene']['sources']=[{'type':'solid_sphere','radius_m':1,
                          'charge_C' if kind=='electric' else 'mass_kg':-1/K if kind=='electric' else 1/G}]
    p['scene']['particles'][0].update(mass_kg=1,charge_C=1,position_m=[0.8,0,0],velocity_m_s=[0,0,0])
    p['scene']['duration_s']=20;p['observations'][0]['condition']['radius_m']=0.4
    r=result(p); assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],expected,atol=1e-10)
    assert_allclose(r['state']['speed_m_s'],0.4*np.sqrt(3),atol=1e-10)


def test_translation_rotation_covariance():
    p=packet();a=result(p)
    q=np.array([[1.,2.,2.],[-2.,2.,-1.],[-2.,-1.,2.]])/3
    shift=np.array([10.,-3.,4.])
    particle=p['scene']['particles'][0]
    particle['position_m']=(q@particle['position_m']+shift).tolist()
    particle['velocity_m_s']=(q@particle['velocity_m_s']).tolist()
    p['observations'][0]['condition']['center_m']=shift.tolist()
    b=result(p); assert b['status']=='ok'
    assert_allclose(b['state']['time_s'],a['state']['time_s'],atol=1e-11)
    assert_allclose(b['state']['position_m'],q@a['state']['position_m']+shift,atol=1e-11)
    assert_allclose(b['state']['velocity_m_s'],q@a['state']['velocity_m_s'],atol=1e-11)


def test_sphere_is_not_forced_to_share_source_center():
    p=packet();p['observations'][0]['condition']['center_m']=[1,0.3,0.4]
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],2,atol=1e-12)


@pytest.mark.parametrize('position', [[1,0,0],[0.6,0.8,0]])
def test_initial_sphere_rejected_without_search(position):
    p=packet();p['scene']['particles'][0]['position_m']=position
    r=result(p);assert r['status']=='initial_condition_error'
    assert r['state'] is None and r['diagnostics']['integration_attempts']==0


def test_large_translation_unresolved_initial_side():
    p=packet();p['observations'][0]['condition']['center_m']=[1e16,0,0]
    p['scene']['particles'][0]['position_m']=[1e16+2,0,0]
    r=result(p);assert r['status']=='initial_condition_error'


def test_no_event_is_detected_absence_not_contact_proof():
    p=packet();p['scene']['particles'][0]['position_m']=[-2,2,0]
    r=run_packet(p);assert r['status']=='ok' and r['counts']['no_events']==1
    assert r['results'][0]['status']=='no_event' and r['results'][0]['state'] is None


def test_grazing_threshold_rejects_found_root():
    p=packet();p['observations'][0]['min_radial_speed_m_s']=2
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


@pytest.mark.parametrize('mutate',[
    lambda r:r['condition'].update(radius_m=0), lambda r:r['condition'].update(radius_m=-1),
    lambda r:r['condition'].update(radius_m=True),lambda r:r['condition'].update(radius_m='1'),
    lambda r:r['condition'].update(radius_m=float('inf')),lambda r:r['condition'].update(radius_m=float('nan')),
    lambda r:r['condition'].update(center_m=[0,0]),lambda r:r['condition'].update(center_m=[False,0,0]),
    lambda r:r['condition'].update(center_m=[0,0,float('nan')]),lambda r:r['condition'].update(point_m=[0,0,0]),
    lambda r:r['condition'].update(normal=[1,0,0]),lambda r:r['condition'].update(direction='positive'),
    lambda r:r['condition'].update(direction='negative'),lambda r:r['condition'].update(direction=[]),
    lambda r:r['condition'].update(type='sphere'),lambda r:r['condition'].pop('center_m'),
    lambda r:r['condition'].pop('radius_m'),lambda r:r.update(min_radial_speed_m_s=0),
    lambda r:r.update(min_radial_speed_m_s=True),lambda r:r.update(min_radial_speed_m_s='1'),
    lambda r:r.update(min_normal_speed_m_s=1e-6),lambda r:r.pop('min_radial_speed_m_s'),
    lambda r:r.update(occurrence='second'),lambda r:r.update(particle_index=True),
    lambda r:r.update(particle_index=3),lambda r:r.update(max_step_s=0),
    lambda r:r.update(max_step_s=1e-20),lambda r:r.update(max_step_s=6),
    lambda r:r.update(max_step_s=True),lambda r:r['accuracy'].update(rtol=-1),
    lambda r:r['accuracy'].update(position_atol_m=0),lambda r:r.update(time_s=1),
    lambda r:r.update(expectation={'time_s':1}),lambda r:r.pop('accuracy'),
])
def test_strict_radial_authoring(mutate):
    p=packet();mutate(p['observations'][0])
    with pytest.raises(ValueError):packet_from_dict(p)


def test_terminal_gravity_infall_before_source_singularity():
    p=packet();p['scene']['sources']=[{'type':'point','mass_kg':1/G}]
    p['scene']['particles'][0].update(position_m=[2,0,0],velocity_m_s=[0,0,0])
    p['scene']['duration_s']=10
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],1+np.pi/2,atol=1e-9)
    assert_allclose(r['state']['speed_m_s'],1,atol=1e-10)


@pytest.mark.parametrize('source',[{'type':'shell','mass_kg':1,'radius_m':1},
                                   {'type':'plane','mass_per_m2_kg_m2':1}])
def test_radial_surface_does_not_enable_shell_or_plane_source_motion(source):
    p=packet();p['scene']['sources']=[source]
    p['observations'].append({'id':'potential','type':'potential','position_m':[0,0,0]})
    rows=run_packet(p)['results'];assert [r['status'] for r in rows]==['unsupported_trajectory','ok']


def test_cli_roundtrip(tmp_path,capsys):
    p=tmp_path/'p.json';o=tmp_path/'r.json';p.write_text(json.dumps(packet()))
    assert main([str(p),'--validate-only'])==0;assert json.loads(capsys.readouterr().out)['valid_schema']
    assert main([str(p),'--output',str(o)])==0
    assert json.loads(capsys.readouterr().out)==json.loads(o.read_text())


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('direction',['inward','outward'])
def test_inclined_elliptical_orbit_against_kepler(kind,direction):
    p=packet(kind,direction)
    p['scene']['sources']=[{'type':'point','charge_C' if kind=='electric' else 'mass_kg':1/K if kind=='electric' else 1/G}]
    particle=p['scene']['particles'][0]
    particle.update(mass_kg=2,charge_C=-2,position_m=[3,0,0],velocity_m_s=[0,np.sqrt(1/6),0])
    p['scene']['duration_s']=20;p['observations'][0]['condition']['radius_m']=2
    rotation=np.array([[1.,2.,2.],[-2.,2.,-1.],[-2.,-1.,2.]])/3
    particle['position_m']=(rotation@particle['position_m']).tolist()
    particle['velocity_m_s']=(rotation@particle['velocity_m_s']).tolist()
    n=1/np.sqrt(8);sign=-1 if direction=='inward' else 1
    E=3*np.pi/2 if direction=='inward' else 5*np.pi/2
    time=(E-0.5*np.sin(E)-np.pi)/n
    state=result(p);assert state['status']=='ok'
    assert_allclose(state['state']['time_s'],time,atol=1e-9)
    assert_allclose(state['state']['position_m'],rotation@[1,-sign*np.sqrt(3),0],atol=1e-9)
    assert_allclose(state['state']['velocity_m_s'],rotation@[sign*2*n,0,0],atol=1e-9)
    assert_allclose(state['state']['total_energy_J'],-0.5,atol=1e-10)
    assert_allclose(state['diagnostics']['radial_speed_m_s'],sign*n,atol=1e-10)


def test_repulsive_solid_sphere_penetration_without_collision():
    p=packet('electric');p['scene']['sources']=[{'type':'solid_sphere','radius_m':1,'charge_C':1/K}]
    p['scene']['particles'][0].update(mass_kg=1,charge_C=1,position_m=[2,0,0],velocity_m_s=[-2,0,0])
    p['observations'][0]['condition']['radius_m']=0.5
    from scipy.integrate import quad
    time=quad(lambda x:1/np.sqrt(5-2/x),1,2,epsabs=1e-12)[0]+np.arcsinh(1/np.sqrt(2))-np.arcsinh(0.5/np.sqrt(2))
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],time,atol=1e-8)
    assert_allclose(r['state']['speed_m_s'],1.5,atol=1e-8)
    assert_allclose(r['state']['total_energy_J'],2.5,atol=1e-8)


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_overlap_composition_reuses_source_laws(kind):
    # Two R=10 spheres, offset centres. Chosen strengths give total r''=-(r-c).
    p=packet(kind); strength=-500/K if kind=='electric' else 500/G
    key='charge_C' if kind=='electric' else 'mass_kg'
    p['scene']['sources']=[{'type':'solid_sphere','radius_m':10,key:strength,'center_m':[1,0,0]},
                          {'type':'solid_sphere','radius_m':10,key:strength,'center_m':[-1,0,0]}]
    p['scene']['particles'][0].update(mass_kg=1,charge_C=1,position_m=[2,0,0],velocity_m_s=[0,0,0])
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],np.pi/3,atol=1e-10)
    assert_allclose(r['state']['speed_m_s'],np.sqrt(3),atol=1e-10)


@pytest.mark.parametrize('seed',range(8))
def test_unfamiliar_free_geometry_against_quadratic(seed):
    rng=np.random.default_rng(seed);p=packet(direction='either')
    center=rng.uniform(-10,10,3);u=rng.normal(size=3);u/=np.linalg.norm(u)
    lateral=rng.normal(size=3);lateral-=np.dot(lateral,u)*u;lateral*=0.6/np.linalg.norm(lateral)
    velocity=1.3*u;initial=center-2*u+lateral
    p['scene']['particles'][0].update(position_m=initial.tolist(),velocity_m_s=velocity.tolist())
    p['observations'][0]['condition']['center_m']=center.tolist()
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],(2-0.8)/1.3,atol=1e-11)
    assert_allclose(r['state']['position_m'],center-0.8*u+lateral,atol=1e-11)


def test_duplicate_radial_requests_reuse_native_searches_and_copy_results(monkeypatch):
    from emfeeld import radial_events
    calls=[];original=radial_events.solve_ivp
    def counted(*a,**k):calls.append(k);return original(*a,**k)
    monkeypatch.setattr(radial_events,'solve_ivp',counted)
    p=packet();r=deepcopy(p['observations'][0]);r['id']='again';p['observations'].append(r)
    rows=run_packet(p)['results'];assert len(calls)==2
    assert rows[0]['state']==rows[1]['state']
    rows[0]['state']['position_m'][0]=888
    assert rows[1]['state']['position_m'][0]!=888
    assert calls[0]['events'].terminal is True and calls[0]['events'].direction==-1
    assert calls[1]['max_step']==calls[0]['max_step']/2 and 't_eval' not in calls[0]
    assert calls[1]['rtol']==calls[0]['rtol']/10


def test_cache_keys_include_geometry_direction_particle_and_accuracy(monkeypatch):
    from emfeeld import radial_events
    calls=[];original=radial_events.solve_ivp
    def counted(*a,**k):calls.append(k);return original(*a,**k)
    monkeypatch.setattr(radial_events,'solve_ivp',counted)
    p=packet();p['scene']['particles'].append(deepcopy(p['scene']['particles'][0]))
    for i,change in enumerate(['radius','center','direction','particle','accuracy']):
        r=deepcopy(p['observations'][0]);r['id']=f'other{i}'
        if change=='radius':r['condition']['radius_m']=1.1
        if change=='center':r['condition']['center_m']=[0.1,0,0]
        if change=='direction':r['condition']['direction']='outward'
        if change=='particle':r['particle_index']=1
        if change=='accuracy':r['accuracy']['time_atol_s']=2e-7
        p['observations'].append(r)
    assert all(r['status']=='ok' for r in run_packet(p)['results'])
    assert len(calls)==12
    run_packet(packet());assert len(calls)==14  # no cross-packet cache


def test_plane_radial_and_saved_requests_use_separate_caches(monkeypatch):
    from emfeeld import radial_events,plane_events,trajectory_samples
    counts={'radial':0,'plane':0,'sample':0}
    for name,module,attr in [('radial',radial_events,'solve_ivp'),('plane',plane_events,'solve_ivp'),('sample',trajectory_samples,'integrate')]:
        original=getattr(module,attr)
        def counted(*a,_name=name,_original=original,**k):counts[_name]+=1;return _original(*a,**k)
        monkeypatch.setattr(module,attr,counted)
    p=packet();plane=deepcopy(p['observations'][0]);plane['id']='plane'
    plane['condition']={'type':'plane','point_m':[0,0,0],'normal':[1,0,0],'direction':'positive'}
    plane['min_normal_speed_m_s']=plane.pop('min_radial_speed_m_s')
    p['observations']+=[plane,{'id':'sample','type':'trajectory_sample','particle_index':0,'sample_index':0,'quantity':'speed'},
                       {'id':'potential','type':'potential','position_m':[0,0,0]}]
    before=deepcopy(p);report=run_packet(p);assert p==before
    assert all(r['status']=='ok' for r in report['results'])
    assert counts=={'radial':2,'plane':2,'sample':1}
    assert report['plane_event_contract']==report['radial_event_contract']==1
    json.dumps(report,allow_nan=False)


def test_all_validation_precedes_physics(monkeypatch):
    from emfeeld import radial_events
    monkeypatch.setattr(radial_events,'solve_ivp',lambda *a,**k:pytest.fail('integrated during validation'))
    p=packet();r=deepcopy(p['observations'][0]);r['id']='bad';r['condition']['radius_m']=-1;p['observations'].append(r)
    with pytest.raises(ValueError):run_packet(p)


def test_singular_start_preserves_another_particle_and_static_probe():
    p=packet();p['scene']['sources']=[{'type':'point','mass_kg':1/G}]
    p['scene']['particles'][0].update(position_m=[0,0,0],velocity_m_s=[0,0,0])
    p['scene']['particles'].append(dict(p['scene']['particles'][0],position_m=[2,0,0]))
    r=deepcopy(p['observations'][0]);r.update(id='valid',particle_index=1)
    p['observations']+=[r,{'id':'potential','type':'potential','position_m':[1,0,0]}]
    assert [r['status'] for r in run_packet(p)['results']]==['domain_error','ok','ok']


@pytest.mark.parametrize('fault',['missing','time','position','velocity','residual','grazing','direction','uncertainty','malformed'])
def test_failed_refinement_never_returns_an_accepted_state(monkeypatch,fault):
    from emfeeld import radial_events
    original=radial_events._search
    def damaged(scene,request,refined):
        r=original(scene,request,refined)
        if refined:
            if fault=='missing':r['status']='no_event'
            elif fault=='time':r['state']['time_s']+=0.1
            elif fault=='position':r['state']['position_m'][0]+=1
            elif fault=='velocity':r['state']['velocity_m_s'][0]+=1
            elif fault=='residual':r['signed_radial_residual_m']=1
            elif fault=='grazing':r['radial_speed_m_s']=0
            elif fault=='direction':r['radial_speed_m_s']=1
            elif fault=='uncertainty':r['coordinate_uncertainty_m']=1
            else:raise FloatingPointError('synthetic malformed event output')
        return r
    monkeypatch.setattr(radial_events,'_search',damaged)
    r=result(packet());assert r['status'] in ('convergence_error','ambiguous_event','numerical_error')
    assert r['state'] is None


def test_native_solver_failure_not_no_event(monkeypatch):
    from emfeeld import radial_events
    monkeypatch.setattr(radial_events,'solve_ivp',lambda *a,**k:SimpleNamespace(success=False,message='synthetic step failure'))
    r=result(packet());assert r['status']=='integration_error' and r['state'] is None


@pytest.mark.parametrize('exception',[ValueError('f(a) and f(b) must have different signs'),RuntimeError('Failed to converge after 100 iterations.')])
def test_known_root_failure_is_local(monkeypatch,exception):
    from emfeeld import radial_events
    def fail(*a,**k):raise exception
    monkeypatch.setattr(radial_events,'solve_ivp',fail)
    r=result(packet());assert r['status']=='numerical_error' and r['state'] is None


def test_unexpected_programming_error_propagates(monkeypatch):
    from emfeeld import radial_events
    def fail(*a,**k):raise RuntimeError('synthetic programming mistake')
    monkeypatch.setattr(radial_events,'solve_ivp',fail)
    with pytest.raises(RuntimeError,match='programming mistake'):run_packet(packet())


@pytest.mark.parametrize('scale',[1e-15,1e-6,1.,1e12])
def test_radial_geometric_filter_is_scale_aware_not_a_length_cutoff(scale):
    from emfeeld.radial_events import separation
    s,error=separation([1.1*scale,0,0],[0,0,0],scale)
    assert s>error and error<1e-12*scale
    s,error=separation([0.6*scale,0.8*scale,0],[0,0,0],scale)
    assert abs(s)<=error


def test_radial_roundoff_resolution_not_met_is_explicit():
    p=packet();p['observations'][0]['accuracy']['position_atol_m']=1e-20
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


def test_defined_centre_normal_never_needed_during_crossing_function():
    from emfeeld.radial_events import separation
    assert separation([0,0,0],[0,0,0],1)[0]==-1


def test_horizon_ending_near_sphere_is_ambiguous_without_detected_root():
    p=packet();p['scene']['duration_s']=0.5;p['scene']['particles'][0]['position_m']=[-2,0,0]
    p['scene']['particles'][0]['velocity_m_s']=[1,0,0]
    p['observations'][0]['condition']['radius_m']=1.5-1e-9
    r=result(p);assert r['status']=='ambiguous_event' and r['state'] is None


EXAMPLES=Path(__file__).resolve().parents[1]/'examples'/'radial_events'
@pytest.mark.parametrize('entry',json.loads((EXAMPLES/'manifest.json').read_text())['packets'],ids=lambda e:e['file'])
def test_authored_example_packets(entry):
    report=run_packet(json.loads((EXAMPLES/entry['file']).read_text()))
    assert (0 if report['status']=='ok' else 1)==entry['cli_exit']
    assert len(report['results'])==len(entry['expected_results'])
    for r,e in zip(report['results'],entry['expected_results']):
        assert (r['id'],r['status'])==(e['id'],e['status'])
        for name,value in e.get('state',{}).items():
            assert_allclose(r['state'][name],value,atol=e['atol'],rtol=e['rtol'])
