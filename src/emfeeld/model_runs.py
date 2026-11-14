"""Named investigations of immutable model revisions; legacy physics stays authoritative.

python -m emfeeld.model_runs --help
Runtime dependency: Teaching Study V1 capture/presentation adapter, not a new solver.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

from . import study
from .model_revisions import (ModelStore, RevisionError, REQUIREMENTS, decode, encode,
    exact_keys, identifier, identity, put, scene_data, sha256, text, validate_snapshot)
from .observations import packet_from_dict, run_packet


def _presentation(data, revision):
    exact_keys(data, ('presentation_version', 'id', 'bounds_m'),
               ('replay_seconds', 'camera', 'entity_order'))
    if type(data['presentation_version']) is not int or data['presentation_version'] != 1:
        raise ValueError('only presentation_version 1 is supported')
    identifier(data['id'])
    order = data.get('entity_order', list(revision['entities']))
    if not isinstance(order, list) or len(order) != len(set(order)) or set(order) != set(revision['entities']):
        raise ValueError('display ordering must name each entity exactly once')
    for name in ('bounds_m', 'camera'):
        if name not in data: continue
        values = data[name]
        if not isinstance(values, list) or (name == 'camera' and any(not isinstance(r, list) for r in values)):
            raise ValueError('presentation coordinates must have the declared array shape')
        flat = [x for r in values for x in r] if name == 'camera' else values
        if not isinstance(values, list) or any(type(x) not in (int, float) for x in flat):
            raise ValueError('presentation coordinates must be finite JSON numbers')
        a = np.asarray(values, dtype=float)
        if a.shape != ((3, 3) if name == 'camera' else (6,)) or not np.isfinite(a).all():
            raise ValueError('invalid display bounds or camera')
        if name == 'bounds_m' and np.any(a[::2] >= a[1::2]):
            raise ValueError('display bounds need min < max')
        if name == 'camera' and (np.linalg.norm(a[0]-a[1]) == 0 or np.linalg.norm(a[2]) == 0):
            raise ValueError('camera position, focal point and view-up must be resolved')
    speed = data.get('replay_seconds', 12.)
    if type(speed) not in (int, float) or not np.isfinite(speed) or speed <= 0:
        raise ValueError('replay_seconds must be finite and positive')


def lower(revision, investigation, analysis, presentation):
    """Named physical input -> unchanged observation packet + explicit index receipt."""
    validate_snapshot(revision)
    exact_keys(investigation, ('investigation_version', 'id', 'model_id', 'observations'))
    if type(investigation['investigation_version']) is not int or investigation['investigation_version'] != 1:
        raise ValueError('only investigation_version 1 is supported')
    identifier(investigation['id'])
    if investigation['model_id'] != revision['model_id']:
        raise RevisionError('wrong_model', 'investigation belongs to another physical model')
    exact_keys(analysis, ('analysis_version', 'id', 'mode'), ('duration_s', 'samples', 'checks'))
    if type(analysis['analysis_version']) is not int or analysis['analysis_version'] != 1:
        raise ValueError('only analysis_version 1 is supported')
    identifier(analysis['id'])
    mode = analysis['mode']
    if mode not in ('static', 'trajectory'):
        raise RevisionError('unsupported_analysis', 'only prescribed static probes and existing test trajectories are qualified')
    if mode == 'trajectory':
        exact_keys(analysis, ('analysis_version', 'id', 'mode', 'duration_s', 'samples', 'checks'))
        exact_keys(analysis['checks'], ('position_atol_m', 'velocity_atol_m_s', 'rtol', 'max_normalized_energy_drift'))
        for key, value in analysis['checks'].items():
            if type(value) not in (int, float) or not np.isfinite(value) or value <= 0:
                raise ValueError(f'{key}: strictly positive finite numerical check setting required')
    elif set(analysis) != {'analysis_version', 'id', 'mode'}:
        raise ValueError('static analysis has no trajectory horizon, sampling or trajectory checks')
    _presentation(presentation, revision)
    requirements = revision['interpretation']['requirements']
    unsupported = [r for r in requirements if r not in REQUIREMENTS]
    if unsupported:
        raise RevisionError('unsupported_physics', f'unsupported declared physical requirements: {unsupported}')
    unknown = [x['description'] for x in revision['interpretation']['unresolved']
               if x['affects'] in ('all', mode)]
    for key, entity in revision['entities'].items():
        if entity['role'] == 'source' or mode == 'trajectory':
            unknown += [f'{key}.{p}' for p, origin in entity['provenance'].items() if origin['origin'] == 'unknown']
    if unknown:
        raise RevisionError('incomplete_physics', f'missing information required for this analysis: {unknown}')
    stale = [x for x in revision['stale_dependencies']
             if mode == 'trajectory' or revision['entities'][x['target_id']]['role'] == 'source']
    if stale:
        raise RevisionError('stale_computation', f'changed dependencies require new computation evidence: {stale}')
    source_map = {k: i for i, k in enumerate(revision['source_order'])}
    particle_map = {k: i for i, k in enumerate(revision['particle_order'])}
    requests = deepcopy(investigation['observations'])
    if not isinstance(requests, list) or not requests:
        raise ValueError('investigation observations must be a nonempty array')
    for request in requests:
        if not isinstance(request, dict):
            raise ValueError('observation must be an object')
        if 'particle_index' in request:
            raise RevisionError('positional_reference', 'new investigations must address physical particle_id, not array indices')
        if request.get('type') in ('trajectory_sample', 'trajectory_event'):
            if mode != 'trajectory':
                raise RevisionError('unsupported_analysis', 'trajectory requests require a trajectory analysis')
            key = request.pop('particle_id', None)
            if not isinstance(key, str) or key not in particle_map:
                raise RevisionError('wrong_role', 'missing or wrong-role named particle reference')
            request['particle_index'] = particle_map[key]
        elif 'particle_id' in request:
            raise RevisionError('wrong_role', 'static world-coordinate observations do not bind a particle')
    packet = {'observation_schema_version': 1,
              'scene': scene_data(revision, duration_s=analysis.get('duration_s', 1.),
                    samples=analysis.get('samples', 2), bounds_m=presentation['bounds_m']),
              'observations': requests}
    packet_from_dict(packet)
    return packet, {'sources': source_map, 'particles': particle_map,
                    'world_coordinate_probes': True, 'physical_time_origin_s': 0.,
                    'plan': 'rebuild_existing_source_assembly; fresh requested calculations',
                    'analysis_mode': mode, 'cached_cross_revision_results': False}


def _inventory(path):
    return {p.relative_to(path).as_posix(): sha256(p.read_bytes())
            for p in sorted(path.rglob('*')) if p.is_file() and p != path/'integrity.json'}


def execute(store_path, reference_path, investigation_path, analysis_path, presentation_path,
            output, *, run_id):
    """Each attempt is a new directory, including rejected analyses and failures."""
    identifier(run_id)
    store = ModelStore(store_path)
    raw = {'reference.json': Path(reference_path).read_bytes(),
           'investigation.json': Path(investigation_path).read_bytes(),
           'analysis.json': Path(analysis_path).read_bytes(),
           'presentation.json': Path(presentation_path).read_bytes()}
    reference, inv, analysis, presentation = [decode(raw[n]) for n in raw]
    revision, revision_raw = store.read(reference)
    raw['revision.json'] = revision_raw
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    for name, b in raw.items(): put(output/name, b)
    run = {'run_id': run_id, 'reference': reference, 'root_reference': store.info['root'],
           'input_sha256': {name: sha256(b) for name, b in raw.items()},
           'implementation_sha256': {p.name: sha256(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))},
           'status': 'pending', 'qualification': 'not independent review; interpretation requires human assessment'}
    put(output/'run.json', encode(run))
    summary = {'status': 'pending', 'execution_complete': False, 'request_statuses': {},
               'evaluation': {'interpretation_fidelity': 'author recorded; not automatically certified',
                              'physical_correctness': 'see native diagnostics and applicable reference checks',
                              'simulation_coverage': 'explicit per-analysis and per-request outcomes',
                              'educational_usefulness': 'awaiting teacher task feedback',
                              'textbook_answer_completeness': 'optional; not graded'}}
    try:
        packet, mapping = lower(revision, inv, analysis, presentation)
    except (RevisionError, ValueError) as exc:
        summary.update(status='rejected', code=getattr(exc, 'code', 'invalid_analysis'), reason=str(exc))
    else:
        # Unexpected execution exceptions propagate: the pending attempt is retained
        # without a completion/integrity marker, never relabelled unsupported physics.
        put(output/'mapping.json', encode(mapping))
        native_dir = output/'native'; native_dir.mkdir()
        if analysis['mode'] == 'trajectory' or not packet['scene']['particles']:
            # Empty-particle static scenes can retain an empty capture without
            # integrating. A fields-only query must not propagate unrequested bodies.
            result, report = study._capture(native_dir, packet, analysis.get('checks', {}))
        else:
            report = run_packet(packet)  # no full-scene capture and no integration
            put(native_dir/'packet.json', encode(packet)); put(native_dir/'result.json', encode(report))
            result = {'request_statuses': {r['id']: r['status'] for r in report['results']},
                      'render_ready': False, 'numerical_checks_passed': True,
                      'verification_scope': 'native analytic evaluation; no independent per-run reference implied'}
        result['unfulfilled_requests'] = {
            r['id']: r['status'] if r['status'] != 'ok' else 'reference_mismatch'
            for r in report['results'] if r['status'] != 'ok' or r.get('check', {}).get('passed') is False}
        complete = not result['unfulfilled_requests'] and result['numerical_checks_passed']
        summary.update(result, status='complete' if complete else 'partial', execution_complete=complete,
                       mode=analysis['mode'], plan=mapping['plan'])
    put(output/'summary.json', encode(summary))
    put(output/'integrity.json', encode({'files': _inventory(output)}))
    lines = [f'# Model {revision["model_id"]}: revision {revision["revision_id"]}',
             f'Run: {run_id}', f'Parent: {revision["parent"]}',
             f'Scenario intent: {revision["interpretation"]["scenario_intent"]}',
             f'Investigation: {inv.get("id")}; analysis: {analysis.get("id")}',
             f'Status: {summary["status"]}', '',
             'This is a separate prescribed scenario, not a physical transition from its parent.',
             'Canonical records and exact identities are in this directory. REPORT is a presentation only.',
             '', '## Outcomes', json.dumps(summary, indent=2), '',
             '## Physical change', json.dumps(revision['operation'], indent=2),
             '', '## Interpretation', json.dumps(revision['interpretation'], indent=2)]
    # The readable report is an independent presentation, outside sealed evidence.
    report_path = output.parent / (output.name+'.REPORT.md')
    # Avoid accidental overwrite when a different output name shares an existing report.
    if not report_path.exists(): put(report_path, ('\n'.join(lines)+'\n').encode())
    return summary


def inspect_run(output, *, expected_reference=None):
    """Verify saved bindings and re-lower data only; never integrates or uses latest."""
    output = Path(output)
    recorded = decode((output/'integrity.json').read_bytes())
    if recorded.get('files') != _inventory(output):
        raise RevisionError('run_integrity', 'run file inventory or exact bytes changed')
    run = decode((output/'run.json').read_bytes())
    for name, digest in run['input_sha256'].items():
        if sha256((output/name).read_bytes()) != digest:
            raise RevisionError('run_integrity', 'captured input changed')
    raw = (output/'revision.json').read_bytes(); revision = decode(raw)
    if identity(revision, raw) != run['reference']:
        raise RevisionError('wrong_revision', 'run is not bound to the recorded model revision')
    if expected_reference is not None and run['reference'] != expected_reference:
        raise RevisionError('wrong_revision', 'requested revision differs from the recorded run')
    if decode((output/'reference.json').read_bytes()) != run['reference']:
        raise RevisionError('wrong_revision', 'run reference and captured reference disagree')
    summary = decode((output/'summary.json').read_bytes())
    if summary['status'] == 'rejected':
        return run, revision, summary, None
    packet, mapping = lower(revision, decode((output/'investigation.json').read_bytes()),
                            decode((output/'analysis.json').read_bytes()), decode((output/'presentation.json').read_bytes()))
    if packet != decode((output/'native/packet.json').read_bytes()) or mapping != decode((output/'mapping.json').read_bytes()):
        raise RevisionError('wrong_revision', 'native input or physical ID mapping belongs to another revision')
    report = decode((output/'native/result.json').read_bytes())
    if report['input'] != packet:
        raise RevisionError('wrong_revision', 'native results belong to another generated packet')
    return run, revision, summary, report


def compare_runs(left, right):
    a, ar, _, av = inspect_run(left); b, br, _, bv = inspect_run(right)
    if a['root_reference'] != b['root_reference']:
        raise RevisionError('incompatible_models', 'comparisons require the same root model lineage')
    ai = decode((Path(left)/'investigation.json').read_bytes())
    bi = decode((Path(right)/'investigation.json').read_bytes())
    if ai['observations'] != bi['observations'] or ar['kind'] != br['kind']:
        raise RevisionError('incompatible_observations', 'world-coordinate measurements and units must match')
    # Initial slice forbids gauge/frame/source-type changes. Event times are NOT aligned.
    return {'left_run': a['run_id'], 'right_run': b['run_id'],
            'left_revision': a['reference'], 'right_revision': b['reference'],
            'measurements': study._comparisons(av or {}, bv or {}),
            'meaning': 'Separate scenarios; energy differences do not model charging or accretion work.'}


def present_run(output, *, presentation_path=None, sample_index=0, screenshot_directory=None):
    """A separate presentation of one sealed run; snapshots never change source state."""
    from .viewer import make_plotter
    run, revision, summary, _ = inspect_run(output)
    if not summary.get('render_ready'):
        raise RevisionError('preview_unavailable', 'this run has no complete checked trajectories; static measurements remain available')
    scene, trajectories = study.load_recorded(Path(output)/'native')
    presentation = decode(Path(presentation_path).read_bytes()) if presentation_path else decode((Path(output)/'presentation.json').read_bytes())
    _presentation(presentation, revision)
    if summary.get('mode') == 'static' and sample_index != 0:
        raise ValueError('a static field presentation has no physical sample evolution')
    if type(sample_index) is not int or not 0 <= sample_index < scene.samples:
        raise ValueError('sample index must select a recorded state')
    scene = replace(scene, bounds_m=tuple(presentation['bounds_m']))
    dest = Path(screenshot_directory) if screenshot_directory is not None else None
    if dest is not None:
        if dest.resolve().is_relative_to(Path(output).resolve()):
            raise ValueError('presentation output must be outside the sealed run')
        dest.mkdir(parents=True, exist_ok=False)
    label = f'{revision["model_id"]} / {revision["revision_id"]} / {run["run_id"]}; captured run'
    if summary.get('mode') == 'static': label += '; static field, no dynamics'
    plot = make_plotter(scene, recorded=trajectories, study_label=label, off_screen=dest is not None,
                        replay_seconds=presentation.get('replay_seconds', 12.))
    try:
        if 'camera' in presentation: plot.camera_position = presentation['camera']
        if dest is None:
            plot.show()
        else:
            plot.show(auto_close=False)
            time = float(np.linspace(0, scene.duration_s, scene.samples)[sample_index])
            if trajectories: plot._emfeeld_playback.seek(time)
            plot.screenshot(str(dest/'frame.png'))
            put(dest/'presentation.json', encode({'run_id': run['run_id'], 'reference': run['reference'],
                'run_integrity_sha256': sha256((Path(output)/'integrity.json').read_bytes()),
                'settings': presentation, 'sample_index': sample_index, 'time_s': time if trajectories else None,
                'frame_sha256': sha256((dest/'frame.png').read_bytes()),
                'meaning': 'Recorded sample; no reintegration or interpolation; not teacher acceptance.'}))
    finally:
        plot.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('import'); p.add_argument('source'); p.add_argument('--assignment', required=True); p.add_argument('--store', required=True)
    p = sub.add_parser('reference'); p.add_argument('revision_id'); p.add_argument('--store', required=True)
    p = sub.add_parser('revise'); p.add_argument('proposal'); p.add_argument('--store', required=True)
    p = sub.add_parser('run'); p.add_argument('reference'); p.add_argument('--store', required=True)
    for name in ('investigation', 'analysis', 'presentation', 'output', 'run-id'): p.add_argument('--'+name, required=True)
    p = sub.add_parser('compare'); p.add_argument('left'); p.add_argument('right')
    p = sub.add_parser('view'); p.add_argument('run'); p.add_argument('--presentation'); p.add_argument('--sample-index', type=int, default=0); p.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        if args.command == 'import':
            _, result = ModelStore.import_legacy(args.source, args.assignment, args.store)
        elif args.command == 'reference':
            result = ModelStore(args.store).reference(args.revision_id)
        elif args.command == 'revise':
            result = ModelStore(args.store).revise(args.proposal)
        elif args.command == 'run':
            result = execute(args.store, args.reference, args.investigation, args.analysis,
                             args.presentation, args.output, run_id=args.run_id)
        elif args.command == 'compare':
            result = compare_runs(args.left, args.right)
        else:
            present_run(args.run, presentation_path=args.presentation, sample_index=args.sample_index,
                        screenshot_directory=args.output)
            result = {'presentation': 'completed; not teacher accepted'}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result.get('status') in ('rejected', 'partial', 'no_op') else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'emfeeld model: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
