"""JEE wire B and Ampere circulation: independent SI and refusal challenges."""
import json
import math
from decimal import Decimal, getcontext

import numpy as np
import pytest
from scipy.constants import mu_0

from emfeeld.wire_magnetism import (
    TYPE, WireState, basis, from_dict, load_lesson, magnetic_field,
    measure, sample_ampere_loop, teaching_case,
)


@pytest.mark.parametrize('I',(-350.0,-2.0,0.,2.0,350.0))
@pytest.mark.parametrize('R',(.002,.2,5.0))
@pytest.mark.parametrize('axis',((0.,0.,1.),(1.,0.,0.),(1.,2.,3.)))
def test_ideal_wire_B_right_hand_and_ampere_independent(I,R,axis):
    s=WireState(origin_m=[2,-3,5],axis_direction=axis,current_A=I,loop_radius_m=R)
    d=sample_ampere_loop(s)
    u,e1,e2=basis(s)
    points=d['points_m'];B=d['field_T']; tangent=d['tangents'];n=s.samples_per_loop
    rho=points-np.asarray(s.origin_m)
    assert np.allclose(rho@u,0,atol=4e-14)  # every point in perpendicular plane
    assert np.allclose(tangent@u,0,atol=1e-14)
    assert np.allclose(np.linalg.norm(rho,axis=1),R,rtol=2e-12)
    assert np.allclose(np.cross(e1,e2),u,atol=2e-15)
    independent=(mu_0*I/(2*math.pi*R))*tangent
    if I:
        # Test relative *vector norm*, not componentwise relative precision
        # for ideally zero components after translated-coordinate subtraction.
        rel=np.linalg.norm(B-independent,axis=1)/np.linalg.norm(independent,axis=1)
        assert np.max(rel) < 1e-11
    else:
        assert np.count_nonzero(B)==0
    assert np.allclose(np.einsum('ij,ij->i',B,tangent),mu_0*I/(2*math.pi*R),rtol=1e-11,atol=1e-19)
    assert np.isclose(d['sampled_circulation_T_m'],mu_0*I,rtol=3e-12,atol=1e-19)
    assert d['ampere_expected_T_m']==mu_0*I
    assert len(points)==n


def test_right_hand_in_world_coordinates_and_reverse():
    s=WireState(current_A=5,loop_radius_m=.3)
    p=[.3,0,0]
    actual=magnetic_field(s,p)
    assert actual[0]==0 and actual[2]==0 and actual[1]>0
    expected=mu_0*5/(2*math.pi*.3)
    assert actual[1]==pytest.approx(expected,rel=1e-13)
    assert np.allclose(magnetic_field(WireState(current_A=-5,loop_radius_m=.3),p),-actual)


def test_decimal_reference_current_radius_and_ratio():
    getcontext().prec=60
    s=WireState(current_A=4.0,loop_radius_m=.12)
    v=measure(s); twice=measure(teaching_case(s,'2'))
    # Decimal independent scalar arithmetic to check sign and units; constants
    # are the installed scipy mu_0 represented exactly as a decimal here.
    reference=float(Decimal(str(mu_0))*Decimal(4)/(Decimal(2)*Decimal(str(math.pi))*Decimal('.12')))
    assert v['field_magnitude_T']==pytest.approx(reference,rel=3e-16)
    assert twice['field_magnitude_T']==pytest.approx(v['field_magnitude_T']/2,rel=4e-16)
    assert twice['sampled_ampere_circulation_T_m']==pytest.approx(v['sampled_ampere_circulation_T_m'],rel=2e-15)
    reverse=measure(teaching_case(s,'3'))
    assert reverse['signed_tangent_field_T']==-v['signed_tangent_field_T']
    assert reverse['sampled_ampere_circulation_T_m']==pytest.approx(-v['sampled_ampere_circulation_T_m'],rel=2e-15)
    zero=measure(teaching_case(s,'4'))
    assert zero['field_magnitude_T']==zero['sampled_ampere_circulation_T_m']==0
    assert np.count_nonzero(magnetic_field(teaching_case(s,'4'),[0,0,0]))==0


