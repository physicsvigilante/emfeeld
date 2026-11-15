"""Independent analytical expressions and RK4 for bounded E1/G1/T1 sweep cases.

This module does NOT import emfeeld or use its source fields, solvers or comparisons.
The same author prepared references; agreement is not independent human review.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.constants import G, epsilon_0

K = 1.0 / (4.0 * np.pi * epsilon_0)


def charge_mass(kind, source):
    if kind == 'electric':
        return K*source.get('charge_C',0.), K*source.get('charge_per_m_C_m',0.)
    return -G*source.get('mass_kg',0.), -G*source.get('mass_per_m_kg_m',0.)


def at_source(kind, src, point):
    """Independent ideal static source formulas, with explicit reference potentials."""
    p=np.asarray(point,dtype=float)
    center=np.asarray(src.get('center_m',[0,0,0]),dtype=float)
    d=p-center; r=float(np.linalg.norm(d))
    category=src['type']; strength, linear=charge_mass(kind,src)
    if category=='uniform':
        f=np.asarray(src['field_N_C' if kind=='electric' else 'field_m_s2'],float)
        return f, -float(np.dot(f,p-np.asarray(src.get('origin_m',[0,0,0]))))
    if category=='point':
        assert r>0
        return strength*d/r**3, strength/r
    if category=='solid_sphere':
        R=src['radius_m']
        if r <= R:return strength*d/R**3,strength*(3-r*r/R**2)/(2*R)
        return strength*d/r**3,strength/r
    if category=='shell':
        R=src['radius_m'];assert not np.isclose(r,R)
        if r<R:return np.zeros(3),strength/R
        return strength*d/r**3,strength/r
    if category=='line':
        direction=np.asarray(src['direction'],float)
        direction/=np.linalg.norm(direction)
        transverse=d-direction*np.dot(d,direction)
        rho=float(np.linalg.norm(transverse));assert rho>0
        return 2*linear*transverse/rho**2,-2*linear*np.log(rho/src['reference_radius_m'])
    raise AssertionError(f'Unexpected source: {category}')


def field_potential(scene,point):
    field=np.zeros(3);potential=0.
    for src in scene['sources']:
        f,v=at_source(scene['kind'],src,point)
        field+=f;potential+=v
    return field,float(potential)


def rk4(scene,p_index,steps_per_sample):
    """Independent fixed-step integration on the same saved physical times."""
    initial=scene['particles'][p_index]
    m=initial['mass_kg']; ratio=initial['charge_C']/m if scene['kind']=='electric' else 1.
    state=np.array(initial['position_m']+initial['velocity_m_s'],float)
    dt=scene['duration_s']/((scene['samples']-1)*steps_per_sample)
    out=[state.copy()]
    def derivative(x):
        f,_=field_potential(scene,x[:3])
        return np.concatenate((x[3:],ratio*f))
    for _ in range(scene['samples']-1):
        for __ in range(steps_per_sample):
            a=derivative(state);b=derivative(state+.5*dt*a)
            c=derivative(state+.5*dt*b);d=derivative(state+dt*c)
            state=state+(dt/6)*(a+2*b+2*c+d)
        out.append(state.copy())
    return np.asarray(out)


def close(actual,expected, *, atol,rtol=2e-6):
    if not np.allclose(actual,expected,rtol=rtol,atol=atol):
        delta=np.max(np.abs(np.asarray(actual)-np.asarray(expected)))
        raise AssertionError(f'independent reference mismatch, maximum absolute delta {delta}')


def verify(directory,case):
    directory=Path(directory)
    summary=json.loads((directory/'summary.json').read_text())
    assert summary['status']=='complete' and len(summary['members'])==2
    locations=[directory/'baseline']+[directory/m['run_path'] for m in summary['members']]
    reports=[json.loads((p/'native/result.json').read_text()) for p in locations]
    checks=[]; dynamic=case in ('E1','G1')
    for member, (location,report) in enumerate(zip(locations,reports)):
        scene=report['input']['scene']
        assert scene['kind']==('gravity' if case=='G1' else 'electric')
        for observation in report['results']:
            if observation['type'] not in ('field','potential'): continue
            assert observation['status']=='ok'
            field,potential=field_potential(scene,observation['position_m'])
            if observation['type']=='field':
                close(observation['value'],field,atol=2e-11,rtol=1e-10)
            else:close(observation['value'],potential,atol=2e-11,rtol=1e-10)
            checks.append((member,observation['id'],'independent_static'))
        if not dynamic:continue
        with np.load(location/'native/trajectories.npz',allow_pickle=False) as values:
            for body in range(len(scene['particles'])):
                true=np.column_stack((values[f'p{body}_position_m'],values[f'p{body}_velocity_m_s']))
                reference=rk4(scene,body,40)
                coarse=rk4(scene,body,20)
                close(true,reference,atol=5e-6,rtol=1e-5)
                close(coarse,reference,atol=5e-6,rtol=1e-5)
                checks.append((member,f'body-{body}','separate_RK4_and_refinement'))
        if case=='E1':
            with np.load(location/'native/trajectories.npz',allow_pickle=False) as a:
                t=a['p0_time_s'];p=a['p0_position_m']
                close(p[:,2],0.1*t+.075*t*t,atol=1e-10,rtol=1e-9)
                checks.append((member,'z','analytic_axial_invariance'))
        if case=='G1':
            with np.load(location/'native/trajectories.npz',allow_pickle=False) as a:
                if member==0:baseline_body_2=a['p1_position_m'].copy()
                else:
                    close(a['p1_position_m'],baseline_body_2,atol=0,rtol=0)
                    checks.append((member,'body-2','unaffected_independent_particle'))
    assert len(checks)>10
    return {'case':case,'status':'passed','checks':len(checks),
            'meaning':'same-author separate formulas and RK4; no rigorous error bound or independent review'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sweep_dir',type=Path)
    p.add_argument('--case',required=True,choices=('E1','G1','T1'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=verify(a.sweep_dir,a.case)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():raise FileExistsError('refuse overwrite of existing reference evidence')
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
