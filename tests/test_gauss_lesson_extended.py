"""Author-owned analytic/admission/evidence challenges; not independent review."""
from dataclasses import replace
import hashlib
import json
import math

import numpy as np
import pytest
from scipy.constants import epsilon_0

from emfeeld.fields import DomainError
from emfeeld.gauss_lesson import (GaussState,GaussianCube,GaussianSphere,HeldCharge,
    from_dict,parse_lesson,measure)
from emfeeld.gauss_view import save_snapshot


@pytest.mark.parametrize('position',[(.7,.1,-.2),(1.7,.2,-.3),(-1.3,1.6,.3)])
@pytest.mark.parametrize('q',[1e-9,-2e-9])
def test_rectangular_face_integral_independent_tensor_quadrature(position,q):
    cube=GaussianCube()
    nodes,weights=np.polynomial.legendre.leggauss(72)
    a,b=np.meshgrid(nodes,nodes,indexing='ij');w=np.outer(weights,weights)
    reference=[]
    for axis in range(3):
        for sign in (1,-1):
            p=np.zeros(a.shape+(3,));p[...,axis]=sign
            p[...,(axis+1)%3]=a;p[...,(axis+2)%3]=b
            d=p-np.asarray(position);r=np.sqrt(np.sum(d*d,axis=-1))
            reference.append(float(np.sum(q/(4*np.pi*epsilon_0)*sign*d[...,axis]/r**3*w)))
    np.testing.assert_allclose(cube.flux([HeldCharge(q,position)])['face_flux_N_m2_per_C'],
                               reference,rtol=4e-13,atol=3e-13)


@pytest.mark.parametrize('gap',[1e-6,1e-9,1e-12])
@pytest.mark.parametrize('sign',[1,-1])
def test_near_edge_closure_is_not_forced_by_rescaling(gap,sign):
    r=GaussianCube().flux([HeldCharge(sign*1e-9,(1-gap,1-gap,0))])
    assert r['sum_faces_N_m2_per_C']==pytest.approx(sign*1e-9/epsilon_0,rel=2e-14)
    assert r['unrenormalized'] is True


def test_far_field_face_sign_and_leading_order():
    pos=np.array([1e8,1e8,1e8]);r=GaussianCube().flux([HeldCharge(1e-9,tuple(pos))])
    expected=[]
    for axis in range(3):
        for sign in (1,-1):
            center=np.eye(3)[axis]*sign;d=center-pos
            expected.append(4*1e-9/(4*np.pi*epsilon_0)*sign*d[axis]/np.linalg.norm(d)**3)
    np.testing.assert_allclose(r['face_flux_N_m2_per_C'],expected,rtol=3e-15,atol=0)
    assert abs(r['sum_faces_N_m2_per_C'])<1e-29


@pytest.mark.parametrize('scale',[1e-5,.7,100])
def test_rigid_motion_and_scale_covariance(scale):
    theta=.37
    rotation=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1]])
    c=np.array([10,-20,30])*scale;p=np.array([.3,-.4,.2])
    moved=GaussianCube(tuple(c),2*scale,rotation)
    a=GaussianCube().flux([HeldCharge(1e-9,tuple(p))])
    b=moved.flux([HeldCharge(1e-9,tuple(c+scale*rotation@p))])
    np.testing.assert_allclose(a['face_flux_N_m2_per_C'],b['face_flux_N_m2_per_C'],rtol=2e-14)


@pytest.mark.parametrize('surface',[GaussianCube,GaussianSphere])
def test_unrepresentable_world_geometry_refused(surface):
    with pytest.raises(ValueError,match='center'):surface(center_m=(1e16,0,0))


def test_world_roundoff_near_rotated_boundary_refused():
    c=GaussianCube(center_m=(1e6,0,0))
    with pytest.raises(DomainError):c.flux([HeldCharge(1e-9,(1e6+1-1e-10,0,0))])


