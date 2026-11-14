"""Saved-state observations: analytic checks, schema failures and cache isolation."""
from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
import pytest

from emfeeld import Scene, scene_from_dict
from emfeeld.fields import G, K, DomainError
from emfeeld.observations import run_packet, packet_from_dict, main


def scene(kind='electric'):
    return {'schema_version': 1, 'title': 'saved-state checks', 'kind': kind,
            'sources': [{'type': 'uniform', 'field_N_C' if kind=='electric' else 'field_m_s2': [1,-2,0.5]}],
            'particles': [{'mass_kg': 2, 'charge_C': -6, 'position_m': [0,1,2], 'velocity_m_s': [3,2,1]},
                          {'mass_kg': 4, 'charge_C': 8, 'position_m': [1,0,-1], 'velocity_m_s': [0,1,2]}],
            'duration_s': 2, 'samples': 9, 'bounds_m': [-20,20,-20,20,-20,20]}


def req(quantity='position', particle=0, **selector):
    if not selector: selector={'sample_index': 4}
    return dict(id='measurement', type='trajectory_sample', particle_index=particle,
                quantity=quantity, **selector)


def packet(rows=None, kind='electric'):
    return {'observation_schema_version':1, 'scene':scene(kind), 'observations':rows or [req()]}


def result(data): return run_packet(data)['results'][0]


@pytest.mark.parametrize('kind', ['electric','gravity'])
@pytest.mark.parametrize('quantity,unit', [('time','s'), ('position','m'), ('velocity','m/s'),
    ('speed','m/s'), ('kinetic_energy','J'), ('potential_energy','J'), ('total_energy','J')])
def test_uniform_field_saved_values_against_analytic(kind, quantity, unit):
    p=packet([req(quantity, sample_index=4)],kind)
    r=run_packet(p); actual=r['results'][0]
    coupling=-6 if kind=='electric' else 2
    acc=coupling/2*np.array([1.,-2.,0.5]); t=1.
    position=np.array([0.,1.,2.])+t*np.array([3.,2.,1.])+0.5*t*t*acc
    velocity=np.array([3.,2.,1.])+t*acc
    kinetic=np.dot(velocity,velocity)
    potential=-coupling*np.dot(position,[1.,-2.,0.5])
    expected=dict(time=t, position=position, velocity=velocity, speed=np.linalg.norm(velocity),
                  kinetic_energy=kinetic,potential_energy=potential,total_energy=kinetic+potential)
    assert_allclose(actual['value'],expected[quantity],rtol=2e-11,atol=1e-10)
    assert actual['unit']==unit and actual['status']=='ok'
    assert actual['particle_index']==0 and actual['sample_index']==4 and actual['time_s']==1
    assert actual['time_offset_s'] is None and actual['error_bound'] is None
    diagnostic=r['trajectory_runs']['0']
    assert diagnostic['status']=='ok' and diagnostic['integration_attempted'] is True
    assert diagnostic['particle']['mass_kg']==2 and diagnostic['particle']['charge_C']==-6
    assert diagnostic['samples']==9 and diagnostic['evaluations']>0
    assert diagnostic['normalized_energy_drift']<1e-11
    assert 'error bound' in diagnostic['diagnostic_meaning']


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_multiple_particles_and_quantities_reuse_exact_saved_arrays(kind,monkeypatch):
    # Obtain reference once via the existing public scene method, before spying.
    p=packet(kind=kind); s=scene_from_dict(p['scene']); originals=s.trajectories()
    from emfeeld import trajectory_samples as ts
    real=ts.integrate; calls=[]
    def count(*args,**kwargs):
        calls.append((args,kwargs)); return real(*args,**kwargs)
    monkeypatch.setattr(ts,'integrate',count)
    p['observations']=[dict(req(q,particle=i,sample_index=j),id=f'p{i}_{q}_{j}')
        for i in [1,0] for j in [0,4,8] for q in ['position','velocity','speed','kinetic_energy','potential_energy','total_energy']]
    p['observations'].insert(7,{'id':'static', 'type':'potential', 'position_m':[1,2,3]})
    r=run_packet(p)
    assert len(calls)==2 and list(r['trajectory_runs'])==['1','0']
    assert r['status']=='ok' and len(r['results'])==37
    for row in r['results']:
        if row['type']!='trajectory_sample':continue
        tr=originals[row['particle_index']]; j=row['sample_index']
        expected={'position':tr.position_m[j], 'velocity':tr.velocity_m_s[j],
          'speed':np.hypot.reduce(tr.velocity_m_s[j]), 'kinetic_energy':tr.kinetic_J[j],
          'potential_energy':tr.potential_J[j], 'total_energy':tr.energy_J[j]}
        assert_array_equal(row['value'],expected[row['quantity']])
    assert [row['id'] for row in r['results']]==[row['id'] for row in p['observations']]


