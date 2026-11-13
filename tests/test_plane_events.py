"""Plane events: analytic oracles, strict authoring and unchanged old APIs."""
from copy import deepcopy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from numpy.testing import assert_allclose
import pytest

from emfeeld.observations import run_packet, packet_from_dict, main
from emfeeld.fields import G, K


def packet(kind='gravity', direction='positive'):
    return {'observation_schema_version': 1,
        'scene': {'schema_version': 1, 'title': 'crossing', 'kind': kind,
            'sources': [{'type': 'uniform', 'field_m_s2' if kind == 'gravity' else 'field_N_C': [0,0,0]}],
            'particles': [{'mass_kg': 2, 'charge_C': -4, 'position_m': [-1,0,0], 'velocity_m_s': [2,0,0]}],
            'duration_s': 3, 'samples': 4, 'bounds_m': [-3,3,-3,3,-3,3]},
        'observations': [{'id': 'cross', 'type': 'trajectory_event', 'particle_index': 0,
            'condition': {'type':'plane', 'point_m':[0,0,0], 'normal':[1,0,0], 'direction':direction},
            'occurrence':'first', 'max_step_s':0.05, 'min_normal_speed_m_s':1e-6,
            'accuracy': {'time_atol_s':1e-7, 'position_atol_m':1e-7, 'velocity_atol_m_s':1e-7, 'rtol':1e-7}}]}


def result(p): return run_packet(p)['results'][0]


@pytest.mark.parametrize('kind', ['electric','gravity'])
@pytest.mark.parametrize('direction', ['positive','either'])
def test_linear_crossing_between_saved_frames(kind, direction):
    p=packet(kind,direction); r=result(p)
    assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],0.5,atol=1e-12,rtol=0)
    assert_allclose(r['state']['position_m'],[0,0,0],atol=1e-12)
    assert_allclose(r['state']['velocity_m_s'],[2,0,0],atol=1e-12)
    assert_allclose(r['state']['speed_m_s'],2,atol=1e-12)
    assert_allclose(r['state']['kinetic_J'],4,atol=1e-12)
    assert r['error_bound'] is None and r['diagnostics']['refinement']['passed']
    assert r['state']['time_s'] not in np.linspace(0,3,4)
    p['scene']['samples']=101
    assert result(p)['state']==r['state']


@pytest.mark.parametrize('kind', ['electric','gravity'])
def test_uniform_acceleration_both_couplings(kind):
    p=packet(kind); key='field_N_C' if kind=='electric' else 'field_m_s2'
    p['scene']['sources'][0][key]=[-1,0,0] if kind=='electric' else [2,0,0]
    p['scene']['particles'][0].update(position_m=[-1,0,0],velocity_m_s=[0,0,0])
    r=result(p); assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],1,atol=1e-10)
    assert_allclose(r['state']['velocity_m_s'],[2,0,0],atol=1e-10)
    assert_allclose(r['state']['total_energy_J'],4,atol=1e-10)


@pytest.mark.parametrize('scale',[1e-100,1,1e100])
def test_oblique_plane_translation_normal_scaling(scale):
    p=packet(); c=np.array([7.,-3.,2.]); n=np.array([1.,2.,-2.])/3
    p['scene']['particles'][0].update(position_m=(c-2*n).tolist(),velocity_m_s=(4*n).tolist())
    p['observations'][0]['condition'].update(point_m=c.tolist(),normal=(n*scale).tolist())
    r=result(p); assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],0.5,atol=1e-12)
    assert_allclose(r['state']['position_m'],c,atol=1e-12)


def test_reverse_normal_and_direction_preserves_event():
    p=packet(); a=result(p);p['observations'][0]['condition'].update(normal=[-2,0,0],direction='negative')
    b=result(p);assert b['state']==a['state']
    assert b['diagnostics']['normal_speed_m_s']==pytest.approx(-2)


