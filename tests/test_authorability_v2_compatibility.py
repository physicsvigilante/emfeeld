"""Live packet compatibility; the original pilot's hash freeze stays historical.

Do not repoint or weaken the frozen pilot's provenance guard to accept modified
production code. These checks replay its unchanged data against the current API.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from emfeeld.observations import run_packet

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'pilots/authorability_v2'
spec=importlib.util.spec_from_file_location('v2_compatibility_judge',HERE/'run_pilot.py')
judge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)
CASES=json.loads((HERE/'cases.json').read_text())['cases']
REFS=json.loads((HERE/'references.json').read_text())['checks']


@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_historical_packet_keeps_its_declared_outcome(case):
    packet=json.loads((HERE/case['file']).read_text())
    if case.get('expected_error_contains'):
        with pytest.raises(ValueError) as exc:run_packet(packet)
        report,code,stderr=None,2,str(exc.value)
    else:
        report=run_packet(packet)
        code,stderr=(0 if report['status']=='ok' else 1),''
    assessed=judge.assess(case,report,REFS[case['id']],code,stderr)
    assert assessed['expected_outcome_verified'],assessed['issues']
    assert assessed['status']==('UNSUPPORTED' if case['role']=='limitation_control' else 'PASS')
