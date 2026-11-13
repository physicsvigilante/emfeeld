"""Current published-byte replay and mutation tests; historical pilots stay frozen."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest
from emfeeld.observations import load_packet, run_packet

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('packet_replay', ROOT/'tools/replay_packets.py')
replay = importlib.util.module_from_spec(spec); spec.loader.exec_module(replay)
MANIFEST = load_packet(ROOT/'verification/v6_published.json')


@pytest.mark.parametrize('case', MANIFEST['cases'], ids=lambda c: c['id'])
def test_exact_published_packet_has_declared_measurements(case):
    raw = (ROOT/case['packet']).read_bytes()
    assert replay.digest(raw) == case['sha256']
    assessment = replay.assess(run_packet(load_packet(ROOT/case['packet'])), case)
    assert assessment['passed'], assessment['issues']


@pytest.mark.parametrize('actual,expected', [
    (True, 1), ('1', 1), ([1], 1), ([1, 2], [1, 2, 3]),
    (float('nan'), 1), (float('inf'), 1), (1, True), ('true', True), (True, 'true'),
])
def test_reference_checker_rejects_coercion_shapes_and_nonfinite(actual, expected):
    assert not replay.compare(actual, {'value': expected})


def test_reference_checker_handles_extreme_finite_subtraction():
    assert not replay.compare(1e308, {'value': -1e308, 'atol': 0, 'rtol': 0})
    assert replay.compare(1e308, {'value': 1e308, 'atol': 0, 'rtol': 0})


@pytest.mark.parametrize('mutation', ['no_event', 'missing_state', 'wrong_value', 'wrong_unit', 'extra_id'])
def test_no_false_event_pass(mutation):
    case = {'statuses': {'cross': 'ok'}, 'checks': [
        {'id': 'cross', 'path': ['state', 'time_s'], 'value': 1, 'atol': 1e-9},
        {'id': 'cross', 'path': ['units', 'time_s'], 'value': 's'}]}
    report = {'results': [{'id': 'cross', 'status': 'ok', 'state': {'time_s': 1}, 'units': {'time_s': 's'}}]}
    assert replay.assess(report, case)['passed']
    row = report['results'][0]
    if mutation == 'no_event': row['status'] = 'no_event'
    if mutation == 'missing_state': del row['state']
    if mutation == 'wrong_value': row['state']['time_s'] = 10
    if mutation == 'wrong_unit': row['units']['time_s'] = 'ms'
    if mutation == 'extra_id': report['results'].append({'id': 'unasked', 'status': 'ok'})
    assert not replay.assess(report, case)['passed']


def fixture_manifest(tmp_path, *, invalid=False):
    packet = {'observation_schema_version': 1,
        'scene': {'schema_version': 1, 'title': 'fixture', 'kind': 'electric',
                  'sources': [{'type': 'uniform', 'field_N_C': [1, 0, 0]}],
                  'bounds_m': [-2, 2, -2, 2, -2, 2]},
        'observations': [{'id': 'E', 'type': 'field', 'position_m': [0, 0, 0]}]}
    if invalid: packet['scene']['sources'][0] = {'type': 'ring', 'charge_C': 1e-9}
    raw = (json.dumps(packet)+'\n').encode()
    (tmp_path/'input.json').write_bytes(raw)
    case = {'id': 'fixture', 'packet': 'input.json', 'sha256': replay.digest(raw)}
    if invalid: case['rejects'] = 'unsupported source type'
    else:
        case.update(statuses={'E': 'ok'}, checks=[{'id': 'E', 'path': ['value'], 'value': [1, 0, 0]}])
    manifest = {'version': 1, 'cases': [case]}
    path = tmp_path/'manifest.json'; path.write_text(json.dumps(manifest))
    return manifest, path, raw


@pytest.mark.parametrize('invalid', [False, True])
def test_capture_bytes_and_refuse_existing_evidence_directory(tmp_path, invalid):
    _, path, raw = fixture_manifest(tmp_path, invalid=invalid)
    output = tmp_path/'run'
    result = replay.replay(path, output, root=tmp_path)
    assert result['passed']
    assert (output/'fixture/input.json').read_bytes() == raw
    assert (tmp_path/'input.json').read_bytes() == raw
    with pytest.raises(FileExistsError): replay.replay(path, output, root=tmp_path)


def test_changed_hash_rejects_whole_batch_before_execution(tmp_path, monkeypatch):
    manifest, path, _ = fixture_manifest(tmp_path)
    second = deepcopy(manifest['cases'][0]); second['id'] = 'second'; second['sha256'] = '0'*64
    manifest['cases'].append(second); path.write_text(json.dumps(manifest))
    monkeypatch.setattr(replay, 'run_packet', lambda *_: pytest.fail('executed before complete preflight'))
    with pytest.raises(ValueError, match='hash mismatch'): replay.replay(path, tmp_path/'out', root=tmp_path)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('mutation', ['unsafe_id', 'duplicate', 'escape', 'bad_reference', 'negative_tolerance', 'unknown_key'])
def test_manifest_validation_before_physics(tmp_path, mutation):
    manifest, _, _ = fixture_manifest(tmp_path); case = manifest['cases'][0]
    if mutation == 'unsafe_id': case['id'] = '../unsafe'
    if mutation == 'duplicate': manifest['cases'].append(deepcopy(case))
    if mutation == 'escape': case['packet'] = '../outside.json'
    if mutation == 'bad_reference': case['checks'][0]['value'] = 10**400
    if mutation == 'negative_tolerance': case['checks'][0]['rtol'] = -1
    if mutation == 'unknown_key': case['checks'][0]['rtoll'] = .01
    with pytest.raises(ValueError): replay.preflight(manifest, tmp_path)