def test_wrong_direction_and_no_crossing_are_explicit():
    for p in (packet(direction='negative'),packet()):
        if p['observations'][0]['condition']['direction']=='positive':
            p['observations'][0]['condition']['point_m']=[10,0,0]
        r=run_packet(p)
        assert r['status']=='ok' and r['counts']['no_events']==1
        assert r['results'][0]['status']=='no_event' and r['results'][0]['state'] is None
        assert len(r['results'][0]['diagnostics']['passes'])==2


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('direction,expected',[('negative',np.pi/2),('positive',3*np.pi/2),('either',np.pi/2)])
def test_first_directional_crossing_among_many(kind,direction,expected):
    p=packet(kind,direction)
    strength=-1/K if kind=='electric' else 1/G
    # Electric particle q/m = 1, so both domains have x''=-x inside R=1.
    p['scene']['sources']=[{'type':'solid_sphere','radius_m':1,
                          'charge_C' if kind=='electric' else 'mass_kg':strength}]
    p['scene']['particles'][0].update(mass_kg=1,charge_C=1,position_m=[0.5,0,0],velocity_m_s=[0,0,0])
    p['scene']['duration_s']=20
    r=result(p); assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],expected,atol=1e-10)
    assert_allclose(r['state']['speed_m_s'],0.5,atol=1e-10)


def test_inclined_circular_gravity_orbit():
    p=packet(direction='negative');n=np.array([1.,2.,-2.])/3;u=np.array([2.,-1.,0.])/np.sqrt(5)
    p['scene']['sources']=[{'type':'point','mass_kg':1/G}]
    p['scene']['particles'][0].update(position_m=n.tolist(),velocity_m_s=u.tolist())
    p['scene']['duration_s']=7;p['observations'][0]['condition']['normal']=n.tolist()
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],np.pi/2,atol=1e-9)
    assert_allclose(r['state']['position_m'],u,atol=1e-9)
    assert_allclose(r['state']['velocity_m_s'],-n,atol=1e-9)


@pytest.mark.parametrize('position,normal', [([0,0,0],[1,0,0]),([7,0,-1],[1,3,7])])
def test_initial_plane_is_not_reported_as_later_crossing(position,normal):
    p=packet();p['scene']['particles'][0]['position_m']=position;p['observations'][0]['condition']['normal']=normal
    r=result(p);assert r['status']=='initial_condition_error' and r['state'] is None


def test_near_grazing_is_explicit_not_ok():
    p=packet();p['observations'][0]['min_normal_speed_m_s']=3
    r=result(p);assert r['status']=='ambiguous_event'


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_composed_sources_accelerate_without_new_model_dispatch(kind):
    p=packet(kind)
    key='field_N_C' if kind=='electric' else 'field_m_s2'
    factor=-2 if kind=='electric' else 1
    p['scene']['sources']=[{'type':'uniform',key:[1/factor,0,0]},{'type':'uniform',key:[1/factor,0,0]}]
    p['scene']['particles'][0]['velocity_m_s']=[0,0,0]
    assert_allclose(result(p)['state']['time_s'],1,atol=1e-10)


@pytest.mark.parametrize('mutate',[
    lambda r:r.update(particle_index=True),lambda r:r.update(particle_index=4),
    lambda r:r.update(occurrence='second'),lambda r:r.update(occurrence=1),
    lambda r:r.update(max_step_s=0),lambda r:r.update(max_step_s=True),
    lambda r:r.update(max_step_s=1e-20),lambda r:r.update(max_step_s=4),
    lambda r:r.update(min_normal_speed_m_s=0),lambda r:r.update(min_normal_speed_m_s='1'),
    lambda r:r['condition'].update(normal=[0,0,0]),lambda r:r['condition'].update(normal=[1,2]),
    lambda r:r['condition'].update(point_m=[0,False,0]),lambda r:r['condition'].update(direction='forward'),
    lambda r:r['condition'].update(type='sphere'),lambda r:r['condition'].update(radius_m=1),
    lambda r:r['accuracy'].update(time_atol_s=0),lambda r:r['accuracy'].update(rtol=-1),
    lambda r:r['accuracy'].update(rtol=float('nan')),lambda r:r.update(time_s=1),
    lambda r:r.pop('accuracy'),lambda r:r.pop('max_step_s'),lambda r:r.pop('min_normal_speed_m_s'),
])
def test_invalid_authoring_rejected_before_physics(mutate):
    p=packet();mutate(p['observations'][0])
    with pytest.raises(ValueError):packet_from_dict(p)


