"""Read-only, separate-expression reference check of Atomic V1 native traces.

This checker does not call emfeeld physics, integrators or revisions. Analytic
ideal-source expressions and independent fixed-step RK4 are provided by the
existing same-author check_structural_runs.py reference module. This is not
independent Chat B or human physics adjudication.
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


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(run):
    sealed = read(run/'integrity.json')['files']
    actual = {p.relative_to(run).as_posix(): digest(p.read_bytes())
              for p in run.rglob('*') if p.is_file() and p != run/'integrity.json'}
    if sealed != actual:
        raise AssertionError(f'run inventory mismatch: {run}')
    report = read(run/'run.json')
    for name, expected in report['input_sha256'].items():
        if digest((run/name).read_bytes()) != expected:
            raise AssertionError('recorded run input bytes changed')
    return report


def check_run(folder, case, entry, record):
    name = entry['name']
    run = folder/name
    metadata = inventory(run)
    if metadata['reference'] != entry['reference']:
        raise AssertionError('run bound to a different revision')
    summary = read(run/'summary.json')
    if entry['status'] == 'rejected':
        assert summary['status'] == 'rejected' and not summary['execution_complete']
        assert 'display ordering' in summary['reason']
        return {'name':name,'status':'rejected','correct_named_display_refusal':True}
    assert summary['status'] == 'complete' and summary['execution_complete']
    packet = read(run/'native/packet.json')
    result = read(run/'native/result.json')
    assert result['input'] == packet
    scene = packet['scene']
    revision = read(run/'revision.json')
    mapping = read(run/'mapping.json')
    assert metadata['reference']['revision_id'] == revision['revision_id']
    assert mapping['sources'] == {k:i for i,k in enumerate(revision['source_order'])}
    assert mapping['particles'] == {k:i for i,k in enumerate(revision['particle_order'])}
    assert [revision['entities'][s]['properties'] for s in revision['source_order']] == scene['sources']
    assert [revision['entities'][p]['properties'] for p in revision['particle_order']] == scene['particles']
    observed = {r['id']:r for r in result['results']}
    assert len(observed) == len(result['results']) == len(packet['observations'])
    count = 0
    for request in packet['observations']:
        row = observed[request['id']]
        assert row['status'] == 'ok' and row.get('check',{}).get('passed') is not False
        if request['type'] not in ('field','potential'):
            continue
        f,v = field_potential(scene,request['position_m'])
        expected = f if request['type'] == 'field' else v
        np.testing.assert_allclose(row['value'],expected,atol=1e-10,rtol=1e-10)
        count += 1
    trajectories = []
    if read(run/'analysis.json')['mode'] == 'trajectory':
        with np.load(run/'native/trajectories.npz',allow_pickle=False) as data:
            for index,particle in enumerate(scene['particles']):
                t = data[f'p{index}_time_s']
                positions = data[f'p{index}_position_m']
                velocities = data[f'p{index}_velocity_m_s']
                state = np.column_stack((positions,velocities))
                fine = rk4(scene,particle,t,40)
                coarse = rk4(scene,particle,t,20)
                np.testing.assert_allclose(state,fine,atol=2e-7,rtol=2e-7)
                np.testing.assert_allclose(coarse,fine,atol=2e-7,rtol=2e-7)
                kinetic = .5*particle['mass_kg']*np.sum(velocities*velocities,axis=1)
                potential = np.array([field_potential(scene,p)[1] for p in positions])
                potential *= particle['charge_C'] if scene['kind']=='electric' else particle['mass_kg']
                np.testing.assert_allclose(data[f'p{index}_kinetic_J'],kinetic,atol=1e-10,rtol=1e-10)
                np.testing.assert_allclose(data[f'p{index}_potential_J'],potential,atol=1e-10,rtol=1e-10)
                if case == 'E1':
                    expected_z = (particle['position_m'][2] + particle['velocity_m_s'][2]*t
                                  + .5*(particle['charge_C']/particle['mass_kg'])*.15*t*t)
                    np.testing.assert_allclose(positions[:,2],expected_z,atol=2e-7,rtol=2e-7)
                trajectories.append({
                    'physical_id':revision['particle_order'][index],
                    'saved_states':len(t),
                    'max_state_difference_from_RK4':float(np.max(np.abs(state-fine))),
                    'max_RK4_refinement_difference':float(np.max(np.abs(fine-coarse))),
                    'kinetic_potential_components_checked':True,
                })
    return {'name':name,'status':'complete','static_checks':count,'trajectories':trajectories}


def check(output):
    root = Path(output)
    qual = read(root/'qualification.json')
    assert qual['status'] == 'complete'
    report = {
        'scope':'same-author independent expressions and fixed-step RK4; not Chat B review',
        'status':'passed', 'cases':{}, 'static_checks':0, 'trajectories':0,
    }
    for case, details in qual['cases'].items():
        folder = root/case
        assert digest((folder/'source.json').read_bytes()) == details['source_sha256']
        original = read(folder/'model/revisions'/digest(b'root')/'revision.json')
        # Exact identities and revisions checked independently of driver claims.
        assert original['parent'] is None
        assert original['model_id'] == details['root']['model_id']
        assert details['accepted_revision_count'] == 1
        assert len(list((folder/'model/revisions').iterdir())) == 2
        final = read(folder/'model/revisions'/digest((case+'-atomic').encode())/'revision.json')
        assert final['parent'] == details['root']
        assert final['operation'] == read(folder/'atomic-proposal.json')
        assert final['source_order'] == details['sources']
        assert final['particle_order'] == details['particles']
        if case == 'E1':
            assert final['source_order'] == ['axial_field','shifted_positive_line']
            assert final['entities']['test_charge'] == original['entities']['test_charge']
        elif case == 'G1':
            assert final['entities']['source_A']['properties']['mass_kg'] == 2.5e9
            assert final['entities']['body_3']['properties']['charge_C'] == 0.
            assert final['entities']['body_3']['provenance']['charge_C']['origin'] == 'source_convention'
            for prior in ('body_1','body_2'):
                assert final['entities'][prior] == original['entities'][prior]
        else:
            assert final['particle_order'] == []
            assert final['entities']['shell']['properties']['charge_C'] == 3e-9
            assert final['entities']['central_point']['properties']['charge_C'] == -8e-10
        rows = [check_run(folder,case,entry,details) for entry in details['runs']]
        report['cases'][case] = rows
        report['static_checks'] += sum(r.get('static_checks',0) for r in rows)
        report['trajectories'] += sum(len(r.get('trajectories',[])) for r in rows)
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    record = check(args.output)
    args.report.open('x',encoding='utf-8').write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
