"""Source-aware authorability experiment against an immutable emfeeld engine.

Only scene JSON and observation/reference code are authored. Case dispatch below
belongs to this evaluation, not the production engine. A completed experiment may
have PARTIAL cases; use --strict to return nonzero unless every request passes.
"""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import platform
import traceback
import numpy as np
import scipy
from scipy.constants import epsilon_0
from scipy.interpolate import CubicHermiteSpline
from scipy.optimize import brentq
from emfeeld import load_scene, scene_from_dict, integrate, sphere_flux
from emfeeld.cli import main as cli_main

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
K = 1 / (4 * np.pi * epsilon_0)
CRITERIA = json.loads((HERE / 'criteria.json').read_text())


def plain(value):
    if isinstance(value, np.ndarray):
        if value.size <= 18:
            return value.tolist()
        return {'shape': list(value.shape), 'min': float(np.min(value)), 'max': float(np.max(value))}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def check(result, name, actual, expected, *, rtol=None, atol=None, required=True):
    rtol = CRITERIA['static_rtol'] if rtol is None else rtol
    atol = CRITERIA['static_atol'] if atol is None else atol
    a, b = np.broadcast_arrays(np.asarray(actual, dtype=float), np.asarray(expected, dtype=float))
    error = np.abs(a - b)
    ok = bool(np.isfinite(a).all() and np.isfinite(b).all() and np.all(error <= atol + rtol * np.abs(b)))
    result['checks'].append(dict(name=name, passed=ok, required=required, actual=plain(a), expected=plain(b),
                                 max_absolute_error=float(np.max(error)), rtol=rtol, atol=atol))
    return ok


def flag(result, name, ok, *, required=True, detail=''):
    result['checks'].append(dict(name=name, passed=bool(ok), required=required, detail=detail))


def frozen():
    expected = json.loads((HERE / 'frozen_files.json').read_text())
    found = {}
    for name, sha in expected['verified_files'].items():
        data = (ROOT / name).read_bytes()
        h = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if h != sha:
            raise RuntimeError(f'Frozen file changed: {name}')
        found[name] = h
    return found


def sc55(s, p, t, r):
    d = np.array([6., -8., 0.])
    force = s.model.field(p['probe_m']) * p['test_charge_C']
    check(r, 'force_vector_N', force, K * 50e-6 * 2e-6 * d / 1000)
    check(r, 'force_magnitude_N', np.linalg.norm(force), K * 50e-6 * 2e-6 / 100)
    check(r, 'potential_at_probe_V', s.model.potential(p['probe_m']), K * 50e-6 / 10)
    r['answer'] = dict(force_N=force, magnitude_N=np.linalg.norm(force), printed_choice='B: approximately 9 mN')


def sc35(s, p, t, r):
    field = s.model.field(p['probe_m'])
    check(r, 'field_at_P_N_C', field, [0, 0, -2*p['sigma_C_m2']/epsilon_0])
    r['answer'] = dict(field_N_C=field, symbolic='-2 sigma/epsilon_0 in +z component', printed_choice='B')


def sc96(s, p, t, r):
    q, a = p['charge_magnitude_C'], p['side_m']
    check(r, 'centre_potential_V', s.model.potential([0,0,0]), 0)
    check(r, 'centre_field_N_C', s.model.field([0,0,0]), [0,-4*np.sqrt(2)*K*q/a**2,0])
    r['answer'] = dict(potential_V=float(s.model.potential([0,0,0])), field_N_C=s.model.field([0,0,0]), printed_choice='B')


def sc122(s, p, t, r):
    q, a, b = p['total_charge_C'], p['inner_radius_m'], p['outer_radius_m']
    sources = s.model.sources
    check(r, 'total_charge_C', sum(x.strength for x in sources), q, atol=1e-20)
    check(r, 'equal_surface_densities_C_m2', sources[0].strength/(4*np.pi*a*a), sources[1].strength/(4*np.pi*b*b), atol=1e-20)
    v = s.model.potential([0,0,0])
    check(r, 'centre_potential_V', v, K*q*(a+b)/(a*a+b*b))
    check(r, 'interior_field_N_C', s.model.field([[0,0,0],[a/3,0,0]]), 0)
    r['answer'] = dict(potential_V=float(v), printed_choice='A')