@pytest.mark.parametrize('kind',['electric','gravity'])
def test_central_circular_orbit_quantities(kind):
    p=packet(kind=kind)
    p['scene']['sources']=[{'type':'point','charge_C' if kind=='electric' else 'mass_kg':1/K if kind=='electric' else 1/G}]
    p['scene']['particles']=[{'mass_kg':1,'charge_C':-1,'position_m':[1,0,0],'velocity_m_s':[0,0.8,0.6]}]
    p['scene'].update(duration_s=2*np.pi,samples=129)
    p['observations']=[dict(req(q,sample_index=j),id=f'{q}_{j}') for j in [0,32,64,128]
                       for q in ['position','velocity','speed','kinetic_energy','potential_energy','total_energy']]
    r=run_packet(p); assert r['status']=='ok'
    for row in r['results']:
        t=row['time_s']; expected={'position':[np.cos(t),0.8*np.sin(t),0.6*np.sin(t)],
          'velocity':[-np.sin(t),0.8*np.cos(t),0.6*np.cos(t)],'speed':1,'kinetic_energy':0.5,
          'potential_energy':-1,'total_energy':-0.5}
        assert_allclose(row['value'],expected[row['quantity']],atol=2e-9,rtol=2e-9)


def test_unfamiliar_sphere_composition_motion_and_gravity_mass_independence():
    p=packet(kind='gravity')
    p['scene']['sources']=[{'type':'solid_sphere','mass_kg':0.5/G,'radius_m':1,'center_m':[0,0,0]},
                          {'type':'solid_sphere','mass_kg':0.5/G,'radius_m':1,'center_m':[0,0,0]}]
    p['scene']['particles']=[{'mass_kg':m,'position_m':[0.3,0,0],'velocity_m_s':[0,0,0]} for m in [1,9]]
    p['scene'].update(duration_s=2*np.pi,samples=65)
    p['observations']=[dict(req('position',i,sample_index=j),id=f'p{i}_{j}') for i in [0,1] for j in [0,16,32,64]]
    r=run_packet(p); assert r['status']=='ok'
    for row in r['results']:
        assert_allclose(row['value'],[0.3*np.cos(row['time_s']),0,0],atol=1e-9)
    for a,b in zip(r['results'][:4],r['results'][4:]):assert_array_equal(a['value'],b['value'])


@pytest.mark.parametrize('time,index',[(0,0),(1,4),(2,8)])
def test_exact_time(time,index):
    r=result(packet([req('velocity',time_s=time,time_selection='exact')]))
    assert r['status']=='ok' and r['sample_index']==index and r['time_s']==time
    assert r['time_offset_s']==0 and r['selection']['time_s']==time


@pytest.mark.parametrize('time,index,offset',[(0.26,1,-0.01),(0.49,2,0.01),(0.375,1,-0.125)])
def test_explicit_nearest_and_tie_to_earlier(time,index,offset):
    r=result(packet([req('position',time_s=time,time_selection='nearest',max_time_error_s=0.13)]))
    assert r['status']=='ok' and r['sample_index']==index
    assert r['time_s']==0.25*index and r['time_offset_s']==pytest.approx(offset)
    assert r['selection']['time_selection']=='nearest'