def test_schema_failure_does_not_run_an_earlier_valid_request(monkeypatch):
    from emfeeld import plane_events
    monkeypatch.setattr(plane_events,'solve_ivp',lambda *a,**k:pytest.fail('physics ran during validation'))
    p=packet();r=deepcopy(p['observations'][0]);r['id']='bad';r['condition']['normal']=[0,0,0];p['observations'].append(r)
    with pytest.raises(ValueError):run_packet(p)


def test_local_failures_do_not_hide_valid_measurements():
    p=packet();p['scene']['particles'].append(dict(p['scene']['particles'][0],position_m=[0,0,0]))
    r=deepcopy(p['observations'][0]);r.update(id='bad_start',particle_index=1)
    p['observations'] += [r,{'id':'potential','type':'potential','position_m':[1,0,0]}]
    rows=run_packet(p)['results']
    assert [r['status'] for r in rows]==['ok','initial_condition_error','ok']


def test_duplicate_event_requests_reuse_two_searches(monkeypatch):
    from emfeeld import plane_events
    calls=[];solve=plane_events.solve_ivp
    def count(*a,**k):calls.append(k);return solve(*a,**k)
    monkeypatch.setattr(plane_events,'solve_ivp',count)
    p=packet();r=deepcopy(p['observations'][0]);r['id']='same';p['observations'].append(r)
    a=run_packet(p);assert len(calls)==2
    assert a['results'][0]['state']==a['results'][1]['state']
    assert calls[0]['events'].terminal is True and calls[0]['events'].direction==1
    assert 't_eval' not in calls[0] and calls[1]['max_step']==calls[0]['max_step']/2


def test_input_unchanged_and_json_finite():
    p=packet();before=deepcopy(p);r=run_packet(p)
    assert p==before;json.dumps(r,allow_nan=False)
    assert r['results'][0]['units']['time_s']=='s'


def test_cli_roundtrip_and_validate_only(tmp_path,capsys):
    p=tmp_path/'packet.json';o=tmp_path/'result.json';p.write_text(json.dumps(packet()))
    assert main([str(p),'--validate-only'])==0;assert json.loads(capsys.readouterr().out)['valid_schema']
    assert main([str(p),'--output',str(o)])==0
    assert json.loads(capsys.readouterr().out)==json.loads(o.read_text())


@pytest.mark.parametrize('source', [{'type':'shell','mass_kg':1,'radius_m':1},
                                   {'type':'plane','mass_per_m2_kg_m2':1}])
def test_observation_plane_does_not_admit_discontinuous_source_motion(source):
    p=packet();p['scene']['sources']=[source]
    p['observations'].append({'id':'potential','type':'potential','position_m':[0,0,0]})
    r=run_packet(p);assert r['status']=='partial'
    assert [x['status'] for x in r['results']]==['unsupported_trajectory','ok']


def test_singular_start_is_local_and_cached(monkeypatch):
    from emfeeld import plane_events
    monkeypatch.setattr(plane_events,'solve_ivp',lambda *a,**k:pytest.fail('singular start integrated'))
    p=packet();p['scene']['sources']=[{'type':'point','mass_kg':1/G,'center_m':[-1,0,0]}]
    r=deepcopy(p['observations'][0]);r['id']='repeat';p['observations'].append(r)
    p['observations'].append({'id':'potential','type':'potential','position_m':[1,0,0]})
    rows=run_packet(p)['results'];assert [r['status'] for r in rows]==['domain_error','domain_error','ok']


def test_terminal_search_can_finish_before_later_singularity():
    p=packet(direction='negative');p['scene']['sources']=[{'type':'point','mass_kg':1/G}]
    p['scene']['particles'][0].update(position_m=[2,0,0],velocity_m_s=[0,0,0])
    p['scene']['duration_s']=10;p['observations'][0]['condition']['point_m']=[1,0,0]
    r=result(p);assert r['status']=='ok'
    assert_allclose(r['state']['time_s'],1+np.pi/2,atol=1e-9)
    assert_allclose(r['state']['speed_m_s'],1,atol=1e-10)
    assert all(x['end_time_s']<10 for x in r['diagnostics']['passes'])


