"""Prepare two illustrative source-composition examples and separate references.

No emfeeld imports. Both spheres contain the entire stated harmonic trajectory.
This is same-author analytic checking, not an independent authorability benchmark.
"""
import hashlib
import json
import math
from pathlib import Path
from scipy.constants import G, epsilon_0

ROOT = Path(__file__).resolve().parents[1]
K = 1/(4*math.pi*epsilon_0)
CENTRES = [(-.4,.2,0), (.3,-.1,.1)]
RADII, WEIGHTS, F = (2.,3.), (.4,.6), (.1,-.05,.025)
EQ = [sum(w*c[j] for w,c in zip(WEIGHTS,CENTRES))+F[j] for j in range(3)]
A, B = (.7,.2,-.1), (-.1,.2,.15)


def state(t):
    return ([EQ[j]+A[j]*math.cos(t)+B[j]*math.sin(t) for j in range(3)],
            [-A[j]*math.sin(t)+B[j]*math.cos(t) for j in range(3)])


def potential(r):
    return sum(-w*(3*radius**2-sum((x-c)**2 for x,c in zip(r,centre)))/2
               for w,radius,centre in zip(WEIGHTS,RADII,CENTRES))-sum(f*x for f,x in zip(F,r))


def build():
    cases=[]
    for kind in ('electric','gravity'):
        sources=[]
        for w,r,c in zip(WEIGHTS,RADII,CENTRES):
            sources.append({'type':'solid_sphere', 'radius_m':r, 'center_m':list(c),
                            'charge_C' if kind=='electric' else 'mass_kg': -w*r**3/K if kind=='electric' else w*r**3/G})
        sources.append({'type':'uniform','field_N_C' if kind=='electric' else 'field_m_s2':list(F)})
        mass=1e-6 if kind=='electric' else 2.
        r0,v0=state(0)
        particle={'mass_kg':mass,'position_m':r0,'velocity_m_s':v0}
        if kind=='electric': particle['charge_C']=mass  # q/m = 1 C/kg, explicit example choice
        scene={'schema_version':1,'title':f'Discovery example: two spheres plus uniform {kind} field',
               'kind':kind,'sources':sources,'particles':[particle],'duration_s':3,'samples':61,
               'bounds_m':[-4,4,-4,4,-4,4]}
        obs=[{'id':'field_initial','type':'field','position_m':r0},
             {'id':'potential_initial','type':'potential','position_m':r0},
             {'id':'position_t1','type':'trajectory_sample','particle_index':0,'quantity':'position','sample_index':20},
             {'id':'velocity_t1_5','type':'trajectory_sample','particle_index':0,'quantity':'velocity','sample_index':30},
             {'id':'cross_equilibrium_plane','type':'trajectory_event','particle_index':0,
              'condition':{'type':'plane','point_m':EQ,'normal':[1,0,0],'direction':'negative'},
              'occurrence':'first','max_step_s':.02,'min_normal_speed_m_s':1e-6,
              'accuracy':{'time_atol_s':1e-7,'position_atol_m':1e-7,'velocity_atol_m_s':1e-7,'rtol':1e-8}}]
        data={'observation_schema_version':1,'scene':scene,'observations':obs,
              'notes':'Illustrative catalogue-guided authoring, not a textbook or blind benchmark. '
                      'Prescribed penetrable uniform spheres and independent nonrelativistic test body. '
                      'The entire trajectory remains inside both spheres; a = -(position-equilibrium) in SI. '
                      'No conductor response, collisions or cross-domain coupling. Plane is an observation, not a material boundary.'}
        rel=f'examples/authoring/discovery_{kind}.json'; path=ROOT/rel; path.parent.mkdir(parents=True,exist_ok=True)
        raw=(json.dumps(data,indent=2,allow_nan=False)+'\n').encode(); path.write_bytes(raw)
        checks=[]
        def ck(ident,key,value,atol=1e-8):
            check={'id':ident,'path':key if isinstance(key,list) else [key],'value':value}
            if not isinstance(value,str): check.update(atol=atol,rtol=1e-8)
            checks.append(check)
        ck('field_initial','value',[-x for x in A]); ck('field_initial','unit','N/C' if kind=='electric' else 'm/s^2')
        ck('potential_initial','value',potential(r0)); ck('potential_initial','unit','V' if kind=='electric' else 'J/kg')
        ck('position_t1','value',state(1)[0]); ck('position_t1','unit','m')
        ck('velocity_t1_5','value',state(1.5)[1]); ck('velocity_t1_5','unit','m/s')
        t=math.atan2(A[0],-B[0]); r,v=state(t); speed=math.sqrt(sum(x*x for x in v))
        for key,value in {'time_s':t,'position_m':r,'velocity_m_s':v,'speed_m_s':speed,
                          'kinetic_J':mass*speed**2/2,'potential_J':mass*potential(r),
                          'total_energy_J':mass*(speed**2/2+potential(r))}.items():
            ck('cross_equilibrium_plane',['state',key],value,1e-10 if key.endswith('_J') else 1e-7)
        ck('cross_equilibrium_plane',['units','time_s'],'s'); ck('cross_equilibrium_plane',['units','total_energy_J'],'J')
        checks.append({'id':'cross_equilibrium_plane','path':['diagnostics','refinement','passed'],'value':True})
        cases.append({'id':f'discovery_{kind}','packet':rel,'sha256':hashlib.sha256(raw).hexdigest(),
                      'statuses':{o['id']:'ok' for o in obs},'checks':checks})
    manifest={'version':1,'description':'Two catalogue-guided compositions checked with same-author harmonic expressions; no engine-derived references.', 'cases':cases}
    path=ROOT/'verification/discovery_examples.json'; path.write_bytes((json.dumps(manifest,indent=2)+'\n').encode())


if __name__=='__main__': build()