def test_off_grid_and_nearest_tolerance_errors_do_not_integrate(monkeypatch):
    from emfeeld import trajectory_samples as ts
    def fail(*a,**kw): raise AssertionError('selection failure must not integrate')
    monkeypatch.setattr(ts,'integrate',fail)
    p=packet([req(time_s=0.26,time_selection='exact'),
              dict(req(time_s=0.26,time_selection='nearest',max_time_error_s=0.001),id='tight'),
              {'id':'static','type':'potential','position_m':[0,0,0]}])
    r=run_packet(p)
    assert r['status']=='partial' and r['counts']['selection_errors']==2
    assert not r['trajectory_runs']
    assert [x['status'] for x in r['results']]==['selection_error','selection_error','ok']
    assert [x['error']['code'] for x in r['results'][:2]]==['time_not_saved','time_tolerance_exceeded']
    assert r['results'][0]['value'] is None


def test_decimal_time_not_silently_rounded():
    p=packet([req(time_s=0.3,time_selection='exact')]); p['scene'].update(duration_s=1,samples=11)
    assert result(p)['status']=='selection_error'  # linspace stores 0.30000000000000004
    p['observations']=[req(sample_index=3)]
    r=result(p); assert r['time_s']==float(np.linspace(0,1,11)[3])


@pytest.mark.parametrize('change',[
    {'particle_index':True},{'particle_index':-1},{'particle_index':2},{'particle_index':0.0},
    {'particle_index':'0'},{'sample_index':True},{'sample_index':-1},{'sample_index':9},
    {'sample_index':1.5},{'sample_index':'4'},{'quantity':'acceleration'}, {'quantity':[]},
    {'quantity':'closest_approach'},{'quantity':'turning_point'}, {'unit':'cm'},
    {'time_s':1},{'time_selection':'nearest'}, {'max_time_error_s':0.1}])
def test_invalid_references_selectors_and_quantity_rejected(change):
    r=req();r.update(change)
    with pytest.raises(ValueError):packet_from_dict(packet([r]))


@pytest.mark.parametrize('selector',[
    {}, {'time_s':1},{'time_s':1,'time_selection':'interpolate'},
    {'time_s':-1,'time_selection':'exact'},{'time_s':3,'time_selection':'exact'},
    {'time_s':True,'time_selection':'exact'},{'time_s':'1','time_selection':'exact'},
    {'time_s':float('nan'),'time_selection':'exact'},{'time_s':float('inf'),'time_selection':'nearest','max_time_error_s':1},
    {'time_s':1,'time_selection':'nearest'},
    {'time_s':1,'time_selection':'nearest','max_time_error_s':-1},
    {'time_s':1,'time_selection':'nearest','max_time_error_s':True},
    {'time_s':1,'time_selection':'nearest','max_time_error_s':float('inf')},
    {'time_s':1,'time_selection':'exact','max_time_error_s':0},
    {'sample_index':0,'time_s':0,'time_selection':'exact'}])
def test_bad_time_contract(selector):
    row=dict(id='bad',type='trajectory_sample',particle_index=0,quantity='position',**selector)
    with pytest.raises(ValueError):packet_from_dict(packet([row]))


def test_full_batch_validation_precedes_any_physics(monkeypatch):
    from emfeeld import trajectory_samples as ts
    def fail(*a,**kw):raise AssertionError('must validate first')
    monkeypatch.setattr(ts,'integrate',fail)
    p=packet([req(),dict(req(),id='bad',particle_index=100)])
    with pytest.raises(ValueError):run_packet(p)
    p=packet([req(),{'id':'measurement','type':'potential','position_m':[1,0,0]}])
    with pytest.raises(ValueError,match='duplicate'):run_packet(p)
    p=packet();p['scene']['particles']=[]
    with pytest.raises(ValueError):run_packet(p)


