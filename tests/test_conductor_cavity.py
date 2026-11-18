"""Analytic references and refusal cases for the opt-in JEE cavity lesson."""
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy.constants import epsilon_0

from emfeeld.fields import DomainError
from emfeeld.conductor_cavity import (ConductorCavity, K, from_dict, load_lesson,
    spherical_quadrature, trace_cavity_lines, seed_directions)


@pytest.mark.parametrize('mode,Q', [('isolated',0), ('isolated',-3e-9), ('grounded',0)])
@pytest.mark.parametrize('q', [1e-9,-2e-9,0])
def test_charge_balance_metal_and_exterior(mode,Q,q):
    m=ConductorCavity(charge_C=q,conductor_charge_C=Q,mode=mode)
    outer=Q+q if mode=='isolated' else 0
    s=m.summary()
    assert s['inner_total_C']==-q and s['outer_total_C']==outer
    assert s['conductor_total_C']==outer-q
    metal=np.array([[1.05,0,0],[0,1.13,0],[0,0,-1.2]])
    np.testing.assert_array_equal(m.field(metal),np.zeros((3,3)))
    np.testing.assert_allclose(m.potential(metal),K*outer/1.25,rtol=2e-15)
    p=np.array([[2,0,0],[0,3,0],[2,-3,4.]])
    r=np.linalg.norm(p,axis=1)
    np.testing.assert_allclose(m.field(p),K*outer*p/r[:,None]**3,rtol=3e-15,atol=1e-15)
    np.testing.assert_allclose(m.potential(p),K*outer/r,rtol=2e-15)


@pytest.mark.parametrize('q',[1e-9,-1e-9])
@pytest.mark.parametrize('offset',[(.5,0,0),(.12,-.36,.23),(0,0,0),(1e-12,0,0)])
def test_independent_image_reference_and_shapes(q,offset):
    m=ConductorCavity(charge_C=q,charge_position_m=offset)
    p=np.array([[[.1,.2,.3],[-.4,.1,.2]],[[.7,-.2,0],[-.3,-.3,-.3]]])
    a=np.array(offset);t=np.linalg.norm(a)
    d=p-a;r=np.linalg.norm(d,axis=-1)
    E=K*q*d/r[...,None]**3;V=K*q/r
    if t:
        image_position=a/t**2;image_q=-q/t
        b=p-image_position;ri=np.linalg.norm(b,axis=-1)
        E+=K*image_q*b/ri[...,None]**3;V+=K*image_q/ri
    else:
        V-=K*q
    V+=K*q/1.25
    np.testing.assert_allclose(m.field(p),E,rtol=5e-14,atol=2e-13)
    np.testing.assert_allclose(m.potential(p),V,rtol=5e-14,atol=2e-13)
    assert m.field(p[0,0]).shape==(3,) and m.potential(p[0,0]).shape==()


@pytest.mark.parametrize('a',[0,.5,.8,.9])
def test_boundary_conditions_surface_density_and_gauss_integral(a):
    m=ConductorCavity(charge_position_m=(a,0,0))
    n=seed_directions(64)
    np.testing.assert_allclose(m.potential(n),m.conductor_potential_V,atol=2e-13)
    np.testing.assert_allclose(m.potential(1.25*n),m.conductor_potential_V,atol=2e-13)
    # Analytic cavity one-sided limit approaches normal E=-sigma/epsilon0.
    e=m.field(n*(1-1e-8));sigma=m.inner_density(n)
    np.testing.assert_allclose(e, -sigma[:,None]*n/epsilon_0,rtol=1e-5,atol=1e-5)
    fine=spherical_quadrature(m,256)
    assert abs(fine['error_C']) <= 2e-13*abs(m.charge_C)
    assert fine['renormalized'] is False
    if a:
        coarse=spherical_quadrature(m,8)
        assert abs(fine['error_C']) < abs(coarse['error_C'])


def test_near_far_ratio_27_is_density_not_hemisphere_charge():
    m=ConductorCavity()
    sigma=m.inner_density([[1,0,0],[-1,0,0]])
    assert sigma[0]/sigma[1]==pytest.approx(27,rel=1e-14)
    assert sigma[0]<0 and sigma[1]<0
    centre=replace(m,charge_position_m=(0,0,0))
    np.testing.assert_allclose(centre.inner_density(seed_directions(32)),-1e-9/(4*math.pi))


def test_rotation_covariance_and_grounding_does_not_change_cavity_field():
    m=ConductorCavity(charge_position_m=(.2,.3,-.1))
    q=np.array([[0,-1,0],[0,0,1],[-1,0,0.]])
    p=np.array([[.2,-.1,.3],[-.5,.1,-.2]])
    rotated=replace(m,charge_position_m=tuple(q@np.array(m.charge_position_m)))
    np.testing.assert_allclose(rotated.field(p@q.T),m.field(p)@q.T,rtol=1e-14)
    np.testing.assert_allclose(rotated.potential(p@q.T),m.potential(p),rtol=1e-14)
    grounded=replace(m,mode='grounded')
    np.testing.assert_array_equal(grounded.field(p),m.field(p))
    np.testing.assert_allclose(m.potential(p)-grounded.potential(p),m.conductor_potential_V,rtol=1e-14)


