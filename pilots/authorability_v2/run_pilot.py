"""Generic assessment of data-only packets through the existing emfeeld CLI.

No case-specific physics/roots/output extraction calculations. Reference JSON is
an external judge and never replaces native results. The source-aware author
prepared it separately; it is not an independent or blind judge.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))

def blob(data: bytes) -> str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def freeze_check() -> dict:
    frozen = load(HERE/'frozen_files.json')
    changed = [name for name, sha in frozen['files'].items()
               if not (ROOT/name).is_file() or blob((ROOT/name).read_bytes()) != sha]
    return {'passed': not changed, 'checked_local_files': len(frozen['files']),
            'changed': changed, 'commit': frozen['commit'], 'tree': frozen['tree'],
            'inherited_entries': frozen['inherited']}

def close(actual: Any, expected: Any, atol: float, rtol: float) -> bool:
    """Strict shape and finite-value comparison; scalar/list mismatch is an error."""
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual)==len(expected)
                and all(close(a,b,atol,rtol) for a,b in zip(actual,expected)))
    if type(actual) not in (int,float) or not math.isfinite(actual):
        return False
    return abs(actual-expected) <= atol+rtol*abs(expected)

def get_path(value: dict, path: str) -> Any:
    for part in path.split('.'):
        value = value[part]
    return value

def assess(case: dict, report: dict | None, references: list, code: int, stderr: str) -> dict:
    issues=[]; comparisons=[]
    if code != case['expected_cli_exit']:
        issues.append(f'CLI exit {code}, expected {case["expected_cli_exit"]}')
    if case.get('expected_error_contains'):
        if case['expected_error_contains'] not in stderr:
            issues.append('Expected schema error text absent')
        if report is not None:
            issues.append('Rejected schema unexpectedly produced a numerical report')
    else:
        if not isinstance(report, dict):
            issues.append('Missing native numerical report')
        else:
            rows=report.get('results',[])
            if len(rows)!=len(case['expected_statuses']):
                issues.append('Unexpected request/result count')
            result_map={r['id']:r for r in rows}
            if set(result_map)!=set(case['expected_statuses']):
                issues.append('Result identifiers do not match requested identifiers')
            for ident, expected in case['expected_statuses'].items():
                r=result_map.get(ident,{})
                if r.get('status')!=expected:
                    issues.append(f'{ident}: {r.get("status")} != {expected}')
                if r.get('type')=='trajectory_event' and r.get('status')=='ok':
                    if (r.get('state') is None or len(r.get('diagnostics',{}).get('passes',[]))!=2
                        or not r.get('diagnostics',{}).get('refinement',{}).get('passed')):
                        issues.append(f'{ident}: missing native event state/refinement evidence')
            for ref in references:
                r=result_map.get(ref['observation'],{})
                try:
                    actual=get_path(r,ref['path'])
                    unit=(r.get('units',{}).get(ref['path'].split('.')[-1])
                          if ref['path'].startswith('state.') else r.get('unit'))
                    ok=(r.get('status')=='ok' and unit==ref['unit']
                        and close(actual,ref['expected'],ref['atol'],ref['rtol']))
                except (KeyError,TypeError):
                    actual=None;unit=None;ok=False
                comparisons.append({**ref,'actual':actual,'actual_unit':unit,'passed':ok})
                if not ok: issues.append(f'{ref["observation"]}.{ref["path"]}: reference/unit/shape mismatch')
    role=case['role']
    return {'id':case['id'],'role':role,
            'status': ('FAIL' if issues else 'UNSUPPORTED' if role=='limitation_control' else 'PASS'),
            'expected_outcome_verified':not issues,'issues':issues,'checks':comparisons,
            'native_returncode':code,
            'native_statuses':{r['id']:r['status'] for r in (report or {}).get('results',[])}}

def run(output: Path, ids: list[str] | None=None) -> dict:
    """Run once per packet. Existing evidence is never overwritten."""
    before=freeze_check()
    if not before['passed']: raise RuntimeError('Frozen engine files changed: '+str(before['changed']))
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()): raise FileExistsError('Use an empty output directory; preserve prior attempts')
    corpus=load(HERE/'cases.json'); refs=load(HERE/'references.json')['checks']
    selected=[c for c in corpus['cases'] if ids is None or c['id'] in ids]
    if not selected or (ids is not None and set(ids)!={c['id'] for c in selected}):
        raise ValueError('Unknown or empty case selection')
    env=dict(os.environ)
    env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    summary={'frozen_engine':before['commit'],'scope':'Source-aware assisted numerical instantiations; not blind/independent.',
             'cases':[],'before':before}
    for case in selected:
        folder=output/case['id'];folder.mkdir()
        packet=HERE/case['file']; target=folder/'native.json'
        prefix=[sys.executable,'-m','emfeeld.observations',str(packet)]
        valid=subprocess.run([*prefix,'--validate-only'],cwd=ROOT,env=env,text=True,capture_output=True,timeout=40)
        (folder/'validate.stdout').write_text(valid.stdout);(folder/'validate.stderr').write_text(valid.stderr)
        result=subprocess.run([*prefix,'--output',str(target)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=40)
        (folder/'run.stdout').write_text(result.stdout);(folder/'run.stderr').write_text(result.stderr)
        report=load(target) if target.exists() else None
        judged=assess(case,report,refs[case['id']],result.returncode,result.stderr)
        validation_expected=2 if case.get('expected_error_contains') else 0
        if valid.returncode!=validation_expected:
            judged['issues'].append('Unexpected schema-validation exit')
            judged.update(status='FAIL',expected_outcome_verified=False)
        judged.update(validate_returncode=valid.returncode,packet_sha256=hashlib.sha256(packet.read_bytes()).hexdigest(),
                      native_report_sha256=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None)
        if report is not None and json.loads(result.stdout)!=report:
            judged['issues'].append('CLI stdout and saved report differ');judged.update(status='FAIL',expected_outcome_verified=False)
        summary['cases'].append(judged)
        print(case['id'],judged['status'],len(judged['checks']),'checks',flush=True)
        (output/'assessment.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    summary['after']=freeze_check()
    summary['counts']={status:sum(c['status']==status for c in summary['cases']) for status in ('PASS','UNSUPPORTED','FAIL')}
    summary['verified']=(summary['after']['passed'] and all(c['expected_outcome_verified'] for c in summary['cases']))
    (output/'assessment.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    return summary

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append',dest='ids',help='Run selected case(s) only')
    parser.add_argument('--strict',action='store_true',help='Nonzero unless every selected task is PASS, including controls')
    args=parser.parse_args()
    summary=run(args.output,args.ids)
    print(json.dumps(summary['counts']))
    return 0 if summary['verified'] and (not args.strict or not summary['counts']['UNSUPPORTED']) else 1

if __name__=='__main__':
    raise SystemExit(main())
