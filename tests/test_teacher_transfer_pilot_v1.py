"""Bounded developer-authored teacher-transfer pilot admission and no-write tests.

Real exact-commit E1/G1/T1 original ZIP execution is an external qualification,
not an extra fake source fixture hidden in these unit tests.
"""
import importlib.util
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'verification' / 'teacher_transfer_pilot_v1.py'
spec = importlib.util.spec_from_file_location('teacher_transfer_pilot_v1', SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_pilot_fixture_is_explicit_three_author_questions():
    fixture, digest = pilot._frozen_fixture(pilot.DEFAULT_FIXTURE)
    assert len(digest) == 64
    assert fixture['pilot_version'] == 1
    assert {q['case'] for q in fixture['questions']} == {'E1','G1','T1'}
    assert fixture['provenance']['teacher_validation'] == 'not_evaluated'
    assert all(q['expected_context'] is not None for q in fixture['questions'] if q['case']!='G1')
    assert next(q for q in fixture['questions'] if q['case']=='G1')['expected_code'] == 'unknown_operand'


@pytest.mark.parametrize('damage', [
    {'questions':[]},
    {'pilot_version':2},
    {'questions':[{'case':'E1'},{'case':'E1'},{'case':'G1'}]},
])
def test_pilot_rejects_changed_question_version_or_identity(tmp_path, damage):
    fixture, _ = pilot._frozen_fixture(pilot.DEFAULT_FIXTURE)
    fixture.update(damage)
    f=tmp_path/'mutated-questions.json'
    f.write_text(json.dumps(fixture))
    with pytest.raises(ValueError):
        pilot._frozen_fixture(f)


def _zip_bytes(entries):
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w') as z:
        for path,payload in entries:
            z.writestr(path,payload)
    return result.getvalue()


@pytest.mark.parametrize('entry', [
    '../escape.txt', '/etc/example', 'scenario-ensembles/E1/../evil',
    'C:/absolute.txt', 'folder\\evil.txt'
])
def test_pilot_refuses_archive_traversal_and_platform_paths(entry):
    with zipfile.ZipFile(io.BytesIO(_zip_bytes([(entry,b'data')]))) as z:
        with pytest.raises(ValueError,match='unsafe'):
            pilot._safe_files(z)


def test_pilot_refuses_symlink_entries():
    output=io.BytesIO()
    info=zipfile.ZipInfo('scenario-ensembles/link')
    info.create_system=3
    info.external_attr=(stat.S_IFLNK|0o777)<<16
    with zipfile.ZipFile(output,'w') as z:z.writestr(info,'../../etc/passwd')
    with zipfile.ZipFile(io.BytesIO(output.getvalue())) as z:
        with pytest.raises(ValueError,match='symlink'):
            pilot._safe_files(z)


def test_pilot_refuses_case_collisions():
    raw=_zip_bytes([('Case/file',b'a'),('case/file',b'b')])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with pytest.raises(ValueError,match='case-folding'):
            pilot._safe_files(z)


def test_pilot_requires_exact_original_archive_sha(tmp_path):
    archive=tmp_path/'different.zip'
    archive.write_bytes(_zip_bytes([('head-sha.txt',b'3f1ec44a54b24b9f8275a98abf81126a9386bf61')]))
    before=archive.read_bytes()
    with pytest.raises(ValueError,match='SHA256'):
        pilot.transfer(archive,platform='linux')
    assert archive.read_bytes()==before


def test_pilot_invalid_platform_does_not_mutate_source(tmp_path):
    archive=tmp_path/'bad.zip';archive.write_bytes(b'not-a-zip')
    original=archive.read_bytes()
    with pytest.raises(ValueError,match='platform'):
        pilot.transfer(archive,platform='unknown')
    assert archive.read_bytes()==original
