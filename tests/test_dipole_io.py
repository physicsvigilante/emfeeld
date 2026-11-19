"""Exact input/state evidence and output refusal tests for dipole lesson."""
from dataclasses import replace
import hashlib
import json
import subprocess
import sys

import numpy as np
import pytest

from emfeeld.dipole_lesson import DipoleState, measure
from emfeeld.dipole_view import save_snapshot, _window


def test_headless_current_state_and_exact_authored_bytes(tmp_path):
    initial=DipoleState()
    current=replace(initial,charge_C=2e-9)
    raw=(json.dumps(initial.to_dict(),indent=4)+"\n").encode()
    out=tmp_path/"new"
    report=save_snapshot(current,out,source_bytes=raw,reference=initial)
    assert report["physics"]==measure(current)
    assert (out/"authored-input.json").read_bytes()==raw
    assert report["original_input_equals_current_state"] is False
    assert report["orientation_work"]["external_work_J"] is None
    assert report["display"] is None and report["screenshot"] is None
    for name,digest in json.loads((out/"integrity.json").read_text())["files"].items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
    with np.load(out/"measurements.npz") as a:
        np.testing.assert_array_equal(a["torque_N_m"],report["physics"]["torque_N_m"])


def test_zero_input_angle_unavailable_not_numeric_answer(tmp_path):
    r=save_snapshot(replace(DipoleState(),charge_C=0),tmp_path/"zero")
    assert r["physics"]["angle_deg"] is None
    out=json.loads((tmp_path/"zero/outcome.json").read_text())
    assert out["execution_complete"] is True and out["angle_available"] is False
    assert out["time_dynamics"] is False


@pytest.mark.parametrize("suffix",["","child","a/b"])
def test_sealed_evidence_refusal_no_pollution(tmp_path,suffix):
    out=tmp_path/"sealed"
    save_snapshot(DipoleState(),out)
    before={str(p.relative_to(out)):p.read_bytes() for p in out.rglob("*") if p.is_file()}
    with pytest.raises((ValueError,OSError)):save_snapshot(DipoleState(),out/suffix)
    after={str(p.relative_to(out)):p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert before==after


@pytest.mark.parametrize("raw",["not bytes",b'{}',b'\xff',b'{"charge_C":1,"charge_C":1}',b'{"charge_C":NaN}'])
def test_bad_authored_input_rejected_before_write(tmp_path,raw):
    output=tmp_path/"new"
    with pytest.raises(ValueError):save_snapshot(DipoleState(),output,source_bytes=raw)
    assert not output.exists()


def test_late_failure_retains_incomplete_unsealed_attempt(tmp_path,monkeypatch):
    from pathlib import Path
    old=Path.write_text
    def fail(self,*args,**kwargs):
        if self.name=="report.json":raise OSError("injected report failure")
        return old(self,*args,**kwargs)
    monkeypatch.setattr(Path,"write_text",fail)
    out=tmp_path/"failed"
    with pytest.raises(OSError,match="injected"):save_snapshot(DipoleState(),out)
    assert not (out/"integrity.json").exists()
    assert json.loads((out/"outcome.json").read_text())["execution_complete"] is False


@pytest.mark.parametrize("size",[(839,560),(840,559),(True,960),(1440.,960),(4000,2200),[840]])
def test_invalid_window_input(size):
    with pytest.raises(ValueError):_window(size)


def test_symlink_alias_of_sealed_evidence_refused(tmp_path):
    out=tmp_path/"sealed";save_snapshot(DipoleState(),out)
    alias=tmp_path/"alias"
    try:alias.symlink_to(out,target_is_directory=True)
    except OSError:pytest.skip("symlink privilege unavailable on this host")
    with pytest.raises(ValueError):save_snapshot(DipoleState(),alias/"new")
    assert not (out/"new").exists()


def test_headless_entrypoint_does_not_import_graphics(tmp_path):
    code="""import sys
from emfeeld.dipole_lesson import DipoleState
from emfeeld.dipole_view import save_snapshot
save_snapshot(DipoleState(),sys.argv[1])
assert 'pyvista' not in sys.modules
assert 'vtk' not in sys.modules
"""
    result=subprocess.run([sys.executable,"-c",code,str(tmp_path/"cli")],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
