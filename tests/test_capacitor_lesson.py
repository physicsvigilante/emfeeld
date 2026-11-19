"""Independent SI/Gauss/energy checks for one ideal whole-gap plate model."""
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from scipy.constants import epsilon_0

from emfeeld.capacitor_lesson import (CapacitorState, measure, field_at_z,
    potential_at_z, from_dict, load_lesson, teaching_case)


def close(a,b,rtol=4e-14):
    assert math.isclose(a,b,rel_tol=rtol,abs_tol=1e-35)


def test_default_and_invariants():
    s=CapacitorState();r=measure(s)
    assert s==load_lesson(Path(__file__).resolve().parents[1]/'examples/lessons/parallel_plate_capacitor.json')
    close(r['capacitance_F'],epsilon_0*0.01/0.005)
    close(r['free_lower_plate_charge_C'],1e-9)
    close(r['free_upper_plate_charge_C'],-1e-9)
    close(r['stored_field_energy_J'],0.5e-9*r['potential_lower_minus_upper_V'])
    close(r['field_z_between_N_C']*s.gap_m,r['potential_lower_minus_upper_V'])
    assert r['ideal_field_outside_N_C']==0
    assert r['finite_plate_fringing_ignored']
    assert r['battery_and_mechanical_work_not_calculated']


@pytest.mark.parametrize('mode',('isolated_charge','battery_voltage'))
@pytest.mark.parametrize('sign',(-1,0,1))
@pytest.mark.parametrize('factor',(1.,2.,4.,7.))
def test_closed_model_against_independent_gauss_decimal(mode,sign,factor):
    with localcontext() as ctx:
        ctx.prec=55
        eps=Decimal(str(epsilon_0))
        area=Decimal('0.01');gap=Decimal('0.005');k=Decimal(str(factor))
        c=eps*k*area/gap
        if mode=='isolated_charge':
            q=Decimal(sign)*Decimal('1e-9');v=q/c
            s=CapacitorState(relative_permittivity=factor,mode=mode,charge_C=sign*1e-9)
        else:
            v=Decimal(sign)*Decimal('25');q=c*v
            s=CapacitorState(relative_permittivity=factor,mode=mode,charge_C=None,voltage_V=sign*25.)
        e=q/(eps*k*area)
        en=q*q/(Decimal(2)*c)
        P=eps*(k-1)*e
        r=measure(s)
        for actual,expected in [(r['capacitance_F'],c),(r['free_lower_plate_charge_C'],q),
            (r['potential_lower_minus_upper_V'],v),(r['field_z_between_N_C'],e),
            (r['stored_field_energy_J'],en),(r['polarization_z_C_m2'],P)]:
            close(actual,float(expected))
        close(r['bound_surface_density_lower_C_m2'],-float(P))
        close(r['bound_surface_density_upper_C_m2'],float(P))
        assert r['stored_field_energy_J']>=0


@pytest.mark.parametrize('mode',('isolated_charge','battery_voltage'))
def test_dielectric_and_gap_comparison(mode):
    initial=CapacitorState() if mode=='isolated_charge' else CapacitorState(
        mode='battery_voltage',charge_C=None,voltage_V=25.)
    v=measure(initial)
    die=__import__('dataclasses').replace(initial,relative_permittivity=4.)
    r=measure(die)
    close(r['capacitance_F']/v['capacitance_F'],4.)
    close(r['stored_field_energy_J']/v['stored_field_energy_J'],
          .25 if mode=='isolated_charge' else 4.)
    close(r['field_z_between_N_C']/v['field_z_between_N_C'],
          .25 if mode=='isolated_charge' else 1.)
    close(r['free_lower_plate_charge_C']/v['free_lower_plate_charge_C'],
          1. if mode=='isolated_charge' else 4.)
    gap=__import__('dataclasses').replace(initial,gap_m=0.0075)
    r2=measure(gap)
    close(r2['capacitance_F']/v['capacitance_F'],2/3)
    close(r2['stored_field_energy_J']/v['stored_field_energy_J'],
          1.5 if mode=='isolated_charge' else 2/3)
    close(r2['field_z_between_N_C']/v['field_z_between_N_C'],
          1. if mode=='isolated_charge' else 2/3)


