"""Independent analytic checks: rectangular current-loop forces, torque and U."""
import json
import math

import numpy as np
import pytest

from emfeeld.rectangular_loop_torque import (
    RectangularLoopState, calculate, from_dict, lesson_from_bytes,
    load_lesson, measure, orientation, teaching_case,
)


def test_reference_parallel_perpendicular_antiparallel():
    s = RectangularLoopState(current_A=3, width_m=.6, height_m=.4,
                             field_strength_T=.2)
    magnitude = 3 * .6 * .4 * .2
    parallel = measure(teaching_case(s, "1"))
    perpendicular = measure(teaching_case(s, "2"))
    opposite = measure(teaching_case(s, "3"))
    assert parallel["torque_magnitude_N_m"] == 0
    assert perpendicular["torque_magnitude_N_m"] == pytest.approx(magnitude)
    assert opposite["torque_magnitude_N_m"] == 0
    assert parallel["orientation_potential_J"] == pytest.approx(-magnitude)
    assert perpendicular["orientation_potential_J"] == 0
    assert opposite["orientation_potential_J"] == pytest.approx(magnitude)
    assert perpendicular["moment_xyz_A_m2"] == pytest.approx([.72, 0, 0])
    assert perpendicular["torque_xyz_N_m"] == pytest.approx([0, -.144, 0])


def test_independent_segment_lorentz_force_and_torque_axis():
    s = RectangularLoopState(tilt_deg=90, width_m=.6, height_m=.4,
                             current_A=3, field_strength_T=.2)
    d, _ = calculate(s)
    # At theta=90 e1=+y, e2=+z and B=+z. Opposite +-y segments
    # experience opposing +-x forces. Axial +-z segments get no force.
    np.testing.assert_allclose(d["forces_N"], np.asarray([
        [.36, 0, 0], [0, 0, 0], [-.36, 0, 0], [0, 0, 0]]),
        rtol=0, atol=1e-15)
    assert d["net_force_N"] == pytest.approx([0, 0, 0], abs=1e-15)
    assert d["segment_torque_N_m"] == pytest.approx([0, -.144, 0], abs=1e-15)
    assert d["torque_N_m"] == pytest.approx([0, -.144, 0], abs=1e-15)


@pytest.mark.parametrize("angle", [0, 15, 37.5, 90, 123.4, 165, 180])
@pytest.mark.parametrize("strength", [-.4, 0.0, .4])
@pytest.mark.parametrize("current", [-5, 0, 5])
def test_scalar_reference_and_signed_vectors(angle, strength, current):
    s = RectangularLoopState(tilt_deg=angle, field_strength_T=strength,
                             current_A=current, width_m=.5, height_m=.3)
    d, U = calculate(s)
    amplitude = current * .5 * .3 * strength
    assert U == pytest.approx(-amplitude*math.cos(math.radians(angle)), abs=2e-15)
    assert np.linalg.norm(d["torque_N_m"]) == pytest.approx(
        abs(amplitude*math.sin(math.radians(angle))), abs=2e-15)
    assert np.linalg.norm(d["moment_A_m2"]) == pytest.approx(
        abs(current*.5*.3), abs=2e-15)
    assert d["net_force_N"] == pytest.approx(np.zeros(3), abs=2e-15)
    assert d["segment_torque_N_m"] == pytest.approx(d["torque_N_m"], abs=2e-15)
    assert np.cross(d["width_unit"], d["height_unit"]) == pytest.approx(
        d["normal_unit"], abs=2e-15)
    assert d["loop_corners_m"].shape == (4, 3)


def test_random_rigid_frame_integral_and_force_couple():
    rng = np.random.default_rng(413)
    for _ in range(250):
        axis = tuple(rng.normal(size=3).tolist())
        center = tuple(rng.uniform(-25, 25, 3).tolist())
        w, h = map(float, rng.uniform(.02, 7, 2))
        I = float(rng.uniform(-60, 60))
        B = float(rng.uniform(-2, 2))
        theta = float(rng.uniform(.001, 179.999))
        s = RectangularLoopState(centre_m=center, field_direction=axis,
                                 width_m=w, height_m=h, current_A=I,
                                 field_strength_T=B, tilt_deg=theta)
        d, U = calculate(s)
        u = np.asarray(s.field_direction)
        expected_abs_torque = abs(I*w*h*B*math.sin(math.radians(theta)))
        assert np.linalg.norm(d["torque_N_m"]) == pytest.approx(
            expected_abs_torque, rel=1e-11, abs=1e-13)
        assert U == pytest.approx(-I*w*h*B*math.cos(math.radians(theta)),
                                  rel=1e-11, abs=1e-13)
        assert np.dot(d["normal_unit"], u) == pytest.approx(
            math.cos(math.radians(theta)), abs=2e-14)
        assert d["segment_torque_N_m"] == pytest.approx(
            d["torque_N_m"], rel=2e-12, abs=2e-12)
        assert d["net_force_N"] == pytest.approx(np.zeros(3), abs=2e-12)


