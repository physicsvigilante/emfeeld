from itertools import permutations
import json
from pathlib import Path
import re

import numpy as np
import pytest

from emfeeld import capacitor_view, conductor_cavity, gauss_lesson, wire_view
from emfeeld.capacitor_lesson import CapacitorState
from emfeeld.fields import K, PointSource, Superposition, UniformField
from emfeeld.scene import scene_from_json
from emfeeld.wire_magnetism import WireState


@pytest.mark.parametrize("raw", [b"NOT JSON", json.dumps(WireState(current_A=-5).to_dict()).encode()])
def test_wire_rejects_unbound_original_before_output(tmp_path, raw):
    destination = tmp_path / "output"
    with pytest.raises(ValueError):
        wire_view.save_snapshot(WireState(), destination, source_bytes=raw)
    assert not destination.exists()


def test_capacitor_rejects_boolean_before_output(tmp_path):
    state = CapacitorState()
    raw = json.dumps(dict(state.to_dict(), relative_permittivity=True)).encode()
    with pytest.raises(ValueError):
        capacitor_view.save_snapshot(state, tmp_path / "output", source_bytes=raw)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("reader,example", [
    (scene_from_json, "electric_composition.json"),
    (gauss_lesson.parse_lesson, "lessons/gauss_cube.json"),
    (conductor_cavity.load_lesson, "lessons/conductor_cavity.json"),
])
def test_charge_token_underflow_is_rejected(tmp_path, reader, example):
    text = (Path(__file__).resolve().parents[1] / "examples" / example).read_text()
    text, count = re.subn(r'("charge_C"\s*:\s*)[-.0-9eE+]+', r'\g<1>1e-9999', text, count=1)
    assert count == 1
    packet = tmp_path / "input.json"
    packet.write_text(text)
    with pytest.raises(ValueError, match="representable"):
        reader(packet if reader is conductor_cavity.load_lesson else text)


def test_field_and_potential_preserve_residual_for_every_order():
    positions = [[1, 0, 0], [2, 0, 0]]
    for order in permutations([1e16, 1., -1e16]):
        model = Superposition(tuple(UniformField("electric", [x, 0, 0]) for x in order))
        np.testing.assert_array_equal(model.field(positions), [[1, 0, 0]] * 2)
        np.testing.assert_array_equal(model.potential(positions), [-1, -2])


@pytest.mark.parametrize("charge,distance,ratio", [
    (1., 1e200, 1e-200), (1e-200, 1e-170, 1e-30), (1e300, 1e100, 1e200),
])
def test_finite_point_potential(charge, distance, ratio):
    with np.errstate(all="raise"):
        value = PointSource("electric", charge).potential([distance, 0, 0])
    assert value == pytest.approx(K * ratio, rel=2e-15, abs=0)
