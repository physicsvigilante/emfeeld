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
    # ZipInfo normalizes backslashes to forward slashes on Windows. Construct
    # the literal raw unsafe ZIP header and restore its name to the metadata
    # supplied to _safe_files if Python normalized it during reading. A safely
    # normalized name is not evidence that the validator accepted a backslash.
    encoded_name = entry.replace('\\', '/')
    raw = _zip_bytes([(encoded_name,b'data')])
    if '\\' in entry:
        raw = raw.replace(encoded_name.encode(), entry.encode())
        assert entry.encode() in raw
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if '\\' in entry and z.infolist()[0].filename != entry:
            assert z.infolist()[0].filename == encoded_name
            z.infolist()[0].filename = entry
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


@pytest.mark.parametrize('spoof', [
    'zip_repin', 'commit_repin', 'both_repin', 'teacher_authorship',
    'negative_field_magnitude', 'missing_body_zero', 'conductor_maxwell',
    'changed_notes', 'not_question_objects',
])
def test_pilot_rejects_untrusted_provenance_and_prose_before_archive_or_native(
        tmp_path, monkeypatch, spoof):
    # A caller cannot redefine the original release or smuggle new alleged
    # teacher/conductor claims into source-bound measurements. The input fixture
    # must fail before even reading the purported ZIP or running native physics.
    fixture, _ = pilot._frozen_fixture(pilot.DEFAULT_FIXTURE)
    if spoof in ('zip_repin', 'both_repin'):
        fixture['provenance']['qualified_archive_sha256']['linux'] = 'f' * 64
    if spoof in ('commit_repin', 'both_repin'):
        fixture['provenance']['qualified_main_sha'] = 'f' * 40
    if spoof == 'teacher_authorship':
        fixture['provenance']['teacher_validation'] = 'passed_by_teacher'
    if spoof == 'negative_field_magnitude':
        fixture['questions'][0]['question'] = 'Certified negative absolute electric field magnitude.'
    if spoof == 'missing_body_zero':
        fixture['questions'][1]['notes'] = 'Teacher verified zero baseline displacement for body_4.'
    if spoof == 'conductor_maxwell':
        fixture['questions'][2]['question'] = 'Teacher-verified Maxwell conductor polarization over time.'
    if spoof == 'changed_notes':
        fixture['questions'][2]['notes'] = 'Independently certified human teacher acceptance.'
    if spoof == 'not_question_objects':
        fixture['questions'] = ['E1', 'G1', 'T1']
    candidate = tmp_path / 'untrusted.json'
    candidate.write_text(json.dumps(fixture), encoding='utf-8')
    monkeypatch.setattr(pilot, 'DEFAULT_FIXTURE', candidate)
    monkeypatch.setattr(pilot, 'read_ensemble_measurements', lambda *a, **kw:
                        pytest.fail('native inspection reached on bad fixture'))
    archive = tmp_path / 'do-not-open.zip'  # deliberately nonexistent
    with pytest.raises(ValueError, match='fixture SHA256'):
        pilot.transfer(archive, platform='linux')
    assert not archive.exists()


def test_pilot_qualified_cli_refuses_fixture_override(tmp_path, capsys):
    # No second, user-controlled interpretation/provenance mode is advertised.
    # A rejected option cannot produce a legitimate original-source report.
    with pytest.raises(SystemExit) as err:
        pilot.main([str(tmp_path / 'not-present.zip'), '--platform', 'linux',
                    '--fixture', str(tmp_path / 'spoof.json')])
    assert err.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert 'unrecognized arguments: --fixture' in output.err


def test_pilot_canonical_constants_are_separate_from_fixture():
    frozen, digest = pilot._frozen_fixture(pilot.DEFAULT_FIXTURE)
    assert digest == pilot.FROZEN_FIXTURE_SHA256
    assert frozen['provenance']['qualified_main_sha'] == pilot.QUALIFIED_MAIN_SHA
    assert frozen['provenance']['qualified_archive_sha256'] == pilot.QUALIFIED_ARCHIVE_SHA256