def mc33(s, p, t, r):
    z = np.array(p['z_samples_m']); points=np.column_stack([z*0,z*0,z])
    a, q = p['a_m'], p['q_C']
    check(r, 'axial_potential_V', s.model.potential(points), 4*K*q/np.sqrt(a*a+z*z))
    field=np.column_stack([z*0,z*0,4*K*q*z/(a*a+z*z)**1.5])
    check(r, 'axial_field_N_C', s.model.field(points), field)
    r['answer'] = dict(positive_z_choices=['A','B','C','D'], z_m=z, potential_V=s.model.potential(points), field_N_C=field)


def sc158(s, p, t, r):
    d,R,lam=p['offset_m'],p['gaussian_radius_m'],p['lambda_C_m']
    check(r, 'pointwise_field_at_gaussian_centre_N_C', s.model.field([0,0,0]), [-2*K*lam/d,0,0])
    expected = 2*lam*np.sqrt(R*R-d*d)/epsilon_0
    rows=[]
    # The second azimuth probes grid alignment of the same physical geometry.
    for azimuth in (0., float(np.pi/7)):
        raw=json.loads((HERE/'scenes/sc-158.json').read_text())
        raw['sources'][0]['center_m']=[d*np.cos(azimuth),d*np.sin(azimuth),0]
        model=scene_from_dict(raw).model
        for n in CRITERIA['flux_refinement_orders']:
            try:
                value=sphere_flux(model, p['gaussian_center_m'], R, n_polar=n, n_azimuth=2*n).total
                rows.append(dict(azimuth_rad=azimuth,n_polar=n,n_azimuth=2*n,flux=value,
                                 relative_error=abs(value-expected)/abs(expected),status='returned_finite' if np.isfinite(value) else 'nonfinite'))
            except ValueError as exc:
                rows.append(dict(azimuth_rad=azimuth,n_polar=n,status='domain_rejection',error=str(exc)))
    r['flux_refinement']=rows
    first=rows[0]
    flag(r, 'native_flux_default_meets_1e-5', first.get('relative_error',float('inf'))<=CRITERIA['flux_relative_tolerance'],required=False,
         detail='Diagnostic: a finite quadrature sum is not a certified answer for an intersecting singular source.')
    flag(r, 'requested_flux_is_in_qualified_domain', False,
         detail='The line intersects this Gaussian sphere. PHYSICS.md explicitly excludes such quadrature certification; no engine correction or special quadrature was introduced.')
    r['answer'] = dict(reference_only_flux_N_m2_C=expected,reference_formula='2 lambda sqrt(R^2-y^2)/epsilon_0',
                       native_default_flux=first.get('flux'),printed_choice='C (analytic Gauss-law reference, NOT accepted native flux)')
    r['limitation'] = 'PARTIAL: authored line field works; requested spherical flux is outside qualified numerical domain. The original shortlist overstated readiness of this observable.'


def sc99(s, p, t, r):
    tr=t[0]; times=tr.time_s; a=p['q_magnitude_C']*p['E_magnitude_N_C']/p['mass_kg']; v=p['initial_speed_m_s']
    expected=np.column_stack([v*times,a*times**2/2,times*0])
    check(r,'parabolic_position_m',tr.position_m,expected,rtol=0,atol=CRITERIA['trajectory_position_atol_m'])
    check(r,'parabolic_velocity_m_s',tr.velocity_m_s,np.column_stack([times*0+v,a*times,times*0]),rtol=0,atol=CRITERIA['trajectory_velocity_atol_m_s'])
    expected_k=.5*p['mass_kg']*v*v+p['q_magnitude_C']*p['E_magnitude_N_C']*expected[:,1]
    check(r,'total_kinetic_energy_J',tr.kinetic_J,expected_k,atol=1e-13)
    r['answer'] = dict(incorrect_choice='A',explanation='q E y is the kinetic-energy GAIN, not total energy when initial speed v is nonzero.',final_position_m=tr.position_m[-1])


def crossing(tr, axis, target):
    """Estimated crossing from saved states; not a native event or new trajectory."""
    v=tr.position_m[:,axis]-target
    candidates=np.flatnonzero((v[:-1]*v[1:]<=0)&(v[:-1]!=v[1:]))
    if len(candidates)==0:raise ValueError('Requested crossing not bracketed by saved states')
    j=int(candidates[0]); times=tr.time_s[j:j+2]
    interp=CubicHermiteSpline(times,tr.position_m[j:j+2],tr.velocity_m_s[j:j+2])
    time=brentq(lambda z:float(interp(z)[axis]-target),float(times[0]),float(times[1]),xtol=1e-12)
    velocity=interp.derivative()(time)
    return dict(time_s=time,speed_m_s=float(np.linalg.norm(velocity)),position_m=interp(time),
                saved_bracket_s=times,method='postprocessed cubic Hermite position from stored r,v; bracketed root')


