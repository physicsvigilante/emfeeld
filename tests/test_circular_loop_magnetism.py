"""Independent analytic identity and strict-boundary checks for Issue 62."""
import json
import math

import numpy as np
import pytest
from scipy.constants import mu_0

from emfeeld.circular_loop_magnetism import (
    CircularLoopState, axis_field, field_at_point, from_dict, load_lesson,
    measure, teaching_case,
)
from emfeeld.circular_loop_presentation import prepare


def test_centre_and_axis_independent_formulas():
    s = CircularLoopState(radius_m=0.4, current_A=3, probe_z_m=0.3)
    assert axis_field(s, 0)[2] == pytest.approx(mu_0 * 3 / (2 * 0.4))
    assert axis_field(s)[2] == pytest.approx(
        mu_0 * 3 * 0.4**2 / (2 * (0.4**2 + 0.3**2)**1.5))
    assert measure(s)["axis_only"] is True


@pytest.mark.parametrize("current", [5.0, -5.0, 0.0])
def test_signed_current_and_schematic_direction(current):
    s = CircularLoopState(current_A=current)
    p = prepare(s)
    assert p.report["centre_signed_B_T"] == pytest.approx(mu_0*current/(2*s.radius_m))
    if current == 0:
        assert np.array_equal(p.field_arrow_display_xyz, np.zeros(3))
        assert np.array_equal(p.current_arrow_display_xyz, np.zeros(3))
    else:
        assert np.sign(p.field_arrow_display_xyz[2]) == np.sign(current)
        assert np.linalg.norm(p.current_arrow_display_xyz) == pytest.approx(.5)


def test_radius_and_current_changes():
    original = CircularLoopState()
    doubled = teaching_case(original, "3")
    reversed_state = teaching_case(original, "2")
    assert axis_field(doubled, 0)[2] / axis_field(original, 0)[2] == pytest.approx(.5)
    assert axis_field(reversed_state)[2] == pytest.approx(-axis_field(original)[2])
    # At fixed SI z != 0, the ratio is not generally 1/2.
    assert axis_field(doubled, .2)[2] / axis_field(original, .2)[2] != pytest.approx(.5)


def test_rigid_normal_rotation_and_off_axis_rejection():
    s = CircularLoopState(centre_m=(1, 2, 3), normal_direction=(1, 1, 1),
                          probe_z_m=.3)
    u = np.asarray(s.normal_direction)
    point = tuple(np.asarray(s.centre_m) + .3*u)
    assert field_at_point(s, point) == pytest.approx(axis_field(s))
    with pytest.raises(ValueError, match="off-axis"):
        field_at_point(s, (1.1, 2, 3))
    assert np.cross(*__import__("emfeeld.circular_loop_magnetism",
        fromlist=["basis"]).basis(s)[1:]).tolist() == pytest.approx(u.tolist())


@pytest.mark.parametrize("updates", [
    {"current_A": True}, {"radius_m": False}, {"probe_z_m": "2"},
    {"radius_m": 0}, {"radius_m": 200}, {"current_A": float("inf")},
    {"normal_direction": (0, 0, 0)},
    {"normal_direction": (True, 0, 1)},
    {"centre_m": (0, 0, 101)}, {"samples_per_loop": True},
    {"samples_per_loop": 20}, {"probe_z_m": 101}
])
def test_invalid_states(updates):
    with pytest.raises(ValueError):
        CircularLoopState(**updates)


def test_json_rejects_duplicate_unknown_underflow_and_bool(tmp_path):
    state = CircularLoopState().to_dict()
    invalid = [
        json.dumps(state)[:-1] + ', "radius_m": 0.4}',
        json.dumps({**state, "unexpected": 1}),
        json.dumps({**state, "lesson_version": True}),
        json.dumps(state).replace('"radius_m": 0.2', '"radius_m": 1e-9999'),
        json.dumps(state).replace('"radius_m": 0.2', '"radius_m": NaN'),
    ]
    for value in invalid:
        path = tmp_path/"invalid.json"
        path.write_text(value)
        with pytest.raises(ValueError):
            load_lesson(path)


def test_immutable_buffers_detached():
    state = CircularLoopState()
    p = prepare(state)
    for arr in (p.loop_positions_m, p.positive_current_tangent, p.field_probe_T,
                p.loop_display_xyz, p.field_arrow_display_xyz):
        assert not arr.flags.writeable
        with pytest.raises(ValueError):
            arr.reshape(-1)[0] = 99
    with pytest.raises(TypeError):
        p.report["extra"] = 1
    assert from_dict(state.to_dict()) == state
