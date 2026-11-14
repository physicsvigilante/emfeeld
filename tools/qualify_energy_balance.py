"""Fresh native model run for issue #7; no alternative physics or tolerance tuning."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from emfeeld.model_revisions import ModelStore, encode
from emfeeld.model_runs import present_run

ROOT = Path(__file__).resolve().parents[1]


def qualify(output, *, render=False):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    def write(name, data):
        path=output/name
        with path.open('xb') as f: f.write(encode(data))
        return path
    scene=dict(schema_version=1, title='Issue 7: exact rest at zero potential, nonzero field',
        kind='electric', sources=[
            dict(type='solid_sphere',charge_C=2e-9,center_m=[-1.,0.,0.],radius_m=.25),
            dict(type='solid_sphere',charge_C=-2e-9,center_m=[1.,0.,0.],radius_m=.25)],
        particles=[dict(mass_kg=1e-11,charge_C=1e-12,position_m=[0.,0.,0.],velocity_m_s=[0.,0.,0.])],
        duration_s=.45,samples=451,bounds_m=[-1.5,1.5,-.9,.9,-.9,.9])
    source=write('source.json',scene)
    assignment=write('assignment.json',dict(import_version=1,model_id='zero_energy_lesson',revision_id='root',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_ids=['positive','negative'],particle_ids=['test_charge'],
        default_origin=dict(origin='illustrative_choice',reason='Reproduce the exact issue-7 physical parameters',evidence='Repository issue #7'),
        interpretation=dict(statement='Rest release at midpoint of two fixed opposite uniform spheres; outside both sources.',
            assumptions=['Static prescribed sources; independent nonrelativistic test charge; no collisions or polarization'],
            requirements=['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],unresolved=[],scenario_intent='illustrative_exploration')))
    _, ref=ModelStore.import_legacy(source,assignment,output/'model')
    reference=write('reference.json',ref)
    observations=[dict(id='E_origin',type='field',position_m=[0,0,0]),dict(id='V_origin',type='potential',position_m=[0,0,0])]
    for q in ('position','velocity','kinetic_energy','potential_energy','total_energy'):
        observations.append(dict(id=q,type='trajectory_sample',particle_id='test_charge',quantity=q,sample_index=450))
    inv=write('investigation.json',dict(investigation_version=1,id='zero_launch',model_id=ref['model_id'],observations=observations))
    analysis=write('analysis.json',dict(analysis_version=1,id='original_policy',mode='trajectory',duration_s=.45,samples=451,
        checks=dict(position_atol_m=1e-7,velocity_atol_m_s=1e-7,rtol=1e-7,max_normalized_energy_drift=1e-7)))
    presentation=write('presentation.json',dict(presentation_version=1,id='recorded_zero_launch',bounds_m=scene['bounds_m']))
    command=[sys.executable,'-m','emfeeld','model','run',str(reference),'--store',str(output/'model'),
        '--investigation',str(inv),'--analysis',str(analysis),'--presentation',str(presentation),
        '--run-id','midpoint-release','--output',str(output/'run')]
    result=subprocess.run(command,text=True,capture_output=True,check=False,timeout=60)
    (output/'command.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'native model run failed with exit {result.returncode}; see {output}/command.log')
    summary=json.loads(result.stdout)
    if not (summary['execution_complete'] and summary['numerical_checks_passed'] and summary['render_ready']):
        raise RuntimeError('native model did not qualify its requested motion')
    if render: present_run(output/'run', sample_index=450, screenshot_directory=output/'preview')
    print(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True); parser.add_argument('--render',action='store_true')
    args=parser.parse_args();qualify(args.output,render=args.render)
