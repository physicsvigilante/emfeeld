"""Same-author independent-expression reference for cross-scenario native evidence.

Never imports the emfeeld runtime or evaluates a production source/solver.
Reads existing sealed native traces and uses separate ideal-source expressions
and fixed-step RK4 from the historical reference checker. Not a Chat B review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from check_structural_runs import field_potential, rk4


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit_files(root, *, ignore='integrity.json'):
    recorded=read(root/ignore)['files']
    actual={p.relative_to(root).as_posix():sha(p.read_bytes())
            for p in root.rglob('*') if p.is_file() and p!=root/ignore}
    if actual != recorded:
        raise AssertionError('sealed inventory mismatch: '+str(root))


def run_info(root):
    audit_files(root)
    run=read(root/'run.json')
    for name,expected in run['input_sha256'].items():
        if sha((root/name).read_bytes())!=expected:
            raise AssertionError('captured native input changed')
    packet=read(root/'native/packet.json')
    report=read(root/'native/result.json')
    assert report['input']==packet
    assert read(root/'summary.json')['execution_complete']
    if (root/'native/integrity.json').is_file():
        audit_files(root/'native')
    results={x['id']:x for x in report['results']}
    assert len(results)==len(report['results'])
    assert set(results)=={x['id'] for x in packet['observations']}
    return run,packet,results


def check(case,folder,info):
    left,right=folder/'left',folder/'right'
    lrun,lp,lv=run_info(left)
    rrun,rp,rv=run_info(right)
    result=read(folder/'comparison/result.json')
    request=read(folder/'comparison/request.json')
    audit_files(folder/'comparison')
    assert request['left_run_sha256']==sha((left/'run.json').read_bytes())
    assert request['right_run_sha256']==sha((right/'run.json').read_bytes())
    assert lrun['reference']==info['root_reference'] and rrun['reference']==info['final_reference']
    assert lrun['root_reference']==rrun['root_reference']
    assert lrun['implementation_sha256']==rrun['implementation_sha256']
    expected_overall='partial' if case=='G1' else 'complete'
    assert result['status']==expected_overall
    lscene,rscene=lp['scene'],rp['scene']
    checks=0;motion=0;largest=0.
    for pair,row in zip(request['pairs'],result['comparisons']):
        assert pair['id']==row['id']
        assert row['error_bound'] is None
        if row['status']!='ok':
            assert case=='G1' and pair['id']=='body-3-absent'
            assert row['code']=='unknown_operand' and row['value'] is None
            continue
        obs_l=lv[pair['left_observation_id']]
        obs_r=rv[pair['right_observation_id']]
        typ=pair['type']
        if typ.startswith('field_'):
            point=row['context']['position_m']
            lvec=field_potential(lscene,point)[0]
            rvec=field_potential(rscene,point)[0]
            if typ=='field_magnitude':
                lval=float(np.linalg.norm(lvec));rval=float(np.linalg.norm(rvec))
            else:lval,rval=lvec,rvec
            checks+=1
            atol=1e-10
        elif typ=='potential_difference':
            p0=row['context']['from_m'];p1=row['context']['to_m']
            lval=field_potential(lscene,p1)[1]-field_potential(lscene,p0)[1]
            rval=field_potential(rscene,p1)[1]-field_potential(rscene,p0)[1]
            checks+=1;atol=1e-10
        else:
            name=pair['particle_id'];idx_l=read(left/'mapping.json')['particles'][name]
            idx_r=read(right/'mapping.json')['particles'][name]
            assert idx_l==obs_l['particle_index'] and idx_r==obs_r['particle_index']
            pos_or_vel=typ.split('_')[1]
            def native_reference(run,scene,index,observed):
                with np.load(run/'native/trajectories.npz',allow_pickle=False) as data:
                    times=data[f'p{index}_time_s']
                    state=np.column_stack((data[f'p{index}_position_m'],data[f'p{index}_velocity_m_s']))
                fine=rk4(scene,scene['particles'][index],times,40)
                coarse=rk4(scene,scene['particles'][index],times,20)
                np.testing.assert_allclose(state,fine,atol=2e-7,rtol=2e-7)
                np.testing.assert_allclose(coarse,fine,atol=2e-7,rtol=2e-7)
                selected=observed['sample_index']
                assert float(times[selected])==observed['time_s']
                np.testing.assert_allclose(observed['value'],state[selected,0:3] if pos_or_vel=='position' else state[selected,3:6],atol=0,rtol=0)
                return fine[selected,0:3] if pos_or_vel=='position' else fine[selected,3:6]
            lval=native_reference(left,lscene,idx_l,obs_l)
            rval=native_reference(right,rscene,idx_r,obs_r)
            assert row['context']['time_s']==obs_l['time_s']==obs_r['time_s']
            motion+=1;atol=3e-7
        expected=np.asarray(rval)-np.asarray(lval)
        actual=np.asarray(row['value'])
        np.testing.assert_allclose(actual,expected,atol=atol,rtol=2e-7)
        native=np.asarray(obs_r['magnitude'] if typ=='field_magnitude' else obs_r['value'])-np.asarray(obs_l['magnitude'] if typ=='field_magnitude' else obs_l['value'])
        np.testing.assert_allclose(actual,native,atol=0,rtol=0)
        largest=max(largest,float(np.max(np.abs(actual-expected))))
    assert info['complete_pairs']==checks+motion
    assert info['unavailable_pairs']==(1 if case=='G1' else 0)
    return {'static_comparisons':checks,'trajectory_comparisons':motion,
            'expected_unavailable':info['unavailable_pairs'],'max_reference_error_native_units':largest}


def verify(output):
    root=Path(output);manifest=read(root/'qualification.json')
    assert manifest['status']=='complete'
    rows={name:check(name,root/name,info) for name,info in manifest['cases'].items()}
    return {'status':'passed','attribution':'same-author independent expressions and RK4, not independent Chat B',
            'cases':rows,'static_comparisons':sum(x['static_comparisons'] for x in rows.values()),
            'trajectory_comparisons':sum(x['trajectory_comparisons'] for x in rows.values()),
            'expected_unavailable':sum(x['expected_unavailable'] for x in rows.values())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--report',type=Path,required=True)
    args=p.parse_args()
    report=verify(args.output)
    with args.report.open('x',encoding='utf-8') as output:
        json.dump(report,output,indent=2);output.write('\n')
    print(json.dumps(report,indent=2))
