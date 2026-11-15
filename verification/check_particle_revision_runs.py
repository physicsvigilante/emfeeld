"""Independent physics/evidence check of structural test-particle revisions.

No emfeeld import or solver code. Reuse previously qualified *separate*
ideal-source expressions and RK4 from check_structural_runs.py. Same-author,
not an independent Chat B review, global-error proof or teacher assessment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from check_structural_runs import field_potential, rk4


def digest(raw):return hashlib.sha256(raw).hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def _inventory(run):
    sealed=read(run/'integrity.json')['files']
    actual={p.relative_to(run).as_posix():digest(p.read_bytes())
            for p in run.rglob('*') if p.is_file() and p!=run/'integrity.json'}
    if sealed!=actual:raise AssertionError(f'run inventory changed: {run}')
    inputs=read(run/'run.json')
    for name,expected in inputs['input_sha256'].items():
        if digest((run/name).read_bytes())!=expected:raise AssertionError('run input changed')
    return inputs


def check_one(folder,case,record):
    run=folder/record['run']
    info=_inventory(run)
    summary=read(run/'summary.json')
    assert info['reference']==record['reference'],(case,record['run'])
    if record['status']=='rejected':
        assert summary['status']=='rejected' and summary['code']=='wrong_role'
        return {'run':record['run'],'status':'rejected','expected_missing_reference':True}
    assert summary['status']=='complete' and summary['execution_complete']
    mapping=read(run/'mapping.json')
    source=read(run/'native/packet.json');report=read(run/'native/result.json')
    assert report['input']==source
    scene=source['scene']
    ids={r['id'] for r in source['observations']}
    assert len(ids)==len(source['observations'])
    observed={r['id']:r for r in report['results']}
    assert ids==set(observed) and len(observed)==len(report['results'])
    for r in observed.values():
        assert r['status']=='ok' and r.get('check',{}).get('passed') is not False
    expected_source={'E1':{'negative_line':0,'axial_field':1},
                     'G1':{'source_A':0,'source_B':1},'T1':{'shell':0,'point':1}}[case]
    assert mapping['sources']==expected_source
    rev=read(run/'revision.json')
    assert rev['particle_order']==list(mapping['particles'])
    assert mapping['particles']=={k:i for i,k in enumerate(rev['particle_order'])}
    for p_id,idx in mapping['particles'].items():
        assert rev['entities'][p_id]['properties']==scene['particles'][idx]
    static_checks=0;energy_checks=0
    for request in source['observations']:
        if request['type'] not in ('field','potential'):continue
        actual=observed[request['id']]
        f,v=field_potential(scene,request['position_m'])
        want=f if request['type']=='field' else v
        np.testing.assert_allclose(actual['value'],want,atol=2e-10,rtol=1e-10)
        static_checks+=1
    trajectory_records=[]
    if scene['particles']:
        # Static T1 intentionally doesn't integrate, even with an authored body.
        if read(run/'analysis.json')['mode']=='trajectory':
            with np.load(run/'native/trajectories.npz',allow_pickle=False) as data:
                for i,particle in enumerate(scene['particles']):
                    t=data[f'p{i}_time_s'];p=data[f'p{i}_position_m'];v=data[f'p{i}_velocity_m_s']
                    actual=np.column_stack((p,v))
                    fine=rk4(scene,particle,t,40)
                    coarse=rk4(scene,particle,t,20)
                    np.testing.assert_allclose(actual,fine,atol=2e-7,rtol=2e-7)
                    np.testing.assert_allclose(coarse,fine,atol=2e-7,rtol=2e-7)
                    kinetic=0.5*particle['mass_kg']*np.sum(v*v,axis=1)
                    coupling=particle['charge_C'] if scene['kind']=='electric' else particle['mass_kg']
                    potential=np.array([field_potential(scene,x)[1] for x in p])*coupling
                    np.testing.assert_allclose(data[f'p{i}_kinetic_J'],kinetic,atol=2e-10,rtol=1e-9)
                    np.testing.assert_allclose(data[f'p{i}_potential_J'],potential,atol=2e-10,rtol=1e-9)
                    energy_checks+=2
                    if case=='E1':
                        z0=particle['position_m'][2];vz=particle['velocity_m_s'][2]
                        q_over_m=particle['charge_C']/particle['mass_kg']
                        az=q_over_m*scene['sources'][1]['field_N_C'][2]
                        np.testing.assert_allclose(p[:,2],z0+vz*t+.5*az*t*t,atol=2e-8,rtol=2e-8)
                        np.testing.assert_allclose(v[:,2],vz+az*t,atol=2e-8,rtol=2e-8)
                    trajectory_records.append({'particle_id':rev['particle_order'][i],
                        'execution_index':i,'saved_states':len(t),
                        'max_difference_separate_RK4':float(np.max(np.abs(actual-fine))),
                        'max_refinement_difference':float(np.max(np.abs(coarse-fine)))})
        else:
            assert case=='T1' and read(run/'analysis.json')['mode']=='static'
            assert not (run/'native/trajectories.npz').exists()
    return {'run':record['run'],'status':'complete','static_checks':static_checks,
            'energy_checks':energy_checks,'trajectories':trajectory_records}


def check(output):
    output=Path(output);manifest=read(output/'qualification.json')
    assert manifest['status']=='complete' and set(manifest['cases'])=={'E1','G1','T1'}
    result={'status':'passed','reference':'separate analytic source formulas and RK4; same author',
            'cases':{},'total_saved_trajectories':0,'total_static_checks':0,
            'meaning':'data-only independent test-body membership, not coupled dynamics'}
    for case,record in manifest['cases'].items():
        folder=output/case
        source=read(folder/'source.json')
        assert digest((folder/'source.json').read_bytes())==record['source_sha256']
        roots=read(folder/'root-run/revision.json')
        source_ids=record['initial_source_ids']
        refs=[]
        for run in record['runs']:
            detail=check_one(folder,case,run);refs.append(detail)
            result['total_saved_trajectories']+=len(detail.get('trajectories',[]))
            result['total_static_checks']+=detail.get('static_checks',0)
            rev=read(folder/run['run']/'revision.json')
            assert rev['source_order']==source_ids
            for key in source_ids:assert rev['entities'][key]==roots['entities'][key]
        if case=='E1':
            with np.load(folder/'root-run/native/trajectories.npz') as old,\
                 np.load(folder/'added-run/native/trajectories.npz') as new:
                for k in ('position_m','velocity_m_s','kinetic_J','potential_J'):
                    np.testing.assert_allclose(old[f'p0_{k}'],new[f'p0_{k}'],atol=0.,rtol=0.)
                assert len(new['p1_time_s'])==source['samples']
        elif case=='G1':
            with np.load(folder/'root-run/native/trajectories.npz') as old,\
                 np.load(folder/'removed-run/native/trajectories.npz') as new:
                for k in ('position_m','velocity_m_s','kinetic_J','potential_J'):
                    np.testing.assert_allclose(old[f'p1_{k}'],new[f'p0_{k}'],atol=0.,rtol=0.)
            assert record['runs'][1]['status']=='rejected'
        else:
            a=[read(folder/r/'native/result.json')['results'] for r in
               ('root-run','static-added-run','static-removed-run')]
            assert a[0]==a[1]==a[2]
            assert record['initial_particle_ids']==[]
            assert read(folder/'static-added-run/revision.json')['particle_order']==['hypothetical_probe']
            assert read(folder/'static-removed-run/revision.json')['particle_order']==[]
        assert record['baseline_preserved']
        result['cases'][case]={'runs':refs,'baseline_byte_preserved':True,
            'structural_revisions':len(record['revisions'])}
    assert result['total_saved_trajectories']==6
    assert result['total_static_checks']==34
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    data=check(args.output)
    with args.report.open('x',encoding='utf-8') as fd:
        json.dump(data,fd,indent=2);fd.write('\n')
    print(json.dumps({'status':data['status'],'static_checks':data['total_static_checks'],
                      'checked_trajectories':data['total_saved_trajectories']}))
