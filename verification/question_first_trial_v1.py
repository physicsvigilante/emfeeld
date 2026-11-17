"""Source-first trial admission for an externally reviewable question-to-evidence attempt.

Commands:
  python verification/question_first_trial_v1.py freeze QUESTION.json --output NEW_LOCK
  python verification/question_first_trial_v1.py assess LOCK --packet PACKET.json --output NEW_RUN

This wrapper verifies original question bytes, requested observation coverage and
native statuses/units. It cannot verify that original prose was interpreted
faithfully or that authored numerical results are physically correct. No viewer,
new solver or arbitrary answer/evaluation code is introduced.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any
from emfeeld.output_safety import protect_saved_evidence

from emfeeld.observations import packet_from_dict, run_packet
from emfeeld.scene import strict_keys

QUESTION_LIMIT = 128 * 1024
PACKET_LIMIT = 2 * 1024 * 1024
ID_RE = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')
ORIGINS = ('developer_authored', 'external_unverified')
SUPPORTED_REQUIREMENTS = frozenset(('fixed_prescribed_sources',
                                    'independent_nonrelativistic_test_particles'))
QUESTION_KEYS = ('trial_version', 'id', 'source', 'givens', 'assumptions',
                 'illustrative_choices', 'unresolved_information',
                 'requirements', 'requested_measurements')


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _read_raw(path: Path, maximum: int) -> bytes:
    # Read exactly once. Every subsequent parsing and retained evidence copy
    # uses these exact captured bytes, not a second read of a moving input.
    with path.open('rb') as handle:
        raw = handle.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('input exceeds the bounded UTF-8 document size')
    return raw


def _parse_json(raw: bytes) -> Any:
    def no_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def no_nonfinite(token):
        raise ValueError(f'nonfinite JSON token: {token}')

    return json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicate_keys,
                      parse_constant=no_nonfinite)


def _string(value: Any, name: str, *, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name} must be nonempty text (maximum {maximum} characters)')
    return value


def _string_list(value: Any, name: str, *, count: int = 32) -> list[str]:
    if not isinstance(value, list) or len(value) > count:
        raise ValueError(f'{name} must be a bounded list of strings')
    return [_string(item, name + '[]') for item in value]


def _number(value: Any, name: str, *, nonnegative: bool = False) -> float:
    import math
    if type(value) not in (int, float):
        raise ValueError(f'{name} must be a finite JSON number')
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be representable as finite float64') from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f'{name} must be finite' + (' and nonnegative' if nonnegative else ''))
    return result



def _same_saved_time(measured: Any, target: Any, *, duration_s: float, samples: int) -> bool:
    """Compare an actual native saved time to its original requested instant.

    Floating-point representation can differ by one ULP (e.g., a decimal
    requested time versus an evenly spaced saved grid). A physical difference
    of even 1e-13 s is NOT generally negligible; the old 1e-12 s absolute
    tolerance could silently accept the wrong sampled instant.
    """
    import math
    try:
        actual = _number(measured, 'native saved time', nonnegative=True)
        requested = _number(target, 'frozen saved time', nonnegative=True)
    except ValueError:
        return False
    if actual == requested:
        return True
    if actual == 0 or requested == 0:
        return False
    spacing = duration_s / (samples - 1)
    difference = abs(actual - requested)
    return (math.isfinite(spacing) and spacing > 0
            and difference <= min(math.ulp(actual), math.ulp(requested))
            and difference < spacing / 4)


def _three_vector(value: Any, name: str) -> None:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f'{name} must be a vector of three finite SI numbers')
    for i, element in enumerate(value):
        _number(element, f'{name}[{i}]')


def _question_context(context: Any) -> None:
    # Exact whitelist prevents accidental interpretation of arbitrary claimed
    # context as native verification. Request type determines required fields.
    if not isinstance(context, dict) or not context:
        raise ValueError('requested context must be a nonempty mapping')
    strict_keys(context, ('position_m', 'from_m', 'to_m', 'particle_index',
                          'sample_index', 'time_s', 'convention'))
    for key in ('position_m', 'from_m', 'to_m'):
        if key in context:
            _three_vector(context[key], 'context.' + key)
    for key in ('particle_index', 'sample_index'):
        if key in context and (type(context[key]) is not int or context[key] < 0):
            raise ValueError(f'context.{key} must be a nonnegative JSON integer')
    if 'time_s' in context:
        _number(context['time_s'], 'context.time_s', nonnegative=True)
    if 'convention' in context and context['convention'] != 'potential(to_m) - potential(from_m)':
        raise ValueError('unknown ordered potential-difference convention')


def _validate_question(data: Any) -> dict:
    strict_keys(data, QUESTION_KEYS, QUESTION_KEYS)
    if type(data['trial_version']) is not int or data['trial_version'] != 1:
        raise ValueError('only question-first trial_version 1 is supported')
    if not isinstance(data['id'], str) or ID_RE.fullmatch(data['id']) is None:
        raise ValueError('trial id is not a safe identifier')
    src = data['source']
    strict_keys(src, ('origin', 'label', 'question'), ('origin', 'label', 'question'))
    if src['origin'] not in ORIGINS or not isinstance(src['origin'], str):
        raise ValueError('source origin must be developer_authored or external_unverified')
    _string(src['label'], 'source.label', maximum=256)
    _string(src['question'], 'source.question', maximum=8192)
    for field in ('givens', 'assumptions', 'illustrative_choices',
                  'unresolved_information', 'requirements'):
        _string_list(data[field], field)
    if len(data['requirements']) != len(set(data['requirements'])):
        raise ValueError('duplicate declared physics requirement')
    requested = data['requested_measurements']
    if not isinstance(requested, list) or not 1 <= len(requested) <= 32:
        raise ValueError('requested_measurements must contain 1–32 declarations')
    ids = set()
    for row in requested:
        strict_keys(row, ('id', 'quantity', 'unit', 'context', 'native_type', 'native_quantity'),
                    ('id', 'quantity', 'unit', 'context', 'native_type'))
        ident = row['id']
        if not isinstance(ident, str) or ID_RE.fullmatch(ident) is None or ident in ids:
            raise ValueError('requested observation IDs must be safe and unique')
        ids.add(ident)
        _string(row['quantity'], 'requested quantity', maximum=128)
        _string(row['unit'], 'requested unit', maximum=32)
        if row['native_type'] not in ('field', 'potential', 'force',
                                      'potential_difference', 'trajectory_sample'):
            raise ValueError('unsupported declared native observation type')
        if row['native_type'] == 'trajectory_sample':
            if row.get('native_quantity') not in ('time', 'position', 'velocity', 'speed',
                                                  'kinetic_energy', 'potential_energy', 'total_energy'):
                raise ValueError('trajectory sample needs a declared native quantity')
        elif 'native_quantity' in row:
            raise ValueError('static request cannot declare trajectory quantity')
        _question_context(row['context'])
    return data


def _receipt(raw: bytes, question: dict) -> dict:
    return {
        'receipt_version': 1,
        'question_sha256': _sha(raw),
        'trial_id': question['id'],
        'declared_origin': question['source']['origin'],
        'requested_ids': [r['id'] for r in question['requested_measurements']],
        'source_authenticity': 'not_authenticated',
        'physical_interpretation': 'not_verified',
        'meaning': 'Local byte checkpoint only; not a timestamped, independent or teacher-certified source',
    }


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def freeze(question_path: Path, output: Path) -> dict:
    protect_saved_evidence(output, new_directory=True)
    raw = _read_raw(question_path, QUESTION_LIMIT)
    question = _validate_question(_parse_json(raw))
    receipt = _receipt(raw, question)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'question.json').write_bytes(raw)
    (output / 'receipt.json').write_bytes(_json_bytes(receipt))
    return receipt


def _load_frozen(lock: Path) -> tuple[bytes, bytes, dict, dict]:
    raw = _read_raw(lock / 'question.json', QUESTION_LIMIT)
    receipt_bytes = _read_raw(lock / 'receipt.json', QUESTION_LIMIT)
    question = _validate_question(_parse_json(raw))
    receipt = _parse_json(receipt_bytes)
    if receipt != _receipt(raw, question):
        raise ValueError('frozen question receipt and exact input bytes disagree')
    return raw, receipt_bytes, question, receipt


def _eligible(question: dict) -> None:
    unresolved = question['unresolved_information']
    if unresolved:
        raise ValueError('question declares unresolved source information; no simulation may be accepted')
    unsupported = set(question['requirements']) - SUPPORTED_REQUIREMENTS
    if unsupported:
        raise ValueError('unsupported declared physics requirements: ' + ', '.join(sorted(unsupported)))


def _validate_packet(packet: dict, question: dict) -> None:
    # Existing native validator remains the sole authority for physics grammar.
    packet_from_dict(packet)
    requests = packet['observations']
    # Requested question quantities must be explicitly accounted for by exactly
    # one native request each. No silent drops or answer substitutions.
    submitted = [r['id'] for r in requests]
    required = [r['id'] for r in question['requested_measurements']]
    if len(submitted) != len(required) or set(submitted) != set(required):
        raise ValueError('native observation IDs do not exactly cover the frozen question')
    if any('expectation' in r for r in requests):
        raise ValueError('authored answers/expectations must remain outside the native packet')
    declarations = {r['id']: r for r in question['requested_measurements']}
    for request in requests:
        declared = declarations[request['id']]
        context = declared['context']
        kind = request['type']
        if kind != declared['native_type'] or (
            kind == 'trajectory_sample' and request.get('quantity') != declared['native_quantity']):
            raise ValueError(request['id'] + ': native quantity/type differs from frozen question')
        if kind in ('field', 'potential', 'force'):
            if set(context) != {'position_m'} or context['position_m'] != request['position_m']:
                raise ValueError(request['id'] + ': world-point context differs from frozen request')
        elif kind == 'potential_difference':
            if set(context) != {'from_m', 'to_m', 'convention'} or (
                context['from_m'] != request['from_m'] or context['to_m'] != request['to_m']):
                raise ValueError(request['id'] + ': ordered potential endpoints differ from frozen request')
        elif kind == 'trajectory_sample':
            # Deliberately bounded V1: saved index with explicit actual time.
            # Native execution later verifies the physical saved time; no
            # nearest-time remapping or event-state reinterpretation is allowed.
            if (set(context) != {'particle_index', 'sample_index', 'time_s'} or
                'sample_index' not in request or
                context['particle_index'] != request['particle_index'] or
                context['sample_index'] != request['sample_index']):
                raise ValueError(request['id'] + ': saved-state context differs from frozen request')
        else:
            raise ValueError('question-first V1 supports only static probes and saved-index trajectory samples')


def _safe_output(output: Path, lock: Path, packet_path: Path) -> None:
    protect_saved_evidence(output, new_directory=True)
    if output.exists() or output.is_symlink():
        raise FileExistsError('output directory already exists; evidence is never overwritten')
    new_root = output.resolve()
    frozen_root = lock.resolve()
    if new_root == frozen_root or new_root.is_relative_to(frozen_root):
        raise ValueError('output cannot be inside the immutable question checkpoint')
    if new_root == packet_path.resolve():
        raise ValueError('output aliases the authored packet')


def assess(lock: Path, packet_path: Path, output: Path) -> dict:
    frozen, receipt_raw, question, receipt = _load_frozen(lock)
    _eligible(question)
    packet_raw = _read_raw(packet_path, PACKET_LIMIT)
    packet = _parse_json(packet_raw)
    _validate_packet(packet, question)
    _safe_output(output, lock, packet_path)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'question.json').write_bytes(frozen)
    (output / 'receipt.json').write_bytes(receipt_raw)
    (output / 'packet.json').write_bytes(packet_raw)
    # An interrupted attempt stays inspectably incomplete. The question and
    # packet originals persist; no success is asserted on an exception.
    (output / 'state.json').write_bytes(_json_bytes({'execution_complete': False}))

    native = run_packet(packet)
    if native['input'] != packet:
        raise RuntimeError('native execution returned a different input packet')
    (output / 'native-result.json').write_bytes(_json_bytes(native))
    results = native['results']
    by_id = {r['id']: r for r in results}
    issues = []
    for expected in question['requested_measurements']:
        actual = by_id.get(expected['id'])
        if actual is None:
            issues.append(expected['id'] + ': missing native result')
            continue
        if actual['status'] != 'ok':
            issues.append(expected['id'] + ': native status ' + actual['status'])
        if actual.get('type') != expected['native_type'] or (
            expected['native_type'] == 'trajectory_sample' and
            actual.get('quantity') != expected['native_quantity']):
            issues.append(expected['id'] + ': native reported quantity/type changed')
        if actual.get('unit') != expected['unit']:
            issues.append(expected['id'] + ': expected unit ' + expected['unit'])
        # Independent of numerical value/status, ensure the original question's
        # world position, ordered endpoints and physical saved time were really
        # the positions/times that the native computation actually reported.
        for key, target in expected['context'].items():
            measured = actual.get(key)
            if key == 'time_s':
                scene = packet['scene']
                if not _same_saved_time(measured, target,
                                        duration_s=scene['duration_s'],
                                        samples=scene.get('samples', 401)):
                    issues.append(expected['id'] + ': actual saved time disagrees with frozen context')
            elif measured != target:
                issues.append(expected['id'] + ': context mismatch for ' + key)
        if actual.get('check', {}).get('passed') is False:
            issues.append(expected['id'] + ': failed native authored expectation')
    if len(results) != len(by_id) or set(by_id) != set(r['id'] for r in question['requested_measurements']):
        issues.append('extra, duplicate or absent native results')
    if native['status'] != 'ok':
        issues.append('native packet aggregate status ' + native['status'])
    evidence = {
        'assessment_version': 1,
        'trial_id': question['id'],
        'frozen_question_sha256': receipt['question_sha256'],
        'authored_packet_sha256': _sha(packet_raw),
        'native_report_sha256': _sha((output / 'native-result.json').read_bytes()),
        'native_measurement_coverage': 'complete' if not issues else 'incomplete',
        'issues': issues,
        'requested_observations': len(question['requested_measurements']),
        'original_declared_source_origin': question['source']['origin'],
        'interpretation_fidelity': 'not_verified',
        'independent_physics_correctness': 'not_evaluated',
        'educational_usefulness': 'not_evaluated',
        'textbook_answer_completeness': 'not_evaluated',
        'limits': 'Source checkpoint and structural coverage are not an authenticated chronology, independent reference, blind teacher test or proof of physical interpretation',
    }
    (output / 'assessment.json').write_bytes(_json_bytes(evidence))
    (output / 'state.json').write_bytes(_json_bytes({'execution_complete': True,
                                                      'native_measurement_coverage': evidence['native_measurement_coverage']}))
    return evidence


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest='command', required=True)
    first = sub.add_parser('freeze', help='checkpoint source question bytes before authoring')
    first.add_argument('question', type=Path)
    first.add_argument('--output', required=True, type=Path)
    final = sub.add_parser('assess', help='check frozen source and exact native observation coverage')
    final.add_argument('lock', type=Path)
    final.add_argument('--packet', type=Path, required=True)
    final.add_argument('--output', required=True, type=Path)
    args = cli.parse_args(argv)
    try:
        if args.command == 'freeze':
            report = freeze(args.question, args.output)
        else:
            report = assess(args.lock, args.packet, args.output)
    except (ValueError, OSError, OverflowError) as exc:
        print(f'question-first trial: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))
    return 0 if args.command == 'freeze' or report['native_measurement_coverage'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
