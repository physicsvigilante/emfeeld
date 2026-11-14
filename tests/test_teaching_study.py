"""Teaching studies: interpretation boundaries, one-change identity and physics checks."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.constants import G, epsilon_0
from scipy.optimize import brentq

from emfeeld import study
from emfeeld.observations import run_packet
from emfeeld.scene import scene_from_dict

ROOT = Path(__file__).resolve().parents[1]


def example(name='electric'):
    return json.loads((ROOT / f'examples/studies/{name}.json').read_text())


def execute(tmp_path, data=None, name='study'):
    path = tmp_path / (name + '.json')
    path.write_text(json.dumps(data or example()))
    output = tmp_path / name
    return study.run_study(path, output), output


def test_only_one_physical_value_changes_and_input_is_immutable():
    data = example(); saved = deepcopy(data)
    models, issues = study.validate_study(data)
    assert not issues and data == saved
    variant = deepcopy(models['variant'])
    variant['scene']['sources'][0]['charge_C'] = data['change']['from_value']
    assert variant == models['baseline']
    assert models['baseline'] == data['baseline']


@pytest.mark.parametrize('field,value', [
    ('source_index', True), ('source_index', -1), ('source_index', 99),
    ('parameter', 'radius_m'), ('parameter', 'origin_m'), ('parameter', 'velocity_m_s'),
    ('from_value', True), ('to_value', '1'), ('to_value', float('nan')),
    ('from_value', 999), ('origin', 'inferred_truth'), ('reason', ''),
])
def test_invalid_changes_are_not_silently_repaired(field, value):
    data = example(); data['change'][field] = value
    with pytest.raises(ValueError): study.validate_study(data)


def test_noop_and_unknown_keys_rejected():
    data = example(); data['change']['to_value'] = data['change']['from_value']
    with pytest.raises(ValueError): study.validate_study(data)
    data = example(); data['new_geometry'] = [1, 2, 3]
    with pytest.raises(ValueError): study.validate_study(data)


@pytest.mark.parametrize('name', ['position_atol_m', 'velocity_atol_m_s', 'rtol', 'max_normalized_energy_drift'])
@pytest.mark.parametrize('value', [0, -1, True, '0.1'])
def test_explicit_finite_check_settings(name, value):
    data = example(); data['checks'][name] = value
    with pytest.raises(ValueError): study.validate_study(data)


def test_conductor_requirement_stops_before_any_calculation(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'run_packet', lambda *a, **k: pytest.fail('physics must not run'))
    report, output = execute(tmp_path, example('unsupported_conductor'))
    assert not report['execution_complete'] and not report['configurations']
    assert report['issues']['study']['status'] == 'unsupported'
    assert (output / 'REPORT.md').is_file()


def test_missing_information_stays_missing(tmp_path, monkeypatch):
    data = example(); data['interpretation']['unresolved'] = ['The initial speed is unspecified.']
    monkeypatch.setattr(study, 'run_packet', lambda *a, **k: pytest.fail('physics must not run'))
    report, _ = execute(tmp_path, data)
    assert report['issues']['study']['status'] == 'incomplete'
    assert not report['execution_complete']


def test_invalid_variant_preserves_valid_baseline(tmp_path):
    data = example('gravity'); data['change']['to_value'] = -1
    report, output = execute(tmp_path, data)
    assert set(report['configurations']) == {'baseline'}
    assert report['issues']['variant']['status'] == 'invalid_model'
    assert (output / 'variant' / 'rejection.json').is_file()
    assert not report['execution_complete']


def test_unknown_source_does_not_become_uniform_sphere(tmp_path):
    data = example(); data['baseline']['scene']['sources'][0]['type'] = 'conducting_sphere'
    report, _ = execute(tmp_path, data)
    assert report['issues']['baseline']['status'] == 'invalid_model'
    assert not report['configurations']


def test_capture_reuses_sample_run_and_preserves_original_results(monkeypatch):
    import emfeeld.trajectory_samples as samples
    original = samples.integrate
    calls = []
    def counted(*args, **kwargs):
        calls.append(1); return original(*args, **kwargs)
    monkeypatch.setattr(samples, 'integrate', counted)
    packet = example()['baseline']
    capture = {}; result = run_packet(packet, capture=capture)
    assert len(calls) == 1
    assert np.array_equal(result['results'][2]['value'], capture['trajectories'][0].position_m[50])
    reference = run_packet(packet)
    assert reference['results'] == result['results']
    with pytest.raises(ValueError): run_packet(packet, capture=capture)


def test_static_packet_no_capture_does_not_integrate_but_study_capture_does(monkeypatch):
    import emfeeld.trajectory_samples as samples
    packet = example()['baseline']; packet['observations'] = packet['observations'][:2]
    original = samples.integrate; calls = []
    def counted(*args, **kwargs):
        calls.append(1); return original(*args, **kwargs)
    monkeypatch.setattr(samples, 'integrate', counted)
    run_packet(packet); assert not calls
    capture = {}; run_packet(packet, capture=capture)
    assert len(calls) == 1 and len(capture['trajectories']) == 1


def test_electric_full_trajectories_match_separate_harmonic_reference(tmp_path):
    report, output = execute(tmp_path)
    assert report['execution_complete']
    k = 1 / (4*np.pi*epsilon_0)
    for name in study.CONFIGURATIONS:
        scene, (trajectory,) = study.load_recorded(output / name)
        packet = json.loads((output/name/'packet.json').read_text())
        s = packet['scene']; p = s['particles'][0]
        sources = s['sources']; r0 = np.array(p['position_m']); v0 = np.array(p['velocity_m_s'])
        weights = np.array([-k*x['charge_C']/x['radius_m']**3 * p['charge_C']/p['mass_kg'] for x in sources])
        centres = np.array([x['center_m'] for x in sources]); omega = np.sqrt(weights.sum())
        equilibrium = (weights[:,None]*centres).sum(axis=0)/weights.sum()
        t = trajectory.time_s[:,None]
        r = equilibrium + (r0-equilibrium)*np.cos(omega*t) + v0/omega*np.sin(omega*t)
        v = -(r0-equilibrium)*omega*np.sin(omega*t)+v0*np.cos(omega*t)
        for source in sources:
            assert np.all(np.linalg.norm(r-np.array(source['center_m']),axis=1)<source['radius_m'])
        np.testing.assert_allclose(trajectory.position_m,r,atol=2e-8,rtol=2e-8)
        np.testing.assert_allclose(trajectory.velocity_m_s,v,atol=2e-8,rtol=2e-8)
        result = json.loads((output/name/'result.json').read_text())
        field = sum(k*x['charge_C']*(r0-np.array(x['center_m']))/x['radius_m']**3 for x in sources)
        potential = sum(k*x['charge_C']*(3-np.sum((r0-np.array(x['center_m']))**2)/x['radius_m']**2)/(2*x['radius_m']) for x in sources)
        np.testing.assert_allclose(result['results'][0]['value'],field,rtol=2e-13)
        assert result['results'][1]['value'] == pytest.approx(potential,rel=2e-13)
    assert len(report['evaluation']) == 5
    assert report['evaluation']['educational_usefulness'] == 'awaiting teacher task feedback'


def test_gravity_reuses_sun_scene_and_matches_kepler_reference(tmp_path):
    data = example('gravity')
    assert data['baseline']['scene'] == json.loads((ROOT/'examples/ideal_sun.json').read_text())
    report, output = execute(tmp_path,data)
    assert report['execution_complete']
    for name in study.CONFIGURATIONS:
        scene, trajectories = study.load_recorded(output/name)
        mu = G*scene.model.sources[0].strength
        for particle, trajectory in zip(scene.particles, trajectories):
            r0=np.array(particle.position_m);v0=np.array(particle.velocity_m_s)
            radius=np.linalg.norm(r0);speed=np.linalg.norm(v0)
            eccentricity=max(0.,1-speed**2*radius/mu)
            a=radius/(1+eccentricity);n=np.sqrt(mu/a**3)
            peri=-r0/radius; transverse=-v0/speed
            for index in (0,250,500,750,1000):
                mean=np.pi+n*trajectory.time_s[index]
                anomaly=mean if eccentricity<1e-14 else brentq(lambda E:E-eccentricity*np.sin(E)-mean,mean-eccentricity-1e-12,mean+eccentricity+1e-12,xtol=1e-13)
                r=a*(np.cos(anomaly)-eccentricity)*peri+a*np.sqrt(1-eccentricity**2)*np.sin(anomaly)*transverse
                np.testing.assert_allclose(trajectory.position_m[index],r,atol=2.,rtol=2e-10)
    assert report['comparisons'][0]['variant'][0] == pytest.approx(1.2*report['comparisons'][0]['baseline'][0],rel=1e-12)


@pytest.mark.parametrize('name', ['packet.json','result.json','checks.json','trajectories.npz'])
def test_modified_capture_refuses_visualization(tmp_path,name):
    _, output=execute(tmp_path)
    path=output/'baseline'/name;path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='hash mismatch'):study.load_recorded(output/'baseline')


def test_output_directory_is_never_overwritten(tmp_path,monkeypatch):
    _, output=execute(tmp_path)
    previous=(output/'summary.json').read_bytes()
    monkeypatch.setattr(study,'run_packet',lambda *a,**k:pytest.fail('must reject before physics'))
    with pytest.raises(FileExistsError):study.run_study(tmp_path/'study.json',output)
    assert (output/'summary.json').read_bytes()==previous


def test_no_event_is_not_a_completed_requested_measurement(tmp_path):
    data=example();data['baseline']['observations']=[{
        'id':'missing','type':'trajectory_event','particle_index':0,
        'condition':{'type':'plane','point_m':[1000,0,0],'normal':[1,0,0],'direction':'either'},
        'occurrence':'first','max_step_s':.01,'min_normal_speed_m_s':1e-7,
        'accuracy':{'time_atol_s':1e-6,'position_atol_m':1e-6,'velocity_atol_m_s':1e-6,'rtol':1e-7}}]
    report,_=execute(tmp_path,data)
    assert not report['execution_complete']
    for config in report['configurations'].values():assert config['unfulfilled_requests']=={'missing':'no_event'}
    assert report['comparisons'][0]['comparison']=='not_available'


def test_failed_particle_does_not_hide_valid_probes_or_other_particle(tmp_path):
    data=example();s=data['baseline']['scene']
    s['sources'].append({'type':'point','charge_C':1e-15,'center_m':[10,0,0]})
    s['particles'].append({'mass_kg':1,'charge_C':1,'position_m':[10,0,0],'velocity_m_s':[0,0,0]})
    report,output=execute(tmp_path,data)
    assert not report['execution_complete']
    assert report['configurations']['baseline']['request_statuses']['field_probe']=='ok'
    assert not report['configurations']['baseline']['render_ready']
    with pytest.raises(ValueError,match='preview unavailable'):study.load_recorded(output/'baseline')


def test_failed_numerical_check_retained_and_blocks_preview(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'check_trajectory',lambda *a:{'passed':False,'reason':'injected refinement failure'})
    report,output=execute(tmp_path)
    assert not report['execution_complete']
    assert report['configurations']['baseline']['request_statuses']['position_half']=='ok'
    with pytest.raises(ValueError,match='preview unavailable'):study.load_recorded(output/'baseline')


def test_loading_never_calls_integrator(tmp_path,monkeypatch):
    _,output=execute(tmp_path)
    monkeypatch.setattr(study,'integrate',lambda *a,**k:pytest.fail('unexpected reintegration'))
    scene,ts=study.load_recorded(output/'baseline')
    assert len(ts)==len(scene.particles)==1


def test_static_only_study_and_zero_source_are_valid(tmp_path):
    data=example();data['baseline']['scene']['particles']=[]
    data['baseline']['observations']=data['baseline']['observations'][:2]
    data['change']['to_value']=0
    report,output=execute(tmp_path,data)
    assert report['execution_complete']
    assert study.load_recorded(output/'variant')[1]==()


def test_cli_exit_codes_and_duplicate_input(tmp_path,capsys):
    path=tmp_path/'input.json';path.write_text(json.dumps(example('unsupported_conductor')))
    assert study.main(['run',str(path),'--output',str(tmp_path/'out')])==1
    path.write_text('{"study_version":1,"study_version":1}')
    assert study.main(['run',str(path),'--output',str(tmp_path/'bad')])==2
    assert not (tmp_path/'bad').exists()
