"""Contract and failure tests for additive static observation requests."""
from copy import deepcopy
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from numpy.testing import assert_allclose
import pytest

from emfeeld import (PointSource, SolidSphere, SphericalShell, InfiniteLine,
                     InfinitePlane, UniformField, Superposition, Scene)
from emfeeld.fields import G, K
from emfeeld.observations import (evaluate_observations, load_packet, main,
                                  packet_from_dict, parse_requests, run_packet)

BASE = {"observation_schema_version": 1,
        "scene": {"schema_version": 1, "title": "measurements", "kind": "electric",
                  "sources": [{"type": "point", "charge_C": 1e-9}],
                  "bounds_m": [-3, 3, -3, 3, -3, 3]},
        "observations": [{"id": "P", "type": "potential", "position_m": [2, 0, 0]}]}


def req(typ, **kwargs):
    return {"id": "probe", "type": typ, **kwargs}


@pytest.mark.parametrize('kind,c', [('electric', K), ('gravity', -G)])
def test_point_values_signs_units_and_force(kind, c):
    model = PointSource(kind, 2, center=(1, 0, 0))
    coupling = {'test_charge_C': -3} if kind == 'electric' else {'test_mass_kg': 3}
    requests = [dict(req(t, position_m=[3, 0, 0]), id=t) for t in ('field', 'potential')]
    requests.append(dict(req('force', position_m=[3, 0, 0], **coupling), id='force'))
    results = evaluate_observations(model, requests)
    assert_allclose(results[0]['value'], [c/2, 0, 0], atol=0)
    assert results[0]['unit'] == ('N/C' if kind == 'electric' else 'm/s^2')
    assert results[1]['value'] == pytest.approx(c)
    assert results[1]['unit'] == ('V' if kind == 'electric' else 'J/kg')
    assert results[2]['unit'] == 'N'
    assert_allclose(results[2]['value'], [c/2 * next(iter(coupling.values())), 0, 0], atol=0)
    assert results[2]['magnitude'] == pytest.approx(abs(1.5*c))
    assert all(r['error_bound'] is None for r in results)


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
def test_difference_direction_and_reference_invariance(kind):
    f = np.array([2., -3., 4.])
    start, end = [1, 2, 3], [3, 1, 2]
    request = req('potential_difference', from_m=start, to_m=end)
    a = evaluate_observations(UniformField(kind, f), [request])[0]
    b = evaluate_observations(UniformField(kind, f, origin=(20, -10, 30)), [request])[0]
    expected = -np.dot(f, np.array(end)-start)
    assert a['value'] == b['value'] == expected
    reverse = evaluate_observations(UniformField(kind, f), [req('potential_difference', from_m=end, to_m=start)])[0]
    assert reverse['value'] == -expected
    assert a['convention'] == 'potential(to_m) - potential(from_m)'


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
def test_line_reference_difference(kind):
    requests = [req('potential_difference', from_m=[0, 3, 4], to_m=[0, 5, 12])]
    a, b = (evaluate_observations(InfiniteLine(kind, 1, direction=(1, 0, 0), reference_radius=ref), requests)[0]
            for ref in (1, 13))
    assert a['value'] == pytest.approx(b['value'], rel=1e-13)
    assert a['value'] == pytest.approx(-2*(K if kind == 'electric' else -G)*math.log(13/5))


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
@pytest.mark.parametrize('factory', [SphericalShell, InfinitePlane])
def test_continuous_potential_not_blocked_by_undefined_field(kind, factory):
    model = factory(kind, 1)
    p = [1, 0, 0]
    requests = [dict(req(t, position_m=p), id=t) for t in ('field', 'potential')]
    results = evaluate_observations(model, requests)
    assert results[0]['status'] == 'domain_error' and results[0]['value'] is None
    assert results[1]['status'] == 'ok' and math.isfinite(results[1]['value'])
    json.dumps(results, allow_nan=False)


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
@pytest.mark.parametrize('method', ['field', 'potential'])
def test_oblique_line_uncertainty_reaches_observation_result(kind, method):
    model = InfiniteLine(kind, 1, direction=(1, 1, 1))
    requests = [dict(req(method, position_m=p), id=f'p{i}')
                for i, p in enumerate(([1, 1, 1], [1, -1, 0]))]
    r = evaluate_observations(model, requests)
    assert [a['status'] for a in r] == ['domain_error', 'ok']
    assert r[0]['error']['code'] == 'undefined_or_unresolved'