def test_reversal_of_current_versus_external_field_and_zero_states():
    s = RectangularLoopState(tilt_deg=50, current_A=2, field_strength_T=.5)
    d, u = calculate(s)
    reversed_I, u_I = calculate(RectangularLoopState(
        tilt_deg=50, current_A=-2, field_strength_T=.5))
    reversed_B, u_B = calculate(RectangularLoopState(
        tilt_deg=50, current_A=2, field_strength_T=-.5))
    assert reversed_I["moment_A_m2"] == pytest.approx(-d["moment_A_m2"])
    assert reversed_B["moment_A_m2"] == pytest.approx(d["moment_A_m2"])
    for actual in (reversed_I, reversed_B):
        for key in ("forces_N", "torque_N_m", "segment_torque_N_m"):
            assert actual[key] == pytest.approx(-d[key], abs=1e-15)
    assert u_I == pytest.approx(-u)
    assert u_B == pytest.approx(-u)
    for kwargs in ({"current_A": 0}, {"field_strength_T": 0}):
        z = RectangularLoopState(tilt_deg=50, **kwargs)
        d0, e0 = calculate(z)
        assert e0 == 0.0
        assert not np.any(d0["forces_N"]) and not np.any(d0["torque_N_m"])


@pytest.mark.parametrize("changes", [
    {"current_A": True}, {"current_A": "2"}, {"current_A": 1e-9},
    {"field_strength_T": False}, {"field_strength_T": 1e-9},
    {"field_strength_T": 100}, {"width_m": 0}, {"height_m": 100},
    {"width_m": float("nan")}, {"height_m": "1"},
    {"centre_m": (1, 2, True)}, {"centre_m": [0, 0, 101]},
    {"field_direction": (0, 0, 0)}, {"field_direction": (1e-20, 0, 0)},
    {"field_direction": (0, True, 1)}, {"tilt_deg": -1},
    {"tilt_deg": 181}, {"tilt_deg": True}, {"tilt_deg": float("inf")},
])
def test_bad_state_rejected(changes):
    with pytest.raises(ValueError):
        RectangularLoopState(**changes)


def test_strict_json_and_canonical_rotated_direction_roundtrip(tmp_path):
    s = RectangularLoopState(centre_m=(2, 1, -3), field_direction=(1, 2, 3),
                             tilt_deg=75)
    good = json.dumps(s.to_dict(), indent=2).encode()
    assert lesson_from_bytes(good) == s
    path = tmp_path/"lesson.json"
    path.write_bytes(good)
    assert load_lesson(path) == s
    bad = [
        b"invalid-json",
        good.replace(b'"current_A": 3.0', b'"current_A": true'),
        good.replace(b'"current_A": 3.0', b'"current_A": 1e-9999'),
        good.replace(b'"current_A": 3.0', b'"current_A": Infinity'),
        good.replace(b'"current_A": 3.0', b'"current_A": 1e309'),
        good[:-1] + b', "current_A": 2}',
        good[:-1] + b', "unknown_solver": true}',
        good.replace(b'"lesson_version": 1', b'"lesson_version": true'),
        b"\xff",
    ]
    for payload in bad:
        path.write_bytes(payload)
        with pytest.raises(ValueError):
            lesson_from_bytes(payload)
        with pytest.raises(ValueError):
            load_lesson(path)
    with pytest.raises(ValueError):
        lesson_from_bytes(good.decode())
    with pytest.raises(ValueError):
        from_dict({**s.to_dict(), "field_strength_T": "0.2"})


def test_near_parallel_resolvable_torque_magnitude_not_squared_to_zero():
    s = RectangularLoopState(tilt_deg=1e-200, current_A=3,
                             width_m=.6, height_m=.4, field_strength_T=.2)
    d, _ = calculate(s)
    expected = abs(3*.6*.4*.2*math.sin(math.radians(1e-200)))
    assert expected > 0
    assert math.hypot(*d["torque_N_m"]) == pytest.approx(expected, rel=1e-13)
    assert measure(s)["torque_magnitude_N_m"] == pytest.approx(expected, rel=1e-13)


def test_teaching_presets_select_geometry_and_explicit_zero():
    initial = RectangularLoopState(tilt_deg=40, current_A=5, field_strength_T=.1)
    assert [teaching_case(initial, str(i)).tilt_deg for i in range(1, 7)] == [
        0, 90, 180, 90, 90, 90]
    assert teaching_case(initial, "4").current_A == -5
    assert teaching_case(initial, "5").current_A == 0
    assert teaching_case(initial, "6").field_strength_T == 0
    with pytest.raises(ValueError):
        teaching_case(initial, "7")
