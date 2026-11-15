"""Same-author transfer through shared native operations and separate references."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def module(relative,name):
    spec=spec_from_file_location(name,ROOT/relative)
    obj=module_from_spec(spec);spec.loader.exec_module(obj)
    return obj


def test_two_motivating_arrangements_and_independent_expressions(tmp_path):
    driver=module('tools/qualify_structural_revisions.py','structural_driver')
    reference=module('verification/check_structural_runs.py','structural_reference')
    runs=tmp_path/'runs';result=driver.qualify(runs)
    assert result['status']=='complete' and set(result['cases'])=={'E1','G1'}
    check=reference.check(runs)
    assert check['passed'] and len(check['runs'])==4
    assert sum(len(r['particles']) for r in check['runs'])==6


def test_preselected_reserved_case_now_retained_as_regression(tmp_path):
    # This case first ran AFTER production freeze in the original qualification.
    # Its subsequent CI replays are regressions, not fresh held-out evidence.
    driver=module('tools/qualify_structural_revisions.py','reserved_driver')
    reference=module('verification/check_structural_runs.py','reserved_reference')
    runs=tmp_path/'reserved'
    result=driver.qualify(runs,ROOT/'examples/structural_revisions/reserved_cases.json')
    check=reference.check(runs)
    assert result['status']=='complete' and check['passed']
    assert len(check['runs'])==3 and sum(r['static_checks'] for r in check['runs'])==18