def check_crossing(s,tr,axis,target,expected,r):
    coarse=crossing(tr,axis,target)
    refined=integrate(s.model,s.particles[0],np.linspace(0,s.duration_s,2*s.samples-1),rtol=1e-11,
                      position_atol_m=1e-10,velocity_atol_m_s=1e-10,max_step_s=s.duration_s/400)
    fine=crossing(refined,axis,target)
    check(r,'crossing_speed_m_s',coarse['speed_m_s'],expected,rtol=CRITERIA['crossing_speed_rtol'],atol=1e-10)
    check(r,'refined_crossing_speed_m_s',fine['speed_m_s'],expected,rtol=CRITERIA['crossing_speed_rtol'],atol=1e-10)
    check(r,'crossing_time_refinement_s',coarse['time_s'],fine['time_s'],rtol=0,atol=CRITERIA['crossing_time_refinement_atol_s'])
    r['crossing']=dict(primary=coarse,refined=fine,reference_speed_m_s=expected)


def sc28(s,p,t,r):
    speed=np.sqrt(2*K*p['source_charge_C']*p['test_charge_magnitude_C']/(p['mass_kg']*p['a_m']))
    check_crossing(s,t[0],1,0.,speed,r)
    check(r,'bisector_invariance_m',t[0].position_m[:,[0,2]],0.,rtol=0,atol=1e-10)
    r['answer']=dict(crossing_speed_m_s=r['crossing']['primary']['speed_m_s'],printed_choice='B')


def sol26(s,p,t,r):
    a,Q,q,m=p['a_m'],p['Q_C'],p['q_C'],p['mass_kg']
    theta=np.linspace(0,2*np.pi,257);points=np.column_stack([5*a+4*a*np.cos(theta),4*a*np.sin(theta),theta*0])
    check(r,'zero_potential_on_xy_circle_V',s.model.potential(points),0.,rtol=0,atol=1e-10)
    x=np.array([-7.,-4.,-2.,0.,1.,2.,4.,5.,9.,12.])*a
    expected=K*Q*(1/np.abs(x-3*a)-2/np.abs(x+3*a))
    check(r,'axis_potential_V',s.model.potential(np.column_stack([x,x*0,x*0])),expected)
    check_crossing(s,t[0],0,9*a,np.sqrt(K*Q*q/(2*m*a)),r)
    r['answer']=dict(circle_center_m=[5*a,0,0],circle_radius_m=4*a,crossing_speed_m_s=r['crossing']['primary']['speed_m_s'])
    r['visual_limitation']='Native viewer does not draw the analytic zero-potential locus or label its crossing; scalar observations are in this report.'


def num31(s,p,t,r):
    rho,R,c,rc=p['density_C_m3'],p['outer_radius_m'],np.array(p['cavity_center_m']),p['cavity_radius_m']
    point=np.array(p['probe_m'])
    expected=rho*(3*R*R-np.dot(point,point))/(6*epsilon_0)-rho*rc**3/(3*epsilon_0*np.linalg.norm(point-c))
    actual=float(s.model.potential(point)); check(r,'potential_at_P_V',actual,expected)
    check(r,'nearest_integer_V',round(actual),35,rtol=0,atol=0)
    samples=c+np.array([[0,0,0],[.002,-.001,.001],[-.002,.001,-.001]])
    check(r,'uniform_cavity_field_N_C',s.model.field(samples),np.broadcast_to(rho*c/(3*epsilon_0),samples.shape))
    check(r,'removed_charge_ratio',s.model.sources[1].strength/s.model.sources[0].strength,-(rc/R)**3,atol=1e-15)
    r['answer']=dict(potential_at_P_V=actual,nearest_integer_V=round(actual))
    r['visual_limitation']='Field/potential subtraction is correct. Two transparent primitive spheres are rendered; no boolean-cut void geometry is claimed.'