def test_oblique_plane_and_shell_surface_policy():
    plane = InfinitePlane('electric', 1, normal=(1, 3, 7))
    r = evaluate_observations(plane, [req('field', position_m=[7, 0, -1])])[0]
    assert r['status'] == 'domain_error'
    shell = SphericalShell('electric', 1)
    r = evaluate_observations(shell, [req('field', position_m=[float(1+np.finfo(float).eps), 0, 0])])[0]
    assert r['status'] == 'domain_error'


def test_same_invalid_endpoint_not_cancelled_and_zero_charge_not_bypass():
    model = PointSource('electric', 1)
    requests = [req('potential_difference', from_m=[0, 0, 0], to_m=[0, 0, 0]),
                dict(req('force', position_m=[0, 0, 0], test_charge_C=0), id='neutral')]
    r = evaluate_observations(model, requests)
    assert all(x['status'] == 'domain_error' for x in r)
    assert evaluate_observations(PointSource('electric', 0), requests)[0]['value'] == 0


@pytest.mark.parametrize('endpoint', ['from_m', 'to_m'])
def test_either_singular_endpoint_is_a_domain_error(endpoint):
    request = req('potential_difference', from_m=[1, 0, 0], to_m=[2, 0, 0])
    request[endpoint] = [0, 0, 0]
    assert evaluate_observations(PointSource('electric', 1), [request])[0]['status'] == 'domain_error'


def test_cavity_grouping_and_source_multiplicity():
    big = SolidSphere('electric', 1e-9, radius=2)
    cavity = SolidSphere('electric', -1e-9/8, radius=1, center=(0.5, 0, 0))
    other = UniformField('electric', (0, 0.3, -0.2))
    flat = Superposition((big, cavity, other, big))
    nested = Superposition((Superposition((big, cavity)), Superposition((other, big))))
    requests = [dict(req(t, position_m=[0.4, 0.2, 0.1]), id=t) for t in ('field', 'potential')]
    a, b = (evaluate_observations(model, requests) for model in (flat, nested))
    for x, y in zip(a, b): assert_allclose(x['value'], y['value'], rtol=1e-14)
    # Independent uniform-density interior field sum including the repeated source.
    expected = K*1e-9/8*(2*np.array([0.4, 0.2, 0.1])-np.array([-0.1, 0.2, 0.1])) + [0, 0.3, -0.2]
    assert_allclose(a[0]['value'], expected, rtol=1e-14)


@pytest.mark.parametrize('bad', [True, '1', None, float('nan'), float('inf'), 1+2j, 10**400])
def test_probe_number_validation(bad):
    with pytest.raises(ValueError):
        parse_requests('electric', [req('field', position_m=[bad, 0, 0])])


@pytest.mark.parametrize('bad', [[0, 0], [0, 0, 0, 0], [[0, 0, 0]], '0,0,0', None, (0, 0, 0)])
def test_probe_shape_validation(bad):
    with pytest.raises(ValueError):
        parse_requests('electric', [req('potential', position_m=bad)])


@pytest.mark.parametrize('id', ['', '9P', 'a b', 'a'*65, None, 12])
def test_ids_are_machine_addressable(id):
    with pytest.raises(ValueError):
        parse_requests('electric', [dict(req('potential', position_m=[1, 0, 0]), id=id)])


@pytest.mark.parametrize('kind,extra', [
    ('electric', {'test_mass_kg': 1}), ('gravity', {'test_charge_C': 1}),
    ('electric', {'test_charge_C': True}), ('gravity', {'test_mass_kg': 0}),
    ('gravity', {'test_mass_kg': -1}), ('electric', {'test_charge_C': 1, 'test_mass_kg': 1})])
def test_coupling_kind_is_explicit(kind, extra):
    with pytest.raises(ValueError):
        parse_requests(kind, [req('force', position_m=[1, 0, 0], **extra)])


