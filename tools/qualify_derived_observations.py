"""E1/G1/T1 qualified derived observations on sealed existing sweep-run evidence.

This invokes no simulation. It reads the already-qualified native E1/G1/T1
sweep baseline runs, checks derived outputs and independent analytic/RK4 references.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'verification'))
from emfeeld.derived_observations import derive,inspect, _inventory as derived_inventory
from emfeeld.model_revisions import encode, decode, put, sha256, RevisionError
from emfeeld.model_runs import _inventory as native_inventory
from check_sweep_runs import field_potential, rk4


def _ratio(ident, a, b):
    return {'id':ident,'type':'ratio',
            'numerator':{'id':a,'part':'magnitude'},
            'denominator':{'id':b,'part':'magnitude'}}


def _snapshot(path):
    return {p.relative_to(path).as_posix():sha256(p.read_bytes()) for p in path.rglob('*') if p.is_file()}


def qualify(source,output):
    source,output=Path(source),Path(output)
    if output.exists():raise FileExistsError('new output required')
    saved={}
    for case in ('E1','G1','T1'):
        path=source/f'sweep-{case}'/'sweep'/'baseline'
        if not path.is_dir():raise ValueError(f'missing sealed {case} baseline: {path}')
        saved[case]=_snapshot(path)
    output.mkdir(parents=True,exist_ok=False)
    outcomes={}
    for case in ('E1','G1','T1'):
        native=source/f'sweep-{case}'/'sweep'/'baseline'
        observations=[_ratio(f'{case}-field-ratio','field_0','field_1')]
        if case=='G1':
            observations += [{'id':'G1-distance','type':'separation','left_id':'body_1_position_50','right_id':'body_2_position_50'},
                 {'id':'G1-invalid-time','type':'separation','left_id':'body_1_position_0','right_id':'body_2_position_50'}]
        if case=='T1':
            observations += [_ratio('T1-another-pair','field_1','field_2')]
        request={'derived_version':1,'id':f'derived-{case}',
                 'source_run_sha256':sha256((native/'run.json').read_bytes()),
                 'observations':observations}
        casepath=output/case;casepath.mkdir()
        put(casepath/'request.json',encode(request))
        result=derive(casepath/'request.json',using=native,output=casepath/'result')
        assert inspect(casepath/'result',using=native)==result
        native_report=decode((native/'native/result.json').read_bytes())
        scene=native_report['input']['scene'];readings={x['id']:x for x in native_report['results']}
        for row in result['observations']:
            if row['type']!='ratio' or row['status']!='ok':continue
            r0=readings[row['operands'][0]['observation_id']]
            r1=readings[row['operands'][1]['observation_id']]
            f0,_=field_potential(scene,r0['position_m']);f1,_=field_potential(scene,r1['position_m'])
            import numpy as np
            expected=float(np.linalg.norm(f0)/np.linalg.norm(f1))
            assert math.isclose(row['value'],expected,rel_tol=1e-10,abs_tol=1e-10)
        if case=='G1':
            assert result['status']=='partial'
            assert result['observations'][-1]['code']=='different_saved_times'
            first=rk4(scene,0,40)[50,:3];second=rk4(scene,1,40)[50,:3]
            import numpy as np
            distance=float(np.linalg.norm(first-second))
            assert math.isclose(result['observations'][1]['value'],distance,rel_tol=1e-5,abs_tol=5e-6)
            # Chat B F-02: challenge the *actual saved G1 partial case*.
            # A re-sealed copy with contradictory top-level completion must
            # not be accepted by deterministic post-run inspection.
            forged=casepath/'review-challenge-resealed-output'
            shutil.copytree(casepath/'result',forged)
            altered=decode((forged/'result.json').read_bytes())
            altered['status']='complete'
            (forged/'result.json').write_bytes(encode(altered))
            (forged/'integrity.json').write_bytes(encode({'files':derived_inventory(forged)}))
            try:
                inspect(forged,using=native)
            except RevisionError as exc:
                assert exc.code=='derived_integrity'
            else:
                raise AssertionError('re-sealed G1 partial result incorrectly certified complete')
            assert inspect(casepath/'result',using=native)['status']=='partial'
            # Chat B F-03: a physically impossible negative magnitude in a
            # separately re-sealed copy of a genuine native G1 report is not
            # evidence of a solver defect, but must fail closed here.
            forged_run=casepath/'review-challenge-resealed-native'
            shutil.copytree(native,forged_run)
            packet=forged_run/'native/result.json'
            altered=decode(packet.read_bytes())
            field=next(r for r in altered['results'] if r['id']=='field_0')
            field['magnitude']=-2.5
            packet.write_bytes(encode(altered))
            (forged_run/'integrity.json').write_bytes(encode({'files':native_inventory(forged_run)}))
            rejected=derive(casepath/'request.json',using=forged_run,
                            output=casepath/'review-challenge-rejected-out')
            assert rejected['status']=='partial'
            assert rejected['observations'][0]['code']=='operand_unavailable'
        else:assert result['status']=='complete'
        outcomes[case]={'status':result['status'],'derived_count':len(result['observations']),
                        'source_run_sha256':request['source_run_sha256'],
                        'reference':'independent ideal-source expressions; G1 also separate 40-substep RK4'}
        if saved[case]!=_snapshot(native):
            raise AssertionError(f'{case} original native artifact changed')
    put(output/'summary.json',encode({'status':'passed','cases':outcomes,
         'meaning':'post-processing on same-author qualified source cases, not independently reviewed'}))
    return outcomes


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(encode(qualify(a.source,a.output)).decode(),end='')