def overlap(s,p,t,r):
    c1,c2=np.array(p['center1_m']),np.array(p['center2_m']);rho=p['density_magnitude_C_m3']
    rng=np.random.default_rng(241);points=rng.uniform(-.7,.7,(2000,3))
    valid=(np.linalg.norm(points-c1,axis=1)<p['radius1_m'])&(np.linalg.norm(points-c2,axis=1)<p['radius2_m'])
    points=points[valid][:100]
    if len(points)<50:raise ValueError('Insufficient sampled points in both spheres')
    field=rho*(c2-c1)/(3*epsilon_0)
    check(r,'constant_overlap_field_N_C',s.model.field(points),np.broadcast_to(field,points.shape))
    potentials=s.model.potential(points)
    check(r,'linear_overlap_potential_differences_V',potentials-potentials[0],-(points-points[0])@field)
    flag(r,'overlap_field_nonzero',np.linalg.norm(field)>0)
    flag(r,'overlap_potential_not_constant',np.ptp(potentials)>1e-6)
    r['answer']=dict(correct_choices=['C','D'],field_N_C=field,overlap_samples=len(points),potential_range_V=[float(potentials.min()),float(potentials.max())])


def mc36(s,p,t,r):
    tr=t[0];a,e,i,mu=p['semimajor_axis_m'],p['eccentricity'],p['inclination_rad'],p['mu_m3_s2']
    n=np.sqrt(mu/a**3);M=n*tr.time_s;E=M.copy()
    for _ in range(20):E-=(E-e*np.sin(E)-M)/(1-e*np.cos(E))
    denom=1-e*np.cos(E); ey=np.sqrt(1-e*e)
    ref=np.column_stack([a*(np.cos(E)-e),a*ey*np.sin(E)*np.cos(i),a*ey*np.sin(E)*np.sin(i)])
    vel=np.column_stack([-a*n*np.sin(E)/denom,a*n*ey*np.cos(E)*np.cos(i)/denom,a*n*ey*np.cos(E)*np.sin(i)/denom])
    check(r,'kepler_ellipse_position_m',tr.position_m,ref,rtol=0,atol=CRITERIA['trajectory_position_atol_m'])
    check(r,'kepler_ellipse_velocity_m_s',tr.velocity_m_s,vel,rtol=0,atol=CRITERIA['trajectory_velocity_atol_m_s'])
    angular=np.cross(tr.position_m,tr.velocity_m_s)*p['mass_kg']
    expect_h=p['mass_kg']*np.sqrt(mu*a*(1-e*e))*np.array([0,-np.sin(i),np.cos(i)])
    check(r,'angular_momentum_kg_m2_s',angular,np.broadcast_to(expect_h,angular.shape),rtol=1e-8,atol=1e-12)
    speed=np.linalg.norm(tr.velocity_m_s,axis=1);omega=np.linalg.norm(np.cross(tr.position_m,tr.velocity_m_s),axis=1)/np.sum(tr.position_m**2,axis=1)
    check(r,'speed_ratio',speed.max()/speed.min(),(1+e)/(1-e),rtol=1e-7,atol=1e-9)
    check(r,'angular_speed_ratio',omega.max()/omega.min(),((1+e)/(1-e))**2,rtol=1e-7,atol=1e-9)
    r['answer']=dict(correct_choices=['A'],speed_min_max_m_s=[float(speed.min()),float(speed.max())],period_s=s.duration_s)


CHECKS={'SC-55':sc55,'SC-35':sc35,'SC-96':sc96,'SC-122':sc122,'MC-33':mc33,'SC-158':sc158,'SC-99':sc99,'SC-28':sc28,'SOL-26':sol26,'NUM-31':num31,'ARCH-ADV-MC-05':overlap,'MC-36':mc36}


