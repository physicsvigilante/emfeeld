"""Bounded one-property investigation sweeps over existing native model APIs.

No new physics, solver, model format, implicit latest, interpolation or display.
Each hypothesis is an immutable sibling of one exactly pinned model revision.
"""
from __future__ import annotations

import argparse
import math
from copy import deepcopy
from pathlib import Path
import sys

from . import model_runs
from .model_cli import _settings
from .model_revisions import (INTENTS, ModelStore, RevisionError, check_reference,
                              decode, encode, exact_keys, identifier, put, sha256)

LIMIT = 8


def _inventory(folder: Path):
    return {p.relative_to(folder).as_posix(): sha256(p.read_bytes())
            for p in sorted(folder.rglob('*'))
            if p.is_file() and p != folder / 'integrity.json'}


def _same_value(a, b):
    """Physical equality, excluding bool, while not relying on JSON formatting."""
    if type(a) in (int, float) and type(b) in (int, float):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_value(x, y) for x, y in zip(a, b))
    return False


def validate_spec(spec, parent):
    exact_keys(spec, ('sweep_version', 'id', 'parent', 'target_id', 'expected_role',
                      'category', 'property', 'expected_value', 'values',
                      'scenario_intent', 'provenance'))
    if type(spec['sweep_version']) is not int or spec['sweep_version'] != 1:
        raise ValueError('only sweep_version 1 is supported')
    identifier(spec['id']); identifier(spec['target_id'])
    # The generated native proposal/revision/run IDs must retain their safe length.
    if len(spec['id']) > 39:
        raise ValueError('sweep ID must be at most 39 characters for safe member identities')
    check_reference(spec['parent'])
    if spec['scenario_intent'] not in INTENTS or spec['scenario_intent'] not in ('teacher_hypothesis', 'illustrative_exploration'):
        raise ValueError('sweeps must have an explicit hypothetical/illustrative scenario intent')
    exact_keys(spec['provenance'], ('origin', 'reason', 'evidence'))
    if spec['provenance']['origin'] not in ('adopted_assumption', 'illustrative_choice', 'supplied_fact'):
        raise ValueError('sweep values must be labelled as an explicit authored assumption, choice or fact')
    for key in ('reason', 'evidence'):
        if not isinstance(spec['provenance'][key], str) or not spec['provenance'][key].strip():
            raise ValueError('sweep provenance requires a nonempty reason and evidence')
    row = parent['entities'].get(spec['target_id'])
    if row is None or row['role'] != spec['expected_role']:
        raise RevisionError('wrong_role', 'sweep target must be a pre-existing physical ID with the asserted role')
    field = spec['property']
    if not isinstance(field, str) or field not in row['properties']:
        raise RevisionError('unknown_property', 'sweep property must exist in the pinned parent')
    actual = row['properties'][field]
    if not _same_value(actual, spec['expected_value']):
        raise RevisionError('old_value_mismatch', 'expected sweep baseline value does not match the pinned parent')
    # Type/shape preflight checks protect the meaning of "one complete property";
    # the existing revision parser remains authoritative for physical admissibility.
    values = spec['values']
    if not isinstance(values, list) or not 1 <= len(values) <= LIMIT:
        raise ValueError('1..8 explicit non-baseline sweep values are required')
    for index, value in enumerate(values):
        def shape_matches(x, y):
            if type(x) in (float, int):
                return type(y) in (float, int)
            if isinstance(x, list) and isinstance(y, list):
                return len(x) == len(y) and all(shape_matches(a, b) for a,b in zip(x,y))
            return False
        if not shape_matches(actual, value):
            raise ValueError(f'sweep member {index}: invalid property shape or type')
        def finite(x):
            return all(finite(z) for z in x) if isinstance(x, list) else type(x) in (int, float) and math.isfinite(x)
        if not finite(value):
            raise ValueError(f'sweep member {index}: finite physical values are required')
        if _same_value(actual, value) or any(_same_value(value, prior) for prior in values[:index]):
            raise ValueError('sweep values must be distinct from one another and the baseline')
    return actual


