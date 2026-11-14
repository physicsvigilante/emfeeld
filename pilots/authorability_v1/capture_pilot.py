"""Capture authored scenes using the unchanged real-viewer qualification function.

This is Linux offscreen evidence, not Windows interaction. No viewer patches or
custom cavity/flux/equipotential geometry are added for this pilot.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,traceback
from pathlib import Path
from emfeeld import load_scene

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/authorability_v1/renders')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('qualified_viewer',ROOT/'tools/qualify_viewer.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    packet=json.loads((HERE/'cases.json').read_text())
    report=dict(frozen_commit=packet['frozen_commit'],cases={},scope='Unchanged real PyVista viewer; numerical source identity checked separately; no Windows or independent-review claim.',visual_inspection='PENDING')
    for case in packet['cases']:
        try:
            report['cases'][case['id']]=module.capture(case['id'],load_scene(HERE/case['scene']),args.output)
        except Exception:report['cases'][case['id']]=dict(status='FAIL',traceback=traceback.format_exc())
        (args.output/'capture_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(case['id'],report['cases'][case['id']]['status'],flush=True)
    report['status']='PASS' if all(c['status']=='PASS' for c in report['cases'].values()) else 'FAIL'
    report['frame_count']=sum(len(c.get('frames',[])) for c in report['cases'].values())
    (args.output/'capture_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(report['status'],report['frame_count'],'frames',flush=True)
    return int(report['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