@pytest.mark.parametrize('bad',[
 {'current_A':1e-9},{'current_A':1e6},{'axis_direction':(0,0,0)},
 {'axis_direction':(1e-15,0,0)},{'axis_direction':(1e8,0,0)},
 {'loop_radius_m':0},{'loop_radius_m':1e-5},{'loop_radius_m':101},
 {'samples_per_loop':11},{'samples_per_loop':193},{'samples_per_loop':48.0},
 {'current_A':True},{'current_A':'5'},{'loop_radius_m':float('nan')},
 {'origin_m':(0,0,101)},{'origin_m':(0,0,'0')},
])
def test_bad_state_refuses(bad):
    with pytest.raises(ValueError):WireState(**bad)


def test_axis_singular_refusal_and_numerical_resolution():
    s=WireState(origin_m=[1,2,3],axis_direction=[0,0,1],current_A=8)
    for point in ([1,2,3],[1,2,4],[1+1e-15,2,3]):
        with pytest.raises(ValueError,match='on or numerically unresolved'):
            magnetic_field(s,point)
    assert np.linalg.norm(magnetic_field(s,[1+1e-5,2,3]))>0
    for bad in ([[1,2,math.nan]],[[1,2,'3']],[[True,False,False]],[[1,2]],[] ,[[1e8,0,0]]):
        with pytest.raises(ValueError):magnetic_field(s,bad)


def test_zero_current_on_axis_and_signed_direction():
    s=WireState(current_A=0)
    assert (magnetic_field(s,np.zeros((2,3)))==0).all()
    assert measure(s)['expected_mu0_I_T_m']==0
    assert magnetic_field(WireState(current_A=2),np.array([.3,0.,0.]))[1]>0
    assert magnetic_field(WireState(current_A=-2),np.array([.3,0.,0.]))[1]<0


@pytest.mark.parametrize('token',('1e-400','-1e-400','-1e-9999','1e309','-1e309'))
def test_raw_json_unrepresentable_current_token_refuses(tmp_path,token):
    d=WireState().to_dict();s=json.dumps(d)
    raw=s.replace('"current_A": 5.0','"current_A": '+token)
    path=tmp_path/'lesson.json';path.write_text(raw)
    with pytest.raises(ValueError):load_lesson(path)


@pytest.mark.parametrize('token',('0.0','-0.0','0e-9999','-0e-9999'))
def test_raw_json_exact_zero_admits(tmp_path,token):
    raw=json.dumps(WireState().to_dict()).replace('"current_A": 5.0','"current_A": '+token)
    path=tmp_path/'lesson.json';path.write_text(raw)
    assert measure(load_lesson(path))['field_magnitude_T']==0


def test_json_duplicates_unknowns_and_schema_refuse(tmp_path):
    d=WireState().to_dict()
    assert from_dict(d).to_dict()==d
    for bad in [dict(d,nonphysical_solver=True),dict(d,lesson_version=True),
                dict(d,lesson_type='charged_wire'),{k:v for k,v in d.items() if k!='current_A'},
                dict(d,loop_radius_m='0.2'),dict(d,current_A=None)]:
        with pytest.raises(ValueError):from_dict(bad)
    p=tmp_path/'in.json'
    p.write_text(json.dumps(d).replace('"current_A": 5.0','"current_A": 5.0, "current_A": 8.0'))
    with pytest.raises(ValueError,match='duplicate'):load_lesson(p)
    p.write_text(json.dumps(d).replace('"current_A": 5.0','"current_A": NaN'))
    with pytest.raises(ValueError,match='nonfinite'):load_lesson(p)


def test_invalid_teaching_case_refuses():
    with pytest.raises(ValueError):teaching_case(WireState(),'5')
    with pytest.raises(ValueError):teaching_case(WireState(loop_radius_m=75),'2')


@pytest.mark.parametrize('probes', [
    [True, 0, 0],
    [0, False, 1],
    ((1.0, 0.0, 0.0), (2.0, np.bool_(False), 0.0)),
    np.array([[1.0, False, 0.0]], dtype=object),
    np.array([np.bool_(True), 0.0, 0.0], dtype=object),
])
@pytest.mark.parametrize('current', (0, 3))
def test_direct_python_mixed_boolean_probe_refused_before_numeric_coercion(probes,current):
    with pytest.raises(ValueError,match='must not contain booleans'):
        magnetic_field(WireState(current_A=current), probes)


def test_numeric_probe_equivalents_still_work_with_zero_and_nonzero_current():
    for x in ([1, 0, 0], (1., 0., 0.), np.array([1, 0, 0], dtype=np.int64)):
        assert magnetic_field(WireState(current_A=0), x).shape == (3,)
        assert magnetic_field(WireState(current_A=3), x)[1] > 0
