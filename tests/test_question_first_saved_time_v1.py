"""Independent-review B1 regression: saved physical time is part of observation identity.

These cases exercise the public source-first CLI and actual native simulation.
They do not change or reinterpret the qualified solver or observation API.
"""
from copy import deepcopy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "verification/question_first_trial_v1.py"
SPEC = importlib.util.spec_from_file_location("question_first_trial_v1_b1", SCRIPT)
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)
QUESTION = ROOT / "examples/question_first_v1/developer_question.json"
PACKET = ROOT / "examples/question_first_v1/developer_packet.json"


def _inputs(tmp_path):
    question_path, packet_path = tmp_path/"question.json", tmp_path/"packet.json"
    question = json.loads(QUESTION.read_text(encoding="utf-8"))
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    return question_path, packet_path, question, packet


def _save(question_path, packet_path, question, packet):
    question_path.write_text(json.dumps(question, ensure_ascii=False), encoding="utf-8")
    packet_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")


def test_public_cli_subpicosecond_wrong_saved_instant_is_incomplete(tmp_path):
    """Reviewer R2 B1: requested time 0 must not match actual sample at 5e-13 s."""
    qpath, ppath, question, packet = _inputs(tmp_path)
    question["source"]["question"] = "Find velocity at the launch instant t=0."
    question["requested_measurements"] = [{
        "id": "velocity_at_zero", "quantity": "velocity exactly at t=0",
        "unit": "m/s", "native_type": "trajectory_sample",
        "native_quantity": "velocity",
        "context": {"particle_index": 0, "sample_index": 20, "time_s": 0},
    }]
    packet["scene"]["sources"] = [{
        "type": "uniform", "field_m_s2": [2e16, 0, 0], "origin_m": [0, 0, 0]
    }]
    packet["scene"]["particles"] = [{
        "mass_kg": 1, "position_m": [0, 0, 0], "velocity_m_s": [0, 0, 0]
    }]
    packet["scene"]["duration_s"] = 5e-13
    packet["scene"]["samples"] = 21
    packet["scene"]["bounds_m"] = [-1, 1, -1, 1, -1, 1]
    packet["observations"] = [{
        "id": "velocity_at_zero", "type": "trajectory_sample",
        "particle_index": 0, "quantity": "velocity", "sample_index": 20
    }]
    _save(qpath, ppath, question, packet)
    question_bytes, packet_bytes = qpath.read_bytes(), ppath.read_bytes()
    lock, attempt = tmp_path/"lock", tmp_path/"attempt"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT/"src") + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, str(SCRIPT)]
    frozen = subprocess.run(
        cmd+["freeze", str(qpath), "--output", str(lock)],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert frozen.returncode == 0, frozen.stderr
    assessed = subprocess.run(
        cmd+["assess", str(lock), "--packet", str(ppath), "--output", str(attempt)],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert assessed.returncode == 1, assessed.stderr
    native = json.loads((attempt/"native-result.json").read_text())
    result = native["results"][0]
    assert result["status"] == "ok"
    assert result["sample_index"] == 20
    assert result["time_s"] == 5e-13
    assert math.isclose(result["value"][0], 10000.0, abs_tol=1e-5, rel_tol=0)
    assessment = json.loads((attempt/"assessment.json").read_text())
    assert assessment["native_measurement_coverage"] == "incomplete"
    assert "velocity_at_zero: actual saved time disagrees with frozen context" in assessment["issues"]
    assert json.loads((attempt/"state.json").read_text()) == {
        "execution_complete": True, "native_measurement_coverage": "incomplete"
    }
    assert (lock/"question.json").read_bytes() == question_bytes
    assert (attempt/"question.json").read_bytes() == question_bytes
    assert (attempt/"packet.json").read_bytes() == packet_bytes
    assert qpath.read_bytes() == question_bytes and ppath.read_bytes() == packet_bytes


def test_distinct_but_nearby_nonzero_time_is_incomplete(tmp_path):
    """A 5e-13 s discrepancy also matters for an ordinary 2-second problem."""
    qpath, ppath, question, packet = _inputs(tmp_path)
    question["requested_measurements"][1]["context"]["time_s"] = 2.0000000000005
    _save(qpath, ppath, question, packet)
    lock, attempt = tmp_path/"lock", tmp_path/"attempt"
    trial.freeze(qpath, lock)
    assessment = trial.assess(lock, ppath, attempt)
    native = json.loads((attempt/"native-result.json").read_text())
    assert native["results"][1]["time_s"] == 2.0
    assert assessment["native_measurement_coverage"] == "incomplete"
    assert "position_final: actual saved time disagrees with frozen context" in assessment["issues"]
    assert json.loads((attempt/"state.json").read_text())["execution_complete"] is True


def test_rounding_of_same_grid_instant_is_accepted(tmp_path):
    """An authored 0.3 may be recorded as 0.30000000000000004 by linspace."""
    qpath, ppath, question, packet = _inputs(tmp_path)
    question["source"]["question"] = "Report position at t=0.3 seconds."
    request = deepcopy(question["requested_measurements"][1])
    request["context"] = {"particle_index": 0, "sample_index": 3, "time_s": 0.3}
    question["requested_measurements"] = [request]
    packet["scene"]["duration_s"] = 1
    packet["scene"]["samples"] = 11
    packet_request = deepcopy(packet["observations"][1])
    packet_request["sample_index"] = 3
    packet["observations"] = [packet_request]
    _save(qpath, ppath, question, packet)
    lock, attempt = tmp_path/"lock", tmp_path/"attempt"
    trial.freeze(qpath, lock)
    assessment = trial.assess(lock, ppath, attempt)
    native = json.loads((attempt/"native-result.json").read_text())
    actual_time = native["results"][0]["time_s"]
    assert abs(actual_time - 0.3) <= math.ulp(0.3)
    assert assessment["issues"] == []
    assert assessment["native_measurement_coverage"] == "complete"
    assert json.loads((attempt/"state.json").read_text())["native_measurement_coverage"] == "complete"


@pytest.mark.parametrize("actual,expected,duration,samples,match", [
    (0, 0, 1, 11, True),
    (5e-13, 0, 5e-13, 21, False),
    (1.5, 1.5000000000005, 1.5, 16, False),
    (math.nextafter(0.3, math.inf), 0.3, 1, 11, True),
    (math.ulp(0.0), 2*math.ulp(0.0), 20*math.ulp(0.0), 21, False),
    (math.ulp(0.0), 0, 20*math.ulp(0.0), 21, False),
    (float("nan"), 0.3, 1, 11, False),
    (float("inf"), 0.3, 1, 11, False),
])
def test_saved_time_guard_boundary_cases(actual, expected, duration, samples, match):
    assert trial._same_saved_time(
        actual, expected, duration_s=duration, samples=samples) is match