def generic_checks(scene,case,result):
    # Authored observations; no automatic guess of a requested point in production.
    p=case['parameters']; probe=np.array(p.get('probe_m',[.23,.17,.31]),dtype=float)
    if case['id']=='NUM-31':probe=np.array([.04,0,0])
    h=1e-5*max(min(np.ptp(np.array(scene.bounds_m).reshape(3,2),axis=1)),1e-3)
    gradient=np.array([(scene.model.potential(probe+h*a)-scene.model.potential(probe-h*a))/(2*h) for a in np.eye(3)])
    field=scene.model.field(probe)
    error=float(np.linalg.norm(gradient+field)/max(1.,np.linalg.norm(field)))
    flag(result,'field_minus_potential_gradient',error<=CRITERIA['gradient_scaled_tolerance'],detail=f'scaled residual {error:.6g}, h={h:.6g} m')
    raw=json.loads((HERE/case['scene']).read_text())
    axis=np.array([1.,2.,3.]);axis/=np.linalg.norm(axis);x,y,z=axis
    cross=np.array([[0,-z,y],[z,0,-x],[-y,x,0]]);angle=.37
    R=np.cos(angle)*np.eye(3)+(1-np.cos(angle))*np.outer(axis,axis)+np.sin(angle)*cross
    shift=np.array([.13,-.17,.29])
    for src in raw['sources']:
        key='origin_m' if src['type']=='uniform' else 'center_m'
        src[key]=(R@np.array(src.get(key,[0,0,0]))+shift).tolist()
        for key in ('normal','direction','field_N_C'):
            if key in src:src[key]=(R@np.array(src[key])).tolist()
    raw['particles']=[]
    transformed=scene_from_dict(raw).model; transformed_p=R@probe+shift
    check(result,'translated_rotated_field_covariance',transformed.field(transformed_p),R@field,rtol=1e-10,atol=1e-9)
    check(result,'translated_rotated_potential_invariance',transformed.potential(transformed_p),scene.model.potential(probe),rtol=1e-10,atol=1e-9)


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    before=frozen(); packet=json.loads((HERE/'cases.json').read_text())
    report={'frozen_commit':packet['frozen_commit'],'assessment_kind':packet['assessment_kind'],
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform()},
            'epsilon_0_SI':epsilon_0,'criteria':CRITERIA,'cases':[],'completed':False}
    target=output/'results.json'
    for case in packet['cases']:
        cid=case['id']; d=output/cid;d.mkdir(exist_ok=True)
        result={'id':cid,'source':{'section':case['section'],'pdf_pages':[case['pdf_page_start'],case['pdf_page_end']],'printed_page':case['printed_page']},
                'checks':[],'status':'RUNNING','source_interpretation':case['interpretation_notes']}
        try:
            path=HERE/case['scene']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=case['scene_sha256']:raise RuntimeError('Scene changed after authoring freeze')
            log=io.StringIO()
            with redirect_stdout(log),redirect_stderr(log):
                validate_code=cli_main(['validate',str(path)])
                run_code=cli_main(['run',str(path),'--output',str(d/'native.npz')])
            (d/'cli.log').write_text(log.getvalue())
            result['cli_validate_exit']=validate_code;result['cli_run_exit']=run_code
            flag(result,'strict_JSON_validate_and_native_run',validate_code==run_code==0)
            if validate_code or run_code:raise RuntimeError('Native CLI failed; see cli.log')
            scene=load_scene(path);trajectories=scene.trajectories()
            CHECKS[cid](scene,case['parameters'],trajectories,result)
            generic_checks(scene,case,result)
            for j,tr in enumerate(trajectories):
                flag(result,f'particle_{j}_energy_conservation',tr.normalized_energy_drift<=CRITERIA['energy_normalized_tolerance'],detail=f'max normalized drift={tr.normalized_energy_drift:.8g}')
                flag(result,f'particle_{j}_finite_states',np.isfinite(tr.position_m).all() and np.isfinite(tr.velocity_m_s).all())
            failures=[x['name'] for x in result['checks'] if x['required'] and not x['passed']]
            if cid=='SC-158' and failures==['requested_flux_is_in_qualified_domain']:
                result['status']='PARTIAL'
            else:result['status']='PASS' if not failures else 'FAIL'
            result['required_failures']=failures
        except Exception:
            result['status']='ERROR';result['traceback']=traceback.format_exc()
        report['cases'].append(plain(result));target.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(cid,result['status'],flush=True)
    after=frozen()
    report['freeze_unchanged']=before==after
    report['counts']={s:sum(x['status']==s for x in report['cases']) for s in ('PASS','PARTIAL','FAIL','ERROR')}
    report['completed']=True;report['all_requested_observables_pass']=report['counts']['PASS']==len(packet['cases'])
    report['core_files_edited']=0;report['frozen_files_verified']=len(after)
    report['limitations']='Source-aware author verification; solutions were visible. Not independent/blind or a statistically estimated LLM success rate. Numerical choices are labelled in cases.json.'
    target.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['counts']),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/authorability_v1')
    parser.add_argument('--strict',action='store_true',help='Nonzero if any requested observation is not fully supported')
    args=parser.parse_args();r=run(args.output)
    return int(bool(r['counts']['ERROR'] or r['counts']['FAIL'] or (args.strict and not r['all_requested_observables_pass'])))

if __name__=='__main__':raise SystemExit(main())
