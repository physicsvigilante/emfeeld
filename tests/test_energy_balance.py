"""Issue #7: gauge-neutral, sampled energy checks without a numerical energy floor.

Reference mechanics here are separately expressed, not a second engine import.
"""
from dataclasses import replace
from types import SimpleNamespace
import json
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from emfeeld import Particle, SolidSphere, Superposition, UniformField, integrate
from emfeeld.dynamics import Trajectory
from emfeeld.scene import scene_from_dict
from emfeeld.study import check_trajectory

CHECKS = dict(position_atol_m=1e-7, velocity_atol_m_s=1e-7, rtol=1e-7,
              max_normalized_energy_drift=1e-7)


def samples(k, u):
    k, u = np.asarray(k, dtype=float), np.asarray(u, dtype=float)
    return Trajectory(np.arange(len(k), dtype=float), np.zeros((len(k), 3)),
                      np.zeros((len(k), 3)), k, u, 0)


def spheres():
    return Superposition((SolidSphere('electric', 2e-9, (-1, 0, 0), radius=.25),
                          SolidSphere('electric', -2e-9, (1, 0, 0), radius=.25)))


def shot(model, p=None, duration=.45, n=451):
    p = p or Particle(1e-11, (0, 0, 0), (0, 0, 0), 1e-12)
    t = integrate(model, p, np.linspace(0, duration, n), max_step_s=duration/200)
    scene = SimpleNamespace(model=model, duration_s=duration)
    return p, t, check_trajectory(scene, p, t, CHECKS)


def test_issue7_original_exact_rest_is_verified_without_changing_inputs():
    p, t, check = shot(spheres())
    assert t.kinetic_J[0] == t.potential_J[0] == 0
    assert t.max_energy_drift_J < 1e-23
    assert t.normalized_energy_drift < 1e-10
    assert check['passed'] and check['energy_check_version'] == 2
    assert check['energy_checks']['base']['scale_J'] > 0
    assert check['energy_checks']['base']['tolerance'] == CHECKS['max_normalized_energy_drift']
    assert_array_equal(t.position_m[0], p.position_m)
    assert_array_equal(t.velocity_m_s[0], p.velocity_m_s)


@pytest.mark.parametrize('x0', [0., 1e-14, -1e-14, 1e-10, -1e-10, -.3])
def test_exact_near_zero_and_ordinary_launches(x0):
    p = Particle(1e-11, (x0, 0, 0), (0, 0, 0), 1e-12)
    _, t, check = shot(spheres(), p)
    assert check['passed']
    assert t.normalized_energy_drift < 1e-10


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
@pytest.mark.parametrize('origin', [(0, 0, 0), (3, 0, 0)])
def test_uniform_field_motion_matches_closed_form(kind, origin):
    model = UniformField(kind, (2., -.5, 0), origin=origin)
    p = Particle(2., (0, 0, 0), (0, 0, 0), 3.)
    _, t, check = shot(model, p, duration=1., n=31)
    a = (p.charge_C/p.mass_kg if kind == 'electric' else 1)*np.array([2., -.5, 0])
    assert_allclose(t.position_m, .5*t.time_s[:, None]**2*a, atol=2e-13, rtol=2e-13)
    assert_allclose(t.velocity_m_s, t.time_s[:, None]*a, atol=2e-13, rtol=2e-13)
    assert check['passed']


@pytest.mark.parametrize('offset_V', [-100., 0., 100., 1e4])
def test_representable_gauge_offsets_do_not_change_motion_or_acceptance(offset_V):
    model = spheres()
    shifted = SimpleNamespace(kind='electric', trajectory_safe=True, field=model.field,
                              potential=lambda r: model.potential(r) + offset_V)
    _, a, ca = shot(model)
    _, b, cb = shot(shifted)
    assert_array_equal(a.position_m, b.position_m)
    assert_array_equal(a.velocity_m_s, b.velocity_m_s)
    assert ca['passed'] and cb['passed']
    assert a.energy_balance['scale_J'] == pytest.approx(b.energy_balance['scale_J'], rel=1e-12)


