"""Independent-expression/RK4 checks; never imports the emfeeld runtime.

Same author and shared physical constants, not independent review or rigorous
error bounds. Inputs are captured authored facts, never fitted to solver output.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.constants import epsilon_0, G


def field_potential(scene, point):
    x = np.asarray(point, dtype=float); f = np.zeros(3); v = 0.
    for source in scene['sources']:
        typ = source['type']; electric = scene['kind']=='electric'
        if typ == 'uniform':
            a = np.asarray(source['field_N_C' if electric else 'field_m_s2'])
            f += a; v -= float(a @ (x-source.get('origin_m',[0,0,0]))); continue
        strength = ('charge_C' if electric else 'mass_kg')
        if typ == 'line': strength = 'charge_per_m_C_m' if electric else 'mass_per_m_kg_m'
        if typ == 'plane': strength = 'charge_per_m2_C_m2' if electric else 'mass_per_m2_kg_m2'
        c = (1/(4*np.pi*epsilon_0) if electric else -G)*source[strength]
        d = x-source.get('center_m',[0,0,0])
        if typ == 'line':
            axis=np.asarray(source.get('direction',[0,0,1]),dtype=float);axis/=np.linalg.norm(axis)
            d=d-(d@axis)*axis; r=np.linalg.norm(d)
            if r==0: raise ValueError('singular reference line evaluation')
            f+=2*c*d/r**2;v-=2*c*np.log(r/source['reference_radius_m'])
        elif typ == 'plane':
            n=np.asarray(source.get('normal',[0,0,1]),dtype=float);n/=np.linalg.norm(n); s=d@n
            if s==0: raise ValueError('unqualified reference sheet location')
            f+=2*np.pi*c*np.sign(s)*n;v-=2*np.pi*c*abs(s)
        else:
            r=np.linalg.norm(d);radius=source.get('radius_m',0)
            if typ=='solid_sphere' and r<radius:
                f+=c*d/radius**3;v+=c*(3-r*r/radius**2)/(2*radius)
            elif typ=='shell' and r<radius:v+=c/radius
            else:
                if r==0 or (typ=='shell' and r==radius):raise ValueError('singular reference surface/point')
                f+=c*d/r**3;v+=c/r
    return f,v


def rk4(scene, particle, times, substeps):
    y=np.array(particle['position_m']+particle['velocity_m_s'],dtype=float)
    ratio=particle['charge_C']/particle['mass_kg'] if scene['kind']=='electric' else 1.
    result=[y.copy()]
    def rhs(state):return np.concatenate((state[3:],ratio*field_potential(scene,state[:3])[0]))
    for left,right in zip(times[:-1],times[1:]):
        h=(right-left)/substeps
        for _ in range(substeps):
            a=rhs(y);b=rhs(y+h*a/2);c=rhs(y+h*b/2);d=rhs(y+h*c)
            y=y+h*(a+2*b+2*c+d)/6
        result.append(y.copy())
    return np.asarray(result)


def check(output):
    output=Path(output); summary=json.loads((output/'qualification.json').read_text())
    report={'reference':'separate ideal-source formulas and fixed-step RK4; same author', 'runs':[], 'passed':True}
    for case,record in summary['cases'].items():
        for run in record['runs']:
            path=output/run['path'];packet=json.loads((path/'native/packet.json').read_text())
            native=json.loads((path/'native/result.json').read_text());scene=packet['scene']
            measured={r['id']:r for r in native['results']}
            nstatic=0
            for request in packet['observations']:
                if request['type'] not in ('field','potential'):continue
                f,v=field_potential(scene,request['position_m'])
                result=measured[request['id']];assert result['status']=='ok'
                expected=f if request['type']=='field' else v
                np.testing.assert_allclose(result['value'],expected,atol=1e-10,rtol=1e-10)
                nstatic+=1
            row={'path':run['path'],'static_checks':nstatic,'particles':[]}
            if scene.get('particles'):
                with np.load(path/'native/trajectories.npz',allow_pickle=False) as data:
                    for i,particle in enumerate(scene['particles']):
                        t=data[f'p{i}_time_s'];r=data[f'p{i}_position_m'];v=data[f'p{i}_velocity_m_s']
                        coarse=rk4(scene,particle,t,20);fine=rk4(scene,particle,t,40)
                        state=np.column_stack((r,v))
                        np.testing.assert_allclose(coarse,fine,atol=1e-7,rtol=1e-7)
                        np.testing.assert_allclose(state,fine,atol=1e-7,rtol=1e-7)
                        kinetic=.5*particle['mass_kg']*np.sum(v*v,axis=1)
                        potential=np.array([field_potential(scene,x)[1] for x in r])
                        potential*=particle['charge_C'] if scene['kind']=='electric' else particle['mass_kg']
                        np.testing.assert_allclose(data[f'p{i}_kinetic_J'],kinetic,atol=1e-10,rtol=1e-10)
                        np.testing.assert_allclose(data[f'p{i}_potential_J'],potential,atol=1e-10,rtol=1e-10)
                        if case=='E1':
                            np.testing.assert_allclose(r[:,2],.1*t+.075*t*t,atol=1e-7,rtol=1e-7)
                        if case=='G1' and len(scene['sources'])==1:
                            h=np.cross(r-np.asarray(scene['sources'][0]['center_m']),v)
                            np.testing.assert_allclose(h,np.tile(h[0],(len(h),1)),atol=1e-7,rtol=1e-7)
                        row['particles'].append({'id':i,'saved_samples':len(t),
                            'max_state_difference_from_RK4':float(np.max(abs(state-fine))),
                            'max_RK4_refinement_difference':float(np.max(abs(coarse-fine))),
                            'energy_components_checked':True})
            report['runs'].append(row)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runs',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=check(a.runs)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