def _member_id(sweep_id, index):
    return f'sweep-{sweep_id}-{index:02d}'


def run_sweep(spec_path, *, store_path, using, output):
    """Run a bounded authored sweep; retain rejected/partial results memberwise.

    Unexpected computation failure preserves a pending attempt, not a false pass.
    """
    spec_path, store_path, using, output = map(Path, (spec_path, store_path, using, output))
    if output.exists() or output.is_symlink():
        raise FileExistsError('sweep output must be a new directory')
    for protected in (store_path, using):
        if output.resolve().is_relative_to(protected.resolve()):
            raise ValueError('sweep output must be outside store and template run')
    raw_spec = spec_path.read_bytes()
    spec = decode(raw_spec)
    if not isinstance(spec, dict): raise ValueError('sweep must be a JSON object')
    store = ModelStore(store_path)
    parent, _ = store.read(spec['parent'])
    validate_spec(spec, parent)
    captured, template = _settings(using, store)
    native, revision, summary, _ = model_runs.inspect_run(using, expected_reference=spec['parent'])
    if not summary.get('execution_complete') or native['reference'] != spec['parent']:
        raise RevisionError('invalid_template', 'the sealed template must be a complete run of this exact parent')
    # Reject collision preflight before output or any mutation. Incomplete attempts
    # also consume identities and must never be overwritten or silently retried.
    for i in range(1, len(spec['values']) + 1):
        ident = _member_id(spec['id'], i)
        if (store._directory(ident).exists() or
                (store.path / 'proposals' / sha256(ident.encode())).exists()):
            raise RevisionError('identity_conflict', f'sweep member identity already reserved: {ident}')
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / 'inputs'; inputs.mkdir()
    put(inputs / 'sweep.json', raw_spec)
    put(inputs / 'template.json', encode(template))
    for name, b in captured.items(): put(inputs / name, b)
    put(output / 'started.json', encode({'status': 'started', 'sweep_version': 1,
        'input_sha256': {p.name: sha256(p.read_bytes()) for p in inputs.iterdir()},
        'meaning': 'A completed summary and inventory, not this started marker, establishes completion.'}))
    ref_path = output / 'parent.reference.json'; put(ref_path, encode(spec['parent']))
    base_dir = output / 'baseline'
    baseline = model_runs.execute(store.path, ref_path, inputs/'investigation.json',
        inputs/'analysis.json', inputs/'presentation.json', base_dir,
        run_id=_member_id(spec['id'], 0))
    report = {'sweep_version': 1, 'id': spec['id'], 'parent': spec['parent'],
              'target_id': spec['target_id'], 'property': spec['property'],
              'expected_value': spec['expected_value'], 'template': template,
              'baseline': {'status': baseline['status'], 'path': 'baseline',
                           'reference': spec['parent']},
              'members': [], 'status': 'started',
              'scope': 'separate stationary prescribed scenarios, not time evolution between variants',
              'verification': 'existing native numerical checks; no independent review or classroom claim'}
    if baseline['execution_complete']:
        model_runs.inspect_run(base_dir, expected_reference=spec['parent'])
        for i, value in enumerate(spec['values'], start=1):
            ident = _member_id(spec['id'], i)
            member_dir = output / f'member-{i:02d}'; member_dir.mkdir()
            proposal = {'proposal_version': 1, 'proposal_id': ident,
                        'revision_id': ident, 'parent': spec['parent'],
                        'category': spec['category'], 'target_id': spec['target_id'],
                        'expected_role': spec['expected_role'], 'property': spec['property'],
                        'expected_value': deepcopy(spec['expected_value']),
                        'value': deepcopy(value), 'scenario_intent': spec['scenario_intent'],
                        'provenance': deepcopy(spec['provenance'])}
            path = member_dir / 'proposal.json'; put(path, encode(proposal))
            decision = store.revise(path)
            put(member_dir / 'decision.json', encode(decision))
            row = {'index': i, 'value': value, 'revision_id': ident,
                   'proposal_sha256': sha256(path.read_bytes()),
                   'decision': decision['status'], 'status': 'rejected',
                   'reference': decision.get('reference')}
            if decision['status'] != 'accepted':
                row['reason'] = decision.get('reason', 'native revision rejected')
            else:
                ref = member_dir / 'reference.json'; put(ref, encode(decision['reference']))
                child_dir = member_dir / 'run'
                calculated = model_runs.execute(store.path, ref, inputs/'investigation.json',
                    inputs/'analysis.json', inputs/'presentation.json', child_dir,
                    run_id=ident)
                row['status'] = 'complete' if calculated['execution_complete'] else 'partial'
                row['run_path'] = str(child_dir.relative_to(output))
                row['request_statuses'] = calculated.get('request_statuses', {})
                row['unfulfilled_requests'] = calculated.get('unfulfilled_requests', {})
                if calculated['execution_complete']:
                    model_runs.inspect_run(child_dir, expected_reference=decision['reference'])
                    comparison = model_runs.compare_runs(base_dir, child_dir)
                    put(member_dir / 'comparison.json', encode(comparison))
                    row['comparison_path'] = str((member_dir / 'comparison.json').relative_to(output))
                    if any(m['comparison'] in ('not_available', 'different_sample_times')
                           for m in comparison['measurements']):
                        row['status'] = 'partial'
                        row['reason'] = 'native comparison unavailable for at least one observation'
            report['members'].append(row)
    else:
        report['reason'] = 'fresh baseline was incomplete; no hypotheses executed'
    report['status'] = ('complete' if baseline['execution_complete'] and
                        all(m['status'] == 'complete' for m in report['members']) else 'partial')
    put(output / 'summary.json', encode(report))
    lines = ['# Bounded native investigation sweep', '',
             f"Sweep: {spec['id']}", f"Status: {report['status']}",
             f"Parent: {spec['parent']}",
             f"Property: {spec['target_id']}.{spec['property']}",
             'All members are distinct hypotheses, not physical transitions.',
             'Comparisons are native matched-time observations only; no invented quantities.',
             'Failures are retained and omitted values never mean zero.',
             'See summary.json and sealed run directories for evidence.', '']
    put(output / 'REPORT.md', '\n'.join(lines).encode())
    put(output / 'integrity.json', encode({'files': _inventory(output)}))
    return report


