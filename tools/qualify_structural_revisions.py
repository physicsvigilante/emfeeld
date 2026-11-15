"""Exercise data-only structural revisions through the native import/run/apply APIs.

Every output is new, inputs and parents are retained, and numerical qualification
is separate from construction validity. No law or case-specific engine is added.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from emfeeld.model_revisions import ModelStore, decode, encode, put, sha256
from emfeeld.model_cli import apply_revision
from emfeeld.model_runs import execute, inspect_run, present_run


def save(path, data):
    put(path, encode(data))
    return path


def inventory(folder):
    return {p.relative_to(folder).as_posix(): sha256(p.read_bytes())
            for p in folder.rglob('*') if p.is_file()}


def qualify(output, cases_path=ROOT/'examples/structural_revisions/cases.json', *, render=False):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    raw = Path(cases_path).read_bytes(); manifest = decode(raw)
    put(output/'cases.json', raw)
    report = {'cases_sha256': sha256(raw), 'status': 'started', 'cases': {},
              'meaning': 'same-author qualification; no independent review or educational claim'}
    save(output/'started.json', report)
    origin = {'origin': 'illustrative_choice', 'reason': 'Frozen structural transfer case',
              'evidence': 'examples/structural_revisions/cases.json; not textbook givens'}
    for case in manifest['cases']:
        folder = output/case['id']; folder.mkdir()
        source_raw = (ROOT/case['scene']).read_bytes(); source = decode(source_raw)
        source_path = folder/'source.json'; put(source_path, source_raw)
        assignment = {'import_version': 1, 'model_id': case['id'], 'revision_id': 'root',
            'source_sha256': sha256(source_raw), 'source_ids': case['source_ids'],
            'particle_ids': case['particle_ids'], 'default_origin': origin,
            'interpretation': {'statement': source['title'], 'assumptions': [
                'Prescribed fixed sources; independent nonrelativistic test bodies; no source reaction or collisions.'],
                'requirements': ['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
                'unresolved': [], 'scenario_intent': 'illustrative_exploration'}}
        store, root = ModelStore.import_legacy(source_path, save(folder/'import.json', assignment), folder/'model')
        inv = {'investigation_version': 1, 'id': 'inspection', 'model_id': case['id'], 'observations': []}
        for i, point in enumerate(case.get('probes', [[.4,.7,.3],[1.1,-.7,.3],[-.8,.9,.4]])):
            for quantity in ('field','potential'):
                inv['observations'].append({'id': f'{quantity}_{i}', 'type': quantity, 'position_m': point})
        analysis = {'analysis_version': 1, 'id': 'analysis', 'mode': case['mode']}
        if case['mode'] == 'trajectory':
            analysis.update(duration_s=source['duration_s'], samples=source['samples'], checks={
                'position_atol_m': 1e-6, 'velocity_atol_m_s': 1e-7,
                'rtol': 1e-7, 'max_normalized_energy_drift': 1e-7})
            for body in case['particle_ids']:
                for index in (0, source['samples']//2, source['samples']-1):
                    for quantity in ('position','velocity','speed','kinetic_energy','potential_energy','total_energy'):
                        inv['observations'].append({'id': f'{body}_{quantity}_{index}', 'type': 'trajectory_sample',
                            'particle_id': body, 'quantity': quantity, 'sample_index': index})
        view = {'presentation_version': 1, 'id': 'root-view', 'bounds_m': source['bounds_m'],
                'entity_order': case['source_ids'] + case['particle_ids']}
        ref_path = save(folder/'root.reference.json', root)
        paths = [save(folder/name, data) for name,data in [('investigation.json',inv),('analysis.json',analysis),('presentation.json',view)]]
        prior = folder/'root-run'
        summary = execute(store.path, ref_path, *paths, prior, run_id=case['id']+'-root')
        if not summary['execution_complete']: raise RuntimeError(summary)
        protected = inventory(store.path); protected_run = inventory(prior)
        entries = [{'revision': root, 'path': str(prior.relative_to(output)), 'summary': summary}]
        parent = root
        for edit in case['changes']:
            snapshot = store.read(parent)[0]
            p = {'proposal_version': 2, 'proposal_id': edit['id'], 'revision_id': edit['id'], 'parent': parent,
                 'category': 'structural_change', 'operation': edit['operation'], 'target_id': edit['target_id'],
                 'expected_role': 'source', 'scenario_intent': 'teacher_hypothesis', 'provenance': origin}
            if edit['operation'] == 'add_source': p['source'] = edit['source']
            else: p['expected_source'] = deepcopy(snapshot['entities'][edit['target_id']]['properties'])
            presentation = {**view, 'id': edit['id']+'-view', 'entity_order': edit['view_order']}
            child = folder/edit['id']
            outcome = apply_revision(save(folder/(edit['id']+'.proposal.json'), p), store_path=store.path,
                using=prior, output=child, run_id=case['id']+'-'+edit['id'],
                presentation_path=save(folder/(edit['id']+'.presentation.json'), presentation))
            if outcome['status'] != 'complete': raise RuntimeError(outcome)
            parent = outcome['decision']['reference']; prior = child/'run'
            inspect_run(prior, expected_reference=parent)
            entries.append({'revision': parent, 'path': str(prior.relative_to(output)), 'summary': outcome['calculation']})
            for name, digest in protected.items():
                if sha256((store.path/name).read_bytes()) != digest: raise AssertionError('baseline store modified')
            if inventory(folder/'root-run') != protected_run: raise AssertionError('baseline run modified')
        if render:
            for i, entry in enumerate(entries):
                present_run(output/entry['path'], sample_index=source.get('samples',2)//2 if case['mode']=='trajectory' else 0,
                            screenshot_directory=folder/f'view-{i}')
        report['cases'][case['id']] = {'runs': entries, 'baseline_preserved': True,
            'production_case_branches': 0, 'visual_review': 'pending' if render else 'not_requested'}
    report['status'] = 'complete'
    save(output/'qualification.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--cases', type=Path, default=ROOT/'examples/structural_revisions/cases.json')
    p.add_argument('--render', action='store_true')
    a = p.parse_args(); print(encode(qualify(a.output, a.cases, render=a.render)).decode())
