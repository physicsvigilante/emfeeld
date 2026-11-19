"""Same-author independently expressed finite-pair checks; not independent review."""
from dataclasses import replace
import json
import math
import numpy as np
import pytest
from scipy.constants import elementary_charge

from emfeeld.dipole_lesson import DipoleState, measure, orientation_work, parse_lesson, from_dict
from emfeeld.fields import DomainError, UniformField


def test_actual_illustration_35_with_e_as_charge_parameter():
    s = DipoleState(charge_C=elementary_charge)
    r = measure(s)
    np.testing.assert_allclose(r["dipole_moment_C_m"], np.full(3, elementary_charge), rtol=1e-15, atol=0)
    np.testing.assert_allclose(r["torque_N_m"], elementary_charge*np.array([-3.,2.,1.]), rtol=1e-15, atol=0)
    assert r["external_orientation_energy_J"] == pytest.approx(-5*elementary_charge, rel=1e-15, abs=0)
    assert r["includes_mutual_energy"] is False and r["time_dynamics"] is False


@pytest.mark.parametrize("q", [0., 1e-30, elementary_charge, 1e-9, 1e-3])
@pytest.mark.parametrize("origin", [(0.,0.,0.), (2.,-3.,4.), (1e6,-1e6,1e6)])
def test_external_forces_and_couple_origin_invariance(q, origin):
    s = DipoleState(charge_C=q,torque_origin_m=origin)
    r=measure(s)
    np.testing.assert_array_equal(r["net_external_force_N"],[0,0,0])
    np.testing.assert_allclose(r["positive_force_N"],q*np.array([2,3,0]),rtol=1e-15,atol=0)
    np.testing.assert_allclose(r["negative_force_N"],-q*np.array([2,3,0]),rtol=1e-15,atol=0)
    expected=np.zeros(3)
    # Independent torque expression from separately applied forces and lever arms.
    for pos, charge in [(s.positive_position_m,q),(s.negative_position_m,-q)]:
        arm=np.array(pos)-origin; force=charge*np.array(s.external_field_N_C)
        expected+=np.cross(arm,force)
    np.testing.assert_allclose(r["torque_N_m"],expected,rtol=3e-9,atol=abs(q)*1e-8)


def test_random_proper_rotation_covariance_translation_and_independent_energy():
    rng=np.random.default_rng(9142)
    s=DipoleState()
    base=measure(s)
    for _ in range(24):
        a=rng.normal(size=(3,3)); rot,_=np.linalg.qr(a)
        if np.linalg.det(rot)<0:rot[:,0]*=-1
        shift=rng.uniform(-2,2,3)
        moved=replace(s,positive_position_m=rot@np.array(s.positive_position_m)+shift,
            negative_position_m=rot@np.array(s.negative_position_m)+shift,
            external_field_N_C=rot@np.array(s.external_field_N_C),torque_origin_m=shift)
        r=measure(moved)
        np.testing.assert_allclose(r["torque_N_m"],rot@base["torque_N_m"],rtol=1e-13,atol=1e-23)
        phi=UniformField("electric",moved.external_field_N_C,origin=tuple(shift))
        independent=moved.charge_C*(phi.potential(moved.positive_position_m)-phi.potential(moved.negative_position_m))
        assert r["external_orientation_energy_J"]==pytest.approx(float(independent),rel=2e-14,abs=1e-23)


@pytest.mark.parametrize("direction, equilibrium, energy",[
    ((1.,0.,0.),"stable_parallel",-2e-9),((-1.,0.,0.),"unstable_antiparallel",2e-9),
    ((0.,1.,0.),"not_equilibrium",0)])
def test_parallel_perpendicular_antiparallel(direction,equilibrium,energy):
    s=DipoleState(positive_position_m=direction,negative_position_m=(0,0,0),external_field_N_C=(2,0,0))
    r=measure(s)
    assert r["equilibrium"]==equilibrium
    assert r["external_orientation_energy_J"]==pytest.approx(energy,rel=1e-15,abs=1e-25)
    assert r["angle_deg"]=={"stable_parallel":0,"unstable_antiparallel":180,"not_equilibrium":90}[equilibrium]


@pytest.mark.parametrize("patch",[{"charge_C":0.},{"external_field_N_C":(0,0,0)}])
def test_degenerate_has_no_preferred_orientation(patch):
    r=measure(replace(DipoleState(),**patch))
    assert r["angle_deg"] is None and r["angle_available"] is False
    assert r["equilibrium"]=="no_preferred_orientation"
    np.testing.assert_array_equal(r["torque_N_m"],[0,0,0])
    assert r["external_orientation_energy_J"]==0


def test_near_collinear_torque_is_not_zeroed():
    s=DipoleState(positive_position_m=(1,1e-14,0),negative_position_m=(0,0,0),external_field_N_C=(1,0,0))
    r=measure(s)
    assert r["torque_N_m"][2]<0 and r["angle_deg"]>0
    assert r["equilibrium"]=="not_equilibrium"