def test_unresolvable_gauge_offset_must_not_be_treated_as_verified():
    model = spheres()
    shifted = SimpleNamespace(kind='electric', trajectory_safe=True, field=model.field,
                              potential=lambda r: model.potential(r) + 1e12)
    _, t, check = shot(shifted)
    assert not check['passed']
    assert check['energy_checks']['base']['status'] == 'unresolved_precision'
    assert check['energy_checks']['base']['resolution_ratio'] > CHECKS['max_normalized_energy_drift']


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
@pytest.mark.parametrize('potential_offset', [0., 1e4])
def test_exact_stationary_zero_exchange_is_explicit(kind, potential_offset):
    zero = UniformField(kind, (0, 0, 0))
    model = SimpleNamespace(kind=kind, trajectory_safe=True, field=zero.field,
                           potential=lambda r: zero.potential(r) + potential_offset)
    _, t, check = shot(model)
    assert t.normalized_energy_drift == 0
    assert t.energy_balance['scale_J'] == 0
    assert check['passed']
    assert check['energy_checks']['base']['status'] == 'stationary_zero_exchange'


@pytest.mark.parametrize('exponent', [-200, -80, 0, 80, 200])
def test_uniform_si_energy_rescaling_does_not_change_relative_drift(exponent):
    factor = 10.**exponent
    t = samples(np.array([2, 3, 5.])*factor, np.array([-2, -3, -4.99])*factor)
    assert t.normalized_energy_drift == pytest.approx(.01/5, rel=2e-13)
    assert t.energy_balance['scale_J'] == pytest.approx(5*factor, rel=2e-15)


def test_zero_total_energy_with_nonzero_components_is_not_zero_exchange():
    t = samples([2, 3, 5], [-2, -3, -5])
    assert t.energy_balance['scale_J'] == 5
    assert t.normalized_energy_drift == 0


@pytest.mark.parametrize('which', ['kinetic_J', 'potential_J'])
def test_injected_nonconservation_fails_existing_tolerance(which):
    model = spheres(); p, t, _ = shot(model)
    damaged = getattr(t, which).copy()
    damaged[-1] += .01*float(np.max(t.kinetic_J))
    corrupted = replace(t, **{which: damaged})
    result = check_trajectory(SimpleNamespace(model=model, duration_s=.45), p, corrupted, CHECKS)
    assert not result['passed']
    assert result['energy_checks']['base']['status'] == 'energy_residual_exceeded'


@pytest.mark.parametrize('field,value', [('kinetic_J', np.nan), ('potential_J', np.inf),
                                       ('kinetic_J', -1.)])
def test_invalid_energy_arrays_are_not_silently_passed(field, value):
    t = samples([0, 1], [0, -1]); a = getattr(t, field).copy(); a[-1] = value
    with pytest.raises((ValueError, FloatingPointError)):
        _ = replace(t, **{field:a}).energy_balance


def test_extreme_differences_fail_explicitly_instead_of_overflow_success():
    with pytest.raises(FloatingPointError):
        _ = samples([0, 1], [-1e308, 1e308]).energy_balance


def test_no_energy_floor_or_nan_in_zero_case_json():
    diagnostic = samples([0, 0], [0, 0]).energy_balance
    assert diagnostic['scale_J'] == 0 and diagnostic['normalized_residual'] == 0
    json.dumps(diagnostic, allow_nan=False)


def test_subnormal_unresolvable_energy_fails_qualification():
    t = samples([0., 1e-320], [0., -1e-320])
    assert t.energy_balance['resolution_ratio'] > CHECKS['max_normalized_energy_drift']


def test_nonstationary_zero_energy_arrays_do_not_get_an_exact_rest_pass():
    model = spheres(); p, t, _ = shot(model)
    corrupted = replace(t, kinetic_J=np.zeros_like(t.kinetic_J), potential_J=np.zeros_like(t.potential_J))
    result = check_trajectory(SimpleNamespace(model=model, duration_s=.45), p, corrupted, CHECKS)
    assert not result['passed']
    assert result['energy_checks']['base']['status'] == 'unresolved_zero_scale'


