"""Source-first provenance/coverage tests; never certify authored prose as physics."""
from copy import deepcopy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'verification/question_first_trial_v1.py'
SPEC = importlib.util.spec_from_file_location('question_first_trial_v1', SCRIPT)
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)
QUESTION = ROOT / 'examples/question_first_v1/developer_question.json'
PACKET = ROOT / 'examples/question_first_v1/developer_packet.json'


def _fixture(tmp_path):
    src = tmp_path / 'question.json'
    src.write_bytes(QUESTION.read_bytes())
    packet = tmp_path / 'packet.json'
    packet.write_bytes(PACKET.read_bytes())
    return src, packet


def _mutate(path, fn):
    data = json.loads(path.read_text(encoding='utf-8'))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def test_source_first_gravity_question_retains_raw_bytes_and_answers_all_requests(tmp_path):
    source, packet = _fixture(tmp_path)
    lock, output = tmp_path/'locked', tmp_path/'attempt'
    before_q, before_p = source.read_bytes(), packet.read_bytes()
    receipt = trial.freeze(source, lock)
    assert (lock/'question.json').read_bytes() == before_q
    assert receipt['question_sha256'] == trial._sha(before_q)
    assert receipt['physical_interpretation'] == 'not_verified'
    assessment = trial.assess(lock, packet, output)
    assert assessment['native_measurement_coverage'] == 'complete'
    assert assessment['interpretation_fidelity'] == 'not_verified'
    assert assessment['independent_physics_correctness'] == 'not_evaluated'
    assert assessment['educational_usefulness'] == 'not_evaluated'
    assert assessment['textbook_answer_completeness'] == 'not_evaluated'
    assert assessment['frozen_question_sha256'] == trial._sha(before_q)
    assert assessment['authored_packet_sha256'] == trial._sha(before_p)
    assert (output/'question.json').read_bytes() == before_q
    assert (output/'packet.json').read_bytes() == before_p
    assert source.read_bytes() == before_q and packet.read_bytes() == before_p
    assert json.loads((output/'state.json').read_text())['execution_complete'] is True

    report = json.loads((output/'native-result.json').read_text())
    values = {r['id']: r for r in report['results']}
    assert set(values) == set(receipt['requested_ids'])
    assert values['field_launch']['value'] == [0., -2., 0.]
    for actual, expected in zip(values['position_final']['value'], (1.8, 0.4, 0.2)):
        assert math.isclose(actual, expected, abs_tol=1e-9, rel_tol=0)
    for actual, expected in zip(values['velocity_final']['value'], (0.4, -2.8, 0.1)):
        assert math.isclose(actual, expected, abs_tol=1e-9, rel_tol=0)
    assert math.isclose(values['total_energy_initial']['value'], 12.0125,
                        abs_tol=1e-10, rel_tol=0)
    assert math.isclose(values['total_energy_final']['value'], 12.0125,
                        abs_tol=1e-10, rel_tol=0)
    assert values['position_final']['sample_index'] == 20
    assert values['position_final']['time_s'] == 2


