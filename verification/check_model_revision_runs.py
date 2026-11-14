"""Separate analytic fixture checks of saved revision runs; no emfeeld imports.

Harmonic interior-sphere motion and elliptic Kepler expressions apply only to
these explicitly illustrative fixtures. Same-author checks, not independent review.
"""
from pathlib import Path
import argparse
import json
import math
import numpy as np
from scipy.constants import G, epsilon_0
from scipy.optimize import brentq


def check(directory):
    directory=Path(directory);checks=[]
    def close(label, actual, expected, atol=1e-8, rtol=1e-8):
        a,b=np.asarray(actual),np.asarray(expected)
        passed=a.shape==b.shape and bool(np.isfinite(a).all()) and bool(np.all(np.abs(a-b)<=atol+rtol*np.abs(b)))
        checks.append({'check':label,'passed':passed,'max_absolute_difference':float(np.max(np.abs(a-b))) if a.shape==b.shape else None,
                       'atol':atol,'rtol':rtol})
    k=1/(4*math.pi*epsilon_0)
    for kind in ('electric','gravity'):
        for revision in ('root','source-hypothesis','launch-hypothesis'):
            base=directory/kind/(revision+'-motion')/'native'
            scene=json.loads((base/'packet.json').read_text())['scene']
            native=json.loads((base/'result.json').read_text())
            out={r['id']:r for r in native['results']}
            probe=scene['particles'][0]['position_m'];probe=np.array(probe)
            if kind=='electric':
                spheres=[s for s in scene['sources'] if s['type']=='solid_sphere']
                uniform=sum((np.array(s['field_N_C']) for s in scene['sources'] if s['type']=='uniform'),np.zeros(3))
                w=np.array([-k*s['charge_C']/s['radius_m']**3 for s in spheres])
                centres=np.array([s['center_m'] for s in spheres])
                equilibrium=((w[:,None]*centres).sum(axis=0)+uniform)/w.sum()
                omega=math.sqrt(w.sum())
                field=-(w[:,None]*(probe-centres)).sum(axis=0)+uniform
                potential=sum(k*s['charge_C']*(3-np.dot(probe-np.array(s['center_m']),probe-np.array(s['center_m']))/s['radius_m']**2)/(2*s['radius_m']) for s in spheres)-np.dot(uniform,probe)
            else:
                mu=G*scene['sources'][0]['mass_kg']
                radius=np.linalg.norm(probe)
                field=-mu*probe/radius**3;potential=-mu/radius
            close(f'{kind}/{revision}/field',out['field_probe']['value'],field,atol=1e-12,rtol=2e-12)
            close(f'{kind}/{revision}/potential',out['potential_probe']['value'],potential,atol=1e-9,rtol=2e-12)
            static=json.loads((directory/kind/(revision+'-static')/'native/result.json').read_text())
            close(f'{kind}/{revision}/static-field',static['results'][0]['value'],field,atol=1e-12,rtol=2e-12)
            close(f'{kind}/{revision}/static-potential',static['results'][1]['value'],potential,atol=1e-9,rtol=2e-12)
            with np.load(base/'trajectories.npz',allow_pickle=False) as data:
                for index,particle in enumerate(scene['particles']):
                    prefix=f'{kind}/{revision}/particle-{index}'
                    t=data[f'p{index}_time_s'];r0=np.array(particle['position_m']);v0=np.array(particle['velocity_m_s'])
                    if kind=='electric':
                        assert particle['charge_C']/particle['mass_kg']==1
                        # Conservative whole-time bound establishes this analytic regime,
                        # not just an interior check at the discrete output samples.
                        amplitude=np.linalg.norm(r0-equilibrium)+np.linalg.norm(v0)/omega
                        assert all(np.linalg.norm(equilibrium-np.array(s['center_m']))+amplitude<s['radius_m'] for s in spheres)
                        tt=t[:,None]
                        r=equilibrium+(r0-equilibrium)*np.cos(omega*tt)+v0/omega*np.sin(omega*tt)
                        v=-(r0-equilibrium)*omega*np.sin(omega*tt)+v0*np.cos(omega*tt)
                        kin=.5*particle['mass_kg']*np.sum(v*v,axis=1)
                        phi=sum(k*s['charge_C']*(3-np.sum((r-np.array(s['center_m']))**2,axis=1)/s['radius_m']**2)/(2*s['radius_m']) for s in spheres)-r@uniform
                        close(prefix+'/position',data[f'p{index}_position_m'],r)
                        close(prefix+'/velocity',data[f'p{index}_velocity_m_s'],v)
                        close(prefix+'/kinetic',data[f'p{index}_kinetic_J'],kin,atol=1e-13)
                        close(prefix+'/potential-energy',data[f'p{index}_potential_J'],particle['charge_C']*phi,atol=1e-13)
                    else:
                        radius=np.linalg.norm(r0);speed=np.linalg.norm(v0)
                        assert abs(np.dot(r0,v0))<1e-8
                        eccentricity=max(0.,1-speed**2*radius/mu)
                        assert eccentricity<1
                        a=radius/(1+eccentricity);n=math.sqrt(mu/a**3)
                        peri=-r0/radius;trans=-v0/speed
                        sample=np.array([0,len(t)//4,len(t)//2,3*len(t)//4,len(t)-1])
                        rr=[];vv=[]
                        for time in t[sample]:
                            mean=math.pi+n*time
                            E=mean if eccentricity<1e-14 else brentq(lambda x:x-eccentricity*math.sin(x)-mean,mean-eccentricity-1e-12,mean+eccentricity+1e-12,xtol=1e-13)
                            rate=n/(1-eccentricity*math.cos(E));q=math.sqrt(1-eccentricity**2)
                            rr.append(a*(math.cos(E)-eccentricity)*peri+a*q*math.sin(E)*trans)
                            vv.append(a*rate*(-math.sin(E)*peri+q*math.cos(E)*trans))
                        close(prefix+'/position',data[f'p{index}_position_m'][sample],rr,atol=2.,rtol=2e-10)
                        close(prefix+'/velocity',data[f'p{index}_velocity_m_s'][sample],vv,atol=2e-5,rtol=2e-10)
                        close(prefix+'/energy',data[f'p{index}_kinetic_J']+data[f'p{index}_potential_J'],np.full(len(t),-particle['mass_kg']*mu/(2*a)),atol=1e-3,rtol=2e-9)
    return {'meaning':'Same-author separate analytic references, not solver-generated answers, blind authorability or teacher acceptance',
            'passed':all(x['passed'] for x in checks),'checks':checks,'count':len(checks)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory');parser.add_argument('--output',required=True)
    a=parser.parse_args();result=check(a.directory)
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'passed':result['passed'],'checks':result['count']}))
    raise SystemExit(0 if result['passed'] else 1)