@pytest.mark.parametrize('rotation',[
    [[True,False,False],[False,True,False],[False,False,True]],
    [['1','0','0'],['0','1','0'],['0','0','1']],
    [[1+1e-10,0,0],[0,1,0],[0,0,1]], [[1,0,0],[0,1,0]]])
def test_rotation_admission_is_strict(rotation):
    with pytest.raises(ValueError):GaussianCube(rotation=rotation)


@pytest.mark.parametrize('order',[True,0,1,257,10**100,4.5])
def test_bounded_quadrature_refuses_before_allocation(order):
    with pytest.raises(ValueError):GaussianSphere().flux([HeldCharge(1e-9,(0,0,0))],n_polar=order)


def test_coplanar_exterior_face_is_zero_not_a_spurious_full_turn():
    r=GaussianCube().flux([HeldCharge(1e-9,(1,3,0))])
    assert r['face_flux_N_m2_per_C'][0]==0
    assert abs(r['sum_faces_N_m2_per_C'])<1e-13


def test_boundary_is_explicit_unavailable_in_serializable_state():
    state=GaussState(charges=(HeldCharge(1e-9,(1,0,0)),))
    result=measure(state)
    assert result['status']=='undefined_boundary' and result['exact_total_N_m2_per_C'] is None
    assert parse_lesson(json.dumps(state.to_dict()))==state


@pytest.mark.parametrize('patch',[{'extra':1},{'gauss_lesson_version':True},{'charges':[]},
                                  {'surface':{'type':'plane'}}])
def test_strict_schema(patch):
    with pytest.raises(ValueError):from_dict(dict(GaussState().to_dict(),**patch))


def test_duplicate_keys_and_original_bytes(tmp_path):
    with pytest.raises(ValueError,match='duplicate'):parse_lesson('{"surface":{},"surface":{}}')
    state=GaussState();raw=json.dumps(state.to_dict(),indent=4).encode()
    out=tmp_path/'new';report=save_snapshot(state,out,source_bytes=raw)
    assert (out/'authored-input.json').read_bytes()==raw
    assert report['original_input_equals_current_state'] is True
    for name,h in json.loads((out/'integrity.json').read_text())['files'].items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==h


def test_output_safety_and_invalid_input_leave_no_new_output(tmp_path):
    state=GaussState();out=tmp_path/'sealed';save_snapshot(state,out)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    with pytest.raises(FileExistsError):save_snapshot(state,out)
    with pytest.raises(ValueError):save_snapshot(state,out/'child')
    assert {p.name:p.read_bytes() for p in out.iterdir()}==before
    with pytest.raises(ValueError):save_snapshot(state,tmp_path/'bad',source_bytes=b'{}')
    assert not (tmp_path/'bad').exists()


def test_late_failure_is_retained_not_success(tmp_path,monkeypatch):
    import emfeeld.gauss_view as module
    writer=module._json
    def fail_report(path,value):
        if path.name=='report.json':raise RuntimeError('injected report failure')
        writer(path,value)
    monkeypatch.setattr(module,'_json',fail_report)
    with pytest.raises(RuntimeError):save_snapshot(GaussState(),tmp_path/'failed')
    assert json.loads((tmp_path/'failed/outcome.json').read_text())['execution_complete'] is False
    assert not (tmp_path/'failed/integrity.json').exists()


def test_large_finite_rotation_rejected_without_numeric_overflow():
    with pytest.raises(ValueError):GaussianCube(rotation=np.eye(3)*1e308)


@pytest.mark.parametrize('order',[None,{},[],True,'24'])
def test_measure_invalid_order_type(order):
    with pytest.raises(ValueError):measure(GaussState(),order=order)


def test_nonbytes_source_rejected_before_writes(tmp_path):
    with pytest.raises(ValueError,match='bytes'):
        save_snapshot(GaussState(),tmp_path/'new',source_bytes=json.dumps(GaussState().to_dict()))
    assert not (tmp_path/'new').exists()