def test_sample_and_event_runs_are_separate_and_static_preserved(monkeypatch):
    from emfeeld import plane_events, trajectory_samples
    calls={'event':0,'sample':0};event_solve=plane_events.solve_ivp;sample_solve=trajectory_samples.integrate
    def event(*a,**k):calls['event']+=1;return event_solve(*a,**k)
    def sample(*a,**k):calls['sample']+=1;return sample_solve(*a,**k)
    monkeypatch.setattr(plane_events,'solve_ivp',event);monkeypatch.setattr(trajectory_samples,'integrate',sample)
    p=packet();p['observations'] += [
      {'id':'saved','type':'trajectory_sample','particle_index':0,'sample_index':1,'quantity':'position'},
      {'id':'speed','type':'trajectory_sample','particle_index':0,'sample_index':1,'quantity':'speed'},
      {'id':'probe','type':'potential','position_m':[1,0,0]}]
    rows=run_packet(p)['results'];assert all(r['status']=='ok' for r in rows)
    assert calls=={'event':2,'sample':1}
    assert_allclose(rows[1]['value'],[1,0,0],atol=1e-12)


@pytest.mark.parametrize('fault', ['missing','time','position','velocity','residual','grazing','malformed'])
def test_unresolved_event_is_not_a_success(monkeypatch,fault):
    from emfeeld import plane_events
    search=plane_events._search
    def damaged(scene,request,refined):
        r=search(scene,request,refined)
        if refined:
            if fault=='missing':r.update(status='no_event')
            elif fault in ('time','position','velocity'):
                if fault=='time':r['state']['time_s']+=0.1
                else:r['state'][fault+'_m' if fault=='position' else 'velocity_m_s'][0]+=1
            elif fault=='residual':r['signed_plane_residual_m']=1
            elif fault=='grazing':r['normal_speed_m_s']=0
            else:raise FloatingPointError('synthetic malformed state')
        return r
    monkeypatch.setattr(plane_events,'_search',damaged)
    r=result(packet());assert r['status'] in ('convergence_error','ambiguous_event','numerical_error')
    assert r['state'] is None


def test_failed_native_solver_not_no_event(monkeypatch):
    from emfeeld import plane_events
    monkeypatch.setattr(plane_events,'solve_ivp',lambda *a,**k:SimpleNamespace(success=False,message='step failed'))
    r=result(packet());assert r['status']=='integration_error' and r['state'] is None


def test_unexpected_programming_error_propagates(monkeypatch):
    from emfeeld import plane_events
    def broken(*a,**k):raise RuntimeError('programming defect')
    monkeypatch.setattr(plane_events,'solve_ivp',broken)
    with pytest.raises(RuntimeError,match='programming defect'):run_packet(packet())


def test_domain_and_numerical_errors_isolated(monkeypatch):
    from emfeeld import plane_events, DomainError
    for error,status in [(DomainError('singular'),'domain_error'),(FloatingPointError('bad'),'numerical_error')]:
        def broken(*a,**k):raise error
        monkeypatch.setattr(plane_events,'solve_ivp',broken)
        p=packet();p['observations'].append({'id':'probe','type':'potential','position_m':[1,0,0]})
        rows=run_packet(p)['results'];assert [r['status'] for r in rows]==[status,'ok']


def test_exact_horizon_not_false_no_event():
    p=packet();p['scene']['duration_s']=0.5
    r=result(p)
    assert r['status'] in ('ok','ambiguous_event','convergence_error')
    if r['status']=='ok':assert_allclose(r['state']['time_s'],0.5,atol=1e-12)


def test_tangent_not_certified_crossing():
    p=packet();p['scene']['sources'][0]['field_m_s2']=[-2,0,0]
    p['scene']['duration_s']=2;p['observations'][0]['min_normal_speed_m_s']=1e-4
    r=result(p)
    # x=-(t-1)^2 touches the plane and turns back, not a transverse crossing.
    assert r['status'] in ('no_event','ambiguous_event','convergence_error')