def test_piecewise_field_and_potential():
    s=CapacitorState(relative_permittivity=3.)
    E=measure(s)['field_z_between_N_C'];d=s.gap_m
    assert field_at_z(s,-d)==0
    assert field_at_z(s,d)==0
    close(field_at_z(s,0),E)
    close(potential_at_z(s,-d),E*d)
    close(potential_at_z(s,0),E*d/2)
    assert potential_at_z(s,d)==0
    for z in (-d/2,d/2):
        with pytest.raises(ValueError,match='one-sided'):
            field_at_z(s,z)
    close(potential_at_z(s,-d/2),E*d)
    assert potential_at_z(s,d/2)==0


@pytest.mark.parametrize('key',('1','2','3','4'))
def test_teacher_cases_retains_source_geometry_and_physical_reference(key):
    s=CapacitorState(area_m2=0.04,gap_m=.008,relative_permittivity=2.,charge_C=-2e-9)
    result=teaching_case(s,key)
    assert result.area_m2==s.area_m2 and result.gap_m==s.gap_m
    assert result.relative_permittivity==(4. if key in ('2','4') else 1.)
    if key in ('1','2'):
        assert result.mode=='isolated_charge'
        close(measure(result)['free_lower_plate_charge_C'],measure(s)['free_lower_plate_charge_C'])
    else:
        assert result.mode=='battery_voltage'
        close(measure(result)['potential_lower_minus_upper_V'],measure(s)['potential_lower_minus_upper_V'])
    assert measure(result)['field_z_between_N_C']<0
    assert s.relative_permittivity==2.


@pytest.mark.parametrize('key',('1','2','3','4'))
def test_zero_and_negative_polarity(key):
    s=CapacitorState(charge_C=0.)
    t=teaching_case(s,key)
    m=measure(t)
    assert m['field_z_between_N_C']==0
    assert m['stored_field_energy_J']==0
    assert m['free_lower_plate_charge_C']==0


def test_roundtrip_both_modes_and_invalid_json(tmp_path):
    for s in (CapacitorState(),CapacitorState(mode='battery_voltage',charge_C=None,voltage_V=-65.)):
        assert from_dict(s.to_dict())==s
        f=tmp_path/('isolated.json' if s.charge_C is not None else 'battery.json')
        f.write_text(json.dumps(s.to_dict()))
        assert load_lesson(f)==s
    for data in ('{"x":1,"x":2}',
                 '{"lesson_version":1,"lesson_version":1}',
                 '{"lesson_version":NaN}',
                 '{"lesson_version":Infinity}'):
        f=tmp_path/'bad.json';f.write_text(data)
        with pytest.raises(ValueError):load_lesson(f)


@pytest.mark.parametrize('patch',[
    {'area_m2':True},{'gap_m':'0.005'},{'relative_permittivity':False},
    {'relative_permittivity':0.999},{'relative_permittivity':11},
    {'area_m2':1e-8},{'area_m2':.5},{'gap_m':1e-7},
    {'gap_m':.02},{'gap_m':.03},{'mode':'unknown'},
    {'mode':'battery_voltage'},{'charge_C':None},
    {'voltage_V':5.},{'charge_C':1e-3},{'charge_C':float('nan')},
    {'area_m2':float('inf')},{'lesson_version':True},{'lesson_version':2},
    {'lesson_type':'electric_dipole'},{'other_field':3.}
])
def test_invalid_strict_admission(patch):
    d=CapacitorState().to_dict();d.update(patch)
    with pytest.raises(ValueError):from_dict(d)


def test_battery_mode_needs_no_charge_and_rejects_ambiguity():
    d=CapacitorState().to_dict()
    d['mode']='battery_voltage';d.pop('charge_C');d['voltage_V']=-7.5
    assert from_dict(d).mode=='battery_voltage'
    d['charge_C']=1e-9
    with pytest.raises(ValueError):from_dict(d)


def test_no_capacitor_field_solver_imports_in_new_model():
    import inspect
    import emfeeld.capacitor_lesson as model
    assert 'pyvista' not in inspect.getsource(model).lower()
    assert 'vtk' not in inspect.getsource(model).lower()