@pytest.mark.parametrize('bad', ['flux', 'crossing_speed', 'turning_point', 'eval', [], None])
def test_unsupported_requests_are_not_invented(bad):
    with pytest.raises(ValueError):
        parse_requests('electric', [req(bad, position_m=[1, 0, 0])])


def test_validate_all_before_evaluation():
    class Untouched:
        kind = 'electric'
        def potential(self, p): raise AssertionError('must validate the whole batch first')
    a = req('potential', position_m=[1, 0, 0])
    with pytest.raises(ValueError, match='duplicate'):
        evaluate_observations(Untouched(), [a, a])
    with pytest.raises(ValueError, match='unknown keys'):
        evaluate_observations(Untouched(), [a, dict(a, id='bad', units='cm')])


@pytest.mark.parametrize('typ,expected', [('field', [1, 2, 3]), ('potential', -6)])
def test_authored_tolerances_and_separate_status(typ, expected):
    request = req(typ, position_m=[1, 1, 1], expectation={'value': expected, 'atol': 0, 'rtol': 0})
    model = UniformField('electric', (1, 2, 3))
    good = evaluate_observations(model, [request])[0]
    assert good['status'] == 'ok' and good['check']['passed']
    request['expectation']['value'] = [2, 3, 4] if typ == 'field' else 0
    bad = evaluate_observations(model, [request])[0]
    assert bad['status'] == 'ok' and not bad['check']['passed']
    assert bad['value'] == good['value']


@pytest.mark.parametrize('e', [
    {'value': 1, 'atol': -1, 'rtol': 0}, {'value': 1, 'atol': 0, 'rtol': -1},
    {'value': 1, 'atol': 0}, {'value': [1, 2, 3], 'atol': 0, 'rtol': 0},
    {'value': 1, 'atol': True, 'rtol': 0}, {'value': 1, 'atol': float('inf'), 'rtol': 0},
    {'value': 1, 'atol': 0, 'rtol': 0, 'unit': 'V'}])
def test_invalid_expectations_rejected(e):
    with pytest.raises(ValueError):
        parse_requests('electric', [req('potential', position_m=[1, 0, 0], expectation=e)])


def test_no_expectation_broadcast_for_vector():
    with pytest.raises(ValueError):
        parse_requests('electric', [req('field', position_m=[1, 0, 0], expectation={'value': 0, 'atol': 0, 'rtol': 0})])


def test_extreme_finite_reference_check_does_not_overflow():
    model = UniformField('electric', (1e308, 0, 0))
    r = evaluate_observations(model, [req('potential', position_m=[-1, 0, 0],
         expectation={'value': -1e308, 'atol': 0, 'rtol': 0})])[0]
    assert r['status'] == 'ok' and r['check']['passed'] is False


def test_domain_and_numerical_errors_return_null_preserving_successes():
    data = deepcopy(BASE)
    data['observations'] = [req('potential', position_m=[0, 0, 0], expectation={'value': 0, 'atol': 0, 'rtol': 0}),
                            dict(req('potential', position_m=[2, 0, 0]), id='valid')]
    r = run_packet(data)
    assert r['status'] == 'partial' and r['counts']['domain_errors'] == 1
    assert r['results'][0]['check']['passed'] is None
    assert r['results'][0]['value'] is None
    model = UniformField('gravity', (1e308, 0, 0))
    reqs = [req('potential', position_m=[10, 0, 0]), dict(req('potential', position_m=[0, 0, 0]), id='valid')]
    r = evaluate_observations(model, reqs)
    assert [x['status'] for x in r] == ['numerical_error', 'ok']
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize('value', [float('nan'), [1, 2], [float('inf'), 0, 0]])
def test_custom_field_bad_results_reported(value):
    class Bad:
        kind = 'gravity'
        def field(self, p): return value
    r = evaluate_observations(Bad(), [req('field', position_m=[1, 0, 0])])[0]
    assert r['status'] == 'numerical_error' and r['value'] is None


def test_unexpected_programming_error_not_hidden():
    class Broken:
        kind = 'electric'
        def field(self, p): raise RuntimeError('implementation bug')
    with pytest.raises(RuntimeError, match='implementation bug'):
        evaluate_observations(Broken(), [req('field', position_m=[1, 0, 0])])


