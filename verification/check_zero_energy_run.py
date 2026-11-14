"""Separate energy/time-quadrature reference, with no import of emfeeld.

This qualifies only the explicit illustrative issue-7 fixture, not arbitrary models.
Same author, not independent review. No fitted trajectory or alternate initial data.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.constants import epsilon_0
from scipy.integrate import quad
from scipy.optimize import brentq


def check(folder):
    folder=Path(folder)
    scene=json.loads((folder/'source.json').read_text())
    assert scene['kind']=='electric' and scene['duration_s']==.45 and scene['samples']==451
    assert scene['sources']==[
        dict(type='solid_sphere',charge_C=2e-9,center_m=[-1.,0.,0.],radius_m=.25),
        dict(type='solid_sphere',charge_C=-2e-9,center_m=[1.,0.,0.],radius_m=.25)]
    assert scene['particles']==[dict(mass_kg=1e-11,charge_C=1e-12,position_m=[0.,0.,0.],velocity_m_s=[0.,0.,0.])]
    k=1/(4*np.pi*epsilon_0); charge=2e-9; q=1e-12; m=1e-11
    # With a=1 m and initial x=0: v^2 = 4 k q Q x / [m (1-x^2)].
    # y=s^2 regularizes the integrable square-root singularity in dt/dx at rest.
    def time_to(x):
        return np.sqrt(m/(k*q*charge))*quad(lambda s: np.sqrt(1-s**4),0,np.sqrt(x),epsabs=1e-13,epsrel=1e-13)[0]
    with np.load(folder/'run/native/trajectories.npz',allow_pickle=False) as data:
        t=data['p0_time_s']; r=data['p0_position_m']; v=data['p0_velocity_m_s']
        kinetic=data['p0_kinetic_J']; potential=data['p0_potential_J']
    x=np.array([0. if time==0 else brentq(lambda x: time_to(x)-time,0,.7,xtol=2e-14,rtol=2e-14) for time in t])
    speed=np.sqrt(4*k*q*charge*x/(m*(1-x*x)))
    u=-2*k*q*charge*x/(1-x*x)
    np.testing.assert_allclose(r[:,0],x,atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(v[:,0],speed,atol=2e-9,rtol=2e-9)
    np.testing.assert_array_equal(r[:,1:],0.); np.testing.assert_array_equal(v[:,1:],0.)
    np.testing.assert_allclose(kinetic,.5*m*speed**2,atol=2e-22,rtol=2e-10)
    np.testing.assert_allclose(potential,u,atol=2e-22,rtol=2e-10)
    assert np.max(x)<.75  # No source intersection; formulas stay exterior.
    native=json.loads((folder/'run/native/result.json').read_text())
    results={row['id']:row for row in native['results']}
    np.testing.assert_allclose(results['E_origin']['value'],[2*k*charge,0,0],rtol=2e-14,atol=0)
    assert results['V_origin']['value']==0 and all(row['status']=='ok' for row in results.values())
    return dict(passed=True,samples_checked=len(t),reference='Regularized energy/time quadrature; same-author, no engine import',
        max_position_difference_m=float(np.max(np.abs(r[:,0]-x))),
        max_velocity_difference_m_s=float(np.max(np.abs(v[:,0]-speed))),
        final_position_m=r[-1].tolist(),final_velocity_m_s=v[-1].tolist(),
        all_samples_outside_sources=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder');p.add_argument('--output',required=True)
    a=p.parse_args(); result=check(a.folder)
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2))