def test_field_is_negative_gradient_and_not_image_continuation_in_metal():
    m=ConductorCavity()
    point=np.array([.2,.15,-.3]);h=1e-5
    gradient=np.array([(m.potential(point+axis*h)-m.potential(point-axis*h))/(2*h) for axis in np.eye(3)])
    np.testing.assert_allclose(m.field(point),-gradient,rtol=2e-9)
    # The image at x=2 lies in the physical exterior: physical field is regular!
    np.testing.assert_allclose(m.field([2,0,0]),[K*1e-9/4,0,0])
    np.testing.assert_array_equal(m.field([1.1,0,0]),[0,0,0])


@pytest.mark.parametrize('q', [1e-9,-1e-9])
@pytest.mark.parametrize('a',[(0,0,0),(.5,0,0),(0,.8,.2)])
def test_field_lines_stay_in_cavity_and_arrows_follow_field(q,a):
    m=ConductorCavity(charge_C=q,charge_position_m=a)
    lines=trace_cavity_lines(m,count=12)
    for line in lines:
        points=line['points_m']
        assert line['termination']=='inner_surface_approached'
        assert line['is_particle_trajectory'] is False
        assert (np.linalg.norm(points,axis=1)<1).all()
        assert (np.linalg.norm(points-np.array(a),axis=1)>0).all()
        delta=np.diff(points,axis=0)
        e=m.field((points[:-1]+points[1:])/2)
        assert (np.sum(e*delta,axis=1)>0).all()
        boundary=points[-1] if q>0 else points[0]
        assert np.linalg.norm(boundary)>1-1e-4
    assert len(lines)==12


def test_trace_limits_are_reported_not_concealed():
    m=ConductorCavity()
    assert all(l['termination']=='step_limit' for l in trace_cavity_lines(m,count=4,max_steps=1))
    assert trace_cavity_lines(replace(m,charge_C=0))==[]


@pytest.mark.parametrize('patch',[
    {'inner_radius_m':0},{'inner_radius_m':1e200},{'inner_radius_m':True},
    {'outer_radius_m':1},{'outer_radius_m':6}, {'charge_C':float('nan')},
    {'charge_C':1e-300},{'charge_C':10**400},{'charge_C':'1e-9'},
    {'charge_position_m':[True,0,0]},{'charge_position_m':[1,0,0]},
    {'charge_position_m':[[0,0,0]]},{'charge_position_m':[float('inf'),0,0]},
    {'mode':[]},{'mode':'floating'},{'mode':'grounded','conductor_charge_C':1e-9},
])
def test_bad_physical_input_rejected(patch):
    with pytest.raises(ValueError):replace(ConductorCavity(),**patch)


@pytest.mark.parametrize('points', [[True,0,0],['0',0,0],[[1,2]], [float('nan'),0,0], [1e8,0,0]])
def test_bad_probes_rejected(points):
    with pytest.raises(ValueError):ConductorCavity().field(points)


@pytest.mark.parametrize('point',[[.5,0,0],[1,0,0],[1.25,0,0]])
def test_singular_and_discontinuous_field_not_softened(point):
    with pytest.raises(DomainError):ConductorCavity().field(point)
    if point[0]==.5:
        with pytest.raises(DomainError):ConductorCavity().potential(point)


def test_zero_charge_and_schema_and_input_bytes(tmp_path):
    m=ConductorCavity(charge_C=0)
    np.testing.assert_array_equal(m.field([[.5,0,0],[1,0,0],[1.25,0,0]]),np.zeros((3,3)))
    for d in [None,[],{},dict(m.to_dict(),extra=1),dict(m.to_dict(),lesson_version=True)]:
        with pytest.raises(ValueError):from_dict(d)
    p=tmp_path/'lesson.json';raw=json.dumps(m.to_dict()).encode();p.write_bytes(raw)
    assert load_lesson(p)==m and p.read_bytes()==raw
    p.write_text('{"lesson_version":1,"lesson_version":1}')
    with pytest.raises(ValueError,match='duplicate'):load_lesson(p)


def test_sampled_lines_converge_not_massaged_to_match():
    m=ConductorCavity(charge_position_m=(.6,.1,0))
    coarse=trace_cavity_lines(m,count=8,step=.04)
    fine=trace_cavity_lines(m,count=8,step=.02)
    finer=trace_cavity_lines(m,count=8,step=.01)
    err=lambda a,b:max(np.linalg.norm(x['points_m'][-1]-y['points_m'][-1]) for x,y in zip(a,b))
    assert err(fine,finer)<2e-4
    assert err(coarse,finer)<5e-4


def test_headless_model_does_not_import_graphics():
    root=Path(__file__).resolve().parents[1]
    r=subprocess.run([sys.executable,'-c',
        'import sys; from emfeeld.conductor_cavity import ConductorCavity; '
        'ConductorCavity().field([0,0,0]); assert "pyvista" not in sys.modules'],
        cwd=root,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
