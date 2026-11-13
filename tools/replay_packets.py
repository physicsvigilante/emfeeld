"""Replay exact authored bytes with explicit statuses and separate reference checks.

This is a deterministic regression runner, not a blind authoring benchmark.
Run from a checkout: python tools/replay_packets.py MANIFEST --output NEW_DIRECTORY
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from emfeeld.observations import load_packet, run_packet
from emfeeld.scene import strict_keys


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _finite_numbers(value):
    if isinstance(value, list):
        if not value:
            raise ValueError('numeric lists must not be empty')
        for item in value:
            _finite_numbers(item)
    else:
        try:
            valid = type(value) in (int, float) and math.isfinite(float(value))
        except (OverflowError, ValueError):
            valid = False
        if not valid:
            raise ValueError('expected finite numbers, not strings or booleans')


def _check_spec(check):
    strict_keys(check, ('id', 'path', 'value', 'atol', 'rtol'), ('id', 'path', 'value'))
    if not isinstance(check['id'], str):
        raise ValueError('check id must be a string')
    if not isinstance(check['path'], list) or not check['path'] or not all(
            isinstance(x, str) and x for x in check['path']):
        raise ValueError('check path must be a nonempty array of keys')
    target = check['value']
    if isinstance(target, (str, bool)):
        if 'atol' in check or 'rtol' in check:
            raise ValueError('text/boolean comparisons do not have tolerances')
    else:
        _finite_numbers(target)
        # Reject ragged shapes before any execution.
        np.asarray(target, dtype=float)
        for key in ('atol', 'rtol'):
            value = check.get(key, 0)
            _finite_numbers(value)
            if isinstance(value, list) or value < 0:
                raise ValueError('tolerances must be nonnegative scalar numbers')


def compare(actual, check):
    expected = check['value']
    if isinstance(expected, (str, bool)):
        return type(actual) is type(expected) and actual == expected
    try:
        _finite_numbers(actual)
        a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
        if a.shape != b.shape:
            return False
        # Reuse the existing overflow-safe authored-reference comparator.
        from emfeeld.observations import Expectation, _comparison
        exp = Expectation(tuple(b.reshape(-1).tolist()),
                          float(check.get('atol', 0)), float(check.get('rtol', 0)))
        return _comparison(a, exp)['passed']
    except (ValueError, TypeError, OverflowError):
        return False


def assess(report, case):
    rows = report.get('results', [])
    by_id = {row.get('id'): row for row in rows}
    required = case['statuses']
    issues = []
    if len(by_id) != len(rows) or set(by_id) != set(required):
        issues.append('missing, duplicate or extra observation ids')
    for ident, status in required.items():
        if by_id.get(ident, {}).get('status') != status:
            issues.append(f'{ident}: expected status {status}')
    comparisons = []
    for check in case['checks']:
        try:
            actual = by_id[check['id']]
            for key in check['path']:
                actual = actual[key]
            passed = compare(actual, check)
        except (KeyError, TypeError):
            passed = False
        comparisons.append({'id': check['id'], 'path': check['path'], 'passed': bool(passed)})
        if not passed:
            issues.append(f"{check['id']}: reference mismatch at {'.'.join(check['path'])}")
    return {'passed': not issues, 'issues': issues, 'checks': comparisons}


def preflight(manifest, root):
    strict_keys(manifest, ('version', 'description', 'cases'), ('version', 'cases'))
    if type(manifest['version']) is not int or manifest['version'] != 1:
        raise ValueError('only replay version 1 is supported')
    if not isinstance(manifest['cases'], list) or not manifest['cases']:
        raise ValueError('cases must be nonempty')
    captured, seen = [], set()
    for case in manifest['cases']:
        strict_keys(case, ('id', 'packet', 'sha256', 'statuses', 'checks', 'rejects'),
                    ('id', 'packet', 'sha256'))
        ident = case['id']
        if not isinstance(ident, str) or re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', ident) is None or ident in seen:
            raise ValueError('case ids must be unique safe names')
        seen.add(ident)
        if not isinstance(case['packet'], str):
            raise ValueError('packet path must be a string')
        path = (root / case['packet']).resolve()
        if Path(case['packet']).is_absolute() or not path.is_relative_to(root.resolve()):
            raise ValueError('packet path must be inside the repository')
        if not isinstance(case['sha256'], str) or re.fullmatch('[0-9a-f]{64}', case['sha256']) is None:
            raise ValueError('a SHA256 of the exact input bytes is required')
        raw = path.read_bytes()
        if digest(raw) != case['sha256']:
            raise ValueError(f'{ident}: input hash mismatch; refusing execution')
        if 'rejects' in case:
            if not isinstance(case['rejects'], str) or not case['rejects'] or 'checks' in case or 'statuses' in case:
                raise ValueError('rejection cases need only a nonempty rejects substring')
        else:
            statuses = case.get('statuses')
            if not isinstance(statuses, dict) or not statuses or not all(
                    isinstance(k, str) and isinstance(v, str) for k, v in statuses.items()):
                raise ValueError('explicit per-observation statuses are required')
            if not isinstance(case.get('checks'), list) or not case['checks']:
                raise ValueError('at least one separate reference check is required')
            for check in case['checks']:
                _check_spec(check)
                if check['id'] not in statuses:
                    raise ValueError('check refers to an undeclared observation')
        captured.append((case, raw))
    return captured


def replay(manifest_path, output, *, root=ROOT):
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = load_packet(manifest_path)
    captured = preflight(manifest, root)
    if Path(manifest_path).read_bytes() != manifest_bytes:
        raise ValueError('manifest changed during preflight')
    # Refuse even an existing empty directory: do not replace a previous attempt.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'manifest.json').write_bytes(manifest_bytes)
    results = []
    for case, raw in captured:
        folder = output / case['id']; folder.mkdir()
        snapshot = folder / 'input.json'; snapshot.write_bytes(raw)
        try:
            report = run_packet(load_packet(snapshot))
        except ValueError as exc:
            accepted = 'rejects' in case and case['rejects'] in str(exc)
            assessment = {'passed': accepted, 'issues': [] if accepted else [str(exc)], 'checks': []}
            report = {'schema_error': str(exc)}
        else:
            assessment = ({'passed': False, 'issues': ['expected schema rejection did not occur'], 'checks': []}
                          if 'rejects' in case else assess(report, case))
        (folder / 'result.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        results.append({'id': case['id'], 'sha256': digest(raw), **assessment})
    summary = {'description': 'Regression of declared outputs, not proof of original problem-solving or independent review',
               'passed': all(r['passed'] for r in results), 'cases': results,
               'engine_sha256': {p.name: digest(p.read_bytes()) for p in sorted((root/'src/emfeeld').glob('*.py'))}}
    (output/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = replay(args.manifest, args.output)
    except (OSError, ValueError) as exc:
        print(f'replay: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'passed': summary['passed'], 'cases': len(summary['cases'])}))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
