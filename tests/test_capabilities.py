"""Discovery/runtime consistency, bounded authoring examples and safe CLI output."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from emfeeld import cli
from emfeeld import capabilities as cap
from emfeeld.fields import KINDS
from emfeeld.scene import REGISTRY, source_from_dict, scene_from_dict
from emfeeld.observations import packet_from_dict, run_packet, TYPES
from emfeeld.trajectory_samples import QUANTITIES
from emfeeld.turning_events import TurningCondition
from emfeeld.event_core import UNITS

CAT = cap.get_capabilities()
KINDS_TYPES = [(k, t) for k in KINDS for t in (*REGISTRY, 'uniform')]


def packet(kind='electric', observations=None, source=None):
    sc = {'schema_version': 1, 'title': 'catalogue check', 'kind': kind,
          'sources': [source or {'type': 'uniform', 'field_N_C' if kind == 'electric' else 'field_m_s2': [0, 0, 0]}],
          'bounds_m': [-4, 4, -4, 4, -4, 4], 'duration_s': 5, 'samples': 51,
          'particles': [{'mass_kg': 1, 'position_m': [2, 1, 0], 'velocity_m_s': [-1, 0, 0]}]}
    if kind == 'electric': sc['particles'][0]['charge_C'] = 1e-6
    return {'observation_schema_version': 1, 'scene': sc,
            'observations': observations or [{'id': 'V', 'type': 'potential', 'position_m': [2, 1, 0]}]}


def test_catalogue_inventory_and_units_are_implementation_bound():
    assert set(CAT['sources_by_kind']) == set(KINDS)
    for k in KINDS:
        assert set(CAT['sources_by_kind'][k]) == {*REGISTRY, 'uniform'}
        assert set(CAT['static_observations_by_kind'][k]) == set(TYPES)
    assert CAT['trajectory_sample']['quantities'] == {q: {'unit': u, 'shape': list(s)} for q, (u,s) in QUANTITIES.items()}
    assert CAT['trajectory_event']['units'] == UNITS
    assert CAT['trajectory_event']['extra_turning_units'] == TurningCondition.extra_units


@pytest.mark.parametrize('kind,typ', KINDS_TYPES)
def test_source_required_and_optional_contract_matches_parser(kind, typ):
    spec = CAT['sources_by_kind'][kind][typ]
    row = deepcopy(spec['example_source'])
    model = source_from_dict(kind, row)
    assert set(row) == set(spec['required'])
    assert spec['trajectory_supported'] is bool(model.trajectory_safe)
    for key in spec['required']:
        bad = deepcopy(row); del bad[key]
        with pytest.raises(ValueError): source_from_dict(kind, bad)
    full = {**row, **{key: spec['parameters'][key]['default'] for key in spec['optional']}}
    assert source_from_dict(kind, full) == model
    with pytest.raises(ValueError): source_from_dict(kind, {**row, 'invented_key': 1})


@pytest.mark.parametrize('kind,typ', [(k,t) for k in KINDS for t in TYPES])
def test_static_requests_validate_and_return_advertised_units(kind, typ):
    spec = CAT['static_observations_by_kind'][kind][typ]
    req = spec['example_request']
    assert set(req) == set(spec['required'])
    data = packet(kind, [req]); packet_from_dict(data)
    result = run_packet(data)['results'][0]
    assert result['status'] == 'ok'
    assert result['unit'] == spec['result_unit']
    assert isinstance(result['value'], list) == (spec['result_shape'] == [3])
    for key in spec['required']:
        bad = deepcopy(data); del bad['observations'][0][key]
        with pytest.raises(ValueError): packet_from_dict(bad)
    bad = deepcopy(data); bad['observations'][0]['invented_key'] = 1
    with pytest.raises(ValueError): packet_from_dict(bad)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['index','exact','nearest'])
def test_sample_selectors_and_quantities_match_native_results(kind, mode):
    selector = ({'sample_index': 10} if mode=='index' else
                {'time_s': 1, 'time_selection': 'exact'} if mode=='exact' else
                {'time_s': 1.01, 'time_selection': 'nearest', 'max_time_error_s': .02})
    data = packet(kind, [{'id': q, 'type': 'trajectory_sample', 'particle_index': 0,
                        'quantity': q, **selector} for q in QUANTITIES])
    report = run_packet(data)
    assert report['status'] == 'ok'
    for row in report['results']:
        assert row['unit'] == CAT['trajectory_sample']['quantities'][row['id']]['unit']
        assert row['time_s'] == 1


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('typ', ['plane','radial','radial_turning'])
def test_event_required_keys_and_accuracy_are_actual_validation_rules(kind, typ):
    spec = CAT['trajectory_event']['conditions'][typ]
    data = packet(kind, [deepcopy(spec['example_request'])])
    packet_from_dict(data)
    assert set(data['observations'][0]) == set(spec['required'])
    for key in spec['required']:
        bad = deepcopy(data); del bad['observations'][0][key]
        with pytest.raises(ValueError): packet_from_dict(bad)
    for key in spec['condition_required']:
        bad = deepcopy(data); del bad['observations'][0]['condition'][key]
        with pytest.raises(ValueError): packet_from_dict(bad)
    for key in spec['accuracy_required']:
        bad = deepcopy(data); del bad['observations'][0]['accuracy'][key]
        with pytest.raises(ValueError): packet_from_dict(bad)
    for key, values in spec['condition_options'].items():
        for value in values:
            good = deepcopy(data); good['observations'][0]['condition'][key] = value
            packet_from_dict(good)
    bad = deepcopy(data); bad['observations'][0]['condition']['unknown'] = 1
    with pytest.raises(ValueError): packet_from_dict(bad)
    if typ == 'radial_turning':
        data['observations'][0]['initial_policy'] = spec['rest_launch_option']['initial_policy']
        packet_from_dict(data)  # Initial-state eligibility is a runtime check, not schema proof.


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('typ', ['shell','plane'])
def test_static_only_source_limitation_matches_native_error(kind, typ):
    source = CAT['sources_by_kind'][kind][typ]['example_source']
    assert CAT['sources_by_kind'][kind][typ]['trajectory_supported'] is False
    data = packet(kind, [{'id': 'v', 'type': 'trajectory_sample', 'particle_index': 0,
                         'quantity': 'speed', 'sample_index': 0}], deepcopy(source))
    assert run_packet(data)['results'][0]['status'] == 'unsupported_trajectory'


@pytest.mark.parametrize('kind', KINDS)
def test_declared_rest_policy_preserves_genuine_zero_initial_speed(kind):
    req = deepcopy(CAT['trajectory_event']['conditions']['radial_turning']['example_request'])
    req['initial_policy'] = 'exclude_rest_launch'
    source = {'type': 'uniform', 'field_N_C' if kind=='electric' else 'field_m_s2': [1,0,0]}
    data = packet(kind, [req], source)
    data['scene']['particles'][0]['position_m'] = [-2,1,0]
    data['scene']['particles'][0]['velocity_m_s'] = [0,0,0]
    if kind=='electric': data['scene']['particles'][0]['charge_C'] = 1
    report = run_packet(data)
    row = report['results'][0]
    assert row['status'] == 'ok'
    assert row['state']['time_s'] == pytest.approx(2, abs=1e-7)
    assert row['state']['distance_m'] == pytest.approx(1, abs=1e-7)
    assert data['scene']['particles'][0]['velocity_m_s'] == [0,0,0]


@pytest.mark.parametrize('kind', KINDS)
def test_catalogue_separates_no_event_from_a_solved_crossing(kind):
    req = deepcopy(CAT['trajectory_event']['conditions']['plane']['example_request'])
    req['condition']['point_m'] = [20,0,0]
    data = packet(kind, [req])
    row = run_packet(data)['results'][0]
    assert row['status'] == 'no_event' and row['state'] is None
    assert 'no_event' in CAT['result_handling']['event_statuses']
    assert 'no_event' in CAT['result_handling']['exit_codes']['0']


def test_generation_does_not_solve_or_import_viewer(monkeypatch):
    import emfeeld.fields as fields
    import emfeeld.scene as scene
    monkeypatch.setattr(scene, 'integrate', lambda *a, **k: pytest.fail('integrated during discovery'))
    for cls in (*REGISTRY.values(), fields.UniformField):
        monkeypatch.setattr(cls, 'field', lambda *a, **k: pytest.fail('evaluated during discovery'))
        monkeypatch.setattr(cls, 'potential', lambda *a, **k: pytest.fail('evaluated during discovery'))
    assert cap.get_capabilities()['catalogue_version'] == 1
    code = "import sys; from emfeeld.capabilities import get_capabilities; get_capabilities(); assert 'pyvista' not in sys.modules and 'emfeeld.viewer' not in sys.modules"
    subprocess.run([sys.executable, '-c', code], check=True, timeout=15)


def test_catalogue_is_deterministic_and_caller_mutations_are_isolated():
    a = cap.get_capabilities(); a['sources_by_kind']['gravity']['point']['required'].append('bad')
    a['trajectory_sample']['quantities']['time']['unit'] = 'bad'
    assert cap.get_capabilities() == CAT
    assert json.dumps(cap.get_capabilities(), allow_nan=False) == json.dumps(CAT, allow_nan=False)


def test_catalogue_cli_and_module_write_same_document(tmp_path, capsys):
    output = tmp_path/'catalogue.json'; output.write_text('old output')
    assert cli.main(['capabilities','--output',str(output)]) == 0
    first = capsys.readouterr().out
    assert json.loads(first) == CAT == json.loads(output.read_text(encoding='utf-8'))
    assert cap.main([]) == 0
    assert capsys.readouterr().out == first
    assert not list(tmp_path.glob('.emfeeld-*'))


def test_failed_catalogue_write_preserves_old_destination(tmp_path, monkeypatch):
    output = tmp_path/'catalogue.json'; output.write_bytes(b'old data')
    def broken(*a): raise OSError('injected replace failure')
    monkeypatch.setattr(cap.os, 'replace', broken)
    assert cap.main(['--output',str(output)]) == 2
    assert output.read_bytes() == b'old data'
    assert not list(tmp_path.glob('.emfeeld-*'))


@pytest.mark.parametrize('args', [['run'], ['view'], ['validate'], ['capabilities','scene.json'], ['capabilities','--screenshot','out.png']])
def test_cli_rejects_missing_or_unrelated_inputs(args):
    with pytest.raises(SystemExit) as e: cli.main(args)
    assert e.value.code == 2


@pytest.mark.parametrize('kind', KINDS)
def test_discovery_example_replays_exact_bytes_with_separate_references(kind):
    import hashlib
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('discovery_replay', root/'tools/replay_packets.py')
    replay = importlib.util.module_from_spec(spec); spec.loader.exec_module(replay)
    manifest = json.loads((root/'verification/discovery_examples.json').read_text())
    case = next(c for c in manifest['cases'] if c['id'] == 'discovery_'+kind)
    raw = (root/case['packet']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == case['sha256']
    data = json.loads(raw)
    assert all('expectation' not in o for o in data['observations'])
    assessment = replay.assess(run_packet(data), case)
    assert assessment['passed'], assessment