def test_packet_is_pure_and_does_not_integrate_or_import_viewer(monkeypatch):
    data = deepcopy(BASE)
    data['scene']['sources'] = [{'type': 'plane', 'charge_per_m2_C_m2': 1e-9}]
    data['scene']['particles'] = [{'mass_kg': 1, 'charge_C': 1, 'position_m': [0, 0, 0], 'velocity_m_s': [0, 0, 0]}]
    data['scene']['duration_s'] = 1
    before = deepcopy(data)
    def fail(self): raise AssertionError('static observation must not integrate')
    monkeypatch.setattr(Scene, 'trajectories', fail)
    r = run_packet(data)
    assert r['status'] == 'ok'
    assert data == before
    r['input']['scene']['title'] = 'modified result'
    assert data == before
    code = 'import emfeeld.observations, sys; assert "pyvista" not in sys.modules; assert "emfeeld.viewer" not in sys.modules'
    subprocess.run([sys.executable, '-c', code], check=True)


@pytest.mark.parametrize('change', [
    {'observation_schema_version': True}, {'observation_schema_version': 2},
    {'observations': []}, {'observations': None}, {'scene': 'file.json'},
    {'notes': []}, {'typo': 1}])
def test_packet_schema_rejection(change):
    data = deepcopy(BASE); data.update(change)
    with pytest.raises(ValueError): packet_from_dict(data)


@pytest.mark.parametrize('where', ['charge_C', 'center_m', 'duration_s', 'bounds_m'])
@pytest.mark.parametrize('value', [True, '1'])
def test_packet_rejects_scene_numeric_coercions(where, value):
    data = deepcopy(BASE)
    if where == 'charge_C': data['scene']['sources'][0][where] = value
    elif where == 'center_m': data['scene']['sources'][0][where] = [value, 0, 0]
    elif where == 'duration_s': data['scene'][where] = value
    else: data['scene'][where][0] = value
    with pytest.raises(ValueError): packet_from_dict(data)


@pytest.mark.parametrize('text', ['{"x": 1, "x": 2}', '{"outer":{"x":1,"x":2}}', '{"x":NaN}', '{"x":Infinity}'])
def test_strict_json_loading(tmp_path, text):
    p = tmp_path/'bad.json'; p.write_text(text)
    with pytest.raises(ValueError): load_packet(p)


def test_reports_stable_and_sign_sensitive():
    a = run_packet(BASE); b = run_packet(BASE)
    assert a == b
    data = deepcopy(BASE); data['scene']['sources'][0]['charge_C'] *= -1
    c = run_packet(data)
    assert c['scene_sha256'] != a['scene_sha256']
    assert c['packet_sha256'] != a['packet_sha256']
    assert c['results'][0]['value'] == -a['results'][0]['value']


