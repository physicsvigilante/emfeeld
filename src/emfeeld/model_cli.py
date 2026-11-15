"""Convenience CLI over the existing immutable-model and recorded-run interfaces.

Apply a native proposal, reuse explicitly identified run settings, calculate fresh
results, and optionally present the recorded run. No second revision engine,
implicit latest reference, automatic migration, or new physical law is introduced.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

from . import model_runs
from .model_revisions import (ModelStore, RevisionError, check_reference, decode,
                              encode, identifier, put, sha256)

SETTINGS = ('investigation.json', 'analysis.json', 'presentation.json')
LEGACY_COMMANDS = ('import', 'reference', 'revise', 'run', 'compare', 'view')


def _settings(using: Path, store: ModelStore) -> tuple[dict[str, bytes], dict]:
    """Capture settings from a sealed run, without trusting a mutable file name."""
    integrity = (using / 'integrity.json').read_bytes()
    inventory = decode(integrity)['files']
    run, _, summary, native = model_runs.inspect_run(using)
    if summary['status'] not in ('complete', 'partial') or native is None:
        raise RevisionError('invalid_template', '--using needs a completed native run, not a rejected/pending attempt')
    if run['root_reference'] != store.info['root']:
        raise RevisionError('wrong_model', '--using belongs to another model root')
    store.read(run['root_reference'])
    store.read(run['reference'])
    raw = {name: (using / name).read_bytes() for name in SETTINGS}
    if (any(sha256(b) != inventory.get(name) for name, b in raw.items())
            or (using / 'integrity.json').read_bytes() != integrity):
        raise RevisionError('input_changed', 'run settings changed during capture')
    return raw, {'run_id': run['run_id'], 'reference': run['reference'],
                 'root_reference': run['root_reference'],
                 'integrity_sha256': sha256(integrity),
                 'settings_sha256': {n: sha256(b) for n, b in raw.items()},
                 'reuse': 'settings only; fresh calculations, no inherited numerical pass'}


def _finish(output: Path, outcome: dict) -> dict:
    # Each attempt is a new directory; final outcome is never overwritten.
    put(output / 'outcome.json', encode(outcome))
    lines = ['# Native revision-and-view attempt', '',
             f"Status: **{outcome['status']}**", '',
             'The exact proposal and reused settings are retained in inputs/.',
             'A native accepted revision is construction-valid, not a numerical certification.',
             'No source facts, launch conditions, tolerances or requested measurements were silently changed.', '']
    decision = outcome.get('decision', {})
    lines += [f"Revision decision: {decision.get('status', 'not available')}"]
    if decision.get('reference'):
        lines += [f"Model: {decision['reference']['model_id']}",
                  f"Revision: {decision['reference']['revision_id']}"]
    calculation = outcome.get('calculation', {})
    if calculation:
        lines += ['', f"Calculation: {calculation['status']}",
                  f"Unfulfilled requests: {calculation.get('unfulfilled_requests', {})}",
                  'Full numerical evidence is in run/; that directory remains sealed.']
    presentation = outcome.get('presentation', {})
    lines += ['', f"Presentation: {presentation.get('status', 'not_requested')}"]
    if presentation.get('reason'):
        lines += [str(presentation['reason'])]
    lines += ['', 'A scenario change is not a physical transition in time.',
              'Interpretation fidelity, numerical checks, coverage and teacher usefulness remain separate.',
              'Textbook-answer completeness is optional. This run is not independent review.', '']
    put(output / 'REPORT.md', '\n'.join(lines).encode('utf-8'))
    return outcome


def apply_revision(proposal_path: str | Path, *, store_path: str | Path,
                   using: str | Path, output: str | Path,
                   run_id: str | None = None, view: bool = False,
                   render: bool = False, sample_index: int = 0,
                   presentation_path: str | Path | None = None) -> dict[str, Any]:
    """Compose native revise -> execute -> present; retain every stage separately.

    Expected proposal/analysis failures return an explicit outcome. Unexpected
    backend exceptions propagate and leave a started attempt, not a false pass.
    Accepted physical revisions are not rolled back when calculation/view fails.
    """
    if type(view) is not bool or type(render) is not bool or (view and render):
        raise ValueError('choose at most one of view and render')
    if type(sample_index) is not int or sample_index < 0 or (sample_index and not render):
        raise ValueError('a nonzero sample_index is supported only for rendered snapshots')
    run_id = identifier(run_id if run_id is not None else 'apply-' + uuid4().hex)
    proposal_path, using = Path(proposal_path), Path(using)
    store_path, output = Path(store_path), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('output must be a new directory; previous attempts are never overwritten')
    for protected in (store_path, using):
        if output.resolve().is_relative_to(protected.resolve()):
            raise ValueError('output must be outside the model store and the sealed --using run')
    if not (store_path / 'model.json').is_file():
        raise ValueError('a native model store is required; portable classroom-model stores need explicit import, not in-place conversion')
    raw_proposal = proposal_path.read_bytes()
    proposal = decode(raw_proposal)
    if (not isinstance(proposal, dict) or type(proposal.get('proposal_version')) is not int
            or proposal['proposal_version'] not in (1, 2)):
        raise ValueError('a native proposal_version 1 or 2 document is required; portable helper revisions are not auto-converted')
    for name in ('proposal_id', 'revision_id'):
        identifier(proposal.get(name))
    check_reference(proposal.get('parent'))
    try:
        store = ModelStore(store_path)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('invalid native model store; portable helper stores require explicit import') from exc
    settings, binding = _settings(using, store)
    if presentation_path is not None:
        replacement = Path(presentation_path).read_bytes()
        decode(replacement)  # capture once; full membership validation uses descendant
        binding['explicit_overrides'] = {'presentation.json': {
            'source': str(presentation_path), 'sha256': sha256(replacement),
            'replaces_sha256': binding['settings_sha256']['presentation.json']}}
        settings['presentation.json'] = replacement
    analysis = decode(settings['analysis.json'])
    if sample_index >= (analysis.get('samples', 1) if analysis['mode'] == 'trajectory' else 1):
        raise ValueError('sample_index must select an existing saved sample')
    # Reserve the attempt before mutating the store, including rejected proposals.
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / 'inputs'; inputs.mkdir()
    for name, raw in {**settings, 'proposal.json': raw_proposal}.items():
        put(inputs / name, raw)
    put(inputs / 'template.json', encode(binding))
    put(output / 'started.json', encode({
        'workflow_version': 1, 'status': 'started', 'run_id': run_id,
        'input_sha256': {p.name: sha256(p.read_bytes()) for p in sorted(inputs.iterdir())},
        'view_requested': view, 'render_requested': render, 'sample_index': sample_index,
        'meaning': 'Only outcome.json completes this attempt; never infer success from accepted revision alone.'}))
    # Reuse the existing native engine, using the captured proposal, never reread
    # the author's original path after preflight.
    decision = store.revise(inputs / 'proposal.json')
    put(output / 'decision.json', encode(decision))
    outcome: dict[str, Any] = {
        'workflow_version': 1, 'status': 'rejected', 'output': str(output),
        'decision': decision, 'presentation': {'status': 'not_requested'},
        'settings_from': binding, 'verification': 'native checks, not independent source/correctness review'}
    if decision['status'] != 'accepted':
        outcome['status'] = decision['status']
        return _finish(output, outcome)
    reference = output / 'reference.json'
    put(reference, encode(decision['reference']))
    calculation = model_runs.execute(
        store_path, reference, inputs / 'investigation.json', inputs / 'analysis.json',
        inputs / 'presentation.json', output / 'run', run_id=run_id)
    put(output / 'calculation.json', encode(calculation))
    outcome.update(status='complete' if calculation['execution_complete'] else 'incomplete',
                   calculation=calculation, recorded_run=str(output / 'run'))
    if view or render:
        outcome['presentation'] = {'status': 'blocked', 'reason': 'requested calculations or full-scene checks did not succeed'}
        if calculation['execution_complete']:
            if not calculation.get('render_ready', False):
                outcome.update(status='presentation_unavailable')
                outcome['presentation'] = {'status': 'unavailable',
                    'reason': 'This analysis has no complete recorded scene; static values remain available. No extra motion was simulated.'}
            else:
                try:
                    model_runs.present_run(output / 'run', sample_index=sample_index,
                        screenshot_directory=output / 'presentation' if render else None)
                except (ValueError, OSError, RuntimeError, ImportError) as exc:
                    outcome['status'] = 'presentation_failed'
                    outcome['presentation'] = {'status': 'failed', 'reason': str(exc),
                        'meaning': 'calculation results are retained; no physics retry or tolerance change'}
                else:
                    outcome['presentation'] = {
                        'status': 'rendered' if render else 'opened_and_closed',
                        'meaning': 'recorded result; not teacher acceptance or independent review'}
    return _finish(output, outcome)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in LEGACY_COMMANDS:
        return model_runs.main(args)
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='Existing import, reference, revise, run, compare and view commands are also available here with their unchanged arguments.')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('apply', help='apply a native revision, calculate with recorded settings, optionally view')
    p.add_argument('proposal', type=Path)
    p.add_argument('--store', required=True, type=Path)
    p.add_argument('--using', required=True, type=Path, help='sealed native run supplying explicit investigation/analysis/presentation settings')
    p.add_argument('--output', required=True, type=Path, help='new attempt directory outside model store and prior run')
    p.add_argument('--presentation', type=Path, help='explicit replacement presentation; inherited entity IDs are never silently repaired')
    p.add_argument('--run-id', help='optional safe identifier; otherwise a fresh run ID is generated')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--view', action='store_true', help='open recorded interactive view after successful calculation')
    group.add_argument('--render', action='store_true', help='export recorded snapshot instead of opening a desktop window')
    p.add_argument('--sample-index', type=int, default=0, help='snapshot sample; nonzero values require --render')
    a = parser.parse_args(args)
    try:
        result = apply_revision(a.proposal, store_path=a.store, using=a.using, output=a.output,
                                run_id=a.run_id, view=a.view, render=a.render, sample_index=a.sample_index,
                                presentation_path=a.presentation)
    except (ValueError, OSError) as exc:
        print(f'emfeeld model apply: {exc}', file=sys.stderr)
        return 2
    print(encode(result).decode('utf-8'), end='')
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