def test_public_cli_freeze_then_assess_without_json_answer_in_source(tmp_path):
    q, packet = _fixture(tmp_path)
    lock, output = tmp_path/'lock', tmp_path/'run'
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT/'src') + os.pathsep + env.get('PYTHONPATH', '')
    base = [sys.executable, str(SCRIPT)]
    frozen = subprocess.run(base + ['freeze', str(q), '--output', str(lock)],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert frozen.returncode == 0, frozen.stderr
    assert json.loads(frozen.stdout)['source_authenticity'] == 'not_authenticated'
    checked = subprocess.run(base + ['assess', str(lock), '--packet', str(packet),
                                     '--output', str(output)],
                             cwd=ROOT, env=env, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout) == json.loads((output/'assessment.json').read_text())
    assert not any('expectation' in o for o in json.loads(packet.read_text())['observations'])


@pytest.mark.parametrize('change', ['source', 'receipt', 'missing_receipt'])
def test_changed_frozen_input_or_receipt_fails_before_new_writes(tmp_path, change):
    q, packet = _fixture(tmp_path)
    lock, output = tmp_path/'lock', tmp_path/'out'
    trial.freeze(q, lock)
    if change == 'source':
        _mutate(lock/'question.json', lambda d: d['source'].update(question='Different physics question'))
    if change == 'receipt':
        _mutate(lock/'receipt.json', lambda d: d.update(source_authenticity='teacher_verified'))
    if change == 'missing_receipt':
        (lock/'receipt.json').unlink()
    with pytest.raises((ValueError, OSError)):
        trial.assess(lock, packet, output)
    assert not output.exists()


@pytest.mark.parametrize('change', ['missing', 'extra', 'renamed', 'expectation'])
def test_packet_source_mismatch_and_embedded_answers_refused_before_execution(tmp_path, change):
    q, packet = _fixture(tmp_path)
    lock, output = tmp_path/'lock', tmp_path/'out'
    trial.freeze(q, lock)
    def change_packet(data):
        rows = data['observations']
        if change == 'missing': rows.pop()
        if change == 'extra': rows.append({'id':'unasked','type':'field','position_m':[1,2,0]})
        if change == 'renamed': rows[0]['id'] = 'unasked'
        if change == 'expectation':
            rows[0]['expectation'] = {'value':[0,-2,0], 'atol':0, 'rtol':0}
    _mutate(packet, change_packet)
    with pytest.raises(ValueError, match='observation IDs|authored answers'):
        trial.assess(lock, packet, output)
    assert not output.exists()


@pytest.mark.parametrize('field,content', [
    ('unresolved_information', ['charge source strength was never supplied']),
    ('requirements', ['fixed_prescribed_sources','conductor_polarization']),
    ('requirements', ['magnetic_lorentz_force']),
])
def test_declared_unsupported_or_unresolved_physics_stops_before_solver(tmp_path, monkeypatch, field, content):
    q, packet = _fixture(tmp_path)
    _mutate(q, lambda d: d.update({field: content}))
    lock, output = tmp_path/'lock', tmp_path/'out'
    trial.freeze(q, lock)
    monkeypatch.setattr(trial, 'run_packet', lambda *_: pytest.fail('unsupported physics executed'))
    with pytest.raises(ValueError, match='unresolved|unsupported'):
        trial.assess(lock, packet, output)
    assert not output.exists()
    assert (lock/'question.json').exists()  # retain honest original unsupported source


@pytest.mark.parametrize('damage', [
    lambda d: d.update(trial_version=True),
    lambda d: d.update(trial_version=2),
    lambda d: d.update(teacher_verified=True),
    lambda d: d['source'].update(origin='teacher_certified'),
    lambda d: d['requested_measurements'].append(deepcopy(d['requested_measurements'][0])),
    lambda d: d['requested_measurements'][0].update(extra='claim'),
    lambda d: d['requirements'].append('fixed_prescribed_sources'),
    lambda d: d.update(requested_measurements=[]),
])
def test_invalid_question_claims_and_schema_rejected_before_lock(tmp_path, damage):
    q, _ = _fixture(tmp_path)
    _mutate(q, damage)
    output = tmp_path/'lock'
    with pytest.raises(ValueError):
        trial.freeze(q, output)
    assert not output.exists()


@pytest.mark.parametrize('raw', [
    b'{"trial_version":1,"trial_version":1}',
    b'{"trial_version":NaN}',
    b'\xff\xfe',
    b'[' + b'1'* (trial.QUESTION_LIMIT + 1) + b']',
])
def test_bad_json_unbounded_or_nonutf8_rejected_without_writes(tmp_path, raw):
    p = tmp_path/'bad.json'
    p.write_bytes(raw)
    with pytest.raises((ValueError, UnicodeDecodeError, json.JSONDecodeError)):
        trial.freeze(p, tmp_path/'lock')
    assert not (tmp_path/'lock').exists()


def test_undeclared_source_truth_not_upgraded_to_teacher_certification(tmp_path):
    q, packet = _fixture(tmp_path)
    _mutate(q, lambda d: d['source'].update(origin='external_unverified',
                                             label='Claims a teacher likes this exercise'))
    lock, out = tmp_path/'lock', tmp_path/'run'
    trial.freeze(q, lock)
    result = trial.assess(lock, packet, out)
    assert result['native_measurement_coverage'] == 'complete'
    assert result['original_declared_source_origin'] == 'external_unverified'
    assert result['interpretation_fidelity'] == 'not_verified'
    assert result['educational_usefulness'] == 'not_evaluated'
    assert 'Claims a teacher' not in (out/'assessment.json').read_text()


def test_actual_native_domain_error_cannot_be_called_covered(tmp_path):
    q, packet = _fixture(tmp_path)
    def change_question(d):
        d['requested_measurements']=[{'id':'undefined_field','quantity':'field at singular point','unit':'N/C', 'native_type':'field','context':{'position_m':[0,0,0]}}]
        d['source']['question']='An undefined point-source center field is requested.'
    def change_packet(d):
        d['scene']['kind']='electric'
        d['scene']['sources']=[{'type':'point','charge_C':1e-9,'center_m':[0,0,0]}]
        d['scene']['particles']=[]
        d['observations']=[{'id':'undefined_field','type':'field','position_m':[0,0,0]}]
    _mutate(q, change_question)
    _mutate(packet, change_packet)
    lock, out = tmp_path/'lock', tmp_path/'run'
    trial.freeze(q, lock)
    report = trial.assess(lock, packet, out)
    assert report['native_measurement_coverage'] == 'incomplete'
    assert any('domain_error' in x for x in report['issues'])
    assert json.loads((out/'state.json').read_text())['execution_complete'] is True
    assert json.loads((out/'native-result.json').read_text())['results'][0]['value'] is None


def test_bad_units_are_retained_as_incomplete_not_silent_success(tmp_path):
    q, packet = _fixture(tmp_path)
    _mutate(q, lambda d: d['requested_measurements'][1].update(unit='km'))
    lock, out = tmp_path/'lock', tmp_path/'run'
    trial.freeze(q, lock)
    report = trial.assess(lock, packet, out)
    assert report['native_measurement_coverage'] == 'incomplete'
    assert 'position_final: expected unit km' in report['issues']
    assert (out/'native-result.json').is_file()


def test_no_event_is_not_success_even_when_packet_aggregate_claims_ok(tmp_path, monkeypatch):
    q, packet = _fixture(tmp_path)
    lock, out = tmp_path/'lock', tmp_path/'run'
    trial.freeze(q, lock)
    source_engine = trial.run_packet
    def fake_native(data):
        report = source_engine(data)
        report['results'][1]['status'] = 'no_event'
        report['results'][1]['value'] = None
        # Intentionally inconsistent aggregate to test fail-closed per-request.
        report['status'] = 'ok'
        return report
    monkeypatch.setattr(trial, 'run_packet', fake_native)
    result = trial.assess(lock, packet, out)
    assert result['native_measurement_coverage'] == 'incomplete'
    assert 'position_final: native status no_event' in result['issues']


@pytest.mark.parametrize('where', ['existing', 'inside_lock', 'alias_packet'])
def test_destination_safety_no_overwrite(tmp_path, where):
    q, packet = _fixture(tmp_path)
    lock = tmp_path/'lock'
    trial.freeze(q, lock)
    out = tmp_path/'run' if where == 'existing' else lock/'new_output' if where == 'inside_lock' else packet
    if where == 'existing':
        out.mkdir()
        (out/'old.txt').write_text('preserve')
    with pytest.raises((ValueError, OSError)):
        trial.assess(lock, packet, out)
    if where == 'existing':
        assert (out/'old.txt').read_text() == 'preserve'
    if where == 'inside_lock':
        assert not out.exists()
    if where == 'alias_packet':
        assert out.read_bytes() == PACKET.read_bytes()


def test_interrupted_attempt_is_not_written_as_complete(tmp_path, monkeypatch):
    q, packet = _fixture(tmp_path)
    lock, out = tmp_path/'lock', tmp_path/'out'
    trial.freeze(q, lock)
    def crash(_):
        raise RuntimeError('unexpected solver exception')
    monkeypatch.setattr(trial, 'run_packet', crash)
    with pytest.raises(RuntimeError, match='unexpected solver'):
        trial.assess(lock, packet, out)
    assert json.loads((out/'state.json').read_text())['execution_complete'] is False
    assert (out/'question.json').exists() and (out/'packet.json').exists()
    assert not (out/'assessment.json').exists()


@pytest.mark.parametrize('mutation', [
    'static_wrong_point', 'static_wrong_declared_point', 'trajectory_wrong_index',
    'trajectory_wrong_particle', 'trajectory_nearest', 'event_request',
])
def test_frozen_measurement_context_cannot_silently_retarget(tmp_path, mutation):
    q, packet = _fixture(tmp_path)
    if mutation == 'static_wrong_declared_point':
        _mutate(q, lambda d: d['requested_measurements'][0]['context'].update(position_m=[4, 0, 0]))
    else:
        def adjust(d):
            if mutation == 'static_wrong_point':
                d['observations'][0]['position_m'] = [4, 0, 0]
            if mutation == 'trajectory_wrong_index':
                d['observations'][1]['sample_index'] = 19
            if mutation == 'trajectory_wrong_particle':
                d['observations'][1]['particle_index'] = 1
                d['scene']['particles'].append(deepcopy(d['scene']['particles'][0]))
            if mutation == 'trajectory_nearest':
                d['observations'][1].pop('sample_index')
                d['observations'][1].update(time_s=1.94, time_selection='nearest', max_time_error_s=0.1)
            if mutation == 'event_request':
                d['observations'][1] = {
                    'id': 'position_final', 'type': 'trajectory_event', 'particle_index': 0,
                    'condition': {'type': 'plane', 'point_m': [100, 0, 0], 'normal': [1, 0, 0], 'direction': 'positive'},
                    'occurrence': 'first', 'max_step_s': 0.05, 'min_normal_speed_m_s': 1e-8,
                    'accuracy': {'time_atol_s': 1e-6, 'position_atol_m': 1e-6,
                                 'velocity_atol_m_s': 1e-6, 'rtol': 1e-8}}
        _mutate(packet, adjust)
    lock, out = tmp_path/'lock', tmp_path/'run'
    trial.freeze(q, lock)
    with pytest.raises(ValueError, match='context|V1 supports|quantity/type'):
        trial.assess(lock, packet, out)
    assert not out.exists()


def test_native_report_wrong_actual_time_is_recorded_incomplete(tmp_path, monkeypatch):
    q, packet = _fixture(tmp_path)
    lock, out = tmp_path/'lock', tmp_path/'run'
    trial.freeze(q, lock)
    native_impl = trial.run_packet
    def wrong_time(data):
        record = native_impl(data)
        record['results'][1]['time_s'] = 1.9  # stale/retargeted saved state
        return record
    monkeypatch.setattr(trial, 'run_packet', wrong_time)
    result = trial.assess(lock, packet, out)
    assert result['native_measurement_coverage'] == 'incomplete'
    assert 'position_final: actual saved time disagrees with frozen context' in result['issues']


@pytest.mark.parametrize('kind', ['energy_swap', 'same_unit_speed_swap', 'wrong_native_type'])
def test_native_quantity_substitution_is_rejected_before_integration(tmp_path, kind):
    q, packet = _fixture(tmp_path)
    def changed(d):
        rows=d['observations']
        if kind=='energy_swap':
            rows[-1]['quantity']='potential_energy'  # same J unit as total energy
        if kind=='same_unit_speed_swap':
            rows[2]['quantity']='speed'  # scalar, same m/s unit as velocity
        if kind=='wrong_native_type':
            rows[0].update(type='potential')  # even if ID and point unchanged
    _mutate(packet, changed)
    lock,out=tmp_path/'lock',tmp_path/'run'
    trial.freeze(q,lock)
    with pytest.raises(ValueError,match='quantity/type'):
        trial.assess(lock,packet,out)
    assert not out.exists()


def test_native_result_quantity_mutation_cannot_claim_coverage(tmp_path, monkeypatch):
    q,packet=_fixture(tmp_path)
    lock,out=tmp_path/'lock',tmp_path/'run'
    trial.freeze(q,lock)
    native_impl=trial.run_packet
    def false_native(data):
        report=native_impl(data)
        report['results'][-1]['quantity']='potential_energy'
        return report
    monkeypatch.setattr(trial,'run_packet',false_native)
    result=trial.assess(lock,packet,out)
    assert result['native_measurement_coverage']=='incomplete'
    assert 'total_energy_final: native reported quantity/type changed' in result['issues']