@pytest.mark.parametrize('quantity,value',[('position',3),('velocity',[0,0]),('speed',[1,2,3]),
    ('kinetic_energy',True),('potential_energy','0')])
def test_expectation_shape_is_not_broadcast(quantity,value):
    row=req(quantity);row['expectation']={'value':value,'atol':0,'rtol':0}
    with pytest.raises(ValueError):packet_from_dict(packet([row]))


def test_authored_expectation_does_not_change_result():
    p=packet([dict(req('speed'),expectation={'value':0,'atol':0,'rtol':0})])
    r=run_packet(p)
    assert r['status']=='failed' and r['counts']['failed_expectations']==1
    p['observations'][0].pop('expectation')
    assert r['results'][0]['value']==result(p)['value']


@pytest.mark.parametrize('kind',['electric','gravity'])
@pytest.mark.parametrize('source',['shell','plane'])
def test_unsupported_trajectory_preserves_static_measurements(kind,source,monkeypatch):
    from emfeeld import trajectory_samples as ts
    def fail(*a,**kw):raise AssertionError('unsafe trajectory must not integrate')
    monkeypatch.setattr(ts,'integrate',fail)
    p=packet(kind=kind); key=('charge_C' if kind=='electric' else 'mass_kg') if source=='shell' else ('charge_per_m2_C_m2' if kind=='electric' else 'mass_per_m2_kg_m2')
    p['scene']['sources']=[dict(type=source,**{key:1e-9},**({'radius_m':1} if source=='shell' else {}))]
    p['observations']=[req(),{'id':'V','type':'potential','position_m':[2,0,2]}]
    r=run_packet(p)
    assert [x['status'] for x in r['results']]==['unsupported_trajectory','ok']
    assert r['counts']['unsupported_trajectories']==1
    assert r['trajectory_runs']['0']['integration_attempted'] is False


def test_singular_particle_does_not_discard_other_particle_or_static_probe(monkeypatch):
    from emfeeld import trajectory_samples as ts
    real=ts.integrate;calls=[]
    def count(*a,**kw):calls.append(a[1]);return real(*a,**kw)
    monkeypatch.setattr(ts,'integrate',count)
    p=packet();p['scene']['sources']=[{'type':'point','charge_C':1e-12}]
    p['scene']['particles'][0]['position_m']=[0,0,0]
    p['scene']['particles'][1]['charge_C']=0
    p['observations']=[req(),dict(req('speed'),id='same_failure'),dict(req('position',1),id='other'),
                       {'id':'V','type':'potential','position_m':[1,0,0]}]
    r=run_packet(p)
    assert r['status']=='partial' and len(calls)==2
    assert [x['status'] for x in r['results']]==['domain_error','domain_error','ok','ok']
    assert r['counts']['domain_errors']==2
    assert r['trajectory_runs']['0']['status']=='domain_error'
    assert_allclose(r['results'][2]['value'],[1,1,1],rtol=0,atol=1e-13)


def test_only_requested_particles_are_integrated():
    p=packet([req('position',1)])
    p['scene']['sources']=[{'type':'point','charge_C':1e-12}]
    p['scene']['particles'][0]['position_m']=[0,0,0]
    p['scene']['particles'][1]['charge_C']=0
    r=run_packet(p)
    assert r['status']=='ok' and list(r['trajectory_runs'])==['1']


def test_packet_cache_is_local_and_input_is_not_mutated():
    p=packet();before=deepcopy(p)
    a=run_packet(p);assert p==before
    b=run_packet(p);assert a==b
    p['scene']['particles'][0]['velocity_m_s'][0]+=2
    c=run_packet(p)
    assert c['scene_sha256']!=a['scene_sha256'] and c['results'][0]['value']!=a['results'][0]['value']
    a['input']['scene']['title']='edited report'
    assert p['scene']['title']=='saved-state checks'