def test_force_swap_reverses_p_torque_energy():
    s=DipoleState(); r=measure(s)
    other=measure(replace(s,positive_position_m=s.negative_position_m,negative_position_m=s.positive_position_m))
    for key in ["dipole_moment_C_m","torque_N_m","external_orientation_energy_J"]:
        np.testing.assert_array_equal(other[key],-np.array(r[key]))


def test_work_sign_and_negative_energy_gradient():
    q=1e-9
    def at(theta):
        return DipoleState(charge_C=q,positive_position_m=(math.cos(theta),math.sin(theta),0),
                           negative_position_m=(0,0,0),external_field_N_C=(3,0,0))
    s0=at(.3); s1=at(1.2)
    w=orientation_work(s0,s1)
    expected=3*q*(math.cos(.3)-math.cos(1.2))
    assert w["external_work_J"]==pytest.approx(expected,rel=2e-14,abs=0)
    assert w["field_work_J"]==-w["external_work_J"]
    h=1e-5
    gradient=(measure(at(.7+h))["external_orientation_energy_J"]-measure(at(.7-h))["external_orientation_energy_J"])/(2*h)
    assert measure(at(.7))["torque_N_m"][2]==pytest.approx(-gradient,rel=3e-10,abs=0)


@pytest.mark.parametrize("patch",[{"charge_C":2e-9},{"external_field_N_C":(3,2,0)},
    {"positive_position_m":(2,3,2)}])
def test_changed_constraints_are_not_rotation_work(patch):
    w=orientation_work(DipoleState(),replace(DipoleState(),**patch))
    assert w["status"]=="unavailable_changed_constraints"
    assert w["external_work_J"] is None and w["field_work_J"] is None


@pytest.mark.parametrize("patch",[
    {"charge_C":True},{"charge_C":-1e-9},{"charge_C":1e-40},{"charge_C":1.1e-3},
    {"charge_C":float("nan")},{"charge_C":10**400},{"charge_C":"1e-9"},
    {"positive_position_m":[True,2,1]},{"positive_position_m":[1+2j,2,1]},
    {"positive_position_m":[1,2]},{"positive_position_m":[float("inf"),2,1]},
    {"positive_position_m":[1e7,0,0]},{"torque_origin_m":[1e7,0,0]},
    {"external_field_N_C":[1e10,0,0]},{"external_field_N_C":[1e-30,0,0]},
    {"positive_position_m":(0,1,0)},
])
def test_invalid_numeric_and_geometry_input(patch):
    with pytest.raises(ValueError):replace(DipoleState(),**patch)


def test_unresolved_large_translation_is_refused():
    with pytest.raises(DomainError):
        DipoleState(positive_position_m=(9e5+2e-9,0,0),negative_position_m=(9e5,0,0))


@pytest.mark.parametrize("patch",[{"lesson_version":True},{"lesson_type":"dynamic_dipole"},
                                  {"time_s":1},{"mass_kg":1}])
def test_schema_does_not_silently_enable_dynamics(patch):
    with pytest.raises(ValueError):from_dict(dict(DipoleState().to_dict(),**patch))


def test_parse_preserves_exact_state_and_refuses_duplicates():
    s=DipoleState()
    assert parse_lesson(json.dumps(s.to_dict()).encode())==s
    with pytest.raises(ValueError,match="duplicate"):parse_lesson('{"charge_C":0,"charge_C":1}')
    with pytest.raises(ValueError):parse_lesson('{"charge_C": NaN}')
    with pytest.raises(ValueError):parse_lesson(b"\xff")


def test_product_cancellation_does_not_invent_parallel_equilibrium():
    eps=2**-52
    s=DipoleState(positive_position_m=(1+eps,1,0),negative_position_m=(0,0,0),
                  external_field_N_C=(1,1-eps,0))
    r=measure(s)
    assert r["torque_N_m"][2]==pytest.approx(-s.charge_C*eps**2,rel=1e-15,abs=0)
    assert r["equilibrium"]=="not_equilibrium" and r["angle_deg"]>0


def test_unrepresentable_nonzero_component_is_not_successful_zero():
    s=DipoleState(charge_C=1e-30,positive_position_m=(1,1e-300,0),
                  negative_position_m=(0,0,0),external_field_N_C=(1,0,0))
    with pytest.raises(DomainError):measure(s)


def test_zero_charge_work_does_not_evaluate_irrelevant_underflow():
    # For a genuinely zero-strength pair, no tiny dot product is required.
    initial = DipoleState(charge_C=0., positive_position_m=(1., 0., 0.),
                          negative_position_m=(0., 0., 0.),
                          external_field_N_C=(1., 1e-300, 0.))
    final = replace(initial, positive_position_m=(1., 1e-300, 0.))
    result = orientation_work(initial, final)
    assert result["status"] == "available"
    assert result["external_work_J"] == result["field_work_J"] == 0.