def inspect_sweep(output):
    """Verify the captured sweep and all complete native runs without executing physics."""
    output = Path(output)
    saved = decode((output/'integrity.json').read_bytes())
    if saved.get('files') != _inventory(output):
        raise RevisionError('sweep_integrity', 'sweep artifact changed or has missing/extra files')
    report = decode((output/'summary.json').read_bytes())
    raw = (output/'inputs/sweep.json').read_bytes()
    if decode(raw)['parent'] != report['parent']:
        raise RevisionError('sweep_integrity', 'sweep input differs from captured parent')
    if report['baseline']['status'] == 'complete':
        model_runs.inspect_run(output/'baseline', expected_reference=report['parent'])
    for member in report['members']:
        if member.get('run_path'):
            model_runs.inspect_run(output/member['run_path'], expected_reference=member['reference'])
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('run', 'inspect'))
    p.add_argument('spec_or_output')
    p.add_argument('--store')
    p.add_argument('--using')
    p.add_argument('--output')
    args = p.parse_args(argv)
    try:
        if args.command == 'inspect':
            if any((args.store, args.using, args.output)):
                raise ValueError('inspect accepts only the completed sweep directory')
            result = inspect_sweep(args.spec_or_output)
        else:
            if not all((args.store, args.using, args.output)):
                raise ValueError('run requires --store, --using and --output')
            result = run_sweep(args.spec_or_output, store_path=args.store, using=args.using, output=args.output)
        print(encode(result).decode(), end='')
        return 0 if result['status'] == 'complete' else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'emfeeld sweeps: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
