"""Published-source *non-blind* rehearsal; never claim teacher or blind grading."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'examples/nasa_ion_public_v0'
SPEC = importlib.util.spec_from_file_location('nasa_ion_trial_v0', ROOT/'verification/question_first_trial_v1.py')
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)
EXPECTED_QUESTION_SHA = 'cd797751a84d86caa57c2024620215895c1414169c6682b96933e4b4cf25cc23'
EXPECTED_PACKET_SHA = 'f86211065ec99e3e82181de256d321a6ebb054f9b397440996529a3ec6ccfeda'
MASS_KG, CHARGE_C, VOLTAGE_V, GAP_M = 2.2e-25, 1.6e-19, 1300., 0.7e-3


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expected_exit_time() -> float:
    field = VOLTAGE_V / GAP_M
    return math.sqrt(2*GAP_M/(CHARGE_C*field/MASS_KG))


def test_exact_source_first_lock_and_no_answer_embedded_in_packet():
    question_bytes, packet_bytes = (DATA/'question.json').read_bytes(), (DATA/'packet.json').read_bytes()
    receipt = json.loads((DATA/'receipt.json').read_text(encoding='utf-8'))
    question = json.loads(question_bytes)
    packet = json.loads(packet_bytes)
    assert _sha(question_bytes) == receipt['question_sha256'] == EXPECTED_QUESTION_SHA
    assert _sha(packet_bytes) == EXPECTED_PACKET_SHA
    assert receipt == trial._receipt(question_bytes, question)
    assert question['source']['origin'] == 'external_unverified'
    assert 'NASA Space Math' in question['source']['label']
    assert receipt['source_authenticity'] == 'not_authenticated'
    assert receipt['physical_interpretation'] == 'not_verified'
    assert len(packet['observations']) == 1
    assert packet['observations'][0]['id'] == 'exit_speed_native'
    assert all('expectation' not in obs for obs in packet['observations'])
    assert question['requested_measurements'][0]['unit'] == 'm/s'
    assert question['requested_measurements'][0]['context']['sample_index'] == 20


def test_original_public_source_first_coverage_vs_same_author_reference(tmp_path):
    before_q, before_p = (DATA/'question.json').read_bytes(), (DATA/'packet.json').read_bytes()
    assessment = trial.assess(DATA, DATA/'packet.json', tmp_path/'evidence')
    assert assessment['native_measurement_coverage'] == 'complete'
    assert assessment['issues'] == []
    assert assessment['requested_observations'] == 1
    for key, value in (
        ('interpretation_fidelity', 'not_verified'),
        ('independent_physics_correctness', 'not_evaluated'),
        ('educational_usefulness', 'not_evaluated'),
        ('textbook_answer_completeness', 'not_evaluated'),
    ):
        assert assessment[key] == value
    evidence = tmp_path/'evidence'
    result = json.loads((evidence/'native-result.json').read_text(encoding='utf-8'))
    assert result['status'] == 'ok' and len(result['results']) == 1
    native = result['results'][0]
    assert native['id'] == 'exit_speed_native' and native['status'] == 'ok'
    assert native['quantity'] == 'speed' and native['unit'] == 'm/s'
    assert native['sample_index'] == 20
    assert math.isclose(native['time_s'], _expected_exit_time(), rel_tol=1e-14)
    expected_speed = math.sqrt(2*CHARGE_C*VOLTAGE_V/MASS_KG)
    assert math.isclose(native['value'], expected_speed, rel_tol=1e-9, abs_tol=0)
    assert math.isclose(native['value']*3.6, expected_speed*3.6, rel_tol=1e-9)
    assert math.isclose(result['input']['scene']['sources'][0]['field_N_C'][0],
                        VOLTAGE_V/GAP_M, rel_tol=1e-14)
    assert _sha((evidence/'native-result.json').read_bytes()) == assessment['native_report_sha256']
    assert json.loads((evidence/'state.json').read_text())['execution_complete'] is True
    assert (evidence/'question.json').read_bytes() == (DATA/'question.json').read_bytes() == before_q
    assert (evidence/'packet.json').read_bytes() == (DATA/'packet.json').read_bytes() == before_p


def test_wrong_frozen_exit_instant_is_incomplete_and_original_stays_fixed(tmp_path):
    source = json.loads((DATA/'question.json').read_text(encoding='utf-8'))
    source['requested_measurements'][0]['context']['time_s'] = _expected_exit_time()*0.9
    changed_question = tmp_path/'different-question.json'
    changed_question.write_text(json.dumps(source), encoding='utf-8')
    lock, output = tmp_path/'alternative-lock', tmp_path/'attempt'
    trial.freeze(changed_question, lock)
    outcome = trial.assess(lock, DATA/'packet.json', output)
    assert outcome['native_measurement_coverage'] == 'incomplete'
    assert 'exit_speed_native: actual saved time disagrees with frozen context' in outcome['issues']
    assert json.loads((output/'state.json').read_text())['execution_complete'] is True
    assert _sha((DATA/'question.json').read_bytes()) == EXPECTED_QUESTION_SHA


def test_false_numeric_interpretation_cannot_be_certified_by_structural_coverage(tmp_path):
    """Wrong source strength may still give native coverage: interpretation is distinct."""
    packet = json.loads((DATA/'packet.json').read_text(encoding='utf-8'))
    packet['scene']['sources'][0]['field_N_C'][0] *= 2
    wrong = tmp_path/'wrong-field.json'
    wrong.write_text(json.dumps(packet), encoding='utf-8')
    report = trial.assess(DATA, wrong, tmp_path/'wrong-attempt')
    assert report['native_measurement_coverage'] == 'complete'
    assert report['interpretation_fidelity'] == 'not_verified'
    assert report['independent_physics_correctness'] == 'not_evaluated'
    actual = json.loads((tmp_path/'wrong-attempt/native-result.json').read_text())['results'][0]['value']
    expected = math.sqrt(2*CHARGE_C*VOLTAGE_V/MASS_KG)
    assert not math.isclose(actual, expected, rel_tol=0.01)
    assert _sha((DATA/'packet.json').read_bytes()) == EXPECTED_PACKET_SHA


def test_answer_bearing_packet_remains_forbidden_before_execution(tmp_path):
    packet = json.loads((DATA/'packet.json').read_text(encoding='utf-8'))
    packet['observations'][0]['expectation'] = {'value': 43500., 'atol': 100., 'rtol': 0.}
    source = tmp_path/'contains-answer.json'
    source.write_text(json.dumps(packet), encoding='utf-8')
    output = tmp_path/'rejected-attempt'
    with pytest.raises(ValueError, match='authored answers'):
        trial.assess(DATA, source, output)
    assert not output.exists()