def test_cli_roundtrip_success_partial_failed_validation_and_input_guard(tmp_path, capsys):
    p = tmp_path/'packet.json'; out = tmp_path/'outputs/result.json'
    p.write_text(json.dumps(BASE))
    assert main([str(p), '--output', str(out)]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(out.read_text())
    original = p.read_bytes()
    assert main([str(p), '--output', str(p)]) == 2
    assert p.read_bytes() == original
    capsys.readouterr()
    data = deepcopy(BASE); data['observations'][0]['position_m'] = [0, 0, 0]
    p.write_text(json.dumps(data))
    assert main([str(p), '--validate-only']) == 0
    assert 'NOT RUN' in json.loads(capsys.readouterr().out)['evaluation']
    assert main([str(p)]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'
    data['observations'].append(dict(BASE['observations'][0], id='valid'))
    p.write_text(json.dumps(data))
    assert main([str(p)]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'partial'
    data['observations'][0]['type'] = 'flux'; p.write_text(json.dumps(data))
    assert main([str(p)]) == 2
    assert 'unsupported' in capsys.readouterr().err


def test_cli_failed_reference_is_nonzero(tmp_path, capsys):
    data = deepcopy(BASE); data['observations'][0]['expectation'] = {'value': 0, 'atol': 0, 'rtol': 0}
    p = tmp_path/'wrong.json'; p.write_text(json.dumps(data))
    assert main([str(p)]) == 1
    r = json.loads(capsys.readouterr().out)
    assert r['results'][0]['status'] == 'ok'
    assert r['counts']['failed_expectations'] == 1
    assert r['status'] == 'failed'


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples' / 'observations'
ENTRIES = json.loads((EXAMPLES/'manifest.json').read_text())['examples']


@pytest.mark.parametrize('entry', ENTRIES, ids=lambda x: x['file'])
def test_authored_packets_via_generic_runner(entry):
    data = json.loads((EXAMPLES/entry['file']).read_text())
    report = run_packet(data)
    assert report['status'] == entry['expected_status']
    assert report['counts']['requests'] == entry['requests']
    assert report['counts']['failed_expectations'] == 0
    if entry['case_id']:
        # Copying a scene into an observation packet must not silently alter it.
        root = EXAMPLES.parents[1]
        original = json.loads((root/'pilots/authorability_v1/scenes'/entry['file']).read_text())
        assert data['scene'] == original


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
def test_observation_covariance(kind):
    # Rotation and translation change coordinates, not the requested physics.
    from scipy.spatial.transform import Rotation
    rot = Rotation.from_rotvec([0.3, -0.5, 0.2]).as_matrix()
    shift = np.array([2., -3., 1.])
    centres = np.array([[-1., 0., 0.], [0., 2., -1.]])
    masses = (1e-9, -2e-9) if kind == 'electric' else (1e10, 2e10)
    original = Superposition(tuple(PointSource(kind, m, center=c) for m, c in zip(masses, centres)))
    moved = Superposition(tuple(PointSource(kind, m, center=rot@c+shift) for m, c in zip(masses, centres)))
    p, q = np.array([2., 1., 3.]), np.array([-2., 3., 4.])
    a = [dict(req(t, position_m=p.tolist()), id=t) for t in ('field','potential')]
    a += [req('potential_difference', from_m=p.tolist(), to_m=q.tolist())]
    b = [dict(req(t, position_m=(rot@p+shift).tolist()), id=t) for t in ('field','potential')]
    b += [req('potential_difference', from_m=(rot@p+shift).tolist(), to_m=(rot@q+shift).tolist())]
    x,y = evaluate_observations(original,a), evaluate_observations(moved,b)
    assert_allclose(y[0]['value'],rot@x[0]['value'],rtol=2e-13,atol=1e-14)
    assert_allclose([r['value'] for r in y[1:]], [r['value'] for r in x[1:]], rtol=2e-13,atol=1e-14)


def test_machine_contract_matches_runtime():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root/'docs/observation_contract_v1.json').read_text())
    from emfeeld.observations import TYPES, ID_PATTERN
    assert set(contract['types']) == set(TYPES)
    assert contract['id_pattern'] == ID_PATTERN
    for kind in ('electric','gravity'):
        model = UniformField(kind,(1,2,3))
        for typ, spec in contract['types'].items():
            row = req(typ)
            if typ == 'potential_difference': row.update(from_m=[0,0,0],to_m=[1,0,0])
            else: row['position_m']=[1,0,0]
            if typ=='force': row[spec['required_by_kind'][kind]]=1
            result=evaluate_observations(model,[row])[0]
            assert result['unit']==spec['units'][kind]
            assert list(np.asarray(result['value']).shape)==spec['shape']
            assert result['status'] in contract['result_statuses']


def test_force_overflow_and_nonfinite_potential_difference_are_explicit():
    model = UniformField('electric',(1e308,0,0))
    rows = [req('force',position_m=[0,0,0],test_charge_C=10),
            dict(req('potential_difference',from_m=[1,0,0],to_m=[-1,0,0]),id='difference')]
    assert all(r['status']=='numerical_error' for r in evaluate_observations(model,rows))


def test_hardlink_input_overwrite_guard(tmp_path, capsys):
    p = tmp_path/'packet.json'; p.write_text(json.dumps(BASE))
    alias = tmp_path/'same.json'; alias.hardlink_to(p)
    before = p.read_bytes()
    assert main([str(p),'--output',str(alias)])==2
    assert p.read_bytes()==before
    assert 'overwrite' in capsys.readouterr().err