def test_static_only_and_validation_only_never_integrate(monkeypatch,tmp_path,capsys):
    from emfeeld import trajectory_samples as ts
    def fail(*a,**kw):raise AssertionError('not requested')
    monkeypatch.setattr(ts,'integrate',fail)
    p=packet([{'id':'V','type':'potential','position_m':[1,0,0]}]);r=run_packet(p)
    assert 'trajectory_runs' not in r and r['trajectories'].startswith('not evaluated')
    file=tmp_path/'packet.json';file.write_text(json.dumps(packet()))
    assert main([str(file),'--validate-only'])==0
    assert 'NOT RUN' in json.loads(capsys.readouterr().out)['evaluation']


def test_unresolved_time_grid_is_explicit_without_solve(monkeypatch):
    from emfeeld import trajectory_samples as ts
    def fail(*a,**kw):raise AssertionError('unresolved grid')
    monkeypatch.setattr(ts,'integrate',fail)
    p=packet();p['scene']['duration_s']=float(np.nextafter(0.,1.))
    r=run_packet(p)
    assert r['status']=='failed' and r['results'][0]['status']=='numerical_error'
    json.dumps(r,allow_nan=False)


def test_native_solver_failure_is_local_and_cached(monkeypatch):
    from emfeeld import trajectory_samples as ts
    calls=[]
    def fail(*a,**kw):calls.append(1);raise RuntimeError('trajectory integration failed: deliberate backend failure')
    monkeypatch.setattr(ts,'integrate',fail)
    p=packet([req(),dict(req('speed'),id='speed'),{'id':'V','type':'potential','position_m':[0,0,0]}])
    r=run_packet(p)
    assert len(calls)==1 and r['status']=='partial'
    assert [x['status'] for x in r['results']]==['integration_error','integration_error','ok']
    assert r['counts']['integration_errors']==2


def test_programming_error_is_not_labelled_a_domain_failure(monkeypatch):
    from emfeeld import trajectory_samples as ts
    def fail(*a,**kw):raise RuntimeError('unrelated programming defect')
    monkeypatch.setattr(ts,'integrate',fail)
    with pytest.raises(RuntimeError,match='programming defect'):run_packet(packet())


@pytest.mark.parametrize('corruption',['time','shape','nan','energy_overflow'])
def test_invalid_solver_output_not_exported(corruption,monkeypatch):
    from emfeeld import trajectory_samples as ts
    real=ts.integrate
    def broken(*a,**kw):
        tr=real(*a,**kw)
        if corruption=='time':return replace(tr,time_s=tr.time_s+0.01)
        if corruption=='shape':return replace(tr,position_m=tr.position_m[:-1])
        if corruption=='nan':return replace(tr,velocity_m_s=tr.velocity_m_s*np.nan)
        return replace(tr,kinetic_J=np.full_like(tr.kinetic_J,1e308),potential_J=np.full_like(tr.potential_J,1e308))
    monkeypatch.setattr(ts,'integrate',broken)
    r=run_packet(packet());assert r['results'][0]['status']=='numerical_error'
    assert r['results'][0]['value'] is None;json.dumps(r,allow_nan=False)


def test_cli_mixed_packet_and_failed_selection_exit_codes(tmp_path,capsys):
    p=tmp_path/'packet.json';out=tmp_path/'result.json'
    data=packet([req('speed'),{'id':'V','type':'potential','position_m':[1,0,0]}]);p.write_text(json.dumps(data))
    assert main([str(p),'--output',str(out)])==0
    assert json.loads(capsys.readouterr().out)==json.loads(out.read_text())
    data['observations'][0]=req('speed',time_s=0.26,time_selection='exact');p.write_text(json.dumps(data))
    assert main([str(p),'--output',str(out)])==1
    assert json.loads(capsys.readouterr().out)['status']=='partial'
    data['observations'][0]['particle_index']=100;p.write_text(json.dumps(data))
    previous=out.read_bytes()
    assert main([str(p),'--output',str(out)])==2 and out.read_bytes()==previous
    assert capsys.readouterr().err


