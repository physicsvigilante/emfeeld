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
    scaled = prepare(doubled, display_reference_radius_m=original.radius_m)
    assert np.linalg.norm(scaled.loop_display_xyz, axis=1) == pytest.approx(
        np.full(doubled.samples_per_loop, 2.0))
    assert scaled.loop_radius_display_reference_units == pytest.approx(2.0)
    assert "loop_radius_display_reference_units" not in scaled.report
    assert np.linalg.norm(scaled.current_arrow_display_xyz) == pytest.approx(.5)
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
    for name in ("centre_B_xyz_T", "probe_B_xyz_T"):
        assert isinstance(p.report[name], tuple)
        with pytest.raises(TypeError):
            p.report[name][0] = 99
    assert from_dict(state.to_dict()) == state


def test_direct_cartesian_axis_probe_numpy_vectors_and_mixed_bool_refusals():
    s = CircularLoopState(centre_m=(100, 0, 0), normal_direction=(1, 0, 0),
                          current_A=4, radius_m=.2)
    point = np.array([150, 0, 0], dtype=float)
    assert field_at_point(s, point) == pytest.approx(axis_field(s, 50))
    assert field_at_point(s, [150, 0, 0]) == pytest.approx(axis_field(s, 50))
    assert field_at_point(s, point.astype(int)) == pytest.approx(axis_field(s, 50))
    for bad in ([True, 0, 0], [0, np.bool_(True), 0],
                np.array([True, 0, 0], dtype=object),
                np.array([1, 2, 3], dtype=object),
                np.array([1.0, np.nan, 0.0]),
                np.array([[150.0, 0, 0]]), (201.0, 0, 0)):
        with pytest.raises(ValueError):
            field_at_point(s, bad)
    for current in (4, 0):
        with pytest.raises(ValueError, match="off-axis"):
            field_at_point(CircularLoopState(current_A=current), (0.02, 0, 0))


def test_teacher_presets_ignore_initial_offset_and_keep_compared_centre():
    s = CircularLoopState(radius_m=.5, current_A=3, probe_z_m=-.4)
    assert teaching_case(s, "1").probe_z_m == 0
    assert teaching_case(s, "2").probe_z_m == 0
    assert teaching_case(s, "3").probe_z_m == 0
    assert teaching_case(s, "2").current_A == -3
    assert teaching_case(s, "3").radius_m == 1.0


def test_review_f2_exactly_representable_off_axis_at_translated_axis():
    """Review 01 F2: seven float64 ULPs are NOT an axis point."""
    for signed_current in (4, 0, -4):
        state = CircularLoopState(centre_m=(100, 0, 0),
                                  normal_direction=(0, 0, 1),
                                  current_A=signed_current)
        for offset in (math.ulp(100.0), 1e-13, -1e-13):
            with pytest.raises(ValueError, match="off-axis"):
                field_at_point(state, (100+offset, 0, 0))
        # No false refusal at a truly axial point, even away from the centre.
        assert field_at_point(state, (100, 0, 0.2)) == pytest.approx(
            axis_field(state, .2), rel=2e-14, abs=1e-20)


def test_review_f2_rotated_roundoff_is_bounded_not_an_off_axis_solver():
    from emfeeld.circular_loop_magnetism import basis
    rng = np.random.default_rng(24681357)
    for _ in range(500):
        centre = tuple(map(float, rng.uniform(-100, 100, 3)))
        normal = tuple(map(float, rng.normal(size=3)))
        z = float(rng.uniform(-100, 100))
        state = CircularLoopState(centre_m=centre, normal_direction=normal)
        # A constructed oblique-axis point can accumulate at most a few ULPs.
        point = np.asarray(centre) + z*np.asarray(state.normal_direction)
        assert field_at_point(state, tuple(point)) == pytest.approx(
            axis_field(state, z), rel=3e-12, abs=2e-20)
        _, e1, _ = basis(state)
        # This separate physical radial displacement is RESOLVED and rejected.
        independent_off_axis = tuple(point + 1e-8*e1)
        with pytest.raises(ValueError, match="off-axis"):
            field_at_point(state, independent_off_axis)


def test_review_f1_snapshot_source_preflight_strict_and_no_output(tmp_path):
    from emfeeld.circular_loop_view import save_snapshot
    plus = CircularLoopState(current_A=5)
    minus = CircularLoopState(current_A=-5)
    valid_wrong = json.dumps(minus.to_dict()).encode("utf-8")
    valid_plus = json.dumps(plus.to_dict(), indent=3).encode("utf-8")
    bad_sources = (
        valid_wrong,
        b"not json",
        b"{\"lesson_version\":1}",
        valid_plus[:-1] + b', "current_A": 6}',  # duplicate key
        valid_plus.replace(b'"current_A": 5.0', b'"current_A": NaN'),
        valid_plus.replace(b'"current_A": 5.0', b'"current_A": 1e-9999'),
        valid_plus.replace(b'"current_A": 5.0', b'"current_A": true'),
        b"\xff"  # invalid UTF-8
    )
    for i, raw in enumerate(bad_sources):
        target = tmp_path/f"reject_{i}"
        with pytest.raises(ValueError):
            save_snapshot(plus, target, source_bytes=raw)
        assert not target.exists(), "preflight must run before the first output write"

    good_dir = tmp_path/"valid"
    report = save_snapshot(plus, good_dir, source_bytes=valid_plus)
    assert report["authored_state"] == plus.to_dict()
    assert (good_dir/"authored-input.json").read_bytes() == valid_plus
    assert json.loads((good_dir/"outcome.json").read_text())["completed"] is True
    with pytest.raises(ValueError):
        save_snapshot(plus, tmp_path/"wrong_type", source_bytes=valid_plus.decode())
    assert not (tmp_path/"wrong_type").exists()


def test_load_lesson_and_source_bytes_apply_identical_strict_rules(tmp_path):
    from emfeeld.circular_loop_magnetism import lesson_from_bytes
    source = CircularLoopState(current_A=3).to_dict()
    raw = json.dumps(source, sort_keys=True, indent=3).encode()
    path = tmp_path/"source.json"
    path.write_bytes(raw)
    assert lesson_from_bytes(raw) == load_lesson(path)
    for bad in (raw.replace(b'"current_A": 3.0', b'"current_A": false'),
                raw.replace(b'"current_A": 3.0', b'"current_A": Infinity'),
                raw.replace(b'"current_A": 3.0', b'"current_A": 1e309')):
        path.write_bytes(bad)
        with pytest.raises(ValueError):
            lesson_from_bytes(bad)
        with pytest.raises(ValueError):
            load_lesson(path)


def test_canonical_generated_snapshot_rotated_unit_normal_round_trip(tmp_path):
    from emfeeld.circular_loop_view import save_snapshot
    from emfeeld.circular_loop_magnetism import lesson_from_bytes
    for index, normal in enumerate(((1, 1, 1), (.3, .4, .5))):
        state = CircularLoopState(normal_direction=normal)
        serialized = json.dumps(state.to_dict(), sort_keys=True).encode()
        assert lesson_from_bytes(serialized) == state
        target = tmp_path/f"canonical_{index}"
        save_snapshot(state, target)
        raw = (target/"authored-input.json").read_bytes()
        assert lesson_from_bytes(raw) == state
        assert json.loads((target/"report.json").read_bytes())["authored_state"] == state.to_dict()
