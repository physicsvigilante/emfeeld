"""Read-only, development-authored teaching-transfer pilot over sealed E1/G1/T1.

This is *not* an interpreter for arbitrary natural-language questions and not a
second physics/comparison engine. The original run/ensemble inspectors remain
sole scientific evidence authorities. Results go only to stdout as JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import stat
import sys
import tempfile
import zipfile

from emfeeld.scenario_ensembles import read_ensemble_measurements

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / 'pilots' / 'teacher_transfer_v1' / 'questions.json'
FILE_LIMIT = 50 * 1024 * 1024
TOTAL_LIMIT = 200 * 1024 * 1024
ENTRY_LIMIT = 10_000


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _frozen_fixture(path: pathlib.Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    _require(len(raw) < 256_000, 'pilot fixture too large')
    fixture = json.loads(raw)
    _require(type(fixture) is dict and fixture.get('pilot_version') == 1,
             'unsupported pilot fixture version')
    _require(type(fixture.get('questions')) is list and len(fixture['questions']) == 3,
             'expected exactly three frozen development-authored questions')
    _require({q.get('case') for q in fixture['questions']} == {'E1', 'G1', 'T1'},
             'frozen question case identities changed')
    return fixture, _sha(raw)


def _safe_files(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    entries = archive.infolist()
    _require(0 < len(entries) <= ENTRY_LIMIT, 'unsafe archive entry count')
    all_names = [entry.filename for entry in entries]
    _require(len(all_names) == len(set(all_names)), 'duplicate archive entry name')
    # A case-insensitive collision is also ambiguous on Windows extraction.
    _require(len(all_names) == len(set(n.casefold() for n in all_names)),
             'case-folding archive filename collision')
    total = 0
    for entry in entries:
        p = pathlib.PurePosixPath(entry.filename)
        _require(not p.is_absolute() and all(part not in ('', '.', '..') for part in p.parts),
                 'unsafe archive member path')
        _require('\\' not in entry.filename and ':' not in entry.filename,
                 'unsafe archive filename syntax')
        file_mode = (entry.external_attr >> 16) & 0xffff
        _require(not stat.S_ISLNK(file_mode), 'symlink archive entry disallowed')
        _require(0 <= entry.file_size <= FILE_LIMIT, 'oversized archive entry')
        total += entry.file_size
    _require(total <= TOTAL_LIMIT, 'oversized decompressed archive')
    return entries


def transfer(archive_path: pathlib.Path, *, platform: str,
             fixture_path: pathlib.Path = DEFAULT_FIXTURE) -> dict:
    fixture, fixture_sha = _frozen_fixture(fixture_path)
    provenance = fixture['provenance']
    known = provenance['qualified_archive_sha256']
    _require(platform in ('linux', 'windows'), 'platform must be linux or windows')
    _require(platform in known, 'unsupported archive platform')
    original_zip_sha = _sha(archive_path.read_bytes())
    _require(original_zip_sha == known[platform], 'archive ZIP SHA256 does not match frozen release')

    with zipfile.ZipFile(archive_path, mode='r') as z:
        entries = _safe_files(z)
        _require(z.testzip() is None, 'corrupt archive CRC')
        _require(z.read('head-sha.txt').decode('ascii').strip() == provenance['qualified_main_sha'],
                 'archive is not from the qualified exact main commit')
        names = {entry.filename for entry in entries}
        # Never write into existing model stores or the archive itself: extract
        # exactly the archived original sealed studies into a disposable tree.
        with tempfile.TemporaryDirectory(prefix='emfeeld-teaching-pilot-') as temp:
            work = pathlib.Path(temp)
            for entry in entries:
                if not entry.filename.startswith('scenario-ensembles/') or entry.is_dir():
                    continue
                _require(entry.filename in names, 'missing archived study')
                target = work / entry.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(entry))
            evidence = {}
            for case in ('E1', 'G1', 'T1'):
                base = work / 'scenario-ensembles' / case
                # Full existing, source-bound run/store/native/comparison
                # inspection is the ONLY physical provenance admission path.
                evidence[case] = read_ensemble_measurements(
                    base / 'ensemble', store_path=base / 'store',
                    using=base / 'parent-template')

    answers = []
    measured = missing = 0
    for request in fixture['questions']:
        case = request['case']
        summary = evidence[case]
        _require(summary['status'] == request['expected_global_status'],
                 'original aggregate status does not match frozen question')
        seen = []
        for declared_id in request['member_ids']:
            row = next((r for r in summary['members'] if r['id'] == declared_id), None)
            _require(row is not None, 'named physical sibling does not exist')
            matching = [m for m in row['measurements'] if m['id'] == request['measurement_id']]
            _require(len(matching) == 1, 'expected exactly one original named measurement')
            item = matching[0]
            _require(item['status'] == request['expected_measurement_status'],
                     'original measurement completion status changed')
            _require(item['unit'] == request['expected_unit'], 'original physical unit changed')
            _require(item['context'] == request['expected_context'],
                     'original authored coordinate/time context changed')
            if item['status'] == 'unavailable':
                _require(item['value'] is None and
                         item['code'] == request['expected_code'],
                         'unavailable cannot be relabeled as numeric zero')
                missing += 1
            else:
                _require(item['value'] is not None and item['code'] is None,
                         'available original result has missing/invalid value')
                measured += 1
            receipt = row['evidence']
            _require(isinstance(receipt, dict) and
                     all(receipt.get(k) for k in (
                         'request_sha256','result_sha256','integrity_sha256',
                         'left_run_sha256','right_run_sha256')),
                     'missing sealed original comparison/native receipt')
            seen.append({
                'member_id': row['id'], 'original_member_index': row['index'],
                'revision_reference': row['reference'],
                'measurement_id': item['id'], 'measurement_type': item['type'],
                'status': item['status'], 'original_signed_right_minus_left_value': item['value'],
                'original_SI_unit': item['unit'], 'original_context': item['context'],
                'unavailable_code': item['code'], 'unavailable_reason': item['reason'],
                'source_comparison_and_run_sha256': receipt,
            })
        answers.append({
            'question_id': request['id'], 'developer_question': request['question'],
            'qualified_case': case, 'global_ensemble_status': summary['status'],
            'requested_member_ids': request['member_ids'],
            'original_reference_parent': summary['parent'],
            'original_parent_run_sha256': summary['source_run_sha256'],
            'original_measurements': seen,
            'interpretation_caveat': request['notes'],
        })
    return {
        'pilot_id': fixture['pilot_id'], 'pilot_version': 1,
        'original_release_commit': provenance['qualified_main_sha'],
        'original_release_zip_sha256': original_zip_sha,
        'platform': platform, 'frozen_fixture_sha256': fixture_sha,
        'questions': answers,
        'five_separate_evaluation_dimensions': {
            'interpretation_fidelity': 'author-selected source/quantity/context matches verified recorded inputs; not blind or independent interpretation',
            'physical_numerical_correctness': 'original source CI/numerical references and saved native integrity qualified; independent human physics certification not performed',
            'simulation_coverage': {'available_original_measurements': measured,
                                    'honestly_unavailable_original_measurements': missing},
            'educational_usefulness': 'not_evaluated_without_teacher',
            'textbook_answer_completeness': 'not_evaluated; this pilot asks only three explicitly specified comparisons'
        },
        'limits': 'Retrospective development-authored illustrative questions, independent prescribed-source alternatives, no physical time-transition simulation, no classroom outcome claim, unkeyed SHA not adversarial authentication'
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=pathlib.Path,help='exact original qualified main release ZIP')
    parser.add_argument('--platform',required=True, choices=('linux','windows'))
    parser.add_argument('--fixture',type=pathlib.Path,default=DEFAULT_FIXTURE)
    args = parser.parse_args(argv)
    try:
        report = transfer(args.archive, platform=args.platform,fixture_path=args.fixture)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError,
            zipfile.BadZipFile) as e:
        print(f'teaching-transfer pilot: {e}',file=sys.stderr)
        return 2
    # Avoid stdout locale accidents. The ASCII-safe JSON transport does not
    # change the original native SI values or their source receipts.
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