def test_field_laws_integrator_states_and_legacy_absolute_metric_unchanged():
    p, t, _ = shot(spheres())
    assert t.max_energy_drift_J == float(np.max(np.abs(t.energy_J-t.energy_J[0])))
    before = [a.copy() for a in (t.time_s, t.position_m, t.velocity_m_s, t.kinetic_J, t.potential_J)]
    _ = t.energy_balance
    for a,b in zip(before, (t.time_s,t.position_m,t.velocity_m_s,t.kinetic_J,t.potential_J)):
        assert_array_equal(a,b)


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
@pytest.mark.parametrize('factor', [1e-9, 1., 1e9])
def test_physical_mass_and_coupling_rescaling_preserves_motion(kind, factor):
    model = UniformField(kind, (2., 0, 0))
    original = Particle(2., (0,0,0), (0,0,0), 3.)
    scaled = Particle(2.*factor, (0,0,0), (0,0,0), 3.*factor)
    _, a, ca = shot(model, original)
    _, b, cb = shot(model, scaled)
    assert ca['passed'] and cb['passed']
    assert_allclose(a.position_m, b.position_m, atol=2e-14, rtol=2e-14)
    assert_allclose(a.velocity_m_s, b.velocity_m_s, atol=2e-14, rtol=2e-14)
    assert_allclose(a.kinetic_J*factor, b.kinetic_J, rtol=3e-14, atol=0)
    assert a.energy_balance['scale_J']*factor == pytest.approx(b.energy_balance['scale_J'], rel=1e-13)


def test_v2_visible_in_new_cli_and_sample_reports():
    from emfeeld.cli import run_scene
    from emfeeld.observations import run_packet
    raw = dict(schema_version=1, title='zero-energy uniform field', kind='electric',
        sources=[dict(type='uniform', field_N_C=[2.,0,0])],
        particles=[dict(mass_kg=2., charge_C=3., position_m=[0,0,0], velocity_m_s=[0,0,0])],
        duration_s=.45, samples=31, bounds_m=[-1,1,-1,1,-1,1])
    _, summary = run_scene(scene_from_dict(raw))
    assert summary['trajectories'][0]['energy_balance']['version'] == 2
    report = run_packet(dict(observation_schema_version=1, scene=raw, observations=[
        dict(id='velocity', type='trajectory_sample', particle_index=0,
             quantity='velocity', sample_index=30)]))
    assert report['status']=='ok'
    assert report['trajectory_runs']['0']['energy_balance']['version']==2
    assert report['results'][0]['value'][0] == pytest.approx(1.35, rel=1e-12)


def test_existing_tolerance_can_still_fail_without_automatic_relaxation():
    model = spheres(); p, t, _ = shot(model)
    settings = dict(CHECKS, max_normalized_energy_drift=1e-30)
    check = check_trajectory(SimpleNamespace(model=model, duration_s=.45), p, t, settings)
    assert not check['passed']
    assert check['energy_checks']['base']['tolerance'] == 1e-30
    assert settings == dict(CHECKS, max_normalized_energy_drift=1e-30)


def test_late_large_corruption_cannot_normalize_itself_to_a_pass():
    from emfeeld.energy import check_energy_balance
    t = samples([0, 1, 1e100], [0, -1, -2])
    result = check_energy_balance(t, 1e-7)
    assert not result['passed']
    assert result['normalized_residual'] == pytest.approx(1.)


def test_new_check_does_not_requalify_a_sealed_historical_failure(tmp_path):
    from emfeeld import study
    from emfeeld.observations import _digest
    # Produce an ordinary captured packet, then construct a sealed v1 failure
    # record. Loading is not permission to replace its judgment with v2.
    raw=dict(schema_version=1, title='retained zero launch', kind='electric',
        sources=[dict(type='uniform',field_N_C=[2.,0,0])],
        particles=[dict(mass_kg=2.,charge_C=3.,position_m=[0,0,0],velocity_m_s=[0,0,0])],
        duration_s=.45,samples=31,bounds_m=[-1,1,-1,1,-1,1])
    packet=dict(observation_schema_version=1,scene=raw,observations=[
        dict(id='v',type='trajectory_sample',particle_index=0,quantity='speed',sample_index=30)])
    study._capture(tmp_path,packet,CHECKS)
    record=json.loads((tmp_path/'checks.json').read_text())
    record.update(render_ready=False, trajectory_checks=[dict(passed=False, max_normalized_energy_drift=1e281)])
    study._write(tmp_path/'checks.json',record)
    inventory=json.loads((tmp_path/'integrity.json').read_text())
    inventory['files']['checks.json']=study.digest((tmp_path/'checks.json').read_bytes())
    study._write(tmp_path/'integrity.json',inventory)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError,match='preview unavailable'):
        study.load_recorded(tmp_path)
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}