def test_large_translation_cannot_claim_unresolved_plane_precision():
    p=packet();p['scene']['particles'][0]['position_m']=[1e12-1,0,0]
    p['observations'][0]['condition']['point_m']=[1e12,0,0]
    r=result(p);assert r['status']=='ambiguous_event'


def test_static_and_saved_only_do_not_use_event_solver(monkeypatch):
    from emfeeld import plane_events
    monkeypatch.setattr(plane_events,'solve_ivp',lambda *a,**k:pytest.fail('unrequested event search'))
    p=packet();p['observations']=[{'id':'p','type':'potential','position_m':[1,0,0]},
       {'id':'s','type':'trajectory_sample','quantity':'speed','particle_index':0,'sample_index':0}]
    assert run_packet(p)['status']=='ok'


def test_caches_do_not_survive_packets(monkeypatch):
    from emfeeld import plane_events
    solve=plane_events.solve_ivp;calls=[]
    def count(*a,**k):calls.append(1);return solve(*a,**k)
    monkeypatch.setattr(plane_events,'solve_ivp',count)
    run_packet(packet());run_packet(packet());assert len(calls)==4


def test_no_viewer_import_in_fresh_process():
    import subprocess
    code="import sys; from emfeeld.observations import run_packet; assert 'pyvista' not in sys.modules; assert 'emfeeld.viewer' not in sys.modules"
    subprocess.run([sys.executable,'-c',code],check=True)


EXAMPLE_ROOT=Path(__file__).resolve().parents[1]/'examples'/'plane_events'
EXAMPLES=json.loads((EXAMPLE_ROOT/'manifest.json').read_text())['packets']

@pytest.mark.parametrize('entry',EXAMPLES,ids=lambda e:Path(e['file']).stem)
def test_data_only_example_packets_against_declared_oracles(entry):
    p=json.loads((EXAMPLE_ROOT/entry['file']).read_text());a=run_packet(p)
    rows={r['id']:r for r in a['results']}
    for expected in entry['expected_results']:
        r=rows[expected['id']];assert r['status']==expected['status']
        for key,value in expected.get('state',{}).items():
            assert_allclose(r['state'][key],value,atol=expected['atol'],rtol=expected['rtol'])


@pytest.mark.parametrize('exception',[ValueError('f(a) and f(b) must have different signs'),
                                     RuntimeError('Failed to converge after 100 iterations.')])
def test_known_root_failure_is_local(monkeypatch,exception):
    from emfeeld import plane_events
    def fail(*a,**k):raise exception
    monkeypatch.setattr(plane_events,'solve_ivp',fail)
    p=packet();p['observations'].append({'id':'valid','type':'potential','position_m':[1,0,0]})
    r=run_packet(p);assert [x['status'] for x in r['results']]==['numerical_error','ok']
    assert r['results'][0]['diagnostics']['integration_attempts']==1


def test_real_rotated_two_charge_composition():
    p=json.loads((EXAMPLE_ROOT/'sc-28.json').read_text());a=result(p)
    from scipy.spatial.transform import Rotation
    Q=Rotation.from_rotvec([.3,-.7,.6]).as_matrix();shift=np.array([3.,-2.,4.])
    for s in p['scene']['sources']:s['center_m']=(Q@np.array(s['center_m'])+shift).tolist()
    for s in p['scene']['particles']:
        s['position_m']=(Q@np.array(s['position_m'])+shift).tolist()
        s['velocity_m_s']=(Q@np.array(s['velocity_m_s'])).tolist()
    c=p['observations'][0]['condition'];c['point_m']=(Q@np.array(c['point_m'])+shift).tolist();c['normal']=(Q@np.array(c['normal'])).tolist()
    b=result(p);assert b['status']=='ok'
    assert_allclose(b['state']['time_s'],a['state']['time_s'],atol=1e-9)
    assert_allclose(b['state']['position_m'],Q@np.array(a['state']['position_m'])+shift,atol=1e-9)
    assert_allclose(b['state']['velocity_m_s'],Q@np.array(a['state']['velocity_m_s']),atol=1e-10)
