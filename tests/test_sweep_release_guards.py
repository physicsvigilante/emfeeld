"""Release-audit regressions; faults below are synthetic, not new physics cases."""
import pytest

from emfeeld import model_runs, sweeps
from emfeeld.model_revisions import RevisionError, encode
from test_sweeps import setup_case, go, inventory


def test_unrepresentable_integer_rejected_cleanly_before_mutation(tmp_path):
    store, _, spec = setup_case(tmp_path)
    spec['values'] = [10**400]
    before = inventory(store.path)
    with pytest.raises(ValueError, match='finite'):
        go(tmp_path, store, spec)
    assert inventory(store.path) == before
    assert not (tmp_path/'sweep-output').exists()


def test_failed_fresh_baseline_records_every_unexecuted_member(tmp_path, monkeypatch):
    store, _, spec = setup_case(tmp_path)
    before = inventory(store.path)
    original = model_runs.execute
    def reject_baseline(*args, **kwargs):
        # Exercise a real sealed native rejection after the valid old template
        # has been inspected; this tests orchestration, not source admissibility.
        def fail_lower(*a, **k):
            raise RevisionError('audit_injected_failure', 'synthetic baseline failure')
        with monkeypatch.context() as local:
            local.setattr(model_runs, 'lower', fail_lower)
            return original(*args, **kwargs)
    monkeypatch.setattr(model_runs, 'execute', reject_baseline)
    report = go(tmp_path, store, spec)
    assert report['status'] == 'partial'
    assert len(report['members']) == len(spec['values'])
    assert [m['value'] for m in report['members']] == spec['values']
    assert all(m['status'] == 'not_run' and m['reference'] is None
               for m in report['members'])
    assert inventory(store.path) == before
    assert sweeps.inspect_sweep(tmp_path/'sweep-output') == report


@pytest.mark.parametrize('omission', ['all', 'one', 'duplicate'])
def test_incomplete_comparison_cannot_pass(tmp_path, monkeypatch, omission):
    store, _, spec = setup_case(tmp_path)
    original = model_runs.compare_runs
    def dropped(*args, **kwargs):
        result = original(*args, **kwargs)
        rows = result['measurements']
        result['measurements'] = ([] if omission == 'all' else
                                  rows[:-1] if omission == 'one' else
                                  [rows[0]]*len(rows))
        return result
    monkeypatch.setattr(model_runs, 'compare_runs', dropped)
    report = go(tmp_path, store, spec)
    assert report['status'] == 'partial'
    assert all(m['status'] == 'partial' for m in report['members'])
    assert all('comparison' in m['reason'] for m in report['members'])


def test_inspect_accepts_original_windows_relative_run_paths(tmp_path):
    store, _, spec = setup_case(tmp_path)
    report = go(tmp_path, store, spec)
    root = tmp_path/'sweep-output'
    # Model the original Windows writer on either platform. This deliberately
    # creates a new test fixture; it does not alter retained execution evidence.
    for member in report['members']:
        member['run_path'] = member['run_path'].replace('/', '\\')
        member['comparison_path'] = member['comparison_path'].replace('/', '\\')
    (root/'summary.json').write_bytes(encode(report))
    (root/'integrity.json').write_bytes(encode({'files': sweeps._inventory(root)}))
    assert sweeps.inspect_sweep(root) == report


def test_unexpected_execution_failure_stays_incomplete(tmp_path, monkeypatch):
    store, _, spec = setup_case(tmp_path)
    before = inventory(store.path)
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic unexpected backend failure')
    monkeypatch.setattr(model_runs, 'execute', fail)
    with pytest.raises(RuntimeError, match='unexpected backend'):
        go(tmp_path, store, spec)
    root = tmp_path/'sweep-output'
    assert (root/'started.json').is_file()
    assert not (root/'summary.json').exists()
    assert not (root/'integrity.json').exists()
    assert inventory(store.path) == before


@pytest.mark.parametrize('value', ['', '.', '../outside', '/outside',
                                  'C:\\outside', 'C:relative',
                                  '\\\\server\\share', 'member-01/../../outside'])
def test_captured_paths_cannot_escape_archive(tmp_path, value):
    with pytest.raises(RevisionError, match='captured path'):
        sweeps._captured_path(tmp_path, value)


def test_huge_integer_cli_exit_is_input_error(tmp_path, capsys):
    store, _, spec = setup_case(tmp_path)
    spec['values'] = [10**400]
    path = tmp_path/'input.json'; path.write_bytes(encode(spec))
    before = inventory(store.path)
    code = sweeps.main(['run', str(path), '--store', str(store.path),
                       '--using', str(tmp_path/'base'),
                       '--output', str(tmp_path/'new-output')])
    assert code == 2
    assert 'finite' in capsys.readouterr().err
    assert inventory(store.path) == before
    assert not (tmp_path/'new-output').exists()


def test_new_artifact_paths_use_forward_slashes(tmp_path):
    store, _, spec = setup_case(tmp_path)
    report = go(tmp_path, store, spec)
    for member in report['members']:
        assert member['run_path'] == f"member-{member['index']:02d}/run"
        assert member['comparison_path'] == f"member-{member['index']:02d}/comparison.json"
