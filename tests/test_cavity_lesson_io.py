"""Output preflight and honest retained headless lesson state."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from emfeeld.conductor_cavity import ConductorCavity
from emfeeld.cavity_lesson import save_snapshot, main


def test_retained_samples_and_all_file_receipts(tmp_path):
    m=ConductorCavity();out=tmp_path/'new';raw=json.dumps(m.to_dict()).encode()
    report=save_snapshot(m,out,source_bytes=raw,count=8)
    assert json.loads((out/'lesson.json').read_text())==m.to_dict()
    assert (out/'authored-input.json').read_bytes()==raw
    assert report['original_input_equals_current_state'] is True
    assert report['teacher_usefulness']=='not_evaluated'
    assert report['field_lines']['count']==8
    arrays=np.load(out/'field_lines.npz',allow_pickle=False)
    for a in arrays.values():assert (np.linalg.norm(a,axis=1)<1).all()
    inventory=json.loads((out/'integrity.json').read_text())['files']
    assert set(inventory)=={p.name for p in out.iterdir() if p.name!='integrity.json'}
    for name,digest in inventory.items():assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
    with pytest.raises(FileExistsError):save_snapshot(m,out,count=4)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    with pytest.raises(ValueError,match='saved evidence'):save_snapshot(m,out/'nested',count=4)
    assert before=={p.name:p.read_bytes() for p in out.iterdir()}


@pytest.mark.parametrize('marker',[('integrity.json',),('question.json','receipt.json'),('started.json','outcome.json')])
def test_refusal_before_trace_or_renderer(tmp_path,monkeypatch,marker):
    import emfeeld.cavity_lesson as lesson
    for name in marker:(tmp_path/name).write_text('{}')
    monkeypatch.setattr(lesson,'trace_cavity_lines',lambda *a,**k: pytest.fail('must preflight before tracing'))
    with pytest.raises(ValueError,match='saved evidence'):save_snapshot(ConductorCavity(),tmp_path/'no')
    assert not (tmp_path/'no').exists()


def test_symlink_sealed_namespace_and_input_alias_preserved(tmp_path):
    sealed=tmp_path/'sealed';sealed.mkdir();(sealed/'integrity.json').write_text('{}')
    alias=tmp_path/'alias'
    try:alias.symlink_to(sealed,target_is_directory=True)
    except (OSError,NotImplementedError):pytest.skip('platform does not permit this symlink')
    with pytest.raises(ValueError):save_snapshot(ConductorCavity(),alias/'nested')
    assert sorted(p.name for p in sealed.iterdir())==['integrity.json']


def test_invalid_sampling_fails_before_writes(tmp_path):
    with pytest.raises(ValueError):save_snapshot(ConductorCavity(),tmp_path/'no',count=0)
    assert not (tmp_path/'no').exists()


def test_interrupted_snapshot_is_retained_not_complete(tmp_path,monkeypatch):
    import emfeeld.cavity_lesson as lesson
    def fail(*a,**kw):raise RuntimeError('test display failure')
    monkeypatch.setattr(lesson,'trace_cavity_lines',fail)
    out=tmp_path/'first_failure'
    with pytest.raises(RuntimeError,match='test display failure'):save_snapshot(ConductorCavity(),out,count=4)
    assert json.loads((out/'outcome.json').read_text())['execution_complete'] is False
    assert (out/'lesson.json').exists() and not (out/'integrity.json').exists()
    with pytest.raises(ValueError):save_snapshot(ConductorCavity(),out/'retry',count=4)


def test_source_file_is_not_replaced_and_current_state_is_explicit(tmp_path):
    source=ConductorCavity();raw=json.dumps(source.to_dict()).encode()
    current=replace(source,mode='grounded',charge_C=-1e-9)
    r=save_snapshot(current,tmp_path/'capture',source_bytes=raw,count=4)
    assert r['original_input_equals_current_state'] is False
    assert json.loads((tmp_path/'capture/lesson.json').read_text())==current.to_dict()
    assert (tmp_path/'capture/authored-input.json').read_bytes()==raw


def test_public_headless_cli_and_bad_snapshot_without_graphics(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=root/'examples/lessons/conductor_cavity.json'
    out=tmp_path/'cli'
    p=subprocess.run([sys.executable,'-m','emfeeld.cavity_lesson',str(source),'--headless',str(out),'--lines','4'],
                      cwd=root,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    assert json.loads((out/'outcome.json').read_text())['execution_complete'] is True
    assert main([str(source),'--snapshot',str(out/'pollute')])==2
    assert not (out/'pollute').exists()
