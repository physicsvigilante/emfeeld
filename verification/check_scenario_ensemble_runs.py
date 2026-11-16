"""Read-only independent-expression E1/G1/T1 scenario ensemble references.

No production model, field evaluation, integrator or scenario-comparison
algorithm is called. Physical expressions and fixed-step RK4 come from the
existing separately expressed structural-reference checker. Same-author
references are not independent Chat B review or human physics certification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from check_structural_runs import field_potential,rk4


def read(path):
    return json.loads(Path(path).read_bytes())


def reference(root, request, result):
    scene=read(root/'native/packet.json')['scene']
    typ=request['type']
    if typ=='field':
        return np.asarray(field_potential(scene,request['position_m'])[0])
    if typ=='potential_difference':
        v1=field_potential(scene,request['from_m'])[1]
        v2=field_potential(scene,request['to_m'])[1]
        return np.asarray(v2-v1)
    if typ!='trajectory_sample' or request['quantity'] not in ('position','velocity'):
        raise AssertionError('unsupported native physical reference quantity')
    index=request['particle_index']
    particle=scene['particles'][index]
    with np.load(root/'native/trajectories.npz',allow_pickle=False) as data:
        t=data[f'p{index}_time_s']
        trajectory=np.column_stack((data[f'p{index}_position_m'],data[f'p{index}_velocity_m_s']))
    fine=rk4(scene,particle,t,80)
    coarse=rk4(scene,particle,t,40)
    np.testing.assert_allclose(trajectory,fine,atol=2e-7,rtol=2e-7)
    np.testing.assert_allclose(coarse,fine,atol=2e-7,rtol=2e-7)
    if result['sample_index']!=request['sample_index'] or result['time_s']!=float(t[result['sample_index']]):
        raise AssertionError('saved sample and original selector mismatch')
    sl=slice(0,3) if request['quantity']=='position' else slice(3,6)
    ref=fine[result['sample_index'],sl]
    np.testing.assert_allclose(result['value'],trajectory[result['sample_index'],sl],atol=0,rtol=0)
    return ref


def verify_member(case,ensemble,idx):
    baseline=ensemble/'baseline'
    member=ensemble/f'member-{idx:02d}'
    variant=member/'run'
    cmp=read(member/'comparison/result.json')
    authored=read(member/'comparison/request.json')
    left_rows={r['id']:r for r in read(baseline/'native/result.json')['results']}
    right_rows={r['id']:r for r in read(variant/'native/result.json')['results']}
    left_req={r['id']:r for r in read(baseline/'native/packet.json')['observations']}
    right_req={r['id']:r for r in read(variant/'native/packet.json')['observations']}
    counts={'static':0,'trajectory':0,'unavailable':0}
    largest=0.
    for pair,out in zip(authored['pairs'],cmp['comparisons']):
        if pair['id']!=out['id']:
            raise AssertionError('comparison row order/id differs from authored pair')
        typ=pair['type']
        left=pair['left_observation_id']
        right=pair['right_observation_id']
        if out['status']!='ok':
            if case!='G1' or typ!='particle_position' or out['code']!='unknown_operand':
                raise AssertionError('unexpected missing or invalid measurement')
            if out['value'] is not None:
                raise AssertionError('unavailable value must be null, not fabricated zero')
            counts['unavailable']+=1
            continue
        if left not in left_req or right not in right_req:
            raise AssertionError('successful comparison lacks a native request')
        left_ref=reference(baseline,left_req[left],left_rows[left])
        right_ref=reference(variant,right_req[right],right_rows[right])
        if typ=='field_magnitude':
            left_ref=np.asarray(float(np.linalg.norm(left_ref)))
            right_ref=np.asarray(float(np.linalg.norm(right_ref)))
        expected=np.asarray(right_ref)-np.asarray(left_ref)
        actual=np.asarray(out['value'])
        atol=3e-7 if typ.startswith('particle_') else 1e-10
        np.testing.assert_allclose(actual,expected,atol=atol,rtol=2e-7)
        origin_l=left_rows[left]['magnitude'] if typ=='field_magnitude' else left_rows[left]['value']
        origin_r=right_rows[right]['magnitude'] if typ=='field_magnitude' else right_rows[right]['value']
        np.testing.assert_allclose(actual,
             np.asarray(origin_r)-np.asarray(origin_l),atol=0,rtol=0)
        largest=max(largest,float(np.max(np.abs(expected-actual))))
        counts['trajectory' if typ.startswith('particle_') else 'static']+=1
    counts['maximum_reference_difference_in_native_units']=largest
    return counts


def verify(output):
    output=Path(output)
    manifest=read(output/'qualification.json')
    if manifest['status']!='complete' or len(manifest['cases'])!=3:
        raise AssertionError('native case manifest is incomplete')
    records={}
    counts={'static_comparisons':0,'trajectory_comparisons':0,'expected_unavailable':0}
    for case,info in manifest['cases'].items():
        if case not in ('E1','G1','T1') or info['accepted_child_revisions']!=2:
            raise AssertionError('wrong native case or member count')
        if info['status']!=('partial' if case=='G1' else 'complete'):
            raise AssertionError('unexpected native aggregate completion status')
        path=output/case/'ensemble'
        summary=read(path/'summary.json')
        if summary['status']!=info['status'] or len(summary['members'])!=2:
            raise AssertionError('ensemble summary contradicts saved case manifest')
        members=[verify_member(case,path,index) for index in (1,2)]
        for item in members:
            counts['static_comparisons']+=item['static']
            counts['trajectory_comparisons']+=item['trajectory']
            counts['expected_unavailable']+=item['unavailable']
        records[case]=members
    if counts!={'static_comparisons':20,'trajectory_comparisons':12,'expected_unavailable':2}:
        raise AssertionError(f'wrong reference-comparison coverage: {counts}')
    return {'status':'passed','scope':'same-author E1 G1 T1 independent source formulas and fixed-step RK4',
            'cases':records,**counts}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    checked=verify(args.output)
    with args.report.open('x',encoding='utf-8') as f:
        json.dump(checked,f,indent=2);f.write('\n')
    print(json.dumps(checked,indent=2))
