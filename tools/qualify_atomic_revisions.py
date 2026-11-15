"""Frozen E1/G1/T1 atomic V3 native scenarios (same-author driver).

Uses the unchanged model store/engine and saves exact original bytes, newly
accepted descendant, complete native baseline/final runs and refusal evidence.
The separate verification checker supplies independently expressed physics.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from emfeeld.model_revisions import ModelStore, decode, encode, put, sha256
from emfeeld.model_runs import execute, inspect_run, present_run


CASES = {
    'E1': {
        'scene': 'examples/marker_regression/E1.json',
        'sources': ['negative_line', 'axial_field'],
        'particles': ['test_charge'], 'mode': 'trajectory',
        'probes': [[1.2,.2,.8], [1.5,-.4,1.4], [-.8,.9,.2]],
    },
    'G1': {
        'scene': 'examples/marker_regression/G1.json',
        'sources': ['source_A', 'source_B'],
        'particles': ['body_1', 'body_2'], 'mode': 'trajectory',
        'probes': [[.5,.7,.3], [.8,-.6,.3], [-.9,.5,.7]],
    },
    'T1': {
        'scene': 'examples/structural_revisions/T1.json',
        'sources': ['shell', 'central_point'],
        'particles': [], 'mode': 'static',
        'probes': [[.4,.6,.3], [2.8,.25,.4], [-1.1,.9,.75]],
    },
}


def save(path, value):
    put(path, encode(value))
    return path


def inventory(folder):
    return {p.relative_to(folder).as_posix(): sha256(p.read_bytes())
            for p in folder.rglob('*') if p.is_file()}


def assert_unchanged(folder, original):
    for name, digest in original.items():
        if sha256((folder/name).read_bytes()) != digest:
            raise AssertionError(f'historical bytes modified: {folder/name}')


def origin(case):
    return {
        'origin': 'illustrative_choice',
        'reason': 'Frozen Atomic Scenario V1 hypothesis',
        'evidence': f'Atomic V1 same-author {case} case, not a source given',
    }


def member(case, operation, target, role='source', **extras):
    return {'operation': operation,
            'category': 'structural_change' if operation != 'replace_property'
                        else 'component_property',
            'target_id': target, 'expected_role': role,
            'provenance': origin(case), **extras}


def proposal(case, root, store):
    if case == 'E1':
        old = deepcopy(store.read(root)[0]['entities']['negative_line']['properties'])
        members = [
            member(case, 'remove_source', 'negative_line', expected_source=old),
            member(case, 'add_source', 'shifted_positive_line',
                   source={'type':'line', 'charge_per_m_C_m':1e-11,
                           'center_m':[.4,-.3,0], 'direction':[0,0,1],
                           'reference_radius_m':1.}),
        ]
        sources = ['axial_field', 'shifted_positive_line']
        particles = ['test_charge']
    elif case == 'G1':
        members = [
            member(case, 'replace_property', 'source_A', property='mass_kg',
                   expected_value=2e9, value=2.5e9),
            member(case, 'add_particle', 'body_3', role='particle', particle={
                'mass_kg':.7, 'position_m':[.3,.9,-.4],
                'velocity_m_s':[.03,-.07,.02],
            }),
        ]
        sources = ['source_A', 'source_B']
        particles = ['body_1', 'body_2', 'body_3']
    else:
        members = [
            member(case, 'replace_property', 'shell', property='charge_C',
                   expected_value=2e-9, value=3e-9),
            member(case, 'replace_property', 'central_point', property='charge_C',
                   expected_value=-5e-10, value=-8e-10),
        ]
        sources = ['shell', 'central_point']
        particles = []
    return {
        'proposal_version': 3, 'proposal_id': case+'-atomic',
        'revision_id': case+'-atomic', 'parent': deepcopy(root),
        'category': 'atomic_change', 'scenario_intent': 'teacher_hypothesis',
        'changes': members,
    }, sources, particles


def configs(case, scene, sources, particles, *, revision='baseline'):
    cfg = CASES[case]
    observations = []
    for n, position in enumerate(cfg['probes']):
        for quantity in ('field', 'potential'):
            observations.append({'id': f'{quantity}_{n}', 'type': quantity,
                                 'position_m': position})
    analysis = {'analysis_version':1, 'id':f'{case}-{revision}-analysis',
                'mode':cfg['mode']}
    if cfg['mode'] == 'trajectory':
        analysis.update(
            duration_s=scene['duration_s'], samples=scene['samples'],
            checks={'position_atol_m':1e-6,'velocity_atol_m_s':1e-7,
                    'rtol':1e-7,'max_normalized_energy_drift':1e-7})
        for physical_id in particles:
            for index in (0, scene['samples']//2, scene['samples']-1):
                for quantity in ('position', 'velocity', 'speed',
                                 'kinetic_energy', 'potential_energy', 'total_energy'):
                    observations.append({
                        'id':f'{physical_id}_{quantity}_{index}',
                        'type':'trajectory_sample', 'particle_id':physical_id,
                        'quantity':quantity, 'sample_index':index,
                    })
    investigation = {
        'investigation_version':1,'id':f'{case}-{revision}',
        'model_id':f'atomic-{case}','observations':observations,
    }
    presentation = {
        'presentation_version':1,'id':f'{case}-{revision}-view',
        'bounds_m':scene['bounds_m'],
        'entity_order':sources+particles,
    }
    return investigation, analysis, presentation


def native_run(folder, store, reference, config, ident):
    ref, inv, ana, view = config
    paths = [save(folder/f'{ident}.{name}.json', value)
             for name, value in zip(('ref', 'inv', 'analysis', 'view'),
                                     (ref,inv,ana,view))]
    output = folder/ident
    summary = execute(store.path, *paths, output, run_id=ident)
    inspect_run(output, expected_reference=reference)
    return output, summary


def qualify(output, *, render=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'version':1,'status':'started','design_parent':
              '8fe6331aefa252585b3b90f54b8ee7cbbac5e605',
              'qualification':'same-author native transfer, not independent R2 review',
              'cases':{}}
    save(output/'started.json', report)
    for case, cfg in CASES.items():
        folder = output/case
        folder.mkdir()
        scene_raw = (ROOT/cfg['scene']).read_bytes()
        put(folder/'source.json', scene_raw)
        scene = decode(scene_raw)
        import_spec = {
            'import_version':1, 'model_id':f'atomic-{case}',
            'revision_id':'root', 'source_sha256':sha256(scene_raw),
            'source_ids':cfg['sources'], 'particle_ids':cfg['particles'],
            'default_origin':origin(case),
            'interpretation': {
                'statement':scene['title'], 'assumptions': [
                    'Prescribed fixed sources and independent nonrelativistic bodies; no backreaction'],
                'requirements':['fixed_prescribed_sources',
                                'independent_nonrelativistic_test_particles'],
                'unresolved':[], 'scenario_intent':'illustrative_exploration',
            },
        }
        store, root = ModelStore.import_legacy(
            folder/'source.json',save(folder/'import.json',import_spec),folder/'model')
        baseline_cfg = (root, *configs(case,scene,cfg['sources'],cfg['particles']))
        baseline, before = native_run(folder,store,root,baseline_cfg,'baseline')
        if not before['execution_complete']:
            raise AssertionError(f'{case} original baseline not complete: {before}')
        old_store, old_run = inventory(store.path), inventory(baseline)
        new_proposal, sources, particles = proposal(case,root,store)
        decision = store.revise(save(folder/'atomic-proposal.json',new_proposal))
        if decision['status'] != 'accepted':
            raise AssertionError(f'{case} atomic physical revision not accepted: {decision}')
        child_ref = decision['reference']
        child = store.read(child_ref)[0]
        if child['parent'] != root or child['source_order'] != sources or child['particle_order'] != particles:
            raise AssertionError('atomic named physical mappings changed unexpectedly')
        final_cfg = (child_ref, *configs(case,scene,sources,particles,revision='final'))
        final, after = native_run(folder,store,child_ref,final_cfg,'final')
        if not after['execution_complete']:
            raise AssertionError(f'{case} requested final analysis incomplete: {after}')
        assert_unchanged(store.path,old_store)
        assert_unchanged(baseline,old_run)
        records = [{'name':'baseline','reference':root,'status':'complete'},
                   {'name':'final','reference':child_ref,'status':'complete'}]
        if case == 'E1':
            # An old display explicitly naming the removed physical source
            # must refuse; it cannot be silently redirected.
            blocked = (child_ref, baseline_cfg[1], baseline_cfg[2],
                       baseline_cfg[3])
            _, denied = native_run(folder,store,child_ref,blocked,'rejected-old-presentation')
            if denied['status'] != 'rejected' or 'display ordering' not in denied['reason']:
                raise AssertionError(f'old presentation not rejected: {denied}')
            records.append({'name':'rejected-old-presentation','reference':child_ref,
                            'status':'rejected'})
        if render:
            present_run(final, sample_index=scene.get('samples',2)//2 if cfg['mode']=='trajectory' else 0,
                        screenshot_directory=folder/'view-final')
        report['cases'][case] = {
            'source_sha256':sha256(scene_raw), 'root':root,'final':child_ref,
            'sources':sources,'particles':particles,'runs':records,
            'baseline_preserved':True, 'accepted_revision_count':1,
            'rendered':render,
        }
    report['status']='complete'
    save(output/'qualification.json',report)
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--render',action='store_true')
    args=p.parse_args()
    print(encode(qualify(args.output,render=args.render)).decode())