def test_headless_module_execution_does_not_import_viewer(tmp_path):
    p=tmp_path/'request.json';p.write_text(json.dumps(packet()))
    code='import json, sys; from emfeeld.observations import run_packet; r=run_packet(json.load(open(sys.argv[1]))); assert r["status"]=="ok"; assert "pyvista" not in sys.modules; assert "emfeeld.viewer" not in sys.modules'
    subprocess.run([sys.executable,'-c',code,str(p)],check=True)
    proc=subprocess.run([sys.executable,'-m','emfeeld.observations',str(p)],check=True,capture_output=True,text=True)
    assert json.loads(proc.stdout)['results'][0]['status']=='ok'


EXAMPLES=Path(__file__).resolve().parents[1]/'examples/trajectory_observations'
ENTRIES=json.loads((EXAMPLES/'manifest.json').read_text())['examples']


@pytest.mark.parametrize('entry',ENTRIES,ids=lambda x:x['file'])
def test_authored_trajectory_packets(entry):
    p=json.loads((EXAMPLES/entry['file']).read_text())
    r=run_packet(p)
    assert r['status']==entry['expected_status']
    assert r['counts']['requests']==entry['requests'] and r['counts']['failed_expectations']==0
    failures={status:sum(row['status']==status for row in r['results'])
              for status in {row['status'] for row in r['results']} if status!='ok'}
    assert failures==entry['expected_failures']
    if entry['original_scene']:
        original=json.loads((EXAMPLES.parents[1]/entry['original_scene']).read_text())
        assert p['scene']==original
    json.dumps(r,allow_nan=False)


def test_time_tolerance_boundary_and_no_outside_clamping():
    r=result(packet([req('speed',time_s=.375,time_selection='nearest',max_time_error_s=.125)]))
    assert r['sample_index']==1 and r['time_offset_s']==-.125
    p=packet([req('speed',time_s=.375,time_selection='nearest',max_time_error_s=float(np.nextafter(.125,0)))])
    assert result(p)['status']=='selection_error'
    with pytest.raises(ValueError):
        run_packet(packet([req(time_s=2.01,time_selection='nearest',max_time_error_s=100)]))


def test_singular_endpoint_failure_never_exports_an_initial_state_as_success():
    p=packet();p['scene']['sources']=[{'type':'point','charge_C':1}]
    p['scene']['particles'][0].update(position_m=[0,0,0],charge_C=0)
    p['observations']=[req(sample_index=0)]
    r=result(p)
    assert r['status']=='domain_error' and r['value'] is None
    assert 'time_s' not in r


def test_expectation_on_failed_selection_is_not_evaluated():
    p=packet([dict(req('speed',time_s=.26,time_selection='exact'),expectation={'value':0,'atol':1,'rtol':0})])
    r=result(p)
    assert r['status']=='selection_error' and r['check']=={'passed':None,'reason':'not_evaluated'}


def test_machine_trajectory_contract_matches_runtime():
    from emfeeld.trajectory_samples import QUANTITIES,SOLVER_SETTINGS
    root=Path(__file__).resolve().parents[1]
    c=json.loads((root/'docs/trajectory_sample_contract_v1.json').read_text())
    static=json.loads((root/'docs/observation_contract_v1.json').read_text())
    assert static['packet_extensions']['trajectory_sample']=='trajectory_sample_contract_v1.json'
    assert set(c['quantities'])==set(QUANTITIES)
    for q,(unit,shape) in QUANTITIES.items():
        assert c['quantities'][q]=={'unit':unit,'shape':list(shape)}
    for name,value in SOLVER_SETTINGS.items():assert c['solver'][name]==value
    assert set(c['result_statuses'])=={'ok','selection_error','unsupported_trajectory','domain_error','numerical_error','integration_error'}
